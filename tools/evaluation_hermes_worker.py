"""Fresh Hermes API child: native credentials stay in memory, tools cannot run."""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import sys
import re
import time
from pathlib import Path
from typing import Any, Callable
from evaluation_runtime import native_transport_failure

ENDPOINT = "https://chatgpt.com/backend-api/codex"
CONTEXT_MARKERS = ("<available_skills>", "<skills_instructions>", "MEMORY_SUMMARY",
                   "[INSTRUCTION-AUTHORING]", "[RECONCILIATION]")


def checked_access_token(credentials: dict) -> str:
    if credentials.get("base_url") != ENDPOINT or not isinstance(credentials.get("api_key"), str) or not credentials["api_key"]:
        raise RuntimeError("native Hermes credential endpoint or access token is unsupported")
    return credentials["api_key"]


def execute_agent(job: dict, access_token: str, factory: Callable, build_prompt: Callable) -> dict:
    """The native registry is empty and all native tool-dispatch paths are blocked."""
    agent = factory(
        model=job["model"], provider="openai-codex", api_mode="codex_responses",
        api_key=access_token, base_url=ENDPOINT, enabled_toolsets=["none"],
        skip_context_files=True, load_soul_identity=False, skip_memory=True,
        skip_background_review=True, quiet_mode=True, save_trajectories=False,
        max_iterations=2, run_budget_seconds=job["timeout"],
        reasoning_config={"enabled": True, "effort": job["reasoning"]}, fallback_model=None,
    )
    attempts = 0

    def reject_tool_execution(*_args: Any, **_kwargs: Any) -> None:
        nonlocal attempts
        attempts += 1
        raise RuntimeError("tool execution is prohibited in the evaluator")

    for method in ("_execute_tool_calls", "_execute_tool_calls_sequential", "_execute_tool_calls_concurrent"):
        if not callable(getattr(agent, method, None)):
            raise RuntimeError("native Hermes tool-dispatch boundary is unavailable")
        setattr(agent, method, reject_tool_execution)
    assembled = build_prompt(agent)
    markers = [*CONTEXT_MARKERS, job["canary"]]
    if agent.valid_tool_names or any(marker in assembled for marker in markers) or access_token in assembled:
        raise RuntimeError("native Hermes prompt/tool isolation failed")
    prompt = job["prompt"]
    if job.get("output_schema") is not None:
        prompt += "\n\nReturn only one JSON object matching this schema:\n" + json.dumps(job["output_schema"])
    transport_failure = None
    try:
        native = agent.run_conversation(prompt)
    except Exception as exc:
        transport_failure = native_transport_failure({"status_code": getattr(exc, "status_code", None), "code": getattr(exc, "code", None)})
        native = {"completed": False, "failed": True, "final_response": ""}
    output = native.get("final_response", "")
    if not isinstance(output, str) or access_token in output:
        raise RuntimeError("native Hermes output failed the secret boundary")
    observed = {"model": agent.model, "provider": agent.provider,
                "reasoning": getattr(agent, "reasoning_config", {}).get("effort"), "tool_calls_count": attempts}
    expected = {"model": job["model"], "provider": "openai-codex", "reasoning": job["reasoning"]}
    errors = [f"native {key} metadata missing or mismatched" for key in expected if observed[key] != expected[key]]
    if attempts:
        errors.append("native Hermes attempted prohibited tool execution")
    if not native.get("completed") or any(native.get(key) for key in ("failed", "interrupted", "partial")):
        errors.append("native Hermes conversation did not complete")
        transport_failure = transport_failure or native_transport_failure({
            "http_status": native.get("http_status"), "code": native.get("error_code"),
            "error": native.get("error") if isinstance(native.get("error"), dict) else {},
        })
    failure = None
    if errors:
        failure = ({"kind": "tool", "source": "runtime-control", "code": "prohibited-native-tool-activity"} if attempts
                   else {"kind": "route", "source": "runtime-control", "code": "native-route-mismatch"}
                   if any("metadata" in error for error in errors)
                   else transport_failure)
    return {
        "ok": not errors, "output": output, "failure": failure,
        "route_attestation": {
            "requested": {**expected, "tool_policy": "none"}, "observed": observed,
            "ok": not errors, "errors": errors, "source": "native-AIAgent-runtime-metadata",
            "provider_resolved_identity_verified": False,
        },
        "prompt_isolation": {
            "verified": True, "source": "native-AIAgent-build-system-prompt",
            "sha256": hashlib.sha256(assembled.encode("utf-8")).hexdigest(), "assembled_prompt": assembled,
            "canary": job["canary"], "canary_absent": job["canary"] not in assembled,
            "contamination": [], "native_tool_names": list(agent.valid_tool_names),
            "tool_schema_absence_verified": False,
        },
        "tool_observation": {"source": "native-AIAgent-tool-dispatch-guard", "tool_activity_count": attempts,
                             "execution_blocker_installed": True, "ok": attempts == 0,
                             "tool_schema_absence_verified": False},
        "native_result_metadata": {**{key: native.get(key) for key in
                                   ("completed", "failed", "interrupted", "partial", "model", "provider", "api_calls")},
                                   "final_response": output},
    }


