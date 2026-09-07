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
    "hermes-workflow",
    "codex-workflow",
    "omp-workflow",
    "hermes-auxiliary",
)
SURFACE_HOSTS = {
    "hermes-delegate": "hermes",
    "hermes-task-thread": "hermes",
    "hermes-workflow": "hermes",
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


def _validate_catalog_v2(catalog: dict[str, Any]) -> None:
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


def _decide_route_v2(
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
    if receipt["outcome"] not in {"selected", "selected_model"}:
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


# V3 is additive. Its schemas are embedded so frozen selector replay remains
# self-contained; the reference JSON files are generated from these constants.
def _v3_object(properties, required=None):
    return {"type": "object", "properties": properties, "required": list(properties) if required is None else required,
            "additionalProperties": False}


_V3_TEXT = {"type": "string", "minLength": 1}
_V3_HASH = {"type": "string", "pattern": "^[a-f0-9]{64}$"}
_V3_OPTIONAL_HASH = {"oneOf": [{"type": "null"}, _V3_HASH]}
_V3_NUMBER = {"type": ["number", "null"], "minimum": 0}
_V3_STRINGS = {"type": "array", "items": _V3_TEXT, "uniqueItems": True}
_V3_TIME = {"type": "string", "format": "date-time"}
_V3_REF = _v3_object({"locator": _V3_TEXT, "sha256": _V3_HASH})
_V3_EFFECT = {"enum": ["none", "reversible", "irreversible"]}
_V3_ROUTE = _v3_object({key: _V3_TEXT for key in ("host", "transport", "provider", "model", "reasoning_effort", "runtime")}
                      | {"contract_sha256": _V3_HASH})
_V3_PARTS = _v3_object({key: _V3_NUMBER for key in ("generation", "verification", "fallback")})
_V3_COST = _v3_object({"billing": {"enum": ["subscription", "api"]}, "basis": {"enum": ["observed", "quoted", "unknown"]},
                      "task_contract_sha256": _V3_OPTIONAL_HASH, "verifier_sha256": _V3_OPTIONAL_HASH, "route_sha256": _V3_OPTIONAL_HASH,
                      "api_usd": _V3_PARTS,
                      "quota": {"oneOf": [{"type": "null"}, _v3_object({"bucket": _V3_TEXT, "unit": _V3_TEXT, "parts": _V3_PARTS})]},
                      "evidence": {"oneOf": [{"type": "null"}, _V3_REF]}})
_V3_AVAILABILITY = _v3_object({"status": {"enum": ["verified", "unverified"]}, "observed_at": _V3_TIME,
                              "valid_until": _V3_TIME, "route_sha256": _V3_HASH,
                              "context_tokens": {"type": ["integer", "null"], "minimum": 0},
                              "tools_verified": _V3_STRINGS, "allowed_effects": {"type": "array", "items": _V3_EFFECT, "uniqueItems": True},
                              "evidence": _V3_REF})
_V3_QUALITY = _v3_object({"task_class": _V3_TEXT, "task_contract_sha256": _V3_HASH, "verifier_sha256": _V3_HASH,
                         "route_sha256": _V3_HASH, "status": {"enum": ["qualified", "regression", "inconclusive"]},
                         "scope": {"enum": ["artifact-effects", "independent-review", "inline-text"]},
                         "evidence": _V3_REF})
_V3_CANDIDATE = _v3_object({"id": _V3_TEXT, "route": _V3_ROUTE, "availability": _V3_AVAILABILITY,
                           "quality": {"type": "array", "items": _V3_QUALITY}, "cost": _V3_COST,
                           "benchmark_priors": {"type": "array", "items": {"type": "object"}}})
V3_CATALOG_SCHEMA = _v3_object({"schema_version": {"const": 3}, "catalog_version": _V3_TEXT,
                               "candidates": {"type": "array", "items": _V3_CANDIDATE}})
_V3_REQUIREMENTS = _v3_object({"host": _V3_TEXT, "transport": _V3_TEXT, "tools": _V3_STRINGS,
                              "context_tokens": {"type": "integer", "minimum": 0}, "task_contract_sha256": _V3_HASH,
                              "model": {"type": ["string", "null"]}, "reasoning_effort": {"type": ["string", "null"]}})
_V3_VERIFIER = _v3_object({"kind": {"enum": ["deterministic", "independent-review", "schema-only", "none"]},
                          "independent": {"type": "boolean"}, "coverage": {"enum": ["complete", "partial", "none"]},
                          "scope": {"enum": ["artifact-effects", "independent-review", "inline-text"]}, "evidence": _V3_REF})
_V3_DETERMINISTIC = {"oneOf": [{"type": "null"}, _v3_object({"executor_id": _V3_TEXT, "artifact_sha256": _V3_HASH,
                        "task_contract_sha256": _V3_HASH, "input_sha256": _V3_HASH,
                        "coverage": {"enum": ["complete", "partial"]}, "effects": _V3_EFFECT})]}
_V3_CONTINUATION = {"oneOf": [{"type": "null"}, _v3_object({"previous_receipt": {"type": "object"},
                        "reason": {"enum": ["transport-failure", "verification-failure"]}, "failure_evidence": _V3_REF})]}
_V3_QUOTA = _v3_object({"unit": _V3_TEXT, "remaining": _V3_NUMBER, "reserve": {"type": "number", "minimum": 0}})
_V3_BUDGET = _v3_object({"objective": {"enum": ["api_usd", "quota"]}, "api_remaining": _V3_NUMBER,
                        "api_reserve": {"type": "number", "minimum": 0}, "allow_api_spend": {"type": "boolean"},
                        "quotas": {"type": "object", "additionalProperties": _V3_QUOTA},
                        "unknown_cost_policy": {"enum": ["explicit_preference", "keep_parent", "defer"]},
                        "preference_order": _V3_STRINGS, "parent_available": {"type": "boolean"},
                        "attempt_cap": {"type": "integer", "minimum": 1, "maximum": 2},
                        "attempts_used": {"type": "integer", "minimum": 0},
                        "fallback_route_id": {"type": ["string", "null"]}, "fallback_route_sha256": {"oneOf": [{"type": "null"}, _V3_HASH]}})
V3_TASK_SCHEMA = _v3_object({"schema_version": {"const": 3}, "task_id": _V3_TEXT, "task_class": _V3_TEXT,
                            "input_sha256": _V3_HASH,
                            "as_of": _V3_TIME, "requirements": _V3_REQUIREMENTS, "verifier": _V3_VERIFIER,
                            "effects": _V3_EFFECT, "failure_cost": {"enum": ["low", "medium", "high"]},
                            "deterministic": _V3_DETERMINISTIC, "budget": _V3_BUDGET, "continuation": _V3_CONTINUATION})
V3_DECISION_SCHEMA = _v3_object({"schema_version": {"const": 3}, "decision_id": _V3_HASH,
                                "outcome": {"enum": ["execute_deterministic", "selected_model", "keep_parent", "defer"]},
                                "policy_sha256": _V3_HASH, "requirement_sha256": _V3_HASH, "policy_version": _V3_TEXT,
                                "policy_locator": _V3_TEXT, "task_id": _V3_TEXT, "task_class": _V3_TEXT,
                                "task_contract_sha256": _V3_HASH, "verifier_sha256": _V3_HASH,
                                "input_sha256": _V3_HASH,
                                "continuation_contract_sha256": _V3_HASH,
                                "route": {"oneOf": [{"type": "null"}, _V3_ROUTE]}, "route_id": {"type": ["string", "null"]},
                                "executor": _V3_DETERMINISTIC, "selection_basis": _V3_TEXT,
                                "qualification": {"type": ["string", "null"]}, "cost_observation": {"type": ["object", "null"]},
                                "excluded": {"type": "object", "additionalProperties": _V3_STRINGS},
                                "evidence_used": {"type": "array", "items": _V3_REF},
                                "previous_decision_id": {"type": ["string", "null"]},
                                "attempt_number": {"type": "integer", "minimum": 1},
                                "attempt_policy": _v3_object({"cap": {"type": "integer", "minimum": 1, "maximum": 2},
                                    "fallback_route_id": {"type": ["string", "null"]}, "fallback_route_sha256": {"oneOf": [{"type": "null"}, _V3_HASH]}}),
                                "resource_claim": _V3_TEXT})


def _v3_validate(value, schema, label):
    try:
        from jsonschema import Draft202012Validator, FormatChecker
    except ImportError as exc:
        raise RouteSelectionError("v3 requires the repository's existing jsonschema dependency") from exc
    # Reject NaN/Infinity as well as structural errors; replay only accepts JSON values.
    try:
        json.dumps(value, allow_nan=False)
    except (ValueError, TypeError) as exc:
        raise RouteSelectionError(f"invalid {label}: not finite JSON") from exc
    errors = sorted(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(value), key=lambda e: str(e.absolute_path))
    if errors:
        raise RouteSelectionError(f"invalid {label}: {errors[0].json_path}: {errors[0].message}")


def _v3_time(value):
    import datetime
    return datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))


