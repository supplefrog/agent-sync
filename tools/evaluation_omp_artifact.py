"""Tool-enabled, single-session OMP measurements for the staged artifact pilot."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import tempfile

from evaluation_omp_worker import OMP_FLAGS, OmpRpc, _state_evidence, stage_omp_auth
from evaluation_runtime import runtime_environment

TOOLS = frozenset({"read", "write", "edit", "bash"})
FLAGS = tuple(flag for flag in OMP_FLAGS if flag not in {"--no-tools", "--no-skills"})


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def run_trial(executable, job, spec):
    fixture = Path(job["fixture"])
    route = {key: spec[key] for key in ("model", "provider", "reasoning")}
    source = dict(os.environ)
    with tempfile.TemporaryDirectory(prefix="omp-artifact-") as directory:
        state = Path(directory)
        env = runtime_environment(source, state)
        env["PI_CODING_AGENT_DIR"] = str(state / "omp")
        stage_omp_auth(executable, source, env, fixture, route["provider"], spec["timeout"])
        if spec.get("quota_remaining") is None:
            raise ValueError("No observed subscription quota for the selected OMP route")
        return run_rpc(executable, job["prompt"], fixture, env, route, spec["timeout"], job["catalog"])


def run_rpc(executable, prompt, fixture, env, route, timeout, catalog):
    """Collect bounded native evidence. The caller owns the isolated auth lifetime."""
    expected = {Path(path).parent.name: Path(path).read_text(encoding="utf-8").rstrip("\n") for path in catalog}
    seen_lines = {name: set() for name in expected}
    name = f"{route['provider']}/{route['model']}"
    command = [executable, "--mode", "rpc", *FLAGS, "--tools", ",".join(sorted(TOOLS)),
               "--model", name, "--thinking", route["reasoning"]]
    calls = {}
    raw_ranges = {}

    def observe(event):
        kind, tool, ident = (event.get(key) for key in ("type", "toolName", "toolCallId"))
        if tool not in TOOLS or not isinstance(ident, str) or len(calls) >= 256 and ident not in calls:
            raise ValueError("Unexpected OMP tool activity")
        if kind == "tool_execution_start" and ident not in calls:
            args = event.get("args") or {}
            path = args.get("path") if isinstance(args, dict) else None
            selected = None
            if tool == "read" and isinstance(path, str):
                for item in catalog:
                    target = Path(item)
                    source_path = re.sub(r"(?::raw|:\d+(?:-\d+)?)++$", "", path)
                    if source_path == f"skill://{target.parent.name}" or (fixture / source_path).resolve() == target:
                        selected = target.parent.name
                        selector = path[len(source_path):]
                        raw_range = re.fullmatch(r":raw:(\d+)-(\d+)", selector)
                        if raw_range:
                            raw_ranges[ident] = tuple(map(int, raw_range.groups()))
                        break
            calls[ident] = {"tool_call_id": ident, "tool": tool, "skill": selected, "finished": False}
        elif kind == "tool_execution_end" and ident in calls and calls[ident]["tool"] == tool and not calls[ident]["finished"]:
            row = calls[ident]
            result = event.get("result") or {}
            body = expected.get(row["skill"])
            content = result.get("content", []) if isinstance(result, dict) else []
            succeeded = event.get("isError") is False
            observed = set()
            if succeeded and body:
                for block in content:
                    if block.get("type") == "text":
                        observed.update(read_lines(body, block["text"], raw_ranges.get(ident)))
                seen_lines[row["skill"]].update(observed)
            row.update(finished=True, succeeded=succeeded, verified_skill_lines=len(observed))
        elif kind != "tool_execution_update" or ident not in calls:
            raise ValueError("OMP tool start and completion do not match")

    rpc = OmpRpc(command, fixture, env, timeout, json.loads, tool_event=observe)
    try:
        before = _state_evidence(rpc.request("get_state", "artifact-preflight"))
        commands = rpc.request("get_available_commands", "artifact-catalog")["commands"]
        found = sorted(row["name"] for row in commands if row["source"] == "skill")
        tools = before["tools"] or []
        if (found != [f"skill:{key}" for key in sorted(expected)]
                or len(tools) != len(TOOLS) or {row["name"] for row in tools} != TOOLS
                or not checked_state(before, route) or before["message_count"] != 0
                or any(body in "\n".join(before["system_prompt"]) for body in expected.values())):
            raise ValueError("OMP preflight rejected the route, tool set, skill catalog or session")
        rpc.request("set_auto_retry", "artifact-no-retry", enabled=False)
        rpc.request("prompt", "artifact-turn", message=prompt)
        terminal = None
        while not rpc.events["settled"]:
            event = rpc.next()
            if event.get("type") == "prompt_result" and event.get("id") == "artifact-turn":
                terminal = event
        after = _state_evidence(rpc.request("get_state", "artifact-final"))
        messages = rpc.request("get_messages", "artifact-output")["messages"]
        user_messages = [message["content"] for message in messages if message["role"] == "user"]
        assistants = [message for message in messages if message["role"] == "assistant"]
        final = assistants[-1] if assistants else {}
        loaded = sorted(name for name, lines in seen_lines.items() if len(lines) == len(expected[name].split("\n")))
        usage = {key: [msg.get("usage", {}).get(key) for msg in assistants]
                 for key in ("input", "output", "cacheRead", "cacheWrite", "totalTokens")}
        completed = bool(terminal and terminal.get("status") == "completed" and terminal.get("agentInvoked") is True
                         and checked_state(after, route) and after["session_id"] == before["session_id"]
                         and digest(after["tools"]) == digest(tools)
                         and rpc.events["starts"] == rpc.events["ends"] == rpc.events["settled"] == 1
                         and user_messages in ([prompt], [[{"type": "text", "text": prompt}]])
                         and final.get("stopReason") == "stop"
                         and all(msg.get("model") == route["model"] and msg.get("provider") == route["provider"]
                                 for msg in assistants) and all(row["finished"] for row in calls.values()))
        exercised = any(row.get("succeeded") and row["tool"] in {"write", "edit", "bash"} for row in calls.values())
        result = {"ok": completed and exercised and loaded == sorted(expected), "completed": completed,
                  "route": route, "tool_schema_sha256": digest(tools), "tool_events": list(calls.values()),
                  "catalog": found, "skill_bodies_read": loaded, "usage": usage,
                  "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
                  "provider_resolved_identity_verified": False}
    finally:
        rpc.close()
    result["process_exit_code"] = rpc.process.returncode
    result["ok"] = result["ok"] and rpc.process.returncode == 0
    return result


def read_lines(body, output, raw_range=None):
    """Verify native full-text or numbered read results against the frozen entry."""
    lines = body.split("\n")
    output = output.replace("\r\n", "\n")
    if body in output:
        return set(range(1, len(lines) + 1))
    if raw_range:
        start, end = raw_range
        if 1 <= start <= end <= len(lines) and output.rstrip("\n") == "\n".join(lines[start - 1:end]).rstrip("\n"):
            return set(range(start, end + 1))
    observed = set()
    for line in output.splitlines():
        match = re.fullmatch(r"\s*(\d+):(.*)", line)
        if match:
            number = int(match[1])
            if 0 < number <= len(lines) and match[2] == lines[number - 1]:
                observed.add(number)
    return observed


def checked_state(state, route):
    return (all(state.get(key) == value for key, value in route.items())
            and state["settled"] is True and state["pending_work"] is False
            and state["session_persisted"] is False and state["goal"] is None
            and bool(state["session_id"]) and isinstance(state["system_prompt"], list)
            and all(isinstance(part, str) for part in state["system_prompt"]))
