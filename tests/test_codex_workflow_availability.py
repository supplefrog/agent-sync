"""Production-seam tests for on-demand Codex availability and receipt replay."""

from __future__ import annotations

import json
import subprocess
import sys
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills/dynamic-workflows/scripts"
sys.path.insert(0, str(SCRIPTS))
import codex_availability as native
import workflow_state as wf
sys.path.pop(0)


@pytest.fixture
def plan():
    path = ROOT / "skills/dynamic-workflows/assets/templates/workflow-v3.json"
    document = json.loads(path.read_bytes())
    first = document["tasks"][0]
    first["role"] = "worker"
    first["risk"] = "write"
    request = first["route_request"]
    request["requirements"].update(model="future-supported-model", reasoning_effort="future-effort",
                                   tools=["apply_patch", "exec_command"])
    request["verifier"].update(kind="deterministic", scope="artifact-effects")
    request["effects"] = "reversible"
    request["budget"].update(
        quotas={"codex-main": {"unit": "percentage-points", "remaining": 10, "reserve": 0}},
        unknown_cost_policy="explicit_preference", preference_order=[native.ROUTE_ID],
    )
    second = deepcopy(first)
    second.update(id="after", depends_on=[first["id"]], include_outputs=[first["id"]],
                  prompt="Verify the evidence: {{output:inspect}}")
    document["tasks"] = [first, second]
    return document


@pytest.fixture
def fake_native(monkeypatch):
    probes = []
    native_traces = {}
    monkeypatch.setitem(sys.modules, "codex_availability", native)
    monkeypatch.setattr(native, "native_cli", lambda: "fake-codex")
    monkeypatch.setattr(native, "cli", lambda exe, *args: subprocess.CompletedProcess(
        args, 0, "codex-cli 7.0\n" if args == ("--version",) else "Logged in using ChatGPT\n", "",
    ))
    monkeypatch.setattr(native, "profile_generation", lambda home: {"id": "fixture-profile"})

    def observe(exe, home, scope, scratch):
        probes.append(scope)
        key = str(len(probes))
        native_traces[key] = datetime.now(timezone.utc), 32_000
        return {"controller": key, "child": key}, native_traces[key]

    monkeypatch.setattr(native, "probe_worker", observe)
    monkeypatch.setattr(native, "native_observation", lambda home, identity, scope: native_traces[identity["child"]])
    return probes


def initialize(tmp_path, plan, surface="codex-workflow"):
    path = tmp_path / "plan.json"
    path.write_text(json.dumps(plan), encoding="utf-8")
    return wf.init_run(path, tmp_path / "runs", {}, target_surface=surface)


def complete(run, task, output):
    token = wf.claim_task(run, task)
    handle = f"native-fixture-{task}"
    wf.start_task(run, task, handle, token)
    file = run / "tasks" / task / "output.md"
    file.write_text(output, encoding="utf-8")
    wf.finish_task(run, task, "succeeded", str(file), "", "", True, handle, token)


def test_refresh_after_expiry_for_unbound_dependency_preserves_existing_receipt(tmp_path, plan, fake_native):
    run = initialize(tmp_path, plan)
    manifest = (run / "run_manifest.json").read_bytes()
    catalog = (run / "route_catalog_v3.json").read_bytes()
    context = {"profile": "fixture"}
    with pytest.raises(wf.PlanError, match="not dependency-ready"):
        wf.task_dispatch(run, "after", context)
    assert not fake_native

    first = wf.task_dispatch(run, "inspect", context)
    assert first["kind"] == "model"
    assert first["route"]["model"] == "future-supported-model"
    assert first["route"]["reasoning_effort"] == "future-effort"
    assert first["input"]["codex_availability"]["tools"] == ["apply_patch", "exec_command"]
    assert len(fake_native) == 1
    complete(run, "inspect", "upstream evidence")
    receipt = Path(first["route_receipt_path"]).read_bytes()
    cache = next((run.parent / ".codex-availability").glob("*.json"))
    stale = json.loads(cache.read_bytes())
    now = datetime.now(timezone.utc)
    stale["proof"].update(observed_at=(now - timedelta(days=2)).isoformat(),
                          valid_until=(now - timedelta(days=1)).isoformat())
    wf.atomic_json(cache, stale)

    second = wf.task_dispatch(run, "after", context)
    assert second["kind"] == "model"
    assert "upstream evidence" in second["input"]["prompt"]
    assert len(fake_native) == 2
    assert second["input"]["codex_availability"] != stale["proof"]
    assert wf.task_dispatch(run, "inspect", context) == first
    assert Path(first["route_receipt_path"]).read_bytes() == receipt
    recorded = json.loads(receipt)
    frozen_catalog = json.loads(Path(recorded["policy_locator"]).read_bytes())
    assert wf.receipt_digest(frozen_catalog) == recorded["policy_sha256"]
    assert (run / "run_manifest.json").read_bytes() == manifest
    assert (run / "route_catalog_v3.json").read_bytes() == catalog


def test_cache_reuses_exact_scope_and_separates_effort(tmp_path, plan, fake_native):
    run = initialize(tmp_path, plan)
    first = wf.task_dispatch(run, "inspect", {})
    other = initialize(tmp_path, plan)
    same = wf.task_dispatch(other, "inspect", {})
    assert same["input"]["codex_availability"] == first["input"]["codex_availability"]
    assert len(fake_native) == 1
    plan["tasks"][0]["route_request"]["requirements"]["reasoning_effort"] = "different-effort"
    different = wf.task_dispatch(initialize(tmp_path, plan), "inspect", {})
    assert different["route"]["reasoning_effort"] == "different-effort"
    assert len(fake_native) == 2


