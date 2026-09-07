"""Synthetic policy tests; no live pricing, quality scores, or model calls."""
from __future__ import annotations

import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT if (ROOT / "tools/route_adapter.py").is_file() else ROOT.parents[1] / "agent-signal"
REL = Path("skills/openai-delegation-route-research")


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


router = load("candidate_task_router", ROOT / REL / "scripts/route_selector.py")
legacy = load("frozen_legacy_router", STAGE / REL / "scripts/selector-history/fcac25bdde0895b46239b7deec662e0711ad63f04a3cb39195ffd5814e2f306c.py")
legacy_tests = load("legacy_route_tests", STAGE / "tests/test_route_selector.py")


def ref(label):
    return {"locator": "synthetic:" + label, "sha256": router.digest(label)}


def request():
    return {"schema_version": 3, "task_id": "fixture-task", "task_class": "exact-extraction",
            "input_sha256": router.digest("fixture-input-1"),
            "as_of": "2026-09-06T12:00:00Z", "requirements": {"host": "codex", "transport": "fixture-native-cli",
                "tools": [], "context_tokens": 100, "task_contract_sha256": router.digest("exact-output-and-no-effects"),
                "model": None, "reasoning_effort": None},
            "verifier": {"kind": "deterministic", "independent": True, "coverage": "complete", "scope": "artifact-effects", "evidence": ref("verifier")},
            "effects": "none", "failure_cost": "low", "deterministic": None, "continuation": None,
            "budget": {"objective": "quota", "api_remaining": None, "api_reserve": 0, "allow_api_spend": False,
                "quotas": {"fixture-pool": {"unit": "fixture-units", "remaining": 100, "reserve": 0}},
                "unknown_cost_policy": "explicit_preference", "preference_order": ["older", "newer"],
                "parent_available": True, "attempt_cap": 2, "attempts_used": 0,
                "fallback_route_id": None, "fallback_route_sha256": None}}


def candidate(name="older", total=1, *, qualified=False):
    task = request()
    route = {"host": "codex", "transport": "fixture-native-cli", "provider": "fixture-provider", "model": "fixture-" + name,
             "reasoning_effort": "low", "runtime": "fixture-runtime", "contract_sha256": router.digest("fixture-runtime-contract")}
    value = {"id": name, "route": route,
             "availability": {"status": "verified", "observed_at": "2026-09-06T11:00:00Z", "valid_until": "2026-09-06T13:00:00Z",
                 "route_sha256": router.digest(route), "context_tokens": 1000, "tools_verified": [], "allowed_effects": ["none", "reversible"], "evidence": ref(name + "-available")},
             "quality": [], "benchmark_priors": [],
             "cost": {"billing": "subscription", "basis": "observed" if total is not None else "unknown",
                 "task_contract_sha256": task["requirements"]["task_contract_sha256"] if total is not None else None,
                 "verifier_sha256": task["verifier"]["evidence"]["sha256"] if total is not None else None,
                 "route_sha256": router.digest(route) if total is not None else None,
                 "api_usd": {"generation": None, "verification": None, "fallback": None},
                 "quota": {"bucket": "fixture-pool", "unit": "fixture-units", "parts": {"generation": total, "verification": 0 if total is not None else None, "fallback": 0 if total is not None else None}},
                 "evidence": ref(name + "-cost") if total is not None else None}}
    if qualified:
        value["quality"] = [{"task_class": task["task_class"], "task_contract_sha256": task["requirements"]["task_contract_sha256"],
                             "verifier_sha256": task["verifier"]["evidence"]["sha256"], "route_sha256": router.digest(route),
                             "status": "qualified", "scope": "artifact-effects", "evidence": ref(name + "-qualified")}]
    return value


def catalog(*items):
    return {"schema_version": 3, "catalog_version": "synthetic-v3", "candidates": list(items)}


