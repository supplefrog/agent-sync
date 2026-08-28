from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

import jsonschema

REPO = Path(__file__).resolve().parents[1]
SELECTOR_PATH = REPO / "skills" / "openai-delegation-route-research" / "scripts" / "route_selector.py"
ADAPTER_PATH = REPO / "tools" / "route_adapter.py"
REFERENCES = REPO / "skills" / "openai-delegation-route-research" / "references"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


def candidate(route_id, model, effort, intelligence, task_time, cost, hallucination):
    return {
        "id": route_id,
        "model": model,
        "reasoning_effort": effort,
        "artificial_analysis": {
            "intelligence_index": intelligence,
            "time_per_task_minutes": task_time,
            "cost_per_task_usd": cost,
            "hallucination_rate_percent": hallucination,
        },
    }


def catalog(*routes):
    return {
        "schema_version": 2,
        "status": "active",
        "catalog_version": "automatic-frontier-test-v1",
        "provider": "openai-codex",
        "source": {
            "name": "Artificial Analysis",
            "url": "https://artificialanalysis.ai/models",
            "observed_at": "2026-08-24",
            "metrics": {
                "intelligence": "Artificial Analysis Intelligence Index",
                "time": "Time per Intelligence Index Task (minutes)",
                "cost": "Cost per Intelligence Index Task (USD)",
                "hallucination": "AA-Omniscience Hallucination Rate (%)",
            },
        },
        "intelligence_tiers": {
            "routine": {"minimum_intelligence_index": 39, "description": "Bounded routine work"},
            "standard": {"minimum_intelligence_index": 47, "description": "Normal professional work"},
            "strong": {"minimum_intelligence_index": 51, "description": "Substantial judgment"},
            "demanding": {"minimum_intelligence_index": 56, "description": "Hard reasoning"},
            "maximum": {"minimum_intelligence_index": 61, "description": "Quality ceiling"},
        },
        "delegation_candidates": list(routes),
        "recommendations": [
            {
                "name": "automatic-default",
                "route_id": routes[0]["id"],
                "use_when": "Automatic selector smoke fixture",
                "why": "Fixture only",
            }
        ],
    }


def frontier_catalog():
    return catalog(
        candidate("luna-medium", "gpt-5.6-luna", "medium", 39, 0.48, 0.01, 90.87),
        candidate("luna-high", "gpt-5.6-luna", "high", 47, 1.04, 0.02, 92.38),
        candidate("luna-xhigh", "gpt-5.6-luna", "xhigh", 50, 1.65, 0.03, 92.47),
        candidate("luna-max", "gpt-5.6-luna", "max", 52, 2.53, 0.05, 92.58),
        candidate("sol-low", "gpt-5.6-sol", "low", 51, 0.68, 0.23, 89.42),
        candidate("sol-medium", "gpt-5.6-sol", "medium", 56, 1.13, 0.37, 90.77),
        candidate("sol-high", "gpt-5.6-sol", "high", 57, 1.81, 0.55, 91.20),
        candidate("sol-xhigh", "gpt-5.6-sol", "xhigh", 59, 2.71, 0.81, 91.87),
        candidate("sol-max", "gpt-5.6-sol", "max", 61, 3.80, 1.23, 92.20),
    )


def task(tier="routine", latency_sensitive=False, **overrides):
    result = {
        "target_surface": "hermes-task-thread",
        "intelligence_tier": tier,
        "latency_sensitive": latency_sensitive,
    }
    result.update(overrides)
    return result


class AutomaticFrontierRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.selector = load_module("route_selector", SELECTOR_PATH)
        cls.adapter = load_module("route_adapter", ADAPTER_PATH)

    def test_cost_is_default_after_intelligence_floor(self):
        routes = frontier_catalog()
        expected = {
            "routine": "luna-medium",
            "standard": "luna-high",
            "strong": "luna-max",
            "demanding": "sol-medium",
            "maximum": "sol-max",
        }
        for tier, route_id in expected.items():
            with self.subTest(tier=tier):
                receipt = self.selector.select_route(routes, task(tier))
                self.assertEqual(receipt["route"]["id"], route_id)
                self.assertEqual(receipt["constraints_applied"]["selection_priority"], "cost")

    def test_latency_sensitive_chooses_fastest_route_meeting_floor(self):
        receipt = self.selector.select_route(frontier_catalog(), task("standard", True))
        self.assertEqual(receipt["route"]["id"], "sol-low")
        self.assertEqual(receipt["constraints_applied"]["selection_priority"], "speed")

    def test_higher_intelligence_does_not_win_when_cheaper_route_meets_floor(self):
        receipt = self.selector.select_route(frontier_catalog(), task("strong"))
        self.assertEqual(receipt["route"]["id"], "luna-max")
        self.assertLess(receipt["metrics"]["artificial_analysis_cost_per_task_usd"], 0.23)

    def test_manual_override_is_escape_hatch_but_cannot_violate_floor(self):
        routes = frontier_catalog()
        selected = self.selector.select_route(
            routes,
            task("standard", selected_route_id="sol-medium", selection_reason="Explicit operator override"),
        )
        self.assertEqual(selected["route"]["id"], "sol-medium")
        self.assertEqual(selected["constraints_applied"]["selection_mode"], "manual-override")

        denied = self.selector.decide_route(
            routes,
            task("maximum", selected_route_id="luna-medium", selection_reason="Too weak"),
        )
        self.assertEqual(denied["outcome"], "fail_closed")
        self.assertIn("below_intelligence_floor", denied["excluded"]["luna-medium"])

    def test_unknown_tier_and_incomplete_override_fail_validation(self):
        with self.assertRaisesRegex(self.selector.RouteSelectionError, "intelligence_tier"):
            self.selector.decide_route(frontier_catalog(), task("unknown"))
        with self.assertRaisesRegex(self.selector.RouteSelectionError, "selection_reason"):
            self.selector.decide_route(
                frontier_catalog(), task("routine", selected_route_id="luna-medium")
            )

    def test_tiers_must_be_monotonic_and_reachable(self):
        routes = frontier_catalog()
        routes["intelligence_tiers"]["standard"]["minimum_intelligence_index"] = 30
        with self.assertRaisesRegex(self.selector.RouteSelectionError, "strictly increasing"):
            self.selector.validate_catalog(routes)

        routes = frontier_catalog()
        routes["intelligence_tiers"]["maximum"]["minimum_intelligence_index"] = 99
        with self.assertRaisesRegex(self.selector.RouteSelectionError, "no eligible route"):
            self.selector.validate_catalog(routes)

    def test_receipt_is_stable_hash_bound_and_adapter_compatible(self):
        routes = frontier_catalog()
        request = task(
            "demanding",
            task_id="task-1",
            task_class="implementation-debugging",
            failure_cost="high",
            verifier_plan={"kind": "independent"},
        )
        first = self.selector.select_route(routes, request, catalog_locator="catalog.json")
        second = self.selector.select_route(routes, request, catalog_locator="catalog.json")
        self.assertEqual(first, second)
        self.assertEqual(first["route"]["id"], "sol-medium")
        self.assertEqual(first["policy_sha256"], self.selector.digest(routes))
        self.assertEqual(first["requirement_sha256"], self.selector.digest(first["constraints_applied"]))
        schema = json.loads((REFERENCES / "route-decision.schema.json").read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator(schema).validate(first)
        mapped = self.adapter.native_mapping(first, "hermes-task-thread", prompt="return PASS")
        self.assertEqual(mapped["fields"]["model"] if "fields" in mapped else mapped["route"]["model"], "gpt-5.6-sol")

    def test_workflow_surfaces_bind_receipts_to_the_executing_host(self):
        expected_hosts = {
            "codex-workflow": "codex",
            "omp-workflow": "omp",
        }
        for surface, host in expected_hosts.items():
            with self.subTest(surface=surface):
                receipt = self.selector.select_route(
                    frontier_catalog(),
                    task("demanding", target_surface=surface, task_id="workflow-task"),
                )
                self.assertEqual(receipt["route"]["runtime"]["host"], host)
                self.assertEqual(receipt["route"]["runtime"]["transport"], surface)
                schema = json.loads((REFERENCES / "route-decision.schema.json").read_text(encoding="utf-8"))
                jsonschema.Draft202012Validator(schema).validate(receipt)

    def test_current_catalog_task_and_aux_files_validate(self):
        catalog_schema = json.loads((REFERENCES / "gpt-route-catalog.schema.json").read_text(encoding="utf-8"))
        task_schema = json.loads((REFERENCES / "route-task.schema.json").read_text(encoding="utf-8"))
        aux_schema = json.loads((REFERENCES / "aux-models.schema.json").read_text(encoding="utf-8"))
        current = json.loads((REFERENCES / "current-gpt-catalog.json").read_text(encoding="utf-8"))
        aux = json.loads((REFERENCES / "current-aux-models.json").read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator(catalog_schema).validate(current)
        jsonschema.Draft202012Validator(task_schema).validate(task())
        jsonschema.Draft202012Validator(aux_schema).validate(aux)

    def test_auxiliary_automatic_assignments_reproduce_from_same_policy(self):
        current = json.loads((REFERENCES / "current-gpt-catalog.json").read_text(encoding="utf-8"))
        aux = json.loads((REFERENCES / "current-aux-models.json").read_text(encoding="utf-8"))
        automatic = [item for item in aux["assignments"] if item["decision"] == "automatic-selected"]
        self.assertTrue(automatic, "expected at least one automatically selected auxiliary assignment")
        for item in automatic:
            with self.subTest(purpose=item["purpose"]):
                receipt = self.selector.select_route(
                    current,
                    task(
                        item["intelligence_tier"],
                        item["latency_sensitive"],
                        target_surface="hermes-auxiliary",
                        task_id=f"aux:{item['purpose']}",
                    ),
                )
                self.assertEqual(receipt["route"]["id"], item["selector_route_id"])
                self.assertEqual(receipt["route"]["model"], item["model"])
                self.assertEqual(receipt["route"]["reasoning_effort"], item["reasoning_effort"])

    def test_cli_selects_automatically(self):
        routes = frontier_catalog()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            catalog_path = root / "catalog.json"
            task_path = root / "task.json"
            out_path = root / "receipt.json"
            catalog_path.write_text(json.dumps(routes), encoding="utf-8")
            task_path.write_text(json.dumps(task("standard", True)), encoding="utf-8")
            self.assertEqual(self.selector.main(["validate", "--catalog", str(catalog_path)]), 0)
            rc = self.selector.main(
                ["select", "--catalog", str(catalog_path), "--task", str(task_path), "--out", str(out_path)]
            )
            decision = json.loads(out_path.read_text(encoding="utf-8"))
            self.assertEqual(rc, 0)
            self.assertEqual(decision["route"]["id"], "sol-low")


if __name__ == "__main__":
    unittest.main()
