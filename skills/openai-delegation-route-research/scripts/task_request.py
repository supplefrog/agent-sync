"""Bind a routing template to the controller's exact native execution input."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any

import jsonschema

_TEMPLATE_FIELDS = frozenset({"schema_version", "task_class", "requirements", "verifier", "effects", "failure_cost", "deterministic", "budget"})
_REQUIREMENT_FIELDS = frozenset({"tools", "context_tokens", "task_contract_sha256", "model", "reasoning_effort"})
_EXECUTOR_FIELDS = frozenset({"executor_id", "artifact_sha256", "task_contract_sha256", "coverage", "effects"})
_SCHEMA_PATH = Path(__file__).resolve().parents[1] / "references/route-task-v3.schema.json"
_VALIDATOR = jsonschema.Draft202012Validator(json.loads(_SCHEMA_PATH.read_bytes()), format_checker=jsonschema.FormatChecker())


def _json_value(value: Any) -> None:
    """Reject Python-only values that JSON would coerce into an ambiguous input."""
    if value is None or type(value) in (str, bool, int):
        return
    if type(value) is float and math.isfinite(value):
        return
    if type(value) is list:
        for item in value:
            _json_value(item)
        return
    if type(value) is dict and all(type(key) is str for key in value):
        for item in value.values():
            _json_value(item)
        return
    raise ValueError("Routing inputs must be finite JSON values with string object keys")


def input_digest(input_descriptor: Any) -> str:
    _json_value(input_descriptor)
    payload = json.dumps(input_descriptor, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def materialize(template: dict[str, Any], *, task_id: str, host: str, transport: str,
                input_descriptor: Any, as_of: str | None = None) -> dict[str, Any]:
    """Fill controller fields without inventing quality, costs, or authorization.

    The caller verifies template/catalog provenance, supplies the complete actual
    execution descriptor and freezes this result before dispatch. This function
    binds data; it neither verifies the declared executor nor launches it.
    """
    _json_value(template)
    if type(template) is not dict or set(template) != _TEMPLATE_FIELDS:
        raise ValueError("Routing template has missing, extra, or controller-owned fields")
    if type(template["schema_version"]) is not int or template["schema_version"] != 3:
        raise ValueError("Routing template schema_version must be integer 3")
    requirements = template["requirements"]
    if type(requirements) is not dict or set(requirements) != _REQUIREMENT_FIELDS:
        raise ValueError("Template requirements must omit controller-owned host and transport")
    deterministic = template["deterministic"]
    if deterministic is not None and (type(deterministic) is not dict or set(deterministic) != _EXECUTOR_FIELDS):
        raise ValueError("Deterministic template has invalid fields; input_sha256 is controller-owned")
    task = json.loads(json.dumps(template, ensure_ascii=False, allow_nan=False))
    digest = input_digest(input_descriptor)
    task.update(task_id=task_id, input_sha256=digest,
                as_of=datetime.now(timezone.utc).isoformat() if as_of is None else as_of,
                continuation=None)
    stamp = task["as_of"]
    if not isinstance(stamp, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}[Tt]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:[Zz]|[+-]\d{2}:\d{2})", stamp):
        raise ValueError("Routing as_of must be a timezone-qualified date-time")
    # jsonschema's optional format dependencies are not installed everywhere.
    datetime.fromisoformat(stamp[:-1] + "+00:00" if stamp[-1:] in ("Z", "z") else stamp)
    task["requirements"].update(host=host, transport=transport)
    if task["deterministic"] is not None:
        task["deterministic"]["input_sha256"] = digest
    errors = sorted(_VALIDATOR.iter_errors(task), key=lambda error: tuple(str(part) for part in error.absolute_path))
    if errors:
        error = errors[0]
        location = ".".join(str(part) for part in error.absolute_path) or "<root>"
        raise ValueError(f"Invalid materialized route task at {location}: {error.message}")
    return task


WORK_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {
        "task_class": {"type": "string", "minLength": 1},
        "acceptance": {"type": "string", "minLength": 1, "maxLength": 8000},
        "placement_reason": {"type": "string", "minLength": 1, "maxLength": 2000},
        "tools": {"type": "array", "uniqueItems": True,
                  "items": {"enum": ["read_file", "search_files"]}},
        "context_tokens": {"type": "integer", "minimum": 1},
        "max_requests": {"type": "integer", "minimum": 1, "maximum": 32},
        "accept_unknown_quota": {"type": "boolean"},
        "authorized": {"type": "boolean", "description": "Caller declares scoped trial permission; never bypasses native approval."},
        "quotas": _VALIDATOR.schema["properties"]["budget"]["properties"]["quotas"],
        "effects": {"enum": ["none", "reversible", "irreversible"]},
        "failure_cost": {"enum": ["low", "medium", "high"]},
    },
    "required": ["task_class", "acceptance", "placement_reason", "tools", "context_tokens",
                 "max_requests", "accept_unknown_quota", "authorized", "effects", "failure_cost"],
}


def work_template(work: dict[str, Any]) -> dict[str, Any]:
    """Describe work without choosing its executor. V3 binding stays internal.

    Acceptance describes the parent's planned check, not a completed verification.
    Only low-risk read-only work can be provisionally admitted by this consumer.
    Other risk/effect declarations produce a parent decision rather than lowering
    the work's stated risk to fit a worker lane.
    """
    _json_value(work)
    errors = list(jsonschema.Draft202012Validator(WORK_SCHEMA).iter_errors(work))
    if errors:
        raise ValueError("Invalid work description: " + errors[0].message)
    if not all(work[key].strip() for key in ("task_class", "acceptance", "placement_reason")):
        raise ValueError("Work descriptions must not be blank")
    template = evidence_review_template(
        candidate={"id": "unused", "route": {"model": None, "reasoning_effort": None}},
        protocol={"task_class": work["task_class"], "acceptance": work["acceptance"]},
        acceptance={"locator": "inline:parent-acceptance/" + input_digest(work["acceptance"]),
                    "sha256": input_digest(work["acceptance"])},
        context_tokens=work["context_tokens"], placement_reason=work["placement_reason"],
        max_requests=work["max_requests"], authorized=work["authorized"],
        accept_unknown_quota=work["accept_unknown_quota"], quotas=work.get("quotas", {}))
    template.update(task_class=work["task_class"], effects=work["effects"], failure_cost=work["failure_cost"])
    template["requirements"]["tools"] = work["tools"][:]
    template["budget"].update(unknown_cost_policy="task_preference", preference_order=[])
    return template


def evidence_review_template(*, candidate: dict[str, Any], protocol: str,
                             acceptance: dict[str, str], context_tokens: int,
                             placement_reason: str, max_requests: int,
                             authorized: bool, accept_unknown_quota: bool,
                             quotas: dict[str, Any]) -> dict[str, Any]:
    """Prepare a local source-review trial; caller retains permission and acceptance.

    Pass actual reserve/remaining declarations in quotas. An empty mapping means
    no declared reserve and no telemetry, never unlimited quota. No evidence or
    monetary value is invented. Host/transport and input identity remain native.
    """
    route = candidate["route"]
    return {
        "schema_version": 3, "task_class": "bounded-source-evidence-review",
        "requirements": {"tools": ["read_file", "search_files"],
            "context_tokens": context_tokens, "task_contract_sha256": input_digest(protocol),
            "model": route["model"], "reasoning_effort": route["reasoning_effort"]},
        "verifier": {"kind": "independent-review", "coverage": "complete",
            "independent": True, "scope": "artifact-effects", "evidence": acceptance},
        "effects": "none", "failure_cost": "low", "deterministic": None,
        "budget": {"objective": "quota", "api_remaining": None, "api_reserve": 0,
            "allow_api_spend": False, "quotas": quotas,
            "unknown_cost_policy": "explicit_preference", "preference_order": [candidate["id"]],
            "parent_available": True, "attempt_cap": 1, "attempts_used": 0,
            "fallback_route_id": None, "fallback_route_sha256": None,
            "evidence_trial": {"authorized": authorized, "max_requests": max_requests,
                "placement_reason": placement_reason, "accept_unknown_quota": accept_unknown_quota}},
    }

