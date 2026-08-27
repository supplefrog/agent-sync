#!/usr/bin/env python
"""Exercise staged Hermes delegate_task exact-route and receipt propagation once."""

from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock


def parent_agent() -> MagicMock:
    parent = MagicMock()
    parent.base_url = ""
    parent.api_key = ""
    parent.provider = "openai-codex"
    parent.api_mode = "codex_responses"
    parent.model = "gpt-5.6-sol"
    parent.platform = "cli"
    parent.providers_allowed = None
    parent.providers_ignored = None
    parent.providers_order = None
    parent.provider_sort = None
    parent._session_db = None
    parent._credential_pool = None
    parent._provider_bundle = None
    parent._delegate_depth = 0
    parent._active_children = []
    parent._active_children_lock = threading.Lock()
    parent._print_fn = None
    parent.tool_progress_callback = None
    parent.thinking_callback = None
    parent.session_id = "route-eval-parent"
    parent._current_turn_id = "route-eval"
    return parent


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hermes-source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--timeout", type=float, default=300)
    args = parser.parse_args()
    source = args.hermes_source.resolve()
    if not (source / "tools/delegate_tool.py").is_file():
        parser.error("--hermes-source does not contain tools/delegate_tool.py")
    for key in list(os.environ):
        if key.startswith("HERMES_KANBAN_") or key in {
            "HERMES_SESSION_ID",
            "HERMES_SESSION_KEY",
            "HERMES_DELEGATED_CHILD",
        }:
            os.environ.pop(key, None)
    sys.path.insert(0, str(source))

    from tools.async_delegation import get_durable_delegation
    from tools.delegate_tool import delegate_task

    receipt = {
        "schema_version": 1,
        "policy_version": "smoke-only-unpromoted-2026-08-15",
        "policy_sha256": "0" * 64,
        "requirement_sha256": "1" * 64,
        "target_surface": "hermes-delegate",
        "task_class": "mechanical-bounded",
        "objective": "speed",
        "failure_cost": "low",
        "route": {
            "id": "luna-high",
            "provider": "openai-codex",
            "model": "gpt-5.6-luna",
            "reasoning_effort": "high",
            "runtime": {"transport": "hermes-delegate", "source": "candidate-worktree"},
        },
        "metrics": {},
        "evidence_receipt": "self:smoke-only",
        "pareto_frontier": ["luna-high"],
        "excluded": {},
    }
    started = time.perf_counter()
    dispatched = json.loads(
        delegate_task(
            goal="Return exactly this JSON object and no prose: {\"value\":42}",
            context="This is a bounded transport smoke. Do not use tools.",
            model="gpt-5.6-luna",
            provider="openai-codex",
            reasoning_effort="high",
            decision_receipt=receipt,
            parent_agent=parent_agent(),
        )
    )
    delegation_id = dispatched.get("delegation_id")
    durable = None
    entries = dispatched.get("results") or []
    durable_state = "completed-inline" if entries else None
    if not entries and delegation_id:
        deadline = time.monotonic() + args.timeout
        while time.monotonic() < deadline:
            durable = get_durable_delegation(delegation_id)
            if durable and durable.get("state") not in {"running", "dispatched"}:
                break
            time.sleep(0.5)
        entries = ((durable or {}).get("result") or {}).get("results") or []
        durable_state = (durable or {}).get("state")
    entry = entries[0] if entries else {}
    try:
        parsed_summary = json.loads(entry.get("summary") or "")
    except (TypeError, json.JSONDecodeError):
        parsed_summary = None
    if not entry:
        result = {
            "passed": False,
            "error": dispatched.get("error") or "delegation produced no result",
            "dispatch_keys": sorted(dispatched),
        }
    else:
        result = {
            "schema_version": 1,
            "evidence_state": "callable-smoke",
            "target_surface": "hermes-delegate",
            "duration_seconds": round(time.perf_counter() - started, 3),
            "delegation_id": delegation_id,
            "durable_state": durable_state,
            "entry": {
                "status": entry.get("status"),
                "summary": entry.get("summary"),
                "model": entry.get("model"),
                "provider": entry.get("provider"),
                "reasoning_effort": entry.get("reasoning_effort"),
                "route_decision_receipt": entry.get("route_decision_receipt"),
            },
            "passed": (
                entry.get("status") == "completed"
                and entry.get("provider") == "openai-codex"
                and entry.get("reasoning_effort") == "high"
                and entry.get("route_decision_receipt") == receipt
                and parsed_summary == {"value": 42}
            ),
            "limitations": [
                "One bounded smoke proves staged delegate route/receipt propagation only.",
                "It is not sufficient task-quality evidence for route promotion.",
            ],
        }
    args.output.resolve().parent.mkdir(parents=True, exist_ok=True)
    args.output.resolve().write_text(json.dumps(result, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output.resolve()), "passed": result.get("passed")}, indent=2))
    return 0 if result.get("passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
