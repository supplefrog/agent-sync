from pathlib import Path
import json
import os
import tempfile
import unittest
from unittest.mock import patch

import task_artifacts as ta


class CloseoutTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "scratch").mkdir()
        (self.root / "scratch/owned.txt").write_text("temporary")
        (self.root / "deliverable.md").write_text("keep me")
        (self.root / "scratch/other.txt").write_text("other task")

    def claim(self):
        return ta.register(self.root, "task-a", ["scratch/owned.txt"], "scratch", "created by task-a; stale")

    def test_archive_restore_preserves_deliverable_and_unowned_files(self):
        self.claim()
        ta.register(self.root, "task-a", ["deliverable.md"], "keep", "authoritative output")
        report = ta.archive(self.root, "task-a", references_checked=True)
        self.assertFalse((self.root / "scratch/owned.txt").exists())
        self.assertEqual(report["files"][0]["state"], "archived")
        self.assertEqual((self.root / "deliverable.md").read_text(), "keep me")
        self.assertEqual((self.root / "scratch/other.txt").read_text(), "other task")
        ta.restore(self.root, "task-a")
        self.assertEqual((self.root / "scratch/owned.txt").read_text(), "temporary")
        self.assertTrue((self.root / ta.CONTROL / "recovery/task-a/scratch/owned.txt").exists())
        ta.archive(self.root, "task-a", references_checked=True)
        self.assertTrue((self.root / "scratch/owned.txt").exists())

    def test_plan_is_read_only(self):
        before = sorted(p.relative_to(self.root).as_posix() for p in self.root.rglob("*"))
        ta.preview(self.root, "unstarted")
        after = sorted(p.relative_to(self.root).as_posix() for p in self.root.rglob("*"))
        self.assertEqual(before, after)
        self.claim()
        before = (self.root / ta.CONTROL / "task-a.json").read_bytes()
        ta.preview(self.root, "task-a")
        self.assertEqual(before, (self.root / ta.CONTROL / "task-a.json").read_bytes())

    def test_changed_file_blocks_before_any_archive(self):
        self.claim()
        (self.root / "scratch/owned.txt").write_text("new active work")
        with self.assertRaises(ta.Blocked):
            ta.archive(self.root, "task-a", references_checked=True)
        self.assertEqual((self.root / "scratch/owned.txt").read_text(), "new active work")
        self.assertFalse((self.root / ta.CONTROL / "recovery").exists())

    def test_reference_check_required(self):
        self.claim()
        with self.assertRaises(ta.Blocked):
            ta.archive(self.root, "task-a", references_checked=False)
        self.assertTrue((self.root / "scratch/owned.txt").exists())

    def test_other_task_cannot_claim_same_file(self):
        self.claim()
        with self.assertRaises(ta.Blocked):
            ta.register(self.root, "task-b", ["scratch/owned.txt"], "scratch", "another claim")
        self.assertFalse((self.root / ta.CONTROL / "task-b.json").exists())
        ta.register(self.root, "task-b", ["scratch/other.txt"], "scratch", "owned by task-b")
        ta.archive(self.root, "task-a", references_checked=True)
        self.assertTrue((self.root / "scratch/other.txt").exists())

    def test_lock_refuses_concurrent_writer(self):
        self.claim()
        with ta.locked(self.root):
            with self.assertRaises(ta.Blocked):
                ta.archive(self.root, "task-a", references_checked=True)
        self.assertTrue((self.root / "scratch/owned.txt").exists())

    def test_traversal_controls_devices_and_directories_refused(self):
        for path in ["../outside", "scratch/../owned.txt", ".git/config", "C:/secret", "scratch\\owned.txt", "scratch/CON", "scratch/file:stream", "scratch/trailing."]:
            with self.subTest(path=path), self.assertRaises(ta.Blocked):
                ta.register(self.root, "task-a", [path], "scratch", "not valid")
        with self.assertRaises(ta.Blocked):
            ta.register(self.root, "task-a", ["scratch"], "scratch", "not a file")

    def test_restore_collision_keeps_new_work(self):
        self.claim()
        ta.archive(self.root, "task-a", references_checked=True)
        (self.root / "scratch/owned.txt").write_text("new work at old path")
        with self.assertRaises(ta.Blocked):
            ta.restore(self.root, "task-a")
        self.assertEqual((self.root / "scratch/owned.txt").read_text(), "new work at old path")

    def test_interruption_after_verified_copy_resumes(self):
        self.claim()
        original = ta.copy_new
        def interrupted(*args):
            original(*args)
            raise OSError("interruption after verified copy")
        with patch.object(ta, "copy_new", interrupted), self.assertRaises(OSError):
            ta.archive(self.root, "task-a", references_checked=True)
        self.assertTrue((self.root / "scratch/owned.txt").exists())
        self.assertEqual(ta.preview(self.root, "task-a")["files"][0]["state"], "archiving")
        ta.archive(self.root, "task-a", references_checked=True)
        self.assertFalse((self.root / "scratch/owned.txt").exists())
        ta.restore(self.root, "task-a")
        self.assertEqual((self.root / "scratch/owned.txt").read_text(), "temporary")

    def test_interruption_after_unlink_retains_recovery(self):
        self.claim()
        original = ta.atomic
        def interrupted(path, value):
            if value["files"][0]["state"] == "archived":
                raise OSError("interruption after unlink")
            original(path, value)
        with patch.object(ta, "atomic", interrupted), self.assertRaises(OSError):
            ta.archive(self.root, "task-a", references_checked=True)
        self.assertFalse((self.root / "scratch/owned.txt").exists())
        ta.archive(self.root, "task-a", references_checked=True)
        self.assertEqual(ta.preview(self.root, "task-a")["files"][0]["state"], "archived")
        ta.restore(self.root, "task-a")

    def test_corrupt_backup_never_removes_original(self):
        self.claim()
        backup = self.root / ta.CONTROL / "recovery/task-a/scratch/owned.txt"
        backup.parent.mkdir(parents=True)
        backup.write_text("collision")
        with self.assertRaises(ta.Blocked):
            ta.archive(self.root, "task-a", references_checked=True)
        self.assertEqual((self.root / "scratch/owned.txt").read_text(), "temporary")
        self.assertEqual(backup.read_text(), "collision")

    def test_links_refused(self):
        link = self.root / "linked"
        try:
            os.symlink(self.root / "scratch", link, target_is_directory=True)
        except OSError:
            self.skipTest("host does not permit symlink creation")
        with self.assertRaises(ta.Blocked):
            ta.register(self.root, "task-a", ["linked/owned.txt"], "scratch", "linked")

    def test_bad_cli_input_returns_failure_without_traceback(self):
        self.assertEqual(ta.main(["register", "--root", str(self.root), "--task", "../other", "--file", "scratch/owned.txt", "--reason", "owned"]), 1)

    def test_malformed_records_block_without_modifying_owned_files(self):
        self.claim()
        record = self.root / ta.CONTROL / "task-a.json"
        for value in [[], {"schema_version": 1, "task": "task-a", "root": str(self.root), "files": [None]}]:
            record.write_text(json.dumps(value))
            with self.assertRaises(ta.Blocked):
                ta.archive(self.root, "task-a", references_checked=True)
            self.assertEqual((self.root / "scratch/owned.txt").read_text(), "temporary")


if __name__ == "__main__":
    unittest.main()
