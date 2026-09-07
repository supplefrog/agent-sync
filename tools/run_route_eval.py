#!/usr/bin/env python
"""Describe historical route observations; unsafe legacy execution is unsupported."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import shutil
import statistics
import math
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


CONTROLLER_ENV_KEYS = {
    "HERMES_SESSION_ID",
    "HERMES_SESSION_KEY",
    "HERMES_DELEGATED_CHILD",
    "HERMES_EPHEMERAL_SESSION_RECEIPT",
}


def canonical_hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")
    ).hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()


def _reject_constant(value: str):
    raise ValueError(f"non-finite JSON constant: {value}")


def _finite_float(value: str):
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError("non-finite JSON number")
    return parsed


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def parse_object(text: str) -> dict[str, Any]:
    value = json.loads(text, object_pairs_hook=_unique_object, parse_constant=_reject_constant, parse_float=_finite_float)
    if not isinstance(value, dict):
        raise ValueError("expected exactly one JSON object")
    return value


SYSTEM_ENV_KEYS = {
    "PATH", "SYSTEMROOT", "WINDIR", "COMSPEC", "PATHEXT", "SYSTEMDRIVE",
    "PROGRAMFILES", "PROGRAMFILES(X86)", "PROGRAMW6432", "PROGRAMDATA",
    "PROCESSOR_ARCHITECTURE", "NUMBER_OF_PROCESSORS", "SSL_CERT_FILE", "SSL_CERT_DIR",
    "REQUESTS_CA_BUNDLE", "CURL_CA_BUNDLE", "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY",
}


def isolated_env(source: dict[str, str] | None = None) -> dict[str, str]:
    """OS/runtime/network allowlist only; never inherit home, auth or instructions.

    This filter is not a tool sandbox. New route execution is explicitly
    unsupported until a native owner supplies isolated homes and tool evidence.
    """
    return {key: value for key, value in (os.environ if source is None else source).items()
            if key.upper() in SYSTEM_ENV_KEYS}


def _under(root: Path, relative: str) -> Path:
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise ValueError("fixture path must be a non-empty relative path")
    root = root.resolve()
    target = (root / relative).resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"fixture path escapes trial root: {relative}") from exc
    return target


def materialize_case(root: Path, case: dict[str, Any]) -> None:
    root.mkdir(parents=True, exist_ok=True)
    fixtures = case.get("fixtures", {})
    if not isinstance(fixtures, dict):
        raise ValueError("case fixtures must be an object")
    for relative, content in fixtures.items():
        target = _under(root, relative)
        if not isinstance(content, str):
            raise ValueError(f"fixture content must be text: {relative}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")


def check_acceptance(root: Path, case: dict[str, Any]) -> dict[str, Any]:
    """Check inert JSON artifacts; mutable-fixture command verification is unsafe."""
    acceptance = case.get("acceptance", {})
    result = {"passed": False, "json_match": None, "command_exit_code": None,
              "command_stdout_sha256": None, "command_stderr_sha256": None,
              "unsupported_checks": [], "errors": [], "acceptance_state": "invalid"}
    if not isinstance(acceptance, dict) or not acceptance:
        result["errors"].append("nonempty acceptance criteria are required")
        return result
    allowed = {"json_file", "expected", "command", "command_exit", "timeout_seconds"}
    unknown = sorted(set(acceptance) - allowed)
    if unknown:
        result["unsupported_checks"].extend(unknown)
    if "command" in acceptance:
        result["unsupported_checks"].append("command")
        result["errors"].append("unsupported-verifier: model-fixture commands require an independently owned sandboxed verifier")
    checked = False
    if "json_file" in acceptance:
        if "expected" not in acceptance:
            result["errors"].append("json_file acceptance requires an explicit expected value")
        else:
            checked = True
            try:
                path = _under(root, acceptance["json_file"])
                actual = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_object,
                                    parse_constant=_reject_constant, parse_float=_finite_float)
                # JSON booleans must not pass numeric answer keys (True == 1 in Python).
                result["json_match"] = canonical_hash(actual) == canonical_hash(acceptance["expected"])
                result["actual"] = actual
            except (OSError, ValueError, TypeError) as exc:
                result["json_match"] = False
                result["json_error"] = type(exc).__name__
    if not checked and not result["unsupported_checks"]:
        result["errors"].append("no supported executable acceptance criterion")
    result["passed"] = checked and result["json_match"] is True and not result["errors"] and not result["unsupported_checks"]
    result["acceptance_state"] = "unsupported-verifier" if result["unsupported_checks"] else "checked" if checked else "invalid"
    return result


_USAGE_FIELDS = {
    "model", "provider", "input_tokens", "output_tokens", "cache_read_tokens", "cache_write_tokens",
    "reasoning_tokens", "total_tokens", "api_calls", "completed", "failed", "interrupted", "partial",
    "estimated_cost_usd", "cost_status", "cost_source", "service_tier",
}


def sanitize_usage(usage: dict[str, Any]) -> dict[str, Any]:
    safe = {key: value for key, value in usage.items() if key in _USAGE_FIELDS and not isinstance(value, (dict, list))}
    session_id = usage.get("session_id")
    if isinstance(session_id, str) and session_id:
        safe["session_id_sha256"] = sha256_text(session_id)
    return safe


def _nonnegative(value: Any) -> float | None:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None
    try:
        numeric = float(value)
    except (OverflowError, ValueError):
        return None
    return numeric if math.isfinite(numeric) and numeric >= 0 else None


def nominal_cost_usd(usage: dict[str, Any], route: dict[str, Any]) -> float | None:
    """CanonicalUsage input tokens already exclude cache reads/writes.

    Missing observations remain unknown. An explicit zero token bucket costs
    zero regardless of an absent rate; a positive unpriced bucket is unknown.
    """
    pricing = route.get("pricing_usd_per_million", {})
    if not isinstance(pricing, dict):
        return None
    total = 0.0
    for price_key, usage_key in {"input": "input_tokens", "output": "output_tokens",
                               "cache_read": "cache_read_tokens", "cache_write": "cache_write_tokens"}.items():
        tokens = usage.get(usage_key)
        if type(tokens) is not int or tokens < 0:
            return None
        if tokens == 0:
            continue
        price = _nonnegative(pricing.get(price_key))
        if price is None:
            return None
        try:
            total += price * tokens / 1_000_000
        except OverflowError:
            return None
    return round(total, 9) if math.isfinite(total) else None


def cost_observation(usage: dict[str, Any], route: dict[str, Any], *,
                     task_contract_sha256: str | None = None, verifier_sha256: str | None = None,
                     exact_route: dict[str, Any] | None = None) -> dict[str, Any]:
    status = usage.get("cost_status")
    if not isinstance(status, str):
        status = "unknown"
    amount = _nonnegative(usage.get("estimated_cost_usd"))
    billing = amount if status in {"actual", "estimated", "included"} else None
    if status == "included" and billing != 0:
        billing = None
    bound = (isinstance(task_contract_sha256, str) and re.fullmatch(r"[a-f0-9]{64}", task_contract_sha256)
             and isinstance(verifier_sha256, str) and re.fullmatch(r"[a-f0-9]{64}", verifier_sha256)
             and isinstance(exact_route, dict))
    return {"nominal_token_cost_usd": nominal_cost_usd(usage, route),
            "reported_billing_cost_usd": billing, "reported_cost_status": status or "unknown",
            "reported_cost_source": usage.get("cost_source"),
            "marginal_oauth_cost_usd": 0.0 if status == "included" and billing == 0 else None,
            "quota_cost": None, "quota_unit": None,
            "task_contract_sha256": task_contract_sha256 if bound else None,
            "verifier_sha256": verifier_sha256 if bound else None,
            "route_sha256": canonical_hash(exact_route) if bound else None,
            "limitation": "Nominal USD, reported billing, and subscription quota are distinct; no USD-to-quota conversion."}


def _percentile(values: list[float], quantile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int(len(ordered) * quantile + 0.999999) - 1))
    return round(ordered[index], 3)


def _mean(values: list[float | None]) -> float | None:
    return round(statistics.fmean(values), 9) if values and all(v is not None for v in values) else None


def _all_observed(rows, field):
    values = [row.get(field) for row in rows]
    if not values or any(type(value) is not bool for value in values):
        return None
    return all(values)


def _tool_observations(rows):
    # Preserve explicit reported native observations, separately from any claim
    # that an independent validator has qualified their origin/effects.
    names = set()
    for row in rows:
        if row.get("runtime_lane") == "inline-text-no-tools-v1":
            continue
        observations = row.get("tool_observations", [])
        if not isinstance(observations, list):
            continue
        for item in observations:
            if isinstance(item, dict) and isinstance(item.get("name"), str):
                names.add(item["name"])
    return sorted(names)


def _observed_cost(row, field):
    observations = row.get("cost_observations", {})
    observation = observations.get(field) if isinstance(observations, dict) else None
    if not isinstance(observation, dict) or not isinstance(observation.get("source"), str) or not observation["source"].strip():
        return None
    evidence = observation.get("evidence", {})
    if not (isinstance(evidence, dict) and isinstance(evidence.get("locator"), str) and evidence["locator"].strip()
            and isinstance(evidence.get("sha256"), str) and re.fullmatch(r"[a-f0-9]{64}", evidence["sha256"])):
        return None
    return _nonnegative(observation.get("amount_usd"))


def _task_summary(rows: list[dict[str, Any]], concurrency: int) -> dict[str, Any]:
    durations = [_nonnegative(row.get("duration_seconds")) for row in rows]
    complete_durations = bool(rows) and all(value is not None for value in durations)
    retries = [row.get("retries") if type(row.get("retries")) is int and row["retries"] >= 0 else None for row in rows]
    components = {name: _mean([_observed_cost(row, field) for row in rows]) for name, field in {
        "attempts_usd": "attempt_nominal_cost_usd", "retries_usd": "retry_nominal_cost_usd",
        "verification_usd": "verification_cost_usd", "recovery_usd": "recovery_cost_usd"}.items()}
    expected_total = round(sum(components.values()), 9) if all(value is not None for value in components.values()) else None
    return {
        "sample_size": len(rows), "passed": sum(row.get("passed") is True for row in rows),
        "pass_rate": round(sum(row.get("passed") is True for row in rows) / len(rows), 6) if rows else None,
        "critical_failures": sum(row.get("critical_failure") is True for row in rows),
        "unobserved_critical_failure_rows": sum(type(row.get("critical_failure")) is not bool for row in rows),
        "p50_seconds": round(statistics.median(durations), 3) if complete_durations else None,
        "p95_seconds": _percentile(durations, .95) if complete_durations else None,
        "attempt_success_rate": round(sum(row.get("transport_success") is True for row in rows) / len(rows), 6) if rows else None,
        "expected_retries": _mean(retries),
        "max_retries_observed": max(retries) if retries and all(value is not None for value in retries) else None,
        "cleanup_passed": _all_observed(rows, "cleanup_passed"),
        "verifier_passed": _all_observed(rows, "verifier_passed"),
        "required_tools_verified": [], "capabilities_verified": [], "concurrency_verified": None,
        "observed_tool_names": _tool_observations(rows), "requested_concurrency": concurrency,
        "recorded_tool_claims": [row.get("required_tools_verified", []) for row in rows],
        "recorded_tool_observations": [row.get("tool_observations", []) for row in rows],
        "expected_total_cost_usd": expected_total, "cost_components": components,
        "generation_nominal_cost_usd": _mean([_nonnegative(row.get("nominal_cost_usd")) for row in rows]),
        "marginal_oauth_cost_usd": _mean([_observed_cost(row, "marginal_oauth_cost_usd") for row in rows]),
        "recorded_cost_claims": [{key: row.get(key) for key in ("attempt_nominal_cost_usd", "retry_nominal_cost_usd", "verification_cost_usd", "recovery_cost_usd", "marginal_oauth_cost_usd")} for row in rows],
        "runtime_evidence_verified": False,
        "nominal_cost_basis": "Explicit observed canonical token buckets and declared token rates; missing data remains unknown.",
    }


def summarize_route(route: dict[str, Any], trials: list[dict[str, Any]], concurrency: int) -> dict[str, Any]:
    rows = [row for row in trials if row.get("route_id") == route["id"]]
    by_class = {}
    for row in rows:
        by_class.setdefault(row["task_class"], []).append(row)
    total = _task_summary(rows, concurrency)
    return {**route, "task_classes": {key: _task_summary(group, concurrency) for key, group in sorted(by_class.items())},
            "transport": {"sample_size": len(rows), "p50_seconds": total["p50_seconds"], "p95_seconds": total["p95_seconds"],
                          "attempt_success_rate": total["attempt_success_rate"],
                          "failures": sum(row.get("transport_success") is False for row in rows),
                          "retries": sum(row["retries"] for row in rows) if rows and all(type(row.get("retries")) is int and row["retries"] >= 0 for row in rows) else None,
                          "empty_outputs": sum(row.get("empty_output") is True for row in rows),
                          "cleanup_passed": total["cleanup_passed"], "concurrency": None, "requested_concurrency": concurrency},
            "evidence_state": "descriptive-only", "eligible_for_routing": False,
            "limitations": ["Historical outcome claims are retained as observations, not independently qualified route evidence.",
                            "Declared required tools and concurrency do not establish exercised capabilities."]}


def _public_safe_text(text: str, root: Path) -> str:
    cleaned = text.replace(str(root), "[TRIAL_ROOT]")
    cleaned = cleaned.replace(str(root).replace("\\", "/"), "[TRIAL_ROOT]")
    cleaned = re.sub(r"(?i)[A-Z]:[\\/]Users[\\/][^\\/\s]+", "[USER_HOME]", cleaned)
    cleaned = re.sub(r"(?i)Bearer\s+\S+", "Bearer [REDACTED]", cleaned)
    cleaned = re.sub(r"(?i)\b(?:sk|sess|token)-[A-Za-z0-9._-]+", "[REDACTED]", cleaned)
    return cleaned[-1000:]


class UnsupportedExecutionError(RuntimeError):
    pass


EXECUTION_SUPPORT = {
    "status": "unsupported-legacy-execution",
    "transport": "hermes-oneshot/openai-codex",
    "reason": "Legacy one-shot inherits personal context and YOLO, exposes mutable receipts/verifiers, and has no proven session cleanup authority.",
    "tool_capability": "required native tool execution remains unsupported here; no-tools evidence is not a substitute",
    "historical_reports": "preserved; pure descriptive summaries remain available",
}


def _delete_session(session_id: Any, env: dict[str, str], cwd: Path) -> bool:
    """An untrusted usage receipt cannot grant global session deletion authority."""
    return not bool(session_id)


async def run_one(route: dict[str, Any], case: dict[str, Any], repeat: int,
                  scratch: Path, semaphore: asyncio.Semaphore, timeout_seconds: int,
                  max_retries: int) -> dict[str, Any]:
    raise UnsupportedExecutionError("unsupported legacy route execution: " + EXECUTION_SUPPORT["reason"])


def _eligible(metrics: dict[str, Any], constraints: dict[str, Any]) -> tuple[bool, list[str]]:
    reasons = []
    comparisons = [("sample_size", "min_sample_size", lambda a,b:a>=b),
                   ("pass_rate", "min_pass_rate", lambda a,b:a>=b),
                   ("critical_failures", "max_critical_failures", lambda a,b:a<=b),
                   ("p95_seconds", "max_p95_seconds", lambda a,b:a<=b),
                   ("expected_total_cost_usd", "max_expected_total_cost_usd", lambda a,b:a<=b),
                   ("max_retries_observed", "max_retries", lambda a,b:a<=b)]
    for field, constraint, compare in comparisons:
        if constraint not in constraints:
            continue
        value = _nonnegative(metrics.get(field))
        limit = _nonnegative(constraints[constraint])
        if value is None:
            reasons.append(field + "_unobserved")
        elif limit is None or not compare(value, limit):
            reasons.append(constraint)
    if metrics.get("cleanup_passed") is not True: reasons.append("cleanup_passed")
    if constraints.get("verifier_required") and metrics.get("verifier_passed") is not True: reasons.append("verifier_required")
    if set(constraints.get("required_tools", [])) - set(metrics.get("required_tools_verified", [])): reasons.append("required_tools")
    # This descriptive producer cannot self-issue a trusted quality record.
    reasons.append("independent_runtime_evidence_required")
    return False, reasons


async def main_async(args: argparse.Namespace) -> None:
    # Fail before fixture allocation, native launch, usage-file reads or cleanup.
    raise UnsupportedExecutionError("unsupported legacy route execution: " + EXECUTION_SUPPORT["reason"])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", default="evals/suites/adaptive-routing-hermes-0205-v1.json")
    parser.add_argument("--routes", default="evals/fixtures/adaptive-routing/openai-codex-routes-hermes-0205-v1.json")
    parser.add_argument("--output", default="evals/results/adaptive-routing-hermes-0205-v1.json")
    parser.add_argument("--repeats", type=int, default=8)
    parser.add_argument("--concurrency", type=int, default=2)
    parser.add_argument("--max-retries", type=int, default=1)
    parser.add_argument("--timeout-seconds", type=int, default=300)
    parser.add_argument("--route-id", action="append", help="Run only this exact route id (repeatable)")
    parser.add_argument("--case-id", action="append", help="Run only this exact case id (repeatable)")
    args = parser.parse_args()
    try:
        asyncio.run(main_async(args))
    except UnsupportedExecutionError:
        print(json.dumps(EXECUTION_SUPPORT, indent=2))
        raise SystemExit(2)


if __name__ == "__main__":
    main()
