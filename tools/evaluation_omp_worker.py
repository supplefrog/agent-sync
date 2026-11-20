"""Run one stock OMP RPC turn in the isolated evaluator's no-tools lane."""
from __future__ import annotations

import hashlib
import json
import os
import queue
import re
import sqlite3
import subprocess
import threading
import time
from contextlib import closing
from pathlib import Path

import yaml


SYSTEM_PROMPT = "Follow the supplied evaluation task. Return only the requested answer."
NATIVE_PROJECT_PROMPT = (
    "\n</workstation>\n</project-context>\n\n<critical>\n"
    "- Each response MUST advance the task; completion only stopping condition.\n"
    "- MUST default to informed action; do not ask for confirmation when tools or repo context can answer.\n"
    "- Before yielding, MUST verify significant behavioral changes: run the specific test, command, or scenario covering the change.\n"
    "</critical>"
)
OMP_FLAGS = (
    "--no-tools", "--no-skills", "--no-rules", "--no-context-files", "--no-session",
    "--no-extensions", "--no-title", "--no-prewalk", "--no-lsp", "--no-pty", "--offline",
)
OMP_CONTROLS = {
    "adapter": "native-omp-stdio-rpc", "ignore_user_config": True, "fresh_user_home": True,
    "fresh_runtime_home": True, "session_logging": "disabled", "active_tools": "none",
    "credential_refresh": "no-refresh-token-copied",
}


def stage_omp_auth(exe, source, env, fixture, provider, timeout):
    """Project only the evaluated OMP account's unexpired access credential."""
    home = Path(source.get("USERPROFILE") or source.get("HOME") or Path.home())
    agent = Path(source.get("PI_CODING_AGENT_DIR") or home / ".omp" / "agent").resolve()
    database = agent / "agent.db"
    selectors = ("OMP_AUTH_BROKER_URL", "OMP_PROFILE", "PI_PROFILE", "PI_CONFIG_DIR", "PI_CONFIG_FILES")
    if any(source.get(key) for key in selectors) or (os.name != "nt" and source.get("XDG_DATA_HOME")):
        raise ValueError("OMP evaluation requires the local credential store for the selected account")
    routing_keys = {*selectors, "PI_CODING_AGENT_DIR", "OMP_CODING_AGENT_DIR",
                    "OMP_CONFIG_DIR", "OMP_CONFIG_FILES", "XDG_DATA_HOME"}
    for directory in {home, home / ".omp", agent}:
        path = directory / ".env"
        if path.is_file():
            defined = re.findall(r"(?m)^[ \t]*(?:export[ \t]+)?([A-Za-z_][\w]*)[ \t]*[=:]",
                                 path.read_text(encoding="utf-8-sig"))
            if routing_keys.intersection(key.upper() for key in defined):
                raise ValueError("OMP evaluation cannot resolve credential routing from dotenv files")
    for filename in ("config.yml", "config.yaml"):
        config_path = agent / filename
        if config_path.is_file():
            config = yaml.safe_load(config_path.read_text(encoding="utf-8-sig")) or {}
            auth = config.get("auth") or {}
            if any(key.startswith("auth.broker") for key in config) or auth.get("broker"):
                raise ValueError("OMP evaluation does not project a broker-managed credential")
    expires_after = int((time.time() + timeout + 300) * 1000)
    with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True, timeout=5)) as store:
        accounts = store.execute(
            """SELECT json_extract(data, '$.access'), json_extract(data, '$.expires'),
                      json_extract(data, '$.accountId')
               FROM auth_credentials
               WHERE provider = ? AND credential_type = 'oauth' AND disabled_cause IS NULL
                 AND json_type(data, '$.expires') IN ('integer', 'real')
                 AND json_extract(data, '$.expires') > ?
               LIMIT 2""",
            (provider, expires_after),
        ).fetchall()
    if len(accounts) != 1 or not isinstance(accounts[0][0], str) or not accounts[0][0]:
        raise ValueError("OMP evaluation needs one ready OAuth login for this provider")
    access, expires, account_id = accounts[0]
    credential = {"type": "oauth", "access": access, "expires": expires, "refresh": ""}
    if isinstance(account_id, str) and account_id:
        credential["accountId"] = account_id
    request = json.dumps({"version": 1, "credentials": [{"provider": provider, "credential": credential}]})
    result = subprocess.run([exe, "auth", "import", "-"], cwd=fixture, env=env, input=request,
                            capture_output=True, text=True, encoding="utf-8", timeout=15, check=False)
    if result.returncode:
        raise ValueError("Native OMP rejected the disposable provider login")


