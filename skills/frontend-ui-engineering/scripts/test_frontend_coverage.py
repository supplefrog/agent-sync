"""Discriminating coverage mutations use real temporary evidence paths."""
import copy
import contextlib
import hashlib
import json
import shutil
import subprocess
import sys
import unittest
import uuid
from pathlib import Path

from frontend_coverage import plan, validate, review_html


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

    def defer_paint(self):
        self.catalog["requirements"][0]["case_stages"] = {"paint": "human_choice"}
        self.catalog["requirements"][0]["case_methods"] = {"paint": ["rendered"]}
        self.observations["results"].pop()

    def bind_reference(self):
        self.contract['references'] = [{'id': 'master', 'evidence': 'capture.png',
            'sha256': hashlib.sha256((self.root / 'capture.png').read_bytes()).hexdigest(),
            'authority': 'User selected master'}]
        case = self.contract['requirements'][0]['cases'][1]
        case.update(reference_ids=['master'], criteria=['Composition', 'Type'])
        self.observations['results'][1]['comparison'] = {
            'reference_ids': ['master'], 'rendered_evidence': ['capture.png'],
            'criteria_findings': [{'criterion': c, 'status': 'pass', 'finding': 'Declared inspection of ' + c}
                                  for c in case['criteria']]}

    def test_reference_bound_pass_and_static_compatibility(self):
        self.assertTrue(self.check()['ready'])
        self.bind_reference()
        self.assertTrue(self.check()['ready'])

    def test_reference_missing_stale_and_escaping(self):
        self.bind_reference()
        original = copy.deepcopy(self.contract)
        for mutate in (lambda: self.contract.pop('references'),
                       lambda: self.contract['references'][0].update(sha256='b' * 64),
                       lambda: self.contract['references'][0].update(evidence='../capture.png'),
                       lambda: self.contract['references'][0].update(evidence=str(self.root / 'capture.png'))):
            self.contract = copy.deepcopy(original)
            mutate()
            self.incomplete()

    def test_comparison_missing_mismatch_criterion_and_image(self):
        self.bind_reference()
        original = copy.deepcopy(self.observations)
        for mutate in (lambda r: r.pop('comparison'),
                       lambda r: r['comparison'].update(reference_ids=['wrong']),
                       lambda r: r['comparison']['criteria_findings'].pop(),
                       lambda r: r['comparison'].update(rendered_evidence=['events.json']),
                       lambda r: r['comparison'].update(rendered_evidence=['../capture.png'])):
            self.observations = copy.deepcopy(original)
            mutate(self.observations['results'][1])
            self.incomplete()

    def test_failed_criterion_overrides_pass_result_and_retains_measurements(self):
        self.bind_reference()
        self.observations['results'][1]['comparison']['criteria_findings'][0]['status'] = 'fail'
        self.observations['measurements'] = {'status': 'incomplete', 'checks': [{'id': 'missing', 'status': 'incomplete'}]}
        report = self.check()
        self.assertEqual(report['status'], 'fail')
        self.assertFalse(report['ready'])
        self.assertEqual(report['measurement_status'], 'incomplete')

    def test_inherited_reference_and_criteria_changes_need_supported_reason(self):
        self.bind_reference()
        previous = copy.deepcopy(self.contract)
        self.contract['requirements'][0]['cases'][1].pop('reference_ids')
        self.assertFalse(self.check(previous)['ready'])
        self.contract = copy.deepcopy(previous)
        self.contract['references'][0]['authority'] = 'Different authority'
        self.assertFalse(self.check(previous)['ready'])
        self.contract['changes'] = {'feedback': 'Explicit supported new approval'}
        self.assertTrue(self.check(previous)['ready'])

    def test_review_html_escapes_strings_and_unsafe_paths(self):
        self.bind_reference()
        self.contract['references'][0]['authority'] = '<script>alert(1)</script>'
        self.observations['results'][1]['comparison']['criteria_findings'][0]['finding'] = '<img onerror="bad">'
        packet = review_html(self.contract, self.observations, self.root, self.check(), self.root / 'review.html')
        self.assertNotIn('<script>', packet)
        self.assertIn('&lt;script&gt;', packet)
        self.assertIn('&lt;img onerror=', packet)
        self.assertIn('src="capture.png"', packet)
        self.assertNotIn('file://', packet)
        self.assertIn('Unverified declarations', packet)
        self.contract['references'][0]['evidence'] = '../capture.png'
        packet = review_html(self.contract, self.observations, self.root, self.check(), self.root / 'review.html')
        self.assertIn('Incomplete image evidence', packet)

    def test_review_html_relative_url_escapes_space_and_delimiters(self):
        self.bind_reference()
        name = 'render space & # quote.png'
        (self.root / name).write_bytes(b'image fixture')
        result = self.observations['results'][1]
        result['evidence'] = [name]
        result['comparison']['rendered_evidence'] = [name]
        packet = review_html(self.contract, self.observations, self.root, self.check(), self.root / 'nested' / 'review.html')
        self.assertIn('src="../render%20space%20%26%20%23%20quote.png"', packet)
        self.assertIn('src="../capture.png"', packet)
        self.assertNotIn('file://', packet)

    def test_review_html_cli_retains_failures_and_only_writes_requested_file(self):
        self.bind_reference()
        self.observations['results'][1]['comparison']['criteria_findings'][0]['status'] = 'fail'
        self.observations['measurements'] = {'status': 'incomplete', 'checks': [{'id': 'measurement', 'status': 'incomplete'}]}
        inputs = []
        for name, value in [('catalog', self.catalog), ('contract', self.contract), ('observations', self.observations)]:
            path = self.root / (name + '.json')
            path.write_text(json.dumps(value), encoding='utf-8')
            inputs.append(str(path))
        before = set(self.root.iterdir())
        output = self.root / 'review.html'
        process = subprocess.run([sys.executable, '-B', str(Path(__file__).with_name('frontend_coverage.py')),
                                  *inputs, str(self.root), '--review-html', str(output)], capture_output=True, text=True)
        self.assertEqual(process.returncode, 1, process.stderr)
        report = json.loads(process.stdout)
        self.assertFalse(report['ready'])
        self.assertEqual(report['measurement_status'], 'incomplete')
        self.assertEqual(set(self.root.iterdir()) - before, {output})
        packet = output.read_text(encoding='utf-8')
        self.assertIn('measurement_status', packet)
        self.assertIn('Composition', packet)
        self.assertIn('320x900', packet)
        output.unlink()
        process = subprocess.run([sys.executable, '-B', str(Path(__file__).with_name('frontend_coverage.py')),
                                  *inputs, str(self.root), '--review-html', str(self.root / 'absent' / 'review.html')], capture_output=True, text=True)
        self.assertEqual(process.returncode, 1, process.stderr)
        self.assertFalse(json.loads(process.stdout)['ready'])
        self.assertFalse((self.root / 'absent').exists())

    def test_catalog_missing_and_deferred_malformed_filled_context_block_pre_review(self):
        self.defer_paint()
        self.contract["requirements"][0]["cases"][1]["context"] = {"viewport": "320x900", "modality": "", "state": "choice"}
        self.assertFalse(self.check()["pre_review_ready"])
        self.catalog["requirements"] = []
        self.assertFalse(self.check()["pre_review_ready"])

    def test_plan_respects_catalog_case_methods_and_rejects_invalid_policy(self):
        row = self.catalog["requirements"][0]
        row["case_methods"] = {"input": ["rendered"], "paint": ["browser"]}
        result = plan(self.catalog, "product", self.hash, ["reader"], [])
        self.assertEqual([c["method"] for c in result["contract"]["requirements"][0]["cases"]], ["rendered", "browser"])
        row["case_stages"] = {"paint": "unknown"}
        result = plan(self.catalog, "product", self.hash, ["reader"], [])
        self.assertTrue(any(c["id"] == "feedback" for c in result["checks"]))

    def test_pending_later_case_preserves_full_status_and_pre_review(self):
        self.defer_paint()
        self.contract["requirements"][0]["cases"][1]["context"] = {"viewport": "", "modality": "", "state": ""}
        report = self.incomplete()
        self.assertTrue(report["pre_review_ready"], report)
        self.assertEqual(report["pre_review_status"], "pass")
        self.assertEqual(report["pending_later_cases"][0]["case_id"], "paint")

    def test_pending_does_not_waive_stale_hash_dropped_commitment_or_missing_pre_review(self):
        self.defer_paint()
        original = copy.deepcopy(self.observations)
        self.observations["source_sha256"] = "b" * 64
        self.assertFalse(self.check()["pre_review_ready"])
        self.observations = copy.deepcopy(original)
        self.observations["results"] = []
        self.assertFalse(self.check()["pre_review_ready"])
        self.observations = original
        previous = copy.deepcopy(self.contract)
        self.contract["requirements"][0]["cases"].pop()
        self.assertFalse(self.check(previous)["pre_review_ready"])

    def test_invalid_stage_suffix_and_worker_override_block_pre_review(self):
        self.defer_paint()
        for mapping in ({"paint": "unknown"}, {"unknown": "integration"}, []):
            self.catalog["requirements"][0]["case_stages"] = mapping
            self.assertFalse(self.check()["pre_review_ready"])
        self.catalog["requirements"][0]["case_stages"] = {"paint": "integration"}
        self.contract["requirements"][0]["cases"][0]["stage"] = "publication"
        self.assertFalse(self.check()["pre_review_ready"])

    def test_deferred_observation_still_requires_valid_context_and_evidence(self):
        self.defer_paint()
        self.result("feedback", "paint", "rendered")
        self.observations["results"][-1]["source_sha256"] = "b" * 64
        self.assertFalse(self.check()["pre_review_ready"])
        self.observations["results"][-1]["source_sha256"] = self.hash
        self.contract["requirements"][0]["cases"][1]["context"] = {"viewport": "", "modality": "", "state": ""}
        self.assertFalse(self.check()["pre_review_ready"])

    def test_human_method_is_not_automatically_deferred_and_choice_cannot_be_rendered(self):
        row = self.catalog["requirements"][0]
        row["methods"] = ["browser", "human"]
        row["case_methods"] = {"paint": ["human"]}
        self.contract["requirements"][0]["cases"][1]["method"] = "human"
        self.observations["results"].pop()
        self.assertFalse(self.check()["pre_review_ready"])
        row["case_stages"] = {"paint": "human_choice"}
        self.assertTrue(self.check()["pre_review_ready"])
        self.contract["requirements"][0]["cases"][1]["method"] = "rendered"
        self.assertFalse(self.check()["pre_review_ready"])

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

    def test_unmapped_case_cannot_substitute_a_method_outside_its_row(self):
        self.catalog["requirements"][0]["methods"] = ["browser"]
        self.contract["requirements"][0]["cases"][1]["method"] = "browser"
        self.observations["results"][1]["method"] = "browser"
        self.assertTrue(self.check()["ready"])
        self.contract["requirements"][0]["cases"][0]["method"] = "rendered"
        self.observations["results"][0]["method"] = "rendered"
        report = self.check()
        self.assertFalse(report["ready"])
        self.assertFalse(report["pre_review_ready"])
        self.assertTrue(any("disallowed case method" in c["finding"] for c in report["checks"]))

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