def _v3_total(parts):
    return None if any(value is None for value in parts.values()) else sum(parts.values())


def _v3_continuation_contract(task):
    """Only observation clock/resource readings and attempt history may change."""
    stable = json.loads(json.dumps(task))
    stable.pop("as_of")
    stable.pop("continuation")
    for field in ("attempts_used", "api_remaining", "parent_available"):
        stable["budget"].pop(field)
    for quota in stable["budget"]["quotas"].values():
        quota.pop("remaining")
    return digest(stable)


def _v3_scope_admissible(task):
    needs_effect_coverage = bool(task["requirements"]["tools"]) or task["effects"] != "none"
    return not needs_effect_coverage or task["verifier"]["scope"] == "artifact-effects"


def _v3_resource(candidate, task):
    """No conversion between API price, distinct quota buckets or unknown costs."""
    cost, budget = candidate["cost"], task["budget"]
    matches = (cost["task_contract_sha256"] == task["requirements"]["task_contract_sha256"]
               and cost["verifier_sha256"] == task["verifier"]["evidence"]["sha256"]
               and cost["route_sha256"] == digest(candidate["route"]))
    api = _v3_total(cost["api_usd"]) if matches else None
    quota = cost["quota"]
    units = _v3_total(quota["parts"]) if quota is not None and matches else None
    reasons = []
    if cost["basis"] != "unknown" and cost["route_sha256"] != digest(candidate["route"]):
        reasons.append("cost_route_binding_mismatch")
    if cost["basis"] != "unknown" and cost["evidence"] is None:
        reasons.append("cost_basis_has_no_evidence")
    # Generation billing does not exempt an API-based verifier or fallback.
    # A known positive component is a spend claim even when its total is unknown.
    api_charge_declared = any(amount is not None and amount > 0 for amount in cost["api_usd"].values())
    if cost["billing"] == "api" or api_charge_declared:
        if not budget["allow_api_spend"]:
            reasons.append("api_spend_not_allowed")
        if api is None or budget["api_remaining"] is None:
            reasons.append("api_budget_not_bounded")
        elif api > budget["api_remaining"] - budget["api_reserve"]:
            reasons.append("api_reserve_would_be_spent")
    if quota is not None:
        pool = budget["quotas"].get(quota["bucket"])
        if pool is None or pool["unit"] != quota["unit"] or pool["remaining"] is None:
            reasons.append("quota_state_unknown_or_incomparable")
        elif pool["remaining"] <= pool["reserve"]:
            reasons.append("quota_reserve_reached")
        elif units is not None and units > pool["remaining"] - pool["reserve"]:
            reasons.append("quota_reserve_would_be_spent")
        elif units is None and pool["reserve"] > 0:
            reasons.append("unknown_cost_cannot_protect_reserve")
    elif cost["billing"] == "subscription":
        reasons.append("subscription_quota_bucket_unknown")
    # A known-looking number without observed evidence must not win as measured cost.
    key, total = None, None
    if cost["basis"] == "observed" and cost["evidence"] is not None and matches:
        if budget["objective"] == "api_usd":
            key, total = ("api_usd",), api
        elif budget["objective"] == "quota" and quota is not None:
            key, total = ("quota", quota["bucket"], quota["unit"]), units
    return reasons, {"comparison_key": list(key) if key else None, "total": total,
                     "binding_status": "unknown" if cost["basis"] == "unknown" else "matched" if matches else "mismatched",
                     "api_usd_total": api, "quota_total": units, "cost": cost}


