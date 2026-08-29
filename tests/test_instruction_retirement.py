from __future__ import annotations

import importlib.util
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
            "tool_policy": "safe",
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

    def test_model_release_selects_only_bounded_model_sensitive_suites(self):
        manifest = json.loads((REPO / "contracts" / "instruction-units.json").read_text(encoding="utf-8"))
        stack = self.stack()
        with tempfile.TemporaryDirectory() as temp:
            plan = self.tool.build_plan(REPO, manifest, stack, "model-release", Path(temp), 1)
        self.assertEqual(len(plan["selected_suites"]), 1)
        self.assertTrue(plan["selected_units"])
        rows = {row["id"]: row for row in plan["units"]}
        self.assertEqual(rows["core.capability-admission"]["action"], "protected-manual")
        self.assertEqual(rows["core.outcome-first-workflow"]["action"], "skip-trigger")
        self.assertEqual(rows["core.delegation-routing"]["action"], "skip-trigger")
        self.assertEqual(rows["core.scope"]["action"], "behavior-ablation")

    def test_effective_stack_change_reopens_only_model_sensitive_units(self):
        manifest = json.loads((REPO / "contracts" / "instruction-units.json").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as temp:
            plan = self.tool.build_plan(
                REPO, manifest, self.stack(), "effective-stack-changed", Path(temp), 2,
            )
        rows = {row["id"]: row for row in plan["units"]}
        self.assertTrue(plan["selected_units"])
        self.assertLessEqual(len(plan["selected_suites"]), 2)
        self.assertEqual(rows["core.scope"]["action"], "behavior-ablation")
        self.assertEqual(rows["core.outcome-first-workflow"]["action"], "skip-trigger")
        self.assertEqual(rows["core.capability-admission"]["action"], "protected-manual")

    def test_exact_receipt_suppresses_retest(self):
        manifest = {
            "schema_version": 1,
            "units": [
                {
                    "id": "unit",
                    "path": "surfaces/core.md",
                    "selector": {"kind": "heading", "value": "# Communication"},
                    "class": "generic-steering",
                    "suite": "evals/core-instruction-retirement.json",
                    "retest_on": ["model-release"],
                }
            ],
        }
        stack = self.stack()
        with tempfile.TemporaryDirectory() as temp:
            receipts = Path(temp)
            first = self.tool.build_plan(REPO, manifest, stack, "model-release", receipts, 1)
            row = first["units"][0]
            (receipts / "receipt.json").write_text(
                json.dumps({"schema_version": 1, "cache_key": row["cache_key"], "decision": "remove"}),
                encoding="utf-8",
            )
            second = self.tool.build_plan(REPO, manifest, stack, "model-release", receipts, 1)
        self.assertEqual(second["units"][0]["action"], "cached-remove")
        self.assertFalse(second["selected_units"])

    def test_any_load_bearing_stack_or_trial_margin_change_invalidates_receipt(self):
        base = self.stack()
        changed_values = {
            "host": "codex",
            "runtime": "runtime-b",
            "model_snapshot": "snapshot-b",
            "provider_snapshot": "provider-b",
            "transport": "transport-b",
            "reasoning": "medium",
            "prompt_assembly": "prompt-b",
            "tool_policy": "full",
            "tool_schema": "tools-b",
            "context_policy": "context-b",
            "evaluator_identity": "eval-b",
            "trial_design": {"seed": 8, "min_trials": 2, "max_trials": 8},
            "decision_margin": {"alpha": 0.05, "margin": 0.2, "rule": "hoeffding-alpha-spending"},
        }
        identity = ("unit", "suite", "harness")
        original = self.tool.receipt_key(base, *identity)
        for field, value in changed_values.items():
            with self.subTest(field=field):
                changed = self.tool.receipt_key(self.stack(**{field: value}), *identity)
                self.assertNotEqual(original, changed)

    def test_receipt_is_host_scoped_without_explicit_equivalence_hash(self):
        identity = ("unit", "suite", "harness")
        self.assertNotEqual(
            self.tool.receipt_key(self.stack(host="hermes"), *identity),
            self.tool.receipt_key(self.stack(host="codex"), *identity),
        )
        self.assertIsNone(self.tool.equivalence_receipt_key(self.stack(host="hermes"), *identity))

    def test_explicit_equivalence_hash_allows_cross_host_receipt_reuse(self):
        manifest = {
            "schema_version": 1,
            "units": [{
                "id": "unit", "path": "surfaces/core.md",
                "selector": {"kind": "heading", "value": "# Communication"},
                "class": "generic-steering", "suite": "evals/core-instruction-retirement.json",
                "retest_on": ["effective-stack-changed"],
            }],
        }
        with tempfile.TemporaryDirectory() as temp:
            receipts = Path(temp)
            hermes = self.tool.build_plan(
                REPO, manifest, self.stack(host="hermes", equivalence_hash="eq-proof"),
                "effective-stack-changed", receipts, 1,
            )
            row = hermes["units"][0]
            raw = receipts / "raw" / "report.json"
            raw.parent.mkdir()
            raw.write_text("{}", encoding="utf-8")
            (receipts / "append-only-receipt.json").write_text(json.dumps({
                "schema_version": 2,
                "cache_key": row["cache_key"],
                "equivalence_hash": "eq-proof",
                "equivalence_cache_key": row["equivalence_cache_key"],
                "decision": "remove",
                "raw_evidence_path": "raw/report.json",
            }), encoding="utf-8")
            codex = self.tool.build_plan(
                REPO, manifest, self.stack(host="codex", runtime="runtime-b", equivalence_hash="eq-proof"),
                "effective-stack-changed", receipts, 1,
            )
        self.assertEqual(codex["units"][0]["action"], "cached-remove")
        self.assertIn("explicit cross-host equivalence", codex["units"][0]["reasons"][0])

    def test_equivalence_receipt_without_preserved_raw_evidence_is_ignored(self):
        stack = self.stack(equivalence_hash="eq-proof")
        identity = ("unit", "suite", "harness")
        with tempfile.TemporaryDirectory() as temp:
            receipts = Path(temp)
            key = self.tool.equivalence_receipt_key(stack, *identity)
            (receipts / "receipt.json").write_text(json.dumps({
                "schema_version": 2,
                "cache_key": "exact-other-host",
                "equivalence_hash": "eq-proof",
                "equivalence_cache_key": key,
                "decision": "remove",
                "raw_evidence_path": "missing.json",
            }), encoding="utf-8")
            loaded = self.tool.load_receipts(receipts)
        self.assertEqual(loaded["equivalent"], {})


if __name__ == "__main__":
    unittest.main()
