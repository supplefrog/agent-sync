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
        self.profile = profile_tool.current_profile(ROOT)

    def test_default_profile_rejects_missing_and_ambiguous_current_observations(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp)
            (repo / "profiles").mkdir()
            with self.assertRaisesRegex(profile_tool.ProfileError, "found 0"):
                profile_tool.current_profile(repo)
            for name in ("old", "new"):
                (repo / "profiles" / f"{name}.json").write_text(json.dumps({"status": "current-observed"}), encoding="utf-8")
            with self.assertRaisesRegex(profile_tool.ProfileError, "found 2"):
                profile_tool.current_profile(repo)
            (repo / "profiles" / "old.json").write_text(json.dumps({"status": "superseded"}), encoding="utf-8")
            self.assertEqual(profile_tool.current_profile(repo), repo / "profiles" / "new.json")

    def mutated_profile(self, mutate) -> Path:
        data = json.loads(self.profile.read_text(encoding="utf-8"))
        mutate(data)
        temp = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
        temp.write(json.dumps(data))
        temp.close()
        self.addCleanup(lambda: Path(temp.name).unlink(missing_ok=True))
        return Path(temp.name)

    def verify(self, profile: Path):
        return profile_tool.verify_profile(ROOT, profile, live=False, hosts=("codex", "hermes", "omp"))

    def test_current_profile_is_bounded_and_excludes_retired_delta(self) -> None:
        report = self.verify(self.profile)
        self.assertEqual("artifact-only", report["verification_mode"])
        declared = json.loads(self.profile.read_text(encoding="utf-8"))
        self.assertEqual(declared["target"]["model"], report["model"])
        self.assertEqual("gpt-6-astra", report["hosts"]["omp"]["model"])
        self.assertEqual("medium", report["hosts"]["hermes"]["reasoning"])
        self.assertEqual("openai-codex", report["provider"])
        for host, settings in declared["hosts"].items():
            self.assertEqual(settings.get("model", declared["target"]["model"]), report["hosts"][host]["model"])
            self.assertEqual(settings.get("provider", declared["target"]["provider"]), report["hosts"][host]["provider"])
        self.assertTrue(all(row["bytes"] <= row["budget"] for row in report["hosts"].values()))
        self.assertNotIn("omp.output-delta", report["hosts"]["omp"]["units"])
        self.assertNotIn("omp.rules-delta", report["hosts"]["omp"]["surfaces"])
        self.assertNotIn("omp.codex-inherited", report["hosts"]["omp"]["surfaces"])
        self.assertEqual([], report["hosts"]["omp"]["units"])
        self.assertEqual([], report["hosts"]["omp"]["artifact_sha256"])
        self.assertEqual(0, report["hosts"]["omp"]["bytes"])
        self.assertIn("not enabled", report["hosts"]["omp"]["no_managed_standing_reason"])

    def test_empty_managed_standing_requires_explicit_observed_reason(self) -> None:
        def mutate(data):
            data["hosts"]["omp"].pop("no_managed_standing_reason")

        with self.assertRaisesRegex(profile_tool.ProfileError, "model profile schema"):
            self.verify(self.mutated_profile(mutate))

    def test_observed_absence_cannot_hide_managed_units(self) -> None:
        def mutate(data):
            data["hosts"]["omp"]["effective_units"] = ["codex.output"]
            data["hosts"]["omp"]["artifact_sha256"] = [
                data["hosts"]["codex"]["artifact_sha256"][0]
            ]

        with self.assertRaisesRegex(profile_tool.ProfileError, "model profile schema"):
            self.verify(self.mutated_profile(mutate))

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
            data["hosts"]["hermes"]["model"] = "fabricated-current-model"

        with self.assertRaisesRegex(profile_tool.ProfileError, "selector mismatch"):
            self.verify(self.mutated_profile(mutate))

    def test_current_profile_rejects_runtime_version_drift(self) -> None:
        def mutate(data):
            data["hosts"]["codex"]["runtime"] = "fabricated-runtime"

        with self.assertRaisesRegex(profile_tool.ProfileError, "runtime mismatch"):
            self.verify(self.mutated_profile(mutate))

    def test_mixed_per_host_selectors_are_valid_but_selector_drift_is_rejected(self) -> None:
        profile = {
            "target": {"model": "gpt-6-astra", "provider": "openai-codex"},
            "hosts": {
                "hermes": {"reasoning": "low"},
                "codex": {
                    "model": "gpt-5.6-sol",
                    "provider": "openai-codex",
                    "reasoning": "low",
                },
                "omp": {"reasoning": "xhigh"},
            },
        }
        observed = {
            "hermes": {"model": "gpt-6-astra", "provider": "openai-codex", "reasoning": "low"},
            "codex": {"model": "gpt-5.6-sol", "provider": "openai-codex", "reasoning": "low"},
            "omp": {"model": "gpt-6-astra", "provider": "openai-codex", "reasoning": "xhigh"},
        }
        profile_tool._verify_selector_observations(profile, observed)

        observed["codex"]["model"] = "fabricated-drift"
        with self.assertRaisesRegex(profile_tool.ProfileError, "selector mismatch for codex"):
            profile_tool._verify_selector_observations(profile, observed)

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

    def test_routine_selector_reads_only_maintained_hosts(self) -> None:
        observed = profile_tool._selector_observations(ROOT)
        self.assertEqual({"codex", "hermes"}, set(observed))

    def test_live_optional_omp_checks_inheritance_only_when_claimed(self) -> None:
        matrix = {"hosts": {"omp": {"cli_version": "fixture-version"}}}
        clean = {"changes": [], "conflicts": []}
        absent = {"hosts": {"omp": {"effective_surfaces": ["omp.runtime-native"]}}}
        inherited = {"hosts": {"omp": {"effective_surfaces": ["omp.codex-inherited"]}}}
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with patch.object(profile_tool.recovery, "_default_roots", return_value={"omp": root}), \
                    patch.object(profile_tool.recovery, "restore", return_value=clean), \
                    patch.object(profile_tool, "_live_runtime_versions", return_value={"omp": "fixture-version"}), \
                    patch.object(profile_tool.recovery, "_read_config", return_value={"disabledProviders": ["codex"]}) as read:
                profile_tool._verify_live_environment(ROOT, matrix, hosts=["omp"], profile=absent)
                read.assert_not_called()
                with self.assertRaisesRegex(profile_tool.ProfileError, "codex discovery provider is disabled"):
                    profile_tool._verify_live_environment(ROOT, matrix, hosts=["omp"], profile=inherited)
                read.return_value = {"enabledProviders": []}
                with self.assertRaisesRegex(profile_tool.ProfileError, "not enabled for claimed inheritance"):
                    profile_tool._verify_live_environment(ROOT, matrix, hosts=["omp"], profile=inherited)
                read.return_value = {"enabledProviders": ["codex"]}
                profile_tool._verify_live_environment(ROOT, matrix, hosts=["omp"], profile=inherited)

    def test_routine_live_environment_does_not_read_omp_config_or_execute_runtime(self) -> None:
        matrix = {"hosts": {host: {"cli_version": "fixture-version"} for host in ("codex", "hermes")}}
        clean = {"changes": [], "conflicts": []}
        with patch.object(profile_tool.recovery, "restore", return_value=clean) as restore, \
                patch.object(profile_tool, "_live_runtime_versions", return_value={"codex": "fixture-version", "hermes": "fixture-version"}) as versions, \
                patch.object(profile_tool.recovery, "_read_config", side_effect=AssertionError("OMP config read")):
            profile_tool._verify_live_environment(ROOT, matrix)
            self.assertEqual(("codex", "hermes"), versions.call_args.args[0])
            self.assertEqual(("codex", "hermes"), restore.call_args.kwargs["hosts"])


if __name__ == "__main__":
    unittest.main()
