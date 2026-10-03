"""Concurrent callers use fresh baselines while shared transactions serialize."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

import test_reconcile as fixtures
import test_sync_completion as completion

TOOLS = Path(__file__).resolve().parents[1] / 'tools'

CHILD = r'''
import json, sys, time
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import reconcile
repo, live, markers = map(Path, sys.argv[2:5])
name = sys.argv[5]
first = True
def checks(*args):
    global first
    if name == 'kept' and first:
        first = False
        (markers / 'held').write_text('held')
        deadline = time.monotonic() + 20
        while not (markers / 'release').exists():
            if time.monotonic() >= deadline: raise RuntimeError('barrier timed out')
            time.sleep(.02)
    return ['fixture checks']
reconcile._run_checks = checks
(markers / (name + '-started')).write_text('started')
result = reconcile.complete_sync(repo, machine='test', recovery_roots={},
    skill_roots=[live], adopt=[name], message='independent ' + name)
(markers / (name + '-result.json')).write_text(json.dumps(result))
'''


class ScopedSyncQueueTests(unittest.TestCase):
    setUp = fixtures.ReconcileTests.setUp
    fixture = fixtures.ReconcileTests.fixture
    setup_git = completion.CompleteSyncTests.setup_git
    git = completion.CompleteSyncTests.git

    def marker(self, path, process):
        deadline = time.monotonic() + 12
        while not path.exists() and time.monotonic() < deadline:
            if process.poll() is not None:
                self.fail('child exited before barrier: ' + process.communicate()[1])
            time.sleep(.02)
        self.assertTrue(path.exists(), 'child did not reach barrier')

    def test_two_scoped_callers_complete_without_manual_retry_or_foreign_publication(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo, live, remote = self.setup_git(root)
            fixtures.write_skill(repo, 'other', 'other baseline')
            registry = json.loads((repo / 'registry.json').read_text())
            registry['skills'].append({'name': 'other', 'status': 'admitted'})
            (repo / 'registry.json').write_text(json.dumps(registry))
            self.fleet.render_snapshot(repo, repo / 'render/fleet')
            self.fleet.apply_snapshot(repo / 'render/fleet', live)
            self.git(repo, 'add', '.')
            self.git(repo, 'commit', '-m', 'other baseline')
            self.git(repo, 'push', 'origin', 'main')
            base = self.git(repo, 'rev-parse', 'HEAD')
            for name in ('kept', 'other'):
                path = repo / 'skills' / name / 'SKILL.md'
                path.write_text(path.read_text() + '\n' + name + ' independent edit\n')
            (repo / 'unselected.md').write_text('foreign staged work')
            self.git(repo, 'add', 'unselected.md')
            staged = self.git(repo, 'diff', '--cached', '--raw')
            markers = root / 'markers'
            markers.mkdir()
            children = []
            try:
                for name in ('kept', 'other'):
                    child = subprocess.Popen([sys.executable, '-B', '-c', CHILD,
                        str(TOOLS), str(repo), str(live), str(markers), name],
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                    children.append(child)
                    self.marker(markers / ('held' if name == 'kept' else 'other-started'), child)
                self.assertFalse((markers / 'other-result.json').exists())
                (markers / 'release').write_text('release')
                for child in children:
                    _, errors = child.communicate(timeout=30)
                    self.assertEqual(0, child.returncode, errors)
                reports = {name: json.loads((markers / (name + '-result.json')).read_text())
                           for name in ('kept', 'other')}
                for name, report in reports.items():
                    self.assertEqual('synced', report['result'], report)
                    self.assertEqual([name], report['verified_owners'])
                    self.assertEqual((repo / 'skills' / name / 'SKILL.md').read_bytes(),
                                     (live / name / 'SKILL.md').read_bytes())
                self.assertEqual(reports['kept']['commit'],
                                 self.git(repo, 'rev-parse', reports['other']['commit'] + '^'))
                first_paths = set(self.git(repo, 'diff', '--name-only', base,
                                           reports['kept']['commit']).splitlines())
                self.assertIn('skills/kept/SKILL.md', first_paths)
                self.assertNotIn('skills/other/SKILL.md', first_paths)
                self.assertEqual(reports['other']['commit'], self.git(remote, 'rev-parse', 'main'))
                self.assertEqual(staged, self.git(repo, 'diff', '--cached', '--raw'))
                self.assertNotIn('unselected.md', self.git(remote, 'ls-tree', '-r', '--name-only', 'main'))
            finally:
                for child in children:
                    if child.poll() is None:
                        child.kill()
                        child.communicate(timeout=5)


if __name__ == '__main__':
    unittest.main()
