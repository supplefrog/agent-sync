from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("recovery", ROOT / "tools" / "recovery.py")
recovery = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(recovery)


def write_policy(path: Path) -> None:
    payload = {
        "$schema": "contracts/recovery.schema.json",
        "schema_version": 1,
        "machine": "test-machine",
        "public_safe": True,
        "hosts": {
            "hermes": {
                "artifacts": [
                    {
                        "id": "settings",
                        "kind": "config",
                        "source": "config.yaml",
                        "snapshot": "hosts/hermes/config.json",
                        "format": "yaml",
                        "strategy": "merge",
                        "include": [
                            "model.default",
                            "model.provider",
                            "agent.max_turns",
                            "security.redact_secrets",
                            "terminal.cwd",
                        ],
                    },
                    {
                        "id": "standing-instructions",
                        "kind": "text",
                        "source": "SOUL.md",
                        "snapshot": "hosts/hermes/SOUL.md",
                        "format": "text",
                        "strategy": "replace-if-absent",
                    },
                ]
            },
            "codex": {
                "artifacts": [
                    {
                        "id": "settings",
                        "kind": "config",
                        "source": "config.toml",
                        "snapshot": "hosts/codex/config.json",
                        "format": "toml",
                        "strategy": "merge",
                        "include": ["model", "model_provider", "features.multi_agent"],
                    },
                    {
                        "id": "global-instructions",
                        "kind": "text",
                        "source": "AGENTS.md",
                        "snapshot": "hosts/codex/AGENTS.md",
                        "format": "text",
                        "strategy": "replace-if-absent",
                    },
                ]
            },
            "omp": {
                "artifacts": [
                    {
                        "id": "settings",
                        "kind": "config",
                        "source": "config.yml",
                        "snapshot": "hosts/omp/config.json",
                        "format": "yaml",
                        "strategy": "merge",
                        "include": ["defaultProvider", "defaultModel", "thinkingLevel"],
                    },
                    {
                        "id": "rules",
                        "kind": "text",
                        "source": "RULES.md",
                        "snapshot": "hosts/omp/RULES.md",
                        "format": "text",
                        "strategy": "replace-if-absent",
                    },
                ]
            },
        },
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


class RecoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.policy = self.base / "recovery.json"
        self.snapshot = self.base / "snapshot"
        self.hermes = self.base / "home" / "hermes"
        self.codex = self.base / "home" / ".codex"
        self.omp = self.base / "home" / ".omp" / "agent"
        for path in (self.hermes, self.codex, self.omp):
            path.mkdir(parents=True)
        write_policy(self.policy)
        (self.hermes / "config.yaml").write_text(
            yaml.safe_dump(
                {
                    "model": {
                        "default": "gpt-5.6-sol",
                        "provider": "openai-codex",
                        "api_key": "never-copy-this",
                    },
                    "agent": {"max_turns": 500},
                    "security": {"redact_secrets": True},
                    "terminal": {"cwd": str(self.base / "home" / "work")},
                    "sessions": {"last_id": "private-session"},
                },
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        (self.hermes / "SOUL.md").write_text("Lead with the conclusion.\n", encoding="utf-8")
        (self.codex / "config.toml").write_text(
            'model = "gpt-5.6-sol"\nmodel_provider = "openai-codex"\n'
            '[features]\nmulti_agent = true\n'
            '[mcp_servers.private]\ntoken = "never-copy-this"\n',
            encoding="utf-8",
        )
        (self.codex / "AGENTS.md").write_text("Verify before claiming success.\n", encoding="utf-8")
        (self.omp / "config.yml").write_text(
            yaml.safe_dump(
                {
                    "defaultProvider": "openai-codex",
                    "defaultModel": "gpt-5.6-sol",
                    "thinkingLevel": "medium",
                    "session": {"last": "private-session"},
                },
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        (self.omp / "RULES.md").write_text("Return the final result directly.\n", encoding="utf-8")
        self.roots = {"hermes": self.hermes, "codex": self.codex, "omp": self.omp}

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_snapshot_copies_only_allowlisted_state_and_normalizes_home(self) -> None:
        manifest = recovery.snapshot(self.policy, self.snapshot, self.roots)

        hermes_fragment = json.loads((self.snapshot / "hosts/hermes/config.json").read_text("utf-8"))
        self.assertEqual(500, hermes_fragment["agent"]["max_turns"])
        self.assertTrue(hermes_fragment["security"]["redact_secrets"])
        self.assertEqual(
            "{{agent-signal:HOME}}/work",
            hermes_fragment["terminal"]["cwd"].replace("\\", "/"),
        )
        self.assertNotIn("api_key", json.dumps(hermes_fragment))
        self.assertNotIn("sessions", hermes_fragment)
        self.assertNotIn("never-copy-this", json.dumps(manifest))
        self.assertEqual(6, len(manifest["artifacts"]))
        recovery.verify_snapshot(self.policy, self.snapshot)

    def test_text_snapshot_canonicalizes_crlf_without_live_drift(self) -> None:
        (self.hermes / "SOUL.md").write_bytes(b"Lead with the conclusion.\r\n")

        recovery.snapshot(self.policy, self.snapshot, self.roots)

        self.assertEqual(
            b"Lead with the conclusion.\n",
            (self.snapshot / "hosts/hermes/SOUL.md").read_bytes(),
        )
        plan = recovery.restore(self.policy, self.snapshot, self.roots, apply=False)
        self.assertEqual([], plan["changes"])
        self.assertEqual([], plan["conflicts"])

    def test_snapshot_diff_is_clean_against_unchanged_source_configs(self) -> None:
        recovery.snapshot(self.policy, self.snapshot, self.roots)

        plan = recovery.restore(self.policy, self.snapshot, self.roots, apply=False)

        self.assertEqual([], plan["changes"])
        self.assertEqual([], plan["conflicts"])

    def test_semantic_compare_treats_windows_path_separator_runs_as_equal(self) -> None:
        left = {'hook': '& "C:\\\\Users\\\\E\\\\.codex\\\\hooks\\\\guard.py"'}
        right = {'hook': '& "C:/' + 'Users/E/.codex/hooks/guard.py"'}

        self.assertTrue(recovery._semantic_equal(left, right))
        self.assertFalse(recovery._semantic_equal(left, {'hook': 'different command'}))
        root_left = 'ROOT="C:' + r'\\Users\\E\\.codex"' + '\nPATTERN=r"\\\\s+"'
        root_right = 'ROOT="C:/' + 'Users/E/.codex"' + '\nPATTERN=r"\\s+"'
        self.assertFalse(recovery._semantic_equal(root_left, root_right))

    def test_admitted_host_local_skills_are_reported_as_fleet_collisions(self) -> None:
        repo = self.base / "repo"
        repo.mkdir()
        (repo / "registry.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "skills": [
                        {"name": "humanizer", "status": "admitted"},
                        {"name": "dynamic-workflows", "status": "admitted"},
                    ],
                }
            ),
            encoding="utf-8",
        )
        (repo / "recovery.json").write_text(
            json.dumps(
                {
                    "hosts": {
                        "omp": {
                            "artifacts": [
                                {
                                    "kind": "text",
                                    "source": "skills/dynamic-workflows/SKILL.md",
                                }
                            ]
                        }
                    }
                }
            ),
            encoding="utf-8",
        )
        local = self.hermes / "skills" / "creative" / "humanizer"
        local.mkdir(parents=True)
        (local / "SKILL.md").write_text("---\nname: humanizer\n---\n", encoding="utf-8")
        system = self.codex / "skills" / ".system" / "humanizer"
        system.mkdir(parents=True)
        (system / "SKILL.md").write_text("---\nname: humanizer\n---\n", encoding="utf-8")
        adapter = self.omp / "skills" / "dynamic-workflows"
        adapter.mkdir(parents=True)
        (adapter / "SKILL.md").write_text("---\nname: dynamic-workflows\n---\n", encoding="utf-8")

        collisions = recovery.find_admitted_local_skill_collisions(repo, self.roots)

        self.assertEqual({"humanizer": ["hermes:creative/humanizer"]}, collisions)

    def test_retired_host_local_skills_are_reported(self) -> None:
        repo = self.base / "repo"
        repo.mkdir()
        (repo / "contracts").mkdir()
        (repo / "contracts/ownership.json").write_text(
            json.dumps(
                {
                    "retired_artifacts": [
                        {"path": "integrations/hermes/cc-dynamic-workflows", "replacement": "skills/dynamic-workflows"}
                    ]
                }
            ),
            encoding="utf-8",
        )
        local = self.hermes / "skills" / "autonomous-ai-agents" / "cc-dynamic-workflows"
        local.mkdir(parents=True)
        (local / "SKILL.md").write_text("---\nname: cc-dynamic-workflows\n---\n", encoding="utf-8")

        retired = recovery.find_retired_local_skills(repo, self.roots)

        self.assertEqual({"cc-dynamic-workflows": ["hermes:autonomous-ai-agents/cc-dynamic-workflows"]}, retired)

    def test_snapshot_refuses_secret_bearing_allowlist_path(self) -> None:
        payload = json.loads(self.policy.read_text("utf-8"))
        payload["hosts"]["hermes"]["artifacts"][0]["include"].append("model.api_key")
        self.policy.write_text(json.dumps(payload), encoding="utf-8")

        with self.assertRaisesRegex(recovery.RecoveryError, "secret-bearing config path"):
            recovery.snapshot(self.policy, self.snapshot, self.roots)
        self.assertFalse(self.snapshot.exists())

    def test_policy_rejects_duplicate_source_or_snapshot_ownership(self) -> None:
        original = json.loads(self.policy.read_text("utf-8"))
        base = dict(original["hosts"]["hermes"]["artifacts"][0])
        for field in ("source", "snapshot"):
            payload = json.loads(json.dumps(original))
            duplicate = dict(base)
            duplicate["id"] = f"duplicate-{field}"
            if field == "source":
                duplicate["snapshot"] = "hosts/hermes/other-config.json"
            else:
                duplicate["source"] = "other-config.yaml"
            payload["hosts"]["hermes"]["artifacts"].append(duplicate)
            with self.subTest(field=field):
                with self.assertRaisesRegex(recovery.RecoveryError, f"duplicate artifact {field}"):
                    recovery._validate_policy(payload)

    def test_snapshot_refuses_secret_bearing_descendant_of_selected_section(self) -> None:
        payload = json.loads(self.policy.read_text("utf-8"))
        payload["hosts"]["hermes"]["artifacts"][0]["include"] = ["model"]
        self.policy.write_text(json.dumps(payload), encoding="utf-8")

        with self.assertRaisesRegex(recovery.RecoveryError, "secret-bearing config path"):
            recovery.snapshot(self.policy, self.snapshot, self.roots)
        self.assertFalse(self.snapshot.exists())

    def test_snapshot_allows_numeric_compression_token_budget(self) -> None:
        payload = json.loads(self.policy.read_text("utf-8"))
        payload["hosts"]["hermes"]["artifacts"][0]["include"].append("compression")
        self.policy.write_text(json.dumps(payload), encoding="utf-8")
        config = yaml.safe_load((self.hermes / "config.yaml").read_text("utf-8"))
        config["compression"] = {"proactive_prune_tokens": 48000}
        (self.hermes / "config.yaml").write_text(yaml.safe_dump(config), encoding="utf-8")

        recovery.snapshot(self.policy, self.snapshot, self.roots)

        fragment = json.loads((self.snapshot / "hosts/hermes/config.json").read_text("utf-8"))
        self.assertEqual(48000, fragment["compression"]["proactive_prune_tokens"])

    def test_snapshot_rejects_non_numeric_compression_token_budget(self) -> None:
        payload = json.loads(self.policy.read_text("utf-8"))
        payload["hosts"]["hermes"]["artifacts"][0]["include"].append("compression")
        self.policy.write_text(json.dumps(payload), encoding="utf-8")
        config = yaml.safe_load((self.hermes / "config.yaml").read_text("utf-8"))
        config["compression"] = {"proactive_prune_tokens": "not-an-integer"}
        (self.hermes / "config.yaml").write_text(yaml.safe_dump(config), encoding="utf-8")

        with self.assertRaisesRegex(recovery.RecoveryError, "token-budget config path"):
            recovery.snapshot(self.policy, self.snapshot, self.roots)
        self.assertFalse(self.snapshot.exists())

    def test_policy_rejects_plural_sensitive_source_names(self) -> None:
        original = json.loads(self.policy.read_text("utf-8"))
        for source in (
            "credentials.json",
            "sessions.json",
            "memories.json",
            "histories.json",
            "logs/output.json",
            "passwords.json",
            "tokens.json",
            "api_keys.json",
            "private_keys.json",
            "oauth.json",
            "oauths.json",
            "pairing.json",
            "pairings.json",
        ):
            payload = json.loads(json.dumps(original))
            payload["hosts"]["hermes"]["artifacts"][0]["source"] = source
            with self.subTest(source=source):
                with self.assertRaisesRegex(recovery.RecoveryError, "blocked source artifact"):
                    recovery._validate_policy(payload)
        for dotted in (
            "model.api_keys",
            "model.tokens",
            "model.passwords",
            "model.passwds",
            "model.secrets",
            "model.credentials",
            "model.private_keys",
            "model.session_keys",
            "model.cookies",
            "model.oauth",
            "model.oauths",
            "model.pairing",
            "model.pairings",
            "model.session",
            "model.sessions",
            "model.memory",
            "model.memories",
        ):
            payload = json.loads(json.dumps(original))
            payload["hosts"]["hermes"]["artifacts"][0]["include"].append(dotted)
            with self.subTest(dotted=dotted):
                with self.assertRaisesRegex(recovery.RecoveryError, "secret-bearing config path"):
                    recovery._validate_policy(payload)

    def test_snapshot_allows_secret_environment_variable_names_not_values(self) -> None:
        payload = json.loads(self.policy.read_text("utf-8"))
        payload["hosts"]["hermes"]["artifacts"][0]["include"].append("model.api_key_env")
        self.policy.write_text(json.dumps(payload), encoding="utf-8")
        config = yaml.safe_load((self.hermes / "config.yaml").read_text("utf-8"))
        config["model"]["api_key_env"] = "OPENAI_API_KEY"
        (self.hermes / "config.yaml").write_text(yaml.safe_dump(config), encoding="utf-8")

        recovery.snapshot(self.policy, self.snapshot, self.roots)
        fragment = json.loads((self.snapshot / "hosts/hermes/config.json").read_text("utf-8"))
        self.assertEqual("OPENAI_API_KEY", fragment["model"]["api_key_env"])

    def test_snapshot_refuses_secret_in_text_before_writing_anything(self) -> None:
        mock_token = "sk" + "-mock-not-a-real-secret-value"
        (self.hermes / "SOUL.md").write_text(f"Use token {mock_token}\n", encoding="utf-8")

        with self.assertRaisesRegex(recovery.RecoveryError, "public-safety"):
            recovery.snapshot(self.policy, self.snapshot, self.roots)
        self.assertFalse(self.snapshot.exists())

    def test_portable_text_artifact_normalizes_and_restores_home_paths(self) -> None:
        payload = json.loads(self.policy.read_text("utf-8"))
        payload["hosts"]["codex"]["artifacts"].append(
            {
                "id": "safety-hook",
                "kind": "text",
                "source": "hooks/safety.py",
                "snapshot": "hosts/codex/hooks/safety.py",
                "format": "text",
                "strategy": "replace-if-absent",
                "portable_paths": True,
            }
        )
        self.policy.write_text(json.dumps(payload), encoding="utf-8")
        (self.codex / "hooks").mkdir()
        script_root = str(self.base / "home" / ".codex").replace("\\", "/")
        (self.codex / "hooks/safety.py").write_text(
            f'ROOT = r"{script_root}"\nPATTERN = r"\\s+\\${{HOME}}"\n',
            encoding="utf-8",
        )

        recovery.snapshot(self.policy, self.snapshot, self.roots)
        saved = (self.snapshot / "hosts/codex/hooks/safety.py").read_text("utf-8")
        self.assertIn("{{agent-signal:CODEX_HOME}}", saved)
        self.assertNotIn(str(self.base), saved)
        self.assertIn(r'PATTERN = r"\s+\${HOME}"', saved)
        same_source = recovery.restore(self.policy, self.snapshot, self.roots, apply=False)
        self.assertEqual([], same_source["changes"])
        self.assertEqual([], same_source["conflicts"])

        fresh = self.base / "restore"
        roots = {"hermes": fresh / "hermes", "codex": fresh / ".codex", "omp": fresh / ".omp/agent"}
        for root in roots.values():
            root.mkdir(parents=True)
        recovery.restore(self.policy, self.snapshot, roots, apply=True)
        restored = (roots["codex"] / "hooks/safety.py").read_text("utf-8")
        self.assertIn(str(roots["codex"]), restored)
        self.assertIn(r'PATTERN = r"\s+\${HOME}"', restored)

    def test_snapshot_rejects_path_escape_and_symlink_crossing(self) -> None:
        payload = json.loads(self.policy.read_text("utf-8"))
        payload["hosts"]["hermes"]["artifacts"][1]["source"] = "../SOUL.md"
        self.policy.write_text(json.dumps(payload), encoding="utf-8")
        with self.assertRaisesRegex(recovery.RecoveryError, "relative canonical path"):
            recovery.snapshot(self.policy, self.snapshot, self.roots)

        write_policy(self.policy)
        target = self.base / "outside.md"
        target.write_text("outside\n", encoding="utf-8")
        (self.hermes / "SOUL.md").unlink()
        try:
            os.symlink(target, self.hermes / "SOUL.md")
        except (OSError, NotImplementedError):
            self.skipTest("symlinks unavailable")
        with self.assertRaisesRegex(recovery.RecoveryError, "reparse|symlink"):
            recovery.snapshot(self.policy, self.snapshot, self.roots)

    @unittest.skipUnless(os.name == "nt", "Windows junction regression")
    def test_snapshot_rejects_a_windows_junction_used_as_a_host_root(self) -> None:
        junction = self.base / "hermes-junction"
        created = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(junction), str(self.hermes)],
            capture_output=True,
            text=True,
            check=False,
        )
        if created.returncode != 0:
            self.skipTest("junction creation unavailable")
        roots = dict(self.roots)
        roots["hermes"] = junction
        try:
            with self.assertRaisesRegex(recovery.RecoveryError, "root.*reparse|reparse.*root"):
                recovery.snapshot(self.policy, self.snapshot, roots)
        finally:
            subprocess.run(["cmd", "/c", "rmdir", str(junction)], check=False)

    def test_verify_detects_tampering(self) -> None:
        recovery.snapshot(self.policy, self.snapshot, self.roots)
        (self.snapshot / "hosts/hermes/SOUL.md").write_text("tampered\n", encoding="utf-8")

        with self.assertRaisesRegex(recovery.RecoveryError, "hash mismatch"):
            recovery.verify_snapshot(self.policy, self.snapshot)

    def test_restore_is_dry_run_by_default_and_merges_without_deleting_private_state(self) -> None:
        recovery.snapshot(self.policy, self.snapshot, self.roots)
        fresh_hermes = self.base / "restore" / "hermes"
        fresh_codex = self.base / "restore" / "codex"
        fresh_omp = self.base / "restore" / "omp"
        for root in (fresh_hermes, fresh_codex, fresh_omp):
            root.mkdir(parents=True)
        (fresh_hermes / "config.yaml").write_text(
            yaml.safe_dump({"model": {"api_key": "keep-me"}, "unmanaged": {"keep": True}}),
            encoding="utf-8",
        )
        roots = {"hermes": fresh_hermes, "codex": fresh_codex, "omp": fresh_omp}

        plan = recovery.restore(self.policy, self.snapshot, roots, apply=False)
        self.assertTrue(plan["changes"])
        self.assertFalse((fresh_hermes / "SOUL.md").exists())

        recovery.restore(self.policy, self.snapshot, roots, apply=True)
        restored = yaml.safe_load((fresh_hermes / "config.yaml").read_text("utf-8"))
        self.assertEqual("keep-me", restored["model"]["api_key"])
        self.assertTrue(restored["unmanaged"]["keep"])
        self.assertEqual(500, restored["agent"]["max_turns"])
        self.assertEqual(str(self.base / "restore" / "work"), restored["terminal"]["cwd"])
        self.assertEqual("Lead with the conclusion.\n", (fresh_hermes / "SOUL.md").read_text("utf-8"))
        self.assertIn('model = "gpt-5.6-sol"', (fresh_codex / "config.toml").read_text("utf-8"))
        self.assertEqual("Return the final result directly.\n", (fresh_omp / "RULES.md").read_text("utf-8"))

    def test_restore_preflights_all_conflicts_before_mutating(self) -> None:
        recovery.snapshot(self.policy, self.snapshot, self.roots)
        restore_root = self.base / "restore" / "hermes"
        restore_root.mkdir(parents=True)
        original_config = yaml.safe_dump({"model": {"provider": "other"}}, sort_keys=False)
        (restore_root / "config.yaml").write_text(original_config, encoding="utf-8")
        (restore_root / "SOUL.md").write_text("local custom instructions\n", encoding="utf-8")
        roots = {"hermes": restore_root, "codex": self.base / "restore/codex", "omp": self.base / "restore/omp"}
        roots["codex"].mkdir(parents=True)
        roots["omp"].mkdir(parents=True)

        with self.assertRaisesRegex(recovery.RecoveryError, "text conflict"):
            recovery.restore(self.policy, self.snapshot, roots, apply=True)
        self.assertEqual(original_config, (restore_root / "config.yaml").read_text("utf-8"))
        self.assertEqual("local custom instructions\n", (restore_root / "SOUL.md").read_text("utf-8"))

    def test_repository_policy_preserves_native_lcm_threshold(self) -> None:
        policy = json.loads((ROOT / "recovery.json").read_text(encoding="utf-8"))
        settings = next(
            artifact
            for artifact in policy["hosts"]["hermes"]["artifacts"]
            if artifact["id"] == "settings"
        )
        self.assertIn("context", settings["include"])
        self.assertIn("lcm.context_threshold", settings["include"])

    def test_restore_can_force_explicit_text_replacement(self) -> None:
        recovery.snapshot(self.policy, self.snapshot, self.roots)
        restore_root = self.base / "restore" / "hermes"
        restore_root.mkdir(parents=True)
        (restore_root / "SOUL.md").write_text("old\n", encoding="utf-8")
        roots = {"hermes": restore_root, "codex": self.base / "restore/codex", "omp": self.base / "restore/omp"}
        roots["codex"].mkdir(parents=True)
        roots["omp"].mkdir(parents=True)

        recovery.restore(self.policy, self.snapshot, roots, apply=True, force_text=True)
        self.assertEqual("Lead with the conclusion.\n", (restore_root / "SOUL.md").read_text("utf-8"))


if __name__ == "__main__":
    unittest.main()
