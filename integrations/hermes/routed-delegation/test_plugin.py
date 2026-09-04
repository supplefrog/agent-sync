from __future__ import annotations

import importlib.util
import contextvars
import json
import os
import sys
import tempfile
import threading
import types
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest import mock

PLUGIN = Path(__file__).with_name("__init__.py")
ROUTE_SKILL = Path(__file__).resolve().parents[3] / "skills" / "openai-delegation-route-research"
DYNAMIC_WORKFLOWS_SKILL = Path(__file__).resolve().parents[3] / "skills" / "dynamic-workflows"


def load_plugin():
    spec = importlib.util.spec_from_file_location("routed_delegation_tested", PLUGIN)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RoutedDelegationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.plugin = load_plugin()
        self.temp = tempfile.TemporaryDirectory()
        self.home = Path(self.temp.name) / "hermes"
        self.env = mock.patch.dict(
            os.environ,
            {
                "HERMES_HOME": str(self.home),
                "HERMES_ROUTED_DELEGATION_SKILL": str(ROUTE_SKILL),
                "HERMES_DYNAMIC_WORKFLOWS_SKILL": str(DYNAMIC_WORKFLOWS_SKILL),
            },
            clear=False,
        )
        self.env.start()

    def tearDown(self) -> None:
        self.env.stop()
        self.temp.cleanup()

    def task(self, goal: str = "Inspect one bounded file") -> dict:
        return self.plugin._normalize_task(
            {
                "id": "inspect",
                "goal": goal,
                "intelligence_tier": "routine",
                "latency_sensitive": False,
                "failure_cost": "low",
            }
        )

    def test_route_is_selected_once_and_reused(self) -> None:
        task = self.task()
        first = self.plugin._select_or_reuse("parent-1", task, 250)
        catalog = json.loads(
            (ROUTE_SKILL / "references" / "current-gpt-catalog.json").read_text(encoding="utf-8")
        )
        selector, _, catalog_path = self.plugin._selector_and_catalog()
        selector.select_route = mock.Mock(side_effect=AssertionError("selector must not rerun for a pinned retry"))
        with mock.patch.object(
            self.plugin,
            "_selector_and_catalog",
            return_value=(selector, catalog, catalog_path),
        ):
            second = self.plugin._select_or_reuse("parent-1", task, 250)
        self.assertEqual(first, second)
        self.assertEqual(first["target_surface"], "hermes-delegate")
        self.assertEqual(first["route"]["provider"], "openai-codex")

    def test_reused_task_id_with_changed_goal_fails_closed(self) -> None:
        self.plugin._select_or_reuse("parent-1", self.task(), 250)
        with self.assertRaisesRegex(RuntimeError, "already pins a different task"):
            self.plugin._select_or_reuse("parent-1", self.task("Different work"), 250)

    def test_reused_task_id_with_changed_execution_fails_closed(self) -> None:
        task = self.task()
        self.plugin._select_or_reuse("parent-1", task, 250)
        changed = dict(task, role="orchestrator", toolsets=["terminal"])
        with self.assertRaisesRegex(RuntimeError, "already pins a different task"):
            self.plugin._select_or_reuse("parent-1", changed, 250)
        with self.assertRaisesRegex(RuntimeError, "already pins a different task"):
            self.plugin._select_or_reuse("parent-1", task, 100)

    def test_tampered_pin_fails_closed(self) -> None:
        self.plugin._select_or_reuse("parent-1", self.task(), 250)
        path = self.plugin._pin_path("parent-1")
        store = json.loads(path.read_text(encoding="utf-8"))
        store["tasks"]["inspect"]["receipt"]["route"]["model"] = "tampered"
        path.write_text(json.dumps(store), encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "integrity validation"):
            self.plugin._select_or_reuse("parent-1", self.task(), 250)

    def test_rehashed_forged_route_pin_fails_catalog_validation(self) -> None:
        self.plugin._select_or_reuse("parent-1", self.task(), 250)
        path = self.plugin._pin_path("parent-1")
        store = json.loads(path.read_text(encoding="utf-8"))
        pinned = store["tasks"]["inspect"]
        receipt = pinned["receipt"]
        receipt["route"]["model"] = "gpt-forged"
        receipt["decision_id"] = self.plugin._sha({
            "policy_sha256": receipt["policy_sha256"],
            "requirement_sha256": receipt["requirement_sha256"],
            "outcome": "selected",
            "route": receipt["route"],
        })
        envelope = {"binding": pinned["binding"], "receipt": receipt}
        pinned["pin_sha256"] = self.plugin._sha(envelope)
        path.write_text(json.dumps(store), encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "outside the active catalog"):
            self.plugin._select_or_reuse("parent-1", self.task(), 250)

    def test_project_sibling_route_skill_is_discovered_without_override(self) -> None:
        with mock.patch.dict(
            os.environ, {"HERMES_ROUTED_DELEGATION_SKILL": ""}, clear=False
        ):
            self.assertEqual(self.plugin._route_skill(), ROUTE_SKILL.resolve())

    def test_host_context_local_home_wins(self) -> None:
        scoped = Path(self.temp.name) / "scoped-profile"
        hermes_constants = types.ModuleType("hermes_constants")
        hermes_constants.get_hermes_home = lambda: scoped
        with mock.patch.dict(sys.modules, {"hermes_constants": hermes_constants}):
            self.assertEqual(self.plugin._hermes_home(), scoped.resolve())

    def test_execute_children_propagates_context_and_finalizes_once(self) -> None:
        marker = contextvars.ContextVar("marker", default="missing")
        marker.set("parent-context")
        finalized = []
        prepared = []
        for index in range(2):
            task = self.task(f"Inspect bounded file {index}")
            task["id"] = f"inspect-{index}"
            receipt = {
                "route": {
                    "provider": "openai-codex",
                    "model": "gpt-5.6-luna",
                    "reasoning_effort": "medium",
                }
            }
            child = types.SimpleNamespace(
                provider="openai-codex",
                model="gpt-5.6-luna",
                reasoning_config={"enabled": True, "effort": "medium"},
                _session_init_model_config={
                    "reasoning_config": {"enabled": True, "effort": "medium"}
                },
                _fallback_chain=[],
            )
            prepared.append((index, task, receipt, child))

        def run(**kwargs):
            return {
                "task_index": kwargs["task_index"],
                "status": "completed",
                "summary": marker.get(),
                "_child_role": "leaf",
                "_child_cost_usd": 0.0,
            }

        def finalize(results, task_list, native_children, parent):
            finalized.append((results, task_list, native_children, parent))
            for result in results:
                result.pop("_child_role", None)
                result.pop("_child_cost_usd", None)

        parent = types.SimpleNamespace(_interrupt_requested=False)
        results = self.plugin._execute_children(
            prepared,
            parent,
            run,
            finalize,
            max_children=2,
            owner_kwargs={},
        )
        self.assertEqual([item["summary"] for item in results], ["parent-context"] * 2)
        self.assertEqual(len(finalized), 1)
        self.assertNotIn("_child_role", results[0])

    def test_prepare_child_injects_and_verifies_exact_route(self) -> None:
        child = types.SimpleNamespace(
            provider="openai-codex",
            model="gpt-5.6-luna",
            _session_init_model_config={
                "reasoning_config": {"enabled": True, "effort": "high"}
            },
            _primary_runtime={
                "reasoning_config": {"enabled": True, "effort": "high"}
            },
        )
        calls = []

        def build(**kwargs):
            calls.append(kwargs)
            return child

        hermes_constants = types.ModuleType("hermes_constants")
        hermes_constants.parse_reasoning_effort = lambda value: {"effort": value}
        receipt = {
            "route": {
                "provider": "openai-codex",
                "model": "gpt-5.6-luna",
                "reasoning_effort": "medium",
            }
        }
        parent = types.SimpleNamespace(provider="openai-codex")
        with mock.patch.dict(sys.modules, {"hermes_constants": hermes_constants}):
            result = self.plugin._prepare_child(
                parent, self.task(), receipt, 0, 1, 50, build=build
            )
        self.assertIs(result, child)
        self.assertEqual(child.reasoning_config, {"effort": "medium"})
        self.assertEqual(
            child._session_init_model_config["reasoning_config"],
            {"effort": "medium"},
        )
        self.assertEqual(
            child._primary_runtime["reasoning_config"],
            {"effort": "medium"},
        )
        self.assertEqual(child._fallback_chain, [])
        self.assertEqual(calls[0]["model"], "gpt-5.6-luna")
        self.assertNotIn("override_provider", calls[0])

    def test_provider_mismatch_fails_before_child_construction(self) -> None:
        receipt = {
            "route": {
                "provider": "nous",
                "model": "stepfun/step-3.7-flash:free",
                "reasoning_effort": "medium",
            }
        }
        parent = types.SimpleNamespace(provider="openai-codex")
        hermes_constants = types.ModuleType("hermes_constants")
        hermes_constants.parse_reasoning_effort = lambda value: {"effort": value}
        with mock.patch.dict(sys.modules, {"hermes_constants": hermes_constants}), self.assertRaisesRegex(
            RuntimeError, "does not match active parent provider"
        ):
            self.plugin._prepare_child(parent, self.task(), receipt, 0, 1, 50)


    def test_reasoning_source_contract_rejects_host_drift(self) -> None:
        reasoning_helper = "cfg = agent.reasoning_config"
        mode_builder = (
            "_wire_reasoning_config = _reasoning_config_for_wire(agent)\n"
            "return transport(reasoning_config=_wire_reasoning_config)"
        )
        transport = (
            'reasoning_config = params.get("reasoning_config")\n'
            'reasoning_effort = reasoning_config["effort"]'
        )
        self.assertTrue(
            self.plugin._reasoning_source_contract(
                reasoning_helper, mode_builder, transport
            )
        )
        self.assertFalse(
            self.plugin._reasoning_source_contract(
                "cfg = None", mode_builder, transport
            )
        )
        self.assertFalse(
            self.plugin._reasoning_source_contract(
                reasoning_helper,
                "return transport(reasoning_config=None)",
                transport,
            )
        )

    def workflow_plan(self) -> Path:
        path = Path(self.temp.name) / "workflow.json"
        path.write_text(json.dumps({
            "name": "hermes-adapter",
            "max_workers": 2,
            "tasks": [
                {
                    "id": "left",
                    "role": "researcher",
                    "intelligence_tier": "standard",
                    "latency_sensitive": False,
                    "failure_cost": "low",
                    "acceptance": ["Returns left evidence."],
                    "prompt": "Return left evidence.",
                },
                {
                    "id": "right",
                    "role": "researcher",
                    "intelligence_tier": "standard",
                    "latency_sensitive": False,
                    "failure_cost": "low",
                    "acceptance": ["Returns right evidence."],
                    "prompt": "Return right evidence.",
                },
                {
                    "id": "synthesize",
                    "role": "synthesizer",
                    "intelligence_tier": "demanding",
                    "latency_sensitive": False,
                    "failure_cost": "high",
                    "depends_on": ["left", "right"],
                    "include_outputs": ["left", "right"],
                    "acceptance": ["Combines both results."],
                    "prompt": "Combine both:\n{{output:left}}\n{{output:right}}",
                },
            ],
        }), encoding="utf-8")
        return path

    def workflow_runtime(self, workflow_state, run_dir: Path):
        barrier = threading.Barrier(2)
        marker = contextvars.ContextVar("workflow-marker", default="missing")
        marker.set("parent-context")
        finalized = []

        def build(**kwargs):
            child = types.SimpleNamespace(
                provider="openai-codex",
                model=kwargs["model"],
                reasoning_config={"effort": "wrong"},
                _session_init_model_config={"reasoning_config": {"effort": "wrong"}},
                _primary_runtime={"reasoning_config": {"effort": "wrong"}},
                _fallback_chain=["must-be-disabled"],
                _delegate_role="leaf",
                _subagent_id=f"sa-{kwargs['task_index']}",
                closed=False,
            )
            child.close = lambda: setattr(child, "closed", True)
            return child

        def run(**kwargs):
            self.assertEqual(marker.get(), "parent-context")
            child = kwargs["child"]
            task_id = child._workflow_task_id
            state = workflow_state.load_json(run_dir / "state.json")
            self.assertEqual(state["tasks"][task_id]["status"], "running")
            self.assertEqual(state["tasks"][task_id]["handle"], child._subagent_id)
            if task_id in {"left", "right"}:
                barrier.wait(timeout=2)
            if task_id == "synthesize":
                self.assertIn("output-left", kwargs["goal"])
                self.assertIn("output-right", kwargs["goal"])
            child.close()
            return {
                "task_index": kwargs["task_index"],
                "status": "completed",
                "exit_reason": "completed",
                "summary": f"output-{task_id}",
                "model": child.model,
                "api_calls": 1,
                "duration_seconds": 0.01,
                "_child_role": "leaf",
                "_child_cost_usd": 0.0,
            }

        def finalize(results, task_list, native_children, parent):
            self.assertTrue(all(child.closed for _index, _task, child in native_children))
            finalized.append([entry["task_index"] for entry in results])
            for result in results:
                result.pop("_child_role", None)
                result.pop("_child_cost_usd", None)

        return {
            "build": build,
            "run": run,
            "finalize": finalize,
            "get_max_children": lambda: 8,
            "load_config": lambda: {"max_iterations": 40},
        }, finalized

    def test_workflow_adapter_runs_parallel_waves_with_pinned_routes(self) -> None:
        workflow_state = self.plugin._workflow_state_module()
        run_dir = self.plugin._initialize_workflow(
            self.workflow_plan(), Path(self.temp.name) / "runs", {}
        )
        state = workflow_state.load_json(run_dir / "state.json")
        self.assertEqual(state["target_surface"], "hermes-workflow")
        for task_state in state["tasks"].values():
            receipt = task_state["decision_receipt"]
            self.assertEqual(receipt["target_surface"], "hermes-workflow")
            self.assertEqual(receipt["route"]["runtime"]["host"], "hermes")

        runtime, finalized = self.workflow_runtime(workflow_state, run_dir)
        parent = types.SimpleNamespace(
            provider="openai-codex", _delegate_depth=0, _interrupt_requested=False
        )
        hermes_constants = types.ModuleType("hermes_constants")
        hermes_constants.parse_reasoning_effort = lambda value: {"effort": value}
        with mock.patch.dict(sys.modules, {"hermes_constants": hermes_constants}):
            result = self.plugin._run_workflow(run_dir, parent, runtime, owner_kwargs={})

        self.assertTrue(result["success"])
        state = workflow_state.load_json(run_dir / "state.json")
        self.assertEqual(state["status"], "succeeded")
        self.assertEqual(finalized, [[0, 1], [0]])
        for task_id, task_state in state["tasks"].items():
            self.assertEqual(task_state["status"], "succeeded")
            self.assertTrue(task_state["handle_closed_at"])
            self.assertEqual(Path(task_state["output_path"]).read_text(encoding="utf-8"), f"output-{task_id}")

    def test_interrupt_waits_for_native_completion_and_closes_the_handle(self) -> None:
        workflow_state = self.plugin._workflow_state_module()
        plan_path = Path(self.temp.name) / "interrupt-workflow.json"
        plan_path.write_text(json.dumps({
            "name": "interrupt-workflow",
            "tasks": [{
                "id": "task",
                "role": "worker",
                "intelligence_tier": "standard",
                "latency_sensitive": False,
                "failure_cost": "low",
                "acceptance": ["Stops cleanly."],
                "prompt": "Wait for interruption.",
            }],
        }), encoding="utf-8")
        run_dir = self.plugin._initialize_workflow(
            plan_path, Path(self.temp.name) / "interrupt-runs", {}
        )
        parent = types.SimpleNamespace(
            provider="openai-codex", _delegate_depth=0, _interrupt_requested=False
        )
        interrupted = threading.Event()
        interrupted_handles = []
        children = []

        def build(**kwargs):
            child = types.SimpleNamespace(
                provider="openai-codex",
                model=kwargs["model"],
                reasoning_config={},
                _session_init_model_config={},
                _primary_runtime={},
                _fallback_chain=[],
                _delegate_role="leaf",
                _subagent_id="sa-interrupt",
                closed=False,
            )
            child.close = lambda: setattr(child, "closed", True)
            children.append(child)
            return child

        def run(**kwargs):
            parent._interrupt_requested = True
            self.assertTrue(interrupted.wait(timeout=2))
            return {
                "task_index": kwargs["task_index"],
                "status": "interrupted",
                "exit_reason": "interrupted",
                "summary": None,
                "error": "interrupt confirmed",
                "model": kwargs["child"].model,
                "_child_role": "leaf",
                "_child_cost_usd": 0.0,
            }

        def interrupt(handle):
            interrupted_handles.append(handle)
            interrupted.set()

        def finalize(_results, _tasks, native_children, _parent):
            for _index, _task, child in native_children:
                child.close()

        runtime = {
            "build": build,
            "run": run,
            "finalize": finalize,
            "interrupt": interrupt,
            "list_active": lambda: [],
            "get_max_children": lambda: 8,
            "load_config": lambda: {"max_iterations": 40},
        }
        hermes_constants = types.ModuleType("hermes_constants")
        hermes_constants.parse_reasoning_effort = lambda value: {"effort": value}
        with mock.patch.dict(sys.modules, {"hermes_constants": hermes_constants}):
            result = self.plugin._run_workflow(run_dir, parent, runtime, owner_kwargs={})

        self.assertFalse(result["success"])
        self.assertEqual(result["status"], "stopped")
        self.assertEqual(interrupted_handles, ["sa-interrupt"])
        self.assertFalse(result["waves"][0]["abandoned_after_interrupt"])
        self.assertTrue(children[0].closed)
        state = workflow_state.load_json(run_dir / "state.json")
        task_state = state["tasks"]["task"]
        self.assertEqual(task_state["status"], "stopped")
        self.assertTrue(task_state["handle_closed_at"])
        self.assertTrue(
            self.plugin._trusted_close_witness_path(
                run_dir,
                "task",
                task_state["handle"],
                task_state["launch_token"],
            ).is_file()
        )

    def test_workflow_binding_rejects_coordinated_run_local_selector_rewrite(self) -> None:
        workflow_state = self.plugin._workflow_state_module()
        run_dir = self.plugin._initialize_workflow(
            self.workflow_plan(), Path(self.temp.name) / "binding-runs", {}
        )
        self.plugin._validate_hermes_workflow_run(workflow_state, run_dir)

        selector_path = run_dir / "route_selector.py"
        selector_path.write_text(
            "raise RuntimeError('run-local selector executed')\n", encoding="utf-8"
        )
        manifest = workflow_state.load_json(run_dir / "run_manifest.json")
        manifest["route_selector_sha256"] = self.plugin._sha(selector_path.read_bytes())
        workflow_state.atomic_json(run_dir / "run_manifest.json", manifest)

        with self.assertRaisesRegex(RuntimeError, "trusted binding"):
            self.plugin._validate_hermes_workflow_run(workflow_state, run_dir)

    def test_unregistered_workflow_run_is_rejected(self) -> None:
        workflow_state = self.plugin._workflow_state_module()
        run_dir = self.plugin._initialize_workflow(
            self.workflow_plan(), Path(self.temp.name) / "unregistered-runs", {}
        )
        self.plugin._workflow_binding_path(run_dir).unlink()
        with self.assertRaisesRegex(RuntimeError, "not registered"):
            self.plugin._validate_hermes_workflow_run(workflow_state, run_dir)

    def test_resume_waits_for_workflow_execution_lock(self) -> None:
        workflow_state = self.plugin._workflow_state_module()
        run_dir = self.plugin._initialize_workflow(
            self.workflow_plan(), Path(self.temp.name) / "execution-lock-runs", {}
        )
        attempted = threading.Event()

        def resume() -> dict:
            attempted.set()
            return json.loads(
                self.plugin._workflow_handle({
                    "action": "resume",
                    "run_dir": str(run_dir),
                })
            )

        with ThreadPoolExecutor(max_workers=1) as pool:
            with workflow_state.execution_lock(run_dir):
                future = pool.submit(resume)
                self.assertTrue(attempted.wait(timeout=1))
                self.assertFalse(future.done())
            result = future.result(timeout=2)
        self.assertTrue(result["success"])

    def test_workflow_child_must_be_native_leaf_and_launch_is_aborted(self) -> None:
        workflow_state = self.plugin._workflow_state_module()
        run_dir = self.plugin._initialize_workflow(
            self.workflow_plan(), Path(self.temp.name) / "leaf-runs", {}
        )

        def build(**kwargs):
            child = types.SimpleNamespace(
                provider="openai-codex",
                model=kwargs["model"],
                reasoning_config={},
                _session_init_model_config={},
                _primary_runtime={},
                _fallback_chain=[],
                _delegate_role="orchestrator",
                _subagent_id="sa-orchestrator",
                closed=False,
            )
            child.close = lambda: setattr(child, "closed", True)
            return child

        runtime = {
            "build": build,
            "run": mock.Mock(side_effect=AssertionError("unsafe child must not run")),
            "finalize": mock.Mock(),
            "get_max_children": lambda: 8,
            "load_config": lambda: {"max_iterations": 40},
        }
        parent = types.SimpleNamespace(
            provider="openai-codex", _delegate_depth=0, _interrupt_requested=False
        )
        hermes_constants = types.ModuleType("hermes_constants")
        hermes_constants.parse_reasoning_effort = lambda value: {"effort": value}
        with mock.patch.dict(sys.modules, {"hermes_constants": hermes_constants}):
            result = self.plugin._run_workflow(run_dir, parent, runtime, owner_kwargs={})

        self.assertFalse(result["success"])
        state = workflow_state.load_json(run_dir / "state.json")
        self.assertEqual(state["tasks"]["left"]["status"], "failed")
        self.assertIn("leaf", state["tasks"]["left"]["error"])
        self.assertFalse(workflow_state.launch_claim_path(run_dir, "left").exists())

    def test_native_failure_without_model_preserves_the_native_error(self) -> None:
        status, error = self.plugin._native_result_status(
            {
                "status": "failed",
                "exit_reason": "error",
                "summary": None,
                "error": "provider rejected the request",
            },
            {"model": "gpt-5.6-sol"},
        )
        self.assertEqual(status, "failed")
        self.assertEqual(error, "provider rejected the request")

    def test_native_success_without_model_uses_verified_launch_route(self) -> None:
        status, error = self.plugin._native_result_status(
            {
                "status": "completed",
                "exit_reason": "completed",
                "summary": "bounded output",
            },
            {"model": "gpt-5.6-sol"},
        )
        self.assertEqual(status, "succeeded")
        self.assertEqual(error, "")

    def test_partial_launch_failure_keeps_finalizer_batch_indexes(self) -> None:
        workflow_state = self.plugin._workflow_state_module()
        run_dir = self.plugin._initialize_workflow(
            self.workflow_plan(), Path(self.temp.name) / "partial-runs", {}
        )
        finalized = []

        def build(**kwargs):
            if kwargs["task_index"] == 0:
                raise RuntimeError("left construction failed")
            child = types.SimpleNamespace(
                provider="openai-codex",
                model=kwargs["model"],
                reasoning_config={},
                _session_init_model_config={},
                _primary_runtime={},
                _fallback_chain=[],
                _delegate_role="leaf",
                _subagent_id="sa-right",
                closed=False,
            )
            child.close = lambda: setattr(child, "closed", True)
            return child

        def run(**kwargs):
            kwargs["child"].close()
            return {
                "task_index": kwargs["task_index"],
                "status": "completed",
                "exit_reason": "completed",
                "summary": "right survived",
                "model": kwargs["child"].model,
                "_child_role": "leaf",
                "_child_cost_usd": 0.0,
            }

        def finalize(results, task_list, native_children, parent):
            finalized.append((results[0]["task_index"], task_list[1]["id"]))

        runtime = {
            "build": build,
            "run": run,
            "finalize": finalize,
            "get_max_children": lambda: 8,
            "load_config": lambda: {"max_iterations": 40},
        }
        parent = types.SimpleNamespace(
            provider="openai-codex", _delegate_depth=0, _interrupt_requested=False
        )
        hermes_constants = types.ModuleType("hermes_constants")
        hermes_constants.parse_reasoning_effort = lambda value: {"effort": value}
        with mock.patch.dict(sys.modules, {"hermes_constants": hermes_constants}):
            result = self.plugin._run_workflow(run_dir, parent, runtime, owner_kwargs={})
        self.assertFalse(result["success"])
        self.assertEqual(finalized, [(1, "right")])
        state = workflow_state.load_json(run_dir / "state.json")
        self.assertEqual(state["tasks"]["left"]["status"], "failed")
        self.assertEqual(state["tasks"]["right"]["status"], "succeeded")
        self.assertEqual(state["tasks"]["synthesize"]["status"], "blocked")

    def test_claim_contention_does_not_discard_started_child_result(self) -> None:
        workflow_state = self.plugin._workflow_state_module()
        run_dir = self.plugin._initialize_workflow(
            self.workflow_plan(), Path(self.temp.name) / "contended-runs", {}
        )
        plan, _state = workflow_state.load_run(run_dir)
        children = []

        def build(**kwargs):
            child = types.SimpleNamespace(
                provider="openai-codex",
                model=kwargs["model"],
                reasoning_config={},
                _session_init_model_config={},
                _primary_runtime={},
                _fallback_chain=[],
                _delegate_role="leaf",
                _subagent_id=f"sa-{kwargs['task_index']}",
                closed=False,
            )
            child.close = lambda: setattr(child, "closed", True)
            children.append(child)
            return child

        def run(**kwargs):
            kwargs["child"].close()
            return {
                "task_index": kwargs["task_index"],
                "status": "completed",
                "exit_reason": "completed",
                "summary": "alpha survived contention",
                "model": kwargs["child"].model,
                "_child_role": "leaf",
                "_child_cost_usd": 0.0,
            }

        runtime = {
            "build": build,
            "run": run,
            "finalize": lambda *_args: None,
            "list_active": lambda: [],
        }
        original_claim = workflow_state.claim_task

        def contended_claim(target_run, task_id, trusted_manifest_sha256=None):
            if task_id == "right":
                raise workflow_state.PlanError("already claimed elsewhere")
            return original_claim(target_run, task_id, trusted_manifest_sha256)

        parent = types.SimpleNamespace(
            provider="openai-codex", _delegate_depth=0, _interrupt_requested=False
        )
        hermes_constants = types.ModuleType("hermes_constants")
        hermes_constants.parse_reasoning_effort = lambda value: {"effort": value}
        with (
            mock.patch.dict(sys.modules, {"hermes_constants": hermes_constants}),
            mock.patch.object(workflow_state, "claim_task", side_effect=contended_claim),
        ):
            result = self.plugin._run_workflow_wave(
                workflow_state,
                run_dir,
                plan,
                self.plugin._verify_workflow_binding(workflow_state, run_dir),
                ["left", "right"],
                parent,
                runtime,
                40,
                {},
            )

        state = workflow_state.load_json(run_dir / "state.json")
        self.assertEqual(result["completed"], 1)
        self.assertEqual(state["tasks"]["left"]["status"], "succeeded")
        self.assertEqual(state["tasks"]["right"]["status"], "pending")
        self.assertTrue(children[0].closed)

    def test_atomic_text_ignores_a_precreated_predictable_temp_hardlink(self) -> None:
        task_dir = Path(self.temp.name) / "atomic-hardlink" / "tasks" / "task"
        task_dir.mkdir(parents=True)
        output_path = task_dir / "output.md"
        victim = Path(self.temp.name) / "atomic-hardlink-victim.txt"
        victim.write_text("do not overwrite", encoding="utf-8")
        old_predictable_temp = output_path.with_suffix(
            f"{output_path.suffix}.{os.getpid()}.{threading.get_ident()}.tmp"
        )
        os.link(victim, old_predictable_temp)

        self.plugin._atomic_text(output_path, "safe output")

        self.assertEqual(victim.read_text(encoding="utf-8"), "do not overwrite")
        self.assertEqual(output_path.read_text(encoding="utf-8"), "safe output")
        self.assertEqual(
            old_predictable_temp.read_text(encoding="utf-8"), "do not overwrite"
        )

    def test_registry_absence_is_not_a_close_witness(self) -> None:
        run_dir = Path(self.temp.name) / "close-witness-run"
        (run_dir / "tasks" / "task").mkdir(parents=True)
        runtime = {"list_active": lambda: []}
        self.assertFalse(
            self.plugin._native_handle_is_closed(
                runtime, run_dir, "task", "sa-1", "claim-1"
            )
        )
        forged_local = {
            "schema_version": 1,
            "run_dir": self.plugin._workflow_run_key(run_dir)[0],
            "task_id": "task",
            "handle": "sa-1",
            "launch_token": "claim-1",
            "closed_at_unix": 1.0,
        }
        self.plugin._atomic_text(
            self.plugin._close_witness_path(run_dir, "task"),
            json.dumps(forged_local) + "\n",
        )
        self.assertFalse(
            self.plugin._native_handle_is_closed(
                runtime, run_dir, "task", "sa-1", "claim-1"
            ),
            "a run-local witness must not authorize retry",
        )
        child = types.SimpleNamespace(closed=False)
        child.close = lambda: setattr(child, "closed", True)
        self.plugin._install_close_witness(
            child, run_dir, "task", "sa-1", "claim-1"
        )
        child.close()
        self.assertTrue(child.closed)
        self.assertTrue(
            self.plugin._trusted_close_witness_path(
                run_dir, "task", "sa-1", "claim-1"
            ).is_file()
        )
        self.assertTrue(
            self.plugin._native_handle_is_closed(
                runtime, run_dir, "task", "sa-1", "claim-1"
            )
        )

    def test_deferred_close_blocks_retry_until_exact_witness_exists(self) -> None:
        workflow_state = self.plugin._workflow_state_module()
        run_dir = self.plugin._initialize_workflow(
            self.workflow_plan(), Path(self.temp.name) / "deferred-close-runs", {}
        )
        plan, _state = workflow_state.load_run(run_dir)
        children = []

        def build(**kwargs):
            child = types.SimpleNamespace(
                provider="openai-codex",
                model=kwargs["model"],
                reasoning_config={},
                _session_init_model_config={},
                _primary_runtime={},
                _fallback_chain=[],
                _delegate_role="leaf",
                _subagent_id="sa-deferred",
                closed=False,
            )
            child.close = lambda: setattr(child, "closed", True)
            children.append(child)
            return child

        def run(**kwargs):
            return {
                "task_index": kwargs["task_index"],
                "status": "failed",
                "exit_reason": "timeout",
                "summary": None,
                "error": "native child timed out before deferred close",
                "model": kwargs["child"].model,
                "_child_role": "leaf",
                "_child_cost_usd": 0.0,
            }

        runtime = {
            "build": build,
            "run": run,
            "finalize": lambda *_args: None,
            "list_active": lambda: [],
        }
        parent = types.SimpleNamespace(
            provider="openai-codex", _delegate_depth=0, _interrupt_requested=False
        )
        hermes_constants = types.ModuleType("hermes_constants")
        hermes_constants.parse_reasoning_effort = lambda value: {"effort": value}
        with mock.patch.dict(sys.modules, {"hermes_constants": hermes_constants}):
            result = self.plugin._run_workflow_wave(
                workflow_state,
                run_dir,
                plan,
                self.plugin._verify_workflow_binding(workflow_state, run_dir),
                ["left"],
                parent,
                runtime,
                40,
                {},
            )

        self.assertEqual(result["completed"], 1)
        self.assertIn("exact close witness", result["launch_errors"][0]["error"])
        state = workflow_state.load_json(run_dir / "state.json")
        self.assertEqual(state["tasks"]["left"]["status"], "running")
        self.assertFalse(state["tasks"]["left"]["handle_closed_at"])

        resume_runtime = dict(runtime, list_active=lambda: [])
        with mock.patch.object(self.plugin, "_private_runtime", return_value=resume_runtime):
            blocked = json.loads(
                self.plugin._workflow_handle({
                    "action": "resume",
                    "run_dir": str(run_dir),
                    "retry_interrupted": True,
                })
            )
        self.assertFalse(blocked["success"])
        self.assertIn("without exact native close witnesses", blocked["error"])

        children[0].close()
        self.assertTrue(children[0].closed)
        with mock.patch.object(self.plugin, "_private_runtime", return_value=resume_runtime):
            resumed = json.loads(
                self.plugin._workflow_handle({
                    "action": "resume",
                    "run_dir": str(run_dir),
                    "retry_interrupted": True,
                })
            )
        self.assertTrue(resumed["success"])
        state = workflow_state.load_json(run_dir / "state.json")
        self.assertEqual(state["tasks"]["left"]["status"], "pending")
        self.assertEqual(state["tasks"]["left"]["handle"], "")

    def test_stopped_attempt_without_close_witness_cannot_resume(self) -> None:
        workflow_state = self.plugin._workflow_state_module()
        run_dir = self.plugin._initialize_workflow(
            self.workflow_plan(), Path(self.temp.name) / "stopped-without-witness-runs", {}
        )
        token = workflow_state.claim_task(run_dir, "left")
        workflow_state.start_task(run_dir, "left", "sa-stopped", token)
        workflow_state.finish_task(
            run_dir,
            "left",
            "stopped",
            "",
            "",
            "interrupted",
            True,
            "sa-stopped",
            token,
        )
        runtime = {"list_active": lambda: []}
        with mock.patch.object(self.plugin, "_private_runtime", return_value=runtime):
            result = json.loads(
                self.plugin._workflow_handle({
                    "action": "resume",
                    "run_dir": str(run_dir),
                    "retry_interrupted": True,
                })
            )
        self.assertFalse(result["success"])
        self.assertIn("without exact native close witnesses", result["error"])

    def test_finalizer_failure_leaves_closed_task_recoverable(self) -> None:
        workflow_state = self.plugin._workflow_state_module()
        run_dir = self.plugin._initialize_workflow(
            self.workflow_plan(), Path(self.temp.name) / "finalizer-failure-runs", {}
        )
        plan, _state = workflow_state.load_run(run_dir)

        def build(**kwargs):
            child = types.SimpleNamespace(
                provider="openai-codex",
                model=kwargs["model"],
                reasoning_config={},
                _session_init_model_config={},
                _primary_runtime={},
                _fallback_chain=[],
                _delegate_role="leaf",
                _subagent_id="sa-finalizer",
                closed=False,
            )
            child.close = lambda: setattr(child, "closed", True)
            return child

        def run(**kwargs):
            kwargs["child"].close()
            return {
                "task_index": kwargs["task_index"],
                "status": "completed",
                "exit_reason": "completed",
                "summary": "completed before finalizer failure",
                "model": kwargs["child"].model,
                "_child_role": "leaf",
                "_child_cost_usd": 0.0,
            }

        runtime = {
            "build": build,
            "run": run,
            "finalize": mock.Mock(side_effect=RuntimeError("finalizer failed")),
            "list_active": lambda: [],
        }
        parent = types.SimpleNamespace(
            provider="openai-codex", _delegate_depth=0, _interrupt_requested=False
        )
        hermes_constants = types.ModuleType("hermes_constants")
        hermes_constants.parse_reasoning_effort = lambda value: {"effort": value}
        with (
            mock.patch.dict(sys.modules, {"hermes_constants": hermes_constants}),
            self.assertRaisesRegex(RuntimeError, "finalizer failed"),
        ):
            self.plugin._run_workflow_wave(
                workflow_state,
                run_dir,
                plan,
                self.plugin._verify_workflow_binding(workflow_state, run_dir),
                ["left"],
                parent,
                runtime,
                40,
                {},
            )

        state = workflow_state.load_json(run_dir / "state.json")
        self.assertEqual(state["tasks"]["left"]["status"], "running")
        witness = self.plugin._close_witness_path(run_dir, "left")
        self.assertTrue(witness.is_file())

        with mock.patch.object(self.plugin, "_private_runtime", return_value=runtime):
            resumed = json.loads(
                self.plugin._workflow_handle({
                    "action": "resume",
                    "run_dir": str(run_dir),
                    "retry_interrupted": True,
                })
            )
        self.assertTrue(resumed["success"])
        state = workflow_state.load_json(run_dir / "state.json")
        self.assertEqual(state["tasks"]["left"]["status"], "pending")

    def test_register_exposes_both_routed_tools(self) -> None:
        registered = []
        ctx = types.SimpleNamespace(
            register_tool=lambda **kwargs: registered.append(kwargs)
        )
        self.plugin.register(ctx)
        self.assertEqual(
            {entry["name"] for entry in registered},
            {"routed_delegate_task", "routed_workflow"},
        )


if __name__ == "__main__":
    unittest.main()
