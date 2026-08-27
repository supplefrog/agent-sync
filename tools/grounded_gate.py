#!/usr/bin/env python
"""Validate independent grounded verification contracts and fail closed."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import jsonschema

REPO = Path(__file__).resolve().parents[1]
REQUIRED_ROLES = {
    "intent_owner",
    "specification_owner",
    "test_author",
    "implementer",
    "oracle_owner",
    "verdict_owner",
}
REQUIRED_CRITERIA = {"capability", "infrastructure_burden", "cost", "portability", "non_goal"}
IMPLEMENTER_DENIALS = {"held_out_tests", "oracle_logic", "rubrics", "gate_recipes"}
DETERMINISTIC_KINDS = {"deterministic", "property", "metamorphic", "mutation", "equivalent-teeth"}
TRIVIAL_PROBES = {"true", "false", "pass", "echo pass", "noop"}


def canonical_sha256(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def validate_schema(contract: dict[str, Any]) -> list[str]:
    schema = json.loads((REPO / "contracts" / "grounded-verification.schema.json").read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker())
    return ["schema: " + error.message for error in sorted(validator.iter_errors(contract), key=lambda item: list(item.path))]


def parse_time(value: str, field: str, errors: list[str]) -> dt.datetime | None:
    try:
        return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError):
        errors.append(f"{field} must be an ISO-8601 timestamp")
        return None


def role_boundary(contract: dict[str, Any], role: str) -> dict[str, Any] | None:
    return next((item for item in contract.get("isolation", []) if item.get("subject_role") == role), None)


def verification_manifest(contract: dict[str, Any]) -> dict[str, Any]:
    """Return the complete mutable verification surface an external verifier must seal."""
    return {
        "contract_id": contract.get("contract_id"),
        "criteria_sha256": (contract.get("criteria_freeze") or {}).get("criteria_sha256"),
        "test_author_receipt": contract.get("test_author_receipt"),
        "isolation": contract.get("isolation"),
        "gates": contract.get("gates"),
        "decision_evidence": contract.get("decision_evidence"),
        "verifier": contract.get("verifier"),
        "verdict": contract.get("verdict"),
    }


def evaluate_pilot_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
    initial = evidence.get("initial_independent_review") or {}
    later = evidence.get("later_independent_review") or {}
    delivery = initial.get("delivery_state") or {}
    required = set(initial.get("required_surfaces") or [])
    observed = set(initial.get("surfaces_with_real_evidence") or [])
    baseline = later.get("baseline_cc_lifecycle") or {}
    candidate = later.get("candidate_cc_lifecycle") or {}
    held_out = evidence.get("held_out_board_event_regression") or {}
    lineage = evidence.get("held_out_intent_lineage_regression") or {}
    convergence = evidence.get("held_out_legacy_convergence_regression") or {}
    blockers: list[dict[str, str]] = []
    if initial.get("task_reasoning") != initial.get("receipt_reasoning"):
        blockers.append({"id": "stale-route-receipt", "classification": "routing-blocker"})
    if required - observed:
        blockers.append({"id": "missing-real-per-surface-evidence", "classification": "promotion-blocker"})
    if initial.get("cross_surface_enforcement") == "declarative-only":
        blockers.append({"id": "declarative-only-cross-surface-enforcement", "classification": "promotion-blocker"})
    if not all(delivery.get(key) for key in ("root_staged", "hermes_staged", "superseded_worktree_removed")):
        blockers.append({"id": "unreconciled-delivery-worktree-state", "classification": "delivery-blocker"})
    lifecycle_failed = candidate.get("failed", 0) > 0 or candidate.get("errors", 0) > 0
    if lifecycle_failed and baseline == candidate:
        blockers.append({"id": "native-cc-lifecycle-suite-6-fail-1-error", "classification": "pre-existing-native-lifecycle-blocker"})
    review_blocked = held_out.get("review_blocked_card") or {}
    if (
        review_blocked.get("status") == "review-blocked"
        and review_blocked.get("promotion_allowed") is False
        and not review_blocked.get("proactively_surfaced_by_event")
    ):
        blockers.append({"id": "review-blocked-status-not-proactively-surfaced", "classification": "status-visibility-blocker"})
    phantom = held_out.get("phantom_assignee_card") or {}
    if (
        phantom.get("status") == "ready"
        and phantom.get("assignee_exists") is False
        and not phantom.get("reconciliation_or_escalation_event")
    ):
        blockers.append({"id": "phantom-assignee-not-reconciled-or-escalated", "classification": "dispatch-authority-blocker"})
    evolving = lineage.get("evolving_card") or {}
    if not evolving.get("authoritative_lineage_preserved"):
        blockers.append({"id": "evolving-multi-turn-lineage-lost", "classification": "intent-lineage-blocker"})
    if evolving.get("generated_summary_overwrote_lineage"):
        blockers.append({"id": "summary-overwrites-authoritative-lineage", "classification": "summary-authority-blocker"})
    if not evolving.get("research_first_sequence_preserved") or not evolving.get("cross_host_resume_preserved"):
        blockers.append({"id": "research-first-cross-host-resume-omitted", "classification": "workflow-resume-blocker"})
    status = lineage.get("proactive_status") or {}
    if not status.get("material_omission_proactively_surfaced"):
        blockers.append({"id": "material-status-required-user-reminder", "classification": "status-visibility-blocker"})
    if status.get("accepted_summarizer_intake_omitted") and status.get("reminders_required", 0) >= 2:
        blockers.append({"id": "summarizer-intake-required-second-reminder", "classification": "intent-intake-blocker"})
    legacy = convergence.get("legacy_done") or {}
    if legacy.get("status") == "done" and legacy.get("evidence_classification") not in {
        "verified", "provisionally-valid", "superseded", "failed"
    }:
        blockers.append({"id": "legacy-done-status-treated-as-evidence", "classification": "legacy-evidence-blocker"})
    outcome = convergence.get("ultimate_agent_outcome") or {}
    if outcome.get("convergence_claimed") and not outcome.get("cross_host_evidence_revalidated"):
        blockers.append({"id": "ultimate-agent-convergence-claim-unrevalidated", "classification": "architecture-evidence-blocker"})
    prime = convergence.get("prime_agent") or {}
    if prime.get("evaluation_requested") and (
        set(prime.get("required_evidence_lanes") or []) - set(prime.get("observed_evidence_lanes") or [])
        or prime.get("self_approved_refinement")
        or prime.get("unsandboxed_execution")
        or not prime.get("windows_quality_proven")
    ):
        blockers.append({"id": "prime-boundaries-not-evidence-bound", "classification": "optional-surface-evidence-blocker"})
    fleet = convergence.get("fleet_omission") or {}
    if not fleet.get("proactively_surfaced") and fleet.get("reminders_required", 0) >= 3:
        blockers.append({"id": "fleet-omission-required-third-reminder", "classification": "fleet-status-blocker"})
    return {
        "blockers": blockers,
        "non_regressions": ["routing-specific-receipt-invalidation-fix"]
        if later.get("routing_specific_checks_passed") and later.get("receipt_invalidation_fix_passed")
        else [],
        "live_route_changed": bool(later.get("live_route_changed")),
    }


def validate_contract(
    contract: dict[str, Any],
    *,
    trusted_freeze_receipt: str | None = None,
    trusted_test_author_receipt: str | None = None,
    trusted_verification_receipt: str | None = None,
) -> list[str]:
    errors: list[str] = []
    if contract.get("schema_version") != 1:
        errors.append("schema_version must be 1")

    roles = contract.get("roles") or {}
    missing_roles = sorted(REQUIRED_ROLES - set(roles))
    if missing_roles:
        errors.append("missing roles: " + ", ".join(missing_roles))
    principals = [record.get("principal_id") for record in roles.values() if isinstance(record, dict)]
    contexts = [record.get("context_id") for record in roles.values() if isinstance(record, dict)]
    if len(principals) != len(set(principals)):
        errors.append("role principal_id values must be distinct")
    if len(contexts) != len(set(contexts)):
        errors.append("role context_id values must be distinct")

    freeze = contract.get("criteria_freeze") or {}
    criteria = freeze.get("criteria") or []
    criterion_ids = [item.get("id") for item in criteria]
    if len(criterion_ids) != len(set(criterion_ids)):
        errors.append("acceptance criterion ids must be unique")
    missing_categories = sorted(REQUIRED_CRITERIA - {item.get("category") for item in criteria})
    if missing_categories:
        errors.append("missing frozen criterion categories: " + ", ".join(missing_categories))
    source_ref = (contract.get("source_intent") or {}).get("reference")
    for item in criteria:
        if not item.get("source_reference") or item.get("source_reference") != source_ref:
            errors.append(f"{item.get('id', 'criterion')} is not sourced directly from source_intent.reference")
    pilot_manifest = freeze.get("pilot_manifest") or {}
    decision_scopes = freeze.get("decision_scopes") or []
    expected_hash = canonical_sha256({
        "criteria": criteria,
        "pilot_manifest": pilot_manifest,
        "decision_scopes": decision_scopes,
    })
    if freeze.get("criteria_sha256") != expected_hash:
        errors.append("criteria_sha256 does not match canonical frozen criteria")
    frozen_at = parse_time(freeze.get("frozen_at"), "criteria_freeze.frozen_at", errors)
    started_at = parse_time(freeze.get("implementation_started_at"), "criteria_freeze.implementation_started_at", errors)
    if frozen_at and started_at and frozen_at >= started_at:
        errors.append("criteria must be frozen before implementation starts")
    receipt_path = REPO / str(freeze.get("freeze_receipt_path") or "")
    receipt_digest = str(freeze.get("freeze_receipt") or "")
    receipt_doc: dict[str, Any] | None = None
    if (
        not isinstance(trusted_freeze_receipt, str)
        or not trusted_freeze_receipt.startswith("sha256:")
        or len(trusted_freeze_receipt) != 71
    ):
        errors.append("verifier-supplied trusted freeze receipt digest is required")
    original_hash: str | None = None
    if not receipt_path.is_file():
        errors.append("criteria freeze receipt_path does not exist")
    elif not receipt_digest.startswith("sha256:"):
        errors.append("criteria freeze receipt requires a sha256 digest")
    else:
        actual_receipt_digest = hashlib.sha256(receipt_path.read_bytes()).hexdigest()
        if trusted_freeze_receipt != f"sha256:{actual_receipt_digest}":
            errors.append("criteria freeze receipt does not match verifier-supplied trust root")
        if receipt_digest.removeprefix("sha256:") != actual_receipt_digest:
            errors.append("criteria freeze receipt hash mismatch")
        else:
            try:
                receipt_doc = json.loads(receipt_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                errors.append("criteria freeze receipt is not JSON")
            else:
                original_hash = receipt_doc.get("original_criteria_sha256")
                if (
                    receipt_doc.get("schema_version") != 1
                    or receipt_doc.get("receipt_type") != "grounded-verification-criteria-freeze"
                    or receipt_doc.get("contract_id") != contract.get("contract_id")
                    or receipt_doc.get("source_intent_reference") != source_ref
                    or receipt_doc.get("frozen_at") != freeze.get("frozen_at")
                    or not isinstance(original_hash, str)
                ):
                    errors.append("criteria freeze receipt has wrong type or contract binding")
                    original_hash = None
    prior_hash = original_hash
    for index, event in enumerate(freeze.get("decision_events") or []):
        decided = parse_time(event.get("decided_at"), f"decision_events[{index}].decided_at", errors)
        if decided and frozen_at and decided <= frozen_at:
            errors.append(f"decision event {event.get('id')} must occur after freeze")
        if event.get("decided_by") != (roles.get("intent_owner") or {}).get("principal_id"):
            errors.append(f"decision event {event.get('id')} must be approved by intent_owner")
        if event.get("before_sha256") != prior_hash:
            errors.append(f"decision event {event.get('id')} does not continue the criteria hash chain")
        if event.get("before_sha256") == event.get("after_sha256"):
            errors.append(f"decision event {event.get('id')} must record a real change")
        prior_hash = event.get("after_sha256")
    if prior_hash is not None and prior_hash != expected_hash:
        errors.append("current criteria are not connected to the immutable freeze receipt by decision events")
    if original_hash is not None and receipt_doc is not None:
        if (
            receipt_doc.get("decision_chain_event_ids")
            != [event.get("id") for event in freeze.get("decision_events") or []]
            or receipt_doc.get("final_criteria_sha256") != expected_hash
        ):
            errors.append("criteria freeze receipt does not bind the complete amendment chain")

    test_author_binding = contract.get("test_author_receipt") or {}
    test_author_receipt_path = REPO / str(test_author_binding.get("receipt_path") or "")
    test_author_receipt_digest = str(test_author_binding.get("receipt") or "")
    test_author_artifact_path = REPO / str(test_author_binding.get("artifact_path") or "")
    test_author_artifact_digest = str(test_author_binding.get("artifact_sha256") or "")
    test_author_receipt_doc: dict[str, Any] | None = None
    if (
        not isinstance(trusted_test_author_receipt, str)
        or not trusted_test_author_receipt.startswith("sha256:")
        or len(trusted_test_author_receipt) != 71
    ):
        errors.append("verifier-supplied trusted test-author receipt digest is required")
    if not test_author_receipt_path.is_file():
        errors.append("test-author receipt_path does not exist")
    elif not test_author_receipt_digest.startswith("sha256:"):
        errors.append("test-author receipt requires a sha256 digest")
    else:
        actual = hashlib.sha256(test_author_receipt_path.read_bytes()).hexdigest()
        if trusted_test_author_receipt != f"sha256:{actual}":
            errors.append("test-author receipt does not match verifier-supplied trust root")
        if test_author_receipt_digest.removeprefix("sha256:") != actual:
            errors.append("test-author receipt hash mismatch")
        else:
            try:
                test_author_receipt_doc = json.loads(test_author_receipt_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                errors.append("test-author receipt is not JSON")
    artifact_doc: dict[str, Any] | None = None
    if not test_author_artifact_path.is_file():
        errors.append("test-author artifact_path does not exist")
    elif len(test_author_artifact_digest) != 64:
        errors.append("test-author artifact requires a sha256 digest")
    else:
        actual = hashlib.sha256(test_author_artifact_path.read_bytes()).hexdigest()
        if test_author_artifact_digest != actual:
            errors.append("test-author artifact hash mismatch")
        else:
            try:
                artifact_doc = json.loads(test_author_artifact_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                errors.append("test-author artifact is not JSON")
    test_author_role = roles.get("test_author") or {}
    if test_author_receipt_doc is not None:
        expected_receipt_fields = {
            "schema_version": 1,
            "receipt_type": "grounded-verification-test-author-input-output",
            "contract_id": contract.get("contract_id"),
            "test_author_principal_id": test_author_role.get("principal_id"),
            "test_author_context_id": test_author_role.get("context_id"),
            "frozen_at": freeze.get("frozen_at"),
            "trusted_original_criteria_sha256": original_hash,
            "final_criteria_sha256": expected_hash,
            "artifact_path": test_author_binding.get("artifact_path"),
            "artifact_sha256": test_author_artifact_digest,
            "input_scope": "frozen_intent_spec",
            "output_type": "independent-test-author-checks",
            "implementation_access": False,
        }
        if any(test_author_receipt_doc.get(field) != value for field, value in expected_receipt_fields.items()):
            errors.append("test-author receipt has wrong type or frozen-input/output binding")
    if artifact_doc is not None:
        frozen_input = artifact_doc.get("frozen_input") or {}
        if (
            artifact_doc.get("schema_version") != 1
            or artifact_doc.get("artifact_type") != "independent-test-author-checks"
            or artifact_doc.get("contract_id") != contract.get("contract_id")
            or artifact_doc.get("test_author_principal_id") != test_author_role.get("principal_id")
            or artifact_doc.get("test_author_context_id") != test_author_role.get("context_id")
        ):
            errors.append("test-author artifact has wrong type or contract binding")
        if frozen_input.get("frozen_at") != freeze.get("frozen_at"):
            errors.append("test-author artifact freeze timestamp mismatch")
        if (
            frozen_input.get("source_intent_reference") != source_ref
            or frozen_input.get("trusted_original_criteria_sha256") != original_hash
            or frozen_input.get("final_criteria_sha256") != expected_hash
        ):
            errors.append("test-author artifact does not match trusted frozen criteria chain")
        if frozen_input.get("criterion_ids") != criterion_ids:
            errors.append("test-author artifact does not cover the complete frozen criterion set")

    test_boundary = role_boundary(contract, "test_author")
    if not test_boundary:
        errors.append("missing test_author isolation boundary")
    else:
        if set(test_boundary.get("readable_scopes") or []) != {"frozen_intent_spec"}:
            errors.append("test_author readable scope must be exactly frozen_intent_spec")
        if "implementation" not in set(test_boundary.get("denied_scopes") or []):
            errors.append("test_author must be denied implementation access")

    implementer_boundary = role_boundary(contract, "implementer")
    if not implementer_boundary:
        errors.append("missing implementer isolation boundary")
    else:
        missing_denials = sorted(IMPLEMENTER_DENIALS - set(implementer_boundary.get("denied_scopes") or []))
        if missing_denials:
            errors.append("implementer missing denied scopes: " + ", ".join(missing_denials))

    for boundary in contract.get("isolation") or []:
        readable = set(boundary.get("readable_scopes") or [])
        denied = set(boundary.get("denied_scopes") or [])
        overlap = sorted(readable & denied)
        if overlap:
            errors.append(f"{boundary.get('subject_role')} scopes are both readable and denied: {', '.join(overlap)}")
        receipt = str(boundary.get("receipt") or "")
        if not receipt.startswith("sha256:") or len(receipt) != 71:
            errors.append(f"{boundary.get('subject_role')} requires a sha256 isolation receipt")
        receipt_path = REPO / str(boundary.get("receipt_path") or "")
        if not receipt_path.is_file():
            errors.append(f"{boundary.get('subject_role')} isolation receipt_path does not exist")
        elif receipt.startswith("sha256:"):
            actual = hashlib.sha256(receipt_path.read_bytes()).hexdigest()
            if receipt.removeprefix("sha256:") != actual:
                errors.append(f"{boundary.get('subject_role')} isolation receipt hash mismatch")
            else:
                try:
                    receipt_doc = json.loads(receipt_path.read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    errors.append(f"{boundary.get('subject_role')} isolation receipt is not JSON")
                else:
                    role_receipt = (receipt_doc.get("boundaries") or {}).get(boundary.get("subject_role"))
                    if (
                        receipt_doc.get("schema_version") != 1
                        or receipt_doc.get("receipt_type") != "grounded-verification-isolation"
                        or receipt_doc.get("contract_id") != contract.get("contract_id")
                        or not role_receipt
                    ):
                        errors.append(f"{boundary.get('subject_role')} isolation receipt has wrong type or role")
                    elif any(
                        role_receipt.get(field) != boundary.get(field)
                        for field in ("readable_scopes", "denied_scopes", "enforcement")
                    ):
                        errors.append(f"{boundary.get('subject_role')} isolation receipt does not match declared boundary")

    gates = contract.get("gates") or []
    gates_by_id = {gate.get("id"): gate for gate in gates}
    if len(gates_by_id) != len(gates):
        errors.append("gate ids must be unique")
    for gate in gates:
        gate_id = gate.get("id", "gate")
        if gate.get("trusted"):
            control = gate.get("negative_control") or {}
            if not control.get("passed") or control.get("observed") not in {"fail", "reject"}:
                errors.append(f"trusted gate {gate_id} lacks a passing negative control")
        if gate.get("open_ended") and gate.get("oracle") != "world-state":
            errors.append(f"open-ended gate {gate_id} must use a world-state oracle")
        if not gate.get("evidence_path"):
            errors.append(f"gate {gate_id} lacks an evidence path")
        elif not (REPO / str(gate.get("evidence_path"))).exists():
            errors.append(f"gate {gate_id} evidence path does not exist")
        if str(gate.get("command_or_probe", "")).strip().lower() in TRIVIAL_PROBES:
            errors.append(f"gate {gate_id} uses a trivial command or probe")

    for path in contract.get("material_code_paths") or []:
        path_name = path.get("path", "path")
        property_gate = gates_by_id.get(path.get("property_or_metamorphic_gate"))
        if not property_gate or not property_gate.get("trusted") or property_gate.get("check_kind") not in {"property", "metamorphic"}:
            errors.append(f"material path {path_name} lacks a property or metamorphic gate")
        if path.get("teeth_supported"):
            teeth_gate = gates_by_id.get(path.get("teeth_gate"))
            if not teeth_gate or not teeth_gate.get("trusted") or teeth_gate.get("check_kind") not in {"mutation", "equivalent-teeth"}:
                errors.append(f"material path {path_name} lacks mutation or equivalent teeth evidence")
        elif not path.get("exemption"):
            errors.append(f"material path {path_name} requires a teeth-testing exemption")

    scopes_by_id = {scope.get("id"): scope for scope in decision_scopes}
    if len(scopes_by_id) != len(decision_scopes):
        errors.append("decision scope ids must be unique")
    mapped_criteria = [criterion_id for scope in decision_scopes for criterion_id in scope.get("criterion_ids") or []]
    unknown_criteria = sorted(set(mapped_criteria) - set(criterion_ids))
    if unknown_criteria:
        errors.append("decision scopes reference unknown criteria: " + ", ".join(unknown_criteria))
    duplicate_criteria = sorted({criterion_id for criterion_id in mapped_criteria if mapped_criteria.count(criterion_id) > 1})
    if duplicate_criteria:
        errors.append("criteria map to multiple decision scopes: " + ", ".join(duplicate_criteria))
    unmapped_criteria = sorted(set(criterion_ids) - set(mapped_criteria))
    if unmapped_criteria:
        errors.append("material criteria lack a decision scope: " + ", ".join(unmapped_criteria))

    evidence_records = contract.get("decision_evidence") or []
    evidence_assertions: list[dict[str, Any]] = []
    evidence_by_scope = {record.get("scope_id"): record for record in evidence_records}
    if len(evidence_by_scope) != len(evidence_records):
        errors.append("decision evidence scope ids must be unique")
    unknown_evidence_scopes = sorted(set(evidence_by_scope) - set(scopes_by_id))
    if unknown_evidence_scopes:
        errors.append("decision evidence references unknown scopes: " + ", ".join(unknown_evidence_scopes))
    for scope_id, scope in scopes_by_id.items():
        record = evidence_by_scope.get(scope_id) or {}
        lanes = record.get("lanes") or []
        lanes_by_id = {lane.get("lane_id"): lane for lane in lanes}
        if len(lanes_by_id) != len(lanes):
            errors.append(f"decision scope {scope_id} has duplicate evidence lanes")
        missing_lanes = sorted(set(scope.get("required_evidence_lanes") or []) - set(lanes_by_id))
        if missing_lanes:
            errors.append(f"decision scope {scope_id} lacks required evidence lanes: " + ", ".join(missing_lanes))
        for lane_id, lane in lanes_by_id.items():
            evidence_path = REPO / str(lane.get("evidence_path") or "")
            if not evidence_path.is_file():
                errors.append(f"decision evidence {scope_id}/{lane_id} path does not exist")
                continue
            actual = hashlib.sha256(evidence_path.read_bytes()).hexdigest()
            if lane.get("sha256") != actual:
                errors.append(f"decision evidence {scope_id}/{lane_id} hash mismatch")
                continue
            try:
                evidence_doc = json.loads(evidence_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                errors.append(f"decision evidence {scope_id}/{lane_id} is not JSON")
                continue
            declared_lanes = set(evidence_doc.get("evidence_lanes") or [])
            if (
                evidence_doc.get("schema_version") != 1
                or evidence_doc.get("artifact_type") != "grounded-verification-decision-evidence"
                or evidence_doc.get("contract_id") != contract.get("contract_id")
                or evidence_doc.get("scope_id") != scope_id
                or lane_id not in declared_lanes
            ):
                errors.append(f"decision evidence {scope_id}/{lane_id} has wrong type or scope binding")
            evidence_result = evidence_doc.get("result")
            evidence_basis = (evidence_doc.get("basis") or {}).get(lane_id)
            if evidence_result not in {"pass", "fail", "inconclusive"} or not isinstance(evidence_basis, str) or not evidence_basis.strip():
                errors.append(f"decision evidence {scope_id}/{lane_id} lacks an independently receiptable result or basis")
            if lane.get("result") != evidence_result:
                errors.append(f"decision evidence {scope_id}/{lane_id} result disagrees with its artifact")
            evidence_assertions.append({
                "scope_id": scope_id,
                "lane_id": lane_id,
                "evidence_path": lane.get("evidence_path"),
                "sha256": actual,
                "result": evidence_result,
                "basis_sha256": canonical_sha256(evidence_basis),
            })
            if contract.get("state") == "verified" and evidence_result != "pass":
                errors.append(f"verified decision scope {scope_id} requires passing evidence lane {lane_id}")

    verifier = contract.get("verifier") or {}
    verdict = contract.get("verdict") or {}
    verifier_role = roles.get("verdict_owner") or {}
    if verifier.get("principal_id") != verifier_role.get("principal_id"):
        errors.append("verifier principal must own the verdict role")
    if verifier.get("context_id") != verifier_role.get("context_id"):
        errors.append("verifier context must match the verdict role context")
    if verifier.get("shared_visible_proxy") and verifier.get("isolation_strength") != "context-only":
        errors.append("shared visible proxy can only be labeled context-only isolation")
    required_reexecution = {
        gate.get("id") for gate in gates
        if gate.get("trusted") and gate.get("check_kind") in DETERMINISTIC_KINDS
    }
    missing_reexecution = sorted(required_reexecution - set(verifier.get("reexecuted_gate_ids") or []))
    if missing_reexecution:
        errors.append("verifier did not re-execute deterministic gates: " + ", ".join(missing_reexecution))
    if not verifier.get("falsification_probes"):
        errors.append("verifier must generate independent falsification probes")
    if verdict.get("principal_id") != verifier_role.get("principal_id"):
        errors.append("verdict must be issued by verdict_owner")
    unknown_basis = sorted(set(verdict.get("basis_gate_ids") or []) - set(gates_by_id))
    if unknown_basis:
        errors.append("verdict references unknown gates: " + ", ".join(unknown_basis))
    for gate_id in verdict.get("basis_gate_ids") or []:
        gate = gates_by_id.get(gate_id) or {}
        if not gate.get("trusted") or gate.get("result") != "pass":
            errors.append(f"verdict basis gate {gate_id} must be trusted and passing")
    claimed_scope_ids = set(verdict.get("claimed_scope_ids") or [])
    unknown_claimed_scopes = sorted(claimed_scope_ids - set(scopes_by_id))
    if unknown_claimed_scopes:
        errors.append("verdict claims unknown decision scopes: " + ", ".join(unknown_claimed_scopes))
    if contract.get("state") == "verified":
        missing_claimed_scopes = sorted(set(scopes_by_id) - claimed_scope_ids)
        if missing_claimed_scopes:
            errors.append("verified verdict omits decision scopes: " + ", ".join(missing_claimed_scopes))
    basis_gate_ids = set(verdict.get("basis_gate_ids") or [])
    for scope_id in sorted(claimed_scope_ids & set(scopes_by_id)):
        missing_scope_gates = sorted(set(scopes_by_id[scope_id].get("required_gate_ids") or []) - basis_gate_ids)
        if missing_scope_gates:
            errors.append(f"claimed decision scope {scope_id} lacks required verdict gates: " + ", ".join(missing_scope_gates))

    verification_binding = contract.get("verification_receipt") or {}
    verification_receipt_path = REPO / str(verification_binding.get("receipt_path") or "")
    verification_receipt_digest = str(verification_binding.get("receipt") or "")
    if (
        not isinstance(trusted_verification_receipt, str)
        or not trusted_verification_receipt.startswith("sha256:")
        or len(trusted_verification_receipt) != 71
    ):
        errors.append("verifier-supplied trusted verification receipt digest is required")
    if not verification_receipt_path.is_file():
        errors.append("verification receipt_path does not exist")
    elif not verification_receipt_digest.startswith("sha256:"):
        errors.append("verification receipt requires a sha256 digest")
    else:
        actual_receipt_digest = hashlib.sha256(verification_receipt_path.read_bytes()).hexdigest()
        if trusted_verification_receipt != f"sha256:{actual_receipt_digest}":
            errors.append("verification receipt does not match verifier-supplied trust root")
        if verification_receipt_digest.removeprefix("sha256:") != actual_receipt_digest:
            errors.append("verification receipt hash mismatch")
        else:
            try:
                verification_receipt_doc = json.loads(verification_receipt_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                errors.append("verification receipt is not JSON")
            else:
                gate_assertions = []
                for gate in gates:
                    gate_path = REPO / str(gate.get("evidence_path") or "")
                    gate_assertions.append({
                        "gate_id": gate.get("id"),
                        "evidence_path": gate.get("evidence_path"),
                        "evidence_sha256": hashlib.sha256(gate_path.read_bytes()).hexdigest() if gate_path.is_file() else None,
                        "result": gate.get("result"),
                        "trusted": gate.get("trusted"),
                        "negative_control": gate.get("negative_control"),
                    })
                expected_receipt = {
                    "schema_version": 1,
                    "receipt_type": "grounded-verification-verdict-manifest",
                    "contract_id": contract.get("contract_id"),
                    "verifier_principal_id": verifier.get("principal_id"),
                    "verifier_context_id": verifier.get("context_id"),
                    "manifest_sha256": canonical_sha256(verification_manifest(contract)),
                    "evidence_assertions": sorted(evidence_assertions, key=lambda item: (item["scope_id"], item["lane_id"])),
                    "gate_assertions": sorted(gate_assertions, key=lambda item: str(item["gate_id"])),
                }
                if verification_receipt_doc != expected_receipt:
                    errors.append("verification receipt does not match the complete evidence and verdict manifest")

    pilot = contract.get("pilot") or {}
    blockers = pilot.get("known_blockers") or []
    expected_blockers = set(pilot_manifest.get("expected_blocker_ids") or [])
    expected_non_regressions = set(pilot_manifest.get("expected_non_regression_ids") or [])
    observed_blockers = {item.get("id") for item in blockers if item.get("expected") == "blocker"}
    observed_non_regressions = {item.get("id") for item in blockers if item.get("expected") == "non-regression"}
    if observed_blockers != expected_blockers:
        errors.append("pilot blocker set does not match the frozen manifest")
    if observed_non_regressions != expected_non_regressions:
        errors.append("pilot non-regression set does not match the frozen manifest")
    evidence_path = pilot.get("evidence_path")
    if not evidence_path or not (REPO / str(evidence_path)).is_file():
        errors.append("pilot evidence_path must reference a local evidence file")
    else:
        evidence = json.loads((REPO / str(evidence_path)).read_text(encoding="utf-8"))
        derived = evaluate_pilot_evidence(evidence)
        derived_map = {item["id"]: item["classification"] for item in derived["blockers"]}
        reported_map = {item.get("id"): item.get("classification") for item in blockers if item.get("expected") == "blocker"}
        if derived_map != reported_map:
            errors.append("pilot blocker detection or attribution does not match deterministic evidence")
        if set(derived["non_regressions"]) != observed_non_regressions:
            errors.append("pilot non-regression detection does not match deterministic evidence")
    false_negatives = sum(1 for item in blockers if item.get("expected") == "blocker" and not item.get("detected"))
    if pilot.get("false_negatives") != false_negatives:
        errors.append("pilot false_negatives does not match known blocker observations")
    if contract.get("state") == "verified" and (
        verdict.get("decision") != "pass"
        or any(gate.get("trusted") and gate.get("result") != "pass" for gate in gates)
        or false_negatives
    ):
        errors.append("verified state requires passing verdict, trusted gates, and zero known false negatives")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("contract", nargs="?", type=Path)
    parser.add_argument("--pilot-evidence", type=Path)
    parser.add_argument(
        "--trusted-freeze-receipt",
        help="Verifier-controlled sha256 digest of the immutable criteria freeze receipt",
    )
    parser.add_argument(
        "--trusted-test-author-receipt",
        help="Verifier-controlled sha256 digest of the immutable test-author input/output receipt",
    )
    parser.add_argument(
        "--trusted-verification-receipt",
        help="Verifier-controlled sha256 digest sealing decision evidence, isolation, gates, verifier, and verdict",
    )
    args = parser.parse_args(argv)
    if args.pilot_evidence:
        evidence = json.loads(args.pilot_evidence.read_text(encoding="utf-8"))
        print(json.dumps(evaluate_pilot_evidence(evidence), indent=2))
        return 0
    if not args.contract:
        parser.error("contract is required unless --pilot-evidence is used")
    try:
        contract = json.loads(args.contract.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    errors = [
        *validate_schema(contract),
        *validate_contract(
            contract,
            trusted_freeze_receipt=args.trusted_freeze_receipt,
            trusted_test_author_receipt=args.trusted_test_author_receipt,
            trusted_verification_receipt=args.trusted_verification_receipt,
        ),
    ]
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print(json.dumps({"contract": str(args.contract.resolve()), "decision": contract["verdict"]["decision"], "valid": True}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