def test_forged_cache_does_not_establish_callability(tmp_path, plan, fake_native):
    run = initialize(tmp_path, plan)
    wf.task_dispatch(run, "inspect", {})
    cache = next((run.parent / ".codex-availability").glob("*.json"))
    forged = json.loads(cache.read_bytes())
    forged["proof"]["context_tokens"] = 900_000
    forged["proof"]["valid_until"] = (datetime.now(timezone.utc) + timedelta(days=90)).isoformat()
    wf.atomic_json(cache, forged)
    fresh = wf.task_dispatch(initialize(tmp_path, plan), "inspect", {})
    assert fresh["input"]["codex_availability"]["context_tokens"] == 32_000
    assert len(fake_native) == 2


def test_execution_context_is_part_of_cache_scope(tmp_path, plan, fake_native):
    first = initialize(tmp_path, plan)
    second = initialize(tmp_path, plan)
    wf.task_dispatch(first, "inspect", {"profile": "one"})
    wf.task_dispatch(second, "inspect", {"profile": "two"})
    assert len(fake_native) == 2


@pytest.mark.parametrize("case", ["unsupported tool", "no quota", "wrong host", "native failure"])
def test_refusal_does_not_freeze_or_claim_task(tmp_path, plan, fake_native, monkeypatch, case):
    request = plan["tasks"][0]["route_request"]
    if case == "unsupported tool":
        request["requirements"]["tools"].append("network_write")
    if case == "no quota":
        request["budget"]["quotas"] = {}
    if case == "native failure":
        def mismatched(*args):
            raise ValueError("runtime reported a different model")
        monkeypatch.setattr(native, "probe_worker", mismatched)
    run = initialize(tmp_path, plan, "omp-workflow" if case == "wrong host" else "codex-workflow")
    with pytest.raises(wf.PlanError):
        wf.task_dispatch(run, "inspect", {}, reverify_codex=True if case == "wrong host" else None)
    state = json.loads((run / "state.json").read_bytes())
    assert state["tasks"]["inspect"]["dispatch"] is None
    assert state["tasks"]["inspect"]["attempts"] == 0
    assert not (run / "tasks/inspect/route_receipt.json").exists()


@pytest.mark.parametrize("case", ["named catalog route", "parent preference", "other host"])
def test_default_dispatch_preserves_other_route_choices(tmp_path, plan, fake_native, case):
    budget = plan["tasks"][0]["route_request"]["budget"]
    surface = "codex-workflow"
    if case == "named catalog route":
        budget["preference_order"] = ["codex-gpt61-sol-medium-workflow"]
    elif case == "parent preference":
        budget.update(unknown_cost_policy="keep_parent", preference_order=[])
    else:
        surface = "omp-workflow"
    run = initialize(tmp_path, plan, surface)
    assert wf.task_dispatch(run, "inspect", {})["kind"] == "parent"
    assert not fake_native


def test_explicit_reverify_flag_remains_compatible(tmp_path, plan, fake_native):
    run = initialize(tmp_path, plan)
    first = wf.task_dispatch(run, "inspect", {}, reverify_codex=True)
    assert first["kind"] == "model"
    assert wf.task_dispatch(run, "inspect", {}) == first
    assert len(fake_native) == 1


def test_child_evidence_checks_real_tool_activity_and_exact_settings(tmp_path):
    scope = {"model": "sample", "reasoning_effort": "example", "version": "7.0",
             "tools": ["functions.exec", "apply_patch"], "effects": "reversible"}
    token = "12ab" * 8
    (tmp_path / "challenge.txt").write_text(token, encoding="ascii")
    (tmp_path / "shell.txt").write_bytes(b"shell-ok")
    patch = tmp_path / "patch.txt"
    patch.write_bytes(b"patch-ok\n")
    commands, _, wrappers = native.probe_recipe(scope)
    read_code, write_code, patch_code = wrappers
    rows = [
        {"type": "session_meta", "payload": {"model_provider": "openai", "cli_version": "7.0"}},
        {"type": "turn_context", "payload": {"model": "sample", "effort": "example", "approval_policy": "never"}},
        {"payload": {"type": "task_started", "model_context_window": 4096}},
        {"payload": {"type": "custom_tool_call", "name": "exec", "input": read_code}},
        {"payload": {"type": "custom_tool_call", "name": "exec", "input": write_code}},
        {"payload": {"type": "custom_tool_call", "name": "exec", "input": patch_code}},
        {"payload": {"type": "item_completed", "item": {
            "type": "CommandExecution", "exit_code": 0, "command": ["shell", commands[0]], "aggregated_output": token}}},
        {"payload": {"type": "item_completed", "item": {
            "type": "CommandExecution", "exit_code": 0, "command": ["shell", commands[1]], "aggregated_output": ""}}},
        {"payload": {"type": "item_completed", "item": {
            "type": "FileChange", "status": "completed", "changes": {
                str(patch): {"type": "update", "unified_diff": "@@ -1 +1 @@\n-before\n+patch-ok\n", "move_path": None}}}}},
        {"payload": {"type": "task_complete", "last_agent_message": token}},
    ]
    assert native.verify_child(rows, scope, tmp_path, token) == 4096
    for index, key, value in (
        (1, "effort", "different"),
        (1, "approval_policy", "on-request"),
        (3, "input", "tools.exec_command({sandbox_permissions:'require_escalated'})"),
        (3, "input", "/* tools.exec_command */ await tools.some_other_tool()"),
        (6, "item", {"type": "CommandExecution", "exit_code": 0, "command": ["shell", commands[0]], "aggregated_output": "wrong"}),
        (8, "item", {"type": "FileChange", "status": "failed", "changes": {str(patch): {}}}),
    ):
        changed = deepcopy(rows)
        changed[index]["payload"][key] = value
        with pytest.raises(ValueError):
            native.verify_child(changed, scope, tmp_path, token)