class ActualCatalogMechanisms(unittest.TestCase):
    def planned_rows(self, features=(), selected=()):
        catalog = json.loads((Path(__file__).resolve().parents[1] / "references" / "regression-catalog.json").read_text(encoding="utf-8"))
        report = plan(catalog, "product", "a" * 64, list(features), list(selected))
        return {row["id"]: row for row in report["contract"]["requirements"]}

    def test_static_mock_does_not_require_invented_motion(self):
        rows = self.planned_rows()
        for identifier in ("I25", "I26"):
            self.assertEqual(rows[identifier]["disposition"], "not_applicable")
        self.assertEqual(rows["R19"]["disposition"], "unselected")

    def test_animated_mock_retains_distinct_smoothness_evidence(self):
        for mechanism in ("animated-transition", "continuous-theme", "illustration-motion"):
            with self.subTest(mechanism=mechanism):
                rows = self.planned_rows([mechanism])
                self.assertEqual(rows["I25"]["disposition"], "required")
                methods = {case["id"]: case["method"] for case in rows["I25"]["cases"]}
                self.assertEqual(methods, {"active-window-response": "browser",
                                           "entry-and-reload": "browser",
                                           "repeated-normal-speed": "rendered"})
                self.assertEqual(rows["I26"]["disposition"], "not_applicable")

    def test_animated_navigation_cannot_be_cleared_by_final_anchor_only(self):
        rows = self.planned_rows(["animated-navigation"])
        self.assertEqual(rows["I25"]["disposition"], "required")
        self.assertEqual(rows["I26"]["disposition"], "required")
        self.assertEqual({case["id"] for case in rows["I26"]["cases"]},
                         {"manual-wheel-takeover", "alternate-input-takeover", "settlement-after-cancel",
                          "rapid-command-burst", "command-reversal"})
        self.assertTrue(all(case["method"] == "browser" for case in rows["I26"]["cases"]))
        self.assertEqual(self.planned_rows(["chapter-reader"])["I26"]["disposition"], "not_applicable")

    def test_illustration_motion_is_a_choice_not_a_hero_quota(self):
        self.assertEqual(self.planned_rows(["concepts"])["R19"]["disposition"], "unselected")
        rows = self.planned_rows(["illustration-motion"], ["R19"])
        self.assertEqual(rows["R19"]["disposition"], "required")
        self.assertEqual(rows["I25"]["disposition"], "required")

    def test_generic_symbol_does_not_claim_plus_cross_pivot(self):
        catalog = json.loads((Path(__file__).resolve().parents[1] / "references" / "regression-catalog.json").read_text(encoding="utf-8"))
        def dispositions(features):
            report = plan(catalog, "product", "a" * 64, features, [])
            return {row["id"]: row["disposition"] for row in report["contract"]["requirements"]}
        generic = dispositions(["transforming-symbol"])
        self.assertEqual(generic["I23"], "required")
        self.assertEqual(generic["V15"], "not_applicable")
        for mechanism in ("plus-cross", "plus-minus"):
            with self.subTest(mechanism=mechanism):
                actual = dispositions([mechanism, "transforming-symbol"])
                self.assertEqual(actual["V15"], "required")
                self.assertEqual(actual["I23"], "required")


if __name__ == "__main__":
    unittest.main()
