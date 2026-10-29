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


def validate_artifact_evidence(report: dict, plan: dict, *, source_bytes: dict | None = None) -> dict:
    """Validate bound native leaf receipts without executing paths or oracles.

    source_bytes maps SHA256 to explicitly supplied bytes. No recorded pathname
    is opened. Source completeness covers declared bytes only, never execution
    origin, source-to-request attribution, oracle adequacy or publication.
    """
    import artifact_hash
    import evaluation_measurement as measurement
    from pathlib import PurePosixPath, PureWindowsPath
    errors, gaps, runtime_gaps, bindings, records = [], [], [], [], []
    blockers = ['native artifact producer has no source-bound instruction admission contract',
                'recorded sources and receipts do not authenticate source-to-execution provenance',
                'leaf case/arm coverage does not establish required acceptance trials or workflow coverage']
    def require(condition, message):
        if not condition:
            errors.append(message)
    def bind(label, value):
        if measurement.sha(value) is None:
            gaps.append(label + ': recorded source hash unavailable')
            return
        data = supplied.get(value)
        matched = isinstance(data, bytes) and hashlib.sha256(data).hexdigest() == value
        bindings.append({'source': label, 'sha256': value, 'bytes_matched': matched})
        if data is None:
            gaps.append(label + ': source bytes not supplied')
        elif not matched:
            errors.append(label + ': supplied source bytes mismatch')
    def files(label, values):
        require(isinstance(values, dict) and bool(values), label + ': missing file manifest')
        for name, value in values.items():
            require(isinstance(name, str) and bool(name) and '\\' not in name
                    and not name.startswith('/') and ':' not in name
                    and all(part not in ('', '.', '..') for part in name.split('/')),
                    label + ': unsafe manifest path')
            require(measurement.sha(value) is not None, label + ': invalid file hash')
            bind(label + '/' + name, value)
    def frame(label, value):
        require(value.get('identity_format') == 'fleet-package-v1', label + ': unsupported package identity')
        manifest = value['files']
        files(label, manifest)
        require('SKILL.md' in manifest, label + ': missing SKILL.md')
        require(artifact_hash.package_hash_from_files(manifest) == value.get('package_sha256'),
                label + ': package identity mismatch')
        prompt = value['prompt_text']
        require(hashlib.sha256(prompt.encode('utf-8')).hexdigest() == value.get('prompt_sha256'),
                label + ': prompt projection hash mismatch')
    try:
        supplied = {} if source_bytes is None else source_bytes
        require(isinstance(supplied, dict), 'source bytes must be an explicit hash map')
        for value, data in supplied.items():
            require(measurement.sha(value) is not None and isinstance(data, bytes)
                    and hashlib.sha256(data).hexdigest() == value, 'supplied source hash/bytes mismatch')
        require(report['kind'] == plan['kind'] == plan['spec']['purpose'] == 'native-skill-study',
                'unsupported or mismatched native artifact kind')
        require(report.get('admission') is False and report.get('workflow_comparison_supported') is False
                and plan.get('workflow_comparison_supported') is False,
                'native artifact authority must remain diagnostic only')
        spec = plan['spec']
        arms = {row['id']: row for row in spec['arms']}
        cases = {row['id']: row for row in spec['cases']}
        require(len(arms) == len(spec['arms']) and len(cases) == len(spec['cases'])
                and 1 <= len(arms) * len(cases) <= 12, 'invalid native case/arm coverage')
        jobs, rows = plan['jobs'], report['results']
        require(len(jobs) == len(arms) * len(cases) == len(rows), 'incomplete native job/result coverage')
        require(type(report.get('completed_trials')) is int and type(report.get('expected_trials')) is int
                and report['completed_trials'] == report['expected_trials'] == len(jobs), 'native trial counts mismatch')
        job_ids = [job['id'] for job in jobs]
        require(len(set(job_ids)) == len(jobs) and [row['id'] for row in rows] == job_ids,
                'duplicate, missing or reordered native results')
        require({(job['case'], job['arm']) for job in jobs} == {(case, arm) for case in cases for arm in arms},
                'native case/arm job mapping mismatch')
        for key in ('oracle_sha256', 'controller_sha256', 'worker_sha256', 'native_hermes_worker_sha256',
                    'runtime_sha256', 'measurement_sha256', 'usage_observer_sha256'):
            bind(key, plan.get(key))
        require(set(plan['candidate_snapshots']) == set(arms), 'candidate snapshot arm coverage mismatch')
        for arm, snapshot in plan['candidate_snapshots'].items():
            require((snapshot is None) == (arms[arm].get('instructions') is None), 'candidate absence mismatch')
            if snapshot is not None:
                frame('candidate/' + arm, snapshot)
        for name, snapshot in plan.get('common_catalog_snapshots', {}).items():
            frame('common-catalog/' + str(len(bindings)), snapshot)
        require(set(plan.get('common_catalog_snapshots', {})) == set(spec.get('catalog', [])),
                'common native catalog source coverage mismatch')
        require(set(plan['case_source_trees']) == set(cases), 'fixture source case coverage mismatch')
        for case, manifest in plan['case_source_trees'].items():
            files('fixture/' + case, manifest)
        for job, row in zip(jobs, rows):
            require(row['arm'] == job['arm'] and row['case'] == job['case'], 'native result case/arm mismatch')
            require(all(job['initial_tree'].get(name) == value for name, value in plan['case_source_trees'][job['case']].items()),
                    'native job differs from frozen fixture source')
            files('final-artifact/' + row['id'], row['final_tree'])
            native = row['native']
            route = {key: spec.get(key) for key in ('model', 'provider', 'reasoning')}
            require(all(isinstance(value, str) and value for value in route.values())
                    and all(native.get('agent_observed_route', {}).get(key) == value for key, value in route.items()),
                    'native observed route mismatch or missing')
            expected_catalog = [snapshot['package_sha256'] for snapshot in plan.get('common_catalog_snapshots', {}).values()]
            snapshot = plan['candidate_snapshots'][job['arm']]
            if snapshot and spec.get('instruction_exposure') != 'explicit-body':
                expected_catalog.append(snapshot['package_sha256'])
            require(sorted(job['catalog_frames'].values()) == sorted(expected_catalog)
                    and len(job['catalog']) == len(set(job['catalog']))
                    and set(job['catalog']) == set(job['catalog_frames']), 'prepared native catalog binding mismatch')
            known_frames = list(plan.get('common_catalog_snapshots', {}).values()) + ([snapshot] if snapshot else [])
            frames_by_hash = {value['package_sha256']: value for value in known_frames}
            expected_tree = dict(plan['case_source_trees'][job['case']])
            path_type = PureWindowsPath if '\\' in job['fixture'] or ':' in job['fixture'] else PurePosixPath
            for location, value in job['catalog_frames'].items():
                relative = path_type(location).relative_to(path_type(job['fixture']))
                require(len(relative.parts) == 4 and relative.parts[:2] == ('.agents', 'skills')
                        and relative.parts[2] not in ('.', '..') and relative.parts[-1] == 'SKILL.md',
                        'native catalog location is outside declared skill staging')
                prefix = relative.parent.as_posix()
                expected_tree.update({prefix + '/' + name: digest for name, digest in frames_by_hash[value]['files'].items()})
            require(job['initial_tree'] == expected_tree, 'native initial tree contains missing, changed or undeclared sources')
            # The worker hashes build_prompt(agent), not job['prompt']. These
            # are different inputs; the recorded hash cannot bind the user task.
            assembled = native.get('catalog_evidence', {}).get('prompt_sha256')
            require(measurement.sha(assembled) is not None, 'native assembled prompt hash unavailable')
            bind('native-assembled-prompt/' + row['id'], assembled)
            runtime_gaps.append('native user-task input has no separately recorded hash or source-attributed request manifest')
            require(cases[job['case']]['prompt'] in job['prompt'], 'prepared job omits declared case prompt')
            if snapshot and spec.get('instruction_exposure') == 'explicit-body':
                require(snapshot['prompt_text'] in job['prompt'], 'prepared job omits declared explicit candidate projection')
            if native.get('host_version') is None:
                runtime_gaps.append('native host version not recorded')
            if native.get('model_launched') is not True:
                runtime_gaps.append('native model launch not recorded')
            if native.get('catalog_evidence', {}).get('exact_catalog_verified') is not True:
                runtime_gaps.append('exact native catalog observation unavailable')
            lifecycle = native.get('native_usage', {}).get('lifecycle', {})
            observed_sources = lifecycle.get('native_sources_before', {})
            if not observed_sources:
                runtime_gaps.append('native implementation source fingerprints not recorded')
            else:
                require(observed_sources == lifecycle.get('native_sources_after'), 'native implementation sources changed during run')
                for index, value in enumerate(observed_sources.values()):
                    bind('native-implementation/' + row['id'] + '/' + str(index), value)
        records = measurement.artifact_records(report, plan)
        for row, record in zip(rows, records):
            expected_ok = record['outcome']['execution_ok'] is True and record['outcome']['task_passed'] is True
            if row.get('exposure_setup_ok') is False:
                expected_ok = False
            require(type(row.get('oracle_exit_code')) is int and type(row.get('ok')) is bool
                    and row['ok'] == expected_ok, 'native outcome contradicts raw execution/oracle receipts')
        if 'measurements' in report:
            require(report['measurements'] == records, 'saved native measurements differ from raw receipt projection')
    except (KeyError, TypeError, ValueError, AttributeError, IndexError) as exc:
        errors.append('malformed native artifact evidence: ' + type(exc).__name__)
    return {'errors': sorted(set(errors)), 'source_gaps': sorted(set(gaps)), 'runtime_gaps': sorted(set(runtime_gaps)),
            'consistent': not errors, 'source_bytes_complete': not errors and not gaps,
            'source_bindings': bindings, 'records': records,
            'usage_readiness': measurement.acceptance_readiness(records),
            'admission': False, 'positive_decision_sufficient': False,
            'execution_authenticated': False, 'admission_blockers': blockers}


