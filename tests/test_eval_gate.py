from __future__ import annotations

import importlib.util
import json
import math
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[1]


def load(name: str, relative: str):
    path = REPO / relative
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


class EvalGateTests(unittest.TestCase):
    def setUp(self):
        self.evaluator = load("eval_gate_harness", "tools/eval.py")

    def test_suite_requires_all_case_classes(self):
        suite = {
            "schema_version": 2,
            "cases": [
                {"id": "r", "kind": "representative", "prompt": "r"},
                {"id": "n", "kind": "near-miss", "prompt": "n"},
                {"id": "a", "kind": "adversarial", "prompt": "a"},
                {"id": "h", "kind": "held-out", "prompt": "h"},
            ]
        }
        self.evaluator.validate_suite(suite)
        suite["cases"].pop()
        with self.assertRaisesRegex(ValueError, "held-out"):
            self.evaluator.validate_suite(suite)

    def test_sequential_rule_is_bounded_and_mode_specific(self):
        rule = self.evaluator.DecisionRule(alpha=0.05, margin=0.1, min_trials=2, max_trials=4)
        pending = self.evaluator.sequential_decision("admission", [1.0], rule)
        self.assertEqual(pending["decision"], "continue")
        bounded = self.evaluator.sequential_decision("admission", [0.0] * 4, rule)
        self.assertEqual(bounded["decision"], "inconclusive")
        retirement = self.evaluator.sequential_decision("retirement", [0.0] * 4, rule)
        self.assertEqual(retirement["decision"], "inconclusive")
        self.assertLessEqual(bounded["confidence_sequence"]["lower"], bounded["mean"])
        self.assertGreaterEqual(bounded["confidence_sequence"]["upper"], bounded["mean"])
        self.assertTrue(math.isfinite(bounded["confidence_sequence"]["radius"]))

    def test_session_parser_and_cleanup_use_supported_cli(self):
        text = "20260814_111111_abcd12  agent-signal-eval\n20260814_222222_deadbeef  agent-signal-eval\n"
        self.assertEqual(
            self.evaluator.parse_session_ids(text),
            {"20260814_111111_abcd12", "20260814_222222_deadbeef"},
        )
        lifecycle = self.evaluator.HermesSessionLifecycle(
            hermes_exe="hermes",
            retain=False,
            protected={"20260814_222222_deadbeef"},
        )
        lifecycle.created = {"20260814_111111_abcd1234", "20260814_222222_deadbeef"}
        completed = mock.Mock(returncode=0, stdout="", stderr="")
        with mock.patch.object(self.evaluator.subprocess, "run", return_value=completed) as run:
            result = lifecycle.cleanup()
        delete_calls = [call.args[0] for call in run.call_args_list if "delete" in call.args[0]]
        self.assertEqual(delete_calls, [["hermes", "sessions", "delete", "20260814_111111_abcd1234", "--yes"]])
        self.assertEqual(result["protected"], ["20260814_222222_deadbeef"])

    def test_child_environment_strips_worker_delegation_and_session_identity(self):
        source = {
            "PATH": "kept",
            "HERMES_KANBAN_TASK": "t_parent",
            "HERMES_KANBAN_DB": "parent.db",
            "HERMES_SESSION_ID": "parent-session",
            "HERMES_PARENT_SESSION_ID": "grandparent-session",
            "HERMES_GATEWAY_SESSION": "1",
            "HERMES_DELEGATED_CHILD_CONTEXT": "1",
            "DELEGATION_CHILD_TIMEOUT_SECONDS": "10",
        }
        self.assertEqual(self.evaluator.isolated_child_env(source), {"PATH": "kept"})

    def test_direct_child_stderr_is_the_only_deletion_authority(self):
        lifecycle = self.evaluator.HermesSessionLifecycle("hermes", retain=False)
        session_ids, error = lifecycle.register_receipt("\nsession_id: 20260814_111111_abcd1234\n")
        self.assertIsNone(error)
        self.assertEqual(session_ids, ["20260814_111111_abcd1234"])
        self.assertEqual(lifecycle.created, {"20260814_111111_abcd1234"})
        ambiguous, error = lifecycle.register_receipt(
            "20260814_222222_deadbeef 20260814_333333_cafebabe"
        )
        self.assertEqual(ambiguous, [])
        self.assertIn("expected one", error)
        self.assertNotIn("20260814_222222_deadbeef", lifecycle.created)

    def test_retain_override_preserves_owned_sessions(self):
        lifecycle = self.evaluator.HermesSessionLifecycle("hermes", retain=True)
        lifecycle.created = {"20260814_111111_abcd12"}
        with mock.patch.object(self.evaluator.subprocess, "run") as run:
            result = lifecycle.cleanup()
        run.assert_not_called()
        self.assertEqual(result["policy"], "retain-evidence")
        self.assertEqual(result["remaining"], ["20260814_111111_abcd12"])

    def test_durable_report_precedes_cleanup(self):
        order: list[str] = []
        with tempfile.TemporaryDirectory() as temp:
            report = Path(temp) / "report.json"
            lifecycle = mock.Mock()
            lifecycle.cleanup.side_effect = lambda: order.append("cleanup") or {"deleted": [], "remaining": []}
            original_write = self.evaluator.durable_json_write

            def write(path, payload):
                order.append("write")
                original_write(path, payload)

            with mock.patch.object(self.evaluator, "durable_json_write", side_effect=write):
                self.evaluator.finalize_report(report, {"status": "complete"}, lifecycle)
            payload = json.loads(report.read_text(encoding="utf-8"))
        self.assertEqual(order, ["write", "cleanup", "write"])
        self.assertEqual(payload["session_lifecycle"]["deleted"], [])

    def test_timeout_kills_child_and_preserves_session_receipt(self):
        process = mock.Mock(returncode=None)
        process.communicate.side_effect = [
            subprocess.TimeoutExpired(["hermes"], 1),
            ("partial", "session_id: 20260814_111111_abcd1234"),
        ]
        lifecycle = mock.Mock()
        lifecycle.register_receipt.return_value = (["20260814_111111_abcd1234"], None)
        with tempfile.TemporaryDirectory() as temp, \
             mock.patch.object(self.evaluator.shutil, "which", return_value="hermes"), \
             mock.patch.object(self.evaluator.subprocess, "Popen", return_value=process):
            result = self.evaluator.run_agent(
                "hermes", "task", Path(temp), 1, False,
                "model", "provider", "low", "safe", lifecycle,
            )
        process.kill.assert_called_once()
        self.assertFalse(result["ok"])
        self.assertEqual(result["session_ids"], ["20260814_111111_abcd1234"])
        lifecycle.register_receipt.assert_called_once_with("session_id: 20260814_111111_abcd1234")

    def test_failed_child_preserves_direct_session_receipt(self):
        process = mock.Mock(returncode=2)
        process.communicate.return_value = (
            "failed output",
            "session_id: 20260814_111111_abcd12",
        )
        lifecycle = mock.Mock()
        lifecycle.register_receipt.return_value = (["20260814_111111_abcd12"], None)
        with tempfile.TemporaryDirectory() as temp, \
             mock.patch.object(self.evaluator.shutil, "which", return_value="hermes"), \
             mock.patch.object(self.evaluator.subprocess, "Popen", return_value=process):
            result = self.evaluator.run_agent(
                "hermes", "task", Path(temp), 1, False,
                "model", "provider", "low", "safe", lifecycle,
            )
        self.assertFalse(result["ok"])
        self.assertEqual(result["returncode"], 2)
        self.assertEqual(result["session_ids"], ["20260814_111111_abcd12"])

    def test_interruption_kills_child_and_registers_direct_receipt_before_reraise(self):
        process = mock.Mock()
        process.communicate.side_effect = [
            KeyboardInterrupt("stop"),
            ("", "session_id: 20260814_111111_abcd1234"),
        ]
        lifecycle = mock.Mock()
        with tempfile.TemporaryDirectory() as temp, \
             mock.patch.object(self.evaluator.shutil, "which", return_value="hermes"), \
             mock.patch.object(self.evaluator.subprocess, "Popen", return_value=process):
            with self.assertRaises(KeyboardInterrupt):
                self.evaluator.run_agent(
                    "hermes", "task", Path(temp), 1, False,
                    "model", "provider", "low", "safe", lifecycle,
                )
        process.kill.assert_called_once()
        lifecycle.register_receipt.assert_called_once_with("session_id: 20260814_111111_abcd1234")


