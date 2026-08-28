from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]


def load_adapter():
    path = REPO / "tools" / "route_adapter.py"
    spec = importlib.util.spec_from_file_location("route_adapter", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


def _digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def receipt(surface: str = "hermes-delegate") -> dict:
    runtime = {
        "host": "hermes",
        "host_version": "0.20.5",
        "transport": surface,
        "harness_version": "route-contract-v1",
    }
    route = {
        "id": "luna-high",
        "provider": "openai-codex",
        "model": "gpt-5.6-luna",
        "reasoning_effort": "high",
        "runtime": runtime,
        "runtime_sha256": _digest(runtime),
    }
    constraints = {
        "target_surface": surface,
        "task_class": "mechanical-bounded",
        "objective": "user-outcome",
        "failure_cost": "medium",
        "verifier_plan": {"kind": "none"},
    }
    policy_sha = "a" * 64
    requirement_sha = _digest(constraints)
    decision_id = _digest(
        {
            "policy_sha256": policy_sha,
            "requirement_sha256": requirement_sha,
            "outcome": "selected",
            "route": route,
        }
    )
    return {
        "schema_version": 2,
        "decision_id": decision_id,
        "outcome": "selected",
        "pin_status": "new",
        "policy_version": "candidate-2026-08-23",
        "policy_sha256": policy_sha,
        "requirement_sha256": requirement_sha,
        "target_surface": surface,
        "task_class": "mechanical-bounded",
        "objective": "user-outcome",
        "failure_cost": "medium",
        "attempt_number": 1,
        "constraints_applied": constraints,
        "route": route,
        "metrics": {"expected_total_cost_usd": 0.10},
        "evidence_receipt": {"locator": "catalog.json", "sha256": policy_sha},
        "excluded": {},
        "verifier_plan": {"kind": "none"},
    }



def test_receipt_hash_bindings_reject_tampered_constraints_and_route():
    adapter = load_adapter()
    altered_constraints = receipt()
    altered_constraints["constraints_applied"]["task_class"] = "different"
    with pytest.raises(adapter.RouteAdapterError, match="requirement_sha256"):
        adapter.native_mapping(altered_constraints, "hermes-delegate")

    altered_route = receipt()
    altered_route["route"]["reasoning_effort"] = "low"
    with pytest.raises(adapter.RouteAdapterError, match="decision_id"):
        adapter.native_mapping(altered_route, "hermes-delegate")


def test_receipt_rejects_tampered_catalog_identity():
    adapter = load_adapter()
    altered = receipt()
    altered["evidence_receipt"]["locator"] = "other-catalog.json"
    altered["evidence_receipt"]["sha256"] = "9" * 64
    with pytest.raises(adapter.RouteAdapterError, match="must match policy_sha256"):
        adapter.native_mapping(altered, "hermes-delegate")


@pytest.mark.parametrize(
    "mutate",
    [
        lambda value: value.update(pin_status="denied"),
        lambda value: value.pop("metrics"),
        lambda value: value.update(unexpected_field=True),
    ],
    ids=["invalid-pin-status", "missing-required-metrics", "unexpected-field"],
)
def test_adapter_rejects_receipts_outside_route_decision_schema(mutate):
    adapter = load_adapter()
    altered = receipt()
    mutate(altered)
    with pytest.raises(adapter.RouteAdapterError, match="schema"):
        adapter.native_mapping(altered, "hermes-delegate")


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("provider", "not-openai", "provider must be openai-codex"),
        ("model", "claude-x", "model must be a GPT"),
        ("reasoning_effort", "turbo", "reasoning_effort is unsupported"),
    ],
)
def test_adapter_enforces_gpt_openai_codex_boundary(field, value, message):
    adapter = load_adapter()
    altered = receipt()
    altered["route"][field] = value
    altered["decision_id"] = _digest(
        {
            "policy_sha256": altered["policy_sha256"],
            "requirement_sha256": altered["requirement_sha256"],
            "outcome": "selected",
            "route": altered["route"],
        }
    )
    with pytest.raises(adapter.RouteAdapterError, match=message):
        adapter.native_mapping(altered, "hermes-delegate")