class TaskRouterTests(unittest.TestCase):
    def test_complete_code_handler_never_becomes_model_dispatch(self):
        task = request()
        task["deterministic"] = {"executor_id": "fixture-extractor", "artifact_sha256": router.digest("script"),
                                 "input_sha256": task["input_sha256"],
                                 "task_contract_sha256": task["requirements"]["task_contract_sha256"], "coverage": "complete", "effects": "none"}
        with mock.patch("subprocess.Popen", side_effect=AssertionError("no model process")), mock.patch("socket.create_connection", side_effect=AssertionError("no network")):
            receipt = router.decide_route(catalog(candidate()), task)
            dispatch = router.dispatch_decision(receipt, catalog(candidate()), task)
        self.assertEqual(receipt["outcome"], "execute_deterministic")
        self.assertEqual(dispatch["kind"], "deterministic")
        self.assertIsNone(receipt["route"])

    def test_local_regression_beats_newer_generation_and_benchmark_prior(self):
        old, new = candidate(qualified=True), candidate("newer", .01, qualified=True)
        new["benchmark_priors"] = [{"source": "synthetic-category", "aggregate_index": 99999, "release_date": "2099-01-01"}]
        new["quality"][0]["status"] = "regression"
        receipt = router.decide_route(catalog(old, new), request())
        self.assertEqual(receipt["route_id"], "older")
        self.assertIn("local_task_regression", receipt["excluded"]["newer"])

    def test_prior_alone_is_not_local_judgment_qualification(self):
        task = request()
        task["failure_cost"] = "high"
        value = candidate()
        value["benchmark_priors"] = [{"category": "synthetic-review", "win_rate": .99}]
        self.assertEqual(router.decide_route(catalog(value), task)["outcome"], "keep_parent")

    def test_schema_only_or_incomplete_verifier_does_not_qualify(self):
        for change in ({"kind": "schema-only"}, {"coverage": "partial"}, {"independent": False}):
            task = request()
            task["verifier"].update(change)
            receipt = router.decide_route(catalog(candidate(qualified=True)), task)
            self.assertEqual(receipt["outcome"], "keep_parent")

    def test_low_risk_provisional_and_uncertain_variant_route_differently(self):
        task = request()
        self.assertEqual(router.decide_route(catalog(candidate()), task)["qualification"], "provisional-complete-verifier")
        for risk in ("medium", "high"):
            task["failure_cost"] = risk
            self.assertEqual(router.decide_route(catalog(candidate()), task)["outcome"], "keep_parent")

    def test_missing_cost_stays_null_and_never_claims_cheapest(self):
        value, task = candidate(total=None), request()
        receipt = router.decide_route(catalog(value), task)
        self.assertEqual(receipt["route_id"], "older")
        self.assertIsNone(receipt["cost_observation"]["total"])
        self.assertIn("no cheapest-route", receipt["resource_claim"])
        fabricated = copy.deepcopy(value)
        fabricated["cost"]["quota"]["parts"]["generation"] = 0
        with self.assertRaisesRegex(router.RouteSelectionError, "must be null"):
            router.decide_route(catalog(fabricated), task)
        task["budget"]["unknown_cost_policy"] = "defer"
        self.assertEqual(router.decide_route(catalog(value), task)["outcome"], "defer")

    def test_total_cost_includes_verification_and_fallback(self):
        old, new = candidate(total=.1), candidate("newer", 2)
        old["cost"]["quota"]["parts"].update(verification=1, fallback=1)
        self.assertEqual(router.decide_route(catalog(old, new), request())["route_id"], "newer")

    def test_bounded_failure_fallback_and_no_effort_ladder(self):
        old, new, task = candidate(), candidate("newer", 2), request()
        task["budget"].update(fallback_route_id="newer", fallback_route_sha256=router.digest(new["route"]))
        first = router.decide_route(catalog(old, new), task)
        retry = copy.deepcopy(task)
        retry["budget"]["attempts_used"] = 1
        retry["continuation"] = {"previous_receipt": first, "reason": "verification-failure", "failure_evidence": ref("failed-verifier")}
        second = router.decide_route(catalog(old, new), retry)
        self.assertEqual(second["route_id"], "newer")
        self.assertEqual(second["previous_decision_id"], first["decision_id"])
        retry["budget"]["attempts_used"] = 2
        retry["continuation"]["previous_receipt"] = second
        self.assertEqual(router.decide_route(catalog(old, new), retry)["outcome"], "defer")
        retry["budget"]["attempt_cap"] = 3
        with self.assertRaises(router.RouteSelectionError):
            router.decide_route(catalog(old, new), retry)

    def test_transport_retry_cannot_retarget_same_id_to_new_model(self):
        old, task = candidate(), request()
        first = router.decide_route(catalog(old), task)
        task["budget"]["attempts_used"] = 1
        task["continuation"] = {"previous_receipt": first, "reason": "transport-failure", "failure_evidence": ref("transport-failure")}
        changed = copy.deepcopy(old)
        changed["route"]["model"] = "fixture-different-model"
        changed["availability"]["route_sha256"] = router.digest(changed["route"])
        receipt = router.decide_route(catalog(changed), task)
        self.assertEqual(receipt["outcome"], "keep_parent")
        self.assertIn("not_the_predeclared_retry_or_fallback_route", receipt["excluded"]["older"])

    def test_retry_cannot_change_immutable_requirements_effects_or_verifier(self):
        task, item = request(), candidate()
        first = router.decide_route(catalog(item), task)
        task["budget"]["attempts_used"] = 1
        task["continuation"] = {"previous_receipt": first, "reason": "transport-failure", "failure_evidence": ref("failure")}
        mutations = [("requirements", "host", "hermes"), ("requirements", "transport", "collaboration"),
                     ("requirements", "tools", ["terminal"]), ("requirements", "context_tokens", 200),
                     ("verifier", "kind", "schema-only"), ("verifier", "coverage", "partial"),
                     ("verifier", "independent", False), ("budget", "api_reserve", 1)]
        for section, key, value in mutations:
            with self.subTest(field=f"{section}.{key}"):
                changed = copy.deepcopy(task)
                changed[section][key] = value
                with self.assertRaisesRegex(router.RouteSelectionError, "bounded task/pin contract"):
                    router.decide_route(catalog(item), changed)
        for key, value in (("effects", "reversible"), ("failure_cost", "high")):
            changed = copy.deepcopy(task)
            changed[key] = value
            with self.assertRaisesRegex(router.RouteSelectionError, "bounded task/pin contract"):
                router.decide_route(catalog(item), changed)
        task["as_of"] = "2026-09-06T12:15:00Z"
        task["budget"]["quotas"]["fixture-pool"]["remaining"] = 90
        self.assertEqual(router.decide_route(catalog(item), task)["outcome"], "selected_model")

    def test_frozen_replay_and_legacy_bridge_preserve_pins(self):
        snapshot, task = catalog(candidate()), request()
        receipt = router.decide_route(snapshot, task)
        self.assertEqual(router.replay_decision(receipt, snapshot, task), receipt)
        changed = copy.deepcopy(snapshot)
        changed["catalog_version"] = "new-policy"
        with self.assertRaises(router.RouteSelectionError):
            router.replay_decision(receipt, changed, task)
        old_catalog, old_task = legacy_tests.frontier_catalog(), legacy_tests.task()
        old_receipt = legacy.decide_route(old_catalog, old_task)
        self.assertEqual(router.decide_route(old_catalog, old_task), old_receipt)
        self.assertEqual(router.replay_decision(old_receipt, old_catalog, old_task), old_receipt)
        self.assertEqual(router.dispatch_decision(old_receipt, old_catalog, old_task)["kind"], "model")

    def test_exact_transport_effort_tools_context_and_expiry_are_constraints(self):
        for field, expected in (("transport", "different-surface"), ("reasoning_effort", "ultra"), ("model", "other-model"), ("context_tokens", 1001), ("tools", ["terminal"])):
            task = request()
            task["requirements"][field] = expected
            self.assertEqual(router.decide_route(catalog(candidate()), task)["outcome"], "keep_parent")
        task = request()
        task["as_of"] = "2026-09-07T12:00:00Z"
        self.assertEqual(router.decide_route(catalog(candidate()), task)["outcome"], "keep_parent")

    def test_worker_done_or_file_exists_is_not_qualification(self):
        task = request()
        task["failure_cost"] = "high"
        value = candidate()
        value["benchmark_priors"] = [{"worker_said": "done", "output_file_exists": True}]
        self.assertEqual(router.decide_route(catalog(value), task)["outcome"], "keep_parent")

    def test_no_tools_evidence_cannot_certify_tool_capability(self):
        task, value = request(), candidate(qualified=True)
        task["requirements"]["tools"] = ["terminal"]
        task["failure_cost"] = "high"
        value["availability"]["tools_verified"] = ["terminal"]
        value["quality"][0]["scope"] = "inline-text"
        self.assertEqual(router.decide_route(catalog(value), task)["outcome"], "keep_parent")

    def test_reserve_unknown_weights_and_distinct_buckets_do_not_convert(self):
        task, value = request(), candidate(total=None)
        task["budget"]["quotas"]["fixture-pool"]["reserve"] = 10
        receipt = router.decide_route(catalog(value), task)
        self.assertIn("unknown_cost_cannot_protect_reserve", receipt["excluded"]["older"])
        known = candidate(total=95)
        self.assertIn("quota_reserve_would_be_spent", router.decide_route(catalog(known), task)["excluded"]["older"])
        alternative = candidate("newer", 1)
        alternative["cost"]["quota"]["bucket"] = "separate-fixture-pool"
        task["budget"]["quotas"]["separate-fixture-pool"] = {"unit": "fixture-units", "remaining": 100, "reserve": 0}
        task["budget"]["preference_order"] = ["newer"]
        receipt = router.decide_route(catalog(candidate(total=2), alternative), task)
        self.assertNotEqual(receipt["selection_basis"], "minimum_observed_total")

    def test_irreversible_effect_and_unavailable_parent_defer(self):
        task = request()
        task["effects"] = "irreversible"
        task["budget"]["parent_available"] = False
        task["deterministic"] = {"executor_id": "irreversible-handler", "artifact_sha256": router.digest("handler"),
                                 "input_sha256": task["input_sha256"],
                                 "task_contract_sha256": task["requirements"]["task_contract_sha256"], "coverage": "complete", "effects": "irreversible"}
        self.assertEqual(router.decide_route(catalog(candidate(qualified=True)), task)["outcome"], "defer")

    def test_schema_version_mixture_and_untrusted_signal_fields_fail(self):
        with self.assertRaises(router.RouteSelectionError):
            router.decide_route(legacy_tests.frontier_catalog(), request())
        task = request()
        task["model_self_confidence"] = 1
        with self.assertRaises(router.RouteSelectionError):
            router.decide_route(catalog(candidate()), task)
        task = request()
        task["budget"]["api_remaining"] = float("nan")
        with self.assertRaises(router.RouteSelectionError):
            router.decide_route(catalog(candidate()), task)

    def test_generated_contracts_match_embedded_snapshot_contracts(self):
        for name, schema in (("gpt-route-catalog-v3", router.V3_CATALOG_SCHEMA), ("route-task-v3", router.V3_TASK_SCHEMA), ("route-decision-v3", router.V3_DECISION_SCHEMA)):
            actual = json.loads((ROOT / REL / "references" / (name + ".schema.json")).read_bytes())
            self.assertEqual({k: v for k, v in actual.items() if k not in {"$schema", "$id"}}, schema)

    def test_qualified_protocol_applies_to_new_input_without_exact_reuse(self):
        old_task, item = request(), candidate(qualified=True)
        old_task["failure_cost"] = "high"
        first = router.decide_route(catalog(item), old_task)
        fresh = copy.deepcopy(old_task)
        fresh["task_id"] = "fresh-task"
        fresh["input_sha256"] = router.digest("fixture-input-2")
        second = router.decide_route(catalog(item), fresh)
        self.assertEqual(second["route_id"], first["route_id"])
        self.assertEqual(second["qualification"], "qualified")
        self.assertNotEqual(second["decision_id"], first["decision_id"])
        with self.assertRaises(router.RouteSelectionError):
            router.replay_decision(first, catalog(item), fresh)
        retry = copy.deepcopy(old_task)
        retry["input_sha256"] = fresh["input_sha256"]
        retry["budget"]["attempts_used"] = 1
        retry["continuation"] = {"previous_receipt": first, "reason": "transport-failure", "failure_evidence": ref("failure")}
        with self.assertRaisesRegex(router.RouteSelectionError, "bounded task/pin contract"):
            router.decide_route(catalog(item), retry)

    def test_deterministic_handler_is_bound_to_exact_input(self):
        task = request()
        task["deterministic"] = {"executor_id": "fixture-extractor", "artifact_sha256": router.digest("script"),
                                 "task_contract_sha256": task["requirements"]["task_contract_sha256"],
                                 "input_sha256": router.digest("different-input"), "coverage": "complete", "effects": "none"}
        self.assertNotEqual(router.decide_route(catalog(candidate()), task)["outcome"], "execute_deterministic")

    def test_unrelated_protocol_or_verifier_cost_cannot_win_as_observed_minimum(self):
        task = request()
        for basis in ("observed", "quoted"):
            for field in ("task_contract_sha256", "verifier_sha256"):
                with self.subTest(basis=basis, field=field):
                    item = candidate(total=.01)
                    item["cost"]["basis"] = basis
                    item["cost"][field] = router.digest("unrelated")
                    receipt = router.decide_route(catalog(item), task)
                    self.assertNotEqual(receipt["selection_basis"], "minimum_observed_total")
                    self.assertEqual(receipt["cost_observation"]["binding_status"], "mismatched")
                    self.assertIsNone(receipt["cost_observation"]["total"])
                    self.assertIsNone(receipt["cost_observation"]["quota_total"])
                    protected = copy.deepcopy(task)
                    protected["budget"]["quotas"]["fixture-pool"]["reserve"] = 10
                    denied = router.decide_route(catalog(item), protected)
                    self.assertIn("unknown_cost_cannot_protect_reserve", denied["excluded"]["older"])

    def test_cost_for_other_exact_route_cannot_authorize_budget_use(self):
        item = candidate(total=.01)
        item["cost"]["route_sha256"] = router.digest("different-route")
        result = router.decide_route(catalog(item), request())
        self.assertIn("cost_route_binding_mismatch", result["excluded"]["older"])


class LegacySelectionPreserved(legacy_tests.AutomaticFrontierRouteTests):
    @classmethod
    def setUpClass(cls):
        cls.selector = router
        cls.adapter = legacy_tests.load_module("unchanged_route_adapter", STAGE / "tools/route_adapter.py")


if __name__ == "__main__":
    unittest.main(verbosity=2)
