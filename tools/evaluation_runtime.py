"""Disposable native runtimes for inline-text, no-tools evaluations only."""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Callable

CODEX_DISABLED_FEATURES = (
    "memories", "hooks", "apps", "plugins", "remote_plugin", "skill_search",
    "multi_agent", "shell_tool", "browser_use", "computer_use", "view_image",
    "image_generation", "workspace_dependencies", "code_mode_host", "sleep_tool",
    "goals", "tool_suggest", "unbounded_connection_retries",
)
CONTEXT_MARKERS = ("<skills_instructions>", "# AGENTS.md instructions", "MEMORY_SUMMARY",
                   "[INSTRUCTION-AUTHORING]", "[RECONCILIATION]")
SYSTEM_ENV_KEYS = {
    "PATH", "SYSTEMROOT", "WINDIR", "COMSPEC", "PATHEXT", "SYSTEMDRIVE",
    "PROGRAMFILES", "PROGRAMFILES(X86)", "PROGRAMW6432", "PROGRAMDATA",
    "PROCESSOR_ARCHITECTURE", "NUMBER_OF_PROCESSORS", "SSL_CERT_FILE", "SSL_CERT_DIR",
    "REQUESTS_CA_BUNDLE", "CURL_CA_BUNDLE",
    "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY",
}


def supported_lane(agent: str, provider: str | None, tool_policy: str, full_tools: bool) -> None:
    if tool_policy != "none" or full_tools:
        raise ValueError("unsupported evaluator tool policy: this inline-text lane requires none and full_tools=False")
    providers = {"codex": {"openai", "openai-codex"}, "hermes": {"openai-codex"}}
    if provider not in providers.get(agent, set()):
        raise ValueError("unsupported evaluator provider: only the built-in OpenAI/Codex route is implemented")


def runtime_environment(source: dict[str, str], root: Path) -> dict[str, str]:
    """Do not inherit provider secrets, host connectors, profiles, or agent state."""
    env = {key: value for key, value in source.items() if key.upper() in SYSTEM_ENV_KEYS}
    home, codex, hermes, scratch = (root / name for name in ("home", "codex", "hermes", "tmp"))
    for path in (home, codex, hermes, scratch, home / "AppData" / "Local", home / "AppData" / "Roaming"):
        path.mkdir(parents=True, exist_ok=True)
    env.update(HOME=str(home), USERPROFILE=str(home), CODEX_HOME=str(codex), HERMES_HOME=str(hermes),
               TEMP=str(scratch), TMP=str(scratch), TMPDIR=str(scratch),
               LOCALAPPDATA=str(home / "AppData" / "Local"), APPDATA=str(home / "AppData" / "Roaming"),
               HERMES_SAFE_MODE="1", HERMES_IGNORE_USER_CONFIG="1", HERMES_IGNORE_RULES="1",
               HERMES_DISABLE_LAZY_INSTALLS="1",
               PYTHONIOENCODING="utf-8", PYTHONUTF8="1", NO_COLOR="1")
    return env


def _token_projection(tokens: Any) -> dict[str, str]:
    if not isinstance(tokens, dict):
        return {}
    return {key: value for key, value in tokens.items()
            if key in {"access_token", "refresh_token", "id_token", "account_id"} and isinstance(value, str)}


def stage_auth(agent: str, source: dict[str, str], env: dict[str, str]) -> None:
    """Codex alone uses disposable auth storage; Hermes resolves in its child."""
    if agent != "codex":
        raise ValueError("Hermes uses its native access-token resolver in memory; credential copying is unsupported")
    home = Path(source.get("USERPROFILE") or source.get("HOME") or Path.home())
    codex_path = Path(source.get("CODEX_HOME") or home / ".codex") / "auth.json"
    if not codex_path.is_file():
        raise ValueError("OpenAI/Codex credentials are unavailable for the isolated evaluator")
    store = json.loads(codex_path.read_text(encoding="utf-8-sig"))
    tokens = _token_projection(store.get("tokens"))
    payload = {key: store[key] for key in ("auth_mode", "OPENAI_API_KEY", "last_refresh") if key in store}
    if tokens:
        payload["tokens"] = tokens
    if not tokens.get("access_token") and not payload.get("OPENAI_API_KEY"):
        raise ValueError("OpenAI/Codex credentials are unavailable for the isolated evaluator")
    destination = Path(env["CODEX_HOME"]) / "auth.json"
    destination.write_text(json.dumps(payload), encoding="utf-8")
    destination.chmod(0o600)


def hermes_owner_home(source: dict[str, str]) -> Path:
    home = Path(source.get("USERPROFILE") or source.get("HOME") or Path.home())
    default = Path(source.get("LOCALAPPDATA") or home / "AppData" / "Local") / "hermes" if os.name == "nt" else home / ".hermes"
    return Path(source.get("HERMES_HOME") or default)


def native_hermes_runtime(exe: str) -> tuple[Path, Path]:
    """Resolve the installed native source and its interpreter, not user config."""
    executable = Path(exe).resolve()
    for source in (executable.parent.parent / "hermes-agent", executable.parent.parent.parent):
        if not (source / "run_agent.py").is_file() or not (source / "hermes_cli" / "auth_codex.py").is_file():
            continue
        for python in (source / ".venv" / "Scripts" / "python.exe", source / ".venv" / "bin" / "python"):
            if python.is_file():
                return python, source
    raise ValueError("native Hermes source/interpreter unavailable for the isolated API worker")