def test_receipt_runtime_transport_must_match_surface():
    adapter = load_adapter()
    altered = receipt("hermes-task-thread")
    altered["route"]["runtime"]["transport"] = "hermes-delegate"
    altered["route"]["runtime_sha256"] = _digest(altered["route"]["runtime"])
    altered["decision_id"] = _digest(
        {
            "policy_sha256": altered["policy_sha256"],
            "requirement_sha256": altered["requirement_sha256"],
            "outcome": "selected",
            "route": altered["route"],
        }
    )
    with pytest.raises(adapter.RouteAdapterError, match="transport"):
        adapter.native_mapping(altered, "hermes-task-thread")


def test_receipt_target_must_match_surface():
    adapter = load_adapter()
    with pytest.raises(adapter.RouteAdapterError, match="target_surface"):
        adapter.native_mapping(receipt("hermes-delegate"), "hermes-task-thread")


def test_all_required_surfaces_have_truthful_smallest_paths(tmp_path):
    adapter = load_adapter()
    expected = {
        "hermes-delegate": "staged-source-integration",
        "hermes-task-thread": "native-cli-external-pin",
    }
    assert set(adapter.SURFACE_CONTRACTS) == set(expected)
    for surface, enforcement in expected.items():
        mapping = adapter.native_mapping(
            receipt(surface),
            surface,
            prompt="return PASS",
            cwd=str(tmp_path),
        )
        assert mapping["enforcement"] == enforcement
        assert mapping["receipt_pinned_before_launch"] is True


def test_task_thread_uses_current_supported_per_run_cli_controls(tmp_path):
    adapter = load_adapter()
    argv = adapter.native_mapping(
        receipt("hermes-task-thread"),
        "hermes-task-thread",
        prompt="return PASS",
        cwd=str(tmp_path),
    )["argv"]
    assert argv[:2] == ["hermes", "chat"]
    assert ["--model", "gpt-5.6-luna"] == argv[argv.index("--model") : argv.index("--model") + 2]
    assert ["--provider", "openai-codex"] == argv[argv.index("--provider") : argv.index("--provider") + 2]
    assert ["--reasoning", "high"] == argv[argv.index("--reasoning") : argv.index("--reasoning") + 2]
    assert ["--source", "tool"] == argv[argv.index("--source") : argv.index("--source") + 2]
    assert "--query-file" in argv


def test_auxiliary_is_not_a_delegation_adapter_surface():
    adapter = load_adapter()
    with pytest.raises(adapter.RouteAdapterError, match="unsupported target surface"):
        adapter.native_mapping(receipt("hermes-auxiliary"), "hermes-auxiliary")


@pytest.mark.parametrize("field", ["suite_hash", "pareto_frontier", "fallback_candidates"])
def test_legacy_decision_fields_are_rejected(field):
    adapter = load_adapter()
    altered = receipt()
    altered[field] = [] if field != "suite_hash" else "f" * 64
    with pytest.raises(adapter.RouteAdapterError, match="legacy decision field"):
        adapter.native_mapping(altered, "hermes-delegate")


def test_legacy_objective_is_rejected():
    adapter = load_adapter()
    altered = receipt()
    altered["objective"] = "speed"
    altered["constraints_applied"]["objective"] = "speed"
    altered["requirement_sha256"] = _digest(altered["constraints_applied"])
    altered["decision_id"] = _digest(
        {
            "policy_sha256": altered["policy_sha256"],
            "requirement_sha256": altered["requirement_sha256"],
            "outcome": "selected",
            "route": altered["route"],
        }
    )
    with pytest.raises(adapter.RouteAdapterError, match="objective must be user-outcome"):
        adapter.native_mapping(altered, "hermes-delegate")


