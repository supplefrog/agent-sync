"""Pure consistency checks for recorded evaluation evidence, not execution proof.

The supplied suite is the decision oracle. Decision and receipt semantics belong
to eval.py; this module reuses them rather than maintaining a second rulebook.
Only documented result/run locations are traversed. Missing attempt evidence is
reported explicitly, including for interrupted or otherwise truthful failures.
"""
from __future__ import annotations

import importlib.util
import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any

_spec = importlib.util.spec_from_file_location("_evidence_evaluator", Path(__file__).with_name("eval.py"))
assert _spec and _spec.loader
evaluator = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(evaluator)
import evaluation_runtime as runtime

ARTIFACT_KEYS = ("candidate_sha256", "baseline_candidate_sha256", "suite_sha256", "harness_sha256", "candidate_prompt_sha256", "baseline_prompt_sha256")
STACK_KEYS = (
    "model", "provider", "reasoning", "tool_policy", "prompt_assembly",
    "context_policy", "equivalence_group", "judge_model", "judge_provider",
    "judge_reasoning", "judge_tool_policy", "judge_panel", "runtime_lane",
)
SIDES = ("baseline", "candidate")


def execution_ok(run: dict[str, Any]) -> bool:
    """Historical reports used overall ok; current reports separate cleanup."""
    return run.get("execution_ok", run.get("ok")) is True


