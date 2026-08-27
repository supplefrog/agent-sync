#!/usr/bin/env python
"""Run one bounded real smoke task through Codex and OMP route adapters."""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import importlib.util
import json
import shutil
import statistics
import subprocess
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ROUTES = [
    {"id": "luna-high", "provider": "openai-codex", "model": "gpt-5.6-luna", "reasoning_effort": "high"},
    {"id": "sol-low", "provider": "openai-codex", "model": "gpt-5.6-sol", "reasoning_effort": "low"},
]
SURFACES = ("codex-workflow", "omp-workflow")


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


ADAPTER = load_module("route_adapter", REPO / "tools" / "route_adapter.py")
EVAL = load_module("route_eval", REPO / "tools" / "run_route_eval.py")


def digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def smoke_receipt(route: dict, surface: str, suite: dict) -> dict:
    return {
        "schema_version": 1,
        "policy_version": "smoke-only-unpromoted-2026-08-15",
        "policy_sha256": "0" * 64,
        "requirement_sha256": digest({"surface": surface, "case": suite["cases"][0]["id"]}),
        "target_surface": surface,
        "task_class": suite["cases"][0]["task_class"],
        "objective": "speed",
        "failure_cost": "low",
        "route": {
            **route,
            "runtime": {"transport": surface, "catalog": "live-cli"},
        },
        "metrics": {},
        "evidence_receipt": "self:smoke-only",
        "pareto_frontier": [route["id"]],
        "excluded": {},
    }


def run_one(route: dict, surface: str, case: dict, scratch: Path) -> dict:
    receipt = smoke_receipt(route, surface, {"cases": [case]})
    state_path = scratch / f"{surface}-{route['id']}-state.json"
    state = ADAPTER.prepare(
        receipt,
        surface,
        state_path,
        prompt=case["prompt"],
        cwd=str(scratch),
    )
    argv = list(state["native_mapping"]["argv"])
    executable = shutil.which(argv[0])
    if not executable:
        return {
            "surface": surface,
            "route_id": route["id"],
            "passed": False,
            "exit_code": 127,
            "duration_seconds": 0.0,
            "error": f"missing executable: {argv[0]}",
            "receipt_persisted_before_launch": state_path.exists(),
            "cleanup_passed": True,
        }
    argv[0] = executable
    output_path = scratch / f"{surface}-{route['id']}-output.txt"
    if surface == "codex-workflow":
        argv[-1:-1] = ["--output-last-message", str(output_path)]
    started = time.perf_counter()
    try:
        proc = subprocess.run(
            argv,
            cwd=scratch,
            env=EVAL.isolated_env(),
            text=True,
            capture_output=True,
            timeout=300,
            check=False,
        )
        exit_code = proc.returncode
        output = (
            output_path.read_text(encoding="utf-8", errors="replace")
            if output_path.exists()
            else proc.stdout
        )
        error = None if exit_code == 0 else (proc.stderr[-1000:] or None)
    except subprocess.TimeoutExpired as exc:
        exit_code = 124
        output = exc.stdout or ""
        error = "timeout"
    duration = round(time.perf_counter() - started, 3)
    parsed = None
    passed = False
    if exit_code == 0:
        try:
            parsed = EVAL.parse_object(output)
            passed = parsed == case["expected"]
        except Exception as exc:
            error = f"{error or ''}\nparse: {exc}".strip()
    return {
        "surface": surface,
        "route_id": route["id"],
        "route": route,
        "case_id": case["id"],
        "passed": passed,
        "exit_code": exit_code,
        "duration_seconds": duration,
        "parsed": parsed,
        "error": error,
        "receipt_persisted_before_launch": state_path.exists(),
        "cleanup_passed": "--ephemeral" in argv or "--no-session" in argv,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", type=Path, default=REPO / "evals/suites/adaptive-routing-smoke.json")
    parser.add_argument("--output", type=Path, default=REPO / "evals/results/adaptive-routing-surface-smoke-2026-08-15.json")
    parser.add_argument("--concurrency", type=int, default=2)
    args = parser.parse_args()
    suite = json.loads(args.suite.resolve().read_text(encoding="utf-8"))
    case = suite["cases"][0]
    with tempfile.TemporaryDirectory(prefix="route-surface-smoke-") as temp:
        scratch = Path(temp)
        jobs = [(route, surface) for surface in SURFACES for route in ROUTES]
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as pool:
            trials = list(pool.map(lambda item: run_one(item[0], item[1], case, scratch), jobs))
    summaries = []
    for surface in SURFACES:
        rows = [row for row in trials if row["surface"] == surface]
        summaries.append({
            "target_surface": surface,
            "sample_size": len(rows),
            "passed": sum(row["passed"] for row in rows),
            "p50_seconds": round(statistics.median(row["duration_seconds"] for row in rows), 3),
            "max_seconds": max(row["duration_seconds"] for row in rows),
            "cleanup_passed": all(row["cleanup_passed"] for row in rows),
            "receipts_persisted_before_launch": all(row["receipt_persisted_before_launch"] for row in rows),
        })
    result = {
        "schema_version": 1,
        "evidence_state": "callable-smoke",
        "suite_id": suite["suite_id"],
        "suite_sha256": digest(suite),
        "case_id": case["id"],
        "routes": ROUTES,
        "summaries": summaries,
        "trials": trials,
        "limitations": [
            "One deterministic task per route/surface proves callable adapter wiring only.",
            "No task-class route is promoted from this small smoke sample.",
        ],
    }
    args.output.resolve().parent.mkdir(parents=True, exist_ok=True)
    args.output.resolve().write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output.resolve()), "summaries": summaries}, indent=2))
    return 0 if all(row["exit_code"] == 0 for row in trials) else 1


if __name__ == "__main__":
    raise SystemExit(main())
