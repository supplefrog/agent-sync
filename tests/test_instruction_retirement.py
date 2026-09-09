from __future__ import annotations

import importlib.util
import copy
import json
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def load_module():
    path = REPO / "tools" / "instruction_retirement.py"
    spec = importlib.util.spec_from_file_location("instruction_retirement", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


class InstructionRetirementTests(unittest.TestCase):
    def setUp(self):
        self.tool = load_module()

    def manifest_with_references(self):
        manifest = json.loads((REPO / "contracts/instruction-units.json").read_text(encoding="utf-8"))
        # Synthetic reference copies exercise planner semantics without requiring
        # retired personality prose to remain in the production instruction set.
        for source_id, reference_id in (("hermes.style", "reference.style"),
                                        ("hermes.instruction-authoring-route", "reference.route")):
            unit = copy.deepcopy(next(u for u in manifest["units"] if u["id"] == source_id))
            unit.update(id=reference_id, status="reference")
            manifest["units"].insert(0, unit)
        return manifest

    @staticmethod
    def stack(host="hermes", equivalence_hash=None, **overrides):
        value = {
            "host": host,
            "runtime": "runtime-a",
            "model": "test-model",
            "model_snapshot": "snapshot-a",
            "provider": "test-provider",
            "provider_snapshot": "provider-a",
            "transport": "transport-a",
            "reasoning": "high",
            "prompt_assembly": "prompt-a",
            "tool_policy": "none",
            "tool_schema": "tools-a",
            "context_policy": "context-a",
            "evaluator_identity": "eval-a",
            "trial_design": {"seed": 7, "min_trials": 2, "max_trials": 8},
            "decision_margin": {"alpha": 0.05, "margin": 0.1, "rule": "hoeffding-alpha-spending"},
        }
        if equivalence_hash is not None:
            value["equivalence_hash"] = equivalence_hash
        value.update(overrides)
        return value

    def test_heading_extraction_and_removal_preserve_neighbors(self):
        text = "# A\n\na\n\n## A1\n\na1\n\n# B\n\nb\n"
        self.assertEqual(self.tool.section(text, "# A"), "# A\n\na\n\n## A1\n\na1\n")
        without = self.tool.without_section(text, "# A")
        self.assertNotIn("## A1", without)
        self.assertEqual(without, "# B\n\nb\n")

    def test_tagged_line_extraction_and_removal_preserve_neighbors(self):
        text = "[OUTPUT] concise result\n[EVIDENCE] verify claims\n"
        selector = {"kind": "tagged-line", "value": "[OUTPUT]"}
        self.assertEqual(self.tool.selected_text(text, selector), "[OUTPUT] concise result\n")
        self.assertEqual(
            self.tool.without_selector(text, selector),
            "[EVIDENCE] verify claims\n",
        )

    def test_paragraph_prefix_extraction_and_removal_preserve_neighbors(self):
        text = "# Defaults\n\nStart with one conclusion. More detail.\n\nWhen thinking aloud, organize first.\n\nRoute durable instructions.\n"
        selector = {"kind": "paragraph-prefix", "value": "When thinking aloud"}
        self.assertEqual(
            self.tool.selected_text(text, selector),
            "When thinking aloud, organize first.\n",
        )
        without = self.tool.without_selector(text, selector)
        self.assertIn("Start with one conclusion", without)
        self.assertIn("Route durable instructions", without)
        self.assertNotIn("When thinking aloud", without)

    def test_model_release_selects_only_bounded_model_sensitive_suites(self):
        manifest = self.manifest_with_references()
        stack = self.stack()
        with tempfile.TemporaryDirectory() as temp:
            plan = self.tool.build_plan(REPO, manifest, stack, "model-release", Path(temp), 1)
        self.assertEqual(len(plan["selected_suites"]), 1)
        self.assertTrue(plan["selected_units"])
        rows = {row["id"]: row for row in plan["units"]}
        self.assertEqual(rows["core.capability-admission"]["action"], "protected-manual")
        self.assertEqual(rows["reference.route"]["action"], "reference-source-review")
        self.assertEqual(rows["reference.style"]["action"], "reference-source-review")

    def test_effective_stack_change_reopens_only_model_sensitive_units(self):
        manifest = self.manifest_with_references()
        with tempfile.TemporaryDirectory() as temp:
            plan = self.tool.build_plan(
                REPO, manifest, self.stack(), "effective-stack-changed", Path(temp), 2,
            )
        rows = {row["id"]: row for row in plan["units"]}
        self.assertTrue(plan["selected_units"])
        self.assertLessEqual(len(plan["selected_suites"]), 2)
        self.assertEqual(rows["reference.style"]["action"], "reference-source-review")
        self.assertEqual(rows["reference.route"]["action"], "reference-source-review")
        self.assertEqual(rows["core.capability-admission"]["action"], "protected-manual")
        self.assertEqual(rows["hermes.deliberation"]["action"], "behavior-ablation")
        self.assertEqual(rows["hermes.instruction-authoring-route"]["action"], "skip-trigger")

    def test_plan_selects_only_live_units_for_the_target_host(self):
        manifest = json.loads((REPO / "contracts" / "instruction-units.json").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as temp:
            plan = self.tool.build_plan(
                REPO, manifest, self.stack(host="hermes"),
                "effective-stack-changed", Path(temp), 4,
            )
        rows = {row["id"]: row for row in plan["units"]}
        self.assertEqual(rows["codex.output"]["action"], "skip-host")
        self.assertEqual(rows["codex.scope"]["action"], "skip-host")
        self.assertNotIn("codex.output", plan["selected_units"])
        self.assertNotIn("codex.scope", plan["selected_units"])
        self.assertTrue(all(unit_id.startswith("hermes.") for unit_id in plan["selected_units"]))

    def test_reference_sources_do_not_shadow_identical_effective_units(self):
        manifest = self.manifest_with_references()
        with tempfile.TemporaryDirectory() as temp:
            plan = self.tool.build_plan(
                REPO, manifest, self.stack(host="hermes"),
                "effective-stack-changed", Path(temp), 4,
            )
        rows = {row["id"]: row for row in plan["units"]}
        self.assertEqual(rows["reference.style"]["action"], "reference-source-review")
        self.assertEqual(rows["hermes.style"]["action"], "behavior-ablation")
        self.assertEqual(rows["hermes.judgment"]["action"], "behavior-ablation")

    def test_live_generic_units_use_complete_owner_specific_suites(self):
        manifest = json.loads((REPO / "contracts" / "instruction-units.json").read_text(encoding="utf-8"))
        required = {"representative", "near-miss", "adversarial", "held-out"}
        for unit in manifest["units"]:
            if unit.get("status") != "effective" or unit["class"] != "generic-steering":
                continue
            suite = json.loads((REPO / unit["suite"]).read_text(encoding="utf-8"))
            self.assertEqual(suite.get("schema_version"), 2, unit["id"])
            self.assertEqual({case.get("kind") for case in suite["cases"]}, required, unit["id"])

    def test_legacy_remove_receipt_is_historical_without_cache_authority(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)
            (path / "old.json").write_text(json.dumps({"schema_version": 1, "cache_key": "old", "decision": "remove"}))
            result = self.tool.load_receipts(path)
        self.assertEqual(result["exact"], {})
        self.assertEqual(result["historical"][0]["recorded_decision"], "remove")
        self.assertFalse(result["historical"][0]["authority"])

    def test_empty_raw_equivalence_receipt_cannot_authorize_cross_host_reuse(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)
            (path / "raw").mkdir()
            (path / "raw/report.json").write_text("{}")
            (path / "old.json").write_text(json.dumps({"schema_version": 2, "cache_key": "old",
                "equivalence_hash": "claimed-equivalence", "decision": "remove", "raw_evidence_path": "raw/report.json"}))
            result = self.tool.load_receipts(path)
        self.assertEqual(result["exact"], {})
        self.assertEqual(result["equivalent"], {})
        self.assertFalse(result["historical"][0]["authority"])

    def test_actual_experiment_identity_changes_with_host_and_task_rule(self):
        manifest = json.loads((REPO / "contracts/instruction-units.json").read_bytes())
        unit = next(u for u in manifest["units"] if u["status"] == "effective" and u["class"] == "generic-steering")
        base = self.tool.build_experiment(REPO, unit, self.stack())["cache_key"]
        for field, value in (("host", "codex"), ("runtime", "runtime-b"), ("reasoning", "medium"),
                             ("decision_margin", {"alpha": .05, "margin": .2, "rule": "hoeffding-alpha-spending"})):
            with self.subTest(field=field):
                changed = self.tool.build_experiment(REPO, unit, self.stack(**{field: value}))["cache_key"]
                self.assertNotEqual(base, changed)

    def test_tool_dependent_lane_is_explicitly_unsupported(self):
        manifest = json.loads((REPO / "contracts/instruction-units.json").read_bytes())
        with tempfile.TemporaryDirectory() as temp:
            result = self.tool.build_plan(REPO, manifest, self.stack(tool_policy="safe"), "effective-stack-changed", Path(temp), 2)
        self.assertFalse(result["selected_units"])
        self.assertTrue(any(row["action"] == "unsupported-runtime" for row in result["units"]))

    def test_unknown_receipt_version_is_diagnostic_not_authority(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)
            (path / "bad.json").write_text(json.dumps({"schema_version": 999, "decision": "remove"}))
            result = self.tool.load_receipts(path)
        self.assertEqual(result["exact"], {})
        self.assertEqual(len(result["invalid"]), 1)


if __name__ == "__main__":
    unittest.main()
