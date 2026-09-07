#!/usr/bin/env python
"""Aggregate host evaluation reports into one no-regression gate decision."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))
from evaluation_evidence import ARTIFACT_KEYS, STACK_KEYS, validate_report


def evidence_errors(report: dict[str, Any], mode: str, suite: dict[str, Any] | None = None) -> list[str]:
    """Validate recorded consistency against an independently supplied suite."""
    errors = validate_report(report, suite)["errors"]
    if report.get("decision_mode") != mode:
        errors.append("decision mode mismatch")
    return sorted(set(errors))


def aggregate(
    reports: list[dict[str, Any]],
    required_hosts: list[str],
    mode: str,
    rollback: str,
    report_hashes: dict[str, str],
    *,
    suite: dict[str, Any] | None = None,
    suite_sha256: str | None = None,
) -> dict[str, Any]:
    if not reports:
        raise ValueError("at least one report is required")
    hosts = [str(report.get("agent")) for report in reports]
    if len(hosts) != len(set(hosts)):
        raise ValueError("one report per host is required")
    anchor = reports[0]
    artifact_keys = (*ARTIFACT_KEYS, "candidate_identity_format", "baseline_candidate_identity_format")
    anchor_artifacts = anchor.get("artifacts", {})
    mismatches: list[str] = []
    validations = {str(report.get("agent")): validate_report(report, suite) for report in reports}
    invalid = {host: list(validation["errors"]) for host, validation in validations.items()}
    for report in reports:
        if report.get("decision_mode") != mode:
            invalid[str(report.get("agent"))].append("decision mode mismatch")
    invalid = {host: errors for host, errors in invalid.items() if errors}
    if suite_sha256 is None:
        for host in hosts:
            invalid.setdefault(host, []).append("independently computed suite hash is required")
    for report in reports:
        if suite_sha256 is not None and report.get("artifacts", {}).get("suite_sha256") != suite_sha256:
            invalid.setdefault(str(report.get("agent")), []).append("suite hash mismatch")
    for report in reports[1:]:
        if report.get("judge_agent") != anchor.get("judge_agent"):
            mismatches.append(f"{report.get('agent')}:judge_agent")
        if report.get("decision_rule") != anchor.get("decision_rule"):
            mismatches.append(f"{report.get('agent')}:decision_rule")
        for key in artifact_keys:
            if report.get("artifacts", {}).get(key) != anchor_artifacts.get(key):
                mismatches.append(f"{report.get('agent')}:{key}")
        for key in STACK_KEYS:
            if report.get("effective_stack", {}).get(key) != anchor.get("effective_stack", {}).get(key):
                mismatches.append(f"{report.get('agent')}:effective_stack.{key}")
    groups = {report.get("effective_stack", {}).get("equivalence_group") for report in reports}
    if None in groups or len(groups) != 1:
        mismatches.append("effective_stack.equivalence_group")
    for host in hosts:
        if not re.fullmatch(r"[0-9a-f]{64}", str(report_hashes.get(host, ""))):
            mismatches.append(f"{host}:report_sha256")

    host_decisions = {
        str(report["agent"]): str(report.get("decision", {}).get("decision", "harness-failure"))
        for report in reports
    }
    missing = sorted(set(required_hosts) - set(host_decisions))
    success = {"admit"} if mode == "admission" else {"retire"}
    explicit_negative = {"reject"} if mode == "admission" else {"retain"}
    regressions = sorted(host for host, decision in host_decisions.items() if decision in explicit_negative)
    inconclusive_hosts = sorted(
        host
        for host, decision in host_decisions.items()
        if decision not in success and decision not in explicit_negative
    )
    insufficient_positive_hosts = sorted(host for host, validation in validations.items()
                                        if host_decisions[host] in success and not validation["positive_decision_sufficient"])
    operational_errors = {host: validation["operational_errors"] for host, validation in validations.items() if validation["operational_errors"]}
    scopes = {host: validation["scope"] for host, validation in validations.items()}
    for host, scope in scopes.items():
        if scope != scopes[hosts[0]]:
            mismatches.append(f"{host}:evaluation_scope")
    if mismatches or missing or invalid:
        decision = "inconclusive"
    elif regressions:
        decision = "reject" if mode == "admission" else "retain"
    elif inconclusive_hosts or insufficient_positive_hosts or operational_errors:
        decision = "inconclusive"
    else:
        decision = "admit" if mode == "admission" else "retire"
    return {
        "schema_version": 1,
        "timestamp_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "mode": mode,
        "suite": anchor.get("suite"),
        "required_hosts": required_hosts,
        "host_decisions": host_decisions,
        "missing_hosts": missing,
        "regression_hosts": regressions,
        "inconclusive_hosts": inconclusive_hosts,
        "insufficient_positive_hosts": insufficient_positive_hosts,
        "operational_ok": not operational_errors,
        "operational_errors": operational_errors,
        "scope": scopes[hosts[0]] if all(scope == scopes[hosts[0]] for scope in scopes.values()) else None,
        "host_scopes": scopes,
        "equivalence_group": next(iter(groups)) if len(groups) == 1 else None,
        "artifact_mismatches": sorted(set(mismatches)),
        "invalid_evidence": invalid,
        "evidence_status": {
            host: {
                "integrity_valid": host not in invalid,
                "evidence_complete": validation["evidence_complete"],
                "computed_decision": validation["computed_decision"],
                "positive_decision_sufficient": validation["positive_decision_sufficient"] and host not in invalid,
                "operational_errors": validation["operational_errors"],
                "scope": validation["scope"],
                "limitations": validation["limitations"],
            }
            for host, validation in validations.items()
        },
        "artifacts": anchor_artifacts,
        "report_hash_inputs": {host: report_hashes.get(host) for host in sorted(hosts)},
        "rollback": rollback,
        "decision": decision,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reports", nargs="+", type=Path)
    parser.add_argument("--suite", type=Path, required=True)
    parser.add_argument("--required-host", action="append", dest="required_hosts", required=True)
    parser.add_argument("--mode", choices=("admission", "retirement"), default="admission")
    parser.add_argument("--rollback", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    reports: list[dict[str, Any]] = []
    report_hashes: dict[str, str] = {}
    for path in args.reports:
        raw = path.read_bytes()
        report = json.loads(raw.decode("utf-8"))
        reports.append(report)
        report_hashes[str(report.get("agent"))] = hashlib.sha256(raw).hexdigest()
    suite_raw = args.suite.read_bytes()
    suite = json.loads(suite_raw.decode("utf-8"))
    result = aggregate(reports, args.required_hosts, args.mode, args.rollback, report_hashes,
                       suite=suite, suite_sha256=hashlib.sha256(suite_raw).hexdigest())
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"decision": result["decision"], "out": str(args.out.resolve())}, indent=2))
    return 0 if result["decision"] in {"admit", "retire"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
