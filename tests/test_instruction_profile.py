from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("instruction_profile", ROOT / "tools" / "instruction_profile.py")
assert SPEC and SPEC.loader
profile_tool = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(profile_tool)


class InstructionProfileTests(unittest.TestCase):
    def setUp(self) -> None:
        self.profile = ROOT / "profiles" / "gpt-5.6-sol-openai-codex.json"

    def mutated_profile(self, mutate) -> Path:
        data = json.loads(self.profile.read_text(encoding="utf-8"))
        mutate(data)
        temp = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
        temp.write(json.dumps(data))
        temp.close()
        self.addCleanup(lambda: Path(temp.name).unlink(missing_ok=True))
        return Path(temp.name)

    def verify(self, profile: Path):
        return profile_tool.verify_profile(ROOT, profile, live=False)

    def test_current_profile_is_bounded_and_excludes_retired_delta(self) -> None:
        report = self.verify(self.profile)
        self.assertEqual("artifact-only", report["verification_mode"])
        self.assertEqual("gpt-5.6-sol", report["model"])
        self.assertEqual("openai-codex", report["provider"])
        self.assertTrue(all(row["bytes"] <= row["budget"] for row in report["hosts"].values()))
        self.assertNotIn("omp.output-delta", report["hosts"]["omp"]["units"])
        self.assertNotIn("omp.rules-delta", report["hosts"]["omp"]["surfaces"])

    def test_unknown_unit_is_rejected(self) -> None:
        path = self.mutated_profile(lambda data: data["hosts"]["hermes"]["effective_units"].append("missing.unit"))
        with self.assertRaisesRegex(profile_tool.ProfileError, "unknown instruction unit"):
            self.verify(path)

    def test_retired_surface_is_rejected(self) -> None:
        path = self.mutated_profile(lambda data: data["hosts"]["omp"]["effective_surfaces"].append("omp.rules-delta"))
        with self.assertRaisesRegex(profile_tool.ProfileError, "retired surface"):
            self.verify(path)

    def test_artifact_hash_mismatch_is_rejected(self) -> None:
        def mutate(data):
            data["hosts"]["hermes"]["artifact_sha256"] = ["0" * 64]

        with self.assertRaisesRegex(profile_tool.ProfileError, "artifact hash"):
            self.verify(self.mutated_profile(mutate))

    def test_standing_byte_budget_is_enforced(self) -> None:
        def mutate(data):
            data["context_policy"]["max_standing_bytes"]["codex"] = 1

        with self.assertRaisesRegex(profile_tool.ProfileError, "standing byte budget"):
            self.verify(self.mutated_profile(mutate))

    def test_humanizer_and_instruction_authoring_remain_on_demand(self) -> None:
        def mutate(data):
            data["writing_routes"]["public-prose"]["loading"] = "standing"

        with self.assertRaisesRegex(profile_tool.ProfileError, "must remain on-demand"):
            self.verify(self.mutated_profile(mutate))

    def test_current_observed_profile_requires_existing_evidence(self) -> None:
        def mutate(data):
            data["status"] = "current-observed"
            data["evidence"] = ["evals/results/not-present.json"]

        with self.assertRaisesRegex(profile_tool.ProfileError, "missing profile evidence"):
            self.verify(self.mutated_profile(mutate))

    def test_current_profile_rejects_model_selector_drift(self) -> None:
        def mutate(data):
            data["target"]["model"] = "fabricated-current-model"

        with self.assertRaisesRegex(profile_tool.ProfileError, "selector mismatch"):
            self.verify(self.mutated_profile(mutate))

    def test_current_profile_rejects_runtime_version_drift(self) -> None:
        def mutate(data):
            data["hosts"]["codex"]["runtime"] = "fabricated-runtime"

        with self.assertRaisesRegex(profile_tool.ProfileError, "runtime mismatch"):
            self.verify(self.mutated_profile(mutate))

    def test_live_profile_rejects_coordinated_snapshot_drift(self) -> None:
        drift = {"apply": False, "changes": [{"host": "codex"}], "conflicts": []}
        with patch.object(profile_tool.recovery, "restore", return_value=drift):
            with self.assertRaisesRegex(profile_tool.ProfileError, "live recovery state mismatch"):
                profile_tool.verify_profile(ROOT, self.profile, live=True)

    def test_live_profile_rejects_runtime_cli_drift(self) -> None:
        clean = {"apply": False, "changes": [], "conflicts": []}
        observed = {"hermes": "0.20.5", "codex": "fabricated", "omp": "17.2.13"}
        with patch.object(profile_tool.recovery, "restore", return_value=clean), patch.object(
            profile_tool, "_live_runtime_versions", return_value=observed, create=True
        ):
            with self.assertRaisesRegex(profile_tool.ProfileError, "live runtime mismatch"):
                profile_tool.verify_profile(ROOT, self.profile, live=True)


if __name__ == "__main__":
    unittest.main()