def _state_evidence(state):
    model = state.get("model") or {}
    return {
        "model": model.get("id"), "provider": model.get("provider"),
        "reasoning": state.get("thinkingLevel"), "session_id": state.get("sessionId"),
        "session_persisted": bool(state.get("sessionFile")),
        "system_prompt": state.get("systemPrompt"), "tools": state.get("dumpTools"),
        "message_count": state.get("messageCount"), "settled": state.get("isSettled"),
        "pending_work": state.get("hasPendingAsyncWork"), "goal": state.get("goal"),
    }


def _checked_state(state, requested, count):
    prompt = state.get("system_prompt")
    route = re.escape(f"{requested['provider']}/{requested['model']}")
    native_context = (r"<project-context>\n<workstation>\n- OS: [a-z0-9 ._+-]{1,80}\n"
                      r"- Arch: [a-z0-9_-]{1,16}\n- Model: " + route + re.escape(NATIVE_PROJECT_PROMPT))
    valid_prompt = (isinstance(prompt, list) and len(prompt) == 2 and prompt[0] == SYSTEM_PROMPT
                    and isinstance(prompt[1], str) and re.fullmatch(native_context, prompt[1]) is not None)
    return (valid_prompt and state.get("tools") == [] and state.get("session_persisted") is False
            and state.get("settled") is True and state.get("pending_work") is False
            and state.get("goal") is None and state.get("message_count") == count
            and isinstance(state.get("session_id"), str) and bool(state["session_id"])
            and all(state.get(key) == requested[key] for key in ("model", "provider", "reasoning")))


def evaluate_evidence(evidence, requested):
    before, after, result = (evidence.get(key, {}) for key in ("before", "after", "result"))
    counts = evidence.get("events", {})
    isolated = _checked_state(before, requested, 0)
    observations = {"source": "native-omp-rpc", "tool_activity_count": counts.get("tools"),
                    "tool_schema_absence_verified": False, "ok": counts.get("tools") == 0}
    isolation = {"source": "native-omp-get-state", "verified": isolated,
                 "sha256": hashlib.sha256("\n\n".join(before["system_prompt"]).encode()).hexdigest() if isolated else None,
                 "contamination": [], "native_tool_names": [] if isolated else None,
                 "tool_schema_absence_verified": False}
    observed = {key: after.get(key) for key in ("model", "provider", "reasoning")}
    observed["tool_calls_count"] = counts.get("tools")
    output = result.get("output")
    success = (isolated and _checked_state(after, requested, 2)
               and after["session_id"] == before["session_id"]
               and counts == {"starts": 1, "ends": 1, "tools": 0, "settled": 1}
               and result.get("status") == "completed" and result.get("agent_invoked") is True
               and result.get("stop_reason") == "stop" and isinstance(output, str) and bool(output)
               and result.get("model") == requested["model"] and result.get("provider") == requested["provider"])
    errors = [] if success else ["OMP RPC prompt, route, tool boundary, or terminal result did not match"]
    return {
        "output": output or "",
        "route_attestation": {"requested": requested, "observed": observed, "ok": success,
                              "errors": errors, "source": "native-omp-rpc",
                              "provider_resolved_identity_verified": False},
        "tool_observation": observations, "prompt_isolation": isolation,
    }