def outcome_efficiency(before: list[dict], after: list[dict]) -> dict:
    """Qualify recorded equal-or-better outcomes at no greater overall tokens.

    Callers retain their source, oracle and harness checks. This consistency
    result grants neither publication authority nor execution authentication.
    Inputs must be freshly projected from the bound raw receipts, not a saved
    comparison's eligibility booleans.
    """
    import evaluation_measurement as measurement
    errors = []
    comparison = None
    try:
        for row in before + after:
            if row.get('record_sha256') != measurement.digest({
                    key: value for key, value in row.items() if key != 'record_sha256'}):
                errors.append('measurement projection digest mismatch')
            if measurement.sha(row.get('provenance', {}).get('evidence_sha256')) is None:
                errors.append('measurement source receipt binding missing')
        comparison = measurement.compare_records(before, after)
        pairs = comparison['pairs']
        if not pairs or not comparison['conditional_efficiency']['equivalent_case_coverage']:
            errors.append('quality-qualified matched case/trial coverage is incomplete')
        for side, records in (('baseline', before), ('candidate', after)):
            ready = measurement.acceptance_readiness(records)
            errors.extend(side + ': ' + gap for gap in ready['gaps'])
        for pair in pairs:
            if not pair['conditional_efficiency_eligible']:
                errors.append('matched task lacks quality-qualified complete overall usage')
            delta = pair['token_delta_after_minus_before']['total_tokens']
            if type(delta) is not int or delta > 0:
                errors.append('matched task must use equal or fewer overall tokens')
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        errors.append('malformed efficiency evidence: ' + type(exc).__name__)
    return {'eligible': not errors, 'errors': sorted(set(errors)),
            'comparison': comparison, 'execution_authenticated': False,
            'behavioral_proof': False}


