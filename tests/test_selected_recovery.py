from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("selected_recovery", ROOT / "tools" / "recovery.py")
recovery = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(recovery)

HOSTS = ("hermes", "codex", "omp")


def write_policy(path: Path) -> None:
    hosts = {}
    for host in HOSTS:
        extension = "yaml" if host != "codex" else "toml"
        fmt = "yaml" if host != "codex" else "toml"
        hosts[host] = {
            "artifacts": [
                {
                    "id": "settings",
                    "kind": "config",
                    "source": f"config.{extension}",
                    "snapshot": f"hosts/{host}/config.json",
                    "format": fmt,
                    "strategy": "merge",
                    "include": ["model.default", "safe.value"],
                },
                {
                    "id": "instructions",
                    "kind": "text",
                    "source": "INSTRUCTIONS.md",
                    "snapshot": f"hosts/{host}/INSTRUCTIONS.md",
                    "format": "text",
                    "strategy": "replace-if-absent",
                },
            ]
        }
    path.write_text(
        json.dumps(
            {
                "$schema": "contracts/recovery.schema.json",
                "schema_version": 1,
                "machine": "test-machine",
                "public_safe": True,
                "hosts": hosts,
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def write_config(path: Path, host: str, *, private: str = "private") -> None:
    value = {
        "model": {"default": f"{host}-model", "api_key": private},
        "safe": {"value": host},
        "sessions": {"last_id": f"{host}-session"},
    }
    if path.suffix == ".toml":
        path.write_text(
            f'model = {{ default = "{host}-model", api_key = "{private}" }}\n'
            f'[safe]\nvalue = "{host}"\n'
            f'[sessions]\nlast_id = "{host}-session"\n',
            encoding="utf-8",
        )
    else:
        path.write_text(yaml.safe_dump(value, sort_keys=False), encoding="utf-8")


def make_state(base: Path) -> tuple[Path, Path, dict[str, Path]]:
    policy = base / "recovery.json"
    snapshot = base / "snapshot"
    source_base = base / "source"
    roots = {host: source_base / host for host in HOSTS}
    for host, root in roots.items():
        root.mkdir(parents=True)
        write_config(root / ("config.toml" if host == "codex" else "config.yaml"), host)
        (root / "INSTRUCTIONS.md").write_text(f"{host} instructions\n", encoding="utf-8")
    write_policy(policy)
    recovery.snapshot(policy, snapshot, roots, repo_root=base)
    return policy, snapshot, roots


class SelectedRestoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.policy, self.snapshot, self.sources = make_state(self.base)
        self.targets = {host: self.base / "target" / host for host in HOSTS}
        for root in self.targets.values():
            root.mkdir(parents=True)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_selected_restore_only_reads_writes_selected_host_and_is_idempotent(self) -> None:
        hermes = self.targets["hermes"]
        write_config(hermes / "config.yaml", "old-hermes", private="keep-hermes-secret")
        (hermes / "unmanaged.txt").write_text("keep", encoding="utf-8")
        (self.targets["codex"] / "config.toml").write_bytes(b"not valid utf-8: \x80")
        (self.targets["omp"] / "config.yaml").write_bytes(b"not valid yaml: \x80")
        unrelated = {
            host: {
                path.name: path.read_bytes()
                for path in path_root.iterdir()
                if path.is_file()
            }
            for host, path_root in self.targets.items()
            if host != "hermes"
        }

        plan = recovery.restore(
            self.policy,
            self.snapshot,
            self.targets,
            hosts=["hermes"],
            apply=True,
            repo_root=self.base,
        )

        self.assertTrue(plan["changes"])
        self.assertEqual({"hermes"}, {item["host"] for item in plan["changes"]})
        restored = yaml.safe_load((hermes / "config.yaml").read_text("utf-8"))
        self.assertEqual("keep-hermes-secret", restored["model"]["api_key"])
        self.assertEqual("keep", (hermes / "unmanaged.txt").read_text("utf-8"))
        self.assertEqual("hermes-model", restored["model"]["default"])
        self.assertEqual("hermes instructions\n", (hermes / "INSTRUCTIONS.md").read_text("utf-8"))
        for host, files in unrelated.items():
            self.assertEqual(files, {path.name: path.read_bytes() for path in self.targets[host].iterdir()})

        second = recovery.restore(
            self.policy,
            self.snapshot,
            self.targets,
            hosts=["hermes"],
            apply=False,
            repo_root=self.base,
        )
        self.assertEqual([], second["changes"])
        self.assertEqual([], second["conflicts"])

    def test_selected_restore_still_validates_the_complete_snapshot(self) -> None:
        (self.snapshot / "hosts/codex/INSTRUCTIONS.md").write_text("tampered\n", encoding="utf-8")

        with self.assertRaisesRegex(recovery.RecoveryError, "hash mismatch"):
            recovery.restore(
                self.policy,
                self.snapshot,
                self.targets,
                hosts=["hermes"],
                apply=False,
                repo_root=self.base,
            )
        self.assertFalse((self.targets["hermes"] / "INSTRUCTIONS.md").exists())

    def test_selected_restore_conflicts_and_unsafe_paths_fail_closed(self) -> None:
        hermes = self.targets["hermes"]
        (hermes / "INSTRUCTIONS.md").write_text("local instructions\n", encoding="utf-8")
        original = (hermes / "INSTRUCTIONS.md").read_bytes()
        with self.assertRaisesRegex(recovery.RecoveryError, "text conflict"):
            recovery.restore(
                self.policy,
                self.snapshot,
                self.targets,
                hosts=["hermes"],
                apply=True,
                repo_root=self.base,
            )
        self.assertEqual(original, (hermes / "INSTRUCTIONS.md").read_bytes())

        (hermes / "INSTRUCTIONS.md").unlink()
        outside = self.base / "outside.md"
        outside.write_text("outside\n", encoding="utf-8")
        try:
            os.symlink(outside, hermes / "INSTRUCTIONS.md")
        except (OSError, NotImplementedError):
            self.skipTest("symlinks unavailable")
        with self.assertRaisesRegex(recovery.RecoveryError, "reparse|symlink"):
            recovery.restore(
                self.policy,
                self.snapshot,
                self.targets,
                hosts=["hermes"],
                apply=True,
                repo_root=self.base,
            )
        self.assertEqual("outside\n", outside.read_text("utf-8"))

    def test_invalid_unselected_host_policy_is_not_hidden_by_selection(self) -> None:
        payload = json.loads(self.policy.read_text("utf-8"))
        payload["hosts"]["codex"]["artifacts"][1]["source"] = "../escape.md"
        self.policy.write_text(json.dumps(payload), encoding="utf-8")

        with self.assertRaisesRegex(recovery.RecoveryError, "relative canonical path"):
            recovery.restore(
                self.policy,
                self.snapshot,
                self.targets,
                hosts=["hermes"],
                apply=False,
                repo_root=self.base,
            )


    def test_reviewed_stock_bytes_can_be_replaced_but_unknown_edits_cannot(self):
        stock = b"stock instructions\n"
        policy = json.loads(self.policy.read_text())
        policy["hosts"]["hermes"]["artifacts"][1]["replace_sha256"] = [hashlib.sha256(stock).hexdigest()]
        self.policy.write_text(json.dumps(policy))
        recovery.snapshot(self.policy, self.snapshot, self.sources, repo_root=self.base)
        target = self.targets["hermes"] / "INSTRUCTIONS.md"
        target.write_bytes(stock)
        recovery.restore(self.policy, self.snapshot, self.targets, hosts=["hermes"], apply=True)
        self.assertEqual("hermes instructions\n", target.read_text())
        target.write_text("recipient's own changes\n")
        with self.assertRaisesRegex(recovery.RecoveryError, "text conflict"):
            recovery.restore(self.policy, self.snapshot, self.targets, hosts=["hermes"], apply=True)
        self.assertEqual("recipient's own changes\n", target.read_text())


class SelectedBootstrapTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.previous_recovery_module = sys.modules.get("recovery")
        sys.modules["recovery"] = recovery
        self.repo = self.base / "repo"
        self.repo.mkdir()
        (self.repo / "tools").mkdir()
        (self.repo / "contracts").mkdir()
        shutil.copy2(ROOT / "tools/fleet.py", self.repo / "tools/fleet.py")
        shutil.copy2(ROOT / "tools/host_deltas.py", self.repo / "tools/host_deltas.py")
        for name in (
            "fleet.schema.json",
            "host-deltas.schema.json",
            "recovery.schema.json",
            "recovery-snapshot.schema.json",
        ):
            shutil.copy2(ROOT / "contracts" / name, self.repo / "contracts" / name)
        (self.repo / "skills" / "portable").mkdir(parents=True)
        (self.repo / "skills" / "portable" / "SKILL.md").write_text(
            "---\nname: portable\ndescription: Use for portable test behavior.\n---\n\nportable\n",
            encoding="utf-8",
        )
        (self.repo / "registry.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "skills": [{"name": "portable", "status": "admitted"}],
                }
            ),
            encoding="utf-8",
        )
        (self.repo / "contracts" / "ownership.json").write_text(
            json.dumps({"retired_artifacts": []}), encoding="utf-8"
        )
        (self.repo / "fleet.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "snapshot_root": "render/fleet",
                    "machines": {
                        "local-windows": {
                            "role": "test",
                            "platform": "windows",
                            "skill_roots": ["{SHARED_SKILLS_HOME}"],
                            "hosts": list(HOSTS),
                        }
                    },
                }
            ),
            encoding="utf-8",
        )
        self.policy, self.snapshot, sources = make_state(self.base)
        shutil.copy2(self.policy, self.repo / "recovery.json")
        shutil.copytree(self.snapshot, self.repo / "recovery" / "current")
        self.targets = {host: self.base / "target" / host for host in HOSTS}
        for root in self.targets.values():
            root.mkdir(parents=True)
        (self.targets["hermes"] / "marker.txt").write_text("marker\n", encoding="utf-8")
        self._write_host_deltas()

    def tearDown(self) -> None:
        if self.previous_recovery_module is None:
            sys.modules.pop("recovery", None)
        else:
            sys.modules["recovery"] = self.previous_recovery_module
        self.temp.cleanup()

    def _write_host_deltas(self) -> None:
        def entry(host: str, item_id: str, path: str) -> dict[str, object]:
            return {
                "id": item_id,
                "host": host,
                "category": "settings",
                "owner": "test",
                "source_identity": f"test:{item_id}",
                "version_or_hash": "version:test",
                "enablement": "managed",
                "prerequisites": [],
                "desired_state": "test state",
                "required": True,
                "restore": {"kind": "manual-prerequisite", "reference": "test"},
                "readback": {"kind": "file", "path": path},
                "redaction": "metadata-only",
            }

        (self.repo / "host-deltas.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "machine": "local-windows",
                    "public_safe": True,
                    "entries": [
                        entry("hermes", "hermes-marker", "hermes:marker.txt"),
                        entry("codex", "codex-must-not-read", "codex:missing.txt"),
                        entry("omp", "omp-must-not-read", "omp:missing.txt"),
                    ],
                    "exclusions": [
                        {
                            "id": "hermes-private",
                            "host": "hermes",
                            "category": "private-state",
                            "reason": "kept private",
                        },
                        {
                            "id": "codex-private",
                            "host": "codex",
                            "category": "private-state",
                            "reason": "kept private",
                        },
                    ],
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    def test_selected_bootstrap_applies_real_files_to_target_local_skill_scope(self) -> None:
        live_shared_skill = Path.home() / ".agents" / "skills" / "portable"
        self.assertFalse(live_shared_skill.exists(), "test requires a unique live-scope canary")

        dry_run = recovery.bootstrap(
            self.repo,
            self.repo / "recovery.json",
            self.repo / "recovery/current",
            self.targets,
            hosts=["hermes"],
            apply=False,
        )
        skill_root = Path(dry_run["fleet_skill_root"])
        self.assertFalse(skill_root.exists())
        self.assertEqual({"hermes"}, {item["host"] for item in dry_run["recovery_preflight"]["changes"]})
        self.assertEqual({"hermes"}, {item["host"] for item in dry_run["state_report"]["entries"]})

        result = recovery.bootstrap(
            self.repo,
            self.repo / "recovery.json",
            self.repo / "recovery/current",
            self.targets,
            hosts=["hermes"],
            apply=True,
        )

        self.assertTrue((skill_root / "portable" / "SKILL.md").is_file())
        self.assertFalse(live_shared_skill.exists())
        self.assertTrue(result["state_report"]["passed"])
        self.assertEqual({"hermes"}, {item["host"] for item in result["state_report"]["entries"]})
        self.assertIn("profile", result)
        self.assertEqual("skipped-selected-hosts", result["profile"]["status"])

        second = recovery.bootstrap(
            self.repo,
            self.repo / "recovery.json",
            self.repo / "recovery/current",
            self.targets,
            hosts=["hermes"],
            apply=True,
        )
        self.assertEqual([], second["postflight"]["changes"])
        self.assertEqual([], second["postflight"]["conflicts"])

    def test_selected_bootstrap_does_not_inspect_unselected_local_skill_roots(self) -> None:
        (self.targets["codex"] / "skills").mkdir()
        (self.targets["codex"] / "skills" / "portable").mkdir()
        (self.targets["codex"] / "skills" / "portable" / "SKILL.md").write_bytes(b"\x80")

        result = recovery.bootstrap(
            self.repo,
            self.repo / "recovery.json",
            self.repo / "recovery/current",
            self.targets,
            hosts=["hermes"],
            apply=False,
        )

        self.assertEqual({"hermes"}, {item["host"] for item in result["state_report"]["entries"]})


    def test_default_home_on_receiving_machine_is_a_valid_target(self) -> None:
        # Mock OS discovery only; exercise actual restore and fleet writes.
        with patch.object(Path, "home", return_value=self.base / "target"):
            result = recovery.bootstrap(
                self.repo, self.repo / "recovery.json",
                self.repo / "recovery/current", self.targets,
                hosts=["hermes"], apply=True,
            )
        self.assertTrue((self.base / "target/.agents/skills/portable/SKILL.md").is_file())
        self.assertTrue(result["state_report"]["passed"])


    def test_missing_native_prerequisite_stops_before_target_writes(self):
        (self.targets["hermes"] / "marker.txt").unlink()
        with self.assertRaisesRegex(recovery.RecoveryError, "prerequisite"):
            recovery.bootstrap(
                self.repo, self.repo / "recovery.json", self.repo / "recovery/current",
                self.targets, hosts=["hermes"], apply=True,
            )
        self.assertFalse((self.targets["hermes"] / "INSTRUCTIONS.md").exists())
        self.assertFalse((self.base / "target/.agents/skills").exists())


if __name__ == "__main__":
    unittest.main()
