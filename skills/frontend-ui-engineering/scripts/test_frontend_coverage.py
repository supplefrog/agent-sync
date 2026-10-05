"""Discriminating coverage mutations use real temporary evidence paths."""
import copy
import contextlib
import json
import shutil
import subprocess
import sys
import unittest
import uuid
from pathlib import Path

from frontend_coverage import plan, validate


@contextlib.contextmanager
def evidence_directory():
    # Default inherited permissions avoid private tempfile ACLs in Windows sandboxes.
    parent = Path(__file__).resolve().parent
    root = parent / ("coverage-test-" + uuid.uuid4().hex)
    root.mkdir()
    try:
        yield root
    finally:
        assert root.resolve().is_relative_to(parent) and root.name.startswith("coverage-test-")
        shutil.rmtree(root)


class CoverageTests(unittest.TestCase):
    def setUp(self):
        self.root = self.enterContext(evidence_directory())
        (self.root / "capture.png").write_bytes(b"capture fixture; not claimed to be an actual image")
        (self.root / "events.json").write_text("{}", encoding="utf-8")
        self.context = {"viewport": "320x900", "modality": "pointer", "state": "closed"}
        self.hash = "a" * 64
        self.catalog = {"schema_version": 1, "requirements": [
            {"id": "feedback", "class": "requirement", "features": ["common"],
             "methods": ["browser", "rendered"], "cases": ["input", "paint"], "summary": "Usable coherent feedback"},
            {"id": "sweep", "class": "capability", "features": ["highlight"],
             "methods": ["rendered"], "cases": ["preview"], "summary": "Optional fitting sweep"},
            {"id": "connector", "class": "conditional", "features": ["diagram"],
             "methods": ["browser"], "cases": ["geometry"], "summary": "Connect actual nodes"},
            {"id": "burst", "class": "tentative", "features": ["common"],
             "methods": ["human"], "cases": ["taste"], "summary": "Tentative optical observation"},
            {"id": "paper", "class": "project", "features": ["reader"],
             "methods": ["source"], "cases": ["choice"], "summary": "Local paper decision"},
        ]}
        self.contract = {"schema_version": 1, "scope": "product", "source_sha256": self.hash,
                         "features": ["reader"], "selected": [], "requirements": [
            {"id": "feedback", "disposition": "required", "cases": [
                {"id": "input", "method": "browser", "context": copy.deepcopy(self.context)},
                {"id": "paint", "method": "rendered", "context": copy.deepcopy(self.context)}]},
            {"id": "sweep", "disposition": "unselected", "reason": "No selected highlight treatment", "cases": []},
            {"id": "connector", "disposition": "not_applicable", "reason": "No diagram in brief", "cases": []},
            {"id": "burst", "disposition": "tentative", "reason": "Unconfirmed taste", "cases": []},
            {"id": "paper", "disposition": "project", "reason": "Another project's decision", "cases": []},
        ]}
        self.observations = {"source_sha256": self.hash, "results": []}
        self.result("feedback", "input", "browser")
        self.result("feedback", "paint", "rendered")

    def result(self, requirement, case, method):
        self.observations["results"].append({"requirement_id": requirement, "case_id": case,
            "source_sha256": self.hash, "method": method, "context": copy.deepcopy(self.context),
            "status": "pass", "evidence": ["capture.png" if method == "rendered" else "events.json"],
            "finding": "Fixture observation; no runtime truth claim"})

    def check(self, previous=None):
        return validate(self.catalog, self.contract, self.observations, self.root, previous)

    def incomplete(self):
        report = self.check()
        self.assertEqual(report["status"], "incomplete", report)
        self.assertFalse(report["ready"])
        return report

    def test_complete_product_preserves_valid_optional_feature_absent_tentative_project(self):
        report = self.check()
        self.assertEqual(report["coverage_status"], "pass")
        self.assertEqual(report["measurement_status"], "not_applicable")
        self.assertTrue(report["ready"])
        self.assertTrue(report["limitations"])

    def test_omitted_catalog_requirement_is_incomplete(self):
        del self.contract["requirements"][1]
        self.incomplete()

    def test_omitted_required_case_or_result_is_incomplete(self):
        for target in ("contract", "result"):
            with self.subTest(target=target):
                contract, observations = copy.deepcopy(self.contract), copy.deepcopy(self.observations)
                if target == "contract":
                    self.contract["requirements"][0]["cases"].pop()
                else:
                    self.observations["results"].pop()
                self.incomplete()
                self.contract, self.observations = contract, observations

    def test_promised_false_or_wrong_disposition_cannot_waive_case(self):
        self.contract["requirements"][0].update(disposition="not_applicable", promised=False, reason="No promise")
        self.contract["requirements"][0]["cases"] = []
        self.incomplete()

    def test_source_only_cannot_discharge_rendered_method_or_requirement(self):
        self.observations["results"][1].update(method="source", evidence=["events.json"])
        self.incomplete()
        self.contract["requirements"][0]["cases"][1]["method"] = "source"
        self.incomplete()

    def test_wrong_root_case_build_context_and_method(self):
        mutations = [("source_sha256", "b" * 64), ("context", {**self.context, "modality": "keyboard"}),
                     ("method", "source")]
        original = copy.deepcopy(self.observations)
        for key, value in mutations:
            with self.subTest(key=key):
                self.observations["results"][0][key] = value
                self.incomplete()
                self.observations = copy.deepcopy(original)
        self.observations["source_sha256"] = "b" * 64
        self.incomplete()

    def test_missing_empty_or_nonimage_rendered_evidence(self):
        (self.root / "empty.png").write_bytes(b"")
        for path in ("missing.png", "empty.png", "events.json"):
            with self.subTest(path=path):
                self.observations["results"][1]["evidence"] = [path]
                self.incomplete()

    def test_absolute_and_traversal_evidence_rejected(self):
        for path in (str(self.root / "capture.png"), "../capture.png"):
            with self.subTest(path=path):
                self.observations["results"][1]["evidence"] = [path]
                self.incomplete()

    def test_evidence_symlink_escape_rejected_when_supported(self):
        with evidence_directory() as outside:
            target = outside / "capture.png"
            target.write_bytes(b"external")
            try:
                (self.root / "escape.png").symlink_to(target)
            except OSError as exc:
                self.skipTest("Symlink privilege unavailable: " + str(exc))
            self.observations["results"][1]["evidence"] = ["escape.png"]
            self.incomplete()

    def test_finding_and_required_context_are_not_optional(self):
        del self.observations["results"][0]["finding"]
        self.incomplete()
        self.observations["results"][0]["finding"] = "finding"
        self.contract["requirements"][0]["cases"][0]["context"]["modality"] = ""
        self.incomplete()

    def test_fail_retains_missing_evidence_details(self):
        self.observations["results"][0]["status"] = "fail"
        self.observations["results"].pop()
        report = self.check()
        self.assertEqual(report["status"], "fail")
        self.assertEqual({c["status"] for c in report["checks"]}, {"fail", "incomplete"})
        self.assertFalse(report["ready"])

    def test_unknown_and_duplicate_identifiers(self):
        for kind in ("catalog", "contract", "case", "result", "selected", "unknown_case", "unknown_result"):
            with self.subTest(kind=kind):
                catalog, contract, observations = copy.deepcopy(self.catalog), copy.deepcopy(self.contract), copy.deepcopy(self.observations)
                if kind == "catalog": self.catalog["requirements"].append(copy.deepcopy(self.catalog["requirements"][0]))
                if kind == "contract": self.contract["requirements"].append({"id": "unknown", "cases": []})
                if kind == "case": self.contract["requirements"][0]["cases"].append(copy.deepcopy(self.contract["requirements"][0]["cases"][0]))
                if kind == "result": self.observations["results"].append(copy.deepcopy(self.observations["results"][0]))
                if kind == "selected": self.contract["selected"] = ["unknown"]
                if kind == "unknown_case": self.contract["requirements"][0]["cases"][0]["id"] = "unknown"
                if kind == "unknown_result": self.observations["results"][0]["case_id"] = "unknown"
                self.incomplete()
                self.catalog, self.contract, self.observations = catalog, contract, observations

    def test_feature_present_or_selected_capability_requires_cases(self):
        self.contract["features"].append("diagram")
        self.incomplete()
        self.contract["features"].remove("diagram")
        self.contract["selected"] = ["sweep"]
        self.incomplete()

    def test_workflow_scope_exercises_capabilities_and_conditional_cases(self):
        self.contract["scope"] = "workflow"
        for index, case_id, method in ((1, "preview", "rendered"), (2, "geometry", "browser")):
            entry = self.contract["requirements"][index]
            entry.update(disposition="required", cases=[{"id": case_id, "method": method, "context": copy.deepcopy(self.context)}])
            self.result(entry["id"], case_id, method)
        self.assertTrue(self.check()["ready"])
        self.observations["results"].pop()
        self.incomplete()

    def test_missing_nonrequired_reason_is_incomplete(self):
        self.contract["requirements"][1]["reason"] = " "
        self.incomplete()

    def test_inherited_required_case_change_needs_explicit_reason(self):
        previous = copy.deepcopy(self.contract)
        self.contract["requirements"][0]["cases"][0]["context"]["state"] = "open"
        self.observations["results"][0]["context"]["state"] = "open"
        self.assertEqual(self.check(previous)["status"], "incomplete")
        self.contract["changes"] = {"feedback": "Brief now asks to test open state"}
        self.assertTrue(self.check(previous)["ready"])

    def test_dropped_inherited_conditional_requires_reason_even_when_feature_absent(self):
        previous = copy.deepcopy(self.contract)
        previous["requirements"][2].update(disposition="required", cases=[
            {"id": "geometry", "method": "browser", "context": copy.deepcopy(self.context)}])
        self.assertEqual(self.check(previous)["status"], "incomplete")
        self.contract["changes"] = {"connector": "Explicit brief removes the diagram"}
        self.assertTrue(self.check(previous)["ready"])

    def test_change_reason_never_waives_current_catalog_case(self):
        self.contract["changes"] = {"feedback": "Author wants fewer cases"}
        self.contract["requirements"][0]["cases"].pop()
        self.incomplete()

    def test_linked_measurements_missing_report_check_or_status_are_incomplete(self):
        self.contract["requirements"][0]["cases"][0]["measurement_ids"] = ["stable"]
        self.incomplete()
        self.observations["measurements"] = {"status": "pass", "checks": [{"id": "other", "status": "pass"}]}
        self.incomplete()
        self.observations["measurements"] = {"status": "pass", "checks": [{"id": "stable"}]}
        self.incomplete()

    def test_measurement_pass_fail_incomplete_and_legacy_result_preserved(self):
        self.contract["requirements"][0]["cases"][0]["measurement_ids"] = ["stable"]
        for status in ("pass", "fail", "incomplete"):
            with self.subTest(status=status):
                item = {"id": "stable", "status": status, "evidence": {"max_edge_delta_px": 2}}
                self.observations["measurements"] = {"status": status, "checks": [item]}
                report = self.check()
                self.assertEqual(report["status"], status)
                self.assertEqual(report["measurement_status"], status)
                self.assertEqual(report["ready"], status == "pass")
                self.assertEqual(report["measurement_checks"][0]["result"], item)

    def test_legacy_unpromised_measurement_pass_cannot_discharge_required_case(self):
        self.contract["requirements"][0]["cases"][0]["measurement_ids"] = ["stable"]
        self.observations["measurements"] = {"status": "pass", "checks": [
            {"id": "stable", "status": "pass", "evidence": {"applicable": False, "reason": "No stability promise"}}]}
        report = self.incomplete()
        self.assertEqual(report["measurement_status"], "pass")
        self.assertEqual(report["coverage_status"], "incomplete")

    def test_unlinked_failed_measurement_still_blocks_ready_and_retains_incomplete(self):
        self.observations["measurements"] = {"status": "fail", "checks": [{"id": "other", "status": "fail"}]}
        self.observations["results"].pop()
        report = self.check()
        self.assertEqual(report["status"], "fail")
        self.assertEqual(report["coverage_status"], "incomplete")
        self.assertFalse(report["ready"])

    def test_inconsistent_measurement_summary_and_duplicate_ids_incomplete(self):
        self.observations["measurements"] = {"status": "fail", "checks": [{"id": "stable", "status": "pass"}]}
        self.incomplete()
        self.observations["measurements"] = {"status": "pass", "checks": [{"id": "stable", "status": "pass"}] * 2}
        self.incomplete()

    def test_invalid_input_types_are_incomplete(self):
        for value in (None, [], {}, {"schema_version": True}):
            with self.subTest(value=value):
                report = validate(value, self.contract, self.observations, self.root)
                self.assertEqual(report["status"], "incomplete")
        self.observations["results"][0]["status"] = []
        self.incomplete()

    def test_plan_classifies_catalog_without_passing_unmeasured_scaffold(self):
        report = plan(self.catalog, "product", self.hash, ["reader"], [])
        self.assertEqual(report["status"], "incomplete")
        self.assertFalse(report["ready"])
        scaffold = report["contract"]
        self.assertEqual([r["disposition"] for r in scaffold["requirements"]],
                         ["required", "unselected", "not_applicable", "tentative", "project"])
        self.assertEqual([c["method"] for c in scaffold["requirements"][0]["cases"]], ["browser", "rendered"])
        self.assertEqual([c["id"] for c in scaffold["requirements"][0]["cases"]], ["input", "paint"])
        validated = validate(self.catalog, scaffold, self.observations, self.root)
        self.assertEqual(validated["status"], "incomplete")
        self.assertFalse(validated["ready"])

    def test_plan_workflow_selected_capability_and_feature_present_classifications(self):
        product = plan(self.catalog, "product", self.hash, ["diagram"], ["sweep"])["contract"]
        self.assertEqual([r["disposition"] for r in product["requirements"][:3]], ["required"] * 3)
        workflow = plan(self.catalog, "workflow", self.hash, [], [])["contract"]
        self.assertEqual([r["disposition"] for r in workflow["requirements"][:3]], ["required"] * 3)

    def test_plan_rejects_unknown_tags_selection_and_unplannable_catalog(self):
        for features, selected in ((["unknown"], []), ([], ["unknown"]), ([], ["feedback"]), (["reader", "reader"], [])):
            report = plan(self.catalog, "product", self.hash, features, selected)
            self.assertGreater(len(report["checks"]), 1)
            self.assertFalse(report["ready"])
        self.catalog["requirements"][0]["cases"] = ["input"]
        report = plan(self.catalog, "product", self.hash, [], [])
        self.assertTrue(any("enough case" in c["finding"] for c in report["checks"]))

    def test_verify_rejects_unknown_features_and_non_capability_selection(self):
        for features, selected in ((["native-selet"], []), (["reader"], ["connector"]),
                                   (["reader"], ["feedback"]), (["reader"], ["unknown"])):
            with self.subTest(features=features, selected=selected):
                self.contract.update(features=features, selected=selected)
                self.incomplete()

    def test_cli_all_exit_codes_and_missing_input(self):
        script = Path(__file__).with_name("frontend_coverage.py")
        catalog, contract, observations = [self.root / name for name in ("catalog.json", "contract.json", "observations.json")]
        catalog.write_text(json.dumps(self.catalog), encoding="utf-8")
        contract.write_text(json.dumps(self.contract), encoding="utf-8")
        planned = subprocess.run([sys.executable, "-B", str(script), "--plan", "--scope", "product",
                                  "--source-sha256", self.hash, "--features", "reader", str(catalog)],
                                 capture_output=True, text=True)
        self.assertEqual(planned.returncode, 2, planned.stderr)
        self.assertEqual(json.loads(planned.stdout)["contract"]["requirements"][0]["disposition"], "required")
        for status, code in (("pass", 0), ("fail", 1), ("incomplete", 2)):
            self.observations["results"][0]["status"] = status
            observations.write_text(json.dumps(self.observations), encoding="utf-8")
            process = subprocess.run([sys.executable, "-B", str(script), str(catalog), str(contract), str(observations), str(self.root)], capture_output=True, text=True)
            self.assertEqual(process.returncode, code, process.stderr)
            self.assertEqual(json.loads(process.stdout)["status"], status)
        observations.unlink()
        process = subprocess.run([sys.executable, "-B", str(script), str(catalog), str(contract), str(observations), str(self.root)], capture_output=True, text=True)
        self.assertEqual(process.returncode, 2)
        self.assertFalse(json.loads(process.stdout)["ready"])


if __name__ == "__main__":
    unittest.main()
