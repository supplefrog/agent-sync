from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.test_fleet import fixture_repo, load_fleet


def git(repo, *args):
    result = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(result.stderr)
    return result.stdout.strip()


class SourceOriginTests(unittest.TestCase):
    def setUp(self):
        self.fleet = load_fleet()
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = fixture_repo(self.root)
        git(self.repo, "init")
        git(self.repo, "config", "user.name", "Fixture")
        git(self.repo, "config", "user.email", "fixture@example.invalid")
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-m", "fixture")
        self.old = self.repo / "render" / "fleet"
        self.fleet.render_snapshot(self.repo, self.old)
        common = Path(git(self.repo, "rev-parse", "--path-format=absolute", "--git-common-dir"))
        self.published = common / "agent-signal-published"
        git(self.repo, "worktree", "add", "--detach", str(self.published), "HEAD")
        self.new = self.published / "render" / "fleet"
        self.fleet.render_snapshot(self.published, self.new)
        self.live = self.root / "live"
        self.fleet.apply_snapshot(self.old, self.live)
        state = self.fleet.load_state(self.live)
        state["extra"] = {"preserve": True}
        state["skills"]["kept"]["source_snapshot"] = "owner-specific-origin"
        state["skills"]["kept"]["manifest_sha256"] = "a" * 64
        self.fleet.atomic_json(self.live / self.fleet.STATE_FILE, state)
        (self.live / "unmanaged").mkdir()
        (self.live / "unmanaged" / "SKILL.md").write_text("unrelated")

    def test_same_repository_preserves_all_records_and_installed_content(self):
        before = self.fleet.load_state(self.live)
        content = self.fleet.path_identity(self.live / "kept")
        unmanaged = self.fleet.path_identity(self.live / "unmanaged")
        expected = self.fleet.state_identity(self.live)
        result = self.fleet.migrate_source_origin(self.new, self.live, expected_state=expected)
        after = self.fleet.load_state(self.live)
        self.assertEqual(result["action"], "migrate-source-origin")
        self.assertEqual(after["source_snapshot"], str(self.new.resolve()))
        self.assertEqual(after["manifest_sha256"], self.fleet.sha256_file(self.new / "manifest.json"))
        self.assertEqual(before["skills"], after["skills"])
        self.assertEqual(before["extra"], after["extra"])
        self.assertEqual(content, self.fleet.path_identity(self.live / "kept"))
        self.assertEqual(unmanaged, self.fleet.path_identity(self.live / "unmanaged"))
        state_id = self.fleet.state_identity(self.live)
        self.assertEqual(self.fleet.migrate_source_origin(self.new, self.live)["action"], "unchanged")
        self.assertEqual(state_id, self.fleet.state_identity(self.live))

    def test_missing_origin_is_rejected_without_mutation(self):
        state = self.fleet.load_state(self.live)
        state.pop("source_snapshot")
        self.fleet.atomic_json(self.live / self.fleet.STATE_FILE, state)
        before = self.fleet.state_identity(self.live)
        with self.assertRaisesRegex(RuntimeError, "missing or invalid"):
            self.fleet.migrate_source_origin(self.new, self.live)
        self.assertEqual(before, self.fleet.state_identity(self.live))

    def test_foreign_origin_is_rejected_without_mutation(self):
        foreign = fixture_repo(self.root / "foreign")
        git(foreign, "init")
        snapshot = foreign / "render" / "fleet"
        self.fleet.render_snapshot(foreign, snapshot)
        state = self.fleet.load_state(self.live)
        state["source_snapshot"] = str(snapshot)
        self.fleet.atomic_json(self.live / self.fleet.STATE_FILE, state)
        before = self.fleet.state_identity(self.live)
        with self.assertRaisesRegex(RuntimeError, "different Git repositories"):
            self.fleet.migrate_source_origin(self.new, self.live)
        self.assertEqual(before, self.fleet.state_identity(self.live))

    def test_nonpersistent_destination_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "persistent published"):
            self.fleet.migrate_source_origin(self.old, self.live)

    def test_invalid_destination_content_is_rejected(self):
        (self.new / "skills" / "kept" / "SKILL.md").write_text("corrupt")
        before = self.fleet.state_identity(self.live)
        with self.assertRaisesRegex(RuntimeError, "does not match manifest"):
            self.fleet.migrate_source_origin(self.new, self.live)
        self.assertEqual(before, self.fleet.state_identity(self.live))

    def test_transaction_state_race_is_rejected(self):
        expected = self.fleet.state_identity(self.live)
        state = self.fleet.load_state(self.live)
        state["racing-writer"] = True
        self.fleet.atomic_json(self.live / self.fleet.STATE_FILE, state)
        with self.assertRaisesRegex(RuntimeError, "transaction backup"):
            self.fleet.migrate_source_origin(self.new, self.live, expected_state=expected)
        self.assertTrue(self.fleet.load_state(self.live)["racing-writer"])

    def test_state_race_before_replace_is_preserved(self):
        atomic = self.fleet.atomic_json
        def racing_atomic(path, value):
            atomic(path, value)
            state = self.fleet.load_state(self.live)
            state["racing-writer"] = True
            atomic(self.live / self.fleet.STATE_FILE, state)
        with patch.object(self.fleet, "atomic_json", side_effect=racing_atomic):
            with self.assertRaisesRegex(RuntimeError, "rollback conflict"):
                self.fleet.migrate_source_origin(self.new, self.live)
        self.assertTrue(self.fleet.load_state(self.live)["racing-writer"])
        self.assertEqual(self.fleet.load_state(self.live)["source_snapshot"], str(self.old.resolve()))

    def test_readback_failure_restores_exact_previous_state_bytes(self):
        before = (self.live / self.fleet.STATE_FILE).read_bytes()
        original = self.fleet.load_state
        calls = 0
        def fail_readback(destination):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise RuntimeError("injected readback failure")
            return original(destination)
        with patch.object(self.fleet, "load_state", side_effect=fail_readback):
            with self.assertRaisesRegex(RuntimeError, "injected readback failure"):
                self.fleet.migrate_source_origin(self.new, self.live)
        self.assertEqual(before, (self.live / self.fleet.STATE_FILE).read_bytes())

    def test_write_failure_after_replace_restores_previous_state_bytes(self):
        before = (self.live / self.fleet.STATE_FILE).read_bytes()
        replace = self.fleet.os.replace
        failed = False
        def fail_after_commit(source, target):
            nonlocal failed
            result = replace(source, target)
            if Path(target) == self.live / self.fleet.STATE_FILE and not failed:
                failed = True
                raise OSError("injected failure after write")
            return result
        with patch.object(self.fleet.os, "replace", side_effect=fail_after_commit):
            with self.assertRaisesRegex(OSError, "injected failure after write"):
                self.fleet.migrate_source_origin(self.new, self.live)
        self.assertEqual(before, (self.live / self.fleet.STATE_FILE).read_bytes())

    def test_write_failure_leaves_previous_state_bytes(self):
        before = (self.live / self.fleet.STATE_FILE).read_bytes()
        replace = self.fleet.os.replace
        def fail_commit(source, target):
            if Path(target) == self.live / self.fleet.STATE_FILE:
                raise OSError("injected write failure")
            return replace(source, target)
        with patch.object(self.fleet.os, "replace", side_effect=fail_commit):
            with self.assertRaisesRegex(OSError, "injected write failure"):
                self.fleet.migrate_source_origin(self.new, self.live)
        self.assertEqual(before, (self.live / self.fleet.STATE_FILE).read_bytes())


if __name__ == "__main__":
    unittest.main()