def _v3_receipt(catalog, task, outcome, basis, excluded, *, selected=None, qualification=None,
                costs=None, evidence=(), catalog_locator=None):
    continuation = task["continuation"]
    receipt = {"schema_version": 3, "outcome": outcome, "policy_sha256": digest(catalog),
               "requirement_sha256": digest(task), "policy_version": catalog["catalog_version"],
               "policy_locator": catalog_locator or "inline:catalog/" + catalog["catalog_version"],
               "task_id": task["task_id"], "task_class": task["task_class"],
               "task_contract_sha256": task["requirements"]["task_contract_sha256"], "verifier_sha256": task["verifier"]["evidence"]["sha256"],
               "input_sha256": task["input_sha256"],
               "continuation_contract_sha256": _v3_continuation_contract(task),
               "route": selected["route"] if selected else None, "route_id": selected["id"] if selected else None,
               "executor": task["deterministic"] if outcome == "execute_deterministic" else None,
               "selection_basis": basis, "qualification": qualification, "cost_observation": costs,
               "excluded": {key: sorted(set(value)) for key, value in sorted(excluded.items())},
               "evidence_used": list(evidence), "previous_decision_id": continuation["previous_receipt"]["decision_id"] if continuation else None,
               "attempt_number": task["budget"]["attempts_used"] + 1,
               "attempt_policy": {"cap": task["budget"]["attempt_cap"], "fallback_route_id": task["budget"]["fallback_route_id"],
                                  "fallback_route_sha256": task["budget"]["fallback_route_sha256"]},
               "resource_claim": "minimum comparable observed total" if basis == "minimum_observed_total" else "no cheapest-route or quota-conversion claim"}
    receipt["decision_id"] = digest(receipt)
    _v3_validate(receipt, V3_DECISION_SCHEMA, "v3 decision")
    return json.loads(json.dumps(receipt))


