#!/usr/bin/env python
"""Deterministic contracts for Agent Signal context-uplift evaluations.

The model/runtime arms are executed by separate isolated adapters.  This module
owns the shared fixture, exact-canary scorer, conservative admission decision,
and public-safe receipt format so every arm is judged against the same rules.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Mapping


class SuiteError(ValueError):
    """The benchmark suite is malformed."""


class ResultError(ValueError):
    """A candidate result does not satisfy the comparison contract."""


_REQUIRED_CASE_FIELDS = {
    "id",
    "kind",
    "critical",
    "position",
    "statement",
    "question",
    "expected",
    "forbidden",
}
_REQUIRED_RESULT_FIELDS = {
    "strategy",
    "score",
    "critical_failures",
    "session_identity_stable",
    "restart_recovery",
    "extra_visible_sessions",
    "median_latency_ms",
}
_ALLOWED_POSITIONS = {"early", "middle", "late"}


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def validate_suite(suite: Mapping[str, Any]) -> dict[str, Any]:
    if suite.get("schema_version") != 1:
        raise SuiteError("schema_version must be 1")
    if not isinstance(suite.get("suite_id"), str) or not suite["suite_id"].strip():
        raise SuiteError("suite_id must be a non-empty string")
    cases = suite.get("cases")
    if not isinstance(cases, list) or len(cases) < 3:
        raise SuiteError("suite must contain at least three cases")

    seen: set[str] = set()
    normalized: list[dict[str, Any]] = []
    for index, raw in enumerate(cases):
        if not isinstance(raw, Mapping):
            raise SuiteError(f"case {index} must be an object")
        missing = sorted(_REQUIRED_CASE_FIELDS - set(raw))
        if missing:
            raise SuiteError(f"case {index} missing fields: {', '.join(missing)}")
        case = dict(raw)
        case_id = case["id"]
        if not isinstance(case_id, str) or not case_id:
            raise SuiteError(f"case {index} has invalid id")
        if case_id in seen:
            raise SuiteError(f"duplicate case id: {case_id}")
        seen.add(case_id)
        if case["position"] not in _ALLOWED_POSITIONS:
            raise SuiteError(f"case {case_id} has invalid position")
        if not isinstance(case["critical"], bool):
            raise SuiteError(f"case {case_id} critical must be boolean")
        if not isinstance(case["statement"], str) or not case["statement"]:
            raise SuiteError(f"case {case_id} statement must be non-empty")
        if not isinstance(case["question"], str) or not case["question"]:
            raise SuiteError(f"case {case_id} question must be non-empty")
        for field in ("expected", "forbidden"):
            values = case[field]
            if not isinstance(values, list) or not all(isinstance(value, str) and value for value in values):
                raise SuiteError(f"case {case_id} {field} must be a list of non-empty strings")
        if not case["expected"]:
            raise SuiteError(f"case {case_id} expected must not be empty")
        normalized.append(case)

    result = dict(suite)
    result["cases"] = normalized
    return result


def load_suite(path: str | Path) -> dict[str, Any]:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SuiteError(f"unable to load suite: {exc}") from exc
    if not isinstance(data, Mapping):
        raise SuiteError("suite root must be an object")
    return validate_suite(data)


def build_transcript(
    suite: Mapping[str, Any], *, filler_turns: int = 36, filler_chars: int = 120
) -> list[dict[str, str]]:
    suite = validate_suite(suite)
    if filler_turns < 3:
        raise SuiteError("filler_turns must be at least 3")
    if filler_chars < 80:
        raise SuiteError("filler_chars must be at least 80")

    slots = {
        "early": 1,
        "middle": filler_turns // 2,
        "late": filler_turns - 1,
    }
    cases_by_slot: dict[int, list[dict[str, Any]]] = {}
    setup_by_slot: dict[int, list[str]] = {}
    for case in suite["cases"]:
        slot = slots[case["position"]]
        cases_by_slot.setdefault(slot, []).append(case)
        setup = case.get("setup_statement")
        if isinstance(setup, str) and setup:
            setup_by_slot.setdefault(max(0, slot - 2), []).append(setup)

    transcript: list[dict[str, str]] = [
        {
            "role": "user",
            "content": (
                "Synthetic context-uplift fixture. Retain exact facts, honor later corrections, "
                "and answer the final question bank without inventing values."
            ),
        },
        {"role": "assistant", "content": "Understood. I will track exact facts and corrections."},
    ]
    for turn in range(filler_turns):
        payload = [
            f"Routine project update {turn:03d}: component-{turn % 7} passed its reversible dry-run.",
            "This filler is synthetic and contains no user or machine data.",
            ((f" synthetic-padding-{turn:03d}") * (filler_chars // 22 + 2))[:filler_chars],
        ]
        payload.extend(setup_by_slot.get(turn, []))
        payload.extend(case["statement"] for case in cases_by_slot.get(turn, []))
        transcript.append({"role": "user", "content": "\n".join(payload)})
        transcript.append(
            {
                "role": "assistant",
                "content": f"Recorded synthetic update {turn:03d}; no external action was taken.",
            }
        )
    return transcript


def score_answers(suite: Mapping[str, Any], answers: Mapping[str, str]) -> dict[str, Any]:
    suite = validate_suite(suite)
    cases: dict[str, dict[str, Any]] = {}
    critical_failures: list[str] = []
    passed = 0
    for case in suite["cases"]:
        answer = str(answers.get(case["id"], ""))
        expected_missing = [token for token in case["expected"] if token not in answer]
        forbidden_hits = [token for token in case["forbidden"] if token in answer]
        ok = not expected_missing and not forbidden_hits
        if ok:
            passed += 1
        elif case["critical"]:
            critical_failures.append(case["id"])
        cases[case["id"]] = {
            "passed": ok,
            "expected_missing": expected_missing,
            "forbidden_hits": forbidden_hits,
        }
    return {
        "score": passed / len(suite["cases"]),
        "critical_failures": critical_failures,
        "cases": cases,
    }


def build_question_prompt(suite: Mapping[str, Any]) -> str:
    suite = validate_suite(suite)
    lines = ["Answer from the earlier conversation."]
    lines.append("Return one JSON object mapping each quoted ID to one string; no markdown.")
    for case in suite["cases"]:
        lines.append(f'{json.dumps(case["id"])}: {case["question"]}')
    return "\n".join(lines)


def extract_answer_mapping(text: str, suite: Mapping[str, Any]) -> dict[str, str]:
    suite = validate_suite(suite)
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < start:
        raise ResultError("answer did not contain a JSON object")
    try:
        parsed = json.loads(text[start : end + 1])
    except json.JSONDecodeError as exc:
        raise ResultError(f"answer JSON is invalid: {exc}") from exc
    if not isinstance(parsed, Mapping):
        raise ResultError("answer JSON must be an object")
    expected_ids = [case["id"] for case in suite["cases"]]
    missing = [case_id for case_id in expected_ids if case_id not in parsed]
    if missing:
        raise ResultError(f"missing answer ids: {', '.join(missing)}")
    return {case_id: str(parsed[case_id]) for case_id in expected_ids}


def validate_result(result: Mapping[str, Any]) -> dict[str, Any]:
    missing = sorted(_REQUIRED_RESULT_FIELDS - set(result))
    if missing:
        raise ResultError(f"missing result fields: {', '.join(missing)}")
    normalized = dict(result)
    if not isinstance(normalized["strategy"], str) or not normalized["strategy"]:
        raise ResultError("strategy must be a non-empty string")
    score = normalized["score"]
    if not isinstance(score, (int, float)) or isinstance(score, bool) or not 0 <= float(score) <= 1:
        raise ResultError("score must be between 0 and 1")
    normalized["score"] = float(score)
    if not isinstance(normalized["critical_failures"], list) or not all(
        isinstance(value, str) for value in normalized["critical_failures"]
    ):
        raise ResultError("critical_failures must be a string list")
    for field in ("session_identity_stable", "restart_recovery"):
        if not isinstance(normalized[field], bool):
            raise ResultError(f"{field} must be boolean")
    if not isinstance(normalized["extra_visible_sessions"], int) or normalized["extra_visible_sessions"] < 0:
        raise ResultError("extra_visible_sessions must be a non-negative integer")
    latency = normalized["median_latency_ms"]
    if not isinstance(latency, (int, float)) or isinstance(latency, bool) or latency < 0:
        raise ResultError("median_latency_ms must be non-negative")
    normalized["median_latency_ms"] = float(latency)
    resource_rank = normalized.get("resource_rank", 0)
    if not isinstance(resource_rank, int) or isinstance(resource_rank, bool) or resource_rank < 0:
        raise ResultError("resource_rank must be a non-negative integer")
    normalized["resource_rank"] = resource_rank
    return normalized


def _hard_failure(result: Mapping[str, Any]) -> str | None:
    if result["critical_failures"]:
        return "critical failure"
    if not result["session_identity_stable"]:
        return "session identity changed"
    if not result["restart_recovery"]:
        return "restart recovery failed"
    if result["extra_visible_sessions"]:
        return "created extra visible sessions"
    return None


def choose_winner(results: Iterable[Mapping[str, Any]], *, minimum_score_gain: float = 0.05) -> dict[str, Any]:
    normalized = [validate_result(result) for result in results]
    by_strategy = {result["strategy"]: result for result in normalized}
    if len(by_strategy) != len(normalized):
        raise ResultError("duplicate strategy result")
    if "baseline" not in by_strategy:
        raise ResultError("baseline result is required")

    baseline = by_strategy["baseline"]
    rejected: dict[str, str] = {}
    eligible: list[dict[str, Any]] = []
    for result in normalized:
        if result["strategy"] == "baseline":
            continue
        failure = _hard_failure(result)
        if failure:
            rejected[result["strategy"]] = failure
            continue
        if result["score"] + 1e-12 < baseline["score"] + minimum_score_gain:
            rejected[result["strategy"]] = "no material score improvement"
            continue
        eligible.append(result)

    if not eligible:
        return {
            "winner": "baseline",
            "material_improvement": False,
            "reason": "no candidate materially improved on baseline",
            "rejected": rejected,
        }

    eligible.sort(
        key=lambda item: (
            -item["score"], item["resource_rank"],
            item["median_latency_ms"], item["strategy"]
        )
    )
    winner = eligible[0]
    return {
        "winner": winner["strategy"],
        "material_improvement": True,
        "reason": "highest eligible recall score; lower resource rank, latency, and name break ties",
        "rejected": rejected,
    }


def build_public_receipt(
    suite: Mapping[str, Any],
    result: Mapping[str, Any],
    *,
    harness_bytes: bytes,
) -> dict[str, Any]:
    suite = validate_suite(suite)
    result = validate_result(result)
    return {
        "schema_version": 1,
        "suite_id": suite["suite_id"],
        "suite_sha256": _sha256(_canonical_json_bytes(suite)),
        "harness_sha256": _sha256(harness_bytes),
        "strategy": result["strategy"],
        "score": result["score"],
        "critical_failures": list(result["critical_failures"]),
        "session_identity_stable": result["session_identity_stable"],
        "restart_recovery": result["restart_recovery"],
        "extra_visible_sessions": result["extra_visible_sessions"],
        "median_latency_ms": result["median_latency_ms"],
    }


def _cmd_fixture(args: argparse.Namespace) -> int:
    suite = load_suite(args.suite)
    transcript = build_transcript(
        suite, filler_turns=args.filler_turns, filler_chars=args.filler_chars
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(transcript, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"messages": len(transcript), "output": args.output}, sort_keys=True))
    return 0


def _cmd_compare(args: argparse.Namespace) -> int:
    results = [json.loads(Path(path).read_text(encoding="utf-8")) for path in args.results]
    decision = choose_winner(results)
    text = json.dumps(decision, indent=2, sort_keys=True) + "\n"
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    fixture = subparsers.add_parser("fixture", help="build a deterministic synthetic transcript")
    fixture.add_argument("--suite", required=True)
    fixture.add_argument("--output", required=True)
    fixture.add_argument("--filler-turns", type=int, default=36)
    fixture.add_argument("--filler-chars", type=int, default=120)
    fixture.set_defaults(func=_cmd_fixture)

    compare = subparsers.add_parser("compare", help="choose a winner from result JSON files")
    compare.add_argument("results", nargs="+")
    compare.add_argument("--output")
    compare.set_defaults(func=_cmd_compare)
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
