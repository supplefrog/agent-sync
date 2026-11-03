"""Real Git/source and native-file controls for reviewed recovery retirement."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import worktree_sync as sync
import recovery


class NativeRetirement(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name) / 'repo'
        self.repo.mkdir()
        self.native = Path(self.temp.name) / 'native'
        self.native.mkdir()
        self.name = 'recovery/current/hosts/omp/adapters/old.md'
        self.source = 'skills/old/SKILL.md'
        self.artifact = dict(id='old', source=self.source, snapshot='hosts/omp/adapters/old.md',
                             kind='text', format='text', strategy='replace-if-absent')
        kept = dict(self.artifact, id='kept', source='skills/kept/SKILL.md',
                    snapshot='hosts/omp/adapters/kept.md')
        self.policy = dict(schema_version=1, public_safe=True,
                           hosts={'omp': {'artifacts': [self.artifact, kept]}})
        self.git('init', '-b', 'main')
        self.git('config', 'user.email', 'fixture@example.invalid')
        self.git('config', 'user.name', 'Fixture')
        self.write('recovery.json', self.policy)
        self.write('contracts/ownership.json', {'retired_artifacts': []})
        path = self.repo / self.name
        path.parent.mkdir(parents=True)
        path.write_text('old wrapper\n', encoding='utf-8')
        self.commit('baseline')
        self.policy['hosts']['omp']['artifacts'].remove(self.artifact)
        self.write('recovery.json', self.policy)
        self.write('contracts/ownership.json', {'retired_artifacts': [{'path': self.name}]})
        path.unlink()
        self.retired = self.commit('reviewed retirement')

    def git(self, *args):
        return subprocess.run(['git', '-C', str(self.repo), *args], check=True,
                              capture_output=True, text=True).stdout.strip()

    def write(self, name, value):
        path = self.repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value), encoding='utf-8')

    def commit(self, message):
        self.git('add', '-A')
        self.git('commit', '-m', message)
        return self.git('rev-parse', 'HEAD')

    def completion(self, commit=None, predecessors=(), roots=True):
        commit = commit or self.retired
        journal = {'last_result': {'commit': commit}, 'predecessors': list(predecessors),
                   'receipt': {'options': {'recovery_roots': {'omp': str(self.native)} if roots else {}},
                               'paths': [self.name]}, 'published_repo': str(self.repo)}
        # Snapshot integrity has its own real suite. Keep the Git delta, policy
        # validation, safe root/path handling and native absence readback real.
        with patch.object(recovery, 'verify_snapshot'), \
                patch.object(recovery, '_default_roots', return_value={'omp': self.native}):
            return sync._native_destination_completion(self.repo, journal)

    def test_reviewed_retirement_verifies_absence_with_bound_old_target(self):
        rows = sync._publication_native_obligations(self.repo, self.retired)
        self.assertEqual(rows[0]['target_spec']['source'], self.source)
        self.assertEqual(rows[0]['after_sha256'], 'absent')
        result = self.completion()
        self.assertTrue(result['saved_verified'], result)
        self.assertIsNone(result['loaded_verified'])

    def test_present_native_file_blocks_and_is_never_deleted(self):
        target = self.native / self.source
        target.parent.mkdir(parents=True)
        target.write_text('local work', encoding='utf-8')
        result = self.completion()
        self.assertFalse(result['saved_verified'], result)
        self.assertEqual(target.read_text(), 'local work')

    def test_missing_root_does_not_prove_native_absence(self):
        self.native.rmdir()
        self.assertFalse(self.completion()['saved_verified'])

    def test_default_native_root_used_when_no_override_selected(self):
        self.assertTrue(self.completion(roots=False)['saved_verified'])

    def test_retirement_record_is_required(self):
        self.write('contracts/ownership.json', {'retired_artifacts': []})
        commit = self.commit('missing retirement record')
        self.assertFalse(self.completion(commit=commit, predecessors=[{
            'published_commit': self.retired,
            'native_obligations': sync._publication_native_obligations(self.repo, self.retired)
        }])['saved_verified'])

    def test_snapshot_removed_but_still_managed_is_incomplete(self):
        self.policy['hosts']['omp']['artifacts'].append(self.artifact)
        self.write('recovery.json', self.policy)
        commit = self.commit('still managed')
        # The current policy still requires this missing snapshot; no omission
        # from the selected diff can turn it into a valid retirement.
        with patch.object(recovery, 'verify_snapshot', side_effect=RuntimeError('missing required snapshot')):
            self.assertFalse(sync._native_destination_completion(self.repo, {
                'last_result': {'commit': commit}, 'predecessors': [{
                    'published_commit': self.retired,
                    'native_obligations': sync._publication_native_obligations(self.repo, self.retired)}],
                'receipt': {'options': {'recovery_roots': {'omp': str(self.native)}}, 'paths': []},
                'published_repo': str(self.repo)})['saved_verified'])

    def test_tool_only_successor_carries_retirement_and_rechecks_live_target(self):
        rows = sync._publication_native_obligations(self.repo, self.retired)
        self.write('tool.json', {'changed': True})
        commit = self.commit('tool-only successor')
        prior = [{'published_commit': self.retired, 'native_obligations': rows}]
        self.assertTrue(self.completion(commit, prior)['saved_verified'])
        target = self.native / self.source
        target.parent.mkdir(parents=True)
        target.write_text('resurrected', encoding='utf-8')
        self.assertFalse(self.completion(commit, prior)['saved_verified'])

    def test_same_live_target_cannot_be_redirected_through_new_snapshot(self):
        self.policy['hosts']['omp']['artifacts'].append(dict(
            self.artifact, id='redirected', snapshot='hosts/omp/new.md'))
        self.write('recovery.json', self.policy)
        commit = self.commit('target redirection')
        rows = sync._publication_native_obligations(self.repo, self.retired)
        self.assertFalse(self.completion(commit, [{
            'published_commit': self.retired, 'native_obligations': rows}])['saved_verified'])


if __name__ == '__main__':
    unittest.main()
