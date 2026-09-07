"""Deterministic counterexamples at evaluator parsing and outcome boundaries."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import io
import contextlib
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("evaluator_core", ROOT / "tools" / "eval.py")
evaluator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(evaluator)


def judgment_v3():
    return {
        "a": {"criteria": [{"id": "scope", "pass": True, "evidence": "A evidence"}]},
        "b": {"criteria": [{"id": "scope", "pass": True, "evidence": "B evidence"}]},
        "winner": "A", "reason": "A satisfies the task",
    }


class EvaluatorCoreTests(unittest.TestCase):
    def test_model_output_cannot_make_a_failed_run_retryable(self):
        result = {"ok": False, "returncode": 1, "stderr": "invalid output schema", "output": "503"}
        self.assertFalse(evaluator.transient_provider_failure(result))

    def test_attempt_history_preserves_complete_results(self):
        failed = {"ok": False, "execution_ok": False, "operational_ok": True, "returncode": 1,
                  "seconds": 0.1, "output": "partial answer", "stderr": "transport failed",
                  "route_attestation": {"ok": False, "errors": ["native transport failed"]},
                  "runtime_contract": {"cleanup": {"credentials_removed": True, "state_removed": True, "errors": []}},
                  "failure": {"kind": "provider-transient", "source": "native-transport", "http_status": 503},
                  "native_events": [{"type": "error", "http_status": 503}], "session_ids": []}
        success = {**failed, "ok": True, "execution_ok": True, "returncode": 0,
                   "output": "final answer", "failure": None}
        with mock.patch.object(evaluator, "run_agent", side_effect=[failed, success]):
            result = evaluator.run_agent_with_retry(evaluator.AgentRunBudget(2), "ignored", transient_retries=1, retry_delay=0)
        self.assertEqual(result["attempt_count"], 2)
        self.assertEqual(result["attempts"][0]["output"], "partial answer")
        self.assertEqual(result["attempts"][0]["native_events"], failed["native_events"])
        self.assertTrue(result["attempts"][0]["transient"])
        self.assertEqual(evaluator.attempt_result(result), evaluator.attempt_result(result["attempts"][-1]))

    def test_retry_cannot_erase_control_or_cleanup_failure(self):
        base = {"ok": False, "execution_ok": False, "operational_ok": True, "returncode": 1,
                "failure": {"kind": "provider-transient", "source": "native-transport", "http_status": 503}}
        for changed in ({"operational_ok": False},
                        {"runtime_contract": {"cleanup": {"credentials_removed": False, "state_removed": False, "errors": ["failed"]}}},
                        {"runtime_contract": {"tool_observation": {"tool_activity_count": 1}}},
                        {"runtime_contract": {"prompt_isolation": {"verified": False}}},
                        {"runtime_contract": {"prompt_isolation": {"verified": True, "contamination": ["canary"]}}},
                        {"runtime_contract": {"prompt_isolation": {"canary_absent": False}}},
                        {"runtime_contract": {"prompt_isolation": {"native_tool_names": ["terminal"]}}},
                        {"runtime_contract": {"tool_observation": {"execution_blocker_installed": False}}}):
            with self.subTest(changed=changed):
                self.assertFalse(evaluator.transient_provider_failure({**base, **changed}))

    def test_subset_positive_is_diagnostic_and_negative_is_preserved(self):
        for positive in ("admit", "retire"):
            self.assertEqual(evaluator.scope_decision({"decision": positive}, False),
                             {"decision": "inconclusive", "coverage_reason": "partial-suite", "diagnostic_decision": positive})
        self.assertEqual(evaluator.scope_decision({"decision": "reject"}, False), {"decision": "reject"})

    def test_supported_suite_to_report_mapping(self):
        for suite, expected in (({}, 2), ({"schema_version": 1}, 2), ({"schema_version": 2}, 2), ({"schema_version": 3}, 3)):
            self.assertEqual(evaluator.suite_report_version(suite), expected)

    def test_report_export_failure_retains_explicit_recovery_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            report = {"decision": {"decision": "reject"}, "operational_ok": True}
            with mock.patch.object(evaluator, "finalize_report", side_effect=OSError("synthetic failure")):
                evaluator.finalize_workspace(root / "report.json", report, mock.Mock(), workspace)
            self.assertFalse(report["operational_ok"])
            self.assertFalse(report["report_export"]["written"])
            self.assertEqual(report["workspace_lifecycle"]["outcome"], "retained-report-write-failure")
            recovery = json.loads(Path(report["report_export"]["recovery_path"]).read_text(encoding="utf-8"))
            self.assertEqual(recovery["decision"]["decision"], "reject")

    def test_workspace_cleanup_failure_is_explicit_without_relabeling_negative(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            report = {"decision": {"decision": "reject"}, "operational_ok": True}
            lifecycle = mock.Mock()
            lifecycle.cleanup.return_value = {"created": [], "deleted": [], "remaining": [], "errors": []}
            with mock.patch.object(evaluator.shutil, "rmtree", side_effect=OSError("synthetic failure")):
                evaluator.finalize_workspace(root / "report.json", report, lifecycle, workspace)
            self.assertFalse(report["operational_ok"])
            self.assertEqual(report["workspace_lifecycle"]["outcome"], "cleanup-failed")
            self.assertEqual(report["decision"]["decision"], "reject")

    def test_attempt_projection_drops_undeclared_sensitive_fields(self):
        result = evaluator.attempt_result({"output": "answer", "api_key": "synthetic-secret", "attempt": 1, "attempts": []})
        self.assertEqual(result, {"output": "answer"})

    def run_v2_main(self, root, *, judge_ok=True, judge_suffix="", mutate_inputs=False, drift=False):
        suite = {"schema_version": 2, "name": "core-regression", "cases": [
            {"id": kind, "kind": kind, "prompt": "ORIGINAL TASK"}
            for kind in ("representative", "near-miss", "adversarial", "held-out")
        ]}
        suite_path, candidate, baseline, out = (root / name for name in ("suite.json", "candidate.md", "baseline.md", "report.json"))
        suite_text = json.dumps(suite)
        suite_path.write_text(suite_text, encoding="utf-8")
        candidate.write_text("ORIGINAL CANDIDATE", encoding="utf-8")
        baseline.write_text("ORIGINAL BASELINE", encoding="utf-8")
        prompts = []
        valid_judgment = json.dumps({"a": {"hard_pass": True, "reason": "passed"},
                                     "b": {"hard_pass": True, "reason": "passed"},
                                     "winner": "tie", "reason": "equal"})

        def fake_run(_agent, prompt, *_args, **_kwargs):
            judge = prompt.startswith("Judge two anonymous")
            if not judge:
                prompts.append(prompt)
            return {"ok": judge_ok if judge else True, "returncode": 0 if judge_ok or not judge else 1,
                    "output": valid_judgment + judge_suffix if judge else "answer", "stderr": "", "seconds": 0,
                    "route_attestation": {"required": True, "ok": True, "errors": []}, "session_ids": []}

        original_read = Path.read_bytes
        def read_then_change(path):
            data = original_read(path)
            if mutate_inputs and path in (candidate, baseline, suite_path):
                path.write_bytes(data.replace(b"ORIGINAL", b"MODIFIED"))
            return data

        argv = ["eval.py", str(suite_path), "--candidate", str(candidate), "--baseline-candidate", str(baseline),
                "--agent", "codex", "--model", "test-model", "--provider", "test-provider", "--reasoning", "high",
                "--min-trials", "1", "--max-trials", "1", "--max-agent-runs", "16",
                "--equivalence-group", "test", "--rollback", "restore fixture", "--out", str(out)]
        with mock.patch.object(evaluator, "run_agent", side_effect=fake_run), \
             mock.patch.object(evaluator, "command_version", return_value="test"), \
             mock.patch.object(evaluator.HermesSessionLifecycle, "cleanup", return_value={"created": [], "deleted": [], "remaining": []}), \
             mock.patch("sys.argv", argv), mock.patch.object(Path, "read_bytes", read_then_change), \
             contextlib.redirect_stdout(io.StringIO()):
            if drift:
                with mock.patch.object(evaluator, "harness_hash", side_effect=["a" * 64, "b" * 64]):
                    code = evaluator.main()
            else:
                code = evaluator.main()
        return code, json.loads(out.read_text(encoding="utf-8")), prompts, valid_judgment + judge_suffix, suite_text

    def test_whole_json_object_required(self):
        for text in ('before {"ok":true}', '{"ok":true} after', '{"ok":true} {}',
                     '```json\n{"ok":true}\n```', '{broken {"ok":true}}',
                     '{"ok":true,"ok":false}', '{"x":{"a":1,"a":2}}',
                     '{"x":NaN}', '{"x":Infinity}', '{"x":-Infinity}', '{"x":1e999}', '[]'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                evaluator.extract_json(text)
        self.assertEqual(evaluator.extract_json(' \n {"ok":true} \t'), {"ok": True})

    def test_receipt_constraints_are_enforced(self):
        schema = {
            "type": "object", "required": ["decision", "approved", "label", "count"],
            "properties": {
                "decision": {"type": "string"}, "approved": {"const": False},
                "label": {"type": ["string", "null"], "minLength": 3, "pattern": "^[a-z]+$"},
                "count": {"type": "integer", "minimum": 1, "maximum": 3},
            }, "additionalProperties": False,
        }
        receipt = {"decision": "hold", "approved": False, "label": "safe", "count": 2}
        case = {"expected_receipt": {"decision": "hold"}}
        self.assertTrue(evaluator.structured_receipt_check(case, json.dumps(receipt), schema)["pass"])
        for field, bad in (("approved", True), ("label", "UPPER"), ("label", "a"), ("count", 4), ("count", True)):
            with self.subTest(field=field, bad=bad):
                self.assertFalse(evaluator.structured_receipt_check(case, json.dumps({**receipt, field: bad}), schema)["pass"])

    def test_malformed_and_unsupported_schema_rejected(self):
        for schema in ({"type": "not-a-type"}, {"type": "string", "minimum": "zero"},
                       {"type": "object", "constt": False},
                       {"$schema": "https://example.invalid/future", "type": "object"},
                       {"type": "object", "properties": {"x": {"$ref": "https://example.invalid/x"}}},
                       {"type": "string", "format": "not-an-implemented-format"}):
            with self.subTest(schema=schema), self.assertRaises(ValueError):
                evaluator._schema_reasons({}, schema)

    def test_full_v3_judgment_contract(self):
        mutations = []
        for key in ("winner", "reason"):
            value = judgment_v3()
            del value[key]
            mutations.append(value)
        value = judgment_v3()
        value["a"]["criteria"][0]["evidence"] = None
        mutations.append(value)
        value = judgment_v3()
        value["extra"] = True
        mutations.append(value)
        value = judgment_v3()
        value["b"]["criteria"][0]["pass"] = "false"
        mutations.append(value)
        for value in mutations:
            with self.subTest(value=value), self.assertRaises(ValueError):
                evaluator.map_v3_judgment(value, ["baseline", "candidate"], ["scope"])
        with self.assertRaises(ValueError):
            evaluator.map_v3_judgment(judgment_v3(), ["candidate", "candidate"], ["scope"])

    def test_schema_combinators_refs_and_array_constraints(self):
        schema = {"type": "object", "$defs": {"permission": {"const": False}},
                  "properties": {"approved": {"$ref": "#/$defs/permission"},
                                 "items": {"type": "array", "uniqueItems": True, "maxItems": 2},
                                 "mode": {"enum": ["hold", "publish"]}},
                  "if": {"properties": {"mode": {"const": "publish"}}},
                  "then": {"required": ["evidence"]}}
        for bad in ({"approved": True}, {"items": [1, 1]}, {"items": [1, 2, 3]}, {"mode": "publish"}):
            with self.subTest(bad=bad):
                self.assertTrue(evaluator._schema_reasons(bad, schema))
        self.assertFalse(evaluator._schema_reasons({"approved": False, "items": [1, 2], "mode": "hold"}, schema))
        self.assertTrue(evaluator._schema_reasons(False, {"const": 0}))

    def test_expected_receipt_local_ref_uses_complete_schema(self):
        suite = {"schema_version": 3, "receipt_schema": {"type": "object", "$defs": {"d": {"const": "hold"}},
                 "properties": {"decision": {"$ref": "#/$defs/d"}}}, "stability": {"trials": 1},
                 "cases": [{"id": kind, "kind": kind, "prompt": "task", "expected_receipt": {"decision": "hold"},
                            "semantic_criteria": [{"id": "scope", "text": "check scope"}]}
                           for kind in ("representative", "near-miss", "adversarial", "held-out")]}
        evaluator.validate_suite(suite)
        suite["cases"][0]["expected_receipt"]["decision"] = "publish"
        with self.assertRaisesRegex(ValueError, "expected_receipt violates"):
            evaluator.validate_suite(suite)

    def test_v2_ineligible_preferred_answer_cannot_win(self):
        result = evaluator.effective_judgment_result(["baseline", "baseline"],
                    [{"baseline": False, "candidate": True}] * 2, {"baseline": True, "candidate": True})
        self.assertEqual(result["winner"], "candidate")
        self.assertEqual(result["eligibility"], {"baseline": "fail", "candidate": "pass"})

    def test_irrelevant_preference_and_semantic_disagreement_do_not_block(self):
        passes = [{"baseline": {"scope": v}, "candidate": {"scope": True}} for v in (True, False)]
        result = evaluator.effective_judgment_result(["baseline", "candidate"], passes,
                    {"baseline": False, "candidate": True}, ["scope"])
        self.assertEqual(result["winner"], "candidate")
        self.assertTrue(result["raw_disagreement"]["winner"])
        self.assertTrue(result["raw_disagreement"]["criteria"])
        self.assertFalse(result["disagreement"]["winner"])
        self.assertFalse(result["disagreement"]["criteria"])
        # Uncertainty about the losing baseline also cannot change a resolved
        # candidate preference when the candidate itself is eligible.
        result = evaluator.effective_judgment_result(["candidate", "candidate"], passes,
                    {"baseline": True, "candidate": True}, ["scope"])
        self.assertEqual(result["eligibility"]["baseline"], "unresolved")
        self.assertFalse(result["disagreement"]["criteria"])

    def test_candidate_eligibility_disagreement_is_not_a_resolved_failure(self):
        passes = [{"baseline": {"scope": True}, "candidate": {"scope": v}} for v in (True, False)]
        result = evaluator.effective_judgment_result(["candidate", "candidate"], passes,
                    {"baseline": True, "candidate": True}, ["scope"])
        self.assertEqual(result["eligibility"]["candidate"], "unresolved")
        self.assertTrue(result["disagreement"]["criteria"])
        row = {**result, "candidate_receipt_pass": True, "candidate_hard_pass": False,
               "judge_disagreement": True}
        decision = evaluator.v3_stability_decision([row], {"trials": 1}, 1)
        self.assertEqual(decision["decision"], "inconclusive")
        self.assertEqual(decision["candidate_hard_failures"], 0)

    def test_failed_v2_judge_with_valid_json_preserves_raw_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            code, report, _, raw, _ = self.run_v2_main(Path(temp), judge_ok=False)
        self.assertEqual(code, 1)
        self.assertEqual(report["decision"]["decision"], "harness-failure")
        for row in report["results"]:
            self.assertEqual(len(row["judge_errors"]), 2)
            for judge in row["judgments"]:
                self.assertEqual(judge["judgment"], {"raw": raw})
                self.assertEqual(judge["run"]["output"], raw)
        self.assertEqual(report["effective_stack"]["judge_reasoning"], "high")
        self.assertEqual(report["effective_stack"]["judge_tool_policy"], "none")

    def test_trailing_judge_text_preserved_when_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            _, report, _, raw, _ = self.run_v2_main(Path(temp), judge_suffix=" trailing")
        self.assertEqual(report["decision"]["decision"], "harness-failure")
        self.assertEqual(report["results"][0]["judgments"][0]["judgment"], {"raw": raw})

    def test_prompt_and_suite_hash_bind_captured_bytes_despite_source_changes(self):
        with tempfile.TemporaryDirectory() as temp:
            _, report, prompts, _, suite_text = self.run_v2_main(Path(temp), mutate_inputs=True)
        self.assertTrue(all("ORIGINAL TASK" in prompt and "MODIFIED" not in prompt for prompt in prompts))
        self.assertEqual(report["artifacts"]["suite_sha256"], hashlib.sha256(suite_text.encode()).hexdigest())
        self.assertEqual(report["input_snapshot"]["suite_source"], suite_text)
        for side, artifact_key in (("candidate", "candidate_prompt_sha256"), ("baseline", "baseline_prompt_sha256")):
            snapshot = report["input_snapshot"][side]
            self.assertEqual(report["artifacts"][artifact_key], hashlib.sha256(snapshot["prompt_text"].encode()).hexdigest())
            self.assertIn("ORIGINAL", snapshot["prompt_text"])

    def test_package_snapshot_matches_fleet_identity_and_freezes_projection(self):
        from fleet import directory_record
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            candidate = root / "SKILL.md"
            candidate.write_bytes(b"Original [details](details.md). Run `worker.py`.")
            (root / "details.md").write_bytes(b"Original details")
            (root / "worker.py").write_bytes(b"print('worker')")
            expected = directory_record(root)["sha256"]
            original_read = Path.read_bytes
            def read_then_change(path):
                data = original_read(path)
                if path == candidate:
                    path.write_bytes(b"Changed")
                return data
            with mock.patch.object(Path, "read_bytes", read_then_change):
                frozen = evaluator.freeze_candidate(candidate)
            self.assertEqual(frozen["package_sha256"], expected)
            self.assertIn("Original", frozen["prompt_text"])
            self.assertNotEqual(frozen["package_sha256"], directory_record(root)["sha256"])
            self.assertIn("worker.py", frozen["files"])
            self.assertNotIn("print('worker')", frozen["prompt_text"])

    def test_harness_change_makes_run_a_harness_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            code, report, *_ = self.run_v2_main(Path(temp), drift=True)
        self.assertEqual(code, 1)
        self.assertEqual(report["status"], "failed")
        self.assertFalse(report["harness_integrity"]["unchanged"])
        self.assertEqual(report["decision"]["reason"], "harness changed during evaluation")

    def test_native_output_is_not_salvaged_by_deleting_a_leading_line(self):
        import evaluation_runtime
        raw = '\x1b[31mUnexpected text\n{"ok":true}'
        with mock.patch.object(evaluation_runtime, "run_no_tools", return_value={"output": raw}):
            result = evaluator.run_agent("hermes", "task", Path("unused"), 1, False,
                                         "test-model", "openai-codex", "high", "none")
        self.assertEqual(result["output"], raw)
        with self.assertRaises(ValueError):
            evaluator.extract_json(result["output"])


if __name__ == "__main__":
    unittest.main()
