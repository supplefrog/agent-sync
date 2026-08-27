from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[1]
RUNNER = SKILL_DIR / "scripts" / "workflow_runner.py"
TIER_CHAT = SKILL_DIR / "scripts" / "tier_chat.py"


def digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
            "utf-8"
        )
    ).hexdigest()


def route_receipt(
    *,
    model: str = "gpt-5.6-sol",
    provider: str = "openai-codex",
    reasoning_effort: str = "low",
) -> dict:
    runtime = {
        "host": "hermes",
        "host_version": "0.20.5",
        "transport": "cc-dynamic-workflow",
        "harness_version": "workflow-test-v2",
    }
    route = {
        "id": "sol-low",
        "model": model,
        "provider": provider,
        "reasoning_effort": reasoning_effort,
        "runtime": runtime,
        "runtime_sha256": digest(runtime),
    }
    constraints = {
        "target_surface": "cc-dynamic-workflow",
        "task_class": "routine-independent",
        "objective": "user-outcome",
        "failure_cost": "low",
        "verifier_plan": {"kind": "none"},
    }
    policy_sha = "a" * 64
    requirement_sha = digest(constraints)
    return {
        "schema_version": 2,
        "decision_id": digest(
            {
                "policy_sha256": policy_sha,
                "requirement_sha256": requirement_sha,
                "outcome": "selected",
                "route": route,
            }
        ),
        "outcome": "selected",
        "pin_status": "new",
        "policy_version": "candidate-test",
        "policy_sha256": policy_sha,
        "requirement_sha256": requirement_sha,
        "target_surface": "cc-dynamic-workflow",
        "task_class": "routine-independent",
        "objective": "user-outcome",
        "failure_cost": "low",
        "attempt_number": 1,
        "constraints_applied": constraints,
        "route": route,
        "metrics": {},
        "evidence_receipt": {
            "locator": "evals/results/test.json",
            "sha256": policy_sha,
        },
        "excluded": {},
        "verifier_plan": {"kind": "none"},
    }


FAKE_HERMES = r'''from __future__ import annotations
import os
import sys
import time
from pathlib import Path

args = sys.argv[1:]
if args[:2] == ["config", "get"]:
    values = {
        "model.default": os.environ.get("FAKE_MAIN_MODEL", "gpt-5.6-sol"),
        "model.provider": os.environ.get("FAKE_MAIN_PROVIDER", "provider-main"),
        "delegation.model": os.environ.get("FAKE_MINI_MODEL", "gpt-5.6-luna"),
        "delegation.provider": os.environ.get("FAKE_MINI_PROVIDER", "provider-mini"),
        "delegation.reasoning_effort": os.environ.get("FAKE_DELEGATION_EFFORT", "high"),
    }
    print(values[args[2]])
    raise SystemExit(0)

if "--ephemeral-parent-session-id" in args:
    import atexit
    import json
    from hermes_state import SessionDB

    def internal_value(name):
        return args[args.index(name) + 1]

    parent = internal_value("--ephemeral-parent-session-id")
    owner_kind = internal_value("--ephemeral-owner-kind")
    owner_pid = int(internal_value("--ephemeral-owner-pid"))
    owner_started_at = int(internal_value("--ephemeral-owner-started-at"))
    receipt_path = Path(internal_value("--ephemeral-receipt-path"))
    child = f"workflow-child-{os.getpid()}"
    db = SessionDB()
    db.create_session(child, "tool", parent_session_id=parent)
    token = db.register_ephemeral_session(
        parent_session_id=parent,
        child_session_id=child,
        owner_kind=owner_kind,
        owner_pid=owner_pid,
        owner_started_at=owner_started_at,
        synthetic_user_messages=1,
    )
    db.append_message(child, "user", "workflow task prompt")
    receipt_path.write_text(
        json.dumps(
            {
                "ownership_token": token,
                "parent_session_id": parent,
                "child_session_id": child,
                "owner_kind": owner_kind,
                "owner_pid": owner_pid,
                "owner_started_at": owner_started_at,
            }
        ),
        encoding="utf-8",
    )
    db.close()

    def close_child_session():
        close_db = SessionDB()
        close_db.end_session(child, "agent_close")
        close_db.close()

    atexit.register(close_child_session)
query = args[args.index("-q") + 1]
start = query.index(" at ") + 4
end = query.index(" and execute it exactly")
prompt_path = Path(query[start:end])
prompt = prompt_path.read_text(encoding="utf-8")
if "ADOPT_CHILD" in prompt and "child" in globals():
    from hermes_state import SessionDB

    adoption_db = SessionDB()
    adoption_db.append_message(child, "user", "user adopted workflow child")
    adoption_db.close()
print("FAKE_RESULT")
print("ARGS=" + " ".join(args))
print("EFFORT=" + os.environ.get("HERMES_WORKFLOW_REASONING_EFFORT", ""))
print("INHERITED_IDENTITIES=" + ",".join(sorted(
    key for key in os.environ
    if key.startswith(("HERMES_KANBAN_", "HERMES_SESSION_", "HERMES_DELEGATION_"))
    or key == "HERMES_DELEGATED_CHILD_CONTEXT"
)))
print(prompt)
if "FAIL_ONCE" in prompt:
    marker = prompt_path.with_suffix(".attempted")
    if not marker.exists():
        marker.write_text("1", encoding="utf-8")
        raise SystemExit(9)
if "FAIL_TASK" in prompt:
    raise SystemExit(7)
if "ESCALATE_ONCE" in prompt:
    marker = prompt_path.with_suffix(".escalated")
    if not marker.exists():
        marker.write_text("1", encoding="utf-8")
        print("WORKFLOW_ESCALATE: deterministic test request")
if "ESCALATE_ALWAYS" in prompt:
    print("WORKFLOW_ESCALATE: deterministic persistent request")
if "REJECT_PRODUCER_ONCE" in prompt:
    marker = prompt_path.with_suffix(".rejected")
    if not marker.exists():
        marker.write_text("1", encoding="utf-8")
        print("WORKFLOW_REJECT: producer: deterministic quality rejection")
if "REJECT_PRODUCER_ALWAYS" in prompt:
    print("WORKFLOW_REJECT: producer: deterministic persistent rejection")
if "REJECT_MALFORMED" in prompt:
    print("WORKFLOW_REJECT: malformed")
if "MENTION_REJECT_THEN_ACCEPT" in prompt:
    print("WORKFLOW_REJECT: producer: discussed, not final")
    print("ACCEPTED_AFTER_DISCUSSION")
if "SLEEP_TASK" in prompt:
    time.sleep(30)
if "BIG_OUTPUT" in prompt:
    print("X" * 120000)
'''


class WorkflowRunnerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.project = self.root / "project"
        self.project.mkdir()
        self.fake = self.root / "fake_hermes.py"
        self.fake.write_text(FAKE_HERMES, encoding="utf-8")
        self.env = os.environ.copy()
        for key in list(self.env):
            if (
                key.startswith("HERMES_KANBAN_")
                or key.startswith("HERMES_SESSION_")
                or key.startswith("HERMES_DELEGATION_")
                or key == "HERMES_DELEGATED_CHILD_CONTEXT"
            ):
                self.env.pop(key, None)
        self.env["HERMES_WORKFLOWS_HOME"] = str(self.root / "workflow-home")
        self.env["HERMES_HOME"] = str(self.root / "hermes-home")
        source_root = str(Path.cwd())
        existing_pythonpath = self.env.get("PYTHONPATH", "")
        self.env["PYTHONPATH"] = (
            source_root + (os.pathsep + existing_pythonpath if existing_pythonpath else "")
        )
        self.env["HERMES_WORKFLOW_TEST_ALLOW_UNPATCHED_HERMES"] = "1"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def write_plan(self, value: dict) -> Path:
        path = self.project / "plan.json"
        path.write_text(json.dumps(value), encoding="utf-8")
        return path

    def call(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(RUNNER), *args],
            env=self.env,
            text=True,
            capture_output=True,
            timeout=30,
        )

    def only_run_dir(self) -> Path:
        runs = list((self.root / "workflow-home" / "runs").iterdir())
        self.assertEqual(len(runs), 1)
        return runs[0]

    def create_parent_session(self, session_id: str = "workflow-parent") -> str:
        from hermes_state import SessionDB

        previous = os.environ.get("HERMES_HOME")
        os.environ["HERMES_HOME"] = self.env["HERMES_HOME"]
        try:
            db = SessionDB()
            db.create_session(session_id, "cli")
            db.close()
        finally:
            if previous is None:
                os.environ.pop("HERMES_HOME", None)
            else:
                os.environ["HERMES_HOME"] = previous
        self.env["HERMES_SESSION_ID"] = session_id
        return session_id

    def lifecycle_rows(self, parent_session_id: str) -> tuple[list[dict], bool]:
        from hermes_state import SessionDB

        previous = os.environ.get("HERMES_HOME")
        os.environ["HERMES_HOME"] = self.env["HERMES_HOME"]
        try:
            db = SessionDB()
            try:
                rows = [
                    dict(row)
                    for row in db._conn.execute(
                        "SELECT child_session_id, terminal_state, protected, "
                        "output_integrated, protection_reason "
                        "FROM ephemeral_session_ownership "
                        "WHERE parent_session_id = ? ORDER BY created_at",
                        (parent_session_id,),
                    ).fetchall()
                ]
                parent_exists = db.get_session(parent_session_id) is not None
                return rows, parent_exists
            finally:
                db.close()
        finally:
            if previous is None:
                os.environ.pop("HERMES_HOME", None)
            else:
                os.environ["HERMES_HOME"] = previous

    def test_parallel_dag_persists_outputs_and_injects_dependencies(self) -> None:
        plan = self.write_plan(
            {
                "name": "dependency-test",
                "max_workers": 2,
                "tasks": [
                    {"id": "first", "prompt": "FIRST_TOKEN", "workdir": "."},
                    {"id": "peer", "prompt": "PEER_TOKEN", "workdir": "."},
                    {
                        "id": "final",
                        "prompt": "SYNTHESIZE {{output:first}}",
                        "depends_on": ["first", "peer"],
                        "include_outputs": ["first"],
                        "workdir": ".",
                    },
                ],
            }
        )
        result = self.call("run", str(plan), "--hermes", str(self.fake))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        run_dir = self.only_run_dir()
        state = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["status"], "succeeded")
        self.assertTrue(all(task["status"] == "succeeded" for task in state["tasks"].values()))
        final_output = (run_dir / "outputs" / "final.txt").read_text(encoding="utf-8")
        self.assertIn("FIRST_TOKEN", final_output)
        self.assertIn("Output from workflow task first", final_output)

    def test_child_process_does_not_inherit_parent_controller_identity(self) -> None:
        self.create_parent_session("parent-session")
        self.env.update(
            HERMES_KANBAN_TASK="parent-task",
            HERMES_DELEGATED_CHILD_CONTEXT="parent-context",
            HERMES_DELEGATION_TOKEN="parent-token",
        )
        plan = self.write_plan(
            {
                "name": "identity-isolation",
                "tasks": [{"id": "child", "prompt": "CHECK_ENV", "workdir": "."}],
            }
        )
        result = self.call("run", str(plan), "--hermes", str(self.fake))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        output = (self.only_run_dir() / "outputs" / "child.txt").read_text(encoding="utf-8")
        self.assertIn("INHERITED_IDENTITIES=", output)
        self.assertNotIn("HERMES_SESSION_ID", output)
        self.assertNotIn("HERMES_KANBAN_TASK", output)
        self.assertNotIn("HERMES_DELEGATED_CHILD_CONTEXT", output)

    def test_workflow_child_uses_spawn_time_receipt_and_deletes_after_integration(self) -> None:
        from hermes_state import SessionDB

        parent = self.create_parent_session()
        plan = self.write_plan(
            {
                "name": "lifecycle-success",
                "tasks": [{"id": "child", "prompt": "LIFECYCLE", "workdir": "."}],
            }
        )

        result = self.call("run", str(plan), "--hermes", str(self.fake))

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        state = json.loads((self.only_run_dir() / "state.json").read_text(encoding="utf-8"))
        child_state = state["tasks"]["child"]
        self.assertEqual(child_state["lifecycle_state"], "deleted")
        self.assertTrue(child_state["child_session_id"])
        previous = os.environ.get("HERMES_HOME")
        os.environ["HERMES_HOME"] = self.env["HERMES_HOME"]
        try:
            db = SessionDB()
            self.assertIsNone(db.get_session(child_state["child_session_id"]))
            self.assertIsNotNone(db.get_session(parent))
            db.close()
        finally:
            if previous is None:
                os.environ.pop("HERMES_HOME", None)
            else:
                os.environ["HERMES_HOME"] = previous
        attempt = Path(child_state["attempt_history"][0]["output"])
        receipt = json.loads(attempt.with_suffix(".lifecycle.json").read_text(encoding="utf-8"))
        self.assertEqual(receipt["child_session_id"], child_state["child_session_id"])
        self.assertIn("--ephemeral-parent-session-id", attempt.read_text(encoding="utf-8"))

    def test_workflow_user_adoption_retains_child(self) -> None:
        from hermes_state import SessionDB

        self.create_parent_session("workflow-parent-adoption")
        plan = self.write_plan(
            {
                "name": "lifecycle-adoption",
                "tasks": [{"id": "child", "prompt": "ADOPT_CHILD", "workdir": "."}],
            }
        )

        result = self.call("run", str(plan), "--hermes", str(self.fake))

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        state = json.loads((self.only_run_dir() / "state.json").read_text(encoding="utf-8"))
        child_state = state["tasks"]["child"]
        self.assertEqual(child_state["lifecycle_state"], "retained_ambiguous")
        previous = os.environ.get("HERMES_HOME")
        os.environ["HERMES_HOME"] = self.env["HERMES_HOME"]
        try:
            db = SessionDB()
            self.assertIsNotNone(db.get_session(child_state["child_session_id"]))
            owner = db._conn.execute(
                "SELECT adopted FROM ephemeral_session_ownership WHERE child_session_id = ?",
                (child_state["child_session_id"],),
            ).fetchone()
            self.assertEqual(owner["adopted"], 1)
            db.close()
        finally:
            if previous is None:
                os.environ.pop("HERMES_HOME", None)
            else:
                os.environ["HERMES_HOME"] = previous

    def test_failure_blocks_dependents_and_returns_nonzero(self) -> None:
        parent = self.create_parent_session("workflow-parent-failure")
        plan = self.write_plan(
            {
                "name": "failure-test",
                "tasks": [
                    {"id": "bad", "prompt": "FAIL_TASK", "workdir": "."},
                    {
                        "id": "blocked",
                        "prompt": "must not run",
                        "depends_on": ["bad"],
                        "workdir": ".",
                    },
                ],
            }
        )
        result = self.call("run", str(plan), "--hermes", str(self.fake))
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        state = json.loads((self.only_run_dir() / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["tasks"]["bad"]["status"], "failed")
        self.assertEqual(state["tasks"]["blocked"]["status"], "blocked")
        rows, parent_exists = self.lifecycle_rows(parent)
        self.assertTrue(parent_exists)
        self.assertEqual(len(rows), 3)
        self.assertTrue(all(row["terminal_state"] == "failed" for row in rows))
        self.assertTrue(all(row["protected"] == 1 for row in rows))
        self.assertTrue(all(row["output_integrated"] == 0 for row in rows))
        self.assertTrue(all(row["protection_reason"] == "retain_evidence" for row in rows))

    def test_retry_uses_declared_attempt_budget(self) -> None:
        plan = self.write_plan(
            {
                "name": "retry-test",
                "tasks": [
                    {"id": "flaky", "prompt": "FAIL_ONCE", "attempts": 2, "workdir": "."}
                ],
            }
        )
        result = self.call("run", str(plan), "--hermes", str(self.fake))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        state = json.loads((self.only_run_dir() / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["tasks"]["flaky"]["status"], "succeeded")
        self.assertEqual(state["tasks"]["flaky"]["attempts_used"], 2)

    def test_saved_workflow_variables_are_required_and_substituted(self) -> None:
        plan = self.write_plan(
            {
                "name": "variables",
                "tasks": [{"id": "answer", "prompt": "Topic={{var:TOPIC}}", "workdir": "."}],
            }
        )
        missing = self.call("run", str(plan), "--hermes", str(self.fake))
        self.assertEqual(missing.returncode, 2)
        self.assertIn("Missing workflow variables: TOPIC", missing.stderr)
        result = self.call(
            "run", str(plan), "--hermes", str(self.fake), "--var", "TOPIC=dynamic workflows"
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        output = (self.only_run_dir() / "outputs" / "answer.txt").read_text(encoding="utf-8")
        self.assertIn("Topic=dynamic workflows", output)

    def test_stop_terminates_active_task_and_persists_stopped_state(self) -> None:
        parent = self.create_parent_session("workflow-parent-stop")
        plan = self.write_plan(
            {
                "name": "stop-test",
                "tasks": [{"id": "slow", "prompt": "SLEEP_TASK", "workdir": "."}],
            }
        )
        runner = subprocess.Popen(
            [sys.executable, str(RUNNER), "run", str(plan), "--hermes", str(self.fake)],
            env=self.env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        run_dir = None
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            root = self.root / "workflow-home" / "runs"
            runs = list(root.iterdir()) if root.exists() else []
            if runs:
                candidate = runs[0]
                state_path = candidate / "state.json"
                if not state_path.exists():
                    time.sleep(0.05)
                    continue
                state = json.loads(state_path.read_text(encoding="utf-8"))
                if state["tasks"]["slow"]["status"] == "running":
                    attempt = state["tasks"]["slow"]["attempt_history"][0]["output"]
                    if Path(attempt).with_suffix(".lifecycle.json").exists():
                        run_dir = candidate
                        break
            time.sleep(0.1)
        self.assertIsNotNone(run_dir, "task did not enter running state")
        stopped = self.call("stop", str(run_dir))
        self.assertEqual(stopped.returncode, 0, stopped.stdout + stopped.stderr)
        output, _ = runner.communicate(timeout=15)
        self.assertEqual(runner.returncode, 1, output)
        state = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["status"], "stopped")
        self.assertEqual(state["tasks"]["slow"]["status"], "stopped")
        self.assertEqual(state["tasks"]["slow"]["attempt_history"][0]["outcome"], "stopped")
        self.assertTrue((run_dir / "outputs" / "slow.txt").exists())
        rows, parent_exists = self.lifecycle_rows(parent)
        self.assertTrue(parent_exists)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["terminal_state"], "stopped")
        self.assertEqual(rows[0]["protected"], 1)
        self.assertEqual(rows[0]["output_integrated"], 0)

    def test_dependency_injection_has_a_total_context_budget(self) -> None:
        plan = self.write_plan(
            {
                "name": "injection-budget",
                "max_workers": 2,
                "tasks": [
                    {"id": "large-a", "prompt": "BIG_OUTPUT A", "workdir": "."},
                    {"id": "large-b", "prompt": "BIG_OUTPUT B", "workdir": "."},
                    {
                        "id": "final",
                        "prompt": "combine",
                        "depends_on": ["large-a", "large-b"],
                        "include_outputs": ["large-a", "large-b"],
                        "workdir": ".",
                    },
                ],
            }
        )
        result = self.call("run", str(plan), "--hermes", str(self.fake))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        prompt = (self.only_run_dir() / "prompts" / "final.md").read_text(encoding="utf-8")
        self.assertLess(len(prompt), 155000)
        self.assertEqual(prompt.count("injected text truncated"), 2)

    def test_role_defaults_and_explicit_mini_route_to_four_pinned_tiers(self) -> None:
        plan = self.write_plan(
            {
                "name": "tier-routing",
                "max_workers": 4,
                "tasks": [
                    {"id": "worker", "prompt": "WORK", "workdir": "."},
                    {"id": "verify", "role": "verifier", "prompt": "VERIFY", "workdir": "."},
                    {"id": "refute", "role": "refuter", "prompt": "REFUTE", "workdir": "."},
                    {"id": "trivial", "model_tier": "mini", "prompt": "TRIVIAL", "workdir": "."},
                ],
            }
        )
        result = self.call("run", str(plan), "--hermes", str(self.fake))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        run_dir = self.only_run_dir()
        expected = {
            "worker": ("low", "gpt-5.6-luna", "openai-codex", "high"),
            "verify": ("medium", "gpt-5.6-sol", "openai-codex", "medium"),
            "refute": ("high", "gpt-5.6-sol", "openai-codex", "high"),
            "trivial": ("mini", "gpt-5.6-luna", "provider-mini", "low"),
        }
        state = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))
        for task_id, (tier, model, provider, effort) in expected.items():
            task_state = state["tasks"][task_id]
            self.assertEqual(task_state["model_tier"], tier)
            self.assertEqual(task_state["model"], model)
            self.assertEqual(task_state["provider"], provider)
            self.assertEqual(task_state["reasoning_effort"], effort)
            output = (run_dir / "outputs" / f"{task_id}.txt").read_text(encoding="utf-8")
            self.assertIn(f"--model {model} --provider {provider}", output)
            self.assertIn(f"EFFORT={effort}", output)

    def test_explicit_marker_escalates_once_then_succeeds(self) -> None:
        plan = self.write_plan(
            {
                "name": "marker-escalation",
                "tasks": [
                    {
                        "id": "task",
                        "model_tier": "mini",
                        "max_model_tier": "medium",
                        "prompt": "ESCALATE_ONCE",
                        "workdir": ".",
                    }
                ],
            }
        )
        result = self.call("run", str(plan), "--hermes", str(self.fake))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        state = json.loads((self.only_run_dir() / "state.json").read_text(encoding="utf-8"))
        task = state["tasks"]["task"]
        self.assertEqual(task["status"], "succeeded")
        self.assertEqual(task["model_tier"], "low")
        self.assertEqual([entry["tier"] for entry in task["attempt_history"]], ["mini", "low"])
        self.assertIn("WORKFLOW_ESCALATE:", task["attempt_history"][0]["reason"])

    def test_success_does_not_escalate_even_with_spare_attempts(self) -> None:
        plan = self.write_plan(
            {
                "name": "no-unneeded-escalation",
                "tasks": [
                    {
                        "id": "task",
                        "model_tier": "mini",
                        "attempts": 4,
                        "prompt": "SUCCEED",
                        "workdir": ".",
                    }
                ],
            }
        )
        result = self.call("run", str(plan), "--hermes", str(self.fake))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        task = json.loads((self.only_run_dir() / "state.json").read_text(encoding="utf-8"))["tasks"]["task"]
        self.assertEqual(task["attempts_used"], 1)
        self.assertEqual([entry["tier"] for entry in task["attempt_history"]], ["mini"])

    def test_verifier_rejection_escalates_only_its_target_and_rechecks(self) -> None:
        parent = self.create_parent_session("workflow-parent-adaptive")
        plan = self.write_plan(
            {
                "name": "adaptive-verification",
                "tasks": [
                    {"id": "producer", "prompt": "PRODUCE", "workdir": "."},
                    {
                        "id": "verify",
                        "role": "verifier",
                        "prompt": "REJECT_PRODUCER_ONCE",
                        "depends_on": ["producer"],
                        "include_outputs": ["producer"],
                        "verifies": ["producer"],
                        "workdir": ".",
                    },
                    {
                        "id": "consume",
                        "prompt": "CONSUME",
                        "depends_on": ["producer", "verify"],
                        "include_outputs": ["producer"],
                        "workdir": ".",
                    },
                ],
            }
        )
        result = self.call("run", str(plan), "--hermes", str(self.fake))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        run_dir = self.only_run_dir()
        state = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))
        producer = state["tasks"]["producer"]
        verifier = state["tasks"]["verify"]
        self.assertEqual([entry["tier"] for entry in producer["attempt_history"]], ["low", "medium"])
        self.assertEqual([entry["outcome"] for entry in verifier["attempt_history"]], ["rejected", "succeeded"])
        self.assertEqual(producer["feedback_history"][0]["verifier"], "verify")
        self.assertEqual(producer["feedback_history"][0]["from_tier"], "low")
        self.assertEqual(producer["feedback_history"][0]["to_tier"], "medium")
        consumed = (run_dir / "outputs" / "consume.txt").read_text(encoding="utf-8")
        self.assertIn("EFFORT=medium", consumed)
        rows, parent_exists = self.lifecycle_rows(parent)
        self.assertTrue(parent_exists)
        self.assertEqual(rows, [])

    def test_verifier_acceptance_does_not_rerun_a_successful_target(self) -> None:
        plan = self.write_plan(
            {
                "name": "adaptive-verification-accepted",
                "tasks": [
                    {"id": "producer", "prompt": "PRODUCE", "workdir": "."},
                    {
                        "id": "verify",
                        "role": "verifier",
                        "prompt": "ACCEPT",
                        "depends_on": ["producer"],
                        "include_outputs": ["producer"],
                        "verifies": ["producer"],
                        "workdir": ".",
                    },
                ],
            }
        )
        result = self.call("run", str(plan), "--hermes", str(self.fake))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        state = json.loads((self.only_run_dir() / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(len(state["tasks"]["producer"]["attempt_history"]), 1)
        self.assertEqual(len(state["tasks"]["verify"]["attempt_history"]), 1)
        self.assertEqual(state["tasks"]["producer"]["feedback_history"], [])

    def test_malformed_verifier_feedback_fails_the_gate(self) -> None:
        plan = self.write_plan(
            {
                "name": "adaptive-verification-malformed",
                "tasks": [
                    {"id": "producer", "prompt": "PRODUCE", "workdir": "."},
                    {
                        "id": "verify",
                        "role": "verifier",
                        "prompt": "REJECT_MALFORMED",
                        "depends_on": ["producer"],
                        "include_outputs": ["producer"],
                        "verifies": ["producer"],
                        "workdir": ".",
                    },
                ],
            }
        )
        result = self.call("run", str(plan), "--hermes", str(self.fake))
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        state = json.loads((self.only_run_dir() / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["tasks"]["verify"]["status"], "failed")
        self.assertIn("invalid target", state["tasks"]["verify"]["error"])

    def test_nonfinal_rejection_marker_does_not_override_acceptance(self) -> None:
        plan = self.write_plan(
            {
                "name": "adaptive-verification-nonfinal-marker",
                "tasks": [
                    {"id": "producer", "prompt": "PRODUCE", "workdir": "."},
                    {
                        "id": "verify",
                        "role": "verifier",
                        "prompt": "MENTION_REJECT_THEN_ACCEPT",
                        "depends_on": ["producer"],
                        "include_outputs": ["producer"],
                        "verifies": ["producer"],
                        "workdir": ".",
                    },
                ],
            }
        )
        result = self.call("run", str(plan), "--hermes", str(self.fake))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        state = json.loads((self.only_run_dir() / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(len(state["tasks"]["producer"]["attempt_history"]), 1)
        self.assertEqual(state["tasks"]["producer"]["feedback_history"], [])

    def test_verifier_rejection_fails_closed_when_target_cannot_escalate(self) -> None:
        plan = self.write_plan(
            {
                "name": "adaptive-verification-exhausted",
                "tasks": [
                    {
                        "id": "producer",
                        "model_tier": "high",
                        "prompt": "PRODUCE",
                        "workdir": ".",
                    },
                    {
                        "id": "verify",
                        "role": "verifier",
                        "prompt": "REJECT_PRODUCER_ALWAYS",
                        "depends_on": ["producer"],
                        "include_outputs": ["producer"],
                        "verifies": ["producer"],
                        "workdir": ".",
                    },
                    {
                        "id": "consume",
                        "prompt": "MUST_NOT_RUN",
                        "depends_on": ["producer", "verify"],
                        "workdir": ".",
                    },
                ],
            }
        )
        result = self.call("run", str(plan), "--hermes", str(self.fake))
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        state = json.loads((self.only_run_dir() / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["tasks"]["producer"]["status"], "failed")
        self.assertEqual(state["tasks"]["verify"]["status"], "failed")
        self.assertEqual(state["tasks"]["consume"]["status"], "blocked")
        self.assertIn("cannot escalate", state["tasks"]["producer"]["error"])

    def test_adaptive_verifier_requires_gated_consumers(self) -> None:
        plan = self.write_plan(
            {
                "name": "ungated-verification",
                "tasks": [
                    {"id": "producer", "prompt": "PRODUCE", "workdir": "."},
                    {
                        "id": "verify",
                        "role": "verifier",
                        "prompt": "VERIFY",
                        "depends_on": ["producer"],
                        "include_outputs": ["producer"],
                        "verifies": ["producer"],
                        "workdir": ".",
                    },
                    {
                        "id": "ungated",
                        "prompt": "CONSUME",
                        "depends_on": ["producer"],
                        "workdir": ".",
                    },
                ],
            }
        )
        result = self.call("validate", str(plan))
        self.assertEqual(result.returncode, 2)
        self.assertIn("must also depend on verifier", result.stderr)

    def test_max_tier_bounds_persistent_escalation_request(self) -> None:
        plan = self.write_plan(
            {
                "name": "bounded-escalation",
                "tasks": [
                    {
                        "id": "task",
                        "model_tier": "low",
                        "max_model_tier": "medium",
                        "prompt": "ESCALATE_ALWAYS",
                        "workdir": ".",
                    }
                ],
            }
        )
        result = self.call("run", str(plan), "--hermes", str(self.fake))
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        task = json.loads((self.only_run_dir() / "state.json").read_text(encoding="utf-8"))["tasks"]["task"]
        self.assertEqual(task["status"], "failed")
        self.assertEqual([entry["tier"] for entry in task["attempt_history"]], ["low", "medium"])
        self.assertNotIn("high", [entry["tier"] for entry in task["attempt_history"]])

    def test_fixed_task_route_cannot_bypass_required_policy(self) -> None:
        plan = self.write_plan(
            {
                "name": "fixed-route",
                "tasks": [
                    {
                        "id": "custom",
                        "role": "verifier",
                        "model": "custom-model",
                        "provider": "custom-provider",
                        "prompt": "CUSTOM",
                        "workdir": ".",
                    }
                ],
            }
        )
        result = self.call("run", str(plan), "--hermes", str(self.fake))
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("fixed route conflicts", result.stderr)

    def test_automatic_routing_selects_and_pins_exact_route(self) -> None:
        plan = self.write_plan(
            {
                "name": "automatic-route",
                "automatic_routing": True,
                "tasks": [
                    {
                        "id": "custom",
                        "prompt": "CUSTOM",
                        "workdir": ".",
                        "intelligence_tier": "routine",
                        "latency_sensitive": False,
                        "failure_cost": "low",
                    }
                ],
            }
        )

        result = self.call("run", str(plan), "--hermes", str(self.fake))

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        run_dir = self.only_run_dir()
        state = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))
        task = state["tasks"]["custom"]
        self.assertEqual(task["model"], "gpt-5.6-luna")
        self.assertEqual(task["provider"], "openai-codex")
        self.assertEqual(task["reasoning_effort"], "medium")
        self.assertEqual(task["route_decision_receipt"]["outcome"], "selected")
        self.assertEqual(
            task["attempt_history"][0]["route_decision_receipt"],
            task["route_decision_receipt"],
        )
        materialized = json.loads((run_dir / "plan.json").read_text(encoding="utf-8"))
        self.assertEqual(materialized["tasks"][0]["decision_receipt"], task["route_decision_receipt"])
        output = (run_dir / "outputs" / "custom.txt").read_text(encoding="utf-8")
        self.assertIn("--model gpt-5.6-luna --provider openai-codex", output)
        self.assertIn("EFFORT=medium", output)

    def test_automatic_routing_accepts_max_reasoning_and_rejects_manual_route(self) -> None:
        automatic = self.write_plan(
            {
                "name": "automatic-max-route",
                "automatic_routing": True,
                "tasks": [
                    {
                        "id": "custom",
                        "prompt": "CUSTOM",
                        "intelligence_tier": "maximum",
                        "latency_sensitive": False,
                        "failure_cost": "high",
                    }
                ],
            }
        )
        result = self.call("run", str(automatic), "--hermes", str(self.fake))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        task = json.loads((self.only_run_dir() / "state.json").read_text(encoding="utf-8"))["tasks"]["custom"]
        self.assertEqual(task["model"], "gpt-5.6-sol")
        self.assertEqual(task["reasoning_effort"], "max")

        manual = self.write_plan(
            {
                "name": "automatic-manual-conflict",
                "automatic_routing": True,
                "tasks": [
                    {
                        "id": "custom",
                        "prompt": "CUSTOM",
                        "intelligence_tier": "routine",
                        "latency_sensitive": False,
                        "model": "gpt-5.6-sol",
                        "provider": "openai-codex",
                    }
                ],
            }
        )
        rejected = self.call("validate", str(manual))
        self.assertEqual(rejected.returncode, 2)
        self.assertIn("automatic_routing tasks cannot set model", rejected.stderr)

    def test_automatic_routing_requires_task_requirements(self) -> None:
        plan = self.write_plan(
            {
                "name": "automatic-missing-requirements",
                "automatic_routing": True,
                "tasks": [{"id": "custom", "prompt": "CUSTOM"}],
            }
        )
        result = self.call("validate", str(plan))
        self.assertEqual(result.returncode, 2)
        self.assertIn("intelligence_tier", result.stderr)

    def test_evidence_receipt_pins_exact_route_outside_legacy_tiers(self) -> None:
        receipt = route_receipt()
        plan = self.write_plan(
            {
                "name": "receipt-route",
                "tasks": [
                    {
                        "id": "custom",
                        "model": "gpt-5.6-sol",
                        "provider": "openai-codex",
                        "reasoning_effort": "low",
                        "decision_receipt": receipt,
                        "prompt": "CUSTOM",
                        "workdir": ".",
                    }
                ],
            }
        )

        result = self.call("run", str(plan), "--hermes", str(self.fake))

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        state = json.loads((self.only_run_dir() / "state.json").read_text(encoding="utf-8"))
        task = state["tasks"]["custom"]
        self.assertEqual(task["model"], "gpt-5.6-sol")
        self.assertEqual(task["provider"], "openai-codex")
        self.assertEqual(task["reasoning_effort"], "low")
        self.assertEqual(task["route_decision_receipt"], receipt)
        self.assertEqual(task["attempt_history"][0]["route_decision_receipt"], receipt)
        output = (self.only_run_dir() / "outputs" / "custom.txt").read_text(encoding="utf-8")
        self.assertIn("--model gpt-5.6-sol --provider openai-codex", output)
        self.assertIn("EFFORT=low", output)

    def test_receipt_route_must_match_exact_task_route(self) -> None:
        receipt = route_receipt(model="other-model")
        plan = self.write_plan(
            {
                "name": "receipt-mismatch",
                "tasks": [
                    {
                        "id": "custom",
                        "model": "gpt-5.6-sol",
                        "provider": "openai-codex",
                        "reasoning_effort": "low",
                        "decision_receipt": receipt,
                        "prompt": "CUSTOM",
                    }
                ],
            }
        )

        result = self.call("validate", str(plan))

        self.assertEqual(result.returncode, 2)
        self.assertIn("route model must match", result.stderr)

    def test_receipt_constraints_cannot_be_rebound_to_another_task_class(self) -> None:
        receipt = route_receipt()
        receipt["constraints_applied"]["task_class"] = "other-class"
        receipt["requirement_sha256"] = digest(receipt["constraints_applied"])
        receipt["decision_id"] = digest(
            {
                "policy_sha256": receipt["policy_sha256"],
                "requirement_sha256": receipt["requirement_sha256"],
                "outcome": "selected",
                "route": receipt["route"],
            }
        )
        plan = self.write_plan(
            {
                "name": "receipt-constraints-mismatch",
                "tasks": [
                    {
                        "id": "custom",
                        "model": "gpt-5.6-sol",
                        "provider": "openai-codex",
                        "reasoning_effort": "low",
                        "decision_receipt": receipt,
                        "prompt": "CUSTOM",
                    }
                ],
            }
        )

        result = self.call("validate", str(plan))

        self.assertEqual(result.returncode, 2)
        self.assertIn("constraints do not match task_class", result.stderr)

    def test_plan_model_policy_cannot_bypass_required_policy(self) -> None:
        plan = self.write_plan(
            {
                "name": "policy-bypass",
                "model_policy": {
                    "low": {
                        "model": "gpt-5.6-sol",
                        "provider": "provider-main",
                        "reasoning_effort": "low",
                    }
                },
                "tasks": [{"id": "task", "prompt": "TASK", "workdir": "."}],
            }
        )
        result = self.call("run", str(plan), "--hermes", str(self.fake))
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("must use model 'gpt-5.6-luna' at 'high' effort", result.stderr)

    def test_plan_provider_cannot_bypass_active_route_policy(self) -> None:
        plan = self.write_plan(
            {
                "name": "provider-bypass",
                "model_policy": {
                    "low": {
                        "model": "gpt-5.6-luna",
                        "provider": "different-provider",
                        "reasoning_effort": "high",
                    }
                },
                "tasks": [{"id": "task", "prompt": "TASK", "workdir": "."}],
            }
        )
        result = self.call("run", str(plan), "--hermes", str(self.fake))
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("through provider 'openai-codex'", result.stderr)

    def test_resume_keeps_the_original_pinned_model_policy(self) -> None:
        plan = self.write_plan(
            {
                "name": "pinned-resume",
                "tasks": [
                    {
                        "id": "bad",
                        "model_tier": "mini",
                        "max_model_tier": "mini",
                        "prompt": "FAIL_TASK",
                        "workdir": ".",
                    }
                ],
            }
        )
        first = self.call("run", str(plan), "--hermes", str(self.fake))
        self.assertEqual(first.returncode, 1, first.stdout + first.stderr)
        run_dir = self.only_run_dir()
        self.env["FAKE_MINI_MODEL"] = "gpt-5.6-luna-v2"
        resumed = self.call("resume", str(run_dir), "--retry-failed", "--hermes", str(self.fake))
        self.assertEqual(resumed.returncode, 1, resumed.stdout + resumed.stderr)
        state = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["model_policy"]["mini"]["model"], "gpt-5.6-luna")
        self.assertEqual(state["tasks"]["bad"]["model"], "gpt-5.6-luna")
        self.assertEqual(
            [entry["attempt"] for entry in state["tasks"]["bad"]["attempt_history"]],
            [1, 2],
        )
        self.assertEqual(
            [entry["retry_cycle"] for entry in state["tasks"]["bad"]["attempt_history"]],
            [0, 1],
        )
        output = (run_dir / "outputs" / "bad.txt").read_text(encoding="utf-8")
        self.assertIn("--model gpt-5.6-luna --provider provider-mini", output)
        self.assertNotIn("gpt-5.6-luna-v2", output)

    def test_resume_refuses_while_recorded_child_pid_is_alive(self) -> None:
        plan = self.write_plan(
            {
                "name": "live-child-resume",
                "tasks": [{"id": "bad", "prompt": "FAIL_TASK", "workdir": "."}],
            }
        )
        first = self.call("run", str(plan), "--hermes", str(self.fake))
        self.assertEqual(first.returncode, 1, first.stdout + first.stderr)
        run_dir = self.only_run_dir()
        state_path = run_dir / "state.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["tasks"]["bad"].update(status="running", pid=os.getpid())
        state_path.write_text(json.dumps(state), encoding="utf-8")

        resumed = self.call("resume", str(run_dir), "--retry-failed", "--hermes", str(self.fake))
        self.assertEqual(resumed.returncode, 2, resumed.stdout + resumed.stderr)
        self.assertIn("recorded child process", resumed.stderr)

    def test_pre_tier_run_preserves_legacy_main_model_behavior_on_resume(self) -> None:
        plan = self.write_plan(
            {
                "name": "legacy-resume",
                "tasks": [{"id": "bad", "prompt": "FAIL_TASK", "workdir": "."}],
            }
        )
        first = self.call("run", str(plan), "--hermes", str(self.fake))
        self.assertEqual(first.returncode, 1, first.stdout + first.stderr)
        run_dir = self.only_run_dir()
        state_path = run_dir / "state.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state.pop("model_policy")
        for key in ("role", "model_tier", "model", "provider"):
            state["tasks"]["bad"].pop(key)
        state_path.write_text(json.dumps(state), encoding="utf-8")

        self.env["FAKE_MAIN_MODEL"] = "legacy-main"
        self.env["FAKE_MAIN_PROVIDER"] = "legacy-provider"
        resumed = self.call(
            "resume", str(run_dir), "--retry-failed", "--hermes", str(self.fake)
        )
        self.assertEqual(resumed.returncode, 1, resumed.stdout + resumed.stderr)
        state = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual(state["model_policy"]["legacy"]["model"], "legacy-main")
        self.assertEqual(state["tasks"]["bad"]["model_tier"], "legacy")
        self.assertEqual(state["tasks"]["bad"]["model"], "legacy-main")
        output = (run_dir / "outputs" / "bad.txt").read_text(encoding="utf-8")
        self.assertIn("--model legacy-main --provider legacy-provider", output)

    def test_timeout_escalates_and_stops_at_declared_max_tier(self) -> None:
        parent = self.create_parent_session("workflow-parent-timeout")
        plan = self.write_plan(
            {
                "name": "timeout-escalation",
                "tasks": [
                    {
                        "id": "slow",
                        "model_tier": "low",
                        "max_model_tier": "medium",
                        "timeout_seconds": 1,
                        "prompt": "SLEEP_TASK",
                        "workdir": ".",
                    }
                ],
            }
        )
        result = self.call("run", str(plan), "--hermes", str(self.fake))
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        task = json.loads((self.only_run_dir() / "state.json").read_text(encoding="utf-8"))["tasks"]["slow"]
        self.assertEqual([entry["tier"] for entry in task["attempt_history"]], ["low", "medium"])
        self.assertTrue(all("Timed out after 1 seconds" in entry["reason"] for entry in task["attempt_history"]))
        rows, parent_exists = self.lifecycle_rows(parent)
        self.assertTrue(parent_exists)
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(row["terminal_state"] == "failed" for row in rows))
        self.assertTrue(all(row["protected"] == 1 for row in rows))
        self.assertTrue(all(row["output_integrated"] == 0 for row in rows))

    def test_tier_chat_patches_reasoning_only_inside_child_process(self) -> None:
        modules = self.root / "fake-modules"
        (modules / "hermes_cli").mkdir(parents=True)
        (modules / "cli.py").write_text(
            'CLI_CONFIG = {"agent": {"reasoning_effort": "medium"}}\n',
            encoding="utf-8",
        )
        (modules / "hermes_cli" / "__init__.py").write_text("", encoding="utf-8")
        (modules / "hermes_cli" / "main.py").write_text(
            "import json, sys, cli\n"
            "def main():\n"
            "    print(json.dumps({'effort': cli.CLI_CONFIG['agent']['reasoning_effort'], 'argv': sys.argv[1:]}))\n"
            "    return 0\n",
            encoding="utf-8",
        )
        env = self.env.copy()
        env["PYTHONPATH"] = str(modules)
        result = subprocess.run(
            [
                sys.executable,
                str(TIER_CHAT),
                "--reasoning-effort",
                "high",
                "--",
                "chat",
                "-q",
                "probe",
            ],
            env=env,
            text=True,
            capture_output=True,
            timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["effort"], "high")
        self.assertEqual(payload["argv"], ["chat", "-q", "probe"])

    def test_validation_rejects_cycle_and_nondeterministic_output_dependency(self) -> None:
        cycle = self.write_plan(
            {
                "name": "cycle",
                "tasks": [
                    {"id": "a", "prompt": "a", "depends_on": ["b"]},
                    {"id": "b", "prompt": "b", "depends_on": ["a"]},
                ],
            }
        )
        result = self.call("validate", str(cycle))
        self.assertEqual(result.returncode, 2)
        self.assertIn("cycle", result.stderr.lower())

        invalid = self.write_plan(
            {
                "name": "invalid-output",
                "tasks": [
                    {"id": "a", "prompt": "a"},
                    {"id": "b", "prompt": "b", "include_outputs": ["a"]},
                ],
            }
        )
        result = self.call("validate", str(invalid))
        self.assertEqual(result.returncode, 2)
        self.assertIn("not dependencies", result.stderr)

        invalid_role = self.write_plan(
            {
                "name": "invalid-role",
                "tasks": [{"id": "a", "role": "architect", "prompt": "a"}],
            }
        )
        result = self.call("validate", str(invalid_role))
        self.assertEqual(result.returncode, 2)
        self.assertIn("role must be one of", result.stderr)


if __name__ == "__main__":
    unittest.main()
