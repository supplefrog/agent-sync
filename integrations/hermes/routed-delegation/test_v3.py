from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock


HERE = Path(__file__).resolve().parent
PLUGIN = HERE / "__init__.py"
SOURCE_SKILL = Path(os.environ.get("V3_ROUTE_OWNER", str(HERE.parents[2] / "skills/openai-delegation-route-research")))


def load_plugin():
    spec = importlib.util.spec_from_file_location("routed_delegation_v3_tested", PLUGIN)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


def ref(letter):
    return {"locator": f"fixture:{letter}", "sha256": letter * 64}


def route():
    return {
        "host": "hermes",
        "transport": "hermes-delegate",
        "provider": "openai-codex",
        "model": "gpt-test",
        "reasoning_effort": "medium",
        "runtime": "synthetic",
        "contract_sha256": digest({"runtime": "synthetic", "sources": {}}),
    }


def template(*, deterministic=False, parent_available=True, unknown_cost_policy="explicit_preference"):
    executor = None
    if deterministic:
        executor = {
            "executor_id": "fixture-check",
            "artifact_sha256": "e" * 64,
            "task_contract_sha256": "c" * 64,
            "coverage": "complete",
            "effects": "none",
        }
    return {
        "schema_version": 3,
        "task_class": "fixture-task",
        "requirements": {
            "tools": [],
            "context_tokens": 128,
            "task_contract_sha256": "c" * 64,
            "model": None,
            "reasoning_effort": None,
        },
        "verifier": {
            "kind": "deterministic",
            "independent": True,
            "coverage": "complete",
            "scope": "inline-text",
            "evidence": ref("b"),
        },
        "effects": "none",
        "failure_cost": "low",
        "deterministic": executor,
        "budget": {
            "objective": "api_usd",
            "api_remaining": 10.0,
            "api_reserve": 1.0,
            "allow_api_spend": True,
            "quotas": {},
            "unknown_cost_policy": unknown_cost_policy,
            "preference_order": ["fixture-model"],
            "parent_available": parent_available,
            "attempt_cap": 1,
            "attempts_used": 0,
            "fallback_route_id": None,
            "fallback_route_sha256": None,
        },
    }


def catalog(*, include_model=True, unknown_cost=False):
    candidates = []
    if include_model:
        selected_route = route()
        route_sha = digest(selected_route)
        if unknown_cost:
            cost = {
                "billing": "api",
                "basis": "unknown",
                "task_contract_sha256": None,
                "verifier_sha256": None,
                "route_sha256": None,
                "api_usd": {"generation": None, "verification": None, "fallback": None},
                "quota": None,
                "evidence": None,
            }
        else:
            cost = {
                "billing": "api",
                "basis": "observed",
                "task_contract_sha256": "c" * 64,
                "verifier_sha256": "b" * 64,
                "route_sha256": route_sha,
                "api_usd": {"generation": 0.1, "verification": 0.02, "fallback": 0.0},
                "quota": None,
                "evidence": ref("f"),
            }
        candidates.append(
            {
                "id": "fixture-model",
                "route": selected_route,
                "availability": {
                    "status": "verified",
                    "observed_at": "2026-01-01T00:00:00Z",
                    "valid_until": "2099-01-01T00:00:00Z",
                    "route_sha256": route_sha,
                    "context_tokens": 4096,
                    "tools_verified": [],
                    "allowed_effects": ["none"],
                    "evidence": ref("a"),
                },
                "quality": [],
                "cost": cost,
                "benchmark_priors": [],
            }
        )
    return {"schema_version": 3, "catalog_version": "fixture-v3", "candidates": candidates}