def validate_catalog_v3(catalog):
    _v3_validate(catalog, V3_CATALOG_SCHEMA, "v3 catalog")
    ids = [item["id"] for item in catalog["candidates"]]
    if len(ids) != len(set(ids)):
        raise RouteSelectionError("duplicate v3 candidate id")
    for candidate in catalog["candidates"]:
        if _v3_time(candidate["availability"]["observed_at"]) > _v3_time(candidate["availability"]["valid_until"]):
            raise RouteSelectionError("availability expires before its observation")
        cost = candidate["cost"]
        if cost["basis"] == "unknown":
            components = [*cost["api_usd"].values(), *(cost["quota"]["parts"].values() if cost["quota"] else [])]
            if any(value is not None for value in components):
                raise RouteSelectionError("unknown cost components must be null, not fabricated numbers")


def decide_route_v3(catalog, task, *, catalog_locator=None):
    validate_catalog_v3(catalog)
    _v3_validate(task, V3_TASK_SCHEMA, "v3 task")
    budget, requirement, verifier = task["budget"], task["requirements"], task["verifier"]
    continuation = task["continuation"]
    if (budget["attempts_used"] == 0) != (continuation is None):
        raise RouteSelectionError("a subsequent attempt requires its previous-decision/failure link")
    if (budget["fallback_route_id"] is None) != (budget["fallback_route_sha256"] is None):
        raise RouteSelectionError("fallback route id and exact route hash must be declared together")
    if continuation is not None:
        previous = continuation["previous_receipt"]
        _v3_validate(previous, V3_DECISION_SCHEMA, "previous v3 receipt")
        content = {key: value for key, value in previous.items() if key != "decision_id"}
        if digest(content) != previous["decision_id"] or previous["outcome"] != "selected_model" or previous["route"] is None:
            raise RouteSelectionError("invalid previous selected-model pin")
        expected = {"cap": budget["attempt_cap"], "fallback_route_id": budget["fallback_route_id"], "fallback_route_sha256": budget["fallback_route_sha256"]}
        if (previous["attempt_policy"] != expected or previous["attempt_number"] != budget["attempts_used"]
                or previous["continuation_contract_sha256"] != _v3_continuation_contract(task)
                or previous["task_id"] != task["task_id"] or previous["task_class"] != task["task_class"]
                or previous["task_contract_sha256"] != requirement["task_contract_sha256"] or previous["verifier_sha256"] != verifier["evidence"]["sha256"]):
            raise RouteSelectionError("continuation changed its bounded task/pin contract")
    fallback = "keep_parent" if budget["parent_available"] else "defer"

    def finish(outcome, basis, excluded=None, **kwargs):
        return _v3_receipt(catalog, task, outcome, basis, excluded or {}, catalog_locator=catalog_locator, **kwargs)

    scope_admissible = _v3_scope_admissible(task)
    complete_check = (verifier["independent"] and verifier["coverage"] == "complete"
                      and verifier["kind"] == "deterministic" and scope_admissible)
    handler = task["deterministic"]
    if (handler is not None and complete_check and handler["coverage"] == "complete"
            and handler["task_contract_sha256"] == requirement["task_contract_sha256"] and handler["effects"] == task["effects"]
            and handler["input_sha256"] == task["input_sha256"]
            and task["effects"] != "irreversible"):
        return finish("execute_deterministic", "existing_complete_deterministic_handler", evidence=[verifier["evidence"]])
    if budget["attempts_used"] >= budget["attempt_cap"]:
        return finish("defer", "attempt_cap_reached")
    if task["effects"] == "irreversible":
        return finish(fallback, "irreversible_effect_requires_parent")
    now = _v3_time(task["as_of"])
    eligible, excluded = [], {}
    for candidate in catalog["candidates"]:
        route, available = candidate["route"], candidate["availability"]
        reasons = []
        for field in ("host", "transport"):
            if route[field] != requirement[field]:
                reasons.append("required_" + field + "_mismatch")
        for field in ("model", "reasoning_effort"):
            if requirement[field] is not None and route[field] != requirement[field]:
                reasons.append("required_" + field + "_mismatch")
        if available["status"] != "verified" or available["route_sha256"] != digest(route):
            reasons.append("exact_callable_route_unverified")
        if not (_v3_time(available["observed_at"]) <= now <= _v3_time(available["valid_until"])):
            reasons.append("availability_outside_valid_window")
        if available["context_tokens"] is None or requirement["context_tokens"] > available["context_tokens"]:
            reasons.append("context_capacity_unverified_or_exceeded")
        if not set(requirement["tools"]).issubset(available["tools_verified"]):
            reasons.append("required_tools_unverified")
        if task["effects"] not in available["allowed_effects"]:
            reasons.append("effect_not_supported_on_surface")
        if not scope_admissible:
            reasons.append("verifier_scope_does_not_cover_effects")
        evidence = [item for item in candidate["quality"] if item["task_class"] == task["task_class"]
                    and item["task_contract_sha256"] == requirement["task_contract_sha256"]
                    and item["verifier_sha256"] == verifier["evidence"]["sha256"] and item["route_sha256"] == digest(route)
                    and item["scope"] == verifier["scope"]
                    and (not requirement["tools"] or item["scope"] == "artifact-effects")]
        qualified = (scope_admissible and verifier["independent"] and verifier["coverage"] == "complete"
                     and verifier["kind"] in {"deterministic", "independent-review"}
                     and any(item["status"] == "qualified" for item in evidence))
        if any(item["status"] == "regression" for item in evidence):
            reasons.append("local_task_regression")
        deterministic_trial = task["failure_cost"] == "low" and complete_check and task["effects"] in {"none", "reversible"}
        parent_review_trial = (
            task["failure_cost"] == "low" and task["effects"] == "none"
            and not requirement["tools"] and scope_admissible
            and verifier["kind"] == "independent-review" and verifier["independent"]
            and verifier["coverage"] == "complete" and verifier["scope"] == "independent-review"
            and budget["parent_available"] and budget["attempt_cap"] == 1
            and budget["attempts_used"] == 0 and task["continuation"] is None
            and budget["fallback_route_id"] is None and budget["fallback_route_sha256"] is None
            and budget["unknown_cost_policy"] == "explicit_preference"
            and budget["preference_order"] == [candidate["id"]]
        )
        provisional = deterministic_trial or parent_review_trial
        if not qualified and not provisional:
            reasons.append("no_matching_task_qualification_or_complete_low_risk_verifier")
        if continuation is not None:
            previous = continuation["previous_receipt"]
            expected_route = previous["route_id"] if continuation["reason"] == "transport-failure" else budget["fallback_route_id"]
            expected_hash = digest(previous["route"]) if continuation["reason"] == "transport-failure" else budget["fallback_route_sha256"]
            if candidate["id"] != expected_route or digest(route) != expected_hash:
                reasons.append("not_the_predeclared_retry_or_fallback_route")
            if continuation["reason"] == "verification-failure" and digest(route) == digest(previous["route"]):
                reasons.append("verification_failure_cannot_repeat_same_route")
        resource_reasons, costs = _v3_resource(candidate, task)
        reasons.extend(resource_reasons)
        if reasons:
            excluded[candidate["id"]] = reasons
        else:
            eligible.append((candidate, "qualified" if qualified else ("provisional-parent-review-trial" if parent_review_trial else "provisional-complete-verifier"), costs, evidence))
    if not eligible:
        return finish(fallback, "no_eligible_delegation_route", excluded)
    keys = {tuple(item[2]["comparison_key"] or []) for item in eligible}
    comparable = len(keys) == 1 and () not in keys and all(item[2]["total"] is not None for item in eligible)
    if comparable:
        selected = min(eligible, key=lambda item: (item[2]["total"], item[0]["id"]))
        basis = "minimum_observed_total"
    elif budget["unknown_cost_policy"] == "explicit_preference":
        selected = next((item for route_id in budget["preference_order"] for item in eligible if item[0]["id"] == route_id), None)
        if selected is None:
            return finish(fallback, "unknown_cost_has_no_explicit_eligible_preference", excluded)
        basis = "explicit_preference_with_unknown_or_incomparable_cost"
    else:
        outcome = "defer" if budget["unknown_cost_policy"] == "defer" else fallback
        return finish(outcome, "cost_unknown_or_incomparable", excluded)
    candidate, qualification, costs, local = selected
    evidence = [candidate["availability"]["evidence"], verifier["evidence"], *[item["evidence"] for item in local]]
    if candidate["cost"]["evidence"] is not None:
        evidence.append(candidate["cost"]["evidence"])
    return finish("selected_model", basis, excluded, selected=candidate, qualification=qualification, costs=costs, evidence=evidence)


