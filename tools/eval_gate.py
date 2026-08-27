#!/usr/bin/env python
"""Aggregate host evaluation reports into one no-regression gate decision."""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Any


def aggregate(
    reports: list[dict[str, Any]],
    required_hosts: list[str],
    mode: str,
    rollback: str,
) -> dict[str, Any]:
    if not reports:
        raise ValueError("at least one report is required")
    hosts = [str(report.get("agent")) for report in reports]
    if len(hosts) != len(set(hosts)):
        raise ValueError("one report per host is required")
    anchor = reports[0]
    artifact_keys = ("candidate_sha256", "baseline_candidate_sha256", "suite_sha256", "harness_sha256")
    anchor_artifacts = anchor.get("artifacts", {})
    mismatches: list[str] = []
    for report in reports[1:]:
        for key in artifact_keys:
            if report.get("artifacts", {}).get(key) != anchor_artifacts.get(key):
                mismatches.append(f"{report.get('agent')}:{key}")
    groups = {report.get("effective_stack", {}).get("equivalence_group") for report in reports}
    if None in groups or len(groups) != 1:
        mismatches.append("effective_stack.equivalence_group")

    host_decisions = {
        str(report["agent"]): str(report.get("decision", {}).get("decision", "harness-failure"))
        for report in reports
    }
    missing = sorted(set(required_hosts) - set(host_decisions))
    success = {"admit"} if mode == "admission" else {"retire"}
    regressions = sorted(host for host, decision in host_decisions.items() if decision not in success)
    if mismatches or missing:
        decision = "inconclusive"
    elif regressions:
        decision = "reject" if mode == "admission" else "retain"
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
        "equivalence_group": next(iter(groups)) if len(groups) == 1 else None,
        "artifact_mismatches": sorted(set(mismatches)),
        "artifacts": anchor_artifacts,
        "report_hash_inputs": [str(report.get("timestamp_utc")) for report in reports],
        "rollback": rollback,
        "decision": decision,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reports", nargs="+", type=Path)
    parser.add_argument("--required-host", action="append", dest="required_hosts", required=True)
    parser.add_argument("--mode", choices=("admission", "retirement"), default="admission")
    parser.add_argument("--rollback", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    reports = [json.loads(path.read_text(encoding="utf-8")) for path in args.reports]
    result = aggregate(reports, args.required_hosts, args.mode, args.rollback)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"decision": result["decision"], "out": str(args.out.resolve())}, indent=2))
    return 0 if result["decision"] in {"admit", "retire"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
