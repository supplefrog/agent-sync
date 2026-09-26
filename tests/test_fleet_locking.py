from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
import fleet
import sync_git


class FleetLockingTests(unittest.TestCase):
    def run_child(self, code, *args):
        return subprocess.run([sys.executable, "-c", "import sys; sys.path.insert(0, " + repr(str(TOOLS)) + "); " + code, *map(str, args)], capture_output=True, text=True, timeout=15)

    def wait_marker(self, marker, process):
        deadline = time.monotonic() + 10
        while not marker.exists() and time.monotonic() < deadline:
            if process.poll() is not None:
                self.fail("child exited before acquiring lock")
            time.sleep(0.02)
        self.assertTrue(marker.exists(), "child did not signal acquisition")

    def test_process_contention_and_crash_release(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "root"
            marker = Path(directory) / "ready"
            code = "import sync_git, time; from pathlib import Path\nwith sync_git.path_lock(Path(sys.argv[1])):\n Path(sys.argv[2]).write_text('ready'); time.sleep(30)"
            child = subprocess.Popen([sys.executable, "-c", "import sys; sys.path.insert(0, " + repr(str(TOOLS)) + "); " + code, str(root), str(marker)])
            try:
                self.wait_marker(marker, child)
                result = self.run_child("import sync_git; from pathlib import Path\nwith sync_git.path_lock(Path(sys.argv[1])): pass", root)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("another sync is running", result.stderr)
            finally:
                child.kill()
                child.wait(timeout=10)
            with sync_git.path_lock(root):
                pass
            self.assertEqual(len(list(Path(directory).glob(".agent-signal-path-*.lock"))), 1)

    def test_nested_locks_deduplicate_and_order(self):
        with tempfile.TemporaryDirectory() as directory:
            roots = [Path(directory) / "b", Path(directory) / "a"]
            calls = []
            real = sync_git._file_lock
            def record(path):
                calls.append(path)
                return real(path)
            with patch.object(sync_git, "_file_lock", side_effect=record):
                with sync_git.path_locks([*roots, roots[0]]):
                    with sync_git.path_locks(list(reversed(roots))):
                        pass
            self.assertEqual(len(calls), 2)
            expected = [sync_git._path_key(path) for path in sorted(roots)]
            self.assertEqual([path.name for path in calls], ['.agent-signal-path-' + __import__('hashlib').sha256(key.encode()).hexdigest() + '.lock' for key in expected])

    def test_disjoint_direct_applies_fail_fast_then_retry_preserves_both(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            snapshot = root / "snapshot"
            destination = root / "destination"
            records = {}
            for name in ("first", "second"):
                owner = snapshot / "skills" / name
                owner.mkdir(parents=True)
                (owner / "SKILL.md").write_text(name)
                records[name] = fleet.directory_record(owner)
            (snapshot / fleet.MANIFEST_FILE).write_text(json.dumps({"schema_version": 1, "skills": records}))
            marker = root / "ready"
            release = root / "release"
            code = """import fleet, time
from pathlib import Path
original = fleet.atomic_json
def pause(path, data):
 Path(sys.argv[3]).write_text('ready')
 while not Path(sys.argv[4]).exists(): time.sleep(.02)
 original(path, data)
fleet.atomic_json = pause
fleet.apply_snapshot(Path(sys.argv[1]), Path(sys.argv[2]), names=['first'])
"""
            child = subprocess.Popen([sys.executable, "-c", "import sys; sys.path.insert(0, " + repr(str(TOOLS)) + "); " + code, str(snapshot), str(destination), str(marker), str(release)])
            try:
                self.wait_marker(marker, child)
                result = self.run_child("import fleet; from pathlib import Path; fleet.apply_snapshot(Path(sys.argv[1]), Path(sys.argv[2]), names=['second'])", snapshot, destination)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("another sync is running", result.stderr)
                self.assertFalse((destination / "second").exists())
                release.write_text('release')
                self.assertEqual(child.wait(timeout=10), 0)
            finally:
                if child.poll() is None:
                    child.kill()
                    child.wait(timeout=10)
            fleet.apply_snapshot(snapshot, destination, names=["second"])
            self.assertEqual(set(fleet.load_state(destination)["skills"]), {"first", "second"})
            self.assertEqual(fleet.verify_snapshot(snapshot, destination, names=["first", "second"]), [])

    def test_partial_multiroot_acquisition_releases_previous_locks(self):
        with tempfile.TemporaryDirectory() as directory:
            first, second = Path(directory) / "a", Path(directory) / "b"
            original = sync_git.path_lock
            def blocked(path):
                if path == second:
                    raise sync_git.SyncBlocked("contended")
                return original(path)
            with patch.object(sync_git, "path_lock", side_effect=blocked):
                with self.assertRaises(sync_git.SyncBlocked):
                    with sync_git.path_locks([second, first]): pass
            result = self.run_child("import sync_git; from pathlib import Path\nwith sync_git.path_lock(Path(sys.argv[1])): pass", first)
            self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
