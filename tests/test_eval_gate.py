from __future__ import annotations

import importlib.util
import json
import math
import re
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

    def test_retirement_excludes_bilateral_hard_failure(self):
        rule = self.evaluator.DecisionRule(0.05, 0.1, 1, 1)
        rows = [{"score": 1, "hard_pass": {"baseline": False, "candidate": False}}]
        scores = self.evaluator.decision_scores(rows)
        decision = self.evaluator.sequential_decision("retirement", scores, rule, looks=1)
        self.assertEqual(scores, [])
        self.assertEqual(decision["observations"], 0)
        self.assertEqual(decision["decision"], "inconclusive")

        rows[0]["hard_pass"]["baseline"] = True
        self.assertEqual(self.evaluator.decision_scores(rows), [1])

    def test_current_schema_v2_admission_lanes_can_admit_perfect_scores(self):
        lanes = (
            ("evals/capability-curator-current.json", ".evals/run-capability-curator-hermes.sh"),
            ("evals/surface-convergence-current.json", ".evals/run-surface-convergence-hermes.sh"),
        )
        for suite_name, script_name in lanes:
            with self.subTest(suite=suite_name):
                suite = json.loads((REPO / suite_name).read_text(encoding="utf-8"))
                script = (REPO / script_name).read_text(encoding="utf-8")
                min_trials = int(re.search(r"--min-trials (\d+)", script).group(1))
                max_trials = int(re.search(r"--max-trials (\d+)", script).group(1))
                rule = self.evaluator.DecisionRule(0.05, 0.1, min_trials, max_trials)
                perfect = [1.0] * (len(suite["cases"]) * max_trials)
                decision = self.evaluator.sequential_decision(
                    "admission", perfect, rule, looks=max_trials,
                )
                self.assertEqual(decision["decision"], "admit", decision)

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

    def test_transient_provider_failure_retries_within_physical_run_budget(self):
        overloaded = {
            "ok": False,
            "returncode": 1,
            "seconds": 1.0,
            "output": "",
            "stderr": "HTTP 503: provider overloaded",
            "session_ids": [],
            "session_receipt_error": None,
            "route_attestation": {"required": False, "ok": True, "errors": []},
        }
        success = {**overloaded, "ok": True, "returncode": 0, "output": "answer", "stderr": ""}
        budget = self.evaluator.AgentRunBudget(limit=2)
        with mock.patch.object(self.evaluator, "run_agent", side_effect=[overloaded, success]) as run, \
             mock.patch.object(self.evaluator.time, "sleep") as sleep:
            result = self.evaluator.run_agent_with_retry(
                budget, "hermes", "task", Path("."), 1, False,
                transient_retries=2, retry_delay=0.01,
            )
        self.assertTrue(result["ok"])
        self.assertEqual(run.call_count, 2)
        self.assertEqual(budget.used, 2)
        self.assertEqual(result["transient_retry_count"], 1)
        self.assertEqual(result["attempt_count"], 2)
        sleep.assert_called_once_with(0.01)

    def test_explicit_hermes_provider_response_timeout_is_transient(self):
        result = {
            "ok": False,
            "returncode": 1,
            "output": (
                "API call failed after 3 retries: Non-streaming API call timed out "
                "after 90s with no response (threshold: 90s)"
            ),
            "stderr": "session_id: 20260902_192444_e9e49a",
        }

        self.assertTrue(self.evaluator.transient_provider_failure(result))

    def test_nontransient_agent_failure_is_not_retried(self):
        failure = {
            "ok": False,
            "returncode": 1,
            "seconds": 0.1,
            "output": "",
            "stderr": "invalid output schema",
            "session_ids": [],
            "session_receipt_error": None,
            "route_attestation": {"required": False, "ok": True, "errors": []},
        }
        budget = self.evaluator.AgentRunBudget(limit=3)
        with mock.patch.object(self.evaluator, "run_agent", return_value=failure) as run:
            result = self.evaluator.run_agent_with_retry(
                budget, "codex", "task", Path("."), 1, False,
                transient_retries=2, retry_delay=0,
            )
        self.assertFalse(result["ok"])
        self.assertEqual(run.call_count, 1)
        self.assertEqual(budget.used, 1)
        self.assertEqual(result["transient_retry_count"], 0)

    def test_transient_retry_never_exceeds_physical_run_budget(self):
        overloaded = {
            "ok": False,
            "returncode": 1,
            "seconds": 1.0,
            "output": "",
            "stderr": "rate_limit_exceeded (429)",
            "session_ids": [],
            "session_receipt_error": None,
            "route_attestation": {"required": False, "ok": True, "errors": []},
        }
        budget = self.evaluator.AgentRunBudget(limit=1)
        with mock.patch.object(self.evaluator, "run_agent", return_value=overloaded) as run:
            result = self.evaluator.run_agent_with_retry(
                budget, "hermes", "task", Path("."), 1, False,
                transient_retries=2, retry_delay=0,
            )
        self.assertFalse(result["ok"])
        self.assertEqual(run.call_count, 1)
        self.assertEqual(budget.used, 1)
        self.assertTrue(result["run_budget_exhausted"])

    def test_hermes_no_tools_uses_inline_prompt_and_explicit_none_toolset(self):
        process = mock.Mock(returncode=0)
        process.communicate.return_value = ("answer", "session_id: 20260814_111111_abcd1234")
        lifecycle = mock.Mock()
        lifecycle.register_receipt.return_value = (["20260814_111111_abcd1234"], None)
        with tempfile.TemporaryDirectory() as temp, \
             mock.patch.object(self.evaluator.shutil, "which", return_value="hermes"), \
             mock.patch.object(self.evaluator.subprocess, "Popen", return_value=process) as popen:
            result = self.evaluator.run_agent(
                "hermes", "INLINE_SENTINEL", Path(temp), 1, False,
                "model", "provider", "low", "none", lifecycle,
            )
            self.assertFalse((Path(temp) / "eval-prompt.txt").exists())
        command = popen.call_args.args[0]
        self.assertTrue(result["ok"])
        self.assertEqual(command[command.index("-q") + 1], "INLINE_SENTINEL")
        self.assertIn("--toolsets", command)
        self.assertEqual(command[command.index("--toolsets") + 1], "none")

    def test_codex_child_receives_reasoning_override(self):
        process = mock.Mock(returncode=0)
        process.communicate.return_value = ("answer", "")
        with tempfile.TemporaryDirectory() as temp, \
             mock.patch.object(self.evaluator.shutil, "which", return_value="codex"), \
             mock.patch.object(self.evaluator.subprocess, "Popen", return_value=process) as popen:
            result = self.evaluator.run_agent(
                "codex", "task", Path(temp), 1, False,
                "model", "provider", "medium", "none",
            )
        command = popen.call_args.args[0]
        self.assertIn("-c", command)
        self.assertIn('model_reasoning_effort="medium"', command)
        self.assertTrue(result["ok"])

    def test_v3_suite_requires_receipt_contract_and_expected_receipts(self):
        suite = {
            "schema_version": 3,
            "cases": [
                {"id": "representative", "kind": "representative", "prompt": "x"},
                {"id": "near", "kind": "near-miss", "prompt": "x"},
                {"id": "adversarial", "kind": "adversarial", "prompt": "x"},
                {"id": "held", "kind": "held-out", "prompt": "x"},
            ],
        }
        with self.assertRaisesRegex(ValueError, "receipt_schema"):
            self.evaluator.validate_suite(suite)
        suite["receipt_schema"] = {
            "type": "object",
            "required": ["decision"],
            "properties": {"decision": {"type": "string", "enum": ["hold", "publish"]}},
            "additionalProperties": False,
        }
        suite["stability"] = {"trials": 2, "required_win_kinds": ["representative", "held-out"]}
        with self.assertRaisesRegex(ValueError, "expected_receipt"):
            self.evaluator.validate_suite(suite)

    def test_v3_receipt_checks_schema_and_expected_values(self):
        schema = {
            "type": "object",
            "required": ["decision", "writer", "evidence"],
            "properties": {
                "decision": {"type": "string", "enum": ["hold", "publish"]},
                "writer": {"type": "string", "enum": ["single", "conflict"]},
                "evidence": {
                    "type": "object",
                    "required": ["clean_environment"],
                    "properties": {"clean_environment": {"type": "string", "enum": ["required", "not-required"]}},
                    "additionalProperties": False,
                },
            },
            "additionalProperties": False,
        }
        case = {"expected_receipt": {"decision": "hold", "writer": "single", "evidence.clean_environment": "required"}}
        passed = self.evaluator.structured_receipt_check(
            case,
            '{"decision":"hold","writer":"single","evidence":{"clean_environment":"required"}}',
            schema,
        )
        self.assertTrue(passed["pass"])
        self.assertEqual(passed["receipt"]["decision"], "hold")
        failed = self.evaluator.structured_receipt_check(
            case,
            '{"decision":"publish","writer":"single","evidence":{}}',
            schema,
        )
        self.assertFalse(failed["pass"])
        self.assertTrue(any("decision" in reason for reason in failed["reasons"]))
        self.assertTrue(any("evidence.clean_environment" in reason for reason in failed["reasons"]))

    def test_codex_structured_run_uses_native_schema_and_observed_attestation(self):
        process = mock.Mock(returncode=0)
        process.communicate.return_value = (
            '{"decision":"hold"}',
            "model: gpt-5.6-sol\nprovider: openai\nreasoning effort: low\n",
        )
        schema = {"type": "object", "required": ["decision"], "properties": {"decision": {"type": "string"}}}
        with tempfile.TemporaryDirectory() as temp, \
             mock.patch.object(self.evaluator.shutil, "which", return_value="codex"), \
             mock.patch.object(self.evaluator.subprocess, "Popen", return_value=process) as popen:
            result = self.evaluator.run_agent(
                "codex", "task", Path(temp), 1, False,
                "gpt-5.6-sol", "openai-codex", "low", "none",
                output_schema=schema,
                require_attestation=True,
            )
        command = popen.call_args.args[0]
        self.assertIn("--output-schema", command)
        self.assertTrue(result["ok"])
        self.assertEqual(result["route_attestation"]["observed"]["reasoning"], "low")
        self.assertEqual(result["route_attestation"]["observed"]["model"], "gpt-5.6-sol")

    def test_codex_route_attestation_mismatch_fails_the_run(self):
        process = mock.Mock(returncode=0)
        process.communicate.return_value = (
            "answer",
            "model: gpt-5.6-sol\nprovider: openai\nreasoning effort: none\n",
        )
        with tempfile.TemporaryDirectory() as temp, \
             mock.patch.object(self.evaluator.shutil, "which", return_value="codex"), \
             mock.patch.object(self.evaluator.subprocess, "Popen", return_value=process):
            result = self.evaluator.run_agent(
                "codex", "task", Path(temp), 1, False,
                "gpt-5.6-sol", "openai-codex", "low", "none",
                require_attestation=True,
            )
        self.assertFalse(result["ok"])
        self.assertFalse(result["route_attestation"]["ok"])
        self.assertIn("reasoning", result["route_attestation"]["errors"][0])

    def test_hermes_route_attestation_uses_redacted_export_and_discards_payload(self):
        exported = {
            "id": "eval-session-1",
            "model": "gpt-5.6-sol",
            "billing_provider": "openai-codex",
            "model_config": json.dumps({"reasoning_config": {"enabled": True, "effort": "ultra"}}),
            "system_prompt": "SECRET-THAT-MUST-NOT-BE-RETAINED",
            "messages": [{"content": "private prompt"}],
        }
        completed = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=json.dumps(exported) + "\n", stderr=""
        )
        with mock.patch.object(self.evaluator.subprocess, "run", return_value=completed) as run:
            receipt = self.evaluator.hermes_route_attestation(
                "hermes", ["eval-session-1"], "gpt-5.6-sol", "openai-codex", "ultra", "none"
            )
        command = run.call_args.args[0]
        self.assertIn("--redact", command)
        self.assertIn("--session-id", command)
        self.assertTrue(receipt["ok"])
        self.assertEqual(receipt["observed"], {
            "model": "gpt-5.6-sol",
            "provider": "openai-codex",
            "reasoning": "ultra",
            "tool_calls_count": 0,
        })
        self.assertNotIn("SECRET-THAT-MUST-NOT-BE-RETAINED", json.dumps(receipt))
        self.assertNotIn("private prompt", json.dumps(receipt))

    def test_hermes_route_attestation_fails_closed_on_mismatch_or_ambiguous_session(self):
        exported = {
            "id": "eval-session-1",
            "model": "gpt-5.6-sol",
            "billing_provider": "openai-codex",
            "model_config": json.dumps({"reasoning_config": {"effort": "medium"}}),
            "tool_calls_count": 1,
        }
        completed = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=json.dumps(exported) + "\n", stderr=""
        )
        with mock.patch.object(self.evaluator.subprocess, "run", return_value=completed) as run:
            mismatch = self.evaluator.hermes_route_attestation(
                "hermes", ["eval-session-1"], "gpt-5.6-sol", "openai-codex", "ultra", "none"
            )
        self.assertFalse(mismatch["ok"])
        self.assertTrue(any("reasoning" in error for error in mismatch["errors"]))
        ambiguous = self.evaluator.hermes_route_attestation(
            "hermes", ["one", "two"], "gpt-5.6-sol", "openai-codex", "ultra", "none"
        )
        self.assertFalse(ambiguous["ok"])
        self.assertIn("exactly one", ambiguous["errors"][0])
        self.assertTrue(any("tool calls" in error for error in mismatch["errors"]))
        run.assert_called_once()

    def test_v3_route_supports_attested_hermes_generation_with_codex_judges(self):
        self.assertTrue(self.evaluator.v3_route_supported("hermes", "codex"))
        self.assertTrue(self.evaluator.v3_route_supported("codex", "codex"))
        self.assertFalse(self.evaluator.v3_route_supported("hermes", "hermes"))

    def test_v3_judgment_requires_every_semantic_criterion(self):
        judgment = {
            "a": {"criteria": [{"id": "scope", "pass": True, "evidence": "A1"}]},
            "b": {"criteria": [{"id": "scope", "pass": True, "evidence": "B1"}]},
            "winner": "A",
            "reason": "A is clearer",
        }
        winner, mapped = self.evaluator.map_v3_judgment(judgment, ["baseline", "candidate"], ["scope"])
        self.assertEqual(winner, "baseline")
        self.assertTrue(mapped["candidate"]["scope"])
        with self.assertRaisesRegex(ValueError, "missing semantic criterion"):
            self.evaluator.map_v3_judgment(judgment, ["baseline", "candidate"], ["scope", "risk"])

    def test_v3_disagreement_includes_criterion_passes(self):
        winners = ["candidate", "candidate"]
        passes = [
            {"baseline": {"scope": True}, "candidate": {"scope": True}},
            {"baseline": {"scope": True}, "candidate": {"scope": False}},
        ]
        disagreement = self.evaluator.v3_disagreement(winners, passes)
        self.assertFalse(disagreement["winner"])
        self.assertTrue(disagreement["criteria"])
        self.assertIn("candidate.scope", disagreement["details"])

    def test_v3_stability_admits_only_clean_complete_runs(self):
        contract = {"trials": 2, "required_win_kinds": ["representative", "held-out"]}
        results = [
            {"trial": 0, "kind": "representative", "winner": "candidate", "candidate_receipt_pass": True, "judge_disagreement": False},
            {"trial": 0, "kind": "held-out", "winner": "tie", "candidate_receipt_pass": True, "judge_disagreement": False},
            {"trial": 1, "kind": "representative", "winner": "tie", "candidate_receipt_pass": True, "judge_disagreement": False},
            {"trial": 1, "kind": "held-out", "winner": "candidate", "candidate_receipt_pass": True, "judge_disagreement": False},
        ]
        admitted = self.evaluator.v3_stability_decision(results, contract, trials_run=2)
        self.assertEqual(admitted["decision"], "admit")
        self.assertEqual(admitted["basis"], "bounded-stability")
        unstable = [dict(results[0], judge_disagreement=True), *results[1:]]
        blocked = self.evaluator.v3_stability_decision(unstable, contract, trials_run=2)
        self.assertEqual(blocked["decision"], "inconclusive")
        failed = [dict(results[0], candidate_receipt_pass=False), *results[1:]]
        rejected = self.evaluator.v3_stability_decision(failed, contract, trials_run=2)
        self.assertEqual(rejected["decision"], "reject")

        semantic_failure = [dict(results[0], candidate_hard_pass=False), *results[1:]]
        rejected = self.evaluator.v3_stability_decision(semantic_failure, contract, trials_run=2)
        self.assertEqual(rejected["decision"], "reject")
        self.assertEqual(rejected["candidate_hard_failures"], 1)

    def test_v3_third_judge_resolves_two_judge_order_variance(self):
        criteria = ["quality"]
        passes = [
            {"baseline": {"quality": True}, "candidate": {"quality": True}},
            {"baseline": {"quality": True}, "candidate": {"quality": True}},
            {"baseline": {"quality": True}, "candidate": {"quality": True}},
        ]
        resolved = self.evaluator.resolve_v3_judgments(
            ["tie", "candidate", "candidate"], passes, criteria,
        )
        self.assertEqual(resolved["winner"], "candidate")
        self.assertFalse(resolved["unresolved"]["winner"])
        self.assertFalse(resolved["unresolved"]["criteria"])

        unresolved = self.evaluator.resolve_v3_judgments(
            ["tie", "candidate", "baseline"], passes, criteria,
        )
        self.assertTrue(unresolved["unresolved"]["winner"])

    def test_v3_comparative_winner_cannot_override_contract_eligibility(self):
        criteria = ["scope"]
        resolution = {
            "winner": "baseline",
            "passes": {
                "baseline": {"scope": True},
                "candidate": {"scope": True},
            },
        }
        winner, hard_pass = self.evaluator.v3_effective_result(
            resolution,
            {"baseline": False, "candidate": True},
            criteria,
        )
        self.assertEqual(winner, "candidate")
        self.assertEqual(hard_pass, {"baseline": False, "candidate": True})

        resolution["winner"] = "candidate"
        resolution["passes"]["candidate"]["scope"] = False
        winner, hard_pass = self.evaluator.v3_effective_result(
            resolution,
            {"baseline": True, "candidate": True},
            criteria,
        )
        self.assertEqual(winner, "baseline")
        self.assertEqual(hard_pass, {"baseline": True, "candidate": False})

    def test_v3_main_uses_receipts_judges_and_bounded_stability_together(self):
        receipt_schema = {
            "type": "object",
            "required": ["decision", "rationale"],
            "properties": {
                "decision": {"type": "string", "enum": ["publish"]},
                "rationale": {"type": "array", "minItems": 1, "items": {"type": "string"}},
            },
            "additionalProperties": False,
        }
        suite = {
            "schema_version": 3,
            "name": "v3-integration",
            "claim": "candidate makes better decisions",
            "receipt_schema": receipt_schema,
            "stability": {"trials": 1, "required_win_kinds": ["representative", "held-out"]},
            "cases": [
                {
                    "id": kind,
                    "kind": kind,
                    "prompt": f"Decide the {kind} case.",
                    "expected_receipt": {"decision": "publish"},
                    "semantic_criteria": [{"id": "quality", "text": "The rationale is causal and scoped."}],
                }
                for kind in ("representative", "near-miss", "adversarial", "held-out")
            ],
        }

        judge_calls = 0
        generation_prompts = []

        def fake_run(_agent, prompt, *_args, output_schema=None, require_attestation=False, **_kwargs):
            nonlocal judge_calls
            self.assertIsNotNone(output_schema)
            self.assertTrue(require_attestation)
            if prompt.startswith("Judge two anonymous"):
                judge_calls += 1
                a_block = prompt.split("RECEIPT A\n", 1)[1].split("\n\nRECEIPT B", 1)[0]
                candidate_winner = "A" if "candidate" in a_block else "B"
                winner = "tie" if judge_calls % 3 == 1 else candidate_winner
                output = json.dumps({
                    "a": {"criteria": [{"id": "quality", "pass": True, "evidence": "causal"}]},
                    "b": {"criteria": [{"id": "quality", "pass": True, "evidence": "causal"}]},
                    "winner": winner,
                    "reason": "candidate is more explicit",
                })
            else:
                generation_prompts.append(prompt)
            if not prompt.startswith("Judge two anonymous") and "candidate" in prompt:
                output = '{"decision":"publish","rationale":["candidate"]}'
            elif not prompt.startswith("Judge two anonymous"):
                output = '{"decision":"publish","rationale":["baseline"]}'
            return {
                "ok": True,
                "returncode": 0,
                "seconds": 0.01,
                "output": output,
                "stderr": "",
                "session_ids": [],
                "session_receipt_error": None,
                "route_attestation": {"required": True, "ok": True, "errors": []},
            }

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            suite_path = root / "suite.json"
            candidate = root / "candidate.md"
            baseline = root / "baseline.md"
            report = root / "report.json"
            suite_path.write_text(json.dumps(suite), encoding="utf-8")
            candidate.write_text("candidate", encoding="utf-8")
            baseline.write_text("baseline", encoding="utf-8")
            argv = [
                "eval.py", str(suite_path), "--candidate", str(candidate),
                "--baseline-candidate", str(baseline), "--agent", "codex",
                "--judge-agent", "codex", "--model", "gpt-5.6-sol",
                "--provider", "openai-codex", "--reasoning", "low",
                "--judge-model", "gpt-5.6-sol", "--judge-provider", "openai-codex",
                "--min-trials", "1", "--max-trials", "1", "--max-agent-runs", "20",
                "--equivalence-group", "test", "--rollback", "restore baseline",
                "--out", str(report),
            ]
            with mock.patch.object(self.evaluator, "run_agent", side_effect=fake_run), \
                 mock.patch.object(self.evaluator, "command_version", return_value="test"), \
                 mock.patch.object(self.evaluator.HermesSessionLifecycle, "cleanup", return_value={"created": [], "deleted": [], "remaining": []}), \
                 mock.patch("sys.argv", argv):
                self.assertEqual(self.evaluator.main(), 0)
            payload = json.loads(report.read_text(encoding="utf-8"))
        self.assertEqual(payload["schema_version"], 3)
        self.assertEqual(payload["decision"]["decision"], "admit")
        self.assertEqual(payload["decision"]["basis"], "bounded-stability")
        self.assertEqual(payload["summary"]["candidate_receipt_failures"], 0)
        self.assertEqual(payload["summary"]["candidate_losses"], 0)
        self.assertEqual(payload["summary"]["judge_disagreements"], 0)
        self.assertEqual(payload["summary"]["raw_judge_disagreements"], 4)
        self.assertEqual(payload["run_count"], 20)
        self.assertEqual(len(generation_prompts), 8)
        self.assertTrue(all("<INSTRUCTION_ARTIFACT>" in prompt for prompt in generation_prompts))
        self.assertTrue(all("<BASELINE_INSTRUCTIONS>" not in prompt for prompt in generation_prompts))
        self.assertTrue(all("<CANDIDATE_SKILL>" not in prompt for prompt in generation_prompts))
        self.assertEqual(payload["effective_stack"]["prompt_assembly"], "isolated-anonymous-artifact-v3")

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
        hashes = {"codex": "c" * 64, "hermes": "d" * 64}
        result = self.gate.aggregate(
            reports, ["codex", "hermes"], "admission", "restore previous artifacts", hashes,
        )
        self.assertEqual(result["decision"], "reject")
        self.assertEqual(result["host_decisions"]["hermes"], "reject")
        self.assertEqual(result["report_hash_inputs"], hashes)

    def test_missing_required_host_is_inconclusive(self):
        report = {
            "schema_version": 2,
            "suite": "x",
            "agent": "codex",
            "artifacts": {"candidate_sha256": "c", "suite_sha256": "s", "harness_sha256": "h"},
            "effective_stack": {"equivalence_group": "g"},
            "decision": {"decision": "admit"},
        }
        result = self.gate.aggregate(
            [report], ["codex", "hermes"], "admission", "restore", {"codex": "c" * 64},
        )
        self.assertEqual(result["decision"], "inconclusive")
        self.assertEqual(result["missing_hosts"], ["hermes"])

    def test_harness_failure_is_inconclusive_not_candidate_rejection(self):
        base = {
            "schema_version": 2,
            "suite": "x",
            "artifacts": {"candidate_sha256": "c", "suite_sha256": "s", "harness_sha256": "h"},
            "effective_stack": {"equivalence_group": "g"},
            "decision": {"decision": "admit"},
        }
        reports = [
            dict(base, agent="codex"),
            dict(base, agent="hermes", decision={"decision": "harness-failure"}),
        ]
        hashes = {"codex": "c" * 64, "hermes": "d" * 64}

        result = self.gate.aggregate(
            reports, ["codex", "hermes"], "admission", "restore", hashes,
        )

        self.assertEqual(result["decision"], "inconclusive")
        self.assertEqual(result["regression_hosts"], [])
        self.assertEqual(result["inconclusive_hosts"], ["hermes"])

    def test_missing_or_malformed_report_hash_is_inconclusive(self):
        report = {
            "schema_version": 2,
            "suite": "x",
            "agent": "codex",
            "artifacts": {"candidate_sha256": "c", "suite_sha256": "s", "harness_sha256": "h"},
            "effective_stack": {"equivalence_group": "g"},
            "decision": {"decision": "admit"},
        }
        result = self.gate.aggregate([report], ["codex"], "admission", "restore", {"codex": "not-a-hash"})
        self.assertEqual(result["decision"], "inconclusive")
        self.assertEqual(result["artifact_mismatches"], ["codex:report_sha256"])


if __name__ == "__main__":
    unittest.main()