def native_executable(agent: str) -> str | None:
    return shutil.which("codex.exe" if os.name == "nt" and agent == "codex" else agent)


def native_version(agent: str) -> dict[str, Any]:
    """Probe native bookkeeping in a sanitized, bounded, disposable lifetime."""
    root = Path(tempfile.mkdtemp(prefix="agent-signal-version-"))
    fixture = root / "fixture"
    fixture.mkdir()
    state = root / "runtime"
    receipt = {"version": "unavailable", "ok": False, "source": "native-cli-version", "errors": []}
    try:
        env = runtime_environment(dict(os.environ), state)
        exe = native_executable(agent)
        if not exe:
            receipt["errors"].append("native executable unavailable")
        else:
            result = subprocess.run([exe, "--version"], env=env, cwd=fixture, capture_output=True,
                                    text=True, encoding="utf-8", timeout=10, check=False)
            # Never retain arbitrary wrapper/diagnostic output. Recognize only
            # bounded product/version lines and reject conflicting versions.
            pattern = re.compile(r"(?i)^(?:codex(?:-cli)?|hermes(?: agent|-agent|-cli)?)(?: version)?\s+v?(\d+\.\d+\.\d+(?:[-+][A-Za-z0-9._-]{1,48})?)(?=\s|$)")
            versions = {match.group(1) for line in (result.stdout or "").splitlines()
                        if len(line) <= 128 and (match := pattern.match(line.strip()))}
            if result.returncode == 0 and len(versions) == 1:
                receipt.update(version=f"{agent} {next(iter(versions))}", ok=True)
            else:
                receipt["errors"].append("native version output unavailable or unrecognized")
    except Exception as exc:
        receipt["errors"].append(f"native version probe failed: {type(exc).__name__}")
    finally:
        receipt["cleanup"] = cleanup_runtime(state, fixture) if state.exists() else {"credentials_removed": True, "state_removed": True, "errors": []}
        try:
            shutil.rmtree(root)
        except OSError as exc:
            receipt["errors"].append(f"version workspace cleanup failed: {type(exc).__name__}")
        receipt["retained_path"] = str(root) if root.exists() else None
        receipt["ok"] = receipt["ok"] and not receipt["cleanup"]["errors"] and not receipt["errors"]
    return receipt


def native_transport_failure(error: Any) -> dict[str, Any]:
    """Project trusted native transport fields; model answer text is excluded."""
    error = error if isinstance(error, dict) else {}
    nested = error.get("error") if isinstance(error.get("error"), dict) else {}
    status = error.get("http_status", error.get("status_code", nested.get("http_status", nested.get("status_code"))))
    code = error.get("code", nested.get("code"))
    status = status if type(status) is int else None
    code = code if isinstance(code, str) else None
    transient_codes = {"rate_limit_exceeded", "server_error", "overloaded", "service_unavailable", "temporarily_unavailable"}
    permanent_codes = {"insufficient_quota", "invalid_api_key", "authentication_error", "permission_denied", "context_length_exceeded", "invalid_request_error"}
    data = {"source": "native-transport"}
    if type(status) is int and 100 <= status <= 599:
        data["http_status"] = status
    if code in transient_codes | permanent_codes:
        data["code"] = code
    if code not in permanent_codes and (status in {429, 502, 503, 504} or code in transient_codes):
        return {"kind": "provider-transient", **data}
    if "http_status" in data or code in permanent_codes:
        return {"kind": "provider-permanent", **data}
    return {"kind": "runtime", "source": "runtime-control", "code": "unclassified-native-error"}


def codex_common(fixture: Path, model: str, reasoning: str) -> list[str]:
    args = ["-C", str(fixture), "-m", model]
    for setting in (f"model_reasoning_effort={json.dumps(reasoning)}", 'model_provider="openai"',
                    "project_doc_max_bytes=0", 'personality="none"', 'web_search="disabled"',
                    'approval_policy="never"'):
        args += ["-c", setting]
    for feature in CODEX_DISABLED_FEATURES:
        args += ["--disable", feature]
    return args