class V3SelectionTests(unittest.TestCase):
    def setUp(self):
        self.plugin = load_plugin()
        patcher = mock.patch.object(self.plugin, "_v3_native_contract", return_value={"runtime": "synthetic", "sources": {}})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.temp = tempfile.TemporaryDirectory()
        self.home = Path(self.temp.name) / "hermes"
        fixture_skill = Path(self.temp.name) / "route-skill"
        for name in ("references/current-gpt-catalog.json", "scripts/route_selector.py", "scripts/task_request.py", "references/route-task-v3.schema.json"):
            target = fixture_skill / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(SOURCE_SKILL / name, target)
        self.catalog_path = fixture_skill / "references" / "current-task-route-catalog.json"
        self.catalog_path.write_text(json.dumps(catalog()), encoding="utf-8")
        self.env = mock.patch.dict(
            os.environ,
            {
                "HERMES_HOME": str(self.home),
                "HERMES_ROUTED_DELEGATION_SKILL": str(fixture_skill),
            },
            clear=False,
        )
        self.env.start()
        hermes_constants = types.ModuleType("hermes_constants")
        hermes_constants.get_hermes_home = lambda: Path(os.environ["HERMES_HOME"])
        self.modules = mock.patch.dict(sys.modules, {"hermes_constants": hermes_constants})
        self.modules.start()

    def tearDown(self):
        self.modules.stop()
        self.env.stop()
        self.catalog_path.unlink(missing_ok=True)
        self.temp.cleanup()

    def task(self, *, task_id="v3", goal="Inspect exact input", request=None):
        return self.plugin._normalize_task(
            {
                "id": task_id,
                "goal": goal,
                "context": "bounded context",
                "toolsets": ["terminal"],
                "role": "leaf",
                "route_request": request or template(),
            }
        )

    def test_conflicting_and_controller_owned_fields_fail_before_selection(self):
        raw = {
            "id": "bad",
            "goal": "bad",
            "route_request": template(),
            "intelligence_tier": "routine",
        }
        with self.assertRaisesRegex(ValueError, "conflicts"):
            self.plugin._normalize_task(raw)
        with self.assertRaisesRegex(ValueError, "exactly"):
            self.plugin._normalize_task({"id": "null", "goal": "bad", "route_request": None})
        bad = template(deterministic=True)
        bad["deterministic"]["input_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "controller-owned"):
            self.task(request=bad)
        continuation = template()
        continuation["continuation"] = None
        with self.assertRaisesRegex(ValueError, "exactly"):
            self.task(request=continuation)

    def test_model_pin_binds_exact_descriptor_and_replays(self):
        task = self.task()
        first = self.plugin._select_or_reuse_v3("parent", task, 77)
        self.catalog_path.write_text("{}", encoding="utf-8")
        second = self.plugin._select_or_reuse_v3("parent", task, 77)
        self.assertEqual(first, second)
        self.assertEqual(first["dispatch"]["kind"], "model")
        descriptor = first["binding"]["input_descriptor"]
        self.assertEqual(
            descriptor,
            {
                "task_id": "v3",
                "goal": "Inspect exact input",
                "context": "bounded context",
                "toolsets": ["terminal"],
                "role": "leaf",
                "max_iterations": 77,
            },
        )
        self.assertEqual(first["request"]["input_sha256"], digest(descriptor))
        self.assertEqual(first["request"]["requirements"]["host"], "hermes")
        self.assertEqual(first["request"]["requirements"]["transport"], "hermes-delegate")

    def test_changed_input_and_rehashed_tampered_receipt_fail_closed(self):
        task = self.task()
        self.plugin._select_or_reuse_v3("parent", task, 77)
        with self.assertRaisesRegex(RuntimeError, "different task or requirement"):
            self.plugin._select_or_reuse_v3("parent", self.task(goal="changed"), 77)
        pin_path = self.plugin._pin_path("parent")
        store = json.loads(pin_path.read_text(encoding="utf-8"))
        entry = store["tasks"]["v3"]
        entry["decision"]["selection_basis"] = "tampered"
        payload = {key: value for key, value in entry.items() if key != "pin_sha256"}
        entry["pin_sha256"] = self.plugin._sha(payload)
        pin_path.write_text(json.dumps(store), encoding="utf-8")
        with self.assertRaisesRegex(Exception, "decision hash|frozen policy/task"):
            self.plugin._select_or_reuse_v3("parent", task, 77)

    def test_each_non_model_outcome_is_explicit(self):
        self.catalog_path.write_text(json.dumps(catalog(include_model=False)), encoding="utf-8")
        parent = self.plugin._select_or_reuse_v3("p-parent", self.task(task_id="parent"), 10)
        self.assertEqual(parent["dispatch"]["kind"], "parent")

        deferred_request = template(parent_available=False)
        deferred = self.plugin._select_or_reuse_v3(
            "p-defer", self.task(task_id="defer", request=deferred_request), 10
        )
        self.assertEqual(deferred["dispatch"]["kind"], "defer")

        deterministic_request = template(deterministic=True)
        deterministic = self.plugin._select_or_reuse_v3(
            "p-det", self.task(task_id="det", request=deterministic_request), 10
        )
        self.assertEqual(deterministic["dispatch"]["kind"], "deterministic")
        self.assertEqual(
            deterministic["dispatch"]["executor"]["input_sha256"],
            deterministic["request"]["input_sha256"],
        )

    def test_unknown_cost_stays_parent_owned_without_quality_claim(self):
        self.catalog_path.write_text(json.dumps(catalog(unknown_cost=True)), encoding="utf-8")
        pin = self.plugin._select_or_reuse_v3("p-cost", self.task(task_id="cost"), 10)
        self.assertEqual(pin["dispatch"]["kind"], "parent")
        self.assertIsNone(pin["decision"]["qualification"])
        self.assertIsNone(pin["decision"]["cost_observation"])
        self.assertEqual(pin["decision"]["resource_claim"], "no cheapest-route or quota-conversion claim")

    def test_exact_route_tuple_mismatch_is_rejected(self):
        task = self.task()
        materializer = self.plugin._task_request_module()
        request = materializer.materialize(
            task["route_request"],
            task_id=task["id"],
            host="hermes",
            transport="hermes-delegate",
            input_descriptor=self.plugin._v3_input_descriptor(task, 10),
            as_of="2026-09-06T00:00:00Z",
        )
        decision = {"decision_id": "1" * 64, "route": route()}
        dispatch = {"kind": "model", "decision_id": "1" * 64, "route": dict(route(), transport="wrong")}
        with self.assertRaisesRegex(RuntimeError, "changed the selected route"):
            self.plugin._validate_v3_dispatch(dispatch, decision, request)
        bad_route = dict(route(), host="codex")
        decision["route"] = bad_route
        dispatch["route"] = bad_route
        with self.assertRaisesRegex(RuntimeError, "host/transport/provider tuple"):
            self.plugin._validate_v3_dispatch(dispatch, decision, request)


class V3HandleTests(unittest.TestCase):
    def setUp(self):
        self.plugin = load_plugin()
        for name, value in (("_v3_native_envelope", {"fixture": "bound"}), ("_guard_v3_child", None)):
            patcher = mock.patch.object(self.plugin, name, return_value=value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.temp = tempfile.TemporaryDirectory()
        self.home = Path(self.temp.name) / "hermes"
        self.env = mock.patch.dict(os.environ, {"HERMES_HOME": str(self.home),
            "HERMES_ROUTED_DELEGATION_SKILL": str(SOURCE_SKILL)}, clear=False)
        self.env.start()
        self.parent = types.SimpleNamespace(
            session_id="parent", provider="openai-codex", _delegate_depth=0,
            _current_turn_id="turn", _interrupt_requested=False,
        )
        lifecycle = types.ModuleType("agent.subagent_lifecycle")
        lifecycle.get_active_subagent_parent = lambda: self.parent
        agent = types.ModuleType("agent")
        agent.subagent_lifecycle = lifecycle
        hermes_constants = types.ModuleType("hermes_constants")
        hermes_constants.get_hermes_home = lambda: Path(os.environ["HERMES_HOME"])
        self.modules = mock.patch.dict(
            sys.modules,
            {
                "agent": agent,
                "agent.subagent_lifecycle": lifecycle,
                "hermes_constants": hermes_constants,
            },
        )
        self.modules.start()

    def tearDown(self):
        self.modules.stop()
        self.env.stop()
        self.temp.cleanup()

    def raw(self, task_id):
        return {"id": task_id, "goal": f"goal-{task_id}", "route_request": template()}

    def pin(self, task, kind):
        selected_route = route() if kind == "model" else None
        request = dict(template())
        request = json.loads(json.dumps(request))
        request.update(
            task_id=task["id"], input_sha256="8" * 64,
            as_of="2026-09-06T00:00:00Z", continuation=None,
        )
        request["requirements"].update(host="hermes", transport="hermes-delegate")
        decision = {"decision_id": task["id"][0] * 64, "route": selected_route}
        dispatch = {"kind": kind, "decision_id": decision["decision_id"]}
        if kind == "model":
            dispatch["route"] = selected_route
        elif kind == "deterministic":
            dispatch["executor"] = {"executor_id": "fixture"}
        else:
            dispatch["route"] = None
        return {
            "request": request,
            "decision": decision,
            "dispatch": dispatch,
            "catalog": {"schema_version": 3},
            "selector_identity": {"locator": "fixture", "sha256": "9" * 64},
        }

    def runtime(self):
        return {
            "is_paused": lambda: False,
            "get_max_depth": lambda: 2,
            "get_max_children": lambda: 1,
            "load_config": lambda: {"max_iterations": 33},
            "default_iterations": 250,
            "capture_owner": lambda _owner: (None, None),
            "build": object(), "run": object(), "finalize": lambda *args, **kwargs: None,
            "validate_request": None, "budget_summary": object(), "interrupt": None,
            "detach": None,
        }

    def test_non_model_batch_never_prepares_or_executes(self):
        kinds = {"d": "deterministic", "p": "parent", "x": "defer"}
        select = lambda _parent, task, _iterations: self.pin(task, kinds[task["id"]])
        with mock.patch.object(self.plugin, "_private_runtime", return_value=self.runtime()), \
             mock.patch.object(self.plugin, "_select_or_reuse_v3", side_effect=select), \
             mock.patch.object(self.plugin, "_prepare_child", side_effect=AssertionError("must not prepare")), \
             mock.patch.object(self.plugin, "_execute_children", side_effect=AssertionError("must not execute")):
            value = json.loads(self.plugin._handle({"tasks": [self.raw("d"), self.raw("p"), self.raw("x")] }))
        self.assertFalse(value["success"])
        self.assertEqual(value["pending_parent_actions"], 3)
        self.assertEqual([item["action"]["kind"] for item in value["results"]], list(kinds.values()))
        self.assertTrue(all(item["parent_action_required"] for item in value["results"]))

    def test_paused_admission_does_not_consume_an_execution_attempt(self):
        runtime = self.runtime()
        runtime["is_paused"] = lambda: True
        with mock.patch.object(self.plugin, "_private_runtime", return_value=runtime), \
             mock.patch.object(self.plugin, "_select_or_reuse_v3", side_effect=lambda _p, task, _m: self.pin(task, "model")), \
             mock.patch.object(self.plugin, "_prepare_child", side_effect=AssertionError("must not construct")):
            value = json.loads(self.plugin._handle({"tasks": [self.raw("m")]}))
        self.assertFalse(value["success"])
        self.assertIn("paused", value["error"])
        reservations = self.home / "cache/routed-delegation/direct-attempts"
        self.assertFalse(reservations.exists())

    def test_mixed_batch_preserves_input_indices_and_model_summary_count(self):
        kinds = {"p": "parent", "m": "model", "d": "defer"}
        select = lambda _parent, task, _iterations: self.pin(task, kinds[task["id"]])
        prepared_calls = []

        def prepare(_parent, task, receipt, index, count, _max_iterations, **kwargs):
            child = types.SimpleNamespace(_routed_raw_result=None)
            prepared_calls.append((index, count, task["id"]))
            kwargs["on_built"](child)
            return child

        def execute(prepared, *_args, **_kwargs):
            self.assertEqual([item[0] for item in prepared], [1])
            prepared[0][3]._routed_raw_result = {"full": "raw"}
            return [{
                "task_index": 1, "status": "completed", "exit_reason": "completed",
                "execution_outcome": "completed", "closure_confirmed": True,
                "finalization_status": "returned", "summary": "bounded",
            }]

        with mock.patch.object(self.plugin, "_private_runtime", return_value=self.runtime()), \
             mock.patch.object(self.plugin, "_select_or_reuse_v3", side_effect=select), \
             mock.patch.object(self.plugin, "_prepare_child", side_effect=prepare), \
             mock.patch.object(self.plugin, "_execute_children", side_effect=execute):
            value = json.loads(self.plugin._handle({"tasks": [self.raw("p"), self.raw("m"), self.raw("d")] }))
        self.assertEqual(prepared_calls, [(1, 1, "m")], value)
        self.assertEqual([item["task_id"] for item in value["results"]], ["p", "m", "d"])
        self.assertIn("acceptance_required", value["results"][1])
        self.assertNotIn("qualification", value["results"][1])
        self.assertFalse(value["success"])
        reservation = self.plugin._hermes_home() / "cache/routed-delegation/direct-attempts" / (
            self.plugin._sha({"parent": "parent", "task_id": "m"}) + ".json"
        )
        saved = json.loads(reservation.read_text(encoding="utf-8"))
        self.assertEqual(saved["native_result"], {"full": "raw"})

    def test_repeated_task_id_never_reaches_second_preparation(self):
        count = 0

        def prepare(_parent, task, receipt, index, _count, _max_iterations, **kwargs):
            nonlocal count
            count += 1
            child = types.SimpleNamespace(_routed_raw_result={"raw": True})
            kwargs["on_built"](child)
            return child

        def execute(*_args, **_kwargs):
            return [{
                "task_index": 0, "status": "completed", "exit_reason": "completed",
                "execution_outcome": "completed", "closure_confirmed": True,
                "finalization_status": "returned", "summary": "done",
            }]

        select = lambda _parent, task, _iterations: self.pin(task, "model")
        patches = (
            mock.patch.object(self.plugin, "_private_runtime", return_value=self.runtime()),
            mock.patch.object(self.plugin, "_select_or_reuse_v3", side_effect=select),
            mock.patch.object(self.plugin, "_prepare_child", side_effect=prepare),
            mock.patch.object(self.plugin, "_execute_children", side_effect=execute),
        )
        for patcher in patches:
            patcher.start()
        try:
            first = json.loads(self.plugin._handle({"tasks": [self.raw("m")] }))
            second = json.loads(self.plugin._handle({"tasks": [self.raw("m")] }))
        finally:
            for patcher in reversed(patches):
                patcher.stop()
        self.assertTrue(first["success"], first)
        self.assertFalse(second["success"])
        self.assertIn("already has an owned attempt", second["error"])
        self.assertEqual(count, 1)


class NativeBindingTests(unittest.TestCase):
    def setUp(self):
        self.plugin = load_plugin()
        self.child = types.SimpleNamespace(
            _delegate_role="leaf", _delegate_depth=1, enabled_toolsets=["none"],
            disabled_toolsets=["kanban"], ephemeral_system_prompt="actual project context",
            prefill_messages=[], _routed_home=HERE, valid_tool_names=set(),
            context_compressor=types.SimpleNamespace(context_length=4000))
        self.envelope = {
            "effective_role": "leaf", "depth": 1, "enabled_toolsets": ["none"],
            "disabled_toolsets": ["kanban"],
            "child_prompt_sha256": self.plugin._sha("actual project context"),
            "prefill_sha256": self.plugin._sha([]), "home": str(HERE.resolve()),
            "profile_files": self.plugin._v3_profile_files(HERE)}
        self.task = {"_native_envelope": self.envelope}
        self.pin = {"request": {"requirements": {"tools": [], "context_tokens": 128}}}

    def test_actual_native_context_and_capability_fields_accept_matching_child(self):
        self.plugin._validate_v3_child(self.child, self.task, self.pin)

    def test_soul_or_profile_configuration_drift_rejects(self):
        changed = {"SOUL.md": "e" * 64, "config.yaml": None}
        with mock.patch.object(self.plugin, "_v3_profile_files", return_value=changed):
            with self.assertRaisesRegex(RuntimeError, "pinned execution input"):
                self.plugin._validate_v3_child(self.child, self.task, self.pin)

    def test_inherited_prompt_role_prefill_and_profile_drift_reject(self):
        for key, changed in (("ephemeral_system_prompt", "different project instructions"),
                             ("_delegate_role", "orchestrator"),
                             ("prefill_messages", [{"role": "user", "content": "changed"}]),
                             ("_routed_home", HERE / "other-profile")):
            with self.subTest(field=key):
                before = getattr(self.child, key)
                setattr(self.child, key, changed)
                with self.assertRaisesRegex(RuntimeError, "pinned execution input"):
                    self.plugin._validate_v3_child(self.child, self.task, self.pin)
                setattr(self.child, key, before)

    def test_undeclared_tool_and_insufficient_context_reject(self):
        self.child.valid_tool_names = {"terminal"}
        with self.assertRaisesRegex(RuntimeError, "declared tools"):
            self.plugin._validate_v3_child(self.child, self.task, self.pin)
        self.child.valid_tool_names = set()
        self.child.context_compressor.context_length = 127
        with self.assertRaisesRegex(RuntimeError, "context capacity"):
            self.plugin._validate_v3_child(self.child, self.task, self.pin)

    def test_request_time_tool_drift_cannot_reach_native_request_builder(self):
        builder = mock.Mock(return_value={"model": "fixture"})
        self.child._build_api_kwargs = builder
        self.plugin._guard_v3_child(self.child, self.task, self.pin)
        self.assertEqual(self.child._build_api_kwargs([], []), {"model": "fixture"})
        self.child.valid_tool_names = {"terminal"}
        # Editing the caller's pin cannot change the frozen guard.
        self.pin["request"]["requirements"]["tools"] = ["terminal"]
        with self.assertRaisesRegex(RuntimeError, "declared tools"):
            self.child._build_api_kwargs([], [])
        self.assertEqual(builder.call_count, 1)

    def test_envelope_change_changes_actual_input_identity(self):
        task = {"id": "test", "goal": "review", "context": None, "toolsets": ["none"],
                "role": "leaf", "_native_envelope": self.envelope}
        before = digest(self.plugin._v3_input_descriptor(task, 2))
        task["_native_envelope"] = dict(self.envelope, child_prompt_sha256="e" * 64)
        self.assertNotEqual(before, digest(self.plugin._v3_input_descriptor(task, 2)))

    def test_native_source_identity_mismatch_rejects_matching_model_tuple(self):
        request = {"requirements": {"host": "hermes", "transport": "hermes-delegate",
                                   "model": None, "reasoning_effort": None}}
        decision = {"decision_id": "a" * 64, "route": route()}
        dispatch = {"kind": "model", **decision}
        with mock.patch.object(self.plugin, "_v3_native_contract", return_value={"runtime": "synthetic", "sources": {"changed.py": "f" * 64}}):
            with self.assertRaisesRegex(RuntimeError, "runtime/source contract"):
                self.plugin._validate_v3_dispatch(dispatch, decision, request)


if __name__ == "__main__":
    unittest.main()