def validate_report(report: dict[str, Any], suite: dict[str, Any] | None) -> dict[str, Any]:
    """Recompute integrity and decision sufficiency without reading report paths.

Callers bind supplied suite/artifact bytes to hashes independently. Successful
validation means the recorded evidence is internally consistent, not authentic.
"""
    result: dict[str, Any] = {
        "errors": [], "computed_decision": None, "computed_summary": {},
        "runs": [], "physical_attempts": 0, "positive_decision_sufficient": False,
        "operational_errors": [], "evidence_complete": False,
        "host_run_counts": {"codex": 0, "hermes": 0}, "scope": None,
        "limitations": [], "attempt_evidence_complete": True,
        "unpaired_attempts": 0,
    }
    errors = result["errors"]

    def require(condition: bool, message: str) -> None:
        if not condition:
            errors.append(message)

    def same(actual: Any, expected: Any, message: str) -> None:
        def matches(left: Any, right: Any) -> bool:
            if isinstance(right, bool):
                return type(left) is bool and left == right
            if isinstance(right, dict):
                return isinstance(left, dict) and left.keys() == right.keys() and all(matches(left[key], value) for key, value in right.items())
            if isinstance(right, list):
                return isinstance(left, list) and len(left) == len(right) and all(matches(a, b) for a, b in zip(left, right))
            if type(right) in (int, float):
                return type(left) in (int, float) and left == right
            return left == right
        require(matches(actual, expected), message)

    if not isinstance(report, dict):
        errors.append("report must be an object")
        return result
    if not isinstance(suite, dict):
        errors.append("actual suite is required for evidence recomputation")
        return result
    try:
        evaluator.validate_suite(suite)
    except (ValueError, TypeError, KeyError, AttributeError) as exc:
        errors.append(f"invalid suite: {exc}")
        return result
    try:
        schema = report.get("schema_version")
        require(schema in (2, 3), "unsupported report schema")
        same(schema, evaluator.suite_report_version(suite), "suite/report schema mismatch")
        same(report.get("suite"), suite.get("name"), "suite name mismatch")
        mode = report.get("decision_mode")
        require(mode in ("admission", "retirement"), "invalid decision mode")
        require(schema != 3 or mode == "admission", "v3 supports admission only")
        status = report.get("status")
        require(status in ("complete", "failed", "interrupted"), "report has no final execution status")
        abnormal = status in ("failed", "interrupted")
        if abnormal:
            result["operational_errors"].append(f"evaluation {status} before normal completion")
        harness_integrity = report.get("harness_integrity", {})
        if abnormal and harness_integrity.get("unchanged") is not False:
            require(bool(report.get("failure" if status == "failed" else "interruption")), "missing execution failure detail")
        for key in ARTIFACT_KEYS:
            require(bool(re.fullmatch(r"[0-9a-f]{64}", str(report.get("artifacts", {}).get(key, "")))), f"missing or malformed artifact: {key}")
        artifacts = report.get("artifacts", {})
        snapshot = report["input_snapshot"]
        suite_source = snapshot["suite_source"]
        same(evaluator.extract_json(suite_source), suite, "frozen suite differs from supplied suite")
        same(hashlib.sha256(suite_source.encode("utf-8")).hexdigest(), artifacts.get("suite_sha256"), "frozen suite hash mismatch")
        for side, package_key, prompt_key in (("candidate", "candidate_sha256", "candidate_prompt_sha256"), ("baseline", "baseline_candidate_sha256", "baseline_prompt_sha256")):
            source = snapshot.get(side)
            format_key = "candidate_identity_format" if side == "candidate" else "baseline_candidate_identity_format"
            if source is None and side == "baseline" and report.get("baseline_candidate") is None:
                same(artifacts.get(package_key), hashlib.sha256(b"").hexdigest(), "empty baseline hash mismatch")
                same(artifacts.get(prompt_key), hashlib.sha256(b"").hexdigest(), "empty baseline prompt hash mismatch")
                if format_key in artifacts:
                    same(artifacts[format_key], "empty-input-sha256", "empty baseline identity format mismatch")
                continue
            same(source.get("projection"), "inline-linked-text-only", f"{side}: unknown prompt projection")
            same(source.get("package_sha256"), artifacts.get(package_key), f"{side}: frozen package hash mismatch")
            same(source.get("prompt_sha256"), artifacts.get(prompt_key), f"{side}: frozen prompt hash mismatch")
            same(hashlib.sha256(source["prompt_text"].encode("utf-8")).hexdigest(), artifacts.get(prompt_key), f"{side}: prompt text hash mismatch")
            if format_key in artifacts:
                same(artifacts[format_key], source.get("identity_format"), f"{side}: source identity format mismatch")
        require(type(harness_integrity.get("unchanged")) is bool, "missing harness integrity result")
        if harness_integrity.get("unchanged"):
            same(harness_integrity.get("final_sha256"), artifacts.get("harness_sha256"), "harness integrity hash mismatch")
        else:
            require(status == "failed", "changed or unverified harness is not recorded as failed")
            result["operational_errors"].append("harness changed or final integrity check failed")
        stack = report["effective_stack"]
        for key in STACK_KEYS:
            if key == "runtime_lane" and stack.get(key) is None:
                continue
            require(isinstance(stack.get(key), str) and bool(stack[key].strip()), f"missing effective stack: {key}")
        require(stack.get("route_attestation_required") is True, "route attestation not required")
        require(stack.get("tool_policy") in ("none", "safe", "full"), "invalid generation tool policy")
        runtime_lane = stack.get("runtime_lane")
        require(runtime_lane in (None, "inline-text-no-tools-v1"), "unsupported producer runtime lane")
        judge_policy = "none" if runtime_lane == "inline-text-no-tools-v1" else "safe"
        same(stack.get("judge_tool_policy"), judge_policy, "judge tool policy differs from producer plan")
        if runtime_lane and status == "complete":
            same(stack.get("tool_policy"), "none", "generation tool policy differs from no-tools producer plan")
        same(stack.get("judge_reasoning"), stack.get("reasoning"), "judge reasoning differs from producer plan")
        require(report.get("agent") in ("codex", "hermes"), "invalid generation host")
        require(report.get("judge_agent") in ("codex", "hermes"), "invalid judge host")
        require(schema != 3 or evaluator.v3_route_supported(report.get("agent"), report.get("judge_agent")), "unsupported v3 generation/judge route")
        same(stack.get("judge_panel"), "two-order-swapped-plus-bounded-tiebreak" if schema == 3 else "two-order-swapped", "judge panel mismatch")

        cases = suite["cases"]
        case_ids = [case["id"] for case in cases]
        require(all(isinstance(case_id, str) and case_id for case_id in case_ids), "invalid suite case identity")
        same(report.get("suite_cases"), [{"id": case["id"], "kind": case.get("kind")} for case in cases], "suite case declaration mismatch")
        selected = report.get("selected_case_ids")
        require(isinstance(selected, list) and bool(selected), "no selected cases")
        if not isinstance(selected, list) or not selected:
            return result
        require(len(set(selected)) == len(selected) and all(case_id in case_ids for case_id in selected), "unknown or duplicated selected case")
        same(selected, [case_id for case_id in case_ids if case_id in selected], "selected cases are out of suite order")
        selected_cases = {case["id"]: case for case in cases if case["id"] in selected}
        full_suite = selected == case_ids
        result["scope"] = evaluator.evaluation_scope(suite, selected)
        result["scope"]["runtime_lane"] = runtime_lane or "historical-unspecified"
        if not runtime_lane:
            result["scope"]["evaluated_projection"] = "historical-unspecified"
            result["scope"]["package_behavior_exercised"] = None
        if "scope" in report:
            same(report["scope"], result["scope"], "recorded evaluation scope mismatch")

        rule_data = report["decision_rule"]
        for key in ("min_trials", "max_trials", "max_agent_runs"):
            require(type(rule_data.get(key)) is int and rule_data[key] > 0, f"invalid decision rule: {key}")
        low, high, cap = (rule_data[key] for key in ("min_trials", "max_trials", "max_agent_runs"))
        require(1 <= low <= high, "invalid trial bounds")
        require(cap >= len(selected) * (5 if schema == 3 else 4) * low, "run budget is smaller than the declared minimum trial plan")
        require(type(rule_data.get("alpha")) in (int, float) and math.isfinite(rule_data["alpha"]) and 0 < rule_data["alpha"] < 1, "invalid decision rule: alpha")
        require(type(rule_data.get("margin")) in (int, float) and math.isfinite(rule_data["margin"]) and 0 <= rule_data["margin"] < 1, "invalid decision rule: margin")
        same(rule_data.get("score_range"), [-1, 1], "score range mismatch")
        if schema == 3:
            same(report.get("stability"), suite["stability"], "stability contract mismatch")
            require(low == high == suite["stability"]["trials"], "trial plan differs from suite stability contract")
        rule = evaluator.DecisionRule(rule_data["alpha"], rule_data["margin"], low, high)

        rows = report.get("results")
        if not isinstance(rows, list):
            errors.append("results must be an array")
            return result
        require(bool(rows) or abnormal, "no observations")
        require(len(rows) <= len(selected) * high, "trial coverage exceeds declared plan")
        require(abnormal or len(rows) % len(selected) == 0, "incomplete trial coverage")
        seeds = report.get("seeds")
        require(isinstance(seeds, list) and all(type(seed) is int for seed in seeds), "invalid trial seeds")
        if not isinstance(seeds, list):
            return result
        expected_ledger: list[dict[str, Any]] = []

        def check_observation(run: dict[str, Any], label: str, judge: bool = False) -> None:
            require(type(run.get("ok")) is bool, f"{label}: missing run outcome")
            require(isinstance(run.get("output"), str), f"{label}: missing output evidence")
            att = run.get("route_attestation", {})
            require(att.get("required") is True or (not run.get("ok") and run.get("run_budget_exhausted")), f"{label}: route attestation not required")
            observed, requested = att.get("observed", {}), att.get("requested", {})
            host = report.get("judge_agent" if judge else "agent")
            route_errors = []
            for key in ("model", "provider", "reasoning"):
                expected = stack.get("judge_" + key if judge else key)
                accepted = {expected}
                if key == "provider" and host == "codex" and expected == "openai-codex":
                    accepted.add("openai")
                if observed.get(key) not in accepted or observed.get(key) is None:
                    route_errors.append(key)
                if requested:
                    same(requested.get(key), expected, f"{label}: requested {key} mismatch")
            policy = stack.get("judge_tool_policy" if judge else "tool_policy")
            if requested and "tool_policy" in requested:
                same(requested["tool_policy"], policy, f"{label}: requested tool policy mismatch")
            if policy == "none" and (host == "hermes" or runtime_lane) and observed.get("tool_calls_count") != 0:
                route_errors.append("tool_calls_count")
            if att.get("ok") is True:
                require(not route_errors, f"{label}: observed route mismatch: {', '.join(route_errors)}")
                require(not att.get("errors"), f"{label}: successful attestation contains errors")
            else:
                require(not execution_ok(run), f"{label}: successful execution has failed route attestation")
            if execution_ok(run):
                same(run.get("returncode"), 0, f"{label}: successful execution has nonzero return code")
            if run.get("evidence_incomplete") is True:
                require(not execution_ok(run) and run.get("ok") is False, f"{label}: incomplete attempt claims success")
                result["attempt_evidence_complete"] = False
                result["limitations"].append("an invocation ended without complete native output/route evidence")
                if run.get("operational_ok") is not True:
                    result["operational_errors"].append(f"{label}: incomplete invocation has unverified cleanup/operation state")
                return
            if not runtime_lane:
                require(not run.get("runtime_contract") and "native_events" not in run and "native_result_metadata" not in run, f"{label}: native evidence has no declared runtime lane")
                return
            if run.get("run_budget_exhausted") and run.get("attempt_count") == 0:
                return
            contract = run.get("runtime_contract")
            require(isinstance(contract, dict), f"{label}: current runtime evidence missing")
            if not isinstance(contract, dict):
                return
            for key, expected in {
                "lane": runtime_lane, "tool_policy": "none", "credential_owner": host,
                "credentials_outside_fixture": True, "personal_config_copied": False,
                "global_session_cleanup_authority": False, "cross_host_credential_fallback": False,
                "tool_schema_absence_verified": False,
            }.items():
                same(contract.get(key), expected, f"{label}: runtime contract mismatch: {key}")
            same(run.get("session_ids"), [], f"{label}: native lane claims global session ownership")
            same(run.get("session_receipt_error"), None, f"{label}: native lane uses global session receipts")
            cleanup = contract.get("cleanup", {})
            for key in ("credentials_removed", "state_removed"):
                require(type(cleanup.get(key)) is bool, f"{label}: missing native cleanup field: {key}")
            require(isinstance(cleanup.get("errors"), list), f"{label}: missing native cleanup errors")
            clean = cleanup.get("credentials_removed") is True and cleanup.get("state_removed") is True and cleanup.get("errors") == []
            if not clean:
                result["operational_errors"].append(f"{label}: native credential/state cleanup failed or is unverified")
                require(run.get("ok") is not True, f"{label}: successful run contradicts native cleanup failure")
            if "operational_ok" in run:
                same(run["operational_ok"], clean, f"{label}: operational outcome contradicts cleanup")
            if "execution_ok" in run:
                require(type(run["execution_ok"]) is bool, f"{label}: malformed execution outcome")
                same(run.get("ok"), run["execution_ok"] and clean, f"{label}: overall outcome contradicts execution/operation outcomes")
            controls = contract.get("controls", {})
            isolation = contract.get("prompt_isolation", {})
            observation = contract.get("tool_observation", {})
            if isolation.get("verified") is True:
                same(isolation.get("contamination"), [], f"{label}: verified isolation contains contamination")
                same(isolation.get("tool_schema_absence_verified"), False, f"{label}: unsupported isolation tool-schema claim")
                if "canary_absent" in isolation:
                    same(isolation["canary_absent"], True, f"{label}: verified isolation contains canary")
                if "native_tool_names" in isolation:
                    same(isolation["native_tool_names"], [], f"{label}: verified isolation contains native tools")
            # Setup failures may have no native result. A successful execution
            # must carry and satisfy every declared no-tools control.
            if execution_ok(run):
                same(att.get("provider_resolved_identity_verified"), False, f"{label}: unsupported provider identity claim")
                same(observation.get("tool_schema_absence_verified"), False, f"{label}: unsupported tool-schema absence claim")
                for key, expected in {"ignore_user_config": True, "fresh_user_home": True, "fresh_runtime_home": True}.items():
                    same(controls.get(key), expected, f"{label}: runtime control mismatch: {key}")
                same(isolation.get("verified"), True, f"{label}: prompt isolation is unverified")
                same(isolation.get("contamination"), [], f"{label}: prompt isolation contamination")
                require(bool(re.fullmatch(r"[0-9a-f]{64}", str(isolation.get("sha256", "")))), f"{label}: missing prompt isolation hash")
            if host == "codex":
                if execution_ok(run):
                    for key, expected in {"project_doc_max_bytes": 0, "personality": "none", "web_search": "disabled", "model_provider": "openai", "approval_policy": "never", "sandbox": "read-only", "native_events": "json", "session_logging": "disposable-home-only"}.items():
                        same(controls.get(key), expected, f"{label}: Codex control mismatch: {key}")
                    require(set(runtime.CODEX_DISABLED_FEATURES) <= set(controls.get("disabled_features", [])), f"{label}: Codex disabled-feature controls incomplete")
                native = run.get("native_events")
                if isinstance(native, list):
                    recomputed_events = runtime.codex_events("\n".join(json.dumps(event) for event in native), evaluator.extract_json, expected_output=run["output"])
                    expected_observation = {key: value for key, value in recomputed_events.items() if key not in {"events", "thread_id"}}
                    same(observation, expected_observation, f"{label}: native event observation mismatch")
                    expected_count = recomputed_events["tool_activity_count"] if recomputed_events["ok"] else None
                    same(observed.get("tool_calls_count"), expected_count, f"{label}: native Codex tool count mismatch")
                    if not recomputed_events["ok"]:
                        require(not execution_ok(run) and att.get("ok") is not True, f"{label}: successful execution contradicts native events")
                    if (run.get("failure") or {}).get("kind") == "provider-transient":
                        same(run["failure"], recomputed_events.get("failure"), f"{label}: retryable failure contradicts native transport evidence")
                else:
                    require(not execution_ok(run), f"{label}: completed native events missing")
            else:
                if execution_ok(run):
                    for key, expected in {"adapter": "native-AIAgent-API", "safe_mode": True, "toolsets": "none", "ignore_rules": True, "skip_context_files": True, "skip_memory": True, "load_soul_identity": False, "skip_background_review": True, "fallback_model": None, "save_trajectories": False, "credentials_in_memory_only": True, "credential_refresh_if_expiring": False}.items():
                        same(controls.get(key), expected, f"{label}: Hermes control mismatch: {key}")
                    same(isolation.get("native_tool_names"), [], f"{label}: native Hermes tools are not empty")
                    same(observation.get("execution_blocker_installed"), True, f"{label}: native tool blocker missing")
                    same(contract.get("output_source"), "native-AIAgent-final-response", f"{label}: unexpected Hermes output source")
                if "assembled_prompt" in isolation:
                    assembled, canary = isolation["assembled_prompt"], isolation.get("canary")
                    require(isinstance(assembled, str) and isinstance(canary, str) and bool(canary), f"{label}: malformed isolation source")
                    same(hashlib.sha256(assembled.encode()).hexdigest(), isolation.get("sha256"), f"{label}: isolation source hash mismatch")
                    canary_absent = canary not in assembled
                    same(isolation.get("canary_absent"), canary_absent, f"{label}: isolation canary contradiction")
                    require(not execution_ok(run) or canary_absent and not any(marker in assembled for marker in runtime.CONTEXT_MARKERS), f"{label}: successful execution contains personal context")
                elif execution_ok(run):
                    errors.append(f"{label}: Hermes isolation source missing")
                if observation:
                    count = observation.get("tool_activity_count")
                    require(type(count) is int and count >= 0, f"{label}: malformed native tool count")
                    same(observed.get("tool_calls_count"), count, f"{label}: native Hermes tool count mismatch")
                    same(observation.get("ok"), count == 0, f"{label}: native tool observation outcome mismatch")
                    require(not execution_ok(run) or count == 0, f"{label}: successful execution contains prohibited tools")
                metadata = run.get("native_result_metadata", {})
                if metadata:
                    complete = metadata.get("completed") is True and not any(metadata.get(key) for key in ("failed", "interrupted", "partial"))
                    require(not execution_ok(run) or complete, f"{label}: successful execution contradicts native completion")
                    if execution_ok(run) or metadata.get("final_response") is not None:
                        same(metadata.get("final_response"), run.get("output"), f"{label}: native Hermes final response mismatch")
                    for key in ("model", "provider"):
                        if metadata.get(key) is not None:
                            same(metadata[key], requested.get(key), f"{label}: native result {key} mismatch")
                else:
                    require(not execution_ok(run), f"{label}: native Hermes completion metadata missing")

        def check_run(run: dict[str, Any], label: str, judge: bool = False, *, identity: dict[str, Any]) -> None:
            result["runs"].append(run)
            host = report.get("judge_agent" if judge else "agent")
            result["host_run_counts"][host] += 1
            require(type(run.get("attempt_count")) is int and run["attempt_count"] >= 0, f"{label}: invalid attempt count")
            attempts = run.get("attempt_count", 0)
            result["physical_attempts"] += attempts
            require(attempts > 0 or run.get("run_budget_exhausted") is True, f"{label}: unexecuted run has no budget failure")
            if run.get("run_budget_exhausted"):
                require(not execution_ok(run) and report.get("run_count") == cap, f"{label}: budget exhaustion contradicts execution/count")
            check_observation(run, label, judge)
            history = run.get("attempts", [])
            require(isinstance(history, list) and len(history) == attempts, f"{label}: attempt history count mismatch")
            retries = rule_data.get("transient_retries_per_run", 0)
            require(type(retries) is int and retries >= 0 and attempts <= retries + 1, f"{label}: retry budget mismatch")
            same(run.get("transient_retry_count", 0), max(0, attempts - 1), f"{label}: retry count mismatch")
            for index, attempt in enumerate(history):
                same(attempt.get("attempt"), index + 1, f"{label}: nonsequential attempt identity")
                complete_attempt = "output" in attempt and "route_attestation" in attempt
                if not complete_attempt and not runtime_lane:
                    if attempts > 1:
                        result["attempt_evidence_complete"] = False
                        result["limitations"].append("historical attempt history is abbreviated; retry transitions cannot be fully verified")
                    if index == len(history) - 1:
                        for key in ("ok", "returncode", "output"):
                            if key in attempt:
                                same(attempt[key], run.get(key), f"{label}: last historical attempt {key} mismatch")
                    continue
                require(complete_attempt, f"{label}: incomplete retry evidence")
                if not complete_attempt:
                    continue
                payload = evaluator.attempt_result(attempt)
                expected_ledger.append({**identity, "attempt": index + 1, "transient": attempt.get("transient"), **payload})
                check_observation(payload, f"{label} attempt {index + 1}", judge)
                transient = evaluator.transient_provider_failure(payload)
                same(attempt.get("transient"), transient, f"{label}: retry classification mismatch")
                if index < len(history) - 1:
                    require(transient and not execution_ok(payload), f"{label}: prohibited retry transition")
                else:
                    same(payload, evaluator.attempt_result(run), f"{label}: final result differs from last attempt")

        recomputed = []
        for index, row in enumerate(rows):
            case_id = selected[index % len(selected)]
            trial = index // len(selected)
            case = selected_cases[case_id]
            label = f"trial {trial} case {case_id}"
            same(row.get("id"), case_id, f"{label}: incomplete or reordered case coverage")
            require(type(row.get("trial")) is int, f"{label}: invalid trial index")
            same(row.get("trial"), trial, f"{label}: noncontiguous trial coverage")
            same(row.get("kind"), case.get("kind"), f"{label}: case kind mismatch")
            require(trial < len(seeds) and row.get("seed") == seeds[trial], f"{label}: seed mismatch")
            order = row["order"]
            require(isinstance(order, list) and len(order) == 2 and set(order) == set(SIDES), f"{label}: invalid anonymous order")
            deterministic = {}
            for side in SIDES:
                check_run(row[side], f"{label} {side}", identity={"trial": trial, "case_id": case_id, "role": side})
                output = row[side]["output"]
                deterministic[side] = evaluator.structured_receipt_check(case, output, suite["receipt_schema"]) if schema == 3 else evaluator.deterministic(case, output)
            recorded_det = deterministic if schema == 3 else {side: deterministic[side][1] for side in SIDES}
            same(row.get("deterministic"), recorded_det, f"{label}: deterministic checks mismatch")
            judges = row["judgments"]
            require(isinstance(judges, list) and len(judges) in ((2, 3) if schema == 3 else (2,)), f"{label}: incomplete judge panel")
            winners, passes, judge_errors = [], [], []
            criterion_ids = [item["id"] for item in case.get("semantic_criteria", [])]
            pair_disagreement = None
            for judge_index, judgment_row in enumerate(judges):
                judge_order = judgment_row["order"]
                if judge_index < 2:
                    same(judge_order, order if judge_index == 0 else list(reversed(order)), f"{label}: judge pair is not order swapped")
                else:
                    require(schema == 3 and judgment_row.get("role") == "tiebreak", f"{label}: unexpected extra judge")
                    require(bool(pair_disagreement and (pair_disagreement["winner"] or pair_disagreement["criteria"])) and not judge_errors, f"{label}: unjustified tiebreak")
                run = judgment_row["run"]
                check_run(run, f"{label} judge {judge_index}", judge=True, identity={"trial": trial, "case_id": case_id, "role": f"judge-{judge_index}" if judge_index < 2 else "judge-tiebreak"})
                try:
                    if not execution_ok(run) or not run.get("route_attestation", {}).get("ok"):
                        route_messages = run.get("route_attestation", {}).get("errors", [])
                        prefix = "tiebreak judge run failed" if judge_index == 2 else "judge run failed"
                        raise ValueError(prefix + (": " + "; ".join(route_messages) if route_messages else ""))
                    judgment = evaluator.extract_json(run["output"])
                    winner, mapped = evaluator.map_v3_judgment(judgment, judge_order, criterion_ids) if schema == 3 else evaluator.map_judgment(judgment, judge_order)
                    same(judgment_row.get("judgment"), judgment, f"{label}: recorded judgment differs from output")
                    winners.append(winner)
                    passes.append(mapped)
                except (ValueError, TypeError, KeyError) as exc:
                    same(judgment_row.get("judgment"), {"raw": run["output"]}, f"{label}: failed judgment raw output mismatch")
                    judge_errors.append(str(exc))
                if judge_index == 1 and schema == 3:
                    pair_disagreement = evaluator.v3_disagreement(winners, passes)
            same(row.get("judge_errors"), judge_errors, f"{label}: judge errors mismatch")
            if schema == 3:
                raw = pair_disagreement or evaluator.v3_disagreement(winners, passes)
                needs_third = (raw["winner"] or raw["criteria"]) and not judge_errors
                require(len(judges) == 3 or not needs_third, f"{label}: required tiebreak missing")
            outcome = evaluator.effective_judgment_result(
                winners, passes,
                {side: deterministic[side]["pass"] if schema == 3 else deterministic[side][0] for side in SIDES},
                criterion_ids if schema == 3 else None,
            )
            winner, hard_pass = outcome["winner"], outcome["hard_pass"]
            raw, detail = outcome["raw_disagreement"], outcome["disagreement"]
            computed_row = {
                **row, "deterministic": recorded_det, "hard_pass": hard_pass, "eligibility": outcome["eligibility"],
                "winner": winner, "score": 1 if winner == "candidate" else -1 if winner == "baseline" else 0,
                "judge_errors": judge_errors, "raw_judge_disagreement": bool(raw["winner"] or raw["criteria"]),
                "judge_disagreement": bool(detail["winner"] or detail["criteria"]), "judge_disagreement_detail": detail,
            }
            if schema == 3:
                computed_row.update(candidate_receipt_pass=bool(deterministic["candidate"]["pass"]), candidate_hard_pass=bool(hard_pass["candidate"]))
            for key in ("hard_pass", "eligibility", "winner", "score", "raw_judge_disagreement", "judge_disagreement", "judge_disagreement_detail", *(("candidate_receipt_pass", "candidate_hard_pass") if schema == 3 else ())):
                same(row.get(key), computed_row[key], f"{label}: {key} mismatch")
            recomputed.append(computed_row)

        ledger = report.get("attempt_ledger")
        if ledger is not None:
            require(isinstance(ledger, list), "attempt ledger must be an array")
            normal = [{key: entry.get(key) for key in ("trial", "case_id", "role", "attempt", "transient")} | evaluator.attempt_result(entry) for entry in ledger]
            same(normal[:len(expected_ledger)], expected_ledger, "attempt ledger contradicts paired result history")
            orphans = normal[len(expected_ledger):]
            require(not orphans or abnormal, "complete report has unpaired native attempts")
            roles = ["baseline", "candidate", "judge-0", "judge-1", "judge-tiebreak"]
            previous_role, previous_attempt = -1, None
            for entry in orphans:
                trial, case_id = len(rows) // len(selected), selected[len(rows) % len(selected)]
                require(trial < high and entry["trial"] == trial and entry["case_id"] == case_id, "unpaired attempt lies outside the next incomplete case")
                require(entry["role"] in roles, "unknown unpaired attempt role")
                role_index = roles.index(entry["role"])
                same_role = role_index == previous_role
                require(same_role or role_index == previous_role + 1, "unpaired attempt roles are out of order")
                expected_index = previous_attempt["attempt"] + 1 if same_role else 1
                same(entry["attempt"], expected_index, "unpaired retry sequence mismatch")
                require(type(entry["attempt"]) is int and 1 <= entry["attempt"] <= rule_data.get("transient_retries_per_run", 0) + 1, "unpaired retry exceeds its plan")
                if same_role:
                    require(evaluator.transient_provider_failure(previous_attempt), "prohibited unpaired retry transition")
                payload = evaluator.attempt_result(entry)
                check_observation(payload, f"unpaired trial {trial} case {case_id} {entry['role']} attempt {entry['attempt']}", judge=role_index >= 2)
                same(entry["transient"], evaluator.transient_provider_failure(payload), "unpaired retry classification mismatch")
                previous_role, previous_attempt = role_index, entry
            result["physical_attempts"] += len(orphans)
            result["unpaired_attempts"] = len(orphans)
            if orphans:
                result["attempt_evidence_complete"] = False
                result["limitations"].append("native attempts are retained for an incomplete case; no case-level verdict is claimed for them")
        attempts = result["physical_attempts"]
        same(report.get("run_count"), attempts, "physical run count mismatch or missing attempt evidence")
        require(attempts <= cap, "physical run budget exceeded")
        completed_trials = len(rows) // len(selected)
        require(len(seeds) == completed_trials if not abnormal else completed_trials <= len(seeds) <= completed_trials + 1, "trial seed coverage mismatch")
        trial_scores = []
        expected = None
        for trial in range(completed_trials):
            through_trial = recomputed[: (trial + 1) * len(selected)]
            trial_rows = through_trial[trial * len(selected):]
            scores = evaluator.decision_scores(trial_rows)
            trial_scores.append(sum(scores) / len(scores) if scores else 0.0)
            expected = evaluator.v3_stability_decision(through_trial, suite["stability"], trial + 1) if schema == 3 else evaluator.sequential_decision(mode, evaluator.decision_scores(through_trial), rule, trial + 1)
            failed = any(not execution_ok(item["baseline"]) or not execution_ok(item["candidate"]) or item["judge_errors"] for item in through_trial)
            if failed:
                expected["decision"] = "harness-failure"
            elif schema == 2 and any(item["eligibility"]["candidate"] == "fail" for item in through_trial):
                expected["decision"] = "reject" if mode == "admission" else "retain"
            elif schema == 2 and any(item["judge_disagreement"] for item in through_trial) and expected["decision"] != "continue":
                expected["decision"] = "inconclusive"
            require(expected["decision"] == "continue" or trial + 1 == completed_trials, "observations continue after a terminal decision")
        if result["unpaired_attempts"]:
            require(expected is None or expected["decision"] == "continue", "unpaired attempts follow a terminal comparison decision")
        if abnormal:
            if harness_integrity.get("unchanged") is False:
                reason = "harness integrity could not be checked" if harness_integrity.get("error") else "harness changed during evaluation"
                require(bool(harness_integrity.get("error")) or harness_integrity.get("final_sha256") != artifacts.get("harness_sha256"), "harness failure lacks differing hash or check error")
            else:
                reason = "exception" if status == "failed" else "interrupted"
            expected = {"decision": "harness-failure", "reason": reason}
        elif expected is not None and expected["decision"] == "continue":
            # The producer may stop between trials when its remaining run budget
            # cannot reserve the next full generation/panel batch.
            require(cap - attempts < len(selected) * (5 if schema == 3 else 4), "evaluation stopped before its declared trial/budget bound")
            expected["decision"] = "inconclusive"
        if expected is not None:
            expected = evaluator.scope_decision(expected, full_suite)
        result["computed_decision"] = expected
        same(report.get("decision"), expected, "declared decision differs from recomputed evidence")
        summary = {
            "candidate_wins": sum(row["winner"] == "candidate" for row in recomputed),
            "candidate_losses": sum(row["winner"] == "baseline" for row in recomputed),
            "ties": sum(row["winner"] == "tie" for row in recomputed),
            "candidate_hard_failures": sum(row["eligibility"]["candidate"] == "fail" for row in recomputed),
            "judge_errors": sum(bool(row["judge_errors"]) for row in recomputed),
            "judge_disagreements": sum(row["judge_disagreement"] for row in recomputed),
            "raw_judge_disagreements": sum(row["raw_judge_disagreement"] for row in recomputed),
            "criterion_disagreements": sum(bool(row["judge_disagreement_detail"].get("criteria")) for row in recomputed),
            "raw_criterion_disagreements": sum(bool(row["judge_disagreement_detail"].get("raw", {}).get("criteria")) for row in recomputed),
            "candidate_receipt_failures": sum(not row.get("candidate_receipt_pass", row["hard_pass"]["candidate"]) for row in recomputed),
            "route_attestation_failures": sum(run.get("route_attestation", {}).get("ok") is not True for run in result["runs"]),
            "trial_scores": trial_scores,
        }
        result["computed_summary"] = summary
        for key, value in summary.items():
            same(report.get("summary", {}).get(key), value, f"summary {key} mismatch")
        positive = expected is not None and expected["decision"] in ("admit", "retire")
        if positive:
            require(full_suite and completed_trials >= low, "positive decision lacks full suite/trial coverage")
        lifecycle = report.get("session_lifecycle", {})
        policy = lifecycle.get("policy")
        require(policy in ("retain-evidence", "delete-after-durable-report"), "missing or unsupported lifecycle policy")
        for key in ("created", "deleted", "remaining", "protected", "errors"):
            require(isinstance(lifecycle.get(key), list), f"missing lifecycle field: {key}")
            if key != "errors" and isinstance(lifecycle.get(key), list):
                require(all(isinstance(value, str) and value for value in lifecycle[key]) and len(set(lifecycle[key])) == len(lifecycle[key]), f"invalid or duplicate lifecycle sessions: {key}")
        created, deleted, remaining, protected = (set(lifecycle.get(key, [])) for key in ("created", "deleted", "remaining", "protected"))
        require(deleted <= created and remaining <= created and protected <= created, "lifecycle contains uncreated sessions")
        require(not (deleted & protected), "lifecycle deleted a protected session")
        if runtime_lane:
            require(not (created or deleted or remaining or protected), "native no-tools lane claims global session lifecycle authority")
        if policy == "retain-evidence":
            require(not deleted and remaining == created - protected, "retained session accounting mismatch")
        else:
            if remaining:
                result["operational_errors"].append("evaluator sessions remain")
            if deleted != created - protected:
                result["operational_errors"].append("session deletion is incomplete")
        if lifecycle.get("errors"):
            result["operational_errors"].append("session cleanup reported errors")
        workspace = report.get("workspace_lifecycle")
        if workspace is not None:
            same(workspace.get("policy"), "remove-after-durable-report", "workspace lifecycle policy mismatch")
            outcome = workspace.get("outcome")
            require(outcome in ("removed", "retained-report-write-failure", "cleanup-failed"), "workspace lifecycle outcome missing or invalid")
            require(isinstance(workspace.get("errors"), list), "workspace lifecycle errors missing")
            if outcome == "removed":
                require(workspace.get("path") is None and not workspace.get("errors"), "removed workspace has contradictory retention/error evidence")
            else:
                require(isinstance(workspace.get("path"), str) and bool(workspace["path"]), "retained workspace path missing")
                result["operational_errors"].append("evaluation workspace retained or cleanup failed")
        exported = report.get("report_export")
        if exported is not None:
            require(type(exported.get("written")) is bool and isinstance(exported.get("errors"), list), "report export outcome missing")
            if exported.get("written") is not True or exported.get("errors"):
                result["operational_errors"].append("requested report export failed or is unverified")
        for host, probe in report.get("version_probes", {}).items():
            if probe.get("ok") is not True or probe.get("errors"):
                result["operational_errors"].append(f"{host}: native version probe failed or is unverified")
            if probe.get("errors"):
                require(probe.get("ok") is not True, f"{host}: successful version probe contains errors")
            cleanup = probe.get("cleanup", {})
            clean = cleanup.get("credentials_removed") is True and cleanup.get("state_removed") is True and cleanup.get("errors") == []
            if not clean:
                result["operational_errors"].append(f"{host}: native version probe cleanup failed or is unverified")
                require(probe.get("ok") is not True, f"{host}: successful version probe contradicts cleanup")
            if host == report.get("agent"):
                same(report.get("agent_version"), probe.get("version"), "generation version differs from native version receipt")
            if host == report.get("judge_agent"):
                same(report.get("judge_version"), probe.get("version"), "judge version differs from native version receipt")
        if "operational_ok" in report:
            same(report["operational_ok"], not result["operational_errors"], "report operational outcome contradicts recorded operations")
        result["positive_decision_sufficient"] = positive and not errors and not result["operational_errors"] and result["attempt_evidence_complete"]
        result["evidence_complete"] = not errors and result["attempt_evidence_complete"]
    except (AttributeError, KeyError, TypeError, ValueError, IndexError, ZeroDivisionError) as exc:
        errors.append(f"malformed evidence: {type(exc).__name__}: {exc}")
    result["errors"] = sorted(set(errors))
    result["operational_errors"] = sorted(set(result["operational_errors"]))
    result["limitations"] = sorted(set(result["limitations"]))
    return result
