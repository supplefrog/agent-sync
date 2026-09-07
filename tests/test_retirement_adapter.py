"""Offline integration against the real frozen producer, with fake transport only."""
from __future__ import annotations

import copy
import contextlib
import hashlib
import importlib.util
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parents[1]
STAGE = HERE if (HERE / "tools/evaluation_evidence.py").is_file() else HERE.parents[1] / "agent-signal"
sys.dont_write_bytecode = True
sys.path.insert(0, str(STAGE / "tools"))
sys.path.insert(0, str(STAGE / "tests"))
import test_evaluation_evidence as producer_fixture
from artifact_hash import harness_hash

SPEC = importlib.util.spec_from_file_location("candidate_retirement", HERE / "tools/instruction_retirement.py")
adapter = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(adapter)


def make_bound_fixture(root: Path, *, outcome="win", template_suite=None, cleanup_failure=False, case_ids=None):
    repo = root / "repo"
    (repo / "tools").mkdir(parents=True)
    (repo / "contracts").mkdir()
    (repo / "surfaces").mkdir()
    (repo / "evals").mkdir()
    for name in ("artifact_hash.py", "eval.py", "evaluation_runtime.py", "evaluation_hermes_worker.py", "fleet.py"):
        shutil.copyfile(STAGE / "tools" / name, repo / "tools" / name)
    shutil.copyfile(STAGE / "contracts/instruction-units.schema.json", repo / "contracts/instruction-units.schema.json")
    (repo / "surfaces/owner.md").write_bytes(b"[UNIT] Generic removable guidance.\r\n[KEEP] Existing owner behavior.\r\n")
    unit = {"id": "fixture.unit", "path": "surfaces/owner.md", "selector": {"kind": "tagged-line", "value": "[UNIT]"},
            "class": "generic-steering", "status": "effective", "hosts": ["codex"], "suite": "evals/suite.json",
            "priority": 50, "retest_on": ["model-release", "effective-stack-changed"]}
    (repo / "contracts/instruction-units.json").write_text(json.dumps({"schema_version": 1, "units": [unit]}))
    stack = {"host": "codex", "runtime": "fixture-runtime", "model": "gpt-6-astra", "provider": "openai-codex",
             "reasoning": "xhigh", "tool_policy": "none", "prompt_assembly": "isolated-explicit-artifact-v2",
             "context_policy": "fresh-session-per-output", "equivalence_group": "fixture-group",
             "trial_design": {"seed": 0, "min_trials": 2, "max_trials": 2},
             "decision_margin": {"alpha": 0.05, "margin": 0.1, "rule": "hoeffding-alpha-spending"},
             "max_agent_runs": 480, "transient_retries": 0, "retry_delay": 0.0}
    if case_ids:
        stack["case_ids"] = case_ids
    evaluator = producer_fixture.load_evaluator()
    actual_main = evaluator.main
    holder = {}

    def bound_main():
        # Change producer CLI inputs before execution, never edit an output report.
        argv = list(sys.argv)
        suite_raw = template_suite or Path(argv[1]).read_bytes()
        suite_path = repo / "evals/suite.json"
        suite_path.write_bytes(suite_raw)
        argv[1] = str(suite_path)
        argv[argv.index("--max-agent-runs") + 1] = "480"
        experiment = adapter.build_experiment(repo, unit, stack, root / "frozen")
        argv[argv.index("--candidate") + 1] = experiment["candidate_path"]
        argv[argv.index("--baseline-candidate") + 1] = experiment["baseline_candidate_path"]
        holder["experiment"] = experiment
        with mock.patch.object(sys, "argv", argv):
            return actual_main()

    evaluator.main = bound_main
    with mock.patch.object(producer_fixture, "load_evaluator", return_value=evaluator):
        fixture = producer_fixture.make_evaluation(root / "producer", version=2, mode="retirement", outcome=outcome,
                                                  cleanup_failure=cleanup_failure, case_ids=case_ids)
    fixture.update(repo=repo, unit=unit, stack=stack, experiment=holder["experiment"],
                   suite_path=repo / "evals/suite.json", candidate_path=Path(holder["experiment"]["candidate_path"]),
                   baseline_path=Path(holder["experiment"]["baseline_candidate_path"]))
    return fixture


class RetirementAdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.previous_tempdir = tempfile.tempdir
        scratch = HERE / ".tmp"
        scratch.mkdir(exist_ok=True)
        tempfile.tempdir = str(scratch)
        cls.temp = tempfile.TemporaryDirectory(prefix="retirement-adapter-tests-")
        cls.root = Path(cls.temp.name)
        allowed_env = {key: value for key, value in os.environ.items() if key.upper() in {"SYSTEMROOT", "WINDIR", "COMSPEC", "PATH", "PATHEXT"}}
        allowed_env.update(TEMP=str(cls.root), TMP=str(cls.root), USERPROFILE=str(cls.root / "home"),
                           HERMES_HOME=str(cls.root / "home/hermes"), CODEX_HOME=str(cls.root / "home/codex"))
        for patcher in (mock.patch.dict(os.environ, allowed_env, clear=True),
                        mock.patch("subprocess.Popen", side_effect=RuntimeError("offline adapter tests forbid child processes")),
                        mock.patch("socket.create_connection", side_effect=RuntimeError("offline adapter tests forbid network"))):
            patcher.start()
            cls.addClassCleanup(patcher.stop)
        cls.positive = make_bound_fixture(cls.root / "positive")
        cls.suite_raw = cls.positive["suite_path"].read_bytes()
        cls.negative = make_bound_fixture(cls.root / "negative", outcome="early-failure", template_suite=cls.suite_raw)
        cls.cleanup = make_bound_fixture(cls.root / "cleanup", template_suite=cls.suite_raw, cleanup_failure=True)
        cls.partial = make_bound_fixture(cls.root / "partial", template_suite=cls.suite_raw, case_ids=["held-out-0"])

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()
        tempfile.tempdir = cls.previous_tempdir

    def bundle(self, fixture=None):
        fixture = fixture or self.positive
        temporary = tempfile.TemporaryDirectory(dir=self.root)
        self.addCleanup(temporary.cleanup)
        directory = Path(temporary.name)
        raw = fixture["report_path"].read_bytes()
        receipt = adapter.receipt_from_report(raw, fixture["experiment"])
        path = adapter.write_receipt(directory, receipt, raw)
        return directory, path, receipt

    def test_actual_producer_retirement_and_retention_are_recomputed(self):
        for fixture, decision in ((self.positive, "retire"), (self.negative, "retain")):
            with self.subTest(decision=decision):
                directory, _, receipt = self.bundle(fixture)
                self.assertTrue(receipt["cache_authority"])
                self.assertEqual(receipt["computed_decision"]["decision"], decision)
                current = adapter.load_receipts(directory, {fixture["experiment"]["cache_key"]: fixture["experiment"]})
                self.assertEqual(current["exact"][receipt["cache_key"]]["computed_decision"]["decision"], decision)
                self.assertFalse(receipt["scope"]["package_behavior_exercised"])
                manifest = {"schema_version": 1, "units": [fixture["unit"]]}
                plan = adapter.build_plan(fixture["repo"], manifest, fixture["stack"], "model-release", directory, 1)
                self.assertEqual(plan["units"][0]["action"], "cached-" + decision)
                self.assertEqual(plan["selected_units"], [])

    def test_legacy_and_empty_raw_records_have_no_authority(self):
        directory, path, receipt = self.bundle()
        path.unlink()  # Only this test-created current receipt.
        for version in (1, 2):
            (directory / f"legacy-{version}.json").write_text(json.dumps({"schema_version": version,
                "cache_key": receipt["cache_key"], "decision": "remove", "raw_evidence_path": "empty.json"}))
        (directory / "empty.json").write_text("{}")
        loaded = adapter.load_receipts(directory, {receipt["cache_key"]: self.positive["experiment"]})
        self.assertEqual(len(loaded["historical"]), 2)
        self.assertEqual(loaded["exact"], {})
        for malformed in (b"{}", b"[]", b'{"artifacts":[]}'):
            with self.subTest(raw=malformed), self.assertRaisesRegex(ValueError, "invalid retirement evidence"):
                adapter.receipt_from_report(malformed, self.positive["experiment"])

    def test_tampered_raw_and_editorial_decisions_are_rejected(self):
        directory, path, receipt = self.bundle()
        raw_path = directory / receipt["raw_evidence_path"]
        original = raw_path.read_bytes()
        raw_path.write_bytes(original + b" ")
        loaded = adapter.load_receipts(directory, {receipt["cache_key"]: self.positive["experiment"]})
        self.assertEqual(loaded["exact"], {})
        self.assertTrue(loaded["invalid"])
        raw_path.write_bytes(original)
        modified = copy.deepcopy(receipt)
        modified["computed_decision"]["decision"] = "retain"
        path.write_text(json.dumps(modified))
        self.assertTrue(adapter.load_receipts(directory, {receipt["cache_key"]: self.positive["experiment"]})["invalid"])

    def test_conflicting_valid_receipts_do_not_use_filename_precedence(self):
        self.assertEqual(self.positive["experiment"]["cache_key"], self.negative["experiment"]["cache_key"])
        directory, _, receipt = self.bundle()
        negative_raw = self.negative["report_path"].read_bytes()
        negative = adapter.receipt_from_report(negative_raw, self.positive["experiment"])
        adapter.write_receipt(directory, negative, negative_raw)
        loaded = adapter.load_receipts(directory, {receipt["cache_key"]: self.positive["experiment"]})
        self.assertEqual(loaded["exact"], {})
        self.assertEqual(loaded["conflicts"][0]["decisions"], ["retain", "retire"])
        plan = adapter.build_plan(self.positive["repo"], {"schema_version": 1, "units": [self.positive["unit"]]},
                                  self.positive["stack"], "model-release", directory, 1)
        self.assertEqual(plan["units"][0]["action"], "receipt-conflict")

    def test_cleanup_failure_and_partial_suite_remain_diagnostic(self):
        for fixture in (self.cleanup, self.partial):
            with self.subTest(fixture=fixture["report_path"].parent.parent.name):
                directory, _, receipt = self.bundle(fixture)
                self.assertFalse(receipt["cache_authority"])
                loaded = adapter.load_receipts(directory, {receipt["cache_key"]: fixture["experiment"]})
                self.assertEqual(loaded["exact"], {})
                self.assertTrue(loaded["diagnostic"])

    def test_full_owner_helper_and_selected_cases_invalidate_identity(self):
        fixture = self.positive
        baseline = fixture["experiment"]["cache_key"]
        owner = fixture["repo"] / fixture["unit"]["path"]
        raw = owner.read_bytes()
        try:
            owner.write_bytes(raw.replace(b"Existing owner", b"Changed owner"))
            changed = adapter.build_experiment(fixture["repo"], fixture["unit"], fixture["stack"])
            self.assertNotEqual(changed["cache_key"], baseline)
        finally:
            owner.write_bytes(raw)
        helper = fixture["repo"] / "tools/evaluation_runtime.py"
        raw = helper.read_bytes()
        try:
            helper.write_bytes(raw + b"\n# altered runtime\n")
            self.assertNotEqual(adapter.build_experiment(fixture["repo"], fixture["unit"], fixture["stack"])["cache_key"], baseline)
        finally:
            helper.write_bytes(raw)
        self.assertNotEqual(self.partial["experiment"]["cache_key"], baseline)

    def test_materialization_preserves_names_neighbors_and_crlf(self):
        fixture = self.positive
        self.assertEqual(fixture["candidate_path"].name, fixture["baseline_path"].name)
        self.assertEqual(fixture["candidate_path"].read_bytes(), b"[KEEP] Existing owner behavior.\r\n")
        self.assertEqual(fixture["baseline_path"].read_bytes(), (fixture["repo"] / fixture["unit"]["path"]).read_bytes())

    def test_retired_offhost_reference_and_unsupported_runtime_are_not_selected(self):
        fixture = self.positive
        cases = (({"status": "retired"}, fixture["stack"], "skip-retired"),
                 ({"status": "reference"}, fixture["stack"], "reference-source-review"),
                 ({"hosts": ["hermes"]}, fixture["stack"], "skip-host"),
                 ({"hosts": ["omp"]}, {**fixture["stack"], "host": "omp"}, "unsupported-runtime"))
        for unit_changes, stack, expected in cases:
            with self.subTest(expected=expected):
                manifest = {"schema_version": 1, "units": [{**fixture["unit"], **unit_changes}]}
                plan = adapter.build_plan(fixture["repo"], manifest, stack, "model-release", self.root / "none", 2)
                self.assertEqual(plan["selected_units"], [])
                self.assertEqual(plan["units"][0]["action"], expected)

    def test_missing_suite_and_ambiguous_selector_fail_before_selection(self):
        fixture = self.positive
        with self.assertRaisesRegex(ValueError, "escapes repository"):
            adapter.unit_text(fixture["repo"], {**fixture["unit"], "path": (self.root / "outside.md").as_posix()})
        with self.assertRaises(FileNotFoundError):
            adapter.build_plan(fixture["repo"], {"schema_version": 1, "units": [{**fixture["unit"], "suite": "evals/missing.json"}]},
                               fixture["stack"], "model-release", self.root / "none", 1)
        with self.assertRaisesRegex(ValueError, "exactly once"):
            adapter._span("# Duplicate\na\n# Duplicate\nb\n", {"kind": "heading", "value": "# Duplicate"})

    def test_unobserved_snapshot_and_unproved_crosshost_claims_are_rejected(self):
        fixture = self.positive
        for field in ("model_snapshot", "provider_snapshot", "tool_schema", "equivalence_hash"):
            with self.subTest(field=field):
                changed = adapter.build_experiment(fixture["repo"], fixture["unit"], {**fixture["stack"], field: "claimed"})
                with self.assertRaisesRegex(ValueError, "cannot verify stack claim"):
                    adapter.receipt_from_report(fixture["report_path"].read_bytes(), changed)

    def test_append_only_receipt_write_is_idempotent(self):
        directory, target, receipt = self.bundle()
        original = target.read_bytes()
        adapter.write_receipt(directory, receipt, self.positive["report_path"].read_bytes())
        self.assertEqual(target.read_bytes(), original)

    def test_cli_ingests_actual_report_then_planner_reads_same_receipt(self):
        fixture = self.positive
        directory = self.root / "cli-evidence"
        args = ["--repo", str(fixture["repo"]), "--host", "codex", "--runtime", "fixture-runtime",
                "--model", "gpt-6-astra", "--provider", "openai-codex", "--reasoning", "xhigh",
                "--min-trials", "2", "--max-trials", "2", "--max-agent-runs", "480", "--transient-retries", "0",
                "--retry-delay", "0", "--equivalence-group", "fixture-group", "--receipts-dir", str(directory)]
        owner = fixture["repo"] / fixture["unit"]["path"]
        before = owner.read_bytes()
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(adapter.main([*args, "--record-report", str(fixture["report_path"]), "--unit", "fixture.unit"]), 0)
            out = self.root / "cli-plan.json"
            self.assertEqual(adapter.main([*args, "--out", str(out)]), 0)
        self.assertEqual(json.loads(out.read_bytes())["units"][0]["action"], "cached-retire")
        self.assertEqual(owner.read_bytes(), before)

    def test_source_projection_cannot_be_its_own_materialization_target(self):
        fixture = self.positive
        owner = fixture["repo"] / "unsafe/candidate/owner.md"
        owner.parent.mkdir(parents=True)
        owner.write_bytes(b"[UNIT] Removable.\n[KEEP] Unchanged.\n")
        before = owner.read_bytes()
        with self.assertRaisesRegex(ValueError, "overlaps source"):
            adapter.build_experiment(fixture["repo"], {**fixture["unit"], "path": "unsafe/candidate/owner.md"},
                                     fixture["stack"], fixture["repo"] / "unsafe")
        self.assertEqual(owner.read_bytes(), before)



if __name__ == "__main__":
    unittest.main(verbosity=2)
