"""Real CLI consumer probes; synthetic receipts prove policy, never product quality."""
import copy
import json
import subprocess
import sys
import unittest
from pathlib import Path

import test_frontend_coverage as fixtures
from frontend_coverage import delivery_acceptance


class DeliveryTests(unittest.TestCase):
    def setUp(self):
        fixture = fixtures.CoverageTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.root, self.catalog, self.contract, self.observations = (
            fixture.root, fixture.catalog, fixture.contract, fixture.observations)
        self.hash = fixture.hash
        self.contract.update(acceptance_extent="whole_product", journeys=[{
            "id": "open-reader", "job": "Read selected content", "path": "/reader > chapter control",
            "state_producer": "chapter selection and restored location", "case_ids": ["feedback:input"]}])
        self.delivery = {"schema_version": 1, "source_sha256": self.hash, "extent": "whole_product",
            "known_findings": {"source_sha256": self.hash, "findings": []},
            "scrutiny": {"source_sha256": self.hash, "extent": "whole_product", "status": "pass",
                "fresh_context": True, "read_only": True, "artifact_first": True, "ordinary_input": True,
                "finding": "Fixture whole-product exploration found no unresolved declared defects",
                "evidence": ["capture.png", "events.json"], "explored_journey_ids": ["open-reader"]},
            "journey_results": [{"id": "open-reader", "source_sha256": self.hash, "status": "pass",
                "context": copy.deepcopy(fixture.context), "finding": "Selection exposes the expected chapter",
                "steps": [{"at_ms": 0, "state": "Chapter one at reading position", "action": "Open chapter list",
                           "visible_result": "Chapter choices exposed", "evidence": ["capture.png"]},
                          {"at_ms": 1200, "state": "Chapter two visible", "action": "Select chapter two",
                           "visible_result": "Destination and current indication agree", "evidence": ["events.json"]}]}]}

    def cli(self, previous_delivery=None):
        for name, value in (("catalog", self.catalog), ("contract", self.contract),
                            ("observations", self.observations), ("delivery", self.delivery)):
            (self.root / (name + ".json")).write_text(json.dumps(value), encoding="utf-8")
        command = [sys.executable, "-B", str(Path(__file__).with_name("frontend_coverage.py")),
            str(self.root / "catalog.json"), str(self.root / "contract.json"),
            str(self.root / "observations.json"), str(self.root), "--delivery",
            str(self.root / "delivery.json"), "--source-sha256", self.hash]
        if previous_delivery is not None:
            (self.root / "previous-delivery.json").write_text(json.dumps(previous_delivery), encoding="utf-8")
            command.extend(["--previous-delivery", str(self.root / "previous-delivery.json")])
        process = subprocess.run(command, capture_output=True, text=True)
        self.assertIn(process.returncode, (0, 1, 2), process.stderr)
        return process.returncode, json.loads(process.stdout)

    def blocked(self, expected=2):
        code, report = self.cli()
        self.assertEqual(code, expected, report)
        self.assertTrue(report["transport_allowed"])
        self.assertFalse(report["acceptance"])
        self.assertFalse(report["ready_for_taste"])
        self.assertEqual(report["delivery_status"], "transported")
        return report

    def finding(self, **extra):
        return {"id": "user-scroll", "kind": "defect", "status": "open",
                "finding": "User reports chapter activation unexpectedly resets reading position",
                "case_ids": ["feedback:input"], "evidence": ["events.json"], **extra}

    def test_complete_current_whole_product_reaches_taste_with_later_stages_pending(self):
        later = {"id": "publish", "class": "requirement", "features": ["common"],
                 "methods": ["human"], "cases": ["choice", "authorization"], "summary": "Later approvals",
                 "case_stages": {"choice": "human_choice", "authorization": "publication"}}
        self.catalog["requirements"].append(later)
        self.contract["requirements"].append({"id": "publish", "disposition": "required", "cases": [
            {"id": suffix, "method": "human", "context": {"viewport": "", "modality": "", "state": ""}}
            for suffix in later["cases"]]})
        code, report = self.cli()
        self.assertEqual(code, 0, report)
        self.assertTrue(report["ready_for_taste"])
        self.assertFalse(report["fully_ready"])
        self.assertEqual(report["delivery_status"], "ready_for_taste")
        self.assertEqual(len(report["coverage"]["pending_later_cases"]), 2)

    def test_historical_incomplete_whole_product_ignores_supplied_green_summary(self):
        self.delivery["coverage"] = {"ready": True, "pre_review_ready": True}
        self.observations["results"].pop()
        report = self.blocked()
        self.assertEqual(report["coverage"]["pre_review_status"], "incomplete")

    def test_narrow_pass_can_verify_repair_but_never_whole_product(self):
        self.contract["acceptance_extent"] = self.delivery["extent"] = "bounded_repair"
        self.delivery["repair_case_ids"] = ["feedback:input", "feedback:paint"]
        self.delivery.pop("scrutiny")
        code, report = self.cli()
        self.assertEqual(code, 0, report)
        self.assertTrue(report["repair_verified"])
        self.assertFalse(report["ready_for_taste"])
        self.assertEqual(report["delivery_status"], "repair_verified")
        self.delivery["extent"] = "whole_product"
        self.blocked()

    def test_affected_only_repair_retains_unrelated_gap_and_global_integrity(self):
        self.contract["acceptance_extent"] = self.delivery["extent"] = "bounded_repair"
        self.delivery["repair_case_ids"] = ["feedback:input"]
        self.delivery.pop("scrutiny")
        self.observations["results"].pop()
        code, report = self.cli()
        self.assertEqual(code, 0, report)
        self.assertTrue(report["repair_verified"])
        self.assertFalse(report["ready_for_taste"])
        self.assertEqual(report["coverage"]["pre_review_status"], "incomplete")
        self.delivery["repair_case_ids"] = ["feedback:paint"]
        self.blocked()
        self.delivery["repair_case_ids"] = ["feedback:input"]
        self.observations["source_sha256"] = "b" * 64
        self.blocked()

    def bounded(self):
        self.contract["acceptance_extent"] = self.delivery["extent"] = "bounded_repair"
        self.delivery["repair_case_ids"] = ["feedback:input"]
        self.delivery.pop("scrutiny")

    def test_bounded_findings_unknown_mapping_cannot_hide_current_defect(self):
        self.bounded()
        for links in (["feedback:typo"], ["missing:input"], ["feedback:paint:typo"]):
            with self.subTest(links=links):
                self.delivery["known_findings"]["findings"] = [self.finding(case_ids=links)]
                self.blocked()
        self.delivery["known_findings"]["findings"] = [self.finding()]
        self.blocked(1)
        self.delivery["known_findings"]["findings"] = [self.finding(case_ids=["feedback:paint"])]
        code, report = self.cli()
        self.assertEqual(code, 0, report)
        self.assertTrue(report["repair_verified"])
        self.assertFalse(report["ready_for_taste"])

    def test_unrelated_duplicate_unknown_and_malformed_observation_ids_block_repair(self):
        self.bounded()
        original = copy.deepcopy(self.observations)
        for extra in (copy.deepcopy(original["results"][1]),
                      {**original["results"][1], "case_id": "paint:typo"},
                      {**original["results"][1], "case_id": ""},
                      {**original["results"][1], "requirement_id": "missing"}):
            with self.subTest(extra=extra):
                self.observations = copy.deepcopy(original)
                self.observations["results"].append(extra)
                report = self.blocked()
                self.assertEqual(report["coverage"]["status"], "incomplete")
        self.observations = copy.deepcopy(original)
        self.observations["results"][1]["evidence"] = ["missing.png"]
        code, report = self.cli()
        self.assertEqual(code, 0, report)
        self.assertTrue(report["repair_verified"])
        self.assertEqual(report["coverage"]["status"], "incomplete")
        for evidence in (["../escape.png"], ["capture.png", "capture.png"], "capture.png"):
            with self.subTest(evidence=evidence):
                self.observations["results"][1]["evidence"] = evidence
                self.blocked()

    def test_current_observed_failure_blocks_green_coverage_and_transport_survives(self):
        self.delivery["known_findings"]["findings"] = [self.finding()]
        report = self.blocked(1)
        self.assertTrue(report["coverage"]["ready"])
        self.delivery["known_findings"]["findings"] = []
        self.delivery["scrutiny"]["status"] = "fail"
        self.blocked(1)

    def test_missing_stale_or_narrow_scrutiny_cannot_clear_whole_product(self):
        original = copy.deepcopy(self.delivery)
        for mutate in (lambda d: d.pop("scrutiny"),
                       lambda d: d["scrutiny"].update(source_sha256="b" * 64),
                       lambda d: d["scrutiny"].update(extent="bounded_repair"),
                       lambda d: d["scrutiny"].update(artifact_first=False),
                       lambda d: d["scrutiny"].update(explored_journey_ids=[]),
                       lambda d: d["scrutiny"].update(evidence=["missing.txt"])):
            with self.subTest(mutate=mutate):
                self.delivery = copy.deepcopy(original)
                mutate(self.delivery)
                self.blocked()

    def test_missing_stale_or_non_temporal_journey_proof_blocks(self):
        original = copy.deepcopy(self.delivery)
        for mutate in (lambda d: d.update(journey_results=[]),
                       lambda d: d["journey_results"][0].update(source_sha256="b" * 64),
                       lambda d: d["journey_results"][0].update(steps=[]),
                       lambda d: d["journey_results"][0]["steps"][1].update(at_ms=0),
                       lambda d: d["journey_results"][0]["steps"][0].update(evidence=["../escape.json"])):
            with self.subTest(mutate=mutate):
                self.delivery = copy.deepcopy(original)
                mutate(self.delivery)
                self.blocked()

    def test_current_source_identity_and_ledger_required(self):
        self.delivery["source_sha256"] = "b" * 64
        self.blocked()
        self.delivery["source_sha256"] = self.hash
        self.delivery.pop("known_findings")
        self.blocked()

    def test_retained_user_finding_cannot_disappear_and_resolution_requires_evidence(self):
        previous = copy.deepcopy(self.delivery)
        previous["known_findings"]["findings"] = [self.finding()]
        code, report = self.cli(previous)
        self.assertEqual(code, 2, report)
        self.assertFalse(report["ready_for_taste"])
        self.delivery["known_findings"]["findings"] = [self.finding(status="resolved")]
        self.blocked()
        self.delivery["known_findings"]["findings"][0]["resolution_evidence"] = ["events.json"]
        code, report = self.cli(previous)
        self.assertEqual(code, 0, report)
        self.assertTrue(report["fully_ready"])

    def test_api_recomputes_raw_coverage_and_malformed_delivery_preserves_transport(self):
        report = delivery_acceptance(self.catalog, self.contract, self.observations, self.root,
                                     self.delivery, self.hash)
        self.assertTrue(report["ready_for_taste"])
        self.observations["results"][0]["status"] = "fail"
        report = delivery_acceptance(self.catalog, self.contract, self.observations, self.root,
                                     self.delivery, self.hash)
        self.assertFalse(report["acceptance"])
        self.delivery = []
        self.blocked(1)


if __name__ == "__main__":
    unittest.main()
