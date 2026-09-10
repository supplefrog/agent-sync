#!/usr/bin/env python
"""Fail-closed integrity verification for one Agent Sync evaluation report."""

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

from artifact_hash import candidate_hash, freeze_candidate, harness_hash
from evaluation_evidence import validate_report

REPO = Path(__file__).resolve().parents[1]


def verify_report(
    report_path: Path,
    suite_path: Path,
    candidate_path: Path,
    baseline_path: Path | None = None,
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
    report_raw = report_path.read_bytes()
    report = json.loads(report_raw.decode("utf-8"))
    suite_raw = suite_path.read_bytes()
    suite = json.loads(suite_raw.decode("utf-8"))
    validation = validate_report(report, suite)
    errors = list(validation["errors"])

    def require(condition: bool, message: str) -> None:
        if not condition:
            errors.append(message)

    expected_candidate = candidate_path.resolve()
    expected_baseline = baseline_path.resolve() if baseline_path is not None else None
    require(Path(report.get("candidate") or "").resolve() == expected_candidate, "candidate path mismatch")
    if expected_baseline is None:
        require(report.get("baseline_candidate") is None, "baseline path mismatch")
    else:
        require(Path(report.get("baseline_candidate") or "").resolve() == expected_baseline, "baseline path mismatch")
    artifacts = report.get("artifacts", {})
    candidate_snapshot = freeze_candidate(expected_candidate)
    baseline_snapshot = freeze_candidate(expected_baseline) if expected_baseline is not None else {"package_sha256": hashlib.sha256(b"").hexdigest(), "prompt_sha256": hashlib.sha256(b"").hexdigest()}
    require(artifacts.get("candidate_sha256") == candidate_snapshot["package_sha256"], "candidate hash mismatch")
    require(artifacts.get("baseline_candidate_sha256") == baseline_snapshot["package_sha256"], "baseline hash mismatch")
    require(artifacts.get("candidate_prompt_sha256") == candidate_snapshot["prompt_sha256"], "candidate prompt hash mismatch")
    require(artifacts.get("baseline_prompt_sha256") == baseline_snapshot["prompt_sha256"], "baseline prompt hash mismatch")
    require(artifacts.get("suite_sha256") == hashlib.sha256(suite_raw).hexdigest(), "suite hash mismatch")
    require(artifacts.get("harness_sha256") == harness_hash(REPO / "tools" / "eval.py"), "harness hash mismatch")
    stack = report.get("effective_stack", {})
    expected_stack = {
        "model": model, "provider": provider, "reasoning": reasoning,
        "tool_policy": tool_policy, "equivalence_group": equivalence_group,
    }
    for key, value in expected_stack.items():
        require(stack.get(key) == value, f"effective stack mismatch: {key}")
    require(report.get("agent") == agent, "agent mismatch")
    require(report.get("decision", {}).get("decision") == decision, "decision mismatch")
    rule = report.get("decision_rule", {})
    for key, value in {"min_trials": min_trials, "max_trials": max_trials, "max_agent_runs": max_agent_runs}.items():
        require(rule.get(key) == value, f"decision rule mismatch: {key}")
    runs = validation["runs"]
    return {
        "ok": not errors,
        "integrity_valid": not errors,
        "evidence_complete": validation["evidence_complete"],
        "positive_decision_sufficient": validation["positive_decision_sufficient"] and not errors,
        "operational_ok": not validation["operational_errors"],
        "operational_errors": validation["operational_errors"],
        "scope": validation["scope"],
        "limitations": validation["limitations"],
        "report": str(report_path.resolve()),
        "report_sha256": hashlib.sha256(report_raw).hexdigest(),
        "agent": report.get("agent"),
        "status": report.get("status"),
        "decision": report.get("decision", {}).get("decision"),
        "computed_decision": validation["computed_decision"],
        "runs_found": len(runs),
        "physical_attempts": validation["physical_attempts"],
        "unpaired_attempts": validation["unpaired_attempts"],
        "hard_cap": rule.get("max_agent_runs"),
        "hermes_runs": validation["host_run_counts"]["hermes"],
        "codex_runs": validation["host_run_counts"]["codex"],
        "created_sessions": len(report.get("session_lifecycle", {}).get("created", [])),
        "computed_summary": validation["computed_summary"],
        "errors": sorted(set(errors)),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--suite", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--agent", choices=("hermes", "codex"), required=True)
    parser.add_argument("--decision", choices=("admit", "reject", "retire", "retain", "inconclusive", "harness-failure"), required=True)
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