def instruction_improvement(report: dict, suite: dict, *, suite_sha256: str,
                            harness_sha256: str, route: dict) -> list[str]:
    """Require a positive measured difference as well as nonregression/accounting.

    Mechanical eligibility does not establish claim coverage, practical benefit,
    comparability or retention authority. Those remain owner review decisions.
    """
    if not isinstance(report, dict) or not isinstance(suite, dict):
        return ['behavioral measurement and task contract must be objects']
    checked = validate_report(report, suite)
    errors = list(checked['errors'])
    readiness = runtime.comparison_readiness(suite)
    recorded = report.get('comparison_readiness', {})
    if not readiness['ready'] or recorded.get('ready') is not True or recorded.get('requirements') != suite.get('comparison_requirements'):
        errors.append('measurement question did not pass matching readiness')
    cases = suite.get('cases', [])
    minimum = report.get('decision_rule', {}).get('min_trials')
    maximum = report.get('decision_rule', {}).get('max_trials')
    # The validator recomputes contiguous complete trials and checks stopping
    # after every trial. Sequential minima are lower bounds; v3 stability is an
    # exact plan. Do not independently reinterpret a recorded stop decision.
    completed_trials = len(checked['computed_summary'].get('trial_scores', []))
    trial_coverage = (type(minimum) is int and type(maximum) is int
                      and 1 <= minimum <= completed_trials <= maximum
                      and len(report.get('results', [])) == len(cases) * completed_trials)
    if suite.get('schema_version') == 3:
        trial_coverage = trial_coverage and completed_trials == suite.get('stability', {}).get('trials')
    if (report.get('decision_mode') != 'admission' or not checked['evidence_complete']
            or (checked['computed_decision'] or {}).get('decision') not in ('admit', 'inconclusive')
            or checked['operational_errors'] or checked['unpaired_attempts']
            or report.get('selected_case_ids') != [case.get('id') for case in cases]
            or not trial_coverage):
        errors.append('no sufficient full-suite outcome comparison')
    summary = checked['computed_summary']
    if any(summary.get(key, 0) for key in ('candidate_losses', 'candidate_hard_failures',
            'judge_errors', 'judge_disagreements', 'candidate_receipt_failures', 'route_attestation_failures')):
        errors.append('measurement must preserve outcomes without recorded regressions')
    import evaluation_measurement as measurement
    for row in report.get('attempt_ledger', []):
        if str(row.get('role', '')).startswith('judge') and row.get('workflow_accounting', {}).get('target_arm') not in SIDES:
            errors.append('shared judge needs explicit target arm; no guessed allocation')
    records = measurement.inline_records(report)
    expected = {(row.get('id'), row.get('trial')) for row in report.get('results', [])}
    for side in SIDES:
        observed = {(row['identity']['case_id'], row['identity']['trial']) for row in records
                    if row['identity']['role'] == side}
        if observed != expected:
            errors.append('efficiency projection does not cover measured case/trial outcomes')
    # Supporting calls accompany both views; ambiguous shared judges fail closed
    # unless the original receipts explicitly attribute them to an arm.
    before = [row for row in records if row['identity']['arm'] != 'candidate']
    after = [row for row in records if row['identity']['arm'] != 'baseline']
    efficiency = outcome_efficiency(before, after)
    errors.extend(efficiency['errors'])
    # Noninferiority alone is not improvement. Preserve the existing admission
    # decision's quality threshold; do not promote individual wins or an
    # inconclusive quality decision into a supported outcome gain. A strict
    # token saving can qualify only through complete matched accounting.
    token_gain = (not efficiency['errors'] and any(
        pair['token_delta_after_minus_before']['total_tokens'] < 0
        for pair in (efficiency.get('comparison') or {}).get('pairs', [])))
    quality_gain = (checked['computed_decision'] or {}).get('decision') == 'admit'
    if not quality_gain and not token_gain:
        errors.append('no supported outcome gain or complete overall-token saving; '
                      'noninferiority is not improvement or retention authority')
    artifacts = report.get('artifacts', {})
    if artifacts.get('suite_sha256') != suite_sha256:
        errors.append('measurement task contract mismatch')
    if artifacts.get('harness_sha256') != harness_sha256:
        errors.append('measurement harness is outdated or mismatched')
    if report.get('agent') != route.get('host') or any(
            report.get('effective_stack', {}).get(key) != route.get(key)
            for key in ('model', 'provider', 'reasoning')):
        errors.append('measurement does not match the current model route')
    return sorted(set(errors))


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
        if "oracle_preflight" in report or any("acceptance_review" in case for case in suite.get("cases", [])):
            reviewed_oracle = evaluator.oracle_preflight(suite)
            require(reviewed_oracle["ready"], "declared oracle review fails mechanical preflight")
            same(report.get("oracle_preflight"), reviewed_oracle, "oracle preflight receipt mismatch")
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
        if runtime_lane == "inline-text-no-tools-v1":
            same(stack.get("context_policy"), "fresh-session-per-output", "context_policy differs from producer execution")
            same(stack.get("prompt_assembly"),
                 "isolated-anonymous-artifact-v3" if schema == 3 else "isolated-explicit-artifact-v2",
                 "prompt_assembly differs from producer execution")
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


