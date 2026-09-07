"""Counterexamples from neutral review; deterministic synthetic inputs only."""
from __future__ import annotations

import copy
import importlib.util
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
import test_task_router as fixtures

BASELINE = "--baseline" in sys.argv
if BASELINE:
    sys.argv.remove("--baseline")
    path = ROOT.parent / "revision-2/frozen/skills/openai-delegation-route-research/scripts/route_selector.py"
    router = fixtures.load("review_revision_2", path)
else:
    router = fixtures.router


def handler(task):
    return {"executor_id": "synthetic-handler", "artifact_sha256": router.digest("handler"),
            "task_contract_sha256": task["requirements"]["task_contract_sha256"], "input_sha256": task["input_sha256"],
            "coverage": "complete", "effects": task["effects"]}


def cash_mixed(amount=5):
    item = fixtures.candidate()
    item["cost"]["api_usd"] = {"generation": 0, "verification": amount, "fallback": 0}
    return item


class NeutralReviewCounterexamples(unittest.TestCase):
    def test_subscription_cannot_bypass_declared_api_spend(self):
        decision = router.decide_route(fixtures.catalog(cash_mixed()), fixtures.request())
        self.assertNotEqual(decision["outcome"], "selected_model", decision)

    def test_provisional_and_deterministic_paths_require_effect_scope(self):
        task, item = fixtures.request(), fixtures.candidate()
        task["requirements"]["tools"] = ["terminal"]
        task["effects"] = "reversible"
        task["verifier"]["scope"] = "inline-text"
        item["availability"]["tools_verified"] = ["terminal"]
        outcomes = [router.decide_route(fixtures.catalog(item), task)["outcome"]]
        task["deterministic"] = handler(task)
        outcomes.append(router.decide_route(fixtures.catalog(item), task)["outcome"])
        self.assertEqual(outcomes, ["keep_parent", "keep_parent"])

    def test_fallback_alias_cannot_repeat_failed_exact_route(self):
        task, item = fixtures.request(), fixtures.candidate()
        alias = copy.deepcopy(item)
        alias["id"] = "retry-alias"
        task["budget"].update(fallback_route_id=alias["id"], fallback_route_sha256=router.digest(alias["route"]))
        catalog = fixtures.catalog(item, alias)
        first = router.decide_route(catalog, task)
        self.assertEqual(first["route_id"], "older")
        task["budget"]["attempts_used"] = 1
        task["continuation"] = {"previous_receipt": first, "reason": "verification-failure", "failure_evidence": fixtures.ref("failed-verifier")}
        second = router.decide_route(catalog, task)
        self.assertNotEqual(second["outcome"], "selected_model", second)

    def test_replay_and_dispatch_reject_bool_for_integer_tampering(self):
        catalog, task = fixtures.catalog(fixtures.candidate()), fixtures.request()
        receipt = router.decide_route(catalog, task)
        receipt["attempt_number"] = True
        accepted = []
        for call in (router.replay_decision, router.dispatch_decision):
            try:
                call(receipt, catalog, task)
                accepted.append(True)
            except router.RouteSelectionError:
                accepted.append(False)
        self.assertEqual(accepted, [False, False])


class NearbyControls(unittest.TestCase):
    def test_mixed_api_spend_needs_known_budget_and_preserves_reserve(self):
        task = fixtures.request()
        task["budget"].update(allow_api_spend=True, api_remaining=10, api_reserve=2)
        self.assertEqual(router.decide_route(fixtures.catalog(cash_mixed()), task)["outcome"], "selected_model")
        task["budget"]["objective"] = "api_usd"
        api_route = fixtures.candidate("newer")
        api_route["cost"]["billing"] = "api"
        api_route["cost"]["api_usd"] = {"generation": 6, "verification": 0, "fallback": 0}
        compared = router.decide_route(fixtures.catalog(cash_mixed(), api_route), task)
        self.assertEqual(compared["route_id"], "older")
        self.assertEqual(compared["cost_observation"]["comparison_key"], ["api_usd"])
        self.assertEqual(compared["cost_observation"]["total"], 5)
        task["budget"]["api_remaining"] = 6
        result = router.decide_route(fixtures.catalog(cash_mixed()), task)
        self.assertIn("api_reserve_would_be_spent", result["excluded"]["older"])
        task["budget"]["api_remaining"] = None
        result = router.decide_route(fixtures.catalog(cash_mixed()), task)
        self.assertIn("api_budget_not_bounded", result["excluded"]["older"])

    def test_partial_declared_api_amount_still_requires_authorization(self):
        item = cash_mixed()
        item["cost"]["api_usd"]["generation"] = None
        result = router.decide_route(fixtures.catalog(item), fixtures.request())
        self.assertIn("api_spend_not_allowed", result["excluded"]["older"])
        self.assertIn("api_budget_not_bounded", result["excluded"]["older"])

    def test_subscription_without_declared_api_spend_keeps_provisional_lane(self):
        result = router.decide_route(fixtures.catalog(fixtures.candidate()), fixtures.request())
        self.assertEqual(result["outcome"], "selected_model")
        self.assertIsNone(result["cost_observation"]["api_usd_total"])

    def test_inline_scope_still_covers_text_without_tool_or_artifact_effects(self):
        task = fixtures.request()
        task["verifier"]["scope"] = "inline-text"
        self.assertEqual(router.decide_route(fixtures.catalog(fixtures.candidate()), task)["outcome"], "selected_model")
        task["deterministic"] = handler(task)
        self.assertEqual(router.decide_route(fixtures.catalog(fixtures.candidate()), task)["outcome"], "execute_deterministic")

    def test_qualified_record_cannot_override_effect_scope_mismatch(self):
        task, item = fixtures.request(), fixtures.candidate(qualified=True)
        task["effects"] = "reversible"
        task["failure_cost"] = "high"
        task["verifier"]["scope"] = "inline-text"
        item["quality"][0]["scope"] = "inline-text"
        result = router.decide_route(fixtures.catalog(item), task)
        self.assertNotEqual(result["outcome"], "selected_model")

    def test_self_rehashed_numeric_tampering_is_not_exact_replay(self):
        catalog, task = fixtures.catalog(fixtures.candidate()), fixtures.request()
        original = router.decide_route(catalog, task)
        for field in ("attempt_number", "nested_cost"):
            with self.subTest(field=field):
                changed = copy.deepcopy(original)
                if field == "attempt_number":
                    changed["attempt_number"] = 1.0
                else:
                    changed["cost_observation"]["total"] = True
                changed["decision_id"] = router.digest({key: value for key, value in changed.items() if key != "decision_id"})
                with self.assertRaises(router.RouteSelectionError):
                    router.replay_decision(changed, catalog, task)
        reordered = dict(reversed(list(original.items())))
        self.assertEqual(router.replay_decision(reordered, catalog, task), original)


if __name__ == "__main__":
    unittest.main(verbosity=2)
