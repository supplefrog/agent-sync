"""Approved default projection, native CAS/rollback, and truthful observations."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import runtime_defaults as defaults
import instruction_profile as profiles
import recovery


class RuntimeDefaultsTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.repo = Path(self.temporary.name) / "repo"
        (self.repo / "surfaces").mkdir(parents=True)
        (self.repo / "surfaces/core.md").write_bytes((ROOT / "surfaces/core.md").read_bytes())
        self.roots = {host: Path(self.temporary.name) / host for host in ("codex", "hermes")}
        for root in self.roots.values():
            root.mkdir()
        self.codex = {"model": "gpt-6-sol", "model_reasoning_effort": "medium",
                      "approvals_reviewer": "auto_review", "session": {"pin": "old-model"},
                      "model_providers": {"custom": {"base_url": "https://example.test"}},
                      "private": {"token": "private-config-value"}}
        self.hermes = {"model": {"default": "gpt-6-sol", "provider": "openai-codex",
                                 "request_overrides": {"extra_body": {"routing": "retain"}}},
                       "agent": {"reasoning_effort": "medium", "max_turns": 45},
                       "private": {"token": "private-config-value"}}
        self.save_native()

    def save_native(self):
        for host, value in (("codex", self.codex), ("hermes", self.hermes)):
            source, fmt, _ = defaults.ADAPTERS[host]
            (self.roots[host] / source).write_bytes(recovery._serialize_config(value, fmt))

    def prepare(self, hosts=None):
        prepared = defaults.prepare_defaults(self.repo, roots=self.roots, hosts=hosts)
        self.addCleanup(self.cleanup_prepared, prepared)
        return prepared

    @staticmethod
    def cleanup_prepared(prepared):
        if prepared.private_backup and prepared.private_backup.exists():
            shutil.rmtree(prepared.private_backup)

    def edit_preferences(self, edit):
        path = self.repo / "surfaces/core.md"
        value = defaults.load_preferences(self.repo)
        edit(value)
        text = path.read_text()
        begin = "<!-- agent-sync-preferences -->"
        end = "<!-- /agent-sync-preferences -->"
        path.write_text(text.split(begin)[0] + begin + "\n```json\n" + json.dumps(value) +
                        "\n```\n" + end + text.split(end)[1])

    def test_plan_is_read_only_default_scope_and_has_no_private_config(self):
        before = {host: (root / defaults.ADAPTERS[host][0]).read_bytes() for host, root in self.roots.items()}
        report = self.prepare().report
        self.assertEqual(["codex", "hermes"], report["hosts"])
        self.assertFalse(report["mutation_performed"])
        self.assertEqual(2, len(report["changes"]))
        text = json.dumps(report)
        self.assertNotIn("private-config-value", text)
        self.assertNotIn(str(self.roots["codex"]), text)
        self.assertEqual(before, {host: (root / defaults.ADAPTERS[host][0]).read_bytes() for host, root in self.roots.items()})

    def test_core_value_change_drives_native_mapping_without_a_second_table(self):
        self.edit_preferences(lambda value: value["roles"]["worker"].update(model="gpt-6-luna", reasoning="high"))
        report = self.prepare(hosts=["codex"]).report
        self.assertEqual({"gpt-6-luna", "high"}, {change["after"] for change in report["changes"]})

    def test_apply_preserves_all_unselected_parsed_settings_and_is_idempotent(self):
        prepared = self.prepare()
        report = defaults.apply_defaults(prepared)
        self.assertTrue(report["mutation_performed"])
        for host, original in (("codex", self.codex), ("hermes", self.hermes)):
            source, fmt, keys = defaults.ADAPTERS[host]
            observed = recovery._read_config(self.roots[host] / source, fmt)
            expected = deepcopy(original)
            for field, dotted in keys.items():
                recovery._set_dotted(expected, dotted, report["observations"][host][field])
            self.assertEqual(expected, observed)
            self.assertIn("Z", report["observations"][host]["observed_at"])
        again = defaults.apply_defaults(self.prepare())
        self.assertEqual("unchanged", again["result"])
        self.assertFalse(again["mutation_performed"])

    def test_changed_selected_config_blocks_every_write(self):
        prepared = self.prepare()
        codex_path = self.roots["codex"] / "config.toml"
        before = codex_path.read_bytes()
        (self.roots["hermes"] / "config.yaml").write_text("model: changed concurrently\n")
        with self.assertRaisesRegex(defaults.DefaultsError, "changed before apply"):
            defaults.apply_defaults(prepared)
        self.assertEqual(before, codex_path.read_bytes())

    def test_changed_core_blocks_apply(self):
        prepared = self.prepare()
        self.edit_preferences(lambda value: value["roles"]["worker"].update(reasoning="high"))
        with self.assertRaisesRegex(defaults.DefaultsError, "preference owner changed"):
            defaults.apply_defaults(prepared)

    def test_unsupported_provider_blocks_without_mutation(self):
        self.hermes["model"]["provider"] = "unselected-provider"
        self.save_native()
        before = (self.roots["codex"] / "config.toml").read_bytes()
        with self.assertRaisesRegex(defaults.DefaultsError, "provider mapping"):
            self.prepare()
        self.assertEqual(before, (self.roots["codex"] / "config.toml").read_bytes())

    def test_optional_omp_has_no_implicit_config_read_or_default_write(self):
        prepared = self.prepare(hosts=["omp"])
        self.assertEqual([], prepared.entries)
        self.assertEqual("omp", prepared.report["deferred"][0]["host"])
        self.assertFalse(defaults.apply_defaults(prepared)["mutation_performed"])

    def test_invalid_or_duplicate_preference_blocks_are_rejected(self):
        path = self.repo / "surfaces/core.md"
        original = path.read_text()
        path.write_text(original + "\n<!-- agent-sync-preferences -->")
        with self.assertRaisesRegex(defaults.DefaultsError, "exactly one"):
            defaults.load_preferences(self.repo)
        path.write_text(original.replace('"schema_version": 1,', '"schema_version": 1, "schema_version": 1,'))
        with self.assertRaisesRegex(defaults.DefaultsError, "duplicate preference"):
            defaults.load_preferences(self.repo)

    def test_bad_role_shape_and_unknown_hosts_fail_cleanly(self):
        self.edit_preferences(lambda value: value["roles"]["worker"].update(reasoning=[]))
        with self.assertRaisesRegex(defaults.DefaultsError, "unsupported role"):
            self.prepare()
        with self.assertRaises(defaults.DefaultsError):
            defaults.selected_hosts(self.repo, ["missing"])

    def test_second_write_failure_rolls_back_first_own_write(self):
        prepared = self.prepare()
        before = {entry["path"]: entry["original"] for entry in prepared.entries}
        atomic = recovery._atomic_write
        def failure(path, data):
            if path.name == "config.yaml":
                raise OSError("isolated second-write failure")
            atomic(path, data)
        with patch.object(recovery, "_atomic_write", side_effect=failure):
            with self.assertRaisesRegex(defaults.DefaultsError, "rollback"):
                defaults.apply_defaults(prepared)
        self.assertEqual(before, {path: path.read_bytes() for path in before})

    def test_core_change_during_first_write_stops_next_write_and_rolls_back(self):
        prepared = self.prepare()
        before = {entry["path"]: entry["original"] for entry in prepared.entries}
        atomic = recovery._atomic_write
        def change_core(path, data):
            atomic(path, data)
            if path.name == "config.toml":
                self.edit_preferences(lambda value: value["roles"]["worker"].update(reasoning="high"))
        with patch.object(recovery, "_atomic_write", side_effect=change_core):
            with self.assertRaisesRegex(defaults.DefaultsError, "preference owner changed"):
                defaults.apply_defaults(prepared)
        self.assertEqual(before, {path: path.read_bytes() for path in before})

    def test_failure_after_atomic_replace_is_rolled_back(self):
        prepared = self.prepare(hosts=["codex"])
        entry = prepared.entries[0]
        atomic = recovery._atomic_write
        def failure(path, data):
            atomic(path, data)
            raise OSError("failure after replacement")
        with patch.object(recovery, "_atomic_write", side_effect=failure):
            with self.assertRaisesRegex(defaults.DefaultsError, "rollback"):
                defaults.apply_defaults(prepared)
        self.assertEqual(entry["original"], entry["path"].read_bytes())

    def test_outer_rollback_preserves_concurrent_edit_and_retains_private_baseline(self):
        prepared = self.prepare(hosts=["codex"])
        defaults.apply_defaults(prepared)
        path = prepared.entries[0]["path"]
        path.write_text("concurrent edit\n")
        report = defaults.rollback_defaults(prepared)
        self.assertEqual("concurrent edit\n", path.read_text())
        self.assertEqual(["codex"], report["conflict_hosts"])
        backup = Path(report["private_backup"])
        self.addCleanup(shutil.rmtree, backup)
        self.assertEqual(prepared.entries[0]["original"], (backup / "codex.original").read_bytes())

    def profile_fixture(self):
        (self.repo / "profiles").mkdir()
        (self.repo / "contracts").mkdir()
        shutil.copyfile(ROOT / "profiles/current-observed-defaults.json", self.repo / "profiles/current-observed-defaults.json")
        shutil.copyfile(ROOT / "contracts/model-profile.schema.json", self.repo / "contracts/model-profile.schema.json")
        snapshot = Path(self.temporary.name) / "capture"
        for host in ("codex", "hermes"):
            path = snapshot / "hosts" / host / "config.json"
            path.parent.mkdir(parents=True)
            source, fmt, _ = defaults.ADAPTERS[host]
            value = recovery._read_config(self.roots[host] / source, fmt)
            path.write_text(json.dumps(value))
        return snapshot

    def test_profile_refresh_requires_actual_readback_and_matching_capture(self):
        receipt = defaults.apply_defaults(self.prepare(hosts=["codex"]))
        snapshot = self.profile_fixture()
        profile_path = self.repo / "profiles/current-observed-defaults.json"
        before = profile_path.read_bytes()
        candidate = profiles.refresh_observed_profile(self.repo, receipt, snapshot=snapshot)
        self.assertEqual(before, profile_path.read_bytes())
        self.assertEqual("profiles/current-observed-defaults.json", candidate["path"])
        host = candidate["value"]["hosts"]["codex"]
        self.assertEqual(receipt["observations"]["codex"]["model"], host["model"])
        self.assertEqual("known", host["observation"]["time_status"])
        self.assertIsNone(candidate["value"]["hosts"]["omp"]["observation"]["observed_at"])
        stale = snapshot / "hosts/codex/config.json"
        captured = json.loads(stale.read_text())
        captured["model"] = "stale-model"
        stale.write_text(json.dumps(captured))
        with self.assertRaisesRegex(profiles.ProfileError, "differs from live"):
            profiles.refresh_observed_profile(self.repo, receipt, snapshot=snapshot)
        with self.assertRaisesRegex(profiles.ProfileError, "successful configured"):
            profiles.refresh_observed_profile(self.repo, {"result": "planned"}, snapshot=snapshot)

    def test_profile_observation_identity_and_timestamp_are_checked(self):
        snapshot = self.profile_fixture()
        source = snapshot / "hosts/codex/config.json"
        observation = {"source": "recovery/current/hosts/codex/config.json",
                       "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                       "observed_at": None}
        profiles._verify_configured_observation(self.repo, "codex", observation, snapshot_dir=snapshot)
        observation["observed_at"] = "2026-10-01T12:00:00"
        with self.assertRaisesRegex(profiles.ProfileError, "timestamp"):
            profiles._verify_configured_observation(self.repo, "codex", observation, snapshot_dir=snapshot)
        observation["observed_at"] = "2026-10-01T12:00:00Z"
        source.write_text("changed source")
        with self.assertRaisesRegex(profiles.ProfileError, "identity changed"):
            profiles._verify_configured_observation(self.repo, "codex", observation, snapshot_dir=snapshot)


if __name__ == "__main__":
    unittest.main()
