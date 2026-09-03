from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import jsonschema

REPO = Path(__file__).resolve().parents[1]


def load_module():
    path = REPO / "tools" / "learning_intake.py"
    spec = importlib.util.spec_from_file_location("learning_intake", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


class GlobalLearningIntakeTests(unittest.TestCase):
    def setUp(self):
        self.module = load_module()
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = Path(self.temp.name) / "store"

    def event(self, **overrides):
        event = {
            "schema_version": 1,
            "source_type": "user-correction",
            "source_ref": "session:example/message:42",
            "observed_at": "2026-09-02T04:00:00+05:30",
            "scope": "global",
            "behavior_class": "generic-judgment",
            "verification": {
                "status": "verified",
                "evidence_refs": ["evidence/example.json"],
            },
            "lesson": {
                "problem": "The agent treated one successful lookup as format validation.",
                "better_behavior": "Validate the source token before attempting a lookup.",
                "near_miss": "Do not reject a valid token merely because the lookup has no result.",
            },
        }
        event.update(overrides)
        return event

    def test_verified_global_event_creates_shadow_candidate_and_receipt(self):
        result = self.module.ingest(self.event(), self.store)
        self.assertEqual(result["disposition"], "shadow-global")
        self.assertTrue(result["promotion_blocked"])
        candidate = json.loads(Path(result["candidate_path"]).read_text(encoding="utf-8"))
        self.assertEqual(candidate["status"], "shadow")
        self.assertEqual(candidate["owner"], "shared-instruction")
        self.assertEqual(candidate["recurrence_count"], 1)
        self.assertFalse(candidate["promotion_allowed"])
        self.assertTrue(Path(result["receipt_path"]).is_file())

    def test_emitted_event_and_candidate_validate_against_contracts(self):
        result = self.module.ingest(self.event(), self.store)
        receipt = json.loads(Path(result["receipt_path"]).read_text(encoding="utf-8"))
        candidate = json.loads(Path(result["candidate_path"]).read_text(encoding="utf-8"))
        event_schema = json.loads((REPO / "contracts" / "learning-event.schema.json").read_text(encoding="utf-8"))
        candidate_schema = json.loads((REPO / "contracts" / "learning-candidate.schema.json").read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator.check_schema(event_schema)
        jsonschema.Draft202012Validator.check_schema(candidate_schema)
        jsonschema.Draft202012Validator(event_schema).validate(receipt["event"])
        jsonschema.Draft202012Validator(candidate_schema).validate(candidate)

    def test_identical_event_is_idempotent(self):
        first = self.module.ingest(self.event(), self.store)
        second = self.module.ingest(self.event(), self.store)
        self.assertEqual(first["event_id"], second["event_id"])
        self.assertEqual(first["candidate_id"], second["candidate_id"])
        self.assertTrue(second["idempotent"])
        self.assertEqual(len(list((self.store / "receipts").glob("*.json"))), 1)
        candidate = json.loads(Path(second["candidate_path"]).read_text(encoding="utf-8"))
        self.assertEqual(candidate["recurrence_count"], 1)

    def test_recurrent_independent_evidence_merges_without_losing_receipts(self):
        first = self.module.ingest(self.event(), self.store)
        second_event = self.event(
            source_type="verified-task-failure",
            source_ref="run:unrelated-project/17",
            observed_at="2026-09-03T04:00:00+05:30",
            verification={"status": "verified", "evidence_refs": ["evidence/other.json"]},
        )
        second = self.module.ingest(second_event, self.store)
        self.assertEqual(first["candidate_id"], second["candidate_id"])
        self.assertFalse(second["idempotent"])
        candidate = json.loads(Path(second["candidate_path"]).read_text(encoding="utf-8"))
        self.assertEqual(candidate["recurrence_count"], 2)
        self.assertEqual(len(candidate["evidence"]), 2)
        self.assertEqual(len(list((self.store / "receipts").glob("*.json"))), 2)

    def test_project_specific_signal_is_routed_local_not_global(self):
        event = self.event(scope="project", behavior_class="project-convention")
        result = self.module.ingest(event, self.store)
        self.assertEqual(result["disposition"], "local-only")
        self.assertEqual(result["owner"], "project-local")
        self.assertFalse((self.store / "candidates" / "global").exists())
        self.assertIn("candidates\\local", result["candidate_path"].replace("/", "\\"))

    def test_user_fact_is_staged_for_memory_without_mutating_memory(self):
        event = self.event(
            scope="user",
            behavior_class="user-preference",
            lesson={
                "problem": "The response was too long for routine status.",
                "better_behavior": "Use the shortest complete status by default.",
                "near_miss": "Keep decision-changing detail when it matters.",
            },
        )
        result = self.module.ingest(event, self.store)
        self.assertEqual(result["disposition"], "memory-only")
        self.assertEqual(result["owner"], "user-memory")
        self.assertIn("candidates\\memory", result["candidate_path"].replace("/", "\\"))

    def test_unverified_or_sensitive_events_fail_closed(self):
        unverified = self.event(verification={"status": "inferred", "evidence_refs": []})
        with self.assertRaisesRegex(self.module.IntakeError, "verified evidence"):
            self.module.ingest(unverified, self.store)
        token_like = "s" + "k-" + ("a" * 24)
        sensitive = self.event(
            lesson={
                "problem": f"Leaked credential {token_like}.",
                "better_behavior": "Retain it.",
                "near_miss": "None.",
            }
        )
        with self.assertRaisesRegex(self.module.IntakeError, "sensitive"):
            self.module.ingest(sensitive, self.store)
        raw = self.event(raw_transcript="private conversation")
        with self.assertRaisesRegex(self.module.IntakeError, "unsupported field"):
            self.module.ingest(raw, self.store)
        self.assertFalse((self.store / "receipts").exists())

    def test_every_declared_source_type_can_stage_a_verified_event(self):
        for index, source_type in enumerate(sorted(self.module.SOURCE_TYPES)):
            event = self.event(
                source_type=source_type,
                source_ref=f"source-{index}",
                observed_at=f"2026-09-02T00:00:{index:02d}Z",
            )
            result = self.module.ingest(event, self.store)
            self.assertEqual(result["disposition"], "shadow-global")
            self.assertTrue(Path(result["receipt_path"]).is_file())

    def test_behavior_classes_have_one_deterministic_owner(self):
        expected = {
            "generic-judgment": "shared-instruction",
            "reusable-procedure": "agent-skill",
            "runtime-mechanic": "host-adapter",
            "github-workflow": "github-follow-up",
            "safety-governance": "manual-control-plane",
            "project-convention": "project-local",
            "user-preference": "user-memory",
            "environment-fact": "user-memory",
        }
        self.assertEqual(self.module.OWNER_BY_CLASS, expected)

    def test_behavior_suite_uses_fixed_trial_structured_admission_contract(self):
        suite = json.loads((REPO / "evals" / "global-learning-intake.json").read_text(encoding="utf-8"))
        self.assertEqual(suite["schema_version"], 3)
        self.assertEqual(suite["stability"], {
            "trials": 2,
            "required_win_kinds": ["representative", "held-out"],
        })
        self.assertEqual(
            {case["kind"] for case in suite["cases"]},
            {"representative", "near-miss", "adversarial", "held-out"},
        )
        for case in suite["cases"]:
            self.assertTrue(case["expected_receipt"])
            self.assertTrue(case["semantic_criteria"])
        by_id = {case["id"]: case for case in suite["cases"]}
        self.assertEqual(by_id["safety-governance-candidate"]["kind"], "adversarial")
        self.assertEqual(by_id["verified-host-runtime-drift"]["kind"], "adversarial")
        self.assertEqual(by_id["verified-github-follow-up-drift"]["kind"], "adversarial")
        self.assertEqual(by_id["verified-user-environment-fact"]["kind"], "held-out")
        self.assertEqual(
            by_id["verified-user-environment-fact"]["expected_receipt"],
            {
                "disposition": "memory-only",
                "owner": "user-memory",
                "evidence": "verified",
                "promotion_blocked": True,
                "recurrence": "new",
                "next_step": "memory-route",
            },
        )

    def test_skill_distinguishes_portable_procedures_from_host_coupling(self):
        skill = (REPO / "skills" / "global-learning-intake" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("Classify portability before mechanism shape", skill)
        self.assertIn("host runtime, API, CLI, or implementation", skill)
        self.assertIn("applies across hosts or projects remains `agent-skill`", skill)

    def test_skill_requires_concise_owner_specific_rationales(self):
        skill = (REPO / "skills" / "global-learning-intake" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("fewest causal sentences", skill)
        self.assertIn("Name the exact destination surface", skill)
        self.assertIn("Do not repeat receipt fields as rationale padding", skill)

    def test_default_store_resolution_uses_one_shared_hermes_root(self):
        explicit = self.module.default_store(
            {"AGENT_SIGNAL_LEARNING_STORE": str(Path(self.temp.name) / "explicit")},
            platform_name="nt",
            home=Path(self.temp.name) / "home",
        )
        self.assertEqual(explicit, Path(self.temp.name) / "explicit")

        hermes_home = self.module.default_store(
            {"HERMES_HOME": str(Path(self.temp.name) / "hermes-home")},
            platform_name="nt",
            home=Path(self.temp.name) / "home",
        )
        self.assertEqual(hermes_home, Path(self.temp.name) / "hermes-home" / "cache" / "global-learning-intake")

        windows_default = self.module.default_store(
            {"LOCALAPPDATA": str(Path(self.temp.name) / "local")},
            platform_name="nt",
            home=Path(self.temp.name) / "home",
        )
        self.assertEqual(windows_default, Path(self.temp.name) / "local" / "hermes" / "cache" / "global-learning-intake")

    def test_cli_ingest_outputs_json_and_does_not_touch_repo_surfaces(self):
        event_path = Path(self.temp.name) / "event.json"
        event_path.write_text(json.dumps(self.event()), encoding="utf-8")
        protected = REPO / "surfaces" / "core.md"
        before = protected.read_bytes()
        result = subprocess.run(
            [
                sys.executable,
                str(REPO / "tools" / "learning_intake.py"),
                "ingest",
                "--event",
                str(event_path),
            ],
            text=True,
            capture_output=True,
            check=False,
            env={**os.environ, "AGENT_SIGNAL_LEARNING_STORE": str(self.store)},
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["disposition"], "shadow-global")
        self.assertEqual(before, protected.read_bytes())


if __name__ == "__main__":
    unittest.main()
