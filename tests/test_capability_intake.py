from __future__ import annotations

import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def load_tool(name: str):
    path = REPO / "tools" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"test_{name}_tool", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


def write_skill(root: Path, name: str, body: str = "body") -> None:
    target = root / "skills" / name
    target.mkdir(parents=True, exist_ok=True)
    (target / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: Use for {name}.\nlicense: MIT\n---\n\n{body}\n",
        encoding="utf-8",
    )


def tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


class CapabilityIntakeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.intake = load_tool("capability_intake")
        self.fleet = load_tool("fleet")
        self.recovery = load_tool("recovery")

    def test_scan_classifies_live_drift_without_mutation_or_content_leak(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = root / "repo"
            hermes_home = root / "hermes"
            live_skills = root / "shared-skills"
            repo.mkdir()
            hermes_home.mkdir()

            policy = {
                "schema_version": 1,
                "machine": "test",
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
                                "include": ["agent.reasoning_effort"],
                                "strategy": "merge",
                                "portable_paths": False,
                            },
                            {
                                "id": "standing-instructions",
                                "kind": "text",
                                "source": "SOUL.md",
                                "snapshot": "hosts/hermes/SOUL.md",
                                "format": "text",
                                "include": [],
                                "strategy": "replace-if-absent",
                                "portable_paths": False,
                            },
                        ]
                    }
                },
            }
            (repo / "recovery.json").write_text(json.dumps(policy), encoding="utf-8")
            (hermes_home / "config.yaml").write_text(
                "agent:\n  reasoning_effort: medium\napi_key: DO_NOT_LEAK\n",
                encoding="utf-8",
            )
            (hermes_home / "SOUL.md").write_text("original private instruction\n", encoding="utf-8")
            self.recovery.snapshot(
                repo / "recovery.json",
                repo / "recovery" / "current",
                {"hermes": hermes_home},
                repo_root=repo,
            )
            (hermes_home / "config.yaml").write_text(
                "agent:\n  reasoning_effort: high\napi_key: DO_NOT_LEAK\n",
                encoding="utf-8",
            )
            (hermes_home / "SOUL.md").write_text("changed private instruction\n", encoding="utf-8")

            write_skill(repo, "kept")
            write_skill(repo, "staged")
            (repo / "registry.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "skills": [
                            {"name": "kept", "status": "admitted"},
                            {"name": "staged", "status": "staged"},
                        ],
                    }
                ),
                encoding="utf-8",
            )
            (repo / "fleet.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "snapshot_root": "render/fleet",
                        "machines": {
                            "local-windows": {
                                "skill_roots": ["{SHARED_SKILLS_HOME}"],
                                "hosts": ["hermes", "codex", "omp"],
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
            snapshot = repo / "render" / "fleet"
            self.fleet.render_snapshot(repo, snapshot)
            self.fleet.apply_snapshot(snapshot, live_skills)
            (live_skills / "kept" / "SKILL.md").write_text("local private edit\n", encoding="utf-8")
            (live_skills / "unmanaged-new" / "SKILL.md").parent.mkdir(parents=True)
            (live_skills / "unmanaged-new" / "SKILL.md").write_text(
                "---\nname: unmanaged-new\ndescription: private body\n---\n",
                encoding="utf-8",
            )

            before = tree_digest(root)
            first = self.intake.scan(
                repo,
                machine="local-windows",
                recovery_roots={"hermes": hermes_home},
                skill_roots=[live_skills],
            )
            second = self.intake.scan(
                repo,
                machine="local-windows",
                recovery_roots={"hermes": hermes_home},
                skill_roots=[live_skills],
            )
            after = tree_digest(root)

            self.assertEqual(before, after)
            self.assertEqual(first, second)
            self.assertFalse(first["mutation_performed"])
            encoded = json.dumps(first, sort_keys=True)
            self.assertNotIn("DO_NOT_LEAK", encoded)
            self.assertNotIn("local private edit", encoded)
            self.assertNotIn("changed private instruction", encoded)

            by_key = {(item["surface"], item["target"]): item for item in first["findings"]}
            settings = by_key[("recovery", "config.yaml")]
            self.assertEqual(settings["change_class"], "host-config")
            self.assertEqual(settings["owner"], "recovery:hermes:settings")
            self.assertFalse(settings["auto_apply_eligible"])

            soul = by_key[("recovery", "SOUL.md")]
            self.assertEqual(soul["change_class"], "host-instruction")
            self.assertEqual(soul["route"], "hermes-self-engineering")
            self.assertEqual(soul["disposition"], "review-required")

            kept = by_key[("fleet", "kept")]
            self.assertEqual(kept["change_class"], "managed-skill-conflict")
            self.assertEqual(kept["owner"], "skills/kept")
            self.assertEqual(kept["registry_status"], "admitted")
            self.assertFalse(kept["auto_apply_eligible"])

            unmanaged = by_key[("fleet", "unmanaged-new")]
            self.assertEqual(unmanaged["change_class"], "unmanaged-capability")
            self.assertEqual(unmanaged["route"], "capability-curator")
            self.assertEqual(unmanaged["disposition"], "stage-for-review")
            self.assertFalse(unmanaged["auto_apply_eligible"])

    def test_auto_apply_policy_requires_checked_admitted_existing_owner_action(self) -> None:
        admitted = {"name": "kept", "status": "admitted"}
        safe = self.intake.classify_fleet_action(
            {"name": "kept", "action": "update"},
            admitted,
            destination_id="shared-skills",
            checked=True,
        )
        self.assertTrue(safe["eligible_after_checks"])
        self.assertTrue(safe["auto_apply_eligible"])

        for action in ("conflict", "remove", "forget"):
            finding = self.intake.classify_fleet_action(
                {"name": "kept", "action": action},
                admitted,
                destination_id="shared-skills",
                checked=True,
            )
            self.assertFalse(finding["auto_apply_eligible"])

        staged = self.intake.classify_fleet_action(
            {"name": "staged", "action": "add"},
            {"name": "staged", "status": "staged"},
            destination_id="shared-skills",
            checked=True,
        )
        self.assertFalse(staged["eligible_after_checks"])
        self.assertFalse(staged["auto_apply_eligible"])

        for kwargs in (
            {"cross_host_change": True},
            {"safety_sensitive": True},
            {"ambiguous": True},
        ):
            finding = self.intake.classify_fleet_action(
                {"name": "kept", "action": "update"},
                admitted,
                destination_id="shared-skills",
                checked=True,
                **kwargs,
            )
            self.assertFalse(finding["auto_apply_eligible"])


if __name__ == "__main__":
    unittest.main()
