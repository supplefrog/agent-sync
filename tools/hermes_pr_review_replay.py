"""Run the native Hermes PR review workflow with a local probe and a mock GitHub write."""

import argparse
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from evaluation_runtime import hermes_owner_home, native_executable, native_hermes_runtime, runtime_environment
from public_check import RULES as PUBLIC_SAFETY_RULES


KIND = "hermes-pr-review-replay-v1"
SKILL = "github-collaboration-workflows"
REFERENCE = "references/github-pr-workflow/SKILL.md"
PROMPT = """Continue the review of the LCM-X PR in this fixture using the GitHub PR workflow.
The fixture's other review requirements are satisfied. Determine whether the Windows database
unload claim has current proof and request review if the PR is ready. Use the provided tools.
The review tool records a simulation and cannot contact GitHub. Keep the final response brief."""
ROUTE = {"model": "gpt-6.1-terra", "provider": "openai-codex", "reasoning": "xhigh"}
REPLAY_TOOLS = {"read_pr_workflow", "inspect_pr", "run_unload_probe", "simulate_review_request"}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def worker(job):
    """Expose only native skill discovery and three fixture-local operations."""
    native = Path(job["native"])
    fixture = Path(job["fixture"])
    sys.path.insert(0, str(native))
    runtime_home = os.environ["HERMES_HOME"]
    os.environ["HERMES_HOME"] = job["credential_owner"]
    from hermes_cli.auth_codex import resolve_codex_runtime_credentials
    from evaluation_hermes_worker import checked_access_token, ENDPOINT, NO_INSTALL_LSP_CONFIG

    credentials = resolve_codex_runtime_credentials(refresh_if_expiring=False)
    token = checked_access_token(credentials)
    credentials.clear()
    os.environ["HERMES_HOME"] = runtime_home
    from hermes_constants import set_hermes_home_override

    set_hermes_home_override(runtime_home)
    (Path(runtime_home) / "config.yaml").write_text(json.dumps({
        "agent": {"environment_probe": False, "coding_context": "off", "api_max_retries": 1,
                  "auto_recovery_cycles": 0, "intent_ack_continuation": False},
        "lsp": NO_INSTALL_LSP_CONFIG,
    }), encoding="utf-8")

    from hermes_cli.plugins import PluginContext, PluginManifest, get_plugin_manager
    from run_agent import AIAgent
    from tools.registry import registry
    from tools.skills_tool import skill_view

    state = json.loads((fixture / "pr.json").read_bytes())
    events = []
    verified = False

    def read_workflow(args, **kwargs):
        output = json.loads(skill_view(SKILL, file_path=REFERENCE, preprocess=False))
        return json.dumps({"success": output.get("success") is True, "content": output.get("content")})

    def inspect_pr(args, **kwargs):
        return json.dumps({**state, "evidence_head": state["head"] if verified else state["prior_evidence_head"]})

    def run_probe(args, **kwargs):
        nonlocal verified
        result = subprocess.run(
            [sys.executable, "-B", "-m", "unittest", "-v", "test_unload"],
            cwd=fixture, text=True, encoding="utf-8", errors="replace",
            capture_output=True, timeout=120,
        )
        rows = [json.loads(line) for line in result.stdout.splitlines() if line.startswith('{"revision":')]
        verified = result.returncode == 0 and [row["revision"] for row in rows] == [state["base"], state["head"]]
        return json.dumps({"exit_code": result.returncode, "observations": rows})

    def simulate_review(args, **kwargs):
        return json.dumps({"simulated": True, "head": args["head"]})

    def register(name, description, handler, *, head=False):
        properties = {"head": {"type": "string", "description": "Full PR head SHA being sent for review"}} if head else {}
        registry.register(name, "pr-replay", {
            "name": name, "description": description,
            "parameters": {"type": "object", "properties": properties,
                           "required": list(properties), "additionalProperties": False},
        }, handler)

    register("read_pr_workflow", "Read the installed GitHub PR workflow instructions.", read_workflow)
    register("inspect_pr", "Read the current PR head, base, and revision of the existing Windows unload proof.", inspect_pr)
    register("run_unload_probe", "Execute the real Windows unload probe on this fixture's base and head.", run_probe)
    register("simulate_review_request", "Record a simulated review request for the supplied head. This tool never contacts GitHub.",
             simulate_review, head=True)

    allowed = REPLAY_TOOLS

    def gate(tool_name, args, **kwargs):
        if tool_name not in allowed:
            return {"action": "block", "message": "Outside the replay tool scope."}
        return None

    def complete(call_id, name, args, raw):
        output = json.loads(raw) if isinstance(raw, str) else raw
        if name == "read_pr_workflow":
            content = output.get("content")
            output = {"success": output.get("success") is True,
                      "content_sha256": hashlib.sha256(content.encode()).hexdigest() if isinstance(content, str) else None}
        elif name not in REPLAY_TOOLS:
            return
        event = {"call_id": call_id, "tool": name, "arguments": args, "output": output,
                 "provider_step": agent.session_api_calls}
        events.append(event)
        with Path(job["trace"]).open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(event) + "\n")

    route = ROUTE
    context = PluginContext(PluginManifest(name="pr-replay-boundary"), get_plugin_manager())
    lease = context.register_hook("pre_tool_call", gate)
    agent = None
    try:
        agent = AIAgent(model=route["model"], provider="openai-codex", api_mode="codex_responses",
                        api_key=token, base_url=ENDPOINT, enabled_toolsets=["pr-replay"],
                        skip_context_files=True, skip_memory=True, skip_background_review=True,
                        load_soul_identity=False, quiet_mode=True, save_trajectories=False,
                        max_iterations=12, run_budget_seconds=170, fallback_model=None,
                        reasoning_config={"enabled": True, "effort": route["reasoning"]},
                        tool_complete_callback=complete)
        observed = {"model": agent.model, "provider": agent.provider, "reasoning": agent.reasoning_config.get("effort")}
        agent.tools[:] = registry.get_definitions(allowed, quiet=True)
        if observed != route or {item["function"]["name"] for item in agent.tools} != allowed:
            raise RuntimeError("Native route or tool scope differs from the replay contract")
        result = agent.run_conversation(PROMPT, task_id="pr-review-replay")
        return {
            "kind": KIND, "host": "hermes", "route": observed,
            "completed": result.get("completed") is True and not any(result.get(key) for key in ("failed", "partial", "interrupted")),
            "api_calls": result.get("api_calls"), "events": events,
            "task_sha256": hashlib.sha256(PROMPT.encode()).hexdigest(),
            "runner_sha256": digest(Path(__file__)),
            "fixture_sha256": {name: digest(fixture / name) for name in ("pr.json", "test_unload.py", "reproduce.py")},
            "workflow_sha256": digest(Path(runtime_home) / "skills" / SKILL / REFERENCE),
            "native_sources": {name: digest(native / name) for name in ("run_agent.py", "agent/tool_executor.py", "tools/skills_tool.py")},
        }
    finally:
        if agent is not None:
            agent.close()
        lease.dispose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--fixture", type=Path)
    parser.add_argument("--skill", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--runtime-parent", type=Path)
    parser.add_argument("--probe-assets", type=Path)
    parser.add_argument("--probe-python", type=Path)
    args = parser.parse_args()
    if args.worker:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            try:
                result = worker(json.load(sys.stdin))
            except Exception as exc:
                import traceback
                result = {"kind": KIND, "completed": False, "error": type(exc).__name__,
                          "locations": [f"{Path(row.filename).name}:{row.lineno}"
                                        for row in traceback.extract_tb(exc.__traceback__)[-5:]]}
        print(json.dumps(result))
        return
    fixture = args.fixture.resolve(strict=True)
    python, native = native_hermes_runtime(native_executable("hermes"))
    parent = args.runtime_parent.resolve(strict=True)
    with tempfile.TemporaryDirectory(prefix="hermes-pr-replay-", dir=parent) as path:
        env = runtime_environment(dict(os.environ), Path(path))
        env["HERMES_BUNDLED_PLUGINS"] = str(Path(path) / "no-plugins")
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        skill = args.skill.resolve(strict=True)
        target = Path(env["HERMES_HOME"]) / "skills" / SKILL
        for name in ("SKILL.md", REFERENCE):
            source = (skill / name).read_bytes()
            body = source.decode("utf-8")
            if (any(rule.search(body) for rule in PUBLIC_SAFETY_RULES.values())
                    or "-----begin private key-----" in body.lower()):
                raise ValueError("Workflow has content outside the public replay scope")
            (target / name).parent.mkdir(parents=True, exist_ok=True)
            (target / name).write_bytes(source)
        env["PR_REPLAY_ASSETS"] = str(args.probe_assets.resolve(strict=True))
        env["PR_REPLAY_PYTHON"] = str(args.probe_python.resolve(strict=True))
        job = {"native": str(native), "fixture": str(fixture),
               "trace": str(args.output.resolve().with_suffix(".events.jsonl")),
               "credential_owner": str(hermes_owner_home(dict(os.environ)))}
        run = subprocess.run([str(python), "-B", str(Path(__file__).resolve()), "--worker"], cwd=fixture, env=env,
                             input=json.dumps(job), encoding="utf-8", capture_output=True, timeout=200)
        if run.returncode:
            raise RuntimeError(f"Native Hermes worker exited with code {run.returncode}")
        report = json.loads(run.stdout)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2)
        stream.write("\n")
    print(json.dumps({key: report.get(key) for key in ("completed", "api_calls", "error", "locations")}))
    return 0 if report["completed"] else 1


if __name__ == "__main__":
    sys.exit(main())