def validate_catalog(catalog):
    if isinstance(catalog, dict) and catalog.get("schema_version") == 3:
        return validate_catalog_v3(catalog)
    return _validate_catalog_v2(catalog)


def decide_route(catalog, task, *, catalog_locator=None):
    if isinstance(catalog, dict) and isinstance(task, dict) and (catalog.get("schema_version") == 3 or task.get("schema_version") == 3):
        if catalog.get("schema_version") != 3 or task.get("schema_version") != 3:
            raise RouteSelectionError("new routing requires explicit v3 catalog and v3 task; legacy receipts are not migrated")
        return decide_route_v3(catalog, task, catalog_locator=catalog_locator)
    return _decide_route_v2(catalog, task, catalog_locator=catalog_locator)


def replay_decision(receipt, frozen_catalog, frozen_task):
    if not isinstance(receipt, dict):
        raise RouteSelectionError("receipt must be an object")
    if receipt.get("schema_version") == 3:
        _v3_validate(receipt, V3_DECISION_SCHEMA, "v3 replay receipt")
        content = {key: value for key, value in receipt.items() if key != "decision_id"}
        if digest(content) != receipt["decision_id"]:
            raise RouteSelectionError("v3 receipt content does not match its decision hash")
    locator = receipt.get("policy_locator") if receipt.get("schema_version") == 3 else (receipt.get("evidence_receipt") or {}).get("locator")
    expected = decide_route(frozen_catalog, frozen_task, catalog_locator=locator)
    same = canonical_json(receipt) == canonical_json(expected) if receipt.get("schema_version") == 3 else receipt == expected
    if not same:
        raise RouteSelectionError("receipt does not match its frozen policy/task inputs")
    return json.loads(json.dumps(receipt))


def dispatch_decision(receipt, frozen_catalog, frozen_task):
    """Return an explicit dispatch instruction; never launch anything here."""
    receipt = replay_decision(receipt, frozen_catalog, frozen_task)
    outcome = receipt["outcome"]
    if outcome in {"selected", "selected_model"}:
        return {"kind": "model", "route": receipt["route"], "decision_id": receipt["decision_id"]}
    if outcome == "execute_deterministic":
        return {"kind": "deterministic", "executor": receipt["executor"], "decision_id": receipt["decision_id"]}
    return {"kind": "parent" if outcome == "keep_parent" else "defer", "route": None, "decision_id": receipt["decision_id"]}


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
    return 0 if decision["outcome"] in {"selected", "selected_model", "execute_deterministic", "keep_parent"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
