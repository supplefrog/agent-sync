#!/usr/bin/env python
"""Automatically choose and pin a GPT route from a reviewed AA catalogue."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import tempfile
from pathlib import Path
from typing import Any

REASONING_LEVELS = ("none", "minimal", "low", "medium", "high", "xhigh", "max")
SURFACES = (
    "hermes-delegate",
    "hermes-task-thread",
    "codex-workflow",
    "omp-workflow",
    "hermes-auxiliary",
)
SURFACE_HOSTS = {
    "hermes-delegate": "hermes",
    "hermes-task-thread": "hermes",
    "codex-workflow": "codex",
    "omp-workflow": "omp",
    "hermes-auxiliary": "hermes",
}
FAILURE_COSTS = ("low", "medium", "high")
INTELLIGENCE_TIERS = ("routine", "standard", "strong", "demanding", "maximum")
APPROVED_METRICS = {
    "intelligence": "Artificial Analysis Intelligence Index",
    "time": "Time per Intelligence Index Task (minutes)",
    "cost": "Cost per Intelligence Index Task (USD)",
    "hallucination": "AA-Omniscience Hallucination Rate (%)",
}


class RouteSelectionError(ValueError):
    """The catalogue or route request is invalid."""


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _number(value: Any, field: str, *, positive: bool = False, maximum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RouteSelectionError(f"{field} must be a number")
    result = float(value)
    if not math.isfinite(result) or result < 0 or (positive and result <= 0):
        qualifier = "positive" if positive else "non-negative"
        raise RouteSelectionError(f"{field} must be a finite {qualifier} number")
    if maximum is not None and result > maximum:
        raise RouteSelectionError(f"{field} must be at most {maximum:g}")
    return result


def _route_key(route: dict[str, Any]) -> tuple[str, str]:
    return route["model"], route["reasoning_effort"]


def _route_identity(route: dict[str, Any], surface: str) -> dict[str, Any]:
    runtime = {
        "host": SURFACE_HOSTS[surface],
        "transport": surface,
        "selector_contract": "automatic-gpt-frontier-v1",
    }
    return {
        "id": route["id"],
        "provider": "openai-codex",
        "model": route["model"],
        "reasoning_effort": route["reasoning_effort"],
        "runtime": runtime,
        "runtime_sha256": digest(runtime),
    }


def validate_catalog(catalog: dict[str, Any]) -> None:
    if not isinstance(catalog, dict):
        raise RouteSelectionError("catalogue must be an object")
    allowed_catalog = {
        "$schema",
        "schema_version",
        "status",
        "catalog_version",
        "provider",
        "source",
        "intelligence_tiers",
        "delegation_candidates",
        "recommendations",
    }
    unknown = set(catalog) - allowed_catalog
    if unknown:
        raise RouteSelectionError(f"catalogue has unknown fields: {', '.join(sorted(unknown))}")
    if catalog.get("schema_version") != 2:
        raise RouteSelectionError("catalogue schema_version must be 2")
    if catalog.get("status") != "active":
        raise RouteSelectionError("catalogue must be active")
    if not isinstance(catalog.get("catalog_version"), str) or not catalog["catalog_version"]:
        raise RouteSelectionError("catalogue catalog_version is required")
    if catalog.get("provider") != "openai-codex":
        raise RouteSelectionError("catalogue provider must be openai-codex")

    source = catalog.get("source")
    if not isinstance(source, dict) or set(source) != {"name", "url", "observed_at", "metrics"}:
        raise RouteSelectionError("catalogue source must contain name, url, observed_at, and metrics")
    if source.get("name") != "Artificial Analysis":
        raise RouteSelectionError("catalogue source must be Artificial Analysis")
    if not isinstance(source.get("url"), str) or not source["url"].startswith("https://artificialanalysis.ai/"):
        raise RouteSelectionError("catalogue source URL must be on artificialanalysis.ai")
    if not isinstance(source.get("observed_at"), str) or not source["observed_at"]:
        raise RouteSelectionError("active catalogue source.observed_at is required")
    if source.get("metrics") != APPROVED_METRICS:
        raise RouteSelectionError("catalogue must use the four approved Artificial Analysis metrics")

    routes = catalog.get("delegation_candidates")
    if not isinstance(routes, list) or not routes:
        raise RouteSelectionError("active catalogue needs at least one delegation candidate")
    ids: set[str] = set()
    tuples: set[tuple[str, str]] = set()
    required_metrics = {
        "intelligence_index",
        "time_per_task_minutes",
        "cost_per_task_usd",
        "hallucination_rate_percent",
    }
    for index, route in enumerate(routes):
        prefix = f"delegation_candidates[{index}]"
        if not isinstance(route, dict) or set(route) != {
            "id",
            "model",
            "reasoning_effort",
            "artificial_analysis",
        }:
            raise RouteSelectionError(
                f"{prefix} must contain exactly id, model, reasoning_effort, and artificial_analysis"
            )
        route_id = route.get("id")
        if not isinstance(route_id, str) or not route_id:
            raise RouteSelectionError(f"{prefix}.id is required")
        if route_id in ids:
            raise RouteSelectionError(f"duplicate route id: {route_id}")
        ids.add(route_id)
        model = route.get("model")
        if not isinstance(model, str) or not model.startswith("gpt-"):
            raise RouteSelectionError(f"{prefix}.model must be a GPT model identifier")
        effort = route.get("reasoning_effort")
        if effort not in REASONING_LEVELS:
            raise RouteSelectionError(f"{prefix}.reasoning_effort is unsupported")
        route_tuple = _route_key(route)
        if route_tuple in tuples:
            raise RouteSelectionError(f"duplicate model/reasoning tuple: {model}::{effort}")
        tuples.add(route_tuple)
        values = route.get("artificial_analysis")
        if not isinstance(values, dict) or set(values) != required_metrics:
            raise RouteSelectionError(f"{prefix}.artificial_analysis must contain exactly the four required metrics")
        _number(values["intelligence_index"], f"{prefix}.artificial_analysis.intelligence_index")
        _number(values["time_per_task_minutes"], f"{prefix}.artificial_analysis.time_per_task_minutes", positive=True)
        _number(values["cost_per_task_usd"], f"{prefix}.artificial_analysis.cost_per_task_usd")
        _number(
            values["hallucination_rate_percent"],
            f"{prefix}.artificial_analysis.hallucination_rate_percent",
            maximum=100,
        )

    tiers = catalog.get("intelligence_tiers")
    if not isinstance(tiers, dict) or set(tiers) != set(INTELLIGENCE_TIERS):
        raise RouteSelectionError(
            "catalogue intelligence_tiers must contain: " + ", ".join(INTELLIGENCE_TIERS)
        )
    previous = -1.0
    for tier in INTELLIGENCE_TIERS:
        item = tiers[tier]
        if not isinstance(item, dict) or set(item) != {"minimum_intelligence_index", "description"}:
            raise RouteSelectionError(
                f"intelligence_tiers.{tier} must contain minimum_intelligence_index and description"
            )
        floor = _number(item["minimum_intelligence_index"], f"intelligence_tiers.{tier}.minimum_intelligence_index")
        if floor <= previous:
            raise RouteSelectionError("intelligence tier floors must be strictly increasing")
        previous = floor
        if not isinstance(item["description"], str) or not item["description"].strip():
            raise RouteSelectionError(f"intelligence_tiers.{tier}.description is required")
        if not any(float(route["artificial_analysis"]["intelligence_index"]) >= floor for route in routes):
            raise RouteSelectionError(f"intelligence tier {tier} has no eligible route")

    recommendations = catalog.get("recommendations")
    if not isinstance(recommendations, list) or not recommendations:
        raise RouteSelectionError("catalogue needs at least one reviewed recommendation")
    names: set[str] = set()
    for index, recommendation in enumerate(recommendations):
        prefix = f"recommendations[{index}]"
        if not isinstance(recommendation, dict) or set(recommendation) != {
            "name",
            "route_id",
            "use_when",
            "why",
        }:
            raise RouteSelectionError(f"{prefix} must contain exactly name, route_id, use_when, and why")
        for field in ("name", "route_id", "use_when", "why"):
            if not isinstance(recommendation.get(field), str) or not recommendation[field].strip():
                raise RouteSelectionError(f"{prefix}.{field} must be a non-empty string")
        if recommendation["name"] in names:
            raise RouteSelectionError(f"duplicate recommendation name: {recommendation['name']}")
        names.add(recommendation["name"])
        if recommendation["route_id"] not in ids:
            raise RouteSelectionError(f"{prefix} references unknown route: {recommendation['route_id']}")


def validate_task(task: dict[str, Any]) -> None:
    if not isinstance(task, dict):
        raise RouteSelectionError("task request must be an object")
    allowed = {
        "target_surface",
        "intelligence_tier",
        "latency_sensitive",
        "selected_route_id",
        "selection_reason",
        "task_id",
        "task_class",
        "failure_cost",
        "attempt_number",
        "verifier_plan",
    }
    unknown = set(task) - allowed
    if unknown:
        raise RouteSelectionError(f"task request has unknown fields: {', '.join(sorted(unknown))}")
    if task.get("target_surface") not in SURFACES:
        raise RouteSelectionError("task request target_surface is unsupported")
    if task.get("intelligence_tier") not in INTELLIGENCE_TIERS:
        raise RouteSelectionError("task request intelligence_tier is unsupported")
    if not isinstance(task.get("latency_sensitive"), bool):
        raise RouteSelectionError("task request latency_sensitive must be true or false")
    route_override = task.get("selected_route_id")
    reason = task.get("selection_reason")
    if route_override is not None and (not isinstance(route_override, str) or not route_override.strip()):
        raise RouteSelectionError("task request selected_route_id must be a non-empty string")
    if route_override is not None and (not isinstance(reason, str) or not reason.strip()):
        raise RouteSelectionError("task request selection_reason is required for a manual override")
    if route_override is None and reason is not None:
        raise RouteSelectionError("task request selection_reason requires selected_route_id")
    if "task_id" in task and (not isinstance(task["task_id"], str) or not task["task_id"]):
        raise RouteSelectionError("task request task_id must be a non-empty string")
    if "task_class" in task and (not isinstance(task["task_class"], str) or not task["task_class"]):
        raise RouteSelectionError("task request task_class must be a non-empty string")
    if task.get("failure_cost", "medium") not in FAILURE_COSTS:
        raise RouteSelectionError("task request failure_cost is unsupported")
    attempt = task.get("attempt_number", 1)
    if isinstance(attempt, bool) or not isinstance(attempt, int) or attempt < 1:
        raise RouteSelectionError("task request attempt_number must be a positive integer")
    verifier = task.get("verifier_plan", {"kind": "none"})
    if not isinstance(verifier, dict):
        raise RouteSelectionError("task request verifier_plan must be an object")


def _constraints(catalog: dict[str, Any], task: dict[str, Any]) -> dict[str, Any]:
    tier = task["intelligence_tier"]
    manual = "selected_route_id" in task
    result: dict[str, Any] = {
        "target_surface": task["target_surface"],
        "task_class": task.get("task_class", "delegation"),
        "objective": "user-outcome",
        "failure_cost": task.get("failure_cost", "medium"),
        "attempt_number": task.get("attempt_number", 1),
        "verifier_plan": task.get("verifier_plan", {"kind": "none"}),
        "intelligence_tier": tier,
        "minimum_intelligence_index": float(
            catalog["intelligence_tiers"][tier]["minimum_intelligence_index"]
        ),
        "latency_sensitive": task["latency_sensitive"],
        "selection_priority": "speed" if task["latency_sensitive"] else "cost",
        "selection_mode": "manual-override" if manual else "automatic",
        "selection_owner": "deterministic-frontier-selector",
    }
    if manual:
        result["selected_route_id"] = task["selected_route_id"]
        result["selection_reason"] = task["selection_reason"]
    if "task_id" in task:
        result["task_id"] = task["task_id"]
    return result


def _base_receipt(
    catalog: dict[str, Any], task: dict[str, Any], outcome: str, excluded: dict[str, list[str]]
) -> dict[str, Any]:
    policy_hash = digest(catalog)
    constraints = _constraints(catalog, task)
    requirement_hash = digest(constraints)
    return {
        "schema_version": 2,
        "decision_id": digest(
            {
                "policy_sha256": policy_hash,
                "requirement_sha256": requirement_hash,
                "outcome": outcome,
            }
        ),
        "outcome": outcome,
        "pin_status": "new" if outcome == "selected" else "denied",
        "policy_version": catalog["catalog_version"],
        "policy_sha256": policy_hash,
        "requirement_sha256": requirement_hash,
        "target_surface": task["target_surface"],
        "task_class": constraints["task_class"],
        "objective": "user-outcome",
        "failure_cost": constraints["failure_cost"],
        "attempt_number": constraints["attempt_number"],
        "constraints_applied": constraints,
        "route": None,
        "metrics": {},
        "evidence_receipt": None,
        "excluded": {key: excluded[key] for key in sorted(excluded)},
        "verifier_plan": constraints["verifier_plan"],
    }


def _rank_key(route: dict[str, Any], *, latency_sensitive: bool) -> tuple[Any, ...]:
    metrics = route["artificial_analysis"]
    intelligence = float(metrics["intelligence_index"])
    task_time = float(metrics["time_per_task_minutes"])
    cost = float(metrics["cost_per_task_usd"])
    hallucination = float(metrics["hallucination_rate_percent"])
    if latency_sensitive:
        return task_time, cost, hallucination, -intelligence, route["id"]
    return cost, task_time, hallucination, -intelligence, route["id"]


def decide_route(
    catalog: dict[str, Any], task: dict[str, Any], *, catalog_locator: str | None = None
) -> dict[str, Any]:
    """Choose the cheapest or fastest route that meets the task intelligence floor."""
    validate_catalog(catalog)
    validate_task(task)
    floor = float(
        catalog["intelligence_tiers"][task["intelligence_tier"]]["minimum_intelligence_index"]
    )
    routes = catalog["delegation_candidates"]
    excluded: dict[str, list[str]] = {}
    eligible: list[dict[str, Any]] = []
    for route in routes:
        intelligence = float(route["artificial_analysis"]["intelligence_index"])
        if intelligence < floor:
            excluded[route["id"]] = ["below_intelligence_floor"]
        else:
            eligible.append(route)

    override_id = task.get("selected_route_id")
    if override_id is not None:
        selected = next((route for route in routes if route["id"] == override_id), None)
        if selected is None:
            excluded[override_id] = ["selected_route_not_in_catalogue"]
            return _base_receipt(catalog, task, "fail_closed", excluded)
        if selected not in eligible:
            return _base_receipt(catalog, task, "fail_closed", excluded)
    elif eligible:
        selected = min(
            eligible,
            key=lambda route: _rank_key(route, latency_sensitive=task["latency_sensitive"]),
        )
    else:
        return _base_receipt(catalog, task, "fail_closed", excluded)

    receipt = _base_receipt(catalog, task, "selected", excluded)
    selected_identity = _route_identity(selected, task["target_surface"])
    receipt["decision_id"] = digest(
        {
            "policy_sha256": receipt["policy_sha256"],
            "requirement_sha256": receipt["requirement_sha256"],
            "outcome": "selected",
            "route": selected_identity,
        }
    )
    metrics = selected["artificial_analysis"]
    receipt["route"] = selected_identity
    receipt["metrics"] = {
        "artificial_analysis_intelligence_index": float(metrics["intelligence_index"]),
        "artificial_analysis_time_per_task_minutes": float(metrics["time_per_task_minutes"]),
        "artificial_analysis_cost_per_task_usd": float(metrics["cost_per_task_usd"]),
        "artificial_analysis_hallucination_rate_percent": float(
            metrics["hallucination_rate_percent"]
        ),
    }
    receipt["evidence_receipt"] = {
        "locator": catalog_locator or f"inline:catalog/{catalog['catalog_version']}",
        "sha256": receipt["policy_sha256"],
    }
    return receipt


def select_route(
    catalog: dict[str, Any], task: dict[str, Any], *, catalog_locator: str | None = None
) -> dict[str, Any]:
    receipt = decide_route(catalog, task, catalog_locator=catalog_locator)
    if receipt["outcome"] != "selected":
        detail = "; ".join(
            f"{key}: {','.join(value)}" for key, value in receipt["excluded"].items()
        )
        raise RouteSelectionError(f"no route selected ({detail})")
    return receipt


def atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="action", required=True)
    select = subparsers.add_parser("select")
    select.add_argument("--catalog", type=Path, required=True)
    select.add_argument("--task", type=Path, required=True)
    select.add_argument("--out", type=Path)
    validate = subparsers.add_parser("validate")
    validate.add_argument("--catalog", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        catalog = json.loads(args.catalog.read_text(encoding="utf-8"))
        if args.action == "validate":
            validate_catalog(catalog)
            print(
                json.dumps(
                    {"status": "valid", "catalog_version": catalog["catalog_version"]},
                    sort_keys=True,
                )
            )
            return 0
        task = json.loads(args.task.read_text(encoding="utf-8"))
        decision = decide_route(catalog, task, catalog_locator=args.catalog.as_posix())
    except (OSError, json.JSONDecodeError, RouteSelectionError) as exc:
        parser.error(str(exc))
    if args.out:
        atomic_json(args.out, decision)
    else:
        print(json.dumps(decision, indent=2, sort_keys=True))
    return 0 if decision["outcome"] == "selected" else 2


if __name__ == "__main__":
    raise SystemExit(main())
