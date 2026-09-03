#!/usr/bin/env python
"""Fail-closed integrity verification for one Agent Signal evaluation report."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from artifact_hash import candidate_hash

REPO = Path(__file__).resolve().parents[1]


def _runs(value: Any):
    if isinstance(value, dict):
        if {"ok", "returncode", "route_attestation"} <= set(value):
            yield value
        for child in value.values():
            yield from _runs(child)
    elif isinstance(value, list):
        for child in value:
            yield from _runs(child)


def verify_report(
    report_path: Path,
    suite_path: Path,
    candidate_path: Path,
    baseline_path: Path,
    *,
    agent: str,
    decision: str,
    model: str,
    provider: str,
    reasoning: str,
    tool_policy: str,
    equivalence_group: str,
    min_trials: int,
    max_trials: int,
    max_agent_runs: int,
) -> dict[str, Any]:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    runs = list(_runs(report.get("results", [])))
    errors: list[str] = []
    expected_harness_failure = decision == "harness-failure"

    def require(condition: bool, message: str) -> None:
        if not condition:
            errors.append(message)

    expected_candidate = candidate_path.resolve()
    expected_baseline = baseline_path.resolve()
    require(Path(report.get("candidate", "")).resolve() == expected_candidate, "candidate path mismatch")
    require(Path(report.get("baseline_candidate", "")).resolve() == expected_baseline, "baseline path mismatch")

    artifacts = report.get("artifacts", {})
    require(artifacts.get("candidate_sha256") == candidate_hash(expected_candidate), "candidate hash mismatch")
    require(artifacts.get("baseline_candidate_sha256") == candidate_hash(expected_baseline), "baseline hash mismatch")
    require(
        artifacts.get("suite_sha256") == hashlib.sha256(suite_path.read_bytes()).hexdigest(),
        "suite hash mismatch",
    )
    require(
        artifacts.get("harness_sha256") == hashlib.sha256((REPO / "tools" / "eval.py").read_bytes()).hexdigest(),
        "harness hash mismatch",
    )

    stack = report.get("effective_stack", {})
    expected_stack = {
        "model": model,
        "provider": provider,
        "reasoning": reasoning,
        "tool_policy": tool_policy,
        "equivalence_group": equivalence_group,
    }
    for key, value in expected_stack.items():
        require(stack.get(key) == value, f"effective stack mismatch: {key}")
    require(bool(stack.get("route_attestation_required")), "route attestation was not required")

    require(report.get("status") == "complete", "report status is not complete")
    require(report.get("agent") == agent, "agent mismatch")
    require(report.get("decision", {}).get("decision") == decision, "decision mismatch")
    require(bool(runs), "no physical runs found")
    if not expected_harness_failure:
        require(all(run.get("ok") for run in runs), "one or more final runs failed")
        require(
            all(run.get("route_attestation", {}).get("required") and run.get("route_attestation", {}).get("ok") for run in runs),
            "one or more routes are unattested",
        )
    rule = report.get("decision_rule", {})
    expected_rule = {
        "min_trials": min_trials,
        "max_trials": max_trials,
        "max_agent_runs": max_agent_runs,
    }
    for key, value in expected_rule.items():
        require(rule.get(key) == value, f"decision rule mismatch: {key}")

    physical_attempts = sum(int(run.get("attempt_count", 1)) for run in runs)
    require(report.get("run_count") == physical_attempts, "physical run count mismatch")
    hard_cap = int(rule.get("max_agent_runs", 0))
    require(max_agent_runs > 0 and physical_attempts <= max_agent_runs, "physical run budget exceeded or missing")
    if not expected_harness_failure:
        require(not any(run.get("run_budget_exhausted") for run in runs), "physical run budget exhausted")

    results = report.get("results", [])
    schema_version = int(report.get("schema_version", 0))
    computed = {
        "candidate_losses": sum(item.get("winner") == "baseline" for item in results),
        "candidate_hard_failures": sum(
            not bool(
                item.get("hard_pass", {}).get(
                    "candidate",
                    item.get("candidate_hard_pass", item.get("candidate_receipt_pass", False)),
                )
            )
            for item in results
        ),
        "judge_disagreements": sum(bool(item.get("judge_disagreement")) for item in results),
        "candidate_receipt_failures": sum(
            not bool(item.get("candidate_receipt_pass", False)) for item in results
        ) if schema_version >= 3 else None,
        "route_attestation_failures": sum(
            not bool(run.get("route_attestation", {}).get("ok")) for run in runs
        ),
    }
    summary = report.get("summary", {})
    for key, value in computed.items():
        if value is not None:
            require(summary.get(key) == value, f"summary {key} mismatch")
    if expected_harness_failure:
        harness_failure_evidence = (
            any(not run.get("ok") for run in runs)
            or computed["route_attestation_failures"] > 0
            or any(run.get("run_budget_exhausted") for run in runs)
            or int(summary.get("judge_errors", 0)) > 0
        )
        require(harness_failure_evidence, "harness-failure decision lacks failure evidence")
    else:
        require(computed["route_attestation_failures"] == 0, "summary reports route failures")

    lifecycle = report.get("session_lifecycle", {})
    created = lifecycle.get("created", [])
    deleted = lifecycle.get("deleted", [])
    require(created == deleted, "evaluator-created sessions were not exactly deleted")
    require(not lifecycle.get("remaining"), "evaluator sessions remain")
    require(not lifecycle.get("errors"), "session cleanup reported errors")

    hermes_runs = [
        run for run in runs
        if "tool_calls_count" in run.get("route_attestation", {}).get("observed", {})
    ]
    if agent == "hermes":
        require(bool(hermes_runs), "no Hermes generation runs found")
    if tool_policy == "none" and hermes_runs:
        require(
            all(run["route_attestation"]["observed"].get("tool_calls_count") == 0 for run in hermes_runs),
            "Hermes tool calls observed under none policy",
        )

    if decision == "admit":
        require(computed["candidate_losses"] == 0, "candidate loss present")
        require(computed["candidate_hard_failures"] == 0, "candidate hard failure present")
        require(computed["judge_disagreements"] == 0, "unresolved judge disagreement present")
        if schema_version >= 3:
            require(computed["candidate_receipt_failures"] == 0, "candidate receipt failure present")

    return {
        "ok": not errors,
        "report": str(report_path.resolve()),
        "agent": report.get("agent"),
        "decision": report.get("decision", {}).get("decision"),
        "runs_found": len(runs),
        "physical_attempts": physical_attempts,
        "hard_cap": hard_cap,
        "hermes_runs": len(hermes_runs),
        "created_sessions": len(created),
        "computed_summary": computed,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--suite", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--agent", choices=("hermes", "codex"), required=True)
    parser.add_argument("--decision", choices=("admit", "reject", "inconclusive", "harness-failure"), required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--provider", required=True)
    parser.add_argument("--reasoning", required=True)
    parser.add_argument("--tool-policy", choices=("none", "safe", "full"), required=True)
    parser.add_argument("--equivalence-group", required=True)
    parser.add_argument("--min-trials", type=int, required=True)
    parser.add_argument("--max-trials", type=int, required=True)
    parser.add_argument("--max-agent-runs", type=int, required=True)
    args = parser.parse_args()
    result = verify_report(
        args.report,
        args.suite,
        args.candidate,
        args.baseline,
        agent=args.agent,
        decision=args.decision,
        model=args.model,
        provider=args.provider,
        reasoning=args.reasoning,
        tool_policy=args.tool_policy,
        equivalence_group=args.equivalence_group,
        min_trials=args.min_trials,
        max_trials=args.max_trials,
        max_agent_runs=args.max_agent_runs,
    )
    print(json.dumps(result, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