class CrossHostGateTests(unittest.TestCase):
    def setUp(self):
        self.gate = load("cross_host_gate", "tools/eval_gate.py")

    def test_required_host_regression_rejects(self):
        base = {
            "schema_version": 2,
            "suite": "x",
            "artifacts": {"candidate_sha256": "c", "suite_sha256": "s", "harness_sha256": "h"},
            "effective_stack": {"equivalence_group": "g"},
            "decision": {"decision": "admit"},
        }
        reports = [dict(base, agent="codex"), dict(base, agent="hermes", decision={"decision": "reject"})]
        result = self.gate.aggregate(reports, ["codex", "hermes"], "admission", "restore previous artifacts")
        self.assertEqual(result["decision"], "reject")
        self.assertEqual(result["host_decisions"]["hermes"], "reject")

    def test_missing_required_host_is_inconclusive(self):
        report = {
            "schema_version": 2,
            "suite": "x",
            "agent": "codex",
            "artifacts": {"candidate_sha256": "c", "suite_sha256": "s", "harness_sha256": "h"},
            "effective_stack": {"equivalence_group": "g"},
            "decision": {"decision": "admit"},
        }
        result = self.gate.aggregate([report], ["codex", "hermes"], "admission", "restore")
        self.assertEqual(result["decision"], "inconclusive")
        self.assertEqual(result["missing_hosts"], ["hermes"])


if __name__ == "__main__":
    unittest.main()
