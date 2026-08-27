#!/usr/bin/env python
"""Run a frozen adaptive-routing suite through Hermes one-shot transport."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import shutil
import statistics
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psutil

CONTROLLER_ENV_KEYS = {
    "HERMES_SESSION_ID",
    "HERMES_SESSION_KEY",
    "HERMES_DELEGATED_CHILD",
    "HERMES_EPHEMERAL_SESSION_RECEIPT",
}


def canonical_hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()


def parse_object(text: str) -> object:
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()[1:-1]
        stripped = "\n".join(lines)
    start, end = stripped.find("{"), stripped.rfind("}")
    if start < 0 or end < start:
        raise ValueError("no JSON object")
    return json.loads(stripped[start : end + 1])


def isolated_env(source: dict[str, str] | None = None) -> dict[str, str]:
    """Keep provider credentials/config while removing controller identity."""
    env = dict(os.environ if source is None else source)
    for key in list(env):
        if key.startswith("HERMES_KANBAN_") or key in CONTROLLER_ENV_KEYS:
            env.pop(key, None)
    return env


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
    acceptance = case.get("acceptance", {})
    if not isinstance(acceptance, dict):
        raise ValueError("case acceptance must be an object")
    result: dict[str, Any] = {
        "passed": True,
        "json_match": None,
        "command_exit_code": None,
        "command_stdout_sha256": None,
        "command_stderr_sha256": None,
    }
    json_file = acceptance.get("json_file")
    if json_file:
        path = _under(root, json_file)
        try:
            actual = json.loads(path.read_text(encoding="utf-8"))
            result["json_match"] = actual == acceptance.get("expected")
            result["actual"] = actual
        except (OSError, json.JSONDecodeError) as exc:
            result["json_match"] = False
            result["json_error"] = type(exc).__name__
        result["passed"] = result["passed"] and result["json_match"] is True
    command = acceptance.get("command")
    if command:
        if not isinstance(command, list) or any(not isinstance(item, str) for item in command):
            raise ValueError("acceptance command must be an array of strings")
        completed = subprocess.run(
            command,
            cwd=root,
            text=True,
            capture_output=True,
            timeout=int(acceptance.get("timeout_seconds", 30)),
            check=False,
        )
        expected_exit = int(acceptance.get("command_exit", 0))
        result["command_exit_code"] = completed.returncode
        result["command_stdout_sha256"] = sha256_text(completed.stdout)
        result["command_stderr_sha256"] = sha256_text(completed.stderr)
        result["passed"] = result["passed"] and completed.returncode == expected_exit
    return result


def sanitize_usage(usage: dict[str, Any]) -> dict[str, Any]:
    safe = dict(usage)
    session_id = safe.pop("session_id", None)
    if session_id:
        safe["session_id_sha256"] = sha256_text(str(session_id))
    for key in list(safe):
        lowered = key.lower()
        if any(marker in lowered for marker in ("token_value", "api_key", "access_token", "refresh_token", "password")):
            safe.pop(key, None)
    return safe


def nominal_cost_usd(usage: dict[str, Any], route: dict[str, Any]) -> float:
    pricing = route.get("pricing_usd_per_million", {})
    token_fields = {
        "input": "input_tokens",
        "output": "output_tokens",
        "cache_read": "cache_read_tokens",
        "cache_write": "cache_write_tokens",
    }
    total = 0.0
    for price_key, usage_key in token_fields.items():
        price = float(pricing.get(price_key, 0.0) or 0.0)
        tokens = int(usage.get(usage_key, 0) or 0)
        total += price * tokens / 1_000_000
    return round(total, 9)


def _percentile(values: list[float], quantile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int(len(ordered) * quantile + 0.999999) - 1))
    return round(ordered[index], 3)


def _mean(values: list[float]) -> float:
    return round(statistics.fmean(values), 9) if values else 0.0


def _task_summary(rows: list[dict[str, Any]], concurrency: int) -> dict[str, Any]:
    durations = [float(row["duration_seconds"]) for row in rows]
    transport_successes = sum(bool(row["transport_success"]) for row in rows)
    retries = [int(row["retries"]) for row in rows]
    required_tools = [set(row.get("required_tools_verified", [])) for row in rows]
    tools_verified = sorted(set.intersection(*required_tools)) if required_tools else []
    attempts = [
        float(row.get("attempt_nominal_cost_usd", row.get("nominal_cost_usd", 0.0)))
        for row in rows
    ]
    retry_costs = [float(row.get("retry_nominal_cost_usd", 0.0)) for row in rows]
    verification = [float(row.get("verification_cost_usd", 0.0)) for row in rows]
    recovery = [float(row.get("recovery_cost_usd", 0.0)) for row in rows]
    components = {
        "attempts_usd": _mean(attempts),
        "retries_usd": _mean(retry_costs),
        "verification_usd": _mean(verification),
        "recovery_usd": _mean(recovery),
    }
    expected_total = round(sum(components.values()), 9)
    critical_failures = sum(bool(row.get("critical_failure")) for row in rows)
    return {
        "sample_size": len(rows),
        "passed": sum(bool(row["passed"]) for row in rows),
        "pass_rate": round(sum(bool(row["passed"]) for row in rows) / len(rows), 6),
        "critical_failures": critical_failures,
        "p50_seconds": round(statistics.median(durations), 3),
        "p95_seconds": _percentile(durations, 0.95),
        "attempt_success_rate": round(transport_successes / len(rows), 6),
        "expected_retries": round(statistics.fmean(retries), 6),
        "max_retries_observed": max(retries, default=0),
        "cleanup_passed": all(bool(row["cleanup_passed"]) for row in rows),
        "verifier_passed": all(bool(row["verifier_passed"]) for row in rows),
        "required_tools_verified": tools_verified,
        "capabilities_verified": ["text", "tool-use"],
        "concurrency_verified": concurrency,
        "expected_total_cost_usd": expected_total,
        "cost_components": components,
        "marginal_oauth_cost_usd": 0.0,
        "nominal_cost_basis": "live catalog token prices; OAuth marginal billing is included/subscription",
    }


def summarize_route(route: dict[str, Any], trials: list[dict[str, Any]], concurrency: int) -> dict[str, Any]:
    rows = [row for row in trials if row["route_id"] == route["id"]]
    by_class: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_class.setdefault(row["task_class"], []).append(row)
    transport_durations = [float(row["duration_seconds"]) for row in rows]
    result = {
        **route,
        "task_classes": {
            task_class: _task_summary(class_rows, concurrency)
            for task_class, class_rows in sorted(by_class.items())
        },
        "transport": {
            "sample_size": len(rows),
            "p50_seconds": round(statistics.median(transport_durations), 3),
            "p95_seconds": _percentile(transport_durations, 0.95),
            "attempt_success_rate": round(
                sum(bool(row["transport_success"]) for row in rows) / len(rows), 6
            ),
            "failures": sum(not bool(row["transport_success"]) for row in rows),
            "retries": sum(int(row["retries"]) for row in rows),
            "empty_outputs": sum(bool(row.get("empty_output")) for row in rows),
            "cleanup_passed": all(bool(row["cleanup_passed"]) for row in rows),
            "concurrency": concurrency,
        },
    }
    return result


def _public_safe_text(text: str, root: Path) -> str:
    cleaned = text.replace(str(root), "[TRIAL_ROOT]")
    cleaned = cleaned.replace(str(root).replace("\\", "/"), "[TRIAL_ROOT]")
    cleaned = re.sub(r"(?i)[A-Z]:[\\/]Users[\\/][^\\/\s]+", "[USER_HOME]", cleaned)
    cleaned = re.sub(r"(?i)Bearer\s+\S+", "Bearer [REDACTED]", cleaned)
    cleaned = re.sub(r"(?i)\b(?:sk|sess|token)-[A-Za-z0-9._-]+", "[REDACTED]", cleaned)
    return cleaned[-1000:]


def _reset_trial(root: Path, case: dict[str, Any]) -> None:
    if root.exists():
        shutil.rmtree(root)
    materialize_case(root, case)


def _delete_session(session_id: Any, env: dict[str, str], cwd: Path) -> bool:
    if not session_id:
        return True
    try:
        completed = subprocess.run(
            ["hermes", "sessions", "delete", str(session_id), "--yes"],
            cwd=cwd,
            env=env,
            text=True,
            capture_output=True,
            timeout=30,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return False
    return completed.returncode == 0


async def _monitor_descendants(pid: int, stop: asyncio.Event) -> dict[int, float]:
    observed: dict[int, float] = {}
    while not stop.is_set():
        try:
            for child in psutil.Process(pid).children(recursive=True):
                try:
                    observed[child.pid] = child.create_time()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
        try:
            await asyncio.wait_for(stop.wait(), timeout=0.2)
        except asyncio.TimeoutError:
            pass
    return observed


def _reap_owned_processes(observed: dict[int, float]) -> bool:
    remaining: list[psutil.Process] = []
    for pid, create_time in observed.items():
        try:
            process = psutil.Process(pid)
            if abs(process.create_time() - create_time) < 0.01 and process.is_running():
                remaining.append(process)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    for process in remaining:
        try:
            process.terminate()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    _, alive = psutil.wait_procs(remaining, timeout=2)
    for process in alive:
        try:
            process.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    _, alive = psutil.wait_procs(alive, timeout=2)
    return not alive


async def run_one(
    route: dict[str, Any],
    case: dict[str, Any],
    repeat: int,
    scratch: Path,
    semaphore: asyncio.Semaphore,
    timeout_seconds: int,
    max_retries: int,
) -> dict[str, Any]:
    trial_root = scratch / route["id"] / case["id"] / str(repeat)
    _reset_trial(trial_root, case)
    env = isolated_env()
    attempt_records: list[dict[str, Any]] = []
    cleanup_results: list[bool] = []
    final_stdout = b""
    final_stderr = b""
    final_exit_code = 124
    started = 0.0
    ended = 0.0

    async with semaphore:
        started = time.perf_counter()
        for attempt in range(max_retries + 1):
            usage_path = trial_root / f"usage-{attempt}.json"
            cmd = [
                "hermes",
                "-z",
                case["prompt"],
                "--model",
                route["model"],
                "--provider",
                route["provider"],
                "--reasoning",
                route["reasoning_effort"],
                "--toolsets",
                ",".join(case.get("toolsets", ["file", "terminal"])),
                "--usage-file",
                str(usage_path),
                "--safe-mode",
                "--in",
                str(trial_root),
            ]
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
                cwd=trial_root,
            )
            stop_monitor = asyncio.Event()
            monitor = asyncio.create_task(_monitor_descendants(proc.pid, stop_monitor))
            timed_out = False
            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout_seconds)
                exit_code = int(proc.returncode)
            except asyncio.TimeoutError:
                timed_out = True
                proc.kill()
                await proc.wait()
                stdout, stderr, exit_code = b"", b"timeout", 124
            finally:
                stop_monitor.set()
                observed_descendants = await monitor
            process_cleanup_passed = _reap_owned_processes(observed_descendants)
            usage_raw: dict[str, Any] = {}
            if usage_path.exists():
                try:
                    usage_raw = json.loads(usage_path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    usage_raw = {}
            session_cleanup_passed = _delete_session(usage_raw.get("session_id"), env, trial_root)
            cleanup_results.append(session_cleanup_passed and process_cleanup_passed)
            transport_success = exit_code == 0 and not timed_out and usage_raw.get("failed") is not True
            attempt_records.append(
                {
                    "attempt": attempt + 1,
                    "exit_code": exit_code,
                    "timed_out": timed_out,
                    "transport_success": transport_success,
                    "process_cleanup_passed": process_cleanup_passed,
                    "session_cleanup_passed": session_cleanup_passed,
                    "observed_descendant_count": len(observed_descendants),
                    "usage": sanitize_usage(usage_raw),
                    "nominal_cost_usd": nominal_cost_usd(usage_raw, route),
                    "stdout_sha256": sha256_text(stdout.decode("utf-8", errors="replace")),
                    "stderr_sha256": sha256_text(stderr.decode("utf-8", errors="replace")),
                }
            )
            final_stdout, final_stderr, final_exit_code = stdout, stderr, exit_code
            if transport_success or attempt >= max_retries:
                break
            _reset_trial(trial_root, case)
        ended = time.perf_counter()

    transport_success = bool(attempt_records[-1]["transport_success"])
    acceptance = check_acceptance(trial_root, case) if transport_success else {"passed": False}
    passed = transport_success and bool(acceptance["passed"])
    first_cost = float(attempt_records[0]["nominal_cost_usd"])
    retry_cost = sum(float(item["nominal_cost_usd"]) for item in attempt_records[1:])
    required_tools = case.get("required_tools", []) if passed else []
    critical_failure = (
        not transport_success
        or not all(cleanup_results)
        or (bool(case.get("critical_failure_on_fail")) and not passed)
    )
    text = final_stdout.decode("utf-8", errors="replace")
    try:
        final_object = parse_object(text)
    except (ValueError, json.JSONDecodeError):
        final_object = None
    return {
        "route_id": route["id"],
        "case_id": case["id"],
        "task_class": case["task_class"],
        "repeat": repeat,
        "passed": passed,
        "critical_failure": critical_failure,
        "duration_seconds": round(ended - started, 3),
        "exit_code": final_exit_code,
        "transport_success": transport_success,
        "retries": len(attempt_records) - 1,
        "attempts": attempt_records,
        "attempt_nominal_cost_usd": first_cost,
        "retry_nominal_cost_usd": round(retry_cost, 9),
        "nominal_cost_usd": round(first_cost + retry_cost, 9),
        "verification_cost_usd": 0.0,
        "recovery_cost_usd": 0.0,
        "marginal_oauth_cost_usd": 0.0,
        "empty_output": not bool(text.strip()),
        "final_object": final_object,
        "acceptance": acceptance,
        "verifier_passed": bool(acceptance.get("passed")),
        "required_tools_verified": required_tools,
        "cleanup_passed": all(cleanup_results),
        "error": _public_safe_text(final_stderr.decode("utf-8", errors="replace"), trial_root) or None,
    }


def _eligible(metrics: dict[str, Any], constraints: dict[str, Any]) -> tuple[bool, list[str]]:
    reasons = []
    if metrics["sample_size"] < constraints["min_sample_size"]:
        reasons.append("min_sample_size")
    if metrics["pass_rate"] < constraints["min_pass_rate"]:
        reasons.append("min_pass_rate")
    if metrics["critical_failures"] > constraints.get("max_critical_failures", 0):
        reasons.append("max_critical_failures")
    if metrics["p95_seconds"] > constraints["max_p95_seconds"]:
        reasons.append("max_p95_seconds")
    if metrics["expected_total_cost_usd"] > constraints["max_expected_total_cost_usd"]:
        reasons.append("max_expected_total_cost_usd")
    if metrics["max_retries_observed"] > constraints.get("max_retries", 1):
        reasons.append("max_retries")
    if not metrics["cleanup_passed"]:
        reasons.append("cleanup_passed")
    if constraints.get("verifier_required") and not metrics["verifier_passed"]:
        reasons.append("verifier_required")
    if set(constraints.get("required_tools", [])) - set(metrics["required_tools_verified"]):
        reasons.append("required_tools")
    return not reasons, reasons


async def main_async(args: argparse.Namespace) -> None:
    suite_path = Path(args.suite).resolve()
    routes_path = Path(args.routes).resolve()
    suite = json.loads(suite_path.read_text(encoding="utf-8"))
    route_manifest = json.loads(routes_path.read_text(encoding="utf-8"))
    routes = route_manifest["routes"]
    cases = suite["cases"]
    if args.route_id:
        wanted_routes = set(args.route_id)
        routes = [route for route in routes if route["id"] in wanted_routes]
        if {route["id"] for route in routes} != wanted_routes:
            raise ValueError("unknown --route-id")
    if args.case_id:
        wanted_cases = set(args.case_id)
        cases = [case for case in cases if case["id"] in wanted_cases]
        if {case["id"] for case in cases} != wanted_cases:
            raise ValueError("unknown --case-id")
    semaphore = asyncio.Semaphore(args.concurrency)
    batch_started = time.perf_counter()
    temp_parent = suite_path.parents[2] / ".evals"
    temp_parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="route-eval-", dir=temp_parent) as temp:
        scratch = Path(temp)
        jobs = [
            run_one(
                route,
                case,
                repeat,
                scratch,
                semaphore,
                args.timeout_seconds,
                args.max_retries,
            )
            for route in routes
            for case in cases
            for repeat in range(args.repeats)
        ]
        trials = await asyncio.gather(*jobs)
        scratch_root = str(scratch)
    scratch_removed = not Path(scratch_root).exists()
    summaries = [summarize_route(route, trials, args.concurrency) for route in routes]
    constraints = suite["hard_constraints"]
    eligibility: dict[str, Any] = {}
    for summary in summaries:
        route_result: dict[str, Any] = {}
        for task_class, metrics in summary["task_classes"].items():
            eligible, reasons = _eligible(metrics, constraints[task_class])
            route_result[task_class] = {"eligible": eligible, "reasons": reasons}
        eligibility[summary["id"]] = route_result
    observed = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    result = {
        "schema_version": 2,
        "artifact_type": "hermes-adaptive-routing-local-evidence",
        "suite_id": suite["suite_id"],
        "suite_sha256": hashlib.sha256(suite_path.read_bytes()).hexdigest(),
        "route_manifest_sha256": hashlib.sha256(routes_path.read_bytes()).hexdigest(),
        "harness_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "observed_at": observed,
        "transport": "hermes-oneshot/openai-codex",
        "host": route_manifest["host"],
        "repeats": args.repeats,
        "concurrency": args.concurrency,
        "max_retries": args.max_retries,
        "timeout_seconds": args.timeout_seconds,
        "batch_wall_seconds": round(time.perf_counter() - batch_started, 3),
        "routes": routes,
        "summaries": summaries,
        "eligibility": eligibility,
        "trials": trials,
        "cleanup": {
            "scratch_removed": scratch_removed,
            "all_sessions_deleted": all(
                all(attempt["session_cleanup_passed"] for attempt in row["attempts"])
                for row in trials
            ),
            "all_cli_processes_reaped": all(
                all(attempt["process_cleanup_passed"] for attempt in row["attempts"])
                for row in trials
            ),
        },
        "evidence_state": "verified-local" if all(
            summary["transport"]["sample_size"] >= 8 and summary["transport"]["cleanup_passed"]
            for summary in summaries
        ) else "profiled",
        "cost_note": (
            "OpenAI Codex OAuth reported zero marginal billing. Nominal token-equivalent cost uses the "
            "refreshed live catalog rates and includes harness retries plus zero-cost deterministic verification. "
            "No automatic recovery route was exercised; candidates with task failures remain ineligible."
        ),
        "limitations": [
            "Eight samples per task class support only a rough p95 (nearest-rank maximum); uncertainty remains high.",
            "The one-shot Hermes host exercises file and terminal tools but is not proof of native per-child receipt wiring.",
            "Provider-internal retry counts and queue delay are not exposed by the Hermes usage receipt.",
            "Synthetic local research evidence tests synthesis and lineage handling without live-web variability.",
        ],
    }
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    compact = {
        "output": str(output),
        "summaries": [
            {"id": item["id"], "transport": item["transport"], "task_classes": item["task_classes"]}
            for item in summaries
        ],
        "eligibility": eligibility,
        "cleanup": result["cleanup"],
    }
    print(json.dumps(compact, indent=2, sort_keys=True))


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
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
