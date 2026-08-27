#!/usr/bin/env python
"""Pin one route receipt and map it to the smallest truthful surface path."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

import jsonschema

HEX64 = re.compile(r"^[0-9a-f]{64}$")
SURFACE_CONTRACTS = {
    "hermes-delegate": {
        "owner": "tools.delegate_task child construction",
        "enforcement": "staged-source-integration",
        "launch_allowed": False,
        "gap": "Hermes 0.20.5 delegate_task has one global delegation route and no per-child route/receipt fields.",
    },
    "hermes-task-thread": {
        "owner": "hermes chat one-shot/new session",
        "enforcement": "native-cli-external-pin",
        "launch_allowed": True,
        "gap": "The CLI pins model/provider/reasoning per process; this adapter owns the external immutable receipt.",
    },
    "cc-dynamic-workflow": {
        "owner": "integrations/hermes/cc-dynamic-workflows task attempt",
        "enforcement": "staged-repository-integration",
        "launch_allowed": False,
        "gap": "The checked-in compatibility runner consumes exact receipts, but it is not native Hermes DAG support or live-promoted behavior.",
    },
    "kanban-worker": {
        "owner": "Hermes Kanban task/task_runs and dispatcher spawn",
        "enforcement": "staged-source-integration",
        "launch_allowed": False,
        "gap": "Hermes 0.20.5 exposes model/provider overrides, but exact reasoning and decision-receipt propagation remain staged source work.",
    },
}
SUPPORTED_SURFACES = set(SURFACE_CONTRACTS)
SUPPORTED_REASONING_EFFORTS = {
    "none", "minimal", "low", "medium", "high", "xhigh", "max"
}
RECEIPT_SCHEMA_PATH = (
    Path(__file__).resolve().parents[1]
    / "skills"
    / "openai-delegation-route-research"
    / "references"
    / "route-decision.schema.json"
)
RECEIPT_SCHEMA = json.loads(RECEIPT_SCHEMA_PATH.read_text(encoding="utf-8"))
jsonschema.Draft202012Validator.check_schema(RECEIPT_SCHEMA)
RECEIPT_VALIDATOR = jsonschema.Draft202012Validator(RECEIPT_SCHEMA)


class RouteAdapterError(ValueError):
    """Raised when a decision cannot be truthfully mapped to a surface."""


class RunPinConflict(RouteAdapterError):
    """Raised when an existing run is offered a different receipt or launch input."""


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def validate_receipt(receipt: dict[str, Any], surface: str) -> dict[str, Any] | None:
    if surface not in SUPPORTED_SURFACES:
        raise RouteAdapterError(f"unsupported target surface: {surface}")
    if not isinstance(receipt, dict):
        raise RouteAdapterError("decision receipt must be an object")
    if receipt.get("schema_version") != 2:
        raise RouteAdapterError("decision receipt schema_version must be 2")
    if receipt.get("target_surface") != surface:
        raise RouteAdapterError("decision receipt target_surface does not match adapter surface")
    if receipt.get("outcome") not in {"selected", "fail_closed"}:
        raise RouteAdapterError("decision receipt outcome must be selected or fail_closed")
    legacy_fields = sorted(
        {"suite_hash", "pareto_frontier", "fallback_candidates"}.intersection(receipt)
    )
    if legacy_fields:
        raise RouteAdapterError(
            f"legacy decision field is unsupported: {', '.join(legacy_fields)}"
        )
    if receipt.get("objective") != "user-outcome":
        raise RouteAdapterError("decision receipt objective must be user-outcome")
    for key in ("decision_id", "policy_sha256", "requirement_sha256"):
        if not isinstance(receipt.get(key), str) or not HEX64.fullmatch(receipt[key]):
            raise RouteAdapterError(f"decision receipt {key} must be a lowercase SHA-256")
    attempt_number = receipt.get("attempt_number")
    if isinstance(attempt_number, bool) or not isinstance(attempt_number, int) or attempt_number < 1:
        raise RouteAdapterError("decision receipt attempt_number must be a positive integer")
    constraints = receipt.get("constraints_applied")
    if not isinstance(constraints, dict):
        raise RouteAdapterError("decision receipt constraints_applied must be an object")
    if digest(constraints) != receipt["requirement_sha256"]:
        raise RouteAdapterError("decision receipt constraints_applied does not match requirement_sha256")
    verifier_plan = receipt.get("verifier_plan")
    if not isinstance(verifier_plan, dict):
        raise RouteAdapterError("decision receipt verifier_plan must be an object")
    bound_fields = {
        "target_surface": receipt.get("target_surface"),
        "task_class": receipt.get("task_class"),
        "objective": receipt.get("objective"),
        "failure_cost": receipt.get("failure_cost"),
        "verifier_plan": verifier_plan,
    }
    for key, expected in bound_fields.items():
        if constraints.get(key) != expected:
            raise RouteAdapterError(
                f"decision receipt {key} does not match constraints_applied"
            )
    if receipt["attempt_number"] != constraints.get("attempt_number", 1):
        raise RouteAdapterError(
            "decision receipt attempt_number does not match constraints_applied"
        )
    if not isinstance(receipt.get("excluded"), dict):
        raise RouteAdapterError("decision receipt excluded must be an object")
    if not isinstance(receipt.get("policy_version"), str) or not receipt["policy_version"]:
        raise RouteAdapterError("decision receipt policy_version is required")
    try:
        RECEIPT_VALIDATOR.validate(receipt)
    except jsonschema.ValidationError as exc:
        location = ".".join(str(part) for part in exc.absolute_path) or "<root>"
        raise RouteAdapterError(
            f"decision receipt schema validation failed at {location}: {exc.message}"
        ) from exc
    if receipt["outcome"] == "fail_closed":
        if receipt.get("route") is not None:
            raise RouteAdapterError("fail_closed receipt route must be null")
        expected_id = digest(
            {
                "policy_sha256": receipt["policy_sha256"],
                "requirement_sha256": receipt["requirement_sha256"],
                "outcome": "fail_closed",
            }
        )
        if receipt["decision_id"] != expected_id:
            raise RouteAdapterError("decision receipt decision_id does not match its fail-closed decision")
        return None

    route = receipt.get("route")
    if not isinstance(route, dict):
        raise RouteAdapterError("selected decision receipt route must be an object")
    for key in ("id", "provider", "model", "reasoning_effort"):
        if not isinstance(route.get(key), str) or not route[key]:
            raise RouteAdapterError(f"decision receipt route.{key} is required")
    if route["provider"] != "openai-codex":
        raise RouteAdapterError("decision receipt route.provider must be openai-codex")
    if not route["model"].startswith("gpt-"):
        raise RouteAdapterError("decision receipt route.model must be a GPT model identifier")
    if route["reasoning_effort"] not in SUPPORTED_REASONING_EFFORTS:
        raise RouteAdapterError("decision receipt route.reasoning_effort is unsupported")
    runtime = route.get("runtime")
    if not isinstance(runtime, dict) or not runtime:
        raise RouteAdapterError("decision receipt route.runtime must be a non-empty object")
    if not isinstance(route.get("runtime_sha256"), str) or not HEX64.fullmatch(route["runtime_sha256"]):
        raise RouteAdapterError("decision receipt route.runtime_sha256 must be a SHA-256")
    if route["runtime_sha256"] != digest(runtime):
        raise RouteAdapterError("decision receipt route.runtime_sha256 does not match runtime")
    if runtime.get("transport") != surface:
        raise RouteAdapterError("decision receipt route.runtime transport does not match adapter surface")
    evidence = receipt.get("evidence_receipt")
    if not isinstance(evidence, dict) or not isinstance(evidence.get("locator"), str):
        raise RouteAdapterError("selected decision receipt evidence_receipt is required")
    if not isinstance(evidence.get("sha256"), str) or not HEX64.fullmatch(evidence["sha256"]):
        raise RouteAdapterError("decision receipt evidence_receipt.sha256 must be a SHA-256")
    if evidence["sha256"] != receipt["policy_sha256"]:
        raise RouteAdapterError(
            "decision receipt evidence_receipt.sha256 must match policy_sha256"
        )
    expected_id = digest(
        {
            "policy_sha256": receipt["policy_sha256"],
            "requirement_sha256": receipt["requirement_sha256"],
            "outcome": "selected",
            "route": route,
        }
    )
    if receipt["decision_id"] != expected_id:
        raise RouteAdapterError("decision receipt decision_id does not match its selected route")
    return route


def native_mapping(
    receipt: dict[str, Any],
    surface: str,
    *,
    prompt: str | None = None,
    cwd: str | None = None,
) -> dict[str, Any] | None:
    route = validate_receipt(receipt, surface)
    if route is None:
        return None
    contract = SURFACE_CONTRACTS[surface]
    common = {
        "owner": contract["owner"],
        "enforcement": contract["enforcement"],
        "launch_allowed": contract["launch_allowed"],
        "receipt_pinned_before_launch": True,
        "integration_gap": contract["gap"],
        "route": {
            "provider": route["provider"],
            "model": route["model"],
            "reasoning_effort": route["reasoning_effort"],
            "runtime": route["runtime"],
        },
    }
    if surface == "hermes-task-thread":
        if not prompt:
            raise RouteAdapterError("hermes-task-thread requires a prompt")
        workdir = str(Path(cwd or os.getcwd()).resolve())
        return {
            **common,
            "kind": "argv",
            "argv": [
                "hermes",
                "chat",
                "--model",
                route["model"],
                "--provider",
                route["provider"],
                "--reasoning",
                route["reasoning_effort"],
                "--source",
                "tool",
                "--in",
                workdir,
                "--query-file",
                "{prompt_file}",
            ],
            "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
            "_prompt_payload": prompt,
        }
    if surface == "cc-dynamic-workflow":
        return {
            **common,
            "kind": "task-fields",
            "fields": {
                "provider": route["provider"],
                "model": route["model"],
                "reasoning_effort": route["reasoning_effort"],
                "decision_receipt": receipt,
            },
            "adapter_path": "integrations/hermes/cc-dynamic-workflows/scripts/workflow_runner.py",
        }
    if surface == "kanban-worker":
        return {
            **common,
            "kind": "task-and-run-fields",
            "fields": {
                "provider_override": route["provider"],
                "model_override": route["model"],
                "reasoning_effort": route["reasoning_effort"],
                "route_receipt": receipt,
            },
        }
    return {
        **common,
        "kind": "child-construction-fields",
        "fields": {
            "provider": route["provider"],
            "model": route["model"],
            "reasoning_effort": route["reasoning_effort"],
            "decision_receipt": receipt,
        },
    }


def atomic_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def atomic_json(path: Path, value: dict[str, Any]) -> None:
    atomic_bytes(path, (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8"))


def _with_pin_lock(state_path: Path):
    lock_path = state_path.with_name(f".{state_path.name}.pin.lock")
    state_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise RouteAdapterError(f"run pin is busy: {state_path}") from exc
    os.close(fd)
    return lock_path


def _verify_pinned_prompt(mapping: dict[str, Any] | None) -> None:
    if not mapping or mapping.get("kind") != "argv":
        return
    prompt_file = mapping.get("prompt_file")
    expected = mapping.get("prompt_sha256")
    if not isinstance(prompt_file, str) or not isinstance(expected, str):
        raise RunPinConflict("pinned prompt material is incomplete")
    try:
        actual = hashlib.sha256(Path(prompt_file).read_bytes()).hexdigest()
    except OSError as exc:
        raise RunPinConflict("pinned prompt material is missing or unreadable") from exc
    if actual != expected:
        raise RunPinConflict("pinned prompt material no longer matches its hash")


def prepare(
    receipt: dict[str, Any],
    surface: str,
    state_path: Path,
    *,
    run_id: str | None = None,
    prompt: str | None = None,
    cwd: str | None = None,
) -> dict[str, Any]:
    if run_id is None:
        run_id = state_path.resolve().as_posix()
    if not isinstance(run_id, str) or not run_id.strip():
        raise RouteAdapterError("run_id must be a non-empty string")
    mapping = native_mapping(receipt, surface, prompt=prompt, cwd=cwd)
    prompt_payload = None
    prompt_path = None
    if mapping and "_prompt_payload" in mapping:
        prompt_payload = mapping.pop("_prompt_payload")
        prompt_path = state_path.with_name(f"{state_path.stem}.prompt.txt").resolve()
        mapping["argv"] = [str(prompt_path) if item == "{prompt_file}" else item for item in mapping["argv"]]
        mapping["prompt_file"] = str(prompt_path)
    proposed = {
        "schema_version": 2,
        "run_id": run_id.strip(),
        "status": "blocked" if receipt["outcome"] == "fail_closed" else "prepared",
        "pin_status": "new",
        "target_surface": surface,
        "receipt_sha256": digest(receipt),
        "decision_receipt": receipt,
        "native_mapping": mapping,
    }

    lock_path = _with_pin_lock(state_path)
    try:
        if state_path.exists():
            try:
                existing = json.loads(state_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise RunPinConflict(f"existing run pin is unreadable: {state_path}") from exc
            comparable = dict(existing)
            comparable["pin_status"] = "new"
            if comparable != proposed:
                raise RunPinConflict(
                    f"run {run_id!r} is already pinned; policy movement cannot rewrite it"
                )
            _verify_pinned_prompt(existing.get("native_mapping"))
            reused = dict(existing)
            reused["pin_status"] = "reused"
            return reused
        if prompt_payload is not None and prompt_path is not None:
            atomic_bytes(prompt_path, prompt_payload.encode("utf-8"))
        atomic_json(state_path, proposed)
        return proposed
    finally:
        try:
            lock_path.unlink()
        except FileNotFoundError:
            pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--surface", required=True, choices=sorted(SUPPORTED_SURFACES))
    parser.add_argument("--receipt", required=True, type=Path)
    parser.add_argument("--state", required=True, type=Path)
    parser.add_argument(
        "--run-id",
        help="Stable run identity; defaults to the resolved state-file path for legacy callers",
    )
    parser.add_argument("--prompt")
    parser.add_argument("--cwd")
    args = parser.parse_args(argv)
    try:
        receipt = json.loads(args.receipt.read_text(encoding="utf-8"))
        state = prepare(
            receipt,
            args.surface,
            args.state,
            run_id=args.run_id,
            prompt=args.prompt,
            cwd=args.cwd,
        )
    except (OSError, json.JSONDecodeError, RouteAdapterError) as exc:
        parser.error(str(exc))
    print(json.dumps(state, indent=2, sort_keys=True))
    return 0 if state["status"] == "prepared" else 2


if __name__ == "__main__":
    raise SystemExit(main())