def test_prepare_pins_once_and_reuses_identical_receipt(tmp_path):
    adapter = load_adapter()
    state_path = tmp_path / "run.json"
    decision = receipt("hermes-task-thread")
    first = adapter.prepare(
        decision,
        "hermes-task-thread",
        state_path,
        run_id="run-123",
        prompt="return PASS",
        cwd=str(tmp_path),
    )
    second = adapter.prepare(
        decision,
        "hermes-task-thread",
        state_path,
        run_id="run-123",
        prompt="return PASS",
        cwd=str(tmp_path),
    )
    assert first["pin_status"] == "new"
    assert second["pin_status"] == "reused"
    persisted = json.loads(state_path.read_text(encoding="utf-8"))
    assert persisted["decision_receipt"] == decision
    assert persisted["run_id"] == "run-123"
    assert state_path.with_name("run.prompt.txt").read_text(encoding="utf-8") == "return PASS"
    assert not state_path.with_name(".run.json.pin.lock").exists()


def test_prepare_derives_stable_run_id_for_legacy_callers(tmp_path):
    adapter = load_adapter()
    state_path = tmp_path / "legacy.json"
    decision = receipt("hermes-delegate")
    first = adapter.prepare(decision, "hermes-delegate", state_path)
    second = adapter.prepare(decision, "hermes-delegate", state_path)
    assert first["run_id"] == state_path.resolve().as_posix()
    assert second["pin_status"] == "reused"


def test_tampered_pinned_prompt_is_rejected_on_resume(tmp_path):
    adapter = load_adapter()
    state_path = tmp_path / "run.json"
    decision = receipt("hermes-task-thread")
    adapter.prepare(
        decision,
        "hermes-task-thread",
        state_path,
        run_id="run-123",
        prompt="return PASS",
        cwd=str(tmp_path),
    )
    prompt_path = state_path.with_name("run.prompt.txt")
    prompt_path.write_text("altered", encoding="utf-8")
    with pytest.raises(adapter.RunPinConflict, match="prompt material"):
        adapter.prepare(
            decision,
            "hermes-task-thread",
            state_path,
            run_id="run-123",
            prompt="return PASS",
            cwd=str(tmp_path),
        )
    assert prompt_path.read_text(encoding="utf-8") == "altered"
    assert not state_path.with_name(".run.json.pin.lock").exists()


def test_existing_run_cannot_silently_change_route(tmp_path):
    adapter = load_adapter()
    state_path = tmp_path / "run.json"
    original = receipt("hermes-task-thread")
    adapter.prepare(
        original,
        "hermes-task-thread",
        state_path,
        run_id="run-123",
        prompt="return PASS",
        cwd=str(tmp_path),
    )
    moved = receipt("hermes-task-thread")
    moved["policy_sha256"] = "9" * 64
    moved["evidence_receipt"]["sha256"] = moved["policy_sha256"]
    moved["route"]["model"] = "gpt-5.6-sol"
    moved["decision_id"] = _digest(
        {
            "policy_sha256": moved["policy_sha256"],
            "requirement_sha256": moved["requirement_sha256"],
            "outcome": "selected",
            "route": moved["route"],
        }
    )
    with pytest.raises(adapter.RunPinConflict, match="already pinned"):
        adapter.prepare(
            moved,
            "hermes-task-thread",
            state_path,
            run_id="run-123",
            prompt="return PASS",
            cwd=str(tmp_path),
        )
    persisted = json.loads(state_path.read_text(encoding="utf-8"))
    assert persisted["decision_receipt"] == original
    assert not state_path.with_name(".run.json.pin.lock").exists()


def test_fail_closed_receipt_pins_blocked_run(tmp_path):
    adapter = load_adapter()
    decision = receipt("hermes-delegate")
    decision.update({"outcome": "fail_closed", "pin_status": "denied", "route": None})
    decision["evidence_receipt"] = None
    decision["decision_id"] = _digest(
        {
            "policy_sha256": decision["policy_sha256"],
            "requirement_sha256": decision["requirement_sha256"],
            "outcome": "fail_closed",
        }
    )
    state = adapter.prepare(
        decision,
        "hermes-delegate",
        tmp_path / "blocked.json",
        run_id="blocked-1",
    )
    assert state["status"] == "blocked"
    assert state["native_mapping"] is None
