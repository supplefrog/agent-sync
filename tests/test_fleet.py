from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import jsonschema

REPO = Path(__file__).resolve().parents[1]


def load_fleet():
    path = REPO / "tools" / "fleet.py"
    spec = importlib.util.spec_from_file_location("fleet_tool", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


def skill(root: Path, name: str, body: str = "body") -> None:
    target = root / "skills" / name
    target.mkdir(parents=True, exist_ok=True)
    (target / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: Use for {name}.\nlicense: MIT\n---\n\n{body}\n",
        encoding="utf-8",
    )


def fixture_repo(root: Path) -> Path:
    repo = root / "repo"
    skill(repo, "kept")
    skill(repo, "staged")
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
    return repo


class FleetTests(unittest.TestCase):
    def setUp(self):
        self.fleet = load_fleet()

    def test_fleet_configuration_matches_schema(self):
        schema = json.loads((REPO / "contracts" / "fleet.schema.json").read_text(encoding="utf-8"))
        config = json.loads((REPO / "fleet.json").read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator(schema).validate(config)

    def test_fleet_configuration_rejects_snapshot_parent_escape(self):
        schema = json.loads((REPO / "contracts" / "fleet.schema.json").read_text(encoding="utf-8"))
        config = json.loads((REPO / "fleet.json").read_text(encoding="utf-8"))
        config["snapshot_root"] = "../escape"
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.Draft202012Validator(schema).validate(config)
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp)
            (repo / "fleet.json").write_text(json.dumps(config), encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "safe relative path"):
                self.fleet.load_fleet(repo)

    def test_render_is_deterministic_and_contains_only_admitted_skills(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = fixture_repo(root)
            out = repo / "render" / "fleet"
            first = self.fleet.render_snapshot(repo, out)
            second = self.fleet.render_snapshot(repo, out)

            self.assertEqual(first, second)
            self.assertTrue((out / "skills" / "kept" / "SKILL.md").is_file())
            self.assertFalse((out / "skills" / "staged").exists())
            self.assertEqual(set(first["skills"]), {"kept"})

    def test_render_ignores_generated_python_cache(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = fixture_repo(root)
            cache = repo / "skills" / "kept" / "__pycache__"
            cache.mkdir()
            (cache / "generated.pyc").write_bytes(b"generated")
            out = repo / "render" / "fleet"

            self.fleet.render_snapshot(repo, out)

            self.assertFalse((out / "skills" / "kept" / "__pycache__").exists())

    def test_apply_adopts_matching_content_and_preserves_unmanaged_skills(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = fixture_repo(root)
            snapshot = repo / "render" / "fleet"
            self.fleet.render_snapshot(repo, snapshot)
            destination = root / "live"
            skill(destination.parent, "unmanaged", "leave me")
            # Move the helper-created directory into the actual destination.
            destination.mkdir(exist_ok=True)
            (destination.parent / "skills" / "unmanaged").replace(destination / "unmanaged")
            (destination / "kept").mkdir()
            (destination / "kept" / "SKILL.md").write_bytes(
                (snapshot / "skills" / "kept" / "SKILL.md").read_bytes()
            )

            actions = self.fleet.apply_snapshot(snapshot, destination)

            self.assertIn(("kept", "adopt"), [(a["name"], a["action"]) for a in actions])
            self.assertTrue((destination / "unmanaged" / "SKILL.md").is_file())
            state = json.loads((destination / self.fleet.STATE_FILE).read_text(encoding="utf-8"))
            self.assertEqual(state["source_snapshot"], str(snapshot.resolve()))

    def test_apply_updates_managed_skill_and_removes_clean_retired_skill(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = fixture_repo(root)
            snapshot = repo / "render" / "fleet"
            destination = root / "live"
            self.fleet.render_snapshot(repo, snapshot)
            self.fleet.apply_snapshot(snapshot, destination)

            skill(repo, "kept", "changed")
            self.fleet.render_snapshot(repo, snapshot)
            actions = self.fleet.apply_snapshot(snapshot, destination)
            self.assertIn(("kept", "update"), [(a["name"], a["action"]) for a in actions])
            self.assertIn("changed", (destination / "kept" / "SKILL.md").read_text(encoding="utf-8"))

            registry = json.loads((repo / "registry.json").read_text(encoding="utf-8"))
            registry["skills"][0]["status"] = "staged"
            (repo / "registry.json").write_text(json.dumps(registry), encoding="utf-8")
            self.fleet.render_snapshot(repo, snapshot)
            actions = self.fleet.apply_snapshot(snapshot, destination)
            self.assertIn(("kept", "remove"), [(a["name"], a["action"]) for a in actions])
            self.assertFalse((destination / "kept").exists())

    def test_modified_managed_skill_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = fixture_repo(root)
            snapshot = repo / "render" / "fleet"
            destination = root / "live"
            self.fleet.render_snapshot(repo, snapshot)
            self.fleet.apply_snapshot(snapshot, destination)
            (destination / "kept" / "SKILL.md").write_text("local edit", encoding="utf-8")
            skill(repo, "kept", "upstream edit")
            self.fleet.render_snapshot(repo, snapshot)

            plan = self.fleet.plan_snapshot(snapshot, destination)
            self.assertEqual(plan[0]["action"], "conflict")
            with self.assertRaisesRegex(RuntimeError, "managed skill drift"):
                self.fleet.apply_snapshot(snapshot, destination)
            self.assertEqual((destination / "kept" / "SKILL.md").read_text(encoding="utf-8"), "local edit")

    def test_same_name_non_skill_file_is_a_conflict(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = fixture_repo(root)
            snapshot = repo / "render" / "fleet"
            destination = root / "live"
            destination.mkdir()
            (destination / "kept").write_text("unmanaged", encoding="utf-8")
            self.fleet.render_snapshot(repo, snapshot)

            self.assertEqual(self.fleet.plan_snapshot(snapshot, destination)[0]["action"], "conflict")
            with self.assertRaisesRegex(RuntimeError, "collision"):
                self.fleet.apply_snapshot(snapshot, destination)
            self.assertEqual((destination / "kept").read_text(encoding="utf-8"), "unmanaged")

    def test_state_write_failure_rolls_back_all_skill_mutations(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = fixture_repo(root)
            snapshot = repo / "render" / "fleet"
            destination = root / "live"
            self.fleet.render_snapshot(repo, snapshot)
            self.fleet.apply_snapshot(snapshot, destination)
            original = (destination / "kept" / "SKILL.md").read_text(encoding="utf-8")
            skill(repo, "kept", "changed")
            self.fleet.render_snapshot(repo, snapshot)

            with patch.object(self.fleet, "atomic_json", side_effect=OSError("state failed")):
                with self.assertRaisesRegex(OSError, "state failed"):
                    self.fleet.apply_snapshot(snapshot, destination)
            self.assertEqual((destination / "kept" / "SKILL.md").read_text(encoding="utf-8"), original)
            self.assertFalse(any(path.name.startswith(".kept.fleet-") for path in destination.iterdir()))

    def test_registry_skill_name_cannot_escape_source_or_destination(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = fixture_repo(root)
            data = json.loads((repo / "registry.json").read_text(encoding="utf-8"))
            data["skills"][0]["name"] = "../escape"
            (repo / "registry.json").write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "invalid or duplicate"):
                self.fleet.render_snapshot(repo, repo / "render" / "fleet")

    def test_matching_destination_reconciles_stale_state(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = fixture_repo(root)
            snapshot = repo / "render" / "fleet"
            destination = root / "live"
            self.fleet.render_snapshot(repo, snapshot)
            self.fleet.apply_snapshot(snapshot, destination)
            state_path = destination / self.fleet.STATE_FILE
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state["skills"]["kept"]["sha256"] = "0" * 64
            state_path.write_text(json.dumps(state), encoding="utf-8")

            plan = self.fleet.plan_snapshot(snapshot, destination)
            self.assertEqual(plan[0]["action"], "reconcile")
            self.assertIn("untracked", {item["status"] for item in self.fleet.verify_snapshot(snapshot, destination)})
            state["manifest_sha256"] = "stale"
            state_path.write_text(json.dumps(state), encoding="utf-8")
            self.assertIn("manifest-drift", {item["status"] for item in self.fleet.verify_snapshot(snapshot, destination)})
            self.fleet.apply_snapshot(snapshot, destination)
            self.assertEqual(self.fleet.verify_snapshot(snapshot, destination), [])

    def test_apply_repairs_stale_source_snapshot_pointer(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = fixture_repo(root)
            snapshot = repo / "render" / "fleet"
            destination = root / "live"
            self.fleet.render_snapshot(repo, snapshot)
            self.fleet.apply_snapshot(snapshot, destination)
            state_path = destination / self.fleet.STATE_FILE
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state["source_snapshot"] = str(root / "old-checkout" / "render" / "fleet")
            state_path.write_text(json.dumps(state), encoding="utf-8")

            plan = self.fleet.plan_snapshot(snapshot, destination)
            self.assertIn("reconcile-state", {item["action"] for item in plan})
            findings = self.fleet.verify_snapshot(snapshot, destination)
            self.assertIn("source-drift", {item["status"] for item in findings})
            self.fleet.apply_snapshot(snapshot, destination)
            repaired = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(repaired["source_snapshot"], str(snapshot.resolve()))

    def test_verify_detects_missing_and_drifted_managed_skills(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = fixture_repo(root)
            snapshot = repo / "render" / "fleet"
            destination = root / "live"
            self.fleet.render_snapshot(repo, snapshot)
            self.fleet.apply_snapshot(snapshot, destination)
            self.assertEqual(self.fleet.verify_snapshot(snapshot, destination), [])
            (destination / "kept" / "SKILL.md").write_text("drift", encoding="utf-8")
            self.assertEqual(self.fleet.verify_snapshot(snapshot, destination)[0]["status"], "drift")

    @unittest.skipUnless(sys.platform == "win32", "Windows junction behavior")
    def test_retiring_an_adopted_windows_junction_preserves_source(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = fixture_repo(root)
            snapshot = repo / "render" / "fleet"
            destination = root / "live"
            destination.mkdir()
            source = repo / "skills" / "kept"
            target = destination / "kept"
            created = subprocess.run(
                ["cmd", "/c", "mklink", "/J", str(target), str(source)],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(created.returncode, 0, created.stdout + created.stderr)
            self.fleet.render_snapshot(repo, snapshot)
            self.fleet.apply_snapshot(snapshot, destination)
            self.assertFalse(self.fleet.is_linklike_directory(target))
            registry = json.loads((repo / "registry.json").read_text(encoding="utf-8"))
            registry["skills"][0]["status"] = "staged"
            (repo / "registry.json").write_text(json.dumps(registry), encoding="utf-8")
            self.fleet.render_snapshot(repo, snapshot)

            self.fleet.apply_snapshot(snapshot, destination)

            self.assertFalse(target.exists())
            self.assertTrue((source / "SKILL.md").is_file())

    @unittest.skipUnless(sys.platform == "win32", "Windows junction behavior")
    def test_render_rejects_admitted_skill_root_junction(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = fixture_repo(root)
            source = repo / "skills" / "kept"
            source.rename(repo / "skills" / "kept-original")
            outside = root / "outside-skill"
            outside.mkdir()
            (outside / "SKILL.md").write_text("outside-secret", encoding="utf-8")
            created = subprocess.run(
                ["cmd", "/c", "mklink", "/J", str(source), str(outside)],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(created.returncode, 0, created.stdout + created.stderr)

            with self.assertRaisesRegex(RuntimeError, "link or junction|reparse"):
                self.fleet.render_snapshot(repo, repo / "render" / "fleet")

    @unittest.skipUnless(sys.platform == "win32", "Windows junction behavior")
    def test_render_rejects_junction_in_output_path_without_touching_external_files(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = fixture_repo(root)
            external = root / "external"
            target = external / "fleet"
            target.mkdir(parents=True)
            marker = target / "marker.txt"
            marker.write_text("preserve", encoding="utf-8")
            created = subprocess.run(
                ["cmd", "/c", "mklink", "/J", str(repo / "render"), str(external)],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(created.returncode, 0, created.stdout + created.stderr)

            with self.assertRaisesRegex(RuntimeError, "output.*link|junction|reparse"):
                self.fleet.render_snapshot(repo, repo / "render" / "fleet")
            self.assertEqual(marker.read_text(encoding="utf-8"), "preserve")

    def test_render_rejects_snapshot_path_outside_repository(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = fixture_repo(root)
            with self.assertRaisesRegex(RuntimeError, "inside the repository"):
                self.fleet.render_snapshot(repo, root / "escape")
            self.assertFalse((root / "escape").exists())

    def test_all_destinations_are_preflighted_before_first_apply(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = fixture_repo(root)
            snapshot = repo / "render" / "fleet"
            first = root / "first"
            second = root / "second"
            second.mkdir()
            (second / "kept").write_text("collision", encoding="utf-8")
            self.fleet.render_snapshot(repo, snapshot)

            with self.assertRaisesRegex(RuntimeError, "collision"):
                self.fleet.apply_destinations(snapshot, [first, second])
            self.assertFalse(first.exists())
            self.assertEqual((second / "kept").read_text(encoding="utf-8"), "collision")

    def test_tampered_state_cannot_escape_destination(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = fixture_repo(root)
            snapshot = repo / "render" / "fleet"
            destination = root / "live"
            destination.mkdir()
            self.fleet.render_snapshot(repo, snapshot)
            (destination / self.fleet.STATE_FILE).write_text(
                json.dumps({"schema_version": 1, "skills": {"../escape": {"sha256": "0" * 64}}}),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(RuntimeError, "invalid skill name"):
                self.fleet.plan_snapshot(snapshot, destination)


if __name__ == "__main__":
    unittest.main()
