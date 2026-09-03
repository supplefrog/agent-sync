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
    from artifact_hash import candidate_hash
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from artifact_hash import candidate_hash


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
) -> dict[str, object]:
    return {
        "schema_version": 2,
        "suite": report["suite"],
        "host": report["agent"],
        "host_version": compact_version(report["agent_version"]),
        "judge_host": report.get("judge_agent"),
        "judge_version": compact_version(report.get("judge_version")),
        "run_timestamp_utc": report["timestamp_utc"],
        "status": status,
        "artifacts": report["artifacts"],
        "effective_stack": report.get("effective_stack"),
        "decision_rule": report.get("decision_rule"),
        "seeds": report.get("seeds"),
        "run_count": report.get("run_count"),
        "rollback": report.get("rollback"),
        "session_lifecycle": compact_session_lifecycle(report.get("session_lifecycle")),
        "result": report["summary"],
        "cases": [
            {"id": item["id"], "kind": item.get("kind"), "trial": item.get("trial"), "winner": item["winner"]}
            for item in report["results"]
        ],
        "decision": decision,
        "decision_detail": report.get("decision"),
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
    parser.add_argument("--status", required=True)
    parser.add_argument("--decision", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)

    report = json.loads(args.report.read_text(encoding="utf-8"))
    artifacts = report.get("artifacts") or {}
    if args.artifact_policy == "current":
        if args.candidate is None or args.suite is None:
            parser.error("--candidate and --suite are required for current artifact validation")
        expected = {
            "candidate_sha256": candidate_hash(args.candidate),
            "suite_sha256": sha256(args.suite),
            "harness_sha256": sha256(args.harness),
        }
        mismatches = [key for key, value in expected.items() if artifacts.get(key) != value]
        if mismatches:
            print("ERROR stale evaluation artifacts: " + ", ".join(mismatches), file=sys.stderr)
            return 1
        artifact_validation = "current-files"
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
        sha256(args.report),
        artifact_validation,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
