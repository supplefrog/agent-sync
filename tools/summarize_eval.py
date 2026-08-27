#!/usr/bin/env python
"""Create a compact public evidence summary from an ignored raw evaluation report."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

try:
    from artifact_hash import candidate_hash
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from artifact_hash import candidate_hash


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compact(report: dict[str, object], status: str, decision: str) -> dict[str, object]:
    return {
        "schema_version": 2,
        "suite": report["suite"],
        "host": report["agent"],
        "host_version": report["agent_version"],
        "judge_host": report.get("judge_agent"),
        "judge_version": report.get("judge_version"),
        "run_timestamp_utc": report["timestamp_utc"],
        "status": status,
        "artifacts": report["artifacts"],
        "effective_stack": report.get("effective_stack"),
        "decision_rule": report.get("decision_rule"),
        "seeds": report.get("seeds"),
        "run_count": report.get("run_count"),
        "rollback": report.get("rollback"),
        "session_lifecycle": report.get("session_lifecycle"),
        "result": report["summary"],
        "cases": [
            {"id": item["id"], "kind": item.get("kind"), "trial": item.get("trial"), "winner": item["winner"]}
            for item in report["results"]
        ],
        "decision": decision,
        "raw_report_committed": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("report", type=Path)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--suite", type=Path, required=True)
    parser.add_argument("--harness", type=Path, default=Path(__file__).with_name("eval.py"))
    parser.add_argument("--status", required=True)
    parser.add_argument("--decision", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)

    report = json.loads(args.report.read_text(encoding="utf-8"))
    artifacts = report.get("artifacts") or {}
    expected = {
        "candidate_sha256": candidate_hash(args.candidate),
        "suite_sha256": sha256(args.suite),
        "harness_sha256": sha256(args.harness),
    }
    mismatches = [key for key, value in expected.items() if artifacts.get(key) != value]
    if mismatches:
        print("ERROR stale evaluation artifacts: " + ", ".join(mismatches), file=sys.stderr)
        return 1

    summary = compact(report, args.status, args.decision)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