def codex_preflight(exe: str, common: list[str], env: dict[str, str], fixture: Path,
                    source: dict[str, str]) -> tuple[list[str], dict[str, Any]]:
    """Bootstrap bundled skills, disable shared/system skills, then inspect input."""
    def probe(arguments: list[str]) -> subprocess.CompletedProcess:
        result = subprocess.run([exe, *arguments, "debug", "prompt-input", "EVALUATOR_ISOLATION_PROBE"],
                                env=env, cwd=fixture, capture_output=True, text=True, encoding="utf-8", timeout=60)
        if result.returncode:
            raise ValueError("Codex prompt-input isolation probe failed")
        return result

    probe(common)
    homes = {Path.home(), Path(source.get("USERPROFILE") or source.get("HOME") or Path.home())}
    roots = [Path(env["CODEX_HOME"]) / "skills", *(home / ".agents" / "skills" for home in homes),
             *(home / ".codex" / "skills" for home in homes)]
    paths = sorted({path.resolve().as_posix() for root in roots if root.is_dir() for path in root.rglob("SKILL.md")})
    disabled = "skills.config=[" + ",".join("{path=" + json.dumps(path) + ",enabled=false}" for path in paths) + "]"
    checked = [*common, "-c", disabled]
    result = probe(checked)
    items = json.loads(result.stdout)
    if not isinstance(items, list) or not items:
        raise ValueError("Codex prompt-input probe returned no assembled context")
    texts = [part["text"] for item in items for part in item.get("content", []) if isinstance(part.get("text"), str)]
    contamination = [marker for marker in CONTEXT_MARKERS if any(marker in value for value in texts)]
    if contamination:
        raise ValueError("Codex prompt-input isolation failed: personal instruction or skill context remains")
    return checked, {"verified": True, "source": "codex-debug-prompt-input",
                     "sha256": hashlib.sha256(result.stdout.encode("utf-8")).hexdigest(),
                     "disabled_skill_count": len(paths), "contamination": contamination,
                     "tool_schema_absence_verified": False}


def codex_events(text: str, strict_json: Callable[[str], dict], expected_output: str | None = None) -> dict[str, Any]:
    """Accept a complete native text-only event stream; unknown item kinds fail."""
    rows, errors, tool_ids = [], [], set()
    structural_errors, diagnostics, native_failures = [], [], []
    phase, started, completed = "initial", 0, 0
    completed_items, started_items, answers = set(), set(), []
    disabled_mode_message = "Code Mode is unavailable because code-mode host is disabled. Code mode will fail closed; enable `features.code_mode_host` and install `codex-code-mode-host`."
    allowed_events = {"thread.started", "turn.started", "turn.completed", "turn.failed", "error",
                      "item.started", "item.updated", "item.completed"}
    for index, line in enumerate(text.splitlines()):
        if not line.strip():
            continue
        try:
            row = strict_json(line)
        except ValueError:
            structural_errors.append(f"invalid native event at line {index + 1}")
            continue
        rows.append(row)
        kind = row.get("type")
        if not isinstance(kind, str):
            structural_errors.append("native event has no typed event name")
            continue
        if kind not in allowed_events:
            structural_errors.append(f"unsupported native event type: {kind}")
        if kind == "thread.started":
            if phase != "initial":
                structural_errors.append("native thread started out of order")
            phase = "thread"
        elif kind == "turn.started":
            if phase != "thread":
                structural_errors.append("native turn started out of order")
            started += 1
            phase = "turn"
        elif kind == "turn.completed":
            if phase != "turn" or not answers:
                structural_errors.append("native turn completed before its start or final answer")
            completed += 1
            phase = "ended"
        elif kind in {"turn.failed", "error"}:
            errors.append("native turn failed" if kind == "turn.failed" else "native error event")
            if kind == "error" or any(key in row for key in ("error", "code", "http_status", "status_code")):
                native_failures.append(native_transport_failure(row))
            if kind == "turn.failed":
                phase = "ended"
        if kind in {"item.started", "item.updated", "item.completed"}:
            item = row.get("item")
            if not isinstance(item, dict):
                structural_errors.append("native event has no structured item")
                continue
            if (kind == "item.completed" and item.get("type") == "error" and phase == "thread"
                    and item.get("message") == disabled_mode_message and not diagnostics):
                diagnostics.append("code-mode-host-disabled")
                continue
            if phase != "turn":
                structural_errors.append("native item arrived outside the active turn")
            item_id = item.get("id")
            valid_item_id = isinstance(item_id, str) and bool(item_id)
            if not valid_item_id:
                structural_errors.append("native item has no identity")
            elif kind == "item.started":
                if item_id in started_items or item_id in completed_items:
                    structural_errors.append("native item started more than once or after completion")
                started_items.add(item_id)
            elif item_id in completed_items:
                structural_errors.append("native item changed after completion")
            if kind == "item.completed" and valid_item_id:
                completed_items.add(item_id)
            if not isinstance(item.get("type"), str):
                structural_errors.append("native item has no typed item name")
                continue
            if item.get("type") == "error":
                errors.append("native error item")
                native_failures.append(native_transport_failure(item))
            elif item.get("type") not in {"reasoning", "agent_message"}:
                tool_ids.add(str(item.get("id", index)))
            elif item.get("type") == "agent_message" and kind == "item.completed":
                if not isinstance(item.get("text"), str):
                    structural_errors.append("native answer has no text")
                elif item.get("phase") in (None, "final_answer", "final"):
                    answers.append(item["text"])
    thread_ids = [row.get("thread_id") for row in rows if row.get("type") == "thread.started"]
    if len(thread_ids) != 1 or not isinstance(thread_ids[0], str) or not re.fullmatch(r"[a-f0-9-]{36}", thread_ids[0]):
        errors.append("native event stream has no unique thread identity")
    complete = started == 1 and completed == 1 and bool(answers) and phase == "ended"
    if not complete:
        errors.append("native event stream has no completed turn")
    if tool_ids:
        errors.append("native event stream contains tool activity or unsupported items")
    final_response = answers[-1] if answers else None
    output_match = expected_output.strip() == final_response.strip() if expected_output is not None and final_response is not None else None
    if expected_output is not None and output_match is not True:
        errors.append("native final answer differs from output file")
    errors.extend(structural_errors)
    failure = None
    if errors:
        if tool_ids:
            failure = {"kind": "tool", "source": "runtime-control", "code": "prohibited-native-tool-activity"}
        elif structural_errors:
            failure = {"kind": "runtime", "source": "runtime-control", "code": "invalid-native-event-sequence"}
        elif native_failures:
            failure = next((item for item in native_failures if item["kind"] != "provider-transient"), native_failures[0])
        else:
            failure = {"kind": "runtime", "source": "runtime-control", "code": "incomplete-native-evidence"}
    return {"ok": not errors, "errors": errors, "thread_id": thread_ids[0] if len(thread_ids) == 1 else None,
            "event_stream_complete": complete, "tool_activity_count": len(tool_ids),
            "events": rows, "source": "codex-json-events", "tool_schema_absence_verified": False,
            "final_response": final_response, "output_match": output_match, "diagnostics": diagnostics, "failure": failure}


