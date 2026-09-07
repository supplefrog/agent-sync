"""Fresh Hermes API child: native credentials stay in memory, tools cannot run."""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import sys
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
            receipt = execute_agent(job, access_token, AIAgent, build_system_prompt)
            del access_token
        receipt["suppressed_native_diagnostic_characters"] = len(diagnostics.getvalue())
    except BaseException as exc:
        # Native errors or diagnostic buffers can include credentials; never
        # propagate their text, argv, environment, or traceback to the report.
        receipt = {"ok": False, "error_type": type(exc).__name__,
                   "error": "native Hermes worker could not complete the isolated call",
                   "failure": {"kind": "isolation", "source": "runtime-control", "code": type(exc).__name__}}
    finally:
        if canary_file is not None:
            canary_file.unlink(missing_ok=True)
    print(json.dumps(receipt, ensure_ascii=False))
    return 0 if receipt["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
