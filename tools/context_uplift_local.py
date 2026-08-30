#!/usr/bin/env python
"""Run the isolated incumbent Hermes local-compressor recall arm."""
from __future__ import annotations

import argparse
import copy
import json
import statistics
import time
from pathlib import Path

from context_uplift import (
    ResultError,
    build_question_prompt,
    extract_answer_mapping,
    load_suite,
    score_answers,
)
from context_uplift_native import _call, _codex_client, _hermes_source, _safe_error_details


def run_arm(args: argparse.Namespace) -> dict:
    source = _hermes_source()
    from evals.compaction.fixtures import total_tokens
    from evals.compaction.policies import EVAL_MODEL, POLICIES, apply_policy
    from agent.context_compressor import ContextCompressor
    from agent.transports.codex import ResponsesApiTransport

    suite = load_suite(args.suite)
    fixture = json.loads(Path(args.transcript).read_text(encoding="utf-8"))
    if not isinstance(fixture, list):
        raise ResultError("transcript root must be a message list")

    normalized_fixture = []
    for message in fixture:
        item = dict(message)
        if isinstance(item.get("content"), str):
            item["content"] = [{"type": "text", "text": item["content"]}]
        normalized_fixture.append(item)

    before_tokens = total_tokens(normalized_fixture)
    compressor = apply_policy(
        ContextCompressor(model=EVAL_MODEL, quiet_mode=True), POLICIES["current"]
    )
    started = time.perf_counter()
    compacted = compressor.compress(
        copy.deepcopy(normalized_fixture), current_tokens=before_tokens, force=True
    )
    compression_ms = (time.perf_counter() - started) * 1000
    stats = {
        "before_tokens": before_tokens,
        "after_tokens": total_tokens(compacted),
        "summarized_messages": max(0, len(normalized_fixture) - len(compacted)),
    }

    compacted.append({"role": "user", "content": build_question_prompt(suite)})
    client, base_url = _codex_client()
    response, _kwargs, answer_ms = _call(
        client,
        ResponsesApiTransport(),
        model=args.model,
        messages=compacted,
        threshold=None,
        session_id="context-uplift-incumbent",
        max_tokens=1000,
        base_url=base_url,
    )
    answers = extract_answer_mapping(response.content or "", suite)
    scored = score_answers(suite, answers)
    public_stats = {
        key: value
        for key, value in stats.items()
        if key in {"before_tokens", "after_tokens", "summary_tokens", "summarized_messages"}
        and isinstance(value, (int, float, str, bool, type(None)))
    }
    return {
        "strategy": args.strategy,
        "score": scored["score"],
        "critical_failures": scored["critical_failures"],
        "session_identity_stable": False,
        "restart_recovery": True,
        "extra_visible_sessions": 1,
        "median_latency_ms": statistics.median([compression_ms, answer_ms]),
        "details": {
            "answers": answers,
            "case_scores": scored["cases"],
            "compression_ms": compression_ms,
            "answer_ms": answer_ms,
            "compression_stats": public_stats,
            "model": args.model,
            "policy": "current",
            "hermes_revision": source.name,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", required=True)
    parser.add_argument("--transcript", required=True)
    parser.add_argument("--strategy", default="current-rotating-compressor")
    parser.add_argument("--model", default="gpt-5.6-sol")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        result = run_arm(args)
    except Exception as exc:
        result = {
            "strategy": args.strategy,
            "score": 0.0,
            "critical_failures": [f"runtime_error:{type(exc).__name__}"],
            "session_identity_stable": False,
            "restart_recovery": False,
            "extra_visible_sessions": 0,
            "median_latency_ms": 0.0,
            "details": _safe_error_details(exc),
        }
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("strategy", "score", "critical_failures")}, sort_keys=True))
    return 0 if not result["critical_failures"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