def codex_metadata(state: Path, thread_id: str | None, requested: dict[str, str],
                   strict_json: Callable[[str], dict]) -> dict[str, Any]:
    """Read only the exact new thread's metadata inside its disposable home."""
    observed: dict[str, Any] = {}
    errors = []
    if not thread_id or not re.fullmatch(r"[a-f0-9-]{36}", thread_id):
        return {"requested": requested, "observed": observed, "ok": False, "errors": ["native thread identity missing"]}
    files = list((state / "sessions").rglob(f"*{thread_id}.jsonl"))
    if len(files) != 1:
        errors.append("exact native rollout metadata unavailable")
    else:
        metadata, contexts = [], []
        for line in files[0].read_text(encoding="utf-8").splitlines():
            row = strict_json(line)
            payload = row.get("payload", {})
            if row.get("type") == "session_meta":
                metadata.append(payload)
            elif row.get("type") == "turn_context":
                contexts.append(payload)
        if len(metadata) != 1 or metadata[0].get("id") != thread_id or not contexts:
            errors.append("native rollout metadata does not match the exact new thread")
        else:
            providers = {metadata[0].get("model_provider")}
            models = {context.get("model") for context in contexts}
            efforts = {context.get("effort") for context in contexts}
            observed = {"provider": next(iter(providers)) if len(providers) == 1 else None,
                        "model": next(iter(models)) if len(models) == 1 else None,
                        "reasoning": next(iter(efforts)) if len(efforts) == 1 else None}
            for key in ("model", "provider", "reasoning"):
                expected = "openai" if key == "provider" else requested[key]
                if observed[key] != expected:
                    errors.append(f"native {key} metadata missing or mismatched")
    return {"requested": requested, "observed": observed, "ok": not errors, "errors": errors,
            "source": "native-runtime-metadata", "provider_resolved_identity_verified": False}


def cleanup_runtime(root: Path, fixture: Path) -> dict[str, Any]:
    """Delete credential files independently before attempting other state cleanup."""
    root, fixture = root.resolve(), fixture.resolve()
    if root == fixture or root.is_relative_to(fixture):
        raise ValueError("runtime credentials must be outside the model fixture")
    errors = []
    for state in (root / "codex", root / "hermes"):
        try:
            (state / "auth.json").unlink(missing_ok=True)
        except OSError as exc:
            errors.append(f"credential cleanup failed: {type(exc).__name__}")
    credentials_removed = not any((root / state / "auth.json").exists() for state in ("codex", "hermes"))
    try:
        shutil.rmtree(root)
    except OSError as exc:
        errors.append(f"runtime cleanup failed: {type(exc).__name__}")
    return {"credentials_removed": credentials_removed, "state_removed": not root.exists(), "errors": errors}


