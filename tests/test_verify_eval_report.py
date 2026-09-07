from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(REPO / "tests"))
from test_evaluation_evidence import make_evaluation, historical_report
from verify_eval_report import verify_report


class VerifyEvalReportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def fixture(self, **kwargs):
        self.fixture_data = make_evaluation(self.root, **kwargs)
        return self.fixture_data["report"]

    def verify(self, report=None, *, decision=None):
        fixture = self.fixture_data
        if report is not None:
            fixture["report_path"].write_text(json.dumps(report), encoding="utf-8")
        return verify_report(
            fixture["report_path"], fixture["suite_path"], fixture["candidate_path"], fixture["baseline_path"],
            agent=fixture["report"]["agent"], decision=decision or fixture["report"]["decision"]["decision"],
            model="gpt-6-astra", provider="openai-codex", reasoning="xhigh", tool_policy="none",
            equivalence_group="fixture-group", min_trials=2, max_trials=2,
            max_agent_runs=fixture["max_agent_runs"],
        )

    def test_real_producer_admission_and_inconclusive_both_verify(self):
        for outcome in ("win", "tie"):
            with self.subTest(outcome=outcome):
                self.fixture(outcome=outcome)
                result = self.verify()
                self.assertTrue(result["ok"], result["errors"])
                self.assertEqual(result["positive_decision_sufficient"], outcome == "win")

    def test_tie_changed_to_admit_fails_even_with_expected_admit(self):
        payload = self.fixture()
        payload["decision"]["decision"] = "admit"
        result = self.verify(payload, decision="admit")
        self.assertFalse(result["ok"])
        self.assertIn("declared decision differs from recomputed evidence", result["errors"])

    def test_early_reject_and_retention_are_valid_evidence(self):
        for version, mode, expected in ((3, "admission", "reject"), (2, "retirement", "retain")):
            with self.subTest(version=version):
                self.fixture(version=version, mode=mode, outcome="early-failure")
                result = self.verify(decision=expected)
                self.assertTrue(result["ok"], result["errors"])
                self.assertFalse(result["positive_decision_sufficient"])
                self.assertEqual(result["computed_decision"]["trials"], 1)

    def test_live_artifact_or_suite_hash_drift_fails(self):
        self.fixture()
        self.fixture_data["candidate_path"].write_text("changed", encoding="utf-8")
        result = self.verify()
        self.assertIn("candidate hash mismatch", result["errors"])
        self.fixture()
        self.fixture_data["suite_path"].write_bytes(self.fixture_data["suite_path"].read_bytes() + b"\n")
        self.assertIn("suite hash mismatch", self.verify()["errors"])

    def test_hidden_failures_and_coverage_forgery_fail(self):
        original = self.fixture(outcome="win")
        for mutation in ("winner", "model", "judge_model", "coverage"):
            with self.subTest(mutation=mutation):
                payload = copy.deepcopy(original)
                if mutation == "winner":
                    payload["results"][0]["winner"] = "baseline"
                elif mutation == "model":
                    payload["results"][0]["candidate"]["route_attestation"]["observed"]["model"] = "another-model"
                elif mutation == "judge_model":
                    payload["results"][0]["judgments"][0]["run"]["route_attestation"]["observed"]["model"] = "another-model"
                else:
                    payload["results"].pop()
                self.assertFalse(self.verify(payload)["ok"])

    def test_trial_and_run_plan_are_independently_checked(self):
        payload = self.fixture()
        payload["decision_rule"]["max_trials"] = 9
        payload["decision_rule"]["max_agent_runs"] = 999
        result = self.verify(payload)
        self.assertIn("decision rule mismatch: max_trials", result["errors"])
        self.assertIn("decision rule mismatch: max_agent_runs", result["errors"])

    def test_truthful_harness_failure_can_be_verified(self):
        self.fixture(outcome="harness-failure")
        result = self.verify()
        self.assertTrue(result["ok"], result["errors"])
        self.assertFalse(result["positive_decision_sufficient"])

    def test_harness_failure_without_failure_evidence_fails(self):
        payload = self.fixture()
        payload["decision"] = {"decision": "harness-failure"}
        result = self.verify(payload, decision="harness-failure")
        self.assertIn("declared decision differs from recomputed evidence", result["errors"])

    def test_retained_sessions_and_cleanup_failure_do_not_relabel_behavior(self):
        payload = historical_report(self.fixture(retain=True))
        payload["session_lifecycle"].update(created=["fixture-session"], remaining=["fixture-session"])
        retained = self.verify(payload)
        self.assertTrue(retained["ok"], retained["errors"])
        self.assertTrue(retained["operational_ok"])
        payload["session_lifecycle"]["policy"] = "delete-after-durable-report"
        payload["session_lifecycle"]["errors"] = ["fixture cleanup failed"]
        failed_cleanup = self.verify(payload)
        self.assertTrue(failed_cleanup["integrity_valid"], failed_cleanup["errors"])
        self.assertFalse(failed_cleanup["operational_ok"])
        self.assertEqual(failed_cleanup["decision"], "inconclusive")

    def test_default_and_v1_suites_without_baseline_verify_as_v2_reports(self):
        for version in (None, 1, 2):
            for outcome in ("tie", "early-failure"):
                with self.subTest(version=version, outcome=outcome):
                    report = self.fixture(version=version, outcome=outcome, baseline=False)
                    self.assertEqual(report["schema_version"], 2)
                    self.assertIsNone(report["baseline_candidate"])
                    result = self.verify()
                    self.assertTrue(result["ok"], result["errors"])
                    self.assertEqual(result["hermes_runs"], 0)
                    self.assertEqual(result["codex_runs"], result["runs_found"])

    def test_host_counts_follow_generation_and_judge_positions(self):
        self.fixture(agent="hermes")
        result = self.verify()
        self.assertTrue(result["ok"], result["errors"])
        self.assertEqual(result["hermes_runs"], 16)
        self.assertEqual(result["codex_runs"], 16)

    def test_native_cleanup_preserves_negative_and_inconclusive_comparisons(self):
        for outcome, expected in (("early-failure", "reject"), ("tie", "inconclusive"), ("win", "admit")):
            with self.subTest(outcome=outcome):
                self.fixture(outcome=outcome, cleanup_failure=True)
                result = self.verify()
                self.assertTrue(result["integrity_valid"], result["errors"])
                self.assertEqual(result["decision"], expected)
                self.assertFalse(result["operational_ok"])
                self.assertFalse(result["positive_decision_sufficient"])

    def test_valid_retry_and_scope_survive_file_verification(self):
        self.fixture(outcome="win", retry_first=True)
        result = self.verify()
        self.assertTrue(result["ok"], result["errors"])
        self.assertTrue(result["positive_decision_sufficient"])
        self.assertEqual(result["scope"]["runtime_lane"], "inline-text-no-tools-v1")
        self.assertEqual(result["scope"]["evaluated_projection"], "inline-linked-text-only")
        self.assertFalse(result["scope"]["package_behavior_exercised"])


if __name__ == "__main__":
    unittest.main()