def validate_native_diagnostic(report: Any) -> dict[str, Any]:
    """Check a bounded native comparison receipt, never an admission decision.

    Hash syntax/equality checks attest receipt consistency only. The producer must
    preserve raw sources for independent hash recomputation and semantic review.
    This entry point is intentionally not called by validate_report or eval_gate.
    """
    errors: list[str] = []

    def require(condition, message):
        if not condition:
            errors.append(message)

    def digest(value):
        return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None

    try:
        require(report['kind'] == 'native-instruction-diagnostic-v1', 'wrong diagnostic kind')
        require(report['schema_version'] == 1, 'unsupported diagnostic version')
        require(report['authority'] == dict(admission=False, retirement=False, cache=False),
                'diagnostic cannot grant governance authority')
        require(report['status'] == 'complete', 'comparison is incomplete')
        cases, trials = report['cases'], report['trials']
        require(isinstance(cases, list) and len(cases) == 6 and len(set(cases)) == 6,
                'six distinct cases required')
        require(report['trial_cap'] == 12 and type(report['attempts_started']) is int
                and report['attempts_started'] == len(trials) == 12, 'physical trial budget mismatch')
        require(report['cleanup_ok'] is True, 'cleanup unverified')
        for key in ('suite', 'adapter', 'runtime', 'raw_report'):
            require(digest(report['artifacts'][key]), f'invalid {key} binding')
        for arm in ('baseline', 'current'):
            identity = report['arms'][arm]
            require(re.fullmatch(r'[0-9a-f]{40}', identity['revision']) is not None,
                    f'{arm}: invalid revision')
            for key in ('soul_sha256', 'skill_sha256'):
                require(digest(identity[key]), f'{arm}: invalid {key}')
        require(any(report['arms']['baseline'][key] != report['arms']['current'][key]
                    for key in ('soul_sha256', 'skill_sha256')), 'identical instruction arms')
        pairs = {(case, arm) for case in cases for arm in ('baseline', 'current')}
        require([(t['case'], t['arm']) for t in trials].__len__() == len(pairs)
                and {(t['case'], t['arm']) for t in trials} == pairs, 'case/arm coverage mismatch')
        routes = set()
        for trial in trials:
            label = f"{trial['case']}/{trial['arm']}"
            require(trial['completed'] is True, f'{label}: execution incomplete')
            require(trial['cleanup_ok'] is True, f'{label}: cleanup unverified')
            require(trial['boundary_violations'] == [], f'{label}: scope violation')
            require(type(trial['api_calls']) is int and trial['api_calls'] > 0,
                    f'{label}: missing API-call accounting')
            route = trial['requested_route']
            require(all(isinstance(route[k], str) and route[k] for k in ('model', 'provider', 'reasoning')),
                    f'{label}: route incomplete')
            require(route == trial['observed_route'], f'{label}: route mismatch')
            routes.add(tuple(route[k] for k in ('model', 'provider', 'reasoning')))
            for key in ('surrounding_prompt_sha256', 'tools_sha256', 'fixture_before_sha256',
                        'output_sha256', 'actions_sha256', 'fixture_after_sha256'):
                require(digest(trial[key]), f'{label}: invalid {key}')
        require(len(routes) == 1, 'route differs between trials')
        for case in cases:
            pair = [t for t in trials if t['case'] == case]
            if len(pair) == 2:
                for key in ('surrounding_prompt_sha256', 'tools_sha256', 'fixture_before_sha256'):
                    require(pair[0][key] == pair[1][key], f'{case}: unequal {key}')
    except (KeyError, TypeError, ValueError, AttributeError):
        errors.append('malformed diagnostic evidence')
    return {'valid': not errors, 'errors': sorted(set(errors)),
            'admission_eligible': False, 'decision': 'diagnostic-only' if not errors else 'inconclusive'}


