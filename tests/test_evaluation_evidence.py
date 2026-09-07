from __future__ import annotations

import contextlib
import copy
import hashlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))
from evaluation_evidence import validate_report
import evaluation_runtime as runtime


def load_evaluator():
    spec = importlib.util.spec_from_file_location("fixture_evaluator", REPO / "tools" / "eval.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


def historical_report(report: dict) -> dict:
    """Legacy report shape, not a claim that it ran on an earlier runtime."""
    report = copy.deepcopy(report)
    report["effective_stack"].pop("runtime_lane", None)
    report["effective_stack"]["judge_tool_policy"] = "safe"
    report.pop("evaluation_scope", None)
    report.pop("scope", None)
    report.pop("attempt_ledger", None)
    for key in ("operational_ok", "report_export", "workspace_lifecycle", "version_probes"):
        report.pop(key, None)
    for row in report["results"]:
        positions = [(row[side], False) for side in ("baseline", "candidate")]
        positions += [(judgment["run"], True) for judgment in row["judgments"]]
        for run, judge in positions:
            for key in ("runtime_contract", "native_events", "native_result_metadata", "execution_ok", "operational_ok"):
                run.pop(key, None)
            if judge:
                run["route_attestation"]["requested"]["tool_policy"] = "safe"
            run["attempts"] = [{key: value for key, value in attempt.items() if key in ("attempt", "ok", "returncode", "seconds")} for attempt in run["attempts"]]
    return report


def make_evaluation(root: Path, *, version: int | None = 3, outcome: str = "tie", agent: str = "codex", retain: bool = False, mode: str = "admission", baseline: bool = True, case_ids: list[str] | None = None, retry_first: bool = False, cleanup_failure: bool = False, judge_agent: str = "codex") -> dict:
    """Run the actual report producer with fake transport, no network or models.

    Returned paths and bytes are real fixture inputs; receipt checks, judgment
    mapping, eligibility, stopping, summaries and serialization are production.
    """
    evaluator = load_evaluator()
    root.mkdir(parents=True, exist_ok=True)
    include_baseline = baseline
    candidate, baseline_path, suite_path, report_path = (root / name for name in ("candidate.md", "baseline.md", "suite.json", "report.json"))
    candidate.write_text("CANDIDATE_TAG\n", encoding="utf-8")
    baseline_path.write_text("BASELINE_TAG\n", encoding="utf-8")
    kinds = ("representative", "near-miss", "adversarial", "held-out")
    # More observations let the genuine v2 confidence rule admit strong evidence.
    copies = 12 if version != 3 and outcome == "win" else 1
    cases = [{"id": f"{kind}-{index}", "kind": kind, "prompt": f"Decide whether to hold {kind}-{index}.", "criteria": ["Give the correct decision."], "must_contain": ["hold"]} for index in range(copies) for kind in kinds]
    suite = {"schema_version": version, "name": "real-producer-fixture", "claim": "Correct decision receipts.", "cases": cases}
    if version is None:
        del suite["schema_version"]
    if version == 3:
        suite.update(
            receipt_schema={"type": "object", "required": ["decision", "reason"], "properties": {"decision": {"type": "string", "enum": ["hold", "go"]}, "reason": {"type": "string"}}, "additionalProperties": False},
            stability={"trials": 2, "required_win_kinds": ["held-out"]},
        )
        for case in cases:
            case.update(expected_receipt={"decision": "hold"}, semantic_criteria=[{"id": "sound", "text": "Reasoning supports the decision."}])
    suite_raw = (json.dumps(suite, indent=2) + "\n").encode()
    suite_path.write_bytes(suite_raw)
    cap = len(cases) * 5 * 2
    calls = 0
    retried = False

    def fake_run(run_agent, prompt, workdir, timeout, full_tools, model=None, provider=None, reasoning=None, tool_policy="none", lifecycle=None, output_schema=None, require_attestation=False):
        nonlocal calls, retried
        calls += 1
        if outcome == "interrupted" and calls == 1:
            raise KeyboardInterrupt("fixture interruption")
        is_judge = workdir.parent.name == "judge"
        candidate_run = workdir.name == "candidate"
        if is_judge:
            section = "RECEIPT A\n" if version == 3 else "ANSWER A\n"
            a_text = prompt.split(section, 1)[1].split("RECEIPT B\n" if version == 3 else "ANSWER B\n", 1)[0]
            winner = ("A" if "CANDIDATE_TAG" in a_text else "B") if outcome == "win" else "tie"
            if outcome in ("disagreement", "eligibility"):
                preferred = "BASELINE_TAG" if workdir.name == "0" else "CANDIDATE_TAG"
                winner = "tie" if workdir.name == "tiebreak" else "A" if preferred in a_text else "B"
            if version == 3:
                answer = {"criteria": [{"id": "sound", "pass": True, "evidence": "The receipt explains the hold."}]}
            else:
                answer = {"hard_pass": True, "reason": "The answer gives the required hold."}
            output = json.dumps({"a": answer, "b": answer, "winner": winner, "reason": "The required reasoning is present."})
        else:
            decision = "go" if outcome == "early-failure" and candidate_run else "hold"
            if outcome == "eligibility" and not candidate_run:
                decision = "go"
            marker = "CANDIDATE_TAG" if candidate_run else "BASELINE_TAG"
            output = json.dumps({"decision": decision, "reason": marker}) if version == 3 else f"{decision} {marker}"
        observed = {"model": model, "provider": "openai" if run_agent == "codex" and provider == "openai-codex" else provider, "reasoning": reasoning, "tool_calls_count": 0}
        if run_agent == "hermes":
            observed["tool_calls_count"] = 0
        failed = outcome == "harness-failure" and candidate_run
        run = {
            "ok": not failed, "returncode": 1 if failed else 0, "seconds": 0.01,
            "execution_ok": not failed, "operational_ok": True,
            "output": output, "stderr": "fixture execution error" if failed else "",
            "session_ids": [], "session_receipt_error": None,
            "route_attestation": {"required": True, "ok": True, "errors": [], "provider_resolved_identity_verified": False, "source": "native-runtime-metadata" if run_agent == "codex" else "native-AIAgent-runtime-metadata", "requested": {"model": model, "provider": provider, "reasoning": reasoning, "tool_policy": tool_policy}, "observed": observed},
        }
        assembled = "Synthetic native prompt without personal context."
        contract = {
            "lane": "inline-text-no-tools-v1", "tool_policy": "none", "credentials_outside_fixture": True,
            "personal_config_copied": False, "global_session_cleanup_authority": False,
            "credential_owner": run_agent, "cross_host_credential_fallback": False,
            "tool_schema_absence_verified": False,
            "limitations": ["this lane does not exercise shipped scripts or other tool-dependent behavior"],
            "cleanup": {"credentials_removed": True, "state_removed": True, "errors": []},
        }
        if run_agent == "codex":
            events = [{"type": "thread.started", "thread_id": f"{calls:08d}-1111-1111-1111-111111111111"}, {"type": "turn.started"},
                      {"type": "item.completed", "item": {"id": "answer", "type": "agent_message", "text": output}}, {"type": "turn.completed"}]
            native = runtime.codex_events("\n".join(json.dumps(event) for event in events), evaluator.extract_json, expected_output=output)
            run["native_events"] = native["events"]
            contract["tool_observation"] = {key: value for key, value in native.items() if key not in {"events", "thread_id"}}
            contract["prompt_isolation"] = {"verified": True, "source": "codex-debug-prompt-input", "sha256": hashlib.sha256(assembled.encode()).hexdigest(), "disabled_skill_count": 0, "contamination": [], "tool_schema_absence_verified": False}
            contract["controls"] = {"disabled_features": list(runtime.CODEX_DISABLED_FEATURES), "project_doc_max_bytes": 0,
                                    "personality": "none", "web_search": "disabled", "model_provider": "openai", "approval_policy": "never", "sandbox": "read-only", "ignore_user_config": True,
                                    "fresh_user_home": True, "fresh_runtime_home": True, "native_events": "json", "session_logging": "disposable-home-only"}
        else:
            contract["prompt_isolation"] = {"verified": True, "source": "native-AIAgent-build-system-prompt", "sha256": hashlib.sha256(assembled.encode()).hexdigest(), "assembled_prompt": assembled,
                                            "canary": "SYNTHETIC_ISOLATION_CANARY", "canary_absent": True, "contamination": [], "native_tool_names": [], "tool_schema_absence_verified": False}
            contract["tool_observation"] = {"source": "native-AIAgent-tool-dispatch-guard", "tool_activity_count": 0, "execution_blocker_installed": True, "ok": True, "tool_schema_absence_verified": False}
            contract["controls"] = {"adapter": "native-AIAgent-API", "safe_mode": True, "toolsets": "none", "ignore_rules": True, "ignore_user_config": True, "fresh_user_home": True, "fresh_runtime_home": True,
                                    "skip_context_files": True, "skip_memory": True, "load_soul_identity": False, "skip_background_review": True, "fallback_model": None, "save_trajectories": False,
                                    "credentials_in_memory_only": True, "credential_refresh_if_expiring": False, "endpoint": "https://chatgpt.com/backend-api/codex"}
            contract["output_source"] = "native-AIAgent-final-response"
            run["native_result_metadata"] = {"completed": True, "failed": False, "interrupted": False, "partial": False, "model": model, "provider": provider, "api_calls": 1, "final_response": output}
        run["runtime_contract"] = contract
        if cleanup_failure and candidate_run:
            contract["cleanup"] = {"credentials_removed": False, "state_removed": False, "errors": ["fixture cleanup failed"]}
            run.update(ok=False, operational_ok=False)
        if retry_first and candidate_run and run_agent == "codex" and not retried:
            retried = True
            events = run["native_events"][:2] + [{"type": "turn.failed", "error": {"status_code": 503}}]
            native = runtime.codex_events("\n".join(json.dumps(event) for event in events), evaluator.extract_json, expected_output="")
            run.update(ok=False, execution_ok=False, returncode=1, output="", stderr="", failure=native["failure"], native_events=events)
            contract["tool_observation"] = {key: value for key, value in native.items() if key not in {"events", "thread_id"}}
            run["route_attestation"]["ok"] = False
            run["route_attestation"]["errors"] = native["errors"]
            run["route_attestation"]["observed"]["tool_calls_count"] = None
        return run

    def cleanup(lifecycle):
        return {"policy": "retain-evidence" if retain else "delete-after-durable-report", "created": [], "protected": [], "deleted": [], "remaining": [], "errors": []}

    argv = ["eval.py", str(suite_path), "--candidate", str(candidate), "--agent", agent, "--judge-agent", judge_agent, "--model", "gpt-6-astra", "--provider", "openai-codex", "--reasoning", "xhigh", "--tool-policy", "none", "--equivalence-group", "fixture-group", "--min-trials", "2", "--max-trials", "2", "--max-agent-runs", str(cap), "--transient-retries", "1" if retry_first else "0", "--retry-delay", "0", "--rollback", "restore fixture", "--decision-mode", mode, "--out", str(report_path)]
    if include_baseline:
        argv += ["--baseline-candidate", str(baseline_path)]
    for case_id in case_ids or []:
        argv += ["--case", case_id]
    if retain:
        argv.append("--retain-eval-sessions")
    with mock.patch.object(sys, "argv", argv), mock.patch.object(evaluator, "run_agent", side_effect=fake_run), mock.patch.object(evaluator, "command_version", return_value="fixture-runtime"), mock.patch.object(evaluator.HermesSessionLifecycle, "cleanup", cleanup), contextlib.redirect_stdout(io.StringIO()):
        exit_code = evaluator.main()
    report = json.loads(report_path.read_bytes())
    return {"report": report, "suite": suite, "suite_sha256": hashlib.sha256(suite_raw).hexdigest(), "candidate_path": candidate, "baseline_path": baseline_path if include_baseline else None, "suite_path": suite_path, "report_path": report_path, "max_agent_runs": cap, "exit_code": exit_code}


class EvaluationEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def fixture(self, **kwargs):
        return make_evaluation(self.root, **kwargs)

    def test_native_codex_tools_cannot_hide_behind_success_flags(self):
        fixture = self.fixture(outcome="win")
        fixture["report"]["results"][0]["candidate"]["route_attestation"]["observed"]["tool_calls_count"] = 1
        self.assertTrue(validate_report(fixture["report"], fixture["suite"])["errors"])

    def test_native_codex_events_cannot_hide_tool_execution(self):
        fixture = self.fixture(outcome="win")
        fixture["report"]["results"][0]["candidate"]["native_events"][2]["item"]["type"] = "command_execution"
        self.assertTrue(validate_report(fixture["report"], fixture["suite"])["errors"])

    def test_native_cleanup_failure_is_operational_and_blocks_positive_sufficiency(self):
        fixture = self.fixture(outcome="win")
        fixture["report"]["results"][0]["candidate"]["runtime_contract"]["cleanup"] = {"credentials_removed": False, "state_removed": False, "errors": ["permission denied"]}
        result = validate_report(fixture["report"], fixture["suite"])
        self.assertTrue(result["operational_errors"])
        self.assertFalse(result["positive_decision_sufficient"])

    def test_single_attempt_history_cannot_contradict_final_result(self):
        fixture = self.fixture(outcome="win")
        fixture["report"]["results"][0]["candidate"]["attempts"][0]["output"] = "contradictory history"
        self.assertTrue(validate_report(fixture["report"], fixture["suite"])["errors"])

    def test_historical_judge_policy_and_new_no_tools_plan_remain_distinct(self):
        fixture = self.fixture()
        report = fixture["report"]
        report["effective_stack"]["judge_tool_policy"] = "safe"
        for row in report["results"]:
            for judgment in row["judgments"]:
                judgment["run"]["route_attestation"]["requested"]["tool_policy"] = "safe"
        self.assertIn("judge tool policy differs from producer plan", validate_report(report, fixture["suite"])["errors"])
        historical = historical_report(fixture["report"])
        self.assertEqual(validate_report(historical, fixture["suite"])["errors"], [])

    def test_historical_negative_and_inconclusive_evidence_remains_valid(self):
        for outcome, expected in (("early-failure", "reject"), ("tie", "inconclusive")):
            with self.subTest(outcome=outcome):
                fixture = self.fixture(outcome=outcome)
                report = historical_report(fixture["report"])
                result = validate_report(report, fixture["suite"])
                self.assertEqual(result["errors"], [])
                self.assertEqual(result["computed_decision"]["decision"], expected)
                self.assertEqual(result["scope"]["runtime_lane"], "historical-unspecified")
                self.assertEqual(result["scope"]["evaluated_projection"], "historical-unspecified")
                self.assertIsNone(result["scope"]["package_behavior_exercised"])

    def test_native_hermes_completion_and_prompt_contradictions_fail(self):
        fixture = self.fixture(agent="hermes", outcome="win")
        for mutation in ("completion", "prompt", "tools"):
            with self.subTest(mutation=mutation):
                report = copy.deepcopy(fixture["report"])
                run = report["results"][0]["candidate"]
                if mutation == "completion":
                    run["native_result_metadata"]["completed"] = False
                elif mutation == "prompt":
                    run["runtime_contract"]["prompt_isolation"]["assembled_prompt"] += "SYNTHETIC_ISOLATION_CANARY"
                else:
                    run["runtime_contract"]["prompt_isolation"]["native_tool_names"] = ["terminal"]
                self.assertTrue(validate_report(report, fixture["suite"])["errors"])

    def test_producer_subset_positive_is_diagnostic_and_negative_is_preserved(self):
        for outcome, expected in (("win", "inconclusive"), ("early-failure", "reject")):
            with self.subTest(outcome=outcome):
                fixture = self.fixture(outcome=outcome, case_ids=["held-out-0"])
                self.assertEqual(fixture["report"]["decision"]["decision"], expected)
                result = validate_report(fixture["report"], fixture["suite"])
                self.assertEqual(result["errors"], [])
                self.assertFalse(result["scope"]["full_suite"])
                self.assertFalse(result["positive_decision_sufficient"])

    def test_permitted_retry_preserves_attempts_and_recomputes_final_outcome(self):
        for outcome in ("win", "tie", "early-failure"):
            with self.subTest(outcome=outcome):
                fixture = self.fixture(outcome=outcome, retry_first=True)
                run = fixture["report"]["results"][0]["candidate"]
                self.assertEqual(run["attempt_count"], 2)
                self.assertFalse(run["attempts"][0]["ok"])
                result = validate_report(fixture["report"], fixture["suite"])
                self.assertEqual(result["errors"], [])
                self.assertEqual(result["physical_attempts"], fixture["report"]["run_count"])

    def test_retry_count_transition_and_final_history_mutations_fail(self):
        fixture = self.fixture(outcome="win", retry_first=True)
        for mutation in ("classification", "count", "final", "cleanup", "isolation"):
            with self.subTest(mutation=mutation):
                report = copy.deepcopy(fixture["report"])
                run = report["results"][0]["candidate"]
                if mutation == "classification":
                    run["attempts"][0]["failure"]["kind"] = "tool"
                elif mutation == "count":
                    run["transient_retry_count"] = 0
                elif mutation == "final":
                    run["attempts"][-1]["output"] = "503"
                elif mutation == "cleanup":
                    run["attempts"][0]["runtime_contract"]["cleanup"]["credentials_removed"] = False
                else:
                    run["attempts"][0]["runtime_contract"]["prompt_isolation"]["contamination"] = ["personal context"]
                self.assertTrue(validate_report(report, fixture["suite"])["errors"])

    def test_report_export_workspace_and_version_contradictions_are_operational(self):
        fixture = self.fixture(outcome="win")
        for mutation in ("workspace", "export", "version"):
            with self.subTest(mutation=mutation):
                report = copy.deepcopy(fixture["report"])
                if mutation == "workspace":
                    report["workspace_lifecycle"].update(outcome="cleanup-failed", path="synthetic-retained-workspace", errors=["permission denied"])
                elif mutation == "export":
                    report["report_export"].update(written=False, errors=["permission denied"])
                else:
                    report["version_probes"]["codex"] = {"version": report["agent_version"], "ok": True, "source": "native-cli-version", "errors": ["permission denied"], "cleanup": {"credentials_removed": True, "state_removed": True, "errors": []}}
                result = validate_report(report, fixture["suite"])
                self.assertTrue(result["errors"])
                self.assertTrue(result["operational_errors"])
                self.assertFalse(result["positive_decision_sufficient"])

    def test_recorded_native_tool_request_must_match_producer_plan(self):
        fixture = self.fixture()
        fixture["report"]["results"][0]["judgments"][0]["run"]["route_attestation"]["requested"]["tool_policy"] = "full"
        errors = validate_report(fixture["report"], fixture["suite"])["errors"]
        self.assertTrue(any("requested tool policy mismatch" in error for error in errors))

    def test_all_tie_inconclusive_is_valid_but_mutated_admission_is_not(self):
        fixture = self.fixture()
        report = fixture["report"]
        self.assertEqual(report["decision"]["decision"], "inconclusive")
        valid = validate_report(report, fixture["suite"])
        self.assertEqual(valid["errors"], [])
        self.assertFalse(valid["positive_decision_sufficient"])
        report["decision"]["decision"] = "admit"
        invalid = validate_report(report, fixture["suite"])
        self.assertIn("declared decision differs from recomputed evidence", invalid["errors"])

    def test_evaluator_admission_is_sufficient(self):
        fixture = self.fixture(outcome="win")
        valid = validate_report(fixture["report"], fixture["suite"])
        self.assertEqual(valid["errors"], [])
        self.assertTrue(valid["positive_decision_sufficient"])

    def test_early_negative_does_not_require_positive_trial_minimum(self):
        for version, mode, expected in ((3, "admission", "reject"), (2, "admission", "reject"), (2, "retirement", "retain")):
            with self.subTest(version=version, mode=mode):
                fixture = self.fixture(version=version, outcome="early-failure", mode=mode)
                report = fixture["report"]
                self.assertEqual(report["decision"]["decision"], expected)
                self.assertEqual(report["decision"]["trials"], 1)
                valid = validate_report(report, fixture["suite"])
                self.assertEqual(valid["errors"], [])
                self.assertFalse(valid["positive_decision_sufficient"])

    def test_failed_execution_is_valid_evidence(self):
        fixture = self.fixture(outcome="harness-failure")
        self.assertEqual(fixture["report"]["decision"]["decision"], "harness-failure")
        self.assertEqual(validate_report(fixture["report"], fixture["suite"])["errors"], [])

    def test_full_tiebreak_panel_recomputes_material_disagreement(self):
        for outcome, expected in (("disagreement", "inconclusive"), ("eligibility", "admit")):
            with self.subTest(outcome=outcome):
                fixture = self.fixture(outcome=outcome)
                report = fixture["report"]
                self.assertTrue(all(len(row["judgments"]) == 3 for row in report["results"]))
                self.assertEqual(report["decision"]["decision"], expected)
                self.assertEqual(validate_report(report, fixture["suite"])["errors"], [])
                report["results"][0]["judgments"].pop()
                self.assertTrue(validate_report(report, fixture["suite"])["errors"])

    def test_first_trial_cannot_claim_admission_under_two_trial_plan(self):
        fixture = self.fixture(outcome="win")
        report = fixture["report"]
        report["results"] = report["results"][:len(fixture["suite"]["cases"])]
        report["seeds"] = report["seeds"][:1]
        report["run_count"] = len(report["results"]) * 4
        report["attempt_ledger"] = [entry for entry in report["attempt_ledger"] if entry["trial"] == 0]
        errors = validate_report(report, fixture["suite"])["errors"]
        self.assertIn("declared decision differs from recomputed evidence", errors)
        self.assertIn("evaluation stopped before its declared trial/budget bound", errors)

    def test_frozen_prompt_and_suite_are_bound_to_recorded_identity(self):
        fixture = self.fixture()
        for side in ("candidate", "baseline", "suite"):
            report = copy.deepcopy(fixture["report"])
            if side == "suite":
                report["input_snapshot"]["suite_source"] += "\n"
            else:
                report["input_snapshot"][side]["prompt_text"] += "altered"
            self.assertTrue(validate_report(report, fixture["suite"])["errors"])

    def test_interrupt_with_missing_attempt_output_is_explicitly_incomplete(self):
        fixture = self.fixture(outcome="interrupted")
        report = fixture["report"]
        self.assertEqual(report["status"], "interrupted")
        result = validate_report(report, fixture["suite"])
        self.assertEqual(result["computed_decision"]["decision"], "harness-failure")
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["physical_attempts"], report["run_count"])
        self.assertEqual(result["unpaired_attempts"], 1)
        self.assertFalse(result["evidence_complete"])
        self.assertFalse(result["positive_decision_sufficient"])

    def test_route_flags_cannot_hide_changed_generation_or_judge_model(self):
        fixture = self.fixture(outcome="win")
        for judge in (False, True):
            report = copy.deepcopy(fixture["report"])
            run = report["results"][0]["judgments"][0]["run"] if judge else report["results"][0]["candidate"]
            run["route_attestation"]["observed"]["model"] = "another-model"
            errors = validate_report(report, fixture["suite"])["errors"]
            self.assertTrue(any("observed route mismatch" in error for error in errors), errors)

    def test_outputs_panels_and_coverage_are_recomputed(self):
        fixture = self.fixture(outcome="win")
        for mutation in ("receipt", "order", "judgment", "case", "trial", "stability", "summary"):
            with self.subTest(mutation=mutation):
                report = copy.deepcopy(fixture["report"])
                row = report["results"][0]
                if mutation == "receipt":
                    row["candidate"]["output"] = '{"decision":"go","reason":"wrong"}'
                elif mutation == "order":
                    row["judgments"][1]["order"] = row["judgments"][0]["order"]
                elif mutation == "judgment":
                    row["judgments"][0]["judgment"]["winner"] = "tie"
                elif mutation == "case":
                    report["results"].pop()
                elif mutation == "trial":
                    row["trial"] = 5
                elif mutation == "stability":
                    report["stability"]["required_win_kinds"] = []
                else:
                    report["summary"]["candidate_wins"] = 999
                self.assertTrue(validate_report(report, fixture["suite"])["errors"])

    def test_report_cannot_supply_its_own_suite_or_hide_runs_in_arbitrary_dicts(self):
        fixture = self.fixture()
        report = fixture["report"]
        self.assertTrue(validate_report(report, None)["errors"])
        report["arbitrary"] = copy.deepcopy(report["results"][0]["candidate"])
        result = validate_report(report, fixture["suite"])
        self.assertEqual(result["errors"], [])
        self.assertEqual(len(result["runs"]), report["run_count"])

    def test_incomplete_attempts_are_not_execution_proof(self):
        fixture = self.fixture()
        report = fixture["report"]
        report["results"][0]["candidate"]["attempt_count"] = 2
        report["run_count"] += 1
        errors = validate_report(report, fixture["suite"])["errors"]
        self.assertTrue(any("attempt history count mismatch" in error for error in errors), errors)


if __name__ == "__main__":
    unittest.main()
