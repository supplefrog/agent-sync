#!/usr/bin/env python
"""Create a compact public evidence summary from an ignored raw evaluation report."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

try:
    from artifact_hash import candidate_hash, freeze_candidate, harness_hash
    from evaluation_evidence import validate_report
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from artifact_hash import candidate_hash, freeze_candidate, harness_hash
    from evaluation_evidence import validate_report


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compact_session_lifecycle(value: object) -> dict[str, object] | None:
    if not isinstance(value, dict):
        return None
    created = value.get("created", [])
    protected = value.get("protected", [])
    deleted = value.get("deleted", [])
    remaining = value.get("remaining", [])
    errors = value.get("errors", [])
    counts = {
        "created_count": len(created) if isinstance(created, list) else 0,
        "protected_count": len(protected) if isinstance(protected, list) else 0,
        "deleted_count": len(deleted) if isinstance(deleted, list) else 0,
        "remaining_count": len(remaining) if isinstance(remaining, list) else 0,
        "error_count": len(errors) if isinstance(errors, list) else 0,
    }
    return {
        "policy": value.get("policy"),
        **counts,
        "clean": counts["remaining_count"] == 0 and counts["error_count"] == 0,
    }


def compact_version(value: object) -> object:
    if not isinstance(value, str):
        return value
    return value.splitlines()[0].strip()


def compact(
    report: dict[str, object],
    status: str,
    decision: str,
    raw_report_sha256: str | None = None,
    artifact_validation: str = "current-files",
    validation: dict[str, object] | None = None,
) -> dict[str, object]:
    validated = bool(validation is not None and not validation.get("errors")
                     and validation.get("evidence_complete") is True
                     and artifact_validation == "current-files")
    detail = dict(validation.get("computed_decision") or {}) if validated else None
    operational_errors = list(validation.get("operational_errors", [])) if validation else []
    if detail and detail.get("decision") in ("admit", "retire") and (
        operational_errors or validation.get("positive_decision_sufficient") is not True
    ):
        detail = {"decision": "inconclusive", "reason": "positive publication blocked by incomplete or failed operational evidence"}
    stack = report.get("effective_stack") or {}
    candidate = (report.get("input_snapshot") or {}).get("candidate") or {}
    selected = report.get("selected_case_ids", [])
    suite_ids = [item.get("id") for item in report.get("suite_cases", []) if isinstance(item, dict)]
    scope = validation.get("scope") if validation else None
    if not scope:
        lane = stack.get("runtime_lane", "historical-unspecified")
        scope = {"runtime_lane": lane, "evaluated_projection": candidate.get("projection", "historical-unspecified"),
                 "package_behavior_exercised": False if lane == "inline-text-no-tools-v1" else None,
                 "selected_case_ids": selected, "suite_case_ids": suite_ids,
                 "full_suite": bool(suite_ids) and set(selected) == set(suite_ids)}
    return {
        "schema_version": 3,
        "suite": report["suite"],
        "host": report["agent"],
        "host_version": compact_version(report["agent_version"]),
        "judge_host": report.get("judge_agent"),
        "judge_version": compact_version(report.get("judge_version")),
        "run_timestamp_utc": report["timestamp_utc"],
        "status": ("operational-failure" if operational_errors else "evidence-validated") if validated else "recorded-unvalidated",
        "editorial_status": status,
        "recommendation": decision,
        "artifacts": report["artifacts"],
        "effective_stack": report.get("effective_stack"),
        "decision_rule": report.get("decision_rule"),
        "seeds": report.get("seeds"),
        "run_count": report.get("run_count"),
        "rollback": report.get("rollback"),
        "session_lifecycle": compact_session_lifecycle(report.get("session_lifecycle")),
        "result": validation["computed_summary"] if validated else report["summary"],
        "cases": [
            {"id": item["id"], "kind": item.get("kind"), "trial": item.get("trial"), "winner": item["winner"]}
            for item in report["results"]
        ],
        "decision": detail.get("decision") if detail else None,
        "decision_detail": detail,
        "recorded_decision_detail": report.get("decision"),
        "scope": scope,
        "positive_decision_sufficient": bool(validated and not operational_errors and validation.get("positive_decision_sufficient")),
        "operational_errors": operational_errors,
        "limitations": ["Recorded evidence consistency does not authenticate execution or provider-resolved model identity.",
                        "A package hash identifies accompanying files; inline-text evaluation does not exercise packaged scripts or tools."],
        "artifact_validation": artifact_validation,
        "raw_report_sha256": raw_report_sha256,
        "raw_report_committed": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("report", type=Path)
    parser.add_argument("--candidate", type=Path)
    parser.add_argument("--suite", type=Path)
    parser.add_argument("--harness", type=Path, default=Path(__file__).with_name("eval.py"))
    parser.add_argument("--artifact-policy", choices=("current", "recorded"), default="current")
    parser.add_argument("--status", default="", help="editorial label only; never overrides the machine status")
    parser.add_argument("--decision", default="", help="editorial recommendation only; never overrides the evidence decision")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)

    report_raw = args.report.read_bytes()
    report = json.loads(report_raw.decode("utf-8"))
    artifacts = report.get("artifacts") or {}
    validation = None
    if args.artifact_policy == "current":
        if args.candidate is None or args.suite is None:
            parser.error("--candidate and --suite are required for current artifact validation")
        candidate = freeze_candidate(args.candidate)
        suite_raw = args.suite.read_bytes()
        expected = {
            "candidate_sha256": candidate["package_sha256"],
            "candidate_prompt_sha256": candidate["prompt_sha256"],
            "suite_sha256": hashlib.sha256(suite_raw).hexdigest(),
            "harness_sha256": harness_hash(args.harness),
        }
        mismatches = [key for key, value in expected.items() if artifacts.get(key) != value]
        if mismatches:
            print("ERROR stale evaluation artifacts: " + ", ".join(mismatches), file=sys.stderr)
            return 1
        artifact_validation = "current-files"
        validation = validate_report(report, json.loads(suite_raw.decode("utf-8")))
        if validation["errors"]:
            print("ERROR invalid evaluation evidence: " + "; ".join(validation["errors"]), file=sys.stderr)
            return 1
    else:
        required_hashes = ("candidate_sha256", "suite_sha256", "harness_sha256")
        invalid = [
            key for key in required_hashes
            if not re.fullmatch(r"[0-9a-f]{64}", str(artifacts.get(key, "")))
        ]
        if invalid:
            print("ERROR invalid recorded artifact hashes: " + ", ".join(invalid), file=sys.stderr)
            return 1
        artifact_validation = "recorded-hashes-only"

    summary = compact(
        report,
        args.status,
        args.decision,
        hashlib.sha256(report_raw).hexdigest(),
        artifact_validation,
        validation,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