def strict_review_json(text):
    def pairs(items):
        result={}
        for key,value in items:
            if key in result:raise ValueError('duplicate review key')
            result[key]=value
        return result
    def constant(value):raise ValueError('nonfinite review value')
    return json.loads(text,object_pairs_hook=pairs,parse_constant=constant)


def substantive_review(parsed, packet_files, source_bytes):
    """Resolve cited packet evidence and reject internally unsound preference.

    This establishes source consistency, not that a reason is true or a reviewer
    is independent. No receipt-selected path is opened or code executed.
    """
    gaps=[];resolved=[];dimensions={}
    def text_or_list(value,nonempty=False):
        if isinstance(value,str):return bool(value.strip())
        return isinstance(value,list) and (not nonempty or bool(value)) and all(isinstance(v,str) and bool(v.strip()) for v in value)
    def strings(value):
        if isinstance(value,str):return [value]
        if isinstance(value,list):return [text for item in value for text in strings(item)]
        if isinstance(value,dict):return [text for item in value.values() for text in strings(item)]
        return []
    try:
        deliveries=parsed['deliveries']
        if set(deliveries)!={'A','B'}:raise ValueError('two anonymous deliveries required')
        program_key='program_adequacy' if 'program_adequacy' in deliveries['A'] else 'semantic_adequacy'
        handoff_key='handoff_adequacy' if 'handoff_adequacy' in deliveries['A'] else 'explanation_utility'
        preference_keys=('comparative_program_preference','comparative_handoff_preference') if program_key=='program_adequacy' else ('comparative_preference','explanation_preference')
        for label,row in deliveries.items():
            if any(row.get(k) not in ('adequate','inadequate','uncertain') for k in (program_key,handoff_key)):
                gaps.append(label+': adequacy missing/invalid')
            if not text_or_list(row.get('limitations')):
                gaps.append(label+': limitations missing/invalid')
            evidence=row.get('evidence')
            structured=(program_key=='semantic_adequacy' and isinstance(evidence,list) and bool(evidence)
                and all(isinstance(item,dict) and text_or_list(item.get('locations'),True)
                    and isinstance(item.get('reason'),str) and bool(item['reason'].strip())
                    and ('aspect' not in item or isinstance(item['aspect'],str) and bool(item['aspect'].strip())) for item in evidence))
            if not (text_or_list(evidence,True) or structured):gaps.append(label+': evidence missing/invalid')
            count=0
            for text in strings(row.get('evidence')):
                for match in re.finditer(r'(?<![\w/])((?:A|B|starting-source)/[A-Za-z0-9_.@+-]+(?:/[A-Za-z0-9_.@+-]+)*)(?::(\d+)(?:-(\d+))?)?',text):
                    name=match[1].rstrip('.');digest=packet_files.get(name);data=source_bytes.get(digest)
                    if not isinstance(data,bytes) or hashlib.sha256(data).hexdigest()!=digest:
                        gaps.append('unresolved review evidence: '+name);continue
                    if match[2]:
                        start=int(match[2]);end=int(match[3] or start)
                        try:length=len(data.decode('utf-8-sig').splitlines())
                        except UnicodeError:length=0
                        if not 1<=start<=end<=length:
                            gaps.append('out-of-range review evidence: '+name);continue
                    resolved.append({'delivery':label,'path':name,'sha256':digest,'start':match[2],'end':match[3]})
                    if name.startswith(label+'/'):count+=1
            if not count:gaps.append(label+': no resolved own-delivery evidence')
        limits=parsed.get('overall_limits',parsed.get('overall_limitations'))
        if not text_or_list(limits):gaps.append('overall limitations missing/invalid')
        for dimension,key,preference in zip(('program','handoff'),(program_key,handoff_key),preference_keys):
            choice=parsed.get(preference)
            if choice not in ('A','B','tie','inconclusive'):gaps.append('invalid '+dimension+' preference')
            adequate=[label for label in ('A','B') if deliveries[label].get(key)=='adequate']
            if len(adequate)==1 and choice not in (adequate[0],'inconclusive'):
                gaps.append(dimension+': preference contradicts adequacy')
            if choice in ('A','B') and deliveries[choice].get(key)!='adequate':
                gaps.append(dimension+': preferred delivery is not adequate')
            dimensions[dimension]={'preference':choice,'adequacy':{label:deliveries[label].get(key) for label in ('A','B')}}
    except (KeyError,TypeError,ValueError,AttributeError):gaps.append('malformed substantive review')
    return {'ready':not gaps,'gaps':sorted(set(gaps)),'resolved_evidence':resolved,'dimensions':dimensions,
        'semantic_truth_automatically_proven':False}


