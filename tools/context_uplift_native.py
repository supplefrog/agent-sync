#!/usr/bin/env python
"""Run one isolated Hermes native-compaction recall arm.

The script uses Hermes' installed Codex credential resolver and production
Responses transport. It never prints or persists the resolved OAuth token and
does not create a Hermes session.
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from pathlib import Path
from typing import Any

from context_uplift import (
    ResultError,
    build_question_prompt,
    extract_answer_mapping,
    load_suite,
    score_answers,
)


def _hermes_source() -> Path:
    override = os.getenv("HERMES_SOURCE")
    if override:
        source = Path(override)
    elif os.name == "nt" and os.getenv("LOCALAPPDATA"):
        source = Path(os.environ["LOCALAPPDATA"]) / "hermes" / "hermes-agent"
    else:
        source = Path.home() / ".hermes" / "hermes-agent"
    if not (source / "run_agent.py").is_file():
        raise RuntimeError("installed Hermes source checkout not found")
    if str(source) not in sys.path:
        sys.path.insert(0, str(source))
    return source


def _codex_client() -> tuple[Any, str]:
    from agent.auxiliary_client import (
        _CODEX_AUX_BASE_URL,
        _codex_cloudflare_headers,
        _create_openai_client,
        _read_codex_access_token,
    )

    token = _read_codex_access_token()
    if not token:
        raise RuntimeError("Codex OAuth credential unavailable")
    client = _create_openai_client(
        api_key=token,
        base_url=_CODEX_AUX_BASE_URL,
        default_headers=_codex_cloudflare_headers(token, base_url=_CODEX_AUX_BASE_URL),
        timeout=360.0,
    )
    return client, _CODEX_AUX_BASE_URL


def _call(
    client: Any,
    transport: Any,
    *,
    model: str,
    messages: list[dict[str, Any]],
    threshold: int | None,
    session_id: str,
    max_tokens: int,
    base_url: str,
) -> tuple[Any, dict[str, Any], float]:
    native_options: dict[str, Any] = {}
    if threshold is not None:
        native_options["context_management"] = [
            {"type": "compaction", "compact_threshold": threshold}
        ]
    kwargs = transport.build_kwargs(
        model=model,
        messages=messages,
        provider="openai-codex",
        base_url=base_url,
        is_codex_backend=True,
        reasoning_config={"enabled": True, "effort": "low"},
        session_id=session_id,
        cache_scope_id=session_id,
        max_tokens=max_tokens,
        timeout=360.0,
        **native_options,
    )
    from types import SimpleNamespace
    from agent.codex_runtime import (
        _bypass_sdk_request_transform,
        _consume_codex_event_stream,
        _sanitize_consumer_codex_request,
    )

    stand_in = SimpleNamespace(model=model, _is_codex_backend=lambda: True)
    wire_kwargs = _sanitize_consumer_codex_request(stand_in, kwargs)
    wire_kwargs["stream"] = True
    wire_kwargs = _bypass_sdk_request_transform(wire_kwargs)
    started = time.perf_counter()
    stream = client.responses.create(**wire_kwargs)
    try:
        response = _consume_codex_event_stream(stream, model=wire_kwargs["model"])
    finally:
        close_fn = getattr(stream, "close", None)
        if callable(close_fn):
            close_fn()
    elapsed_ms = (time.perf_counter() - started) * 1000
    return transport.normalize_response(response), kwargs, elapsed_ms


def _failure_result(strategy: str, failure: str, latencies: list[float]) -> dict[str, Any]:
    return {
        "strategy": strategy,
        "score": 0.0,
        "critical_failures": [failure],
        "session_identity_stable": True,
        "restart_recovery": False,
        "extra_visible_sessions": 0,
        "median_latency_ms": statistics.median(latencies) if latencies else 0.0,
        "details": {"request_count": len(latencies)},
    }


def run_arm(args: argparse.Namespace) -> dict[str, Any]:
    _hermes_source()
    from agent.transports.codex import ResponsesApiTransport

    suite = load_suite(args.suite)
    fixture = json.loads(Path(args.transcript).read_text(encoding="utf-8"))
    if not isinstance(fixture, list):
        raise ResultError("transcript root must be a message list")

    client, base_url = _codex_client()
    transport = ResponsesApiTransport()
    latencies: list[float] = []
    session_id = f"context-uplift-{args.strategy}"

    first_messages = list(fixture)
    first_messages.append(
        {
            "role": "user",
            "content": "Create the configured compaction checkpoint, then reply only CHECKPOINT_READY.",
        }
    )
    first, _first_kwargs, elapsed = _call(
        client,
        transport,
        model=args.model,
        messages=first_messages,
        threshold=args.threshold,
        session_id=session_id,
        max_tokens=64,
        base_url=base_url,
    )
    latencies.append(elapsed)

    provider_data = first.provider_data or {}
    reasoning_items = provider_data.get("codex_reasoning_items") or []
    checkpoint_items = [
        item
        for item in reasoning_items
        if isinstance(item, dict)
        and item.get("type") == "compaction"
        and item.get("encrypted_content")
    ]
    if checkpoint_items:
        persisted_items = json.loads(json.dumps(reasoning_items))
        replay_messages = [
            {
                "role": "assistant",
                "content": first.content or "CHECKPOINT_READY",
                "codex_reasoning_items": persisted_items,
            },
            {"role": "user", "content": build_question_prompt(suite)},
        ]
    elif args.allow_uncompacted:
        replay_messages = json.loads(json.dumps(fixture))
        replay_messages.append({"role": "user", "content": build_question_prompt(suite)})
    else:
        return _failure_result(args.strategy, "native_checkpoint_missing", latencies)
    second, second_kwargs, elapsed = _call(
        client,
        transport,
        model=args.model,
        messages=replay_messages,
        threshold=args.threshold,
        session_id=session_id,
        max_tokens=1000,
        base_url=base_url,
    )
    latencies.append(elapsed)
    replayed = any(
        isinstance(item, dict)
        and item.get("type") == "compaction"
        and item.get("encrypted_content")
        for item in second_kwargs.get("input", [])
    )
    if checkpoint_items and not replayed:
        return _failure_result(args.strategy, "native_checkpoint_not_replayed", latencies)

    try:
        answers = extract_answer_mapping(second.content or "", suite)
    except ResultError:
        return _failure_result(args.strategy, "answer_parse_failure", latencies)
    scored = score_answers(suite, answers)
    return {
        "strategy": args.strategy,
        "score": scored["score"],
        "critical_failures": scored["critical_failures"],
        "session_identity_stable": True,
        "restart_recovery": True,
        "extra_visible_sessions": 0,
        "median_latency_ms": statistics.median(latencies),
        "details": {
            "answers": answers,
            "case_scores": scored["cases"],
            "checkpoint_items": len(checkpoint_items),
            "checkpoint_replayed": replayed,
            "request_count": len(latencies),
            "model": args.model,
            "compact_threshold": args.threshold,
        },
    }


def _safe_error_details(exc: Exception) -> dict[str, Any]:
    details: dict[str, Any] = {"status_code": getattr(exc, "status_code", None)}

    def collect(value: Any) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if key in {"code", "type", "param", "message"} and child is not None:
                    details[key] = str(child)[:500]
                collect(child)
        elif isinstance(value, list):
            for child in value:
                collect(child)

    collect(getattr(exc, "body", None))
    response = getattr(exc, "response", None)
    try:
        collect(response.json() if response is not None else None)
    except Exception:
        pass
    if "message" not in details:
        details["message"] = str(exc)[:500]
    return details


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", required=True)
    parser.add_argument("--transcript", required=True)
    parser.add_argument("--strategy", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--threshold", required=True, type=int)
    parser.add_argument("--allow-uncompacted", action="store_true")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        result = run_arm(args)
    except Exception as exc:
        result = _failure_result(args.strategy, f"runtime_error:{type(exc).__name__}", [])
        result["details"].update(_safe_error_details(exc))
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("strategy", "score", "critical_failures")}, sort_keys=True))
    return 0 if not result["critical_failures"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
