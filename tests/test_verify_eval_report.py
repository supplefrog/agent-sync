from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def load_module():
    path = REPO / "tools" / "verify_eval_report.py"
    spec = importlib.util.spec_from_file_location("verify_eval_report", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


class VerifyEvalReportTests(unittest.TestCase):
    def setUp(self):
        self.module = load_module()
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.candidate = self.root / "candidate.md"
        self.baseline = self.root / "baseline.md"
        self.suite = self.root / "suite.json"
        self.report = self.root / "report.json"
        self.candidate.write_text("candidate\n", encoding="utf-8")
        self.baseline.write_text("baseline\n", encoding="utf-8")
        self.suite.write_text('{"schema_version":3}\n', encoding="utf-8")

    @staticmethod
    def make_run(*, hermes: bool) -> dict:
        observed = {"model": "gpt-5.6-sol", "provider": "openai-codex", "reasoning": "ultra"}
        if hermes:
            observed["tool_calls_count"] = 0
        return {
            "ok": True,
            "returncode": 0,
            "attempt_count": 1,
            "run_budget_exhausted": False,
            "route_attestation": {"required": True, "ok": True, "observed": observed},
        }

    def payload(self) -> dict:
        hermes_run = self.make_run(hermes=True)
        judge_run = self.make_run(hermes=False)
        return {
            "schema_version": 3,
            "status": "complete",
            "agent": "hermes",
            "candidate": str(self.candidate.resolve()),
            "baseline_candidate": str(self.baseline.resolve()),
            "artifacts": {
                "candidate_sha256": self.module.candidate_hash(self.candidate),
                "baseline_candidate_sha256": self.module.candidate_hash(self.baseline),
                "suite_sha256": hashlib.sha256(self.suite.read_bytes()).hexdigest(),
                "harness_sha256": hashlib.sha256((REPO / "tools" / "eval.py").read_bytes()).hexdigest(),
            },
            "effective_stack": {
                "model": "gpt-5.6-sol",
                "provider": "openai-codex",
                "reasoning": "ultra",
                "tool_policy": "none",
                "equivalence_group": "test-group",
                "route_attestation_required": True,
            },
            "decision": {"decision": "admit"},
            "decision_rule": {"min_trials": 2, "max_trials": 2, "max_agent_runs": 10},
            "run_count": 4,
            "summary": {
                "candidate_losses": 0,
                "candidate_hard_failures": 0,
                "judge_disagreements": 0,
                "candidate_receipt_failures": 0,
                "route_attestation_failures": 0,
            },
            "session_lifecycle": {
                "created": ["baseline", "candidate"],
                "deleted": ["baseline", "candidate"],
                "remaining": [],
                "errors": [],
            },
            "results": [{
                "winner": "candidate",
                "hard_pass": {"baseline": True, "candidate": True},
                "judge_disagreement": False,
                "candidate_receipt_pass": True,
                "baseline": hermes_run,
                "candidate": hermes_run,
                "judgments": [{"run": judge_run}, {"run": judge_run}],
            }],
        }

    def verify(self, *, decision: str = "admit") -> dict:
        return self.module.verify_report(
            self.report,
            self.suite,
            self.candidate,
            self.baseline,
            agent="hermes",
            decision=decision,
            model="gpt-5.6-sol",
            provider="openai-codex",
            reasoning="ultra",
            tool_policy="none",
            equivalence_group="test-group",
            min_trials=2,
            max_trials=2,
            max_agent_runs=10,
        )

    def test_valid_report_passes(self):
        self.report.write_text(json.dumps(self.payload()), encoding="utf-8")
        self.assertTrue(self.verify()["ok"])

    def test_cleanup_or_live_hash_drift_fails_closed(self):
        payload = self.payload()
        payload["session_lifecycle"]["remaining"] = ["candidate"]
        self.report.write_text(json.dumps(payload), encoding="utf-8")
        self.assertIn("evaluator sessions remain", self.verify()["errors"])

        payload["session_lifecycle"]["remaining"] = []
        self.report.write_text(json.dumps(payload), encoding="utf-8")
        self.candidate.write_text("changed\n", encoding="utf-8")
        self.assertIn("candidate hash mismatch", self.verify()["errors"])

    def test_computed_failures_cannot_be_hidden_by_summary(self):
        payload = self.payload()
        payload["results"][0]["winner"] = "baseline"
        payload["results"][0]["hard_pass"]["candidate"] = False
        self.report.write_text(json.dumps(payload), encoding="utf-8")
        errors = self.verify()["errors"]
        self.assertIn("candidate loss present", errors)
        self.assertIn("candidate hard failure present", errors)
        self.assertIn("summary candidate_losses mismatch", errors)
        self.assertIn("summary candidate_hard_failures mismatch", errors)

    def test_predeclared_trial_and_run_bounds_are_exact(self):
        payload = self.payload()
        payload["decision_rule"]["max_agent_runs"] = 999
        payload["decision_rule"]["max_trials"] = 9
        self.report.write_text(json.dumps(payload), encoding="utf-8")
        errors = self.verify()["errors"]
        self.assertIn("decision rule mismatch: max_trials", errors)
        self.assertIn("decision rule mismatch: max_agent_runs", errors)

    def test_truthful_harness_failure_can_be_integrity_verified(self):
        payload = self.payload()
        payload["decision"] = {"decision": "harness-failure"}
        payload["results"][0]["candidate"] = copy.deepcopy(payload["results"][0]["candidate"])
        payload["results"][0]["candidate"]["ok"] = False
        payload["results"][0]["candidate"]["returncode"] = 1
        payload["results"][0]["candidate"]["route_attestation"]["ok"] = False
        payload["summary"]["route_attestation_failures"] = 1
        self.report.write_text(json.dumps(payload), encoding="utf-8")

        result = self.verify(decision="harness-failure")

        self.assertTrue(result["ok"], result["errors"])

    def test_harness_failure_without_failure_evidence_fails_closed(self):
        payload = self.payload()
        payload["decision"] = {"decision": "harness-failure"}
        self.report.write_text(json.dumps(payload), encoding="utf-8")

        errors = self.verify(decision="harness-failure")["errors"]

        self.assertIn("harness-failure decision lacks failure evidence", errors)

    def test_truthful_budget_exhaustion_harness_failure_can_be_verified(self):
        payload = self.payload()
        payload["decision"] = {"decision": "harness-failure"}
        payload["results"][0]["candidate"] = copy.deepcopy(payload["results"][0]["candidate"])
        payload["results"][0]["candidate"]["run_budget_exhausted"] = True
        self.report.write_text(json.dumps(payload), encoding="utf-8")

        result = self.verify(decision="harness-failure")

        self.assertTrue(result["ok"], result["errors"])


if __name__ == "__main__":
    unittest.main()