def rendered_outcome_decision(report, attachment, source_bytes):
    """Join a scoped human judgment to finished renders; never fabricate a judge.

    This checks bindings and consumes explicit semantic assessments. It cannot
    discover omitted requirements, authenticate a human or infer task success
    from a preference. Positive release/efficiency controls remain separate.
    """
    import evaluation_measurement as m
    gaps=[]
    def raw(sha):
        data=source_bytes.get(sha)
        if not isinstance(data,bytes) or hashlib.sha256(data).hexdigest()!=sha:
            raise ValueError('missing/changed outcome evidence: '+str(sha))
        return data
    def doc(sha): return strict_review_json(raw(sha))
    def citation(value):
        excerpt=value.get('excerpt')
        if not isinstance(excerpt,str) or not excerpt.strip() or excerpt not in raw(value['sha256']).decode('utf-8'):
            raise ValueError('outcome citation does not resolve')
    try:
        if attachment.get('output_kind')!='rendered-product': raise ValueError('explicit rendered-product scope required')
        p=doc(attachment['outcome_packet_sha256'])
        if p.get('kind')!='human-rendered-outcome-v1': raise ValueError('unsupported outcome packet')
        # Re-entry receives the wrapper's annotated rows. Bind only the original
        # captured result for BOTH its digest and every source/capture join.
        # Raw outcome_assessment and all unknown/raw fields remain authoritative.
        rows=[{k:v for k,v in row.items()
               if k not in ('completed_review_outcome','completed_outcome_assessment')}
              for row in report['results']]
        ids=[r['id'] for r in rows]
        if len(ids)!=len(set(ids)) or len(ids)<2: raise ValueError('one row per actual invocation required')
        if attachment.get('results_sha256')!=m.digest(rows): raise ValueError('outcome/result binding changed')
        for key in ('product_goal','intervention_description','actor_assignment'): citation(p[key])
        doc(p['assessment_sha256'])
        mapping=doc(p['mapping_sha256']); joins=doc(p['source_joins_sha256'])
        if mapping['source_joins_sha256']!=p['source_joins_sha256']: raise ValueError('mapping/source join changed')
        if {j['id'] for j in joins}!=set(ids) or len(joins)!=len(ids): raise ValueError('incomplete source roster')
        for j in joins:
            r=next(r for r in rows if r['id']==j['id'])
            original=doc(j['report_sha256'])
            if (sum(x==r for x in original['results'])!=1 or m.digest(r['final_tree'])!=j['final_tree_sha256']
                    or j['arm']!=r['arm']):
                raise ValueError('final result/source identity changed')
            if r.get('collection',{}).get('schema_sha256')!=p['assessment_sha256']:
                raise ValueError('assessment differs from collected result schema')
            for sha in r['final_tree'].values(): raw(sha)
        label_ids={}; seen_views=set()
        for view in mapping['views']:
            if view['view'] in seen_views: raise ValueError('duplicate human view identity')
            seen_views.add(view['view'])
            for label in view['map']:
                j=next(j for j in joins if j['id']==label['id'])
                if label['final_tree_sha256']!=j['final_tree_sha256'] or label['arm']!=j['arm']:
                    raise ValueError('label/source identity changed')
                if (view['view'],label['label']) in label_ids: raise ValueError('duplicate human label identity')
                label_ids[(view['view'],label['label'])]=j['id']
        seen=set()
        for cap in mapping['captures']:
            j=next(j for j in joins if j['id']==cap['id'])
            request=doc(cap['request_sha256']); reply=doc(cap['reply_sha256']); delivery=doc(cap['delivery_sha256'])
            raw(cap['capture_sha256'])
            if (cap['final_tree_sha256']!=j['final_tree_sha256'] or request['job_id']!=j['id']
                    or request['artifact_tree_sha256']!=j['final_tree_sha256']
                    or request['artifact_tree']!=next(r for r in rows if r['id']==j['id'])['final_tree']
                    or reply['request_sha256']!=cap['request_sha256'] or reply['request_id']!=request['request_id']
                    or delivery['request_id']!=request['request_id'] or delivery['artifact_tree_sha256']!=j['final_tree_sha256']
                    or reply['state']!=cap['state'] or reply['state_reached'] is not True
                    or reply['capture_sha256']!=cap['capture_sha256'] or delivery['capture_sha256']!=cap['capture_sha256']):
                raise ValueError('render/source/request binding changed')
            seen.add(j['id'])
        if seen!=set(ids): raise ValueError('a judged output has no bound capture')
        human=doc(p['human_judgment_sha256'])
        if human['mapping_sha256']!=p['mapping_sha256']: raise ValueError('stale human judgment mapping')
        raw(human['human_quote_sha256']); raw(human['correction_quote_sha256'])
        if not p.get('human_provenance') or p.get('labels_known') not in (True,False,None):
            raise ValueError('human provenance/label knowledge required')
        # This retained receipt format names two pair views sharing current A.
        # Derive semantic aliases from that actual mapping, never caller choice.
        alias_pairs={'base/B1':('view-1','B'),'current/shared A':('view-1','A'),'edited/B2':('view-2','B')}
        if (set(label_ids)!={('view-1','A'),('view-1','B'),('view-2','A'),('view-2','B')}
                or label_ids[('view-1','A')]!=label_ids[('view-2','A')]
                or p['human_labels']!={name:list(pair) for name,pair in alias_pairs.items()}):
            raise ValueError('human aliases contradict retained pair mapping')
        aliases={name:label_ids[pair] for name,pair in alias_pairs.items()}
        if (len(set(aliases.values()))!=3 or set(aliases.values())!=set(ids)
                or any(next(j for j in joins if j['id']==ident)['arm']!=name.split('/')[0]
                       for name,ident in aliases.items())):
            raise ValueError('human aliases contradict retained arm identities')
        selected=human['selected_visual_copy_direction']
        selected_join=next(j for j in joins if j['id']==selected['id'])
        if (aliases[human['preferred_visual_output']]!=selected['id']
                or any(selected.get(k)!=selected_join[k] for k in ('arm','report_sha256','final_tree_sha256'))):
            raise ValueError('human preferred output contradicts selected artifact')
        preferences=[]
        for relation in human['all_supported_pairwise_preferences']:
            a,b=relation.split(' over ')
            preferences.append({'preferred':aliases[a],'over':aliases[b]})
        unresolved=p['undecided_pair']
        if (human['edited_versus_current']!='undecided' or len(unresolved)!=2 or len(set(unresolved))!=2
                or set(unresolved)!=set(ids)-{selected['id']}):
            raise ValueError('partial-order/undecided judgment changed')
        requirements=p['requirements']
        if not requirements or len({r['id'] for r in requirements})!=len(requirements): raise ValueError('goal requirements missing/duplicated')
        for r in requirements:
            citation(r['goal_citation'])
            if r['goal_citation']['sha256']!=p['product_goal']['sha256']: raise ValueError('requirement not grounded in product description')
            if r['coverage'] not in ('covered','scope-mismatch','unassessed') or r['adequacy'] not in ('adequate','inadequate','unassessed'):
                raise ValueError('explicit coverage/adequacy required')
            if not r['evidence']: raise ValueError('requirement evidence/limit missing')
            for e in r['evidence']: citation(e)
            if r['adequacy']=='adequate' and r['coverage']!='covered': raise ValueError('uncovered outcome cannot pass')
        coverage_failed=any(r['coverage']=='scope-mismatch' for r in requirements)
        # Known scope failure is a terminal non-acceptance, not endless pending.
        # These human preferences alone never establish whole-product adequacy.
        return {'ready':True,'gaps':[], 'execution_complete':all(r.get('ok') is True for r in rows),
            'outcome_coverage':'failed' if coverage_failed else 'partial',
            'finished_result_acceptance':'not-accepted' if coverage_failed else 'not-established',
            'requirements':requirements,'quality_disposition':{'scope':p['judgment_scope'],'preferences':preferences,'undecided_pair':unresolved},
            'deliveries':{i:{'task_passed':None,'reviewed_artifact_adequate':None,'final_source_exactly_reviewed':False,
                'scope':'human visual/copy preference; no whole-product adequacy judgment'} for i in ids},
            'disposition':'do-not-promote-intervention; finish actual product goal' if coverage_failed else 'bounded-human-preference-only',
            'human_provenance':p['human_provenance'],'labels_known':p['labels_known'],'review_identity_authenticated':False,
            'deployment_authority':False,'adoption_authority':False,'whole_workflow_efficiency_qualified':False,
            'source_bound_current_quality':False,'scope':'Description-derived coverage and bound human rendered preference; no causal or release clearance'}
    except (KeyError,TypeError,ValueError,AttributeError,StopIteration) as error:
        gaps.append('malformed rendered outcome: '+str(error))
    return {'ready':False,'gaps':gaps,'finished_result_acceptance':'not-established','deployment_authority':False,'adoption_authority':False}