def study_guard(tool_name, args, fixture, catalog_root):
    """Conservative native request gate, not an operating-system sandbox."""
    def contained(value, root):
        path = Path(value)
        path = path if path.is_absolute() else fixture / path
        return path.resolve().is_relative_to(root.resolve())
    if tool_name in ("skills_list", "skill_view"):
        return None
    if tool_name in ("read_file", "search_files", "write_file", "patch"):
        paths = [args.get("path", ".")]
        if tool_name == "patch" and args.get("mode") == "patch":
            paths = re.findall(r"(?m)^\*\*\* (?:(?:Update|Add|Delete) File|Move to): (.+)$", args.get("patch", ""))
            if not paths:
                return "Patch paths must be explicit"
        if all(isinstance(p, str) and (contained(p, fixture) or tool_name == "read_file" and contained(p, catalog_root)) for p in paths):
            return None
        return "Paths outside the study fixture are prohibited"
    if tool_name == "terminal":
        if any(args.get(key) for key in ("background", "persist_on_release", "pty")):
            return "Persistent or background terminal jobs are prohibited"
        if args.get("workdir") and not contained(args["workdir"], fixture):
            return "Terminal working directory must be in the fixture"
        command = args.get("command", "")
        # Allow fixture testing/listing, reject shell composition, arbitrary code,
        # install/network programs and absolute/parent paths.
        if (isinstance(command, str) and not re.search(r"[;&|<>`\r\n]|\$|\.\.|https?:|[A-Za-z]:|(?:^|\s)/", command)
                and re.fullmatch(r"(?:python(?:\.exe)? -m (?:pytest|unittest)(?: [A-Za-z0-9_. /=-]+)?|pytest(?: [A-Za-z0-9_. /=-]+)?|(?:pwd|ls|dir)(?: [A-Za-z0-9_. /=-]+)?)", command)):
            return None
        return "Only simple fixture test/listing commands are permitted"
    return "This native study prohibits management, delegation and external tools"


def execute_skill_study(job, access_token, factory, build_prompt):
    from artifact_hash import freeze_candidate
    from hermes_cli.plugins import PluginContext, PluginManifest, get_plugin_manager
    from tools.skills_tool import skills_list
    fixture = Path(job["fixture"]).resolve()
    catalog_root = Path(job["runtime_home"]) / "skills"
    agent = None
    leases, events, reads = [], [], []
    blocked = []
    names = []
    for item in job["catalog"]:
        text = Path(item["path"]).read_text(encoding="utf-8")
        match = re.search(r"(?m)^name:\s*(.+)$", text)
        names.append(match.group(1).strip().strip("\"'") if match else Path(item["path"]).parent.name)
    def gate(tool_name, args, **kwargs):
        message = study_guard(tool_name, args, fixture, catalog_root)
        if message:
            blocked.append({"tool": tool_name, "reason": message})
            return {"action": "block", "message": message}
    def completed(call_id, name, args, raw):
        parsed = raw if isinstance(raw, dict) else None
        if parsed is None:
            try:
                parsed = json.loads(raw)
            except (ValueError, TypeError):
                parsed = {}
        events.append({"type": "native-tool-completed", "tool": name, "call_id": call_id,
                       "success": not parsed.get("error") and parsed.get("success", True) is not False})
        if name == "skill_view" and parsed.get("success") and not args.get("file_path"):
            path = Path(parsed.get("_source_path", ""))
            for item in job["catalog"]:
                if path.name == "SKILL.md" and path.parent.name == Path(item["path"]).parent.name and path.is_file():
                    frozen = freeze_candidate(path)
                    if frozen["package_sha256"] == item["package_sha256"]:
                        reads.append({**item, "source": "successful-native-skill_view", "native_source_path": str(path)})
    try:
        manager = get_plugin_manager()
        context = PluginContext(PluginManifest(name="study-runtime-guard"), manager)
        leases.append(context.register_hook("pre_tool_call", gate))
        agent = factory(model=job["model"], provider="openai-codex", api_mode="codex_responses",
            api_key=access_token or "assembly-probe-no-credential", base_url=ENDPOINT,
            enabled_toolsets=["terminal", "file", "skills"], skip_context_files=True,
            load_soul_identity=False, skip_memory=True, skip_background_review=True,
            quiet_mode=True, save_trajectories=False, max_iterations=job["max_iterations"],
            run_budget_seconds=job["timeout"], reasoning_config={"enabled": True, "effort": "medium"},
            fallback_model=None, tool_complete_callback=completed)
        assembled = build_prompt(agent)
        actual = sorted(s["name"] for s in json.loads(skills_list()).get("skills", []))
        if actual != sorted(names) or len(actual) != len(set(actual)) or any(name not in assembled for name in names):
            raise RuntimeError("Native catalog differs from the declared exact catalog")
        if access_token and access_token in assembled or any(marker in assembled for marker in CONTEXT_MARKERS[1:]):
            raise RuntimeError("Native study prompt contamination")
        metadata = {"model": agent.model, "provider": agent.provider,
                    "reasoning": agent.reasoning_config.get("effort")}
        if metadata != {"model": "gpt-6-sol", "provider": "openai-codex", "reasoning": "medium"}:
            raise RuntimeError("Native study route mismatch")
        before = time.monotonic()
        native = {"completed": True, "api_calls": 0} if job.get("assembly_only") else agent.run_conversation(job["prompt"])
        result = {"ok": bool(native.get("completed") and not any(native.get(k) for k in ("failed", "partial", "interrupted"))),
            "assembly_only": bool(job.get("assembly_only")), "model_launched": not job.get("assembly_only"),
            "requested_route": {"model": job["model"], "provider": "openai-codex", "reasoning": job["reasoning"]},
            "agent_observed_route": metadata, "provider_resolved_identity_verified": False,
            "catalog_evidence": {"declared_names": sorted(names), "native_catalog_names": actual,
                                 "exact_catalog_verified": True, "prompt_sha256": hashlib.sha256(assembled.encode()).hexdigest()},
            "skill_read_evidence": reads, "events": events, "blocked_requests": blocked,
            "tokens": {"input": getattr(agent, "session_input_tokens", None), "output": getattr(agent, "session_output_tokens", None)},
            "api_calls": native.get("api_calls"), "dollars": None, "cost_status": "subscription-dollars-unavailable",
            "native_seconds": time.monotonic() - before,
            "limits": ["native request gate is not operating-system isolation", "fixture tests execute model-edited code"]}
        if access_token and access_token in json.dumps(result):
            raise RuntimeError("Credential output rejected")
        return result
    finally:
        if agent is not None:
            agent.close()
        for lease in reversed(leases):
            lease.dispose()


