from __future__ import annotations

import importlib.util
import contextvars
import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

PLUGIN = Path(__file__).with_name("__init__.py")
ROUTE_SKILL = Path(__file__).resolve().parents[3] / "skills" / "openai-delegation-route-research"


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
        helper = "return transport(reasoning_config=agent.reasoning_config)"
        transport = (
            'reasoning_config = params.get("reasoning_config")\n'
            'reasoning_effort = reasoning_config["effort"]'
        )
        self.assertTrue(self.plugin._reasoning_source_contract(helper, transport))
        self.assertFalse(
            self.plugin._reasoning_source_contract(
                "return transport(reasoning_config=None)", transport
            )
        )


if __name__ == "__main__":
    unittest.main()