class OmpRpc:
    """Keep the preflight and inference inside one owned native process."""

    def __init__(self, command, fixture, env, timeout, strict_json):
        self.process = subprocess.Popen(command, cwd=fixture, env=env, stdin=subprocess.PIPE,
                                        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, encoding="utf-8")
        self.deadline = time.monotonic() + timeout
        self.strict_json = strict_json
        self.events = {"starts": 0, "ends": 0, "tools": 0, "settled": 0}
        self.lines = queue.Queue()
        self.reader = threading.Thread(target=self.read, daemon=True)
        self.reader.start()

    def read(self):
        try:
            for _ in range(8192):
                line = self.process.stdout.readline(2_000_001)
                if not line or len(line) > 2_000_000:
                    return
                self.lines.put(line)
        finally:
            self.lines.put(None)

    def next(self):
        try:
            raw = self.lines.get(timeout=max(0, self.deadline - time.monotonic()))
        except queue.Empty as exc:
            raise TimeoutError("OMP RPC attempt exceeded its deadline") from exc
        if raw is None:
            raise ValueError("OMP RPC stream ended before terminal evidence")
        event = self.strict_json(raw)
        kind = event.get("type")
        if kind == "agent_start":
            self.events["starts"] += 1
        elif kind == "agent_end":
            self.events["ends"] += 1
        elif kind == "session_settled":
            self.events["settled"] += 1
        elif isinstance(kind, str) and kind.startswith(("tool_execution_", "host_tool_")):
            self.events["tools"] += 1
            raise ValueError("OMP attempted tool execution in the no-tools lane")
        return event

    def request(self, kind, request_id, **fields):
        self.process.stdin.write(json.dumps({"type": kind, "id": request_id, **fields}) + "\n")
        self.process.stdin.flush()
        while True:
            row = self.next()
            if row.get("type") == "response" and row.get("id") == request_id:
                if row.get("command") != kind or row.get("success") is not True:
                    raise ValueError("OMP RPC rejected the evaluation command")
                return row.get("data", {})

    def close(self):
        try:
            self.process.stdin.close()
        except BrokenPipeError:
            pass
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=5)
        self.reader.join(timeout=5)
        self.process.stdout.close()


def run_omp(exe, prompt, fixture, env, timeout, requested, strict_json):
    route = f"{requested['provider']}/{requested['model']}"
    command = [exe, "--mode", "rpc", *OMP_FLAGS, "--system-prompt", SYSTEM_PROMPT,
               "--model", route, "--thinking", requested["reasoning"]]
    rpc = OmpRpc(command, fixture, env, timeout, strict_json)
    try:
        before = _state_evidence(rpc.request("get_state", "eval-preflight"))
        if not _checked_state(before, requested, 0):
            raise ValueError("OMP preflight rejected the effective route, prompt or tools")
        rpc.request("prompt", "eval-turn", message=prompt)
        terminal = None
        while True:
            row = rpc.next()
            if row.get("type") == "prompt_result" and row.get("id") == "eval-turn":
                terminal = row
            if rpc.events["settled"]:
                break
        after = _state_evidence(rpc.request("get_state", "eval-readback"))
        messages = rpc.request("get_messages", "eval-output").get("messages", [])
        if (len(messages) != 2 or messages[0].get("role") != "user"
                or messages[1].get("role") != "assistant"):
            raise ValueError("OMP did not record exactly one user turn and assistant result")
        user_content = messages[0].get("content")
        if user_content != prompt and user_content != [{"type": "text", "text": prompt}]:
            raise ValueError("OMP did not record the exact submitted evaluation prompt")
        assistant = messages[1]
        content = assistant.get("content", [])
        if any(part.get("type") not in {"text", "thinking"} for part in content):
            raise ValueError("OMP result contains unexpected blocks")
        output = "\n".join(part["text"] for part in content if part["type"] == "text").strip()
        terminal = terminal or {}
        evidence = {
            "before": before, "after": after, "events": rpc.events,
            "result": {"status": terminal.get("status"), "agent_invoked": terminal.get("agentInvoked"),
                       "stop_reason": assistant.get("stopReason"), "model": assistant.get("model"),
                       "provider": assistant.get("provider"), "output": output,
                       "usage": {key: assistant.get("usage", {}).get(key)
                                 for key in ("input", "output", "cacheRead", "cacheWrite", "totalTokens")}},
        }
    finally:
        rpc.close()
    return {"evidence": evidence, "returncode": rpc.process.returncode, **evaluate_evidence(evidence, requested)}