def main() -> int:
    diagnostics = io.StringIO()
    canary_file = None
    try:
        job = json.loads(sys.stdin.read())
        with contextlib.redirect_stdout(diagnostics), contextlib.redirect_stderr(diagnostics):
            sys.path.insert(0, job["native_source"])
            # Resolve only Hermes' own selected provider before changing homes.
            # CODEX_HOME already points at empty disposable state, so the native
            # resolver cannot import credentials from the user's Codex account.
            os.environ["HERMES_HOME"] = job["credential_owner_home"]
            from hermes_cli.auth_codex import resolve_codex_runtime_credentials
            if job.get("assembly_only"):
                access_token = None
            else:
                credentials = resolve_codex_runtime_credentials(refresh_if_expiring=False)
                access_token = checked_access_token(credentials)
                credentials.clear()
            os.environ["HERMES_HOME"] = job["runtime_home"]
            os.environ["TERMINAL_CWD"] = job["fixture"]
            from hermes_constants import set_hermes_home_override
            set_hermes_home_override(job["runtime_home"])
            os.chdir(job["fixture"])
            canary = "EVALUATOR_CONTEXT_CANARY_" + hashlib.sha256(os.urandom(32)).hexdigest()
            job["canary"] = canary
            (Path(job["runtime_home"]) / "SOUL.md").write_text(canary, encoding="utf-8")
            candidate = Path(job["fixture"]) / "AGENTS.md"
            if not candidate.exists():
                with candidate.open("x", encoding="utf-8") as stream:
                    stream.write(canary)
                canary_file = candidate
            from run_agent import AIAgent
            from agent.system_prompt import build_system_prompt
            receipt = (execute_skill_study(job, access_token, AIAgent, build_system_prompt)
                       if job.get("purpose") == "native-skill-study"
                       else execute_agent(job, access_token, AIAgent, build_system_prompt))
            del access_token
        receipt["suppressed_native_diagnostic_characters"] = len(diagnostics.getvalue())
    except BaseException as exc:
        import traceback
        # Native errors or diagnostic buffers can include credentials; never
        # propagate their text, argv, environment, or traceback to the report.
        receipt = {"ok": False, "error_type": type(exc).__name__,
                   "error_locations": [{"file": Path(frame.filename).name, "function": frame.name, "line": frame.lineno}
                                       for frame in traceback.extract_tb(exc.__traceback__)],
                   "error": "native Hermes worker could not complete the isolated call",
                   "failure": {"kind": "isolation", "source": "runtime-control", "code": type(exc).__name__}}
    finally:
        if canary_file is not None:
            canary_file.unlink(missing_ok=True)
    print(json.dumps(receipt, ensure_ascii=False))
    return 0 if receipt["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
