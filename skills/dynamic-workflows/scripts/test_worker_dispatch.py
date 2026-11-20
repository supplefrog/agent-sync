"""Exercise broker selection, renewal and result binding through the workflow CLI."""
import json
import os
import subprocess
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

import worker_dispatch as wd
import workflow_state as ws


SCRIPTS = Path(__file__).resolve().parent
REPO = SCRIPTS.parents[2]


def cli(script, *args, ok=True):
    result = subprocess.run(
        [sys.executable, "-B", str(SCRIPTS / script), *map(str, args)],
        capture_output=True, text=True, encoding="utf-8",
        env={**os.environ, "AGENT_SIGNAL_ROOT": str(REPO)}, check=False,
    )
    if (result.returncode == 0) != ok:
        raise AssertionError(f"{args}: {result.returncode}\n{result.stderr}\n{result.stdout}")
    return result.stdout.strip()


def write(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def plan(dispatcher):
    template = json.loads((SCRIPTS.parent / "assets/templates/workflow-v3.json").read_bytes())
    template["max_workers"] = 1
    for item in template["tasks"]:
        req = item["route_request"]
        req["requirements"].update(context_tokens=1024, reasoning_effort="medium")
        req["verifier"].update(kind="deterministic", scope="inline-text")
        req["budget"].update(unknown_cost_policy="explicit_preference",
                             preference_order=[wd.route_id(dispatcher)],
                             quotas={"codex-main": {"unit":"percentage-points", "remaining":30, "reserve":0}})
    return template


def native_result(selected, handle, assignment, output):
    recorded = datetime.now(timezone.utc).isoformat()
    if selected["dispatcher"] == "t3":
        environment, project, parent = selected["scope"].split(":")
        route = {"providerInstanceId": selected["instance"], "model": selected["model"]}
        return {
            "environment": environment,
            "status": {**route, "status": "completed", "workState": "result_available", "taskId": handle,
                       "childRunId": "run", "childThreadId": "child", "latestTerminalRunId": "run",
                       "latestTerminalStatus": "completed", "hasPendingChildRuns": False,
                       "hasPendingQuestion": False, "pendingApproval": None,
                       "options": [{"id": selected["option"], "value": selected["effort"]}]},
            "activity": {"thread": {**route, "threadId": "child", "projectId": project, "parentThreadId": parent,
                                    "activeRunId": None, "runCount": 1, "pendingRequestCount": 0},
                         "recentRuns": [{**route, "runId": "run", "status": "completed", "completedAt": recorded}],
                         "hasMore": False,
                         "items": [
                             {"visibility": "local", "sourceThreadId": "child", "runId": "run",
                              "textTruncated": False, "type": kind, "text": message}
                             for kind, message in [("user_message", assignment), ("assistant_message", output),
                                                   ("checkpoint", "[]")]
                         ]},
        }
    server, workspace = selected["scope"].split(":")
    return {
        "daemon": {"serverId": server, "connectedDaemon": "reachable"},
        "workspace": {"workspaceId": workspace, "cwd": "fixture"},
        "inspect": {"Id": handle, "Provider": selected["instance"], "Model": selected["model"],
                    "Thinking": selected["effort"], "Mode": selected["mode"], "Cwd": "fixture",
                    "Status": "closed", "Archived": True, "PendingPermissions": [], "CreatedAt": recorded},
        "logs": f"[User] {assignment}\n{output}",
        **dict.fromkeys(("tools", "errors", "permissions"), "No activity to display."),
    }


def assignment_for(dispatcher, request):
    return request["arguments"]["task"] if dispatcher == "t3" else request["argv"][-1]


class WorkerDispatchTests(unittest.TestCase):
    def test_real_cli_for_both_dispatchers(self):
        for dispatcher in ("t3", "paseo"):
            with self.subTest(dispatcher=dispatcher), TemporaryDirectory() as temp:
                root = Path(temp)
                selected = {"dispatcher": dispatcher,
                            "scope": "local:project:parent" if dispatcher == "t3" else "srv_fixture:wks_fixture",
                            "instance": "codex",
                            "model": "gpt-6.2-sol", "effort": "medium",
                            "option": "reasoningEffort" if dispatcher == "t3" else "thinkingOptionId",
                            "mode": "inherit" if dispatcher == "t3" else "auto"}
                selected_path = write(root / "target.json", selected)
                cache = root / "runs" / ".worker-dispatch"
                extra = []
                if dispatcher == "t3":
                    caps = write(root / "capabilities.json", {
                        "parentThreadId": "parent", "inheritedProviderInstanceId": "codex",
                        "inheritedModel": selected["model"],
                        "inheritedOptions": [{"id": selected["option"], "value": "low"}],
                        "providers": [{
                            "providerInstanceId": "codex", "canRunChildTask": True,
                            "models": [{"id": selected["model"],
                                        "options": [{"id": selected["option"], "values": ["medium"]}]}],
                        }],
                    })
                    extra = ["--capabilities", caps]
                    matching = json.loads(caps.read_bytes())
                    mismatch = {**matching, "inheritedOptions": [{"id": "serviceTier", "value": "fast"}]}
                    with self.assertRaisesRegex(ValueError, "inherit options"):
                        wd.validate_t3_capabilities(selected, mismatch)
                prepare = lambda: json.loads(cli("worker_dispatch.py", "prepare", selected_path, "--root", cache, *extra))
                probe = prepare()
                self.assertEqual(probe["kind"], "probe")
                self.assertEqual(prepare()["kind"], "pending")
                self.assertEqual(prepare()["attempt"], probe["attempt"])
                prompt = assignment_for(dispatcher, probe)
                self.assertIn("READY-" + probe["attempt"], prompt)
                result = native_result(selected, "fixture-worker-1", prompt, "READY-" + probe["attempt"])
                bad_result = json.loads(json.dumps(result))
                if dispatcher == "t3":
                    bad_result["status"]["hasPendingChildRuns"] = True
                else:
                    bad_result["inspect"]["Archived"] = False
                observed = write(root / "probe.json", bad_result)
                cli("worker_dispatch.py", "complete", probe["cache"], probe["attempt"], observed, ok=False)
                observed = write(observed, result)
                fresh = json.loads(cli("worker_dispatch.py", "complete", probe["cache"], probe["attempt"], observed))
                self.assertEqual(prepare(), fresh)
                run = Path(cli("workflow_state.py", "init", write(root / "plan.json", plan(dispatcher)),
                               "--root", root / "runs", "--target-surface", f"{dispatcher}-workflow"))
                context = {"active_t3": dispatcher == "t3", "dispatcher_scope": selected["scope"],
                           "dispatcher_observation": fresh["observation"]}
                context_file = write(root / "context.json", {**context, "active_t3": not context["active_t3"]})
                cli("workflow_state.py", "dispatch", run, "inspect", "--execution-context-file", context_file, ok=False)
                write(context_file, context)
                cli("workflow_state.py", "dispatch", run, "inspect", ok=False)
                cli("workflow_state.py", "dispatch", run, "decide", "--execution-context-file", context_file, ok=False)
                dispatch = json.loads(cli("workflow_state.py", "dispatch", run, "inspect",
                                          "--execution-context-file", context_file))
                self.assertEqual(dispatch["kind"], "model")
                freeze = (run / "tasks/inspect/route_receipt.json").read_bytes()
                stale = {**fresh["observation"]}
                yesterday = datetime.now(timezone.utc) - timedelta(days=2)
                stale.update(observed_at=yesterday.isoformat(), valid_until=(yesterday + wd.WINDOW).isoformat())
                write(Path(probe["cache"]), {"target": selected, "observation": stale})
                cli("workflow_state.py", "claim", run, "inspect", ok=False)
                renewed = prepare()
                self.assertEqual(renewed["kind"], "probe")
                self.assertNotEqual(renewed["attempt"], probe["attempt"])
                cli("worker_dispatch.py", "probe-failed", renewed["cache"], probe["attempt"],
                    "--reason", "Fixture closed without a result", ok=False)
                cli("worker_dispatch.py", "probe-failed", renewed["cache"], renewed["attempt"],
                    "--reason", "Fixture closed without a result")
                renewed = prepare()
                result = native_result(selected, "fixture-worker-renewed", assignment_for(dispatcher, renewed),
                                       "READY-" + renewed["attempt"])
                fresh = json.loads(cli("worker_dispatch.py", "complete", renewed["cache"], renewed["attempt"],
                                       write(observed, result)))
                token = cli("workflow_state.py", "claim", run, "inspect")
                cli("workflow_state.py", "broker-launch", run, "inspect", "--launch-token", "wrong", ok=False)
                launch = json.loads(cli("workflow_state.py", "broker-launch", run, "inspect", "--launch-token", token,
                                        *extra))
                assignment = assignment_for(dispatcher, launch)
                cli("workflow_state.py", "broker-launch", run, "inspect", "--launch-token", token, ok=False)
                if dispatcher == "paseo":
                    path = run / "tasks/inspect/dispatcher-launch.json"
                    saved = json.loads(path.read_bytes())
                    with wd.paseo_send_slot(saved, launch, path, ws) as marker:
                        self.assertEqual(marker, path.with_name(path.name + ".paseo-sent"))
                    copy = write(path.with_name("copy.json"), saved)
                    with self.assertRaisesRegex(ValueError, "canonical"):
                        with wd.paseo_send_slot(saved, launch, copy, ws):
                            self.fail("Copied intent got a second send slot")
                self.assertNotEqual(assignment, prompt)
                cli("workflow_state.py", "start", run, "inspect", "--handle", "fixture-worker-2", "--launch-token", token)
                output = run / "tasks/inspect/output.md"
                output.write_text("Dependency output 42", encoding="utf-8")
                finish_args = (run, "inspect", "--status", "succeeded", "--output", output, "--handle", "fixture-worker-2",
                               "--launch-token", token, "--handle-closed")
                receipt_path = run / "tasks/inspect/dispatcher-result.json"
                write(receipt_path, native_result(selected, "fixture-worker-2", prompt, output.read_text()))
                cli("workflow_state.py", "finish", *finish_args, ok=False)
                write(receipt_path, native_result(selected, "fixture-worker-2", assignment, output.read_text()))
                cli("workflow_state.py", "finish", *finish_args)
                write(context_file, {**context, "dispatcher_observation": fresh["observation"]})
                output.write_text("Unverified replacement", encoding="utf-8")
                cli("workflow_state.py", "dispatch", run, "decide", "--execution-context-file", context_file, ok=False)
                output.write_text("Dependency output 42", encoding="utf-8")
                next_action = json.loads(cli("workflow_state.py", "dispatch", run, "decide",
                                             "--execution-context-file", context_file))
                self.assertIn("Dependency output 42", Path(next_action["prompt_path"]).read_text(encoding="utf-8"))
                self.assertEqual((run / "tasks/inspect/route_receipt.json").read_bytes(), freeze)


if __name__ == "__main__":
    unittest.main()