def completed_artifact_decision(report, attachment, source_bytes):
    """Consume frozen packet-bound substantive review, without granting rollout.

    Historical replays may establish reviewed-view quality while final-source
    projection or execution provenance remains limited; no backfilled proof.
    """
    if attachment.get('review_kind') == 'human-rendered-outcome':
        return rendered_outcome_decision(report, attachment, source_bytes)
    import evaluation_measurement as m
    gaps=[];assessment={};outcomes={}
    def blob(key):
        value=attachment[key];data=source_bytes.get(value)
        if not isinstance(data,bytes) or hashlib.sha256(data).hexdigest()!=value:raise ValueError(key+' bytes unavailable/changed')
        return data
    try:
        if attachment.get('output_kind') not in ('program','text'):
            gaps.append('nonvisual completed-review consumer requires explicit program/text scope; rendered capture/review remains separate')
        packet=strict_review_json(blob('packet_sha256'));review=strict_review_json(blob('review_sha256'));seal=strict_review_json(blob('review_freeze_sha256'))
        for name,value in seal.get('files',{}).items():
            data=source_bytes.get(value)
            if not isinstance(data,bytes) or hashlib.sha256(data).hexdigest()!=value:gaps.append('frozen review member missing/changed: '+name)
        native_hash=seal.get('files',{}).get(attachment.get('native_file'))
        native_data=source_bytes.get(native_hash)
        if not isinstance(native_data,bytes) or hashlib.sha256(native_data).hexdigest()!=native_hash:
            gaps.append('frozen native review receipt missing/changed')
        else:
            native=strict_review_json(native_data)
            if native.get('ok') is not True:gaps.append('reviewer runtime did not complete')
            reply=native.get('final_response')
            if not isinstance(reply,str) or not reply.strip():gaps.append('retained native judgment text missing')
            else:
                authoritative=strict_review_json(reply)
                if authoritative!=review.get('parsed'):gaps.append('parsed review contradicts retained native judgment')
                for name,value in seal.get('files',{}).items():
                    if name.upper().endswith('-RAW.TXT') or name==attachment.get('raw_judgment_file'):
                        if strict_review_json(source_bytes[value])!=authoritative:gaps.append('frozen raw judgment contradicts native reply: '+name)
        if review.get('readonly') is not True or review.get('both_sources_read') is not True:
            gaps.append('reviewer observation/read-only evidence missing')
        if not (review.get('recording_complete') is True or review.get('request_recording',{}).get('complete') is True):
            gaps.append('reviewer request recording incomplete')
        if seal.get('phase')!='before-unblinding':gaps.append('review not frozen before unblinding')
        if seal.get('files',{}).get(attachment['review_file'])!=attachment['review_sha256']:
            gaps.append('raw review differs from freeze')
        if attachment['packet_sha256'] not in (seal.get('packet_sha256'),*seal.get('files',{}).values()):
            gaps.append('review freeze does not bind packet')
        manifest=packet['files']
        for name,value in manifest.items():
            data=source_bytes.get(value)
            if not isinstance(data,bytes) or hashlib.sha256(data).hexdigest()!=value:gaps.append('packet bytes missing/changed: '+name)
        raw_results=[{key:value for key,value in row.items() if key not in ('completed_review_outcome','completed_outcome_assessment')}
                     for row in report['results']]
        if attachment.get('results_sha256')!=m.digest(raw_results):gaps.append('review attachment/result binding changed')
        if set(attachment['label_to_result'])!={'A','B'} or len(set(attachment['label_to_result'].values()))!=2:
            gaps.append('ambiguous delivery mapping')
        assessment=substantive_review(review['parsed'],manifest,source_bytes);gaps.extend(assessment['gaps'])
        for label,ident in attachment['label_to_result'].items():
            row=next(r for r in report['results'] if r['id']==ident)
            viewed={name[len(label+'/source/'):]:value for name,value in manifest.items() if name.startswith(label+'/source/')}
            exact=row.get('final_tree')==viewed
            adequate=assessment['dimensions'].get('program',{}).get('adequacy',{}).get(label)=='adequate'
            dimensions=row.get('outcome_assessment',{})
            runtime=(row.get('runtime_completed',dimensions.get('runtime_completed',row.get('native',{}).get('ok'))) is True
                and row.get('deterministic_invariants_passed',dimensions.get('deterministic_invariants_passed')) is True)
            outcomes[ident]={'reviewed_artifact_adequate':adequate,'final_source_exactly_reviewed':exact,
                'task_passed':bool(adequate and runtime) if exact and runtime else None,
                'scope':'exact final source plus recorded runtime/invariants' if exact and runtime else 'frozen reviewed view; execution/projection linkage not promoted'}
    except (KeyError,TypeError,ValueError,AttributeError,StopIteration) as error:gaps.append('malformed completed review: '+str(error))
    ready=not gaps
    if not ready:
        for row in outcomes.values():row['task_passed']=None
    return {'ready':ready,'gaps':sorted(set(gaps)),'quality_disposition':assessment.get('dimensions',{}),
        'deliveries':outcomes,'packet_source_consistent':ready,'execution_authenticated':False,
        'deployment_authority':False,'adoption_authority':False,'whole_workflow_efficiency_qualified':False,
        'legacy_efficiency':report.get('legacy_efficiency'),
        'source_bound_current_quality':bool(ready and outcomes and all(row['final_source_exactly_reviewed'] for row in outcomes.values())),
        'scope':'Bounded artifact quality; no skill-wide retirement, fresh-receiver or complete cost proof'}


def quality_tradeoff_decision(quality, policy, source_bytes):
    """Current source-bound quality preference, alongside legacy efficiency."""
    quality=quality if isinstance(quality,dict) else {}
    source_bytes=source_bytes if isinstance(source_bytes,dict) else {}
    valid=False
    if isinstance(policy,dict):
        raw=source_bytes.get(policy.get('source_sha256'))
        valid=(isinstance(raw,bytes) and hashlib.sha256(raw).hexdigest()==policy.get('source_sha256')
            and policy.get('allow_more_tokens_for_better_quality') is True
            and isinstance(policy.get('excerpt'),str) and bool(policy['excerpt'].strip())
            and policy['excerpt'] in raw.decode('utf-8',errors='replace'))
    return {'policy_source_verified':valid,'quality_recommendation_sufficient':bool(valid and quality.get('ready') and quality.get('source_bound_current_quality',True)),
        'quality_disposition':quality.get('quality_disposition'), 'legacy_efficiency_independent':True,
        'unknown_cost_is_zero':False,'deployment_authority':False,'adoption_authority':False}