def run_no_tools(agent: str, prompt: str, fixture: Path, timeout: int, model: str, provider: str,
                 reasoning: str, output_schema: dict | None, require_attestation: bool,
                 strict_json: Callable[[str], dict]) -> dict[str, Any]:
    supported_lane(agent, provider, "none", False)
    # Windows command shims can consult the original LOCALAPPDATA or execute
    # a user PowerShell profile. Resolve the native Codex binary before isolation.
    exe = native_executable(agent)
    if not exe:
        raise ValueError(f"{agent} executable unavailable")
    fixture = fixture.resolve()
    fixture.mkdir(parents=True, exist_ok=True)
    runtime = Path(tempfile.mkdtemp(prefix="agent-signal-runtime-"))
    if runtime.resolve().is_relative_to(fixture):
        raise ValueError("disposable runtime must be outside the model fixture")
    source = dict(os.environ)
    started = time.monotonic()
    requested = {"model": model, "provider": provider, "reasoning": reasoning, "tool_policy": "none"}
    contract = {"lane": "inline-text-no-tools-v1", "tool_policy": "none", "credentials_outside_fixture": True,
                "personal_config_copied": False, "global_session_cleanup_authority": False,
                "credential_owner": agent, "cross_host_credential_fallback": False,
                "tool_schema_absence_verified": False, "controls": {},
                "limitations": ["native runtime metadata does not verify provider-resolved model identity",
                                "disabled execution controls do not prove that all tool schemas are absent",
                                "this lane does not exercise shipped scripts or other tool-dependent behavior"]}
    result = {"ok": False, "execution_ok": False, "operational_ok": True, "failure": None,
              "returncode": None, "seconds": 0.0, "output": "", "stderr": "",
              "session_ids": [], "session_receipt_error": None,
              "route_attestation": {"required": require_attestation, "requested": requested, "observed": {},
                                    "ok": False, "errors": ["runtime did not complete"]},
              "runtime_contract": contract}
    process = None
    contract["phase"] = "setup"
    try:
        env = runtime_environment(source, runtime)
        output_file = fixture / f"last-{time.time_ns()}.txt"
        if agent == "codex":
            common = codex_common(fixture, model, reasoning)
            contract["phase"] = "preflight"
            common, contract["prompt_isolation"] = codex_preflight(exe, common, env, fixture, source)
            contract["controls"] = {"disabled_features": list(CODEX_DISABLED_FEATURES), "project_doc_max_bytes": 0,
                                    "personality": "none", "web_search": "disabled", "model_provider": "openai",
                                    "approval_policy": "never", "sandbox": "read-only", "ignore_user_config": True,
                                    "fresh_user_home": True, "fresh_runtime_home": True, "native_events": "json",
                                    "session_logging": "disposable-home-only"}
            command = [exe, "exec", *common, "--ignore-user-config", "--ignore-rules", "--skip-git-repo-check",
                       "--sandbox", "read-only", "--json", "-o", str(output_file)]
            if output_schema is not None:
                schema_file = fixture / "output-schema.json"
                schema_file.write_text(json.dumps(output_schema), encoding="utf-8")
                command += ["--output-schema", str(schema_file)]
            command.append("-")
            input_text = prompt
        else:
            native_python, native_source = native_hermes_runtime(exe)
            contract["controls"] = {"adapter": "native-AIAgent-API", "safe_mode": True, "toolsets": "none", "ignore_rules": True,
                                    "ignore_user_config": True, "fresh_user_home": True, "fresh_runtime_home": True,
                                    "skip_context_files": True, "skip_memory": True, "load_soul_identity": False,
                                    "skip_background_review": True, "fallback_model": None,
                                    "save_trajectories": False, "credentials_in_memory_only": True,
                                    "credential_refresh_if_expiring": False,
                                    "endpoint": "https://chatgpt.com/backend-api/codex"}
            command = [str(native_python), str(Path(__file__).with_name("evaluation_hermes_worker.py"))]
            input_text = json.dumps({"native_source": str(native_source), "credential_owner_home": str(hermes_owner_home(source)),
                                     "runtime_home": env["HERMES_HOME"], "fixture": str(fixture), "model": model,
                                     "reasoning": reasoning, "timeout": timeout, "prompt": prompt, "output_schema": output_schema})
        if agent == "codex":
            stage_auth(agent, source, env)
        contract["phase"] = "launch"
        process = subprocess.Popen(command, cwd=fixture, env=env,
                                   stdin=subprocess.PIPE if input_text is not None else None,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8")
        timed_out = False
        try:
            stdout, stderr = process.communicate(input=input_text, timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            process.kill()
            stdout, stderr = process.communicate(timeout=30)
        result.update(returncode=None if timed_out else process.returncode, stderr=stderr[-4000:])
        contract["phase"] = "observe"
        if agent == "codex":
            result["output"] = output_file.read_text(encoding="utf-8") if output_file.exists() else ""
            events = codex_events(stdout, strict_json, expected_output=result["output"])
            contract["tool_observation"] = {key: value for key, value in events.items() if key not in {"events", "thread_id"}}
            result["native_events"] = events["events"]
            attestation = codex_metadata(Path(env["CODEX_HOME"]), events["thread_id"], requested, strict_json)
            attestation["observed"]["tool_calls_count"] = events["tool_activity_count"] if events["ok"] else None
            attestation["errors"].extend(events["errors"])
            attestation["ok"] = attestation["ok"] and events["ok"]
            result["failure"] = events["failure"]
            if result["failure"] is None and not attestation["ok"]:
                result["failure"] = {"kind": "route", "source": "runtime-control", "code": "native-route-mismatch"}
        else:
            worker = strict_json(stdout)
            result["failure"] = worker.get("failure")
            if "route_attestation" not in worker:
                raise ValueError("native Hermes worker failed before producing route metadata")
            result["output"] = worker["output"]
            attestation = worker["route_attestation"]
            contract["prompt_isolation"] = worker["prompt_isolation"]
            contract["tool_observation"] = worker["tool_observation"]
            contract["output_source"] = "native-AIAgent-final-response"
            result["native_result_metadata"] = worker.get("native_result_metadata", {})
            native_result = result["native_result_metadata"]
            if (worker.get("ok") is not True or native_result.get("completed") is not True
                    or any(native_result.get(key) for key in ("failed", "partial", "interrupted"))
                    or native_result.get("final_response") != result["output"]):
                attestation["errors"].append("native Hermes completion or final-response evidence is inconsistent")
                attestation["ok"] = False
                if result["failure"] is None:
                    result["failure"] = {"kind": "runtime", "source": "runtime-control", "code": "native-result-mismatch"}
        if timed_out:
            attestation["errors"].append("run timed out")
            attestation["ok"] = False
            result["failure"] = {"kind": "timeout", "source": "runtime-control", "code": "native-attempt-timeout"}
        result["route_attestation"] = {"required": require_attestation, **attestation}
        result["execution_ok"] = not timed_out and process.returncode == 0 and attestation["ok"]
        if result["execution_ok"]:
            contract["phase"] = "complete"
        elif result["failure"] is None:
            result["failure"] = {"kind": "runtime", "source": "runtime-control", "code": "native-execution-failed"}
    except KeyboardInterrupt:
        if process is not None and process.poll() is None:
            process.kill()
            process.communicate(timeout=30)
        raise
    except Exception as exc:
        result["runtime_error"] = f"{type(exc).__name__}: isolated runtime setup or execution failed"
        result["route_attestation"]["errors"] = [result["runtime_error"]]
        if result["failure"] is None:
            result["failure"] = {"kind": "isolation" if contract["phase"] in {"setup", "preflight"} else "runtime",
                                  "source": "runtime-control", "code": type(exc).__name__}
        if process is not None and process.poll() is None:
            process.kill()
            process.communicate(timeout=30)
    finally:
        contract["cleanup"] = cleanup_runtime(runtime, fixture)
        result["operational_ok"] = (contract["cleanup"]["credentials_removed"] is True
                                    and contract["cleanup"]["state_removed"] is True
                                    and not contract["cleanup"]["errors"])
        if not result["operational_ok"] and result["failure"] is None:
            result["failure"] = {"kind": "cleanup", "source": "runtime-control", "code": "native-runtime-cleanup-failed"}
        result["ok"] = result["execution_ok"] and result["operational_ok"]
        result["seconds"] = round(time.monotonic() - started, 3)
    return result


def skill_study_events(text: str, expected_skills: list[str]) -> dict[str, Any]:
    """Native typed tools prove reads; answer prose never proves skill use."""
    rows, errors, calls, loaded, answers = [], [], {}, [], []
    usage = None
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except ValueError:
            errors.append("invalid native JSON event")
            continue
        rows.append(row)
        item = row.get("item", {})
        if row.get("type") == "turn.completed":
            usage = row.get("usage")
        if row.get("type") in {"turn.failed", "error"}:
            errors.append("native execution failed")
        if row.get("type") == "item.completed" and item.get("type") == "agent_message":
            answers.append(item.get("text", ""))
        if item.get("type") == "command_execution":
            calls[item.get("id")] = item
            if row.get("type") == "item.completed" and item.get("exit_code") == 0:
                command = item.get("command", "")
                # A successful native read command with an exact literal path
                # is evidence of body loading. Searches, echoes and near-miss
                # names do not establish that the file was consumed.
                for path in expected_skills:
                    normalized = command.replace("\\", "/")
                    target = path.replace("\\", "/")
                    literal = re.escape(target)
                    paths = [r'"' + literal + r'"', "'" + literal + "'"]
                    if not re.search(r"[\s;&|<>`$\"']", target):
                        paths.append(literal)
                    # Shell compounds, quoted examples and wrappers cannot prove
                    # this particular read succeeded from one command exit code.
                    read = re.fullmatch(r"\s*(?i:Get-Content|cat|type|more)\s+(?:(?i:-Raw)\s+)?"
                        r"(?:(?i:-LiteralPath|-Path)\s+)?(?:" + "|".join(paths) + r")(?:\s+(?i:-Raw))?\s*", normalized)
                    if read:
                        loaded.append({"path": path, "item_id": item.get("id"), "source": "native-command-execution", "exit_code": 0})
    completed = (sum(row.get("type") == "turn.completed" for row in rows) == 1
                 and sum(row.get("type") == "turn.started" for row in rows) == 1
                 and sum(row.get("type") == "thread.started" for row in rows) == 1
                 and rows[-1].get("type") == "turn.completed")
    if not completed or not answers:
        errors.append("missing native completion evidence")
    def token(key):
        value = usage.get(key) if isinstance(usage, dict) else None
        return value if type(value) is int and value >= 0 else None
    return {"ok": not errors, "errors": errors, "events": rows,
            "final_response": answers[-1] if answers else None,
            "tool_calls_count": len(calls), "loaded_skills": loaded,
            "tokens": {"input": token("input_tokens"), "cached_input": token("cached_input_tokens"),
                       "output": token("output_tokens"), "source": "native-turn-completed-usage"},
            "dollars": None, "cost_status": "subscription-dollar-cost-unavailable"}


def skill_study_preflight(exe: str, fixture: Path, env: dict[str, str], source: dict[str, str],
                          expected_skills: list[str]) -> tuple[list[str], dict[str, Any]]:
    common = codex_common(fixture, "gpt-6-sol", "medium")
    common += ["-c", 'default_permissions=":workspace"', "--enable", "shell_tool", "--enable", "code_mode_host"]
    # Preserve shell tools and native discovery while removing unrelated state.
    required_features = {"shell_tool", "code_mode_host"}
    common = [part for index, part in enumerate(common)
              if not ((part in required_features and index > 0 and common[index-1] == "--disable") or (part == "--disable" and index + 1 < len(common) and common[index + 1] in required_features))]
    def probe(args):
        proc = subprocess.run([exe, *args, "debug", "prompt-input", "EVALUATOR_ISOLATION_PROBE"],
                              cwd=fixture, env=env, text=True, encoding="utf-8", capture_output=True, timeout=60)
        if proc.returncode:
            raise ValueError("native skill catalog probe failed")
        return proc.stdout
    probe(common)
    home = Path(source.get("USERPROFILE") or source.get("HOME") or Path.home())
    roots = [Path(env["CODEX_HOME"]) / "skills", home / ".agents" / "skills", home / ".codex" / "skills"]
    disabled = sorted({p.resolve().as_posix() for root in roots if root.is_dir() for p in root.rglob("SKILL.md")})
    settings = [{"path": path, "enabled": False} for path in disabled]
    settings += [{"path": Path(path).resolve().as_posix(), "enabled": True} for path in expected_skills]
    # Inline TOML, not JSON object syntax.
    common += ["-c", "skills.config=[" + ",".join("{path=" + json.dumps(s["path"]) + ",enabled=" + str(s["enabled"]).lower() + "}" for s in settings) + "]"]
    raw = probe(common)
    items = json.loads(raw)
    texts = [part["text"] for item in items for part in item.get("content", []) if isinstance(part.get("text"), str)]
    combined = "\n".join(texts).replace("\\", "/")
    if any(marker in combined for marker in CONTEXT_MARKERS if marker != "<skills_instructions>"):
        raise ValueError("native skill study contains personal instructions")
    # Catalog paths are emitted by Codex's assembled skill list; bind exact set.
    aliases = dict(re.findall(r"- `([^`]+)` = `([^`]+)`", combined))
    catalog = []
    for reference in re.findall(r"\(file:\s*([^\r\n)]+SKILL\.md)\)", combined):
        prefix, _, relative = reference.partition("/")
        expanded = str(Path(aliases[prefix]) / relative) if prefix in aliases else reference
        catalog.append(Path(expanded).resolve().as_posix())
    expected = sorted(Path(p).resolve().as_posix() for p in expected_skills)
    if sorted(catalog) != expected:
        raise ValueError("native skill catalog differs from staged skills")
    return common, {"verified": True, "source": "codex-debug-prompt-input", "catalog": catalog,
                    "sha256": hashlib.sha256(raw.encode()).hexdigest(), "disabled_skill_count": len(disabled)}


def run_hermes_skill_study(prompt, fixture, timeout, expected_skills, max_iterations, assembly_only=False):
    """Explicit native host adapter; never chooses a route or falls back."""
    from artifact_hash import freeze_candidate
    runtime = Path(tempfile.mkdtemp(prefix="agent-signal-hermes-study-"))
    started = time.monotonic()
    result = {"ok": False, "tokens": None, "dollars": None, "timings": {},
              "resource_limits": {"timeout_seconds": timeout, "max_iterations": max_iterations,
                                  "iteration_limit_enforced": True}}
    try:
        source = dict(os.environ)
        env = runtime_environment(source, runtime)
        python, native = native_hermes_runtime(native_executable("hermes"))
        env.update(TERMINAL_ENV="local", TERMINAL_CONTAINER_PERSISTENT="false")
        catalog = []
        for skill in expected_skills:
            skill = Path(skill)
            frozen = freeze_candidate(skill)
            text = skill.read_text(encoding="utf-8")
            if re.search(r"(?m)^deps\s*:|!`|\{\{", text):
                raise ValueError("Study catalog cannot install dependencies or preprocess dynamic content")
            destination = Path(env["HERMES_HOME"]) / "skills" / skill.parent.name
            shutil.copytree(skill.parent, destination)
            staged = destination / "SKILL.md"
            if freeze_candidate(staged)["package_sha256"] != frozen["package_sha256"]:
                raise ValueError("Native Hermes staged package changed")
            catalog.append({"path": str(staged), "package_sha256": frozen["package_sha256"],
                            "body_sha256": hashlib.sha256(frozen["prompt_text"].encode()).hexdigest()})
        env["HERMES_BUNDLED_PLUGINS"] = str(runtime / "no-plugins")
        job = {"purpose": "native-skill-study", "assembly_only": assembly_only,
               "native_source": str(native), "credential_owner_home": str(hermes_owner_home(source)),
               "runtime_home": env["HERMES_HOME"], "fixture": str(fixture), "catalog": catalog,
               "prompt": prompt, "model": "gpt-6-sol", "reasoning": "medium",
               "max_iterations": max_iterations, "timeout": timeout}
        result["timings"]["preflight"] = time.monotonic() - started
        before = time.monotonic()
        proc = subprocess.run([str(python), str(Path(__file__).with_name("evaluation_hermes_worker.py"))],
                              input=json.dumps(job), cwd=fixture, env=env, text=True, encoding="utf-8",
                              capture_output=True, timeout=timeout + 30)
        receipts = []
        for line in proc.stdout.splitlines():
            try:
                receipt = json.loads(line)
            except ValueError:
                continue
            if isinstance(receipt, dict) and "ok" in receipt:
                receipts.append(receipt)
        if len(receipts) != 1:
            raise ValueError("Native worker did not emit one typed receipt")
        result.update(receipts[0])
        result["timings"]["worker"] = time.monotonic() - before
        result["returncode"] = proc.returncode
        result["ok"] = result["ok"] and proc.returncode == 0
    except subprocess.TimeoutExpired as exc:
        result["failure"] = "TimeoutExpired"
        diagnostics = exc.stderr or ""
        if isinstance(diagnostics, bytes):
            diagnostics = diagnostics.decode("utf-8", errors="replace")
        result["assembly_phases"] = re.findall(r"(?m)^ASSEMBLY_PHASE:([A-Za-z0-9_]+)$", diagnostics)[-15:]
        result["assembly_frames"] = [{"file": Path(filename).name, "line": int(line), "function": function}
            for filename, line, function in re.findall(r'File "([^"]+)", line (\d+) in ([A-Za-z0-9_<>]+)', diagnostics)][-15:]
    except Exception as exc:
        result["failure"] = type(exc).__name__
    finally:
        before = time.monotonic()
        result["cleanup"] = cleanup_runtime(runtime, fixture)
        result["timings"]["cleanup"] = time.monotonic() - before
        result["timings"]["controller_total"] = time.monotonic() - started
        result["ok"] = result["ok"] and result["cleanup"]["state_removed"] and not result["cleanup"]["errors"]
    return result


def run_native_skill_study(prompt: str, fixture: Path, timeout: int, expected_skills: list[str], *, agent: str = "codex", max_iterations: int = 24, assembly_only: bool = False) -> dict[str, Any]:
    if agent == "hermes":
        return run_hermes_skill_study(prompt, fixture, timeout, expected_skills, max_iterations, assembly_only)
    if agent != "codex" or assembly_only:
        raise ValueError("Unsupported native study host or probe")
    started = time.monotonic()
    runtime = Path(tempfile.mkdtemp(prefix="agent-signal-skill-study-"))
    source = dict(os.environ)
    result = {"ok": False, "failure": None, "tokens": None, "dollars": None,
              "timings": {"preflight": None, "worker": None, "cleanup": None},
              "resource_limits": {"timeout_seconds": timeout, "max_iterations_requested": max_iterations,
                                  "max_iterations": None, "iteration_limit_enforced": False},
              "limits": ["Codex exec supports the wall timeout here, not an iteration ceiling"]}
    try:
        exe = native_executable("codex")
        if not exe:
            raise ValueError("native Codex unavailable")
        env = runtime_environment(source, runtime)
        # This lane must never turn subscription study authorization into API spend.
        owner = Path(source.get("CODEX_HOME") or Path(source.get("USERPROFILE") or source.get("HOME") or Path.home()) / ".codex")
        auth = json.loads((owner / "auth.json").read_text(encoding="utf-8-sig"))
        if not _token_projection(auth.get("tokens")).get("access_token") or auth.get("auth_mode") == "apikey":
            raise ValueError("native skill study requires subscription authentication")
        stage_auth("codex", source, env)
        staged = Path(env["CODEX_HOME"]) / "auth.json"
        clean_auth = json.loads(staged.read_text(encoding="utf-8"))
        clean_auth.pop("OPENAI_API_KEY", None)
        staged.write_text(json.dumps(clean_auth), encoding="utf-8")
        before = time.monotonic()
        common, result["catalog_evidence"] = skill_study_preflight(exe, fixture, env, source, expected_skills)
        result["timings"]["preflight"] = time.monotonic() - before
        command = [exe, "exec", *common, "--ignore-user-config", "--ignore-rules", "--skip-git-repo-check",
                   "--ephemeral", "--json", "-"]
        before = time.monotonic()
        proc = subprocess.run(command, input=prompt, cwd=fixture, env=env, text=True, encoding="utf-8",
                              capture_output=True, timeout=timeout)
        result["timings"]["worker"] = time.monotonic() - before
        result.update(skill_study_events(proc.stdout, expected_skills))
        result["returncode"] = proc.returncode
        # Record public configuration/readiness headers, never raw diagnostics.
        result["runtime_headers"] = [line for line in proc.stderr.splitlines()
            if re.match(r"^(model|provider|reasoning effort|sandbox|approval):", line)]
        result["ok"] = result["ok"] and proc.returncode == 0
        result["requested_route"] = {"model": "gpt-6-sol", "reasoning": "medium", "provider": "openai-codex"}
        result["provider_resolved_identity_verified"] = False
        if not result["ok"]:
            result["failure"] = "native execution or event evidence failed"
    except Exception as exc:
        result["failure"] = type(exc).__name__ + ": " + str(exc)
    finally:
        before = time.monotonic()
        result["cleanup"] = cleanup_runtime(runtime, fixture)
        result["timings"]["cleanup"] = time.monotonic() - before
        result["timings"]["controller_total"] = time.monotonic() - started
        result["ok"] = result["ok"] and result["cleanup"]["credentials_removed"] and result["cleanup"]["state_removed"] and not result["cleanup"]["errors"]
    return result
