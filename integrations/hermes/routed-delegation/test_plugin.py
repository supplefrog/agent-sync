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
REPO_ROOT = Path(__file__).resolve().parents[3]
ROUTE_SKILL = REPO_ROOT / "skills" / "openai-delegation-route-research"
DYNAMIC_WORKFLOWS_SKILL = REPO_ROOT / "skills" / "dynamic-workflows"


def load_plugin():
    spec = importlib.util.spec_from_file_location("routed_delegation_tested", PLUGIN)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_staged_workflow_state():
    path = DYNAMIC_WORKFLOWS_SKILL / "scripts" / "workflow_state.py"
    spec = importlib.util.spec_from_file_location("staged_workflow_state_tested", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.default_router_paths = lambda: (
        ROUTE_SKILL / "references" / "current-gpt-catalog.json",
        ROUTE_SKILL / "scripts" / "route_selector.py",
    )
    module.default_v3_router_paths = lambda: (
        ROUTE_SKILL / "references" / "current-task-route-catalog.json",
        ROUTE_SKILL / "scripts" / "route_selector.py",
        ROUTE_SKILL / "scripts" / "task_request.py",
    )
    return module


class RoutedDelegationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.plugin = load_plugin()
        self.workflow = load_staged_workflow_state()
        self.workflow_patcher = mock.patch.object(
            self.plugin, "_workflow_state_module", return_value=self.workflow
        )
        self.workflow_patcher.start()
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.home = self.root / "hermes"
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
        self.workflow_patcher.stop()
        logging_module = sys.modules.get("hermes_logging")
        reset_logging = getattr(logging_module, "_reset_queued_handlers", None)
        if callable(reset_logging):
            reset_logging()
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
        ), mock.patch.object(
            self.plugin, "__file__",
            str(REPO_ROOT / "integrations" / "hermes" / "routed-delegation" / "__init__.py"),
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
                "exit_reason": "completed",
                "_child_role": "leaf",
                "_child_cost_usd": 0.0,
            }

        def finalize(results, task_list, native_children, parent):
            finalized.append((results, task_list, native_children, parent))
            for result in results:
                result.pop("_child_role", None)
                result.pop("_child_cost_usd", None)

        parent = types.SimpleNamespace(_interrupt_requested=False)
        for item in prepared:
            self.plugin._own_child(item[3], parent)
        results = self.plugin._execute_children(
            prepared,
            parent,
            run,
            finalize,
            max_children=2,
            owner_kwargs={},
        )
        self.assertEqual([item["summary"] for item in results], ["parent-context"] * 2)
        self.assertEqual(len(finalized), 2)
        self.assertNotIn("_child_role", results[0])  # native bounded response projection
        self.assertIn("_child_role", prepared[0][3]._routed_raw_result)

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


    def test_native_request_contract_rejects_changed_wire_route(self) -> None:
        route = {"provider": "openai-codex", "model": "gpt-6-astra", "reasoning_effort": "xhigh"}
        child = types.SimpleNamespace(provider="openai-codex", api_mode="codex_responses", base_url="https://chatgpt.com/backend-api/codex")
        self.plugin._assert_native_request_kwargs(child, route, {"model": "gpt-6-astra", "reasoning": {"effort": "xhigh"}})
        for kwargs in [{"model": "gpt-6-astra", "reasoning": {"effort": "high"}}, {"model": "other", "reasoning": {"effort": "xhigh"}}, {"model": "gpt-6-astra", "reasoning": {"effort": "xhigh"}, "extra_body": {"model": "other"}}]:
            with self.assertRaises(RuntimeError):
                self.plugin._assert_native_request_kwargs(child, route, kwargs)

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
        self.assertEqual(sorted(finalized[:2]), [[0], [1]])
        self.assertEqual(finalized[2:], [[0]])
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
            kwargs['child'].close()  # current native runner owns close, not finalizer
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
        self.assertFalse(resumed["success"])
        state = workflow_state.load_json(run_dir / "state.json")
        self.assertEqual(state["tasks"]["left"]["status"], "running")
        self.assertEqual(state["tasks"]["left"]["handle"], "sa-deferred")

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

    def test_finalizer_failure_preserves_completed_execution_without_replay(self) -> None:
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
        self.assertEqual(state["tasks"]["left"]["status"], "succeeded")
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
        self.assertEqual(state["tasks"]["left"]["status"], "succeeded")
        self.assertEqual(resumed["finalization_pending"], ["left"])
        runtime["finalize"].assert_called_once()

    def _v3_workflow_template(self, kind: str) -> dict:
        deterministic = None
        effects = "none"
        parent_available = True
        if kind == "deterministic":
            deterministic = {
                "executor_id": "fixture-parent-check", "artifact_sha256": "e" * 64,
                "task_contract_sha256": "c" * 64, "coverage": "complete", "effects": "none",
            }
        elif kind == "parent":
            effects = "irreversible"
        elif kind == "defer":
            effects = "irreversible"
            parent_available = False
        result = {
            "schema_version": 3,
            "task_class": "workflow-fixture",
            "requirements": {"tools": [], "context_tokens": 128,
                "task_contract_sha256": "c" * 64, "model": None, "reasoning_effort": None},
            "verifier": {"kind": "deterministic", "independent": True, "coverage": "complete",
                "scope": "inline-text", "evidence": {"locator": "fixture:verifier", "sha256": "b" * 64}},
            "effects": effects, "failure_cost": "low", "deterministic": deterministic,
            "budget": {"objective": "quota", "api_remaining": None, "api_reserve": 0,
                "allow_api_spend": False,
                "quotas": {"codex-main": {"unit": "percentage-points", "remaining": 100, "reserve": 0}},
                "unknown_cost_policy": "keep_parent", "preference_order": [],
                "parent_available": parent_available, "attempt_cap": 1, "attempts_used": 0,
                "fallback_route_id": None, "fallback_route_sha256": None},
        }
        if kind == "model":
            result["budget"]["unknown_cost_policy"] = "explicit_preference"
            result["budget"]["preference_order"] = ["synthetic-workflow-model"]
        return result

    def _install_synthetic_workflow_catalog(self) -> tuple[Path, dict]:
        canonical = json.loads(
            (ROUTE_SKILL / "references" / "current-task-route-catalog.json").read_text(encoding="utf-8")
        )
        candidate = canonical["candidates"][0]
        contract = self.plugin._v3_native_contract()
        route = candidate["route"]
        route.update(
            transport="hermes-workflow", runtime=contract["runtime"],
            contract_sha256=self.plugin._sha(contract),
        )
        candidate["id"] = "synthetic-workflow-model"
        candidate["availability"]["route_sha256"] = self.plugin._sha(route)
        candidate["availability"]["valid_until"] = "2099-01-01T00:00:00Z"
        candidate["quality"] = []
        candidate["cost"] = {
            "billing": "subscription", "basis": "unknown",
            "task_contract_sha256": None, "verifier_sha256": None, "route_sha256": None,
            "api_usd": {"generation": None, "verification": None, "fallback": None},
            "quota": {"bucket": "codex-main", "unit": "percentage-points",
                      "parts": {"generation": None, "verification": None, "fallback": None}},
            "evidence": None,
        }
        canonical["catalog_version"] = "synthetic-workflow-test-only"
        path = self.root / "synthetic-workflow-catalog.json"
        path.write_text(json.dumps(canonical), encoding="utf-8")
        selector = ROUTE_SKILL / "scripts" / "route_selector.py"
        materializer = ROUTE_SKILL / "scripts" / "task_request.py"
        self.workflow.default_v3_router_paths = lambda: (path, selector, materializer)
        return path, route

    def _write_v3_workflow(self, tasks: list[dict], name: str) -> Path:
        path = self.root / f"{name}.json"
        path.write_text(json.dumps({"name": name, "tasks": tasks}), encoding="utf-8")
        return path

    def test_workflow_v3_nonmodel_handoffs_do_not_construct_or_loop(self) -> None:
        tasks = [
            {"id": kind, "role": "worker", "risk": "read", "acceptance": [f"parent checks {kind}"],
             "prompt": kind, "route_request": self._v3_workflow_template(kind)}
            for kind in ("parent", "deterministic", "defer")
        ]
        run_dir = self.plugin._initialize_workflow(
            self._write_v3_workflow(tasks, "nonmodel-v3"), self.root / "runs-v3", {}
        )
        manifest = self.workflow.load_json(run_dir / "run_manifest.json")
        self.assertEqual(manifest["schema_version"], 3)
        trusted = self.plugin._verify_workflow_binding(self.workflow, run_dir)
        self.assertEqual(trusted, self.plugin._sha(manifest))
        parent = types.SimpleNamespace(_delegate_depth=0, _interrupt_requested=False)
        runtime = {"load_config": lambda: {"max_iterations": 5}, "default_iterations": 5,
                   "get_max_children": lambda: 2}
        with mock.patch.object(self.plugin, "_prepare_workflow_child", side_effect=AssertionError("must not construct")):
            first = self.plugin._run_workflow(run_dir, parent, runtime, owner_kwargs={})
            second = self.plugin._run_workflow(run_dir, parent, runtime, owner_kwargs={})
        self.assertEqual([item["kind"] for item in first["parent_actions"]], ["parent", "deterministic", "defer"])
        self.assertEqual(second["waves"], [])
        self.assertEqual([item["kind"] for item in second["parent_actions"]], ["parent", "deterministic", "defer"])

    def test_workflow_v3_truthful_parent_completion_releases_dependency(self) -> None:
        tasks = [
            {"id": "parent", "role": "worker", "risk": "read", "acceptance": ["parent checks root"],
             "prompt": "root", "route_request": self._v3_workflow_template("parent")},
            {"id": "child", "role": "worker", "risk": "read", "acceptance": ["parent checks child"],
             "prompt": "use {{output:parent}}", "depends_on": ["parent"], "include_outputs": ["parent"],
             "route_request": self._v3_workflow_template("parent")},
        ]
        run_dir = self.plugin._initialize_workflow(
            self._write_v3_workflow(tasks, "dependent-v3"), self.root / "runs-dependent", {}
        )
        parent = types.SimpleNamespace(_delegate_depth=0, _interrupt_requested=False)
        runtime = {"load_config": lambda: {"max_iterations": 5}, "default_iterations": 5,
                   "get_max_children": lambda: 1}
        first = self.plugin._run_workflow(run_dir, parent, runtime, owner_kwargs={})
        self.assertEqual([item["task_id"] for item in first["parent_actions"]], ["parent"])
        output = self.root / "parent-output.md"
        output.write_text("parent-produced evidence", encoding="utf-8")
        trusted = self.plugin._verify_workflow_binding(self.workflow, run_dir)
        from agent.subagent_lifecycle import bind_subagent_parent
        with bind_subagent_parent(parent):
            completed = json.loads(self.plugin._workflow_handle({
                "action": "complete-parent", "run_dir": str(run_dir), "task_id": "parent",
                "output_path": str(output), "summary": "parent actually completed work",
            }))
        self.assertTrue(completed["success"], completed)
        state = self.workflow.load_json(run_dir / "state.json")
        self.assertEqual(state["tasks"]["parent"]["handle"], "parent-sequential:parent")
        self.assertTrue(state["tasks"]["parent"]["launch_token"])
        self.assertEqual(self.workflow.ready_tasks(run_dir, trusted), ["child"])
        second = self.plugin._run_workflow(run_dir, parent, runtime, owner_kwargs={})
        self.assertEqual([item["task_id"] for item in second["parent_actions"]], ["child"])

    def test_workflow_v3_parent_envelope_mutation_rejects_before_child_construction(self) -> None:
        self._install_synthetic_workflow_catalog()
        task = {"id": "model", "role": "worker", "risk": "read", "acceptance": ["checked"],
                "prompt": "model", "route_request": self._v3_workflow_template("model")}
        run_dir = self.plugin._initialize_workflow(
            self._write_v3_workflow([task], "mutated-parent-v3"), self.root / "runs-mutated", {}
        )
        parent = types.SimpleNamespace(_delegate_depth=0, _interrupt_requested=False)
        runtime = {"load_config": lambda: {"max_iterations": 5}, "default_iterations": 5,
                   "get_max_children": lambda: 1, "build": object(), "validate_request": None,
                   "budget_summary": None, "finalize": lambda *_a, **_k: None, "detach": None}
        with mock.patch.object(
            self.plugin, "_v3_native_envelope", side_effect=[{"profile": "before"}, {"profile": "changed"}]
        ), mock.patch.object(
            self.plugin, "_prepare_workflow_child", side_effect=AssertionError("must not construct")
        ):
            result = self.plugin._run_workflow(run_dir, parent, runtime, owner_kwargs={})
        self.assertEqual(result["waves"][0]["launch_errors"][0]["task_id"], "model")
        self.assertIn("execution context changed", result["waves"][0]["launch_errors"][0]["error"])

    def test_workflow_v3_synthetic_model_uses_actual_native_child_and_intercepted_run(self) -> None:
        _catalog_path, route = self._install_synthetic_workflow_catalog()
        task = {"id": "model", "role": "worker", "risk": "read", "acceptance": ["parent checks result"],
                "prompt": "offline model preparation", "route_request": self._v3_workflow_template("model")}
        run_dir = self.plugin._initialize_workflow(
            self._write_v3_workflow([task], "native-model-v3"), self.root / "runs-native", {}
        )
        self.home.mkdir(parents=True, exist_ok=True)
        (self.home / "config.yaml").write_text(
            "delegation:\n  max_iterations: 2\n  max_concurrent_children: 1\n"
            "  max_spawn_depth: 1\n  orchestrator_enabled: false\n  max_summary_chars: 24000\n",
            encoding="utf-8",
        )
        actual = self.plugin._private_runtime()
        holder = {"build": 0, "intercept": 0, "provider": 0}
        native_build = actual["build"]

        def build(**kwargs):
            holder["build"] += 1
            child = native_build(**kwargs)
            holder["child"] = child
            child.skip_context_files = True
            child.load_soul_identity = False
            child.skip_background_review = True
            child.save_trajectories = False
            from agent.system_prompt import invalidate_system_prompt
            invalidate_system_prompt(child)
            return child

        def intercept(**kwargs):
            holder["intercept"] += 1
            child = kwargs["child"]
            built = child._build_api_kwargs(
                [{"role": "user", "content": "offline model preparation"}], []
            )
            self.assertEqual(built.get("model"), route["model"])
            self.assertEqual((built.get("reasoning") or {}).get("effort"), route["reasoning_effort"])
            child.close()
            actual["detach"](kwargs["parent_agent"], child)
            return {
                "task_index": kwargs["task_index"], "status": "completed",
                "exit_reason": "completed", "summary": "offline intercepted result",
                "model": route["model"], "api_calls": 0, "duration_seconds": 0,
                "execution_outcome": "completed", "closure_confirmed": True,
                "_child_role": "leaf", "_child_cost_usd": 0.0,
            }

        runtime = {**actual, "build": build, "run": intercept}
        parent = types.SimpleNamespace(
            provider=route["provider"], model=route["model"], api_mode="codex_responses",
            base_url="https://chatgpt.com/backend-api/codex", api_key="synthetic-offline-token",
            reasoning_config={"enabled": True, "effort": route["reasoning_effort"]},
            session_id="workflow-native-parent", _current_turn_id="offline-turn",
            _current_task_id=None, _delegate_depth=0, _interrupt_requested=False,
            enabled_toolsets=["none"], disabled_toolsets=[], request_overrides={},
            prefill_messages=None, _session_db=None, _credential_pool=None, _memory_manager=None,
            session_prompt_tokens=0, session_completion_tokens=0, session_reasoning_tokens=0,
            session_estimated_cost_usd=0.0, context_compressor=None,
            _print_fn=lambda *_args, **_kwargs: None,
        )
        from tools import delegate_tool, delegate_tool_progress
        old_delegate_hint = delegate_tool._resolve_workspace_hint
        old_progress_hint = delegate_tool_progress._resolve_workspace_hint
        delegate_tool._resolve_workspace_hint = lambda _parent: None
        delegate_tool_progress._resolve_workspace_hint = lambda _parent: None
        try:
            result = self.plugin._run_workflow(
                run_dir, parent, runtime, owner_kwargs=self.plugin._workflow_owner_kwargs(runtime)
            )
        finally:
            delegate_tool._resolve_workspace_hint = old_delegate_hint
            delegate_tool_progress._resolve_workspace_hint = old_progress_hint
        self.assertTrue(result["success"], result)
        self.assertEqual(holder["build"], 1)
        self.assertEqual(holder["intercept"], 1)
        self.assertEqual(holder["provider"], 0)
        self.assertTrue(getattr(holder["child"], "_routed_closed", False))
        state = self.workflow.load_json(run_dir / "state.json")
        current = state["tasks"]["model"]
        self.assertEqual(current["status"], "succeeded")
        self.assertEqual(current["summary"], "offline intercepted result")
        self.assertTrue(current["launch_token"])
        self.assertTrue(current["handle_closed_at"])
        record = json.loads((run_dir / "tasks" / "model" / "result.json").read_text(encoding="utf-8"))
        self.assertEqual(record["native_result"]["summary"], "offline intercepted result")
        self.assertEqual(Path(current["output_path"]).read_text(encoding="utf-8"), "offline intercepted result")
        self.assertEqual(result["finalization_pending"], [])
        self.assertEqual(list(self.root.rglob("auth.json")), [])

    def test_current_native_adapter_shares_budget_and_accounts_once(self) -> None:
        from hermes_cli import plugins

        from tools import delegate_tool_results as native
        runtime = self.plugin._private_runtime()
        parent = types.SimpleNamespace(
            session_id="adapter-parent", _current_turn_id="turn",
            context_compressor=types.SimpleNamespace(context_length=20000, max_tokens=1000),
            _last_prompt_size_tokens=11000, session_estimated_cost_usd=1.0,
            _memory_manager=mock.Mock(),
        )
        children, raw = [], []
        for index in range(4):
            child = types.SimpleNamespace(session_id=f"child-{index}")
            self.plugin._own_child(child, parent)
            child._routed_summary_count = 4
            child._routed_budget_summary = runtime["budget_summary"]
            children.append(child)
            raw.append({"task_index": index, "summary": (f"evidence-{index}\n" * 3000),
                        "status": "completed", "exit_reason": "completed",
                        "_child_cost_usd": 0.25, "_child_role": "leaf"})
        expected = json.loads(json.dumps(raw))
        # Native batch output is the oracle. Only the filesystem boundary is
        # intercepted, leaving native cap, trim, accounting and hooks real.
        with mock.patch.object(native, "_spill_summary_to_file", return_value=None), \
             mock.patch.object(plugins, "invoke_hook") as hooks:
            native._apply_summary_budget(expected, parent)
            for index, child in enumerate(children):
                item = (index, {"goal": f"goal-{index}"}, {}, child)
                self.plugin._schedule_finalization(runtime["finalize"], parent, item, raw[index])
                self.assertTrue(child._routed_accounting_done.wait(5))
                self.plugin._schedule_finalization(runtime["finalize"], parent, item, raw[index])
                self.assertEqual(child._routed_accounting["status"], "returned")
                self.assertEqual(child._routed_display_result["summary"], expected[index]["summary"])
                self.assertEqual(child._routed_finalized_result["summary"], expected[index]["summary"])
                self.assertNotIn("_child_cost_usd", child._routed_finalized_result)
                self.assertEqual(raw[index]["summary"], f"evidence-{index}\n" * 3000)
            self.assertEqual(hooks.call_count, 4)
        self.assertEqual(parent._memory_manager.on_delegation.call_count, 4)
        self.assertEqual(parent.session_estimated_cost_usd, 2.0)
        self.assertEqual([call.kwargs["result"] for call in
                          parent._memory_manager.on_delegation.call_args_list],
                         [entry["summary"] for entry in expected])

    def test_legacy_adapter_rejects_unknown_native_finalization_body(self) -> None:
        from tools import delegate_tool_results as native
        def changed(results, task_list, children, parent_agent):
            raise AssertionError("new native obligation must not be silently omitted")
        with self.assertRaisesRegex(RuntimeError, "finalization.*unsupported"):
            self.plugin._summary_runtime_adapter(changed, native)

    def test_native_spawn_requires_router_but_controls_remain_available(self) -> None:
        registered_hooks = {}
        ctx = types.SimpleNamespace(
            register_tool=lambda **kwargs: None,
            register_hook=lambda name, callback: registered_hooks.update({name: callback}),
        )
        self.plugin.register(ctx)
        self.assertIn("pre_tool_call", registered_hooks)
        gate = registered_hooks["pre_tool_call"]
        for args in ({}, {"tasks": [{"goal": "Review code"}]},
                     {"action": "spawn"}, {"action": "unknown"}, {"action": []}):
            with self.subTest(args=args):
                decision = gate(tool_name="delegate_task", args=args)
                self.assertEqual(decision["action"], "block")
                self.assertIn("routed_delegate_task", decision["message"])
        for action in ("list", "steer", "stop"):
            self.assertIsNone(gate(tool_name="delegate_task", args={"action": action}))
        for name in ("routed_delegate_task", "routed_workflow", "terminal", "memory"):
            self.assertIsNone(gate(tool_name=name, args={}))

    def test_register_exposes_both_routed_tools(self) -> None:
        registered = []
        ctx = types.SimpleNamespace(
            register_tool=lambda **kwargs: registered.append(kwargs),
            register_hook=lambda *args: None,
        )
        self.plugin.register(ctx)
        self.assertEqual(
            {entry["name"] for entry in registered},
            {"routed_delegate_task", "routed_workflow"},
        )
        workflow = next(entry for entry in registered if entry["name"] == "routed_workflow")
        self.assertIn("complete-parent", workflow["schema"]["parameters"]["properties"]["action"]["enum"])


if __name__ == "__main__":
    unittest.main()
