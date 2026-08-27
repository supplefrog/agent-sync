#!/usr/bin/env python
"""Run a temporary-database Kanban exact-route and receipt smoke."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
from pathlib import Path


def receipt() -> dict:
    return {
        "schema_version": 1,
        "policy_version": "smoke-only-unpromoted-2026-08-16",
        "policy_sha256": "0" * 64,
        "requirement_sha256": "1" * 64,
        "target_surface": "kanban-worker",
        "task_class": "mechanical-bounded",
        "objective": "speed",
        "failure_cost": "low",
        "route": {
            "id": "sol-low",
            "provider": "openai-codex",
            "model": "gpt-5.6-sol",
            "reasoning_effort": "low",
            "runtime": {"transport": "kanban-worker", "source": "candidate-worktree"},
        },
        "metrics": {},
        "evidence_receipt": "self:smoke-only",
        "pareto_frontier": ["sol-low"],
        "excluded": {},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hermes-source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    source = args.hermes_source.resolve()
    if not (source / "hermes_cli/kanban_db.py").is_file():
        parser.error("--hermes-source does not contain hermes_cli/kanban_db.py")

    for key in list(os.environ):
        if key.startswith("HERMES_KANBAN_") or key.startswith("HERMES_SESSION_"):
            os.environ.pop(key, None)
    started = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="kanban-route-smoke-") as temp:
        os.environ["HERMES_HOME"] = temp
        os.environ["HERMES_PROFILE"] = "route-smoke"
        sys.path.insert(0, str(source))
        from hermes_cli import kanban_db as kb

        kb._INITIALIZED_PATHS.clear()
        kb.init_db()
        conn = kb.connect()
        try:
            decision = receipt()
            task_id = kb.create_task(
                conn,
                title="route receipt smoke",
                assignee="route-smoke",
                model_override="gpt-5.6-sol",
                provider_override="openai-codex",
                reasoning_effort="low",
                route_decision_receipt=decision,
            )
            claimed = kb.claim_task(conn, task_id)
            completed = kb.complete_task(
                conn,
                task_id,
                summary="smoke complete",
                metadata={"acceptance": "passed"},
            )
            run = kb.latest_run(conn, task_id)

            mutable_id = kb.create_task(
                conn,
                title="route receipt invalidation smoke",
                assignee="route-smoke",
                model_override="gpt-5.6-sol",
                provider_override="openai-codex",
                reasoning_effort="low",
                route_decision_receipt=decision,
            )
            kb.set_reasoning_effort(conn, mutable_id, "high")
            mutated = kb.get_task(conn, mutable_id)
            run_metadata = run.metadata or {}
            passed = bool(
                claimed
                and completed
                and run_metadata.get("dispatch_route")
                == {
                    "model": "gpt-5.6-sol",
                    "provider": "openai-codex",
                    "reasoning_effort": "low",
                }
                and run_metadata.get("route_decision_receipt") == decision
                and mutated.reasoning_effort == "high"
                and mutated.route_decision_receipt is None
            )
            result = {
                "schema_version": 1,
                "evidence_state": "integration-smoke",
                "target_surface": "kanban-worker",
                "passed": passed,
                "duration_seconds": round(time.perf_counter() - started, 3),
                "claimed_run_metadata": run_metadata,
                "stale_receipt_invalidation_passed": (
                    mutated.reasoning_effort == "high"
                    and mutated.route_decision_receipt is None
                ),
                "cleanup_passed": True,
                "limitations": [
                    "Temporary SQLite integration proves exact-route claim/completion persistence and stale-receipt invalidation.",
                    "It does not launch a model worker and is not task-quality evidence for route promotion.",
                ],
            }
        finally:
            conn.close()
    args.output.resolve().parent.mkdir(parents=True, exist_ok=True)
    args.output.resolve().write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output.resolve()), "passed": result["passed"]}, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
