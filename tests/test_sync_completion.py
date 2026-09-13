"""Exercise complete sync against real temporary Git repositories/remotes."""
from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import test_reconcile as fixtures


class CompleteSyncTests(unittest.TestCase):
    setUp = fixtures.ReconcileTests.setUp
    fixture = fixtures.ReconcileTests.fixture
    def git(self, repo, *args):
        return subprocess.check_output(['git', '-C', str(repo), *args], text=True).strip()

    def setup_git(self, root):
        repo, live = self.fixture(root)
        # Real governance owners are required by complete sync.
        registry = json.loads((repo / 'registry.json').read_text())
        for name in ('cross-agent-surface-engineering', 'fleet-sync'):
            fixtures.write_skill(repo, name)
            registry['skills'].append({'name': name, 'status': 'admitted'})
        (repo / 'registry.json').write_text(json.dumps(registry))
        self.fleet.render_snapshot(repo, repo / 'render/fleet')
        self.fleet.apply_snapshot(repo / 'render/fleet', live)
        (repo / '.gitignore').write_text('render/\n')
        self.git(repo, 'init', '-b', 'main')
        self.git(repo, 'config', 'user.name', 'Sync Test')
        self.git(repo, 'config', 'user.email', 'sync@example.invalid')
        self.git(repo, 'add', '.')
        self.git(repo, 'commit', '-m', 'baseline')
        remote = root / 'remote.git'
        subprocess.run(['git', 'init', '--bare', str(remote)], check=True, capture_output=True)
        self.git(repo, 'remote', 'add', 'origin', str(remote))
        self.git(repo, 'push', '-u', 'origin', 'main')
        return repo, live, remote

    def run_sync(self, repo, live, **kwargs):
        # Fixtures have no application validators. Only that external boundary is replaced.
        with patch.object(self.reconcile, '_run_checks', return_value=['fixture checks']):
            return self.reconcile.complete_sync(repo, machine='test', recovery_roots={},
                                                skill_roots=[live], **kwargs)

    def test_complete_sync_adopts_commits_pushes_and_repeats_without_new_commit(self):
        with tempfile.TemporaryDirectory() as temp:
            repo, live, remote = self.setup_git(Path(temp))
            target = live / 'kept/SKILL.md'
            target.write_text(target.read_text() + '\nchanged from an agent\n')
            report = self.run_sync(repo, live)
            self.assertEqual('synced', report['result'])
            head = self.git(repo, 'rev-parse', 'HEAD')
            self.assertEqual(head, self.git(remote, 'rev-parse', 'refs/heads/main'))
            self.assertEqual('', self.git(repo, 'status', '--porcelain'))
            self.assertIn('changed from an agent', (repo / 'skills/kept/SKILL.md').read_text())
            self.assertEqual([], self.fleet.verify_snapshot(repo / 'render/fleet', live))
            self.assertEqual('synced', self.run_sync(repo, live)['result'])
            self.assertEqual(head, self.git(repo, 'rev-parse', 'HEAD'))

    def test_unreviewed_dirty_work_blocks_before_any_agent_write(self):
        with tempfile.TemporaryDirectory() as temp:
            repo, live, remote = self.setup_git(Path(temp))
            (repo / 'notes.md').write_text('unrelated work')
            original = (live / 'kept/SKILL.md').read_bytes()
            path = repo / 'skills/kept/SKILL.md'
            path.write_text(path.read_text() + '\nchange\n')
            report = self.run_sync(repo, live)
            self.assertEqual('review-required', report['result'])
            self.assertEqual(original, (live / 'kept/SKILL.md').read_bytes())
            self.assertEqual(self.git(remote, 'rev-parse', 'refs/heads/main'), self.git(repo, 'rev-parse', 'HEAD'))

    def test_reviewed_extra_file_is_committed_but_not_deployed_as_a_skill(self):
        with tempfile.TemporaryDirectory() as temp:
            repo, live, _ = self.setup_git(Path(temp))
            (repo / 'notes.md').write_text('reviewed change')
            report = self.run_sync(repo, live, include=['notes.md'])
            self.assertEqual('synced', report['result'])
            self.assertEqual('', self.git(repo, 'status', '--porcelain'))
            self.assertFalse((live / 'notes.md').exists())

    def test_large_reviewed_file_set_avoids_windows_command_limit(self):
        with tempfile.TemporaryDirectory() as temp:
            repo, live, remote = self.setup_git(Path(temp))
            paths = [f'reviewed/{i:04d}-' + 'x' * 80 + '.md' for i in range(450)]
            paths.append('reviewed/literal [x] ü.md')
            self.assertGreater(len(subprocess.list2cmdline(['git', 'add', '--', *paths])), 32767)
            (repo / 'reviewed').mkdir()
            for name in paths:
                (repo / name).write_text('reviewed public source\n', encoding='utf-8')
            report = self.run_sync(repo, live, include=paths)
            self.assertEqual('synced', report['result'], report)
            self.assertEqual('', self.git(repo, 'status', '--porcelain'))
            self.assertEqual(self.git(repo, 'rev-parse', 'HEAD'),
                             self.git(remote, 'rev-parse', 'refs/heads/main'))
            tracked = set(self.git(repo, 'ls-files', '-z').split('\0'))
            self.assertTrue(set(paths).issubset(tracked))

    def test_push_failure_is_incomplete_and_retry_reuses_commit(self):
        with tempfile.TemporaryDirectory() as temp:
            repo, live, remote = self.setup_git(Path(temp))
            (repo / 'notes.md').write_text('reviewed change')
            hook = remote / 'hooks/pre-receive'
            hook.write_text('#!/bin/sh\nexit 1\n')
            hook.chmod(0o755)
            report = self.run_sync(repo, live, include=['notes.md'])
            self.assertEqual('incomplete', report['result'])
            self.assertEqual('push', report['failed_step'])
            head = self.git(repo, 'rev-parse', 'HEAD')
            hook.unlink()
            self.assertEqual('synced', self.run_sync(repo, live)['result'])
            self.assertEqual(head, self.git(repo, 'rev-parse', 'HEAD'))
            self.assertEqual(head, self.git(remote, 'rev-parse', 'refs/heads/main'))

    def test_checks_fail_without_commit_or_push(self):
        with tempfile.TemporaryDirectory() as temp:
            repo, live, remote = self.setup_git(Path(temp))
            head = self.git(repo, 'rev-parse', 'HEAD')
            (repo / 'notes.md').write_text('reviewed change')
            with patch.object(self.reconcile, '_run_checks', side_effect=RuntimeError('failed')):
                report = self.reconcile.complete_sync(repo, machine='test', recovery_roots={},
                                                      skill_roots=[live], include=['notes.md'])
            self.assertNotEqual('synced', report['result'])
            self.assertEqual(head, self.git(repo, 'rev-parse', 'HEAD'))
            self.assertEqual(head, self.git(remote, 'rev-parse', 'refs/heads/main'))

    def test_conflicting_origins_and_staged_owner_remain_blocked(self):
        with tempfile.TemporaryDirectory() as temp:
            repo, live, _ = self.setup_git(Path(temp))
            (repo / 'skills/kept/SKILL.md').write_text('canonical change')
            (live / 'kept/SKILL.md').write_text('different agent change')
            report = self.run_sync(repo, live)
            self.assertEqual('review-required', report['result'])
            self.assertEqual('different agent change', (live / 'kept/SKILL.md').read_text())
            self.assertEqual('review-required', self.run_sync(repo, live, adopt=['staged'])['result'])


    def test_missing_one_managed_baseline_blocks_multi_agent_adoption(self):
        import shutil
        with tempfile.TemporaryDirectory() as temp:
            repo, live, _ = self.setup_git(Path(temp))
            other = Path(temp) / 'other'
            shutil.copytree(live, other)
            state_path = other / self.fleet.STATE_FILE
            state = json.loads(state_path.read_text())
            del state['skills']['kept']
            state_path.write_text(json.dumps(state))
            state = self.reconcile._skill_state(repo, repo / 'render/fleet', [('one', live), ('two', other)], 'kept')
            self.assertEqual('review-required', state['mode'])

    def test_commit_hook_failure_preserves_real_index_and_retries(self):
        with tempfile.TemporaryDirectory() as temp:
            repo, live, remote = self.setup_git(Path(temp))
            (repo / 'notes.md').write_text('reviewed change')
            hook = repo / '.git/hooks/pre-commit'
            hook.write_text('#!/bin/sh\nexit 1\n')
            hook.chmod(0o755)
            head = self.git(repo, 'rev-parse', 'HEAD')
            report = self.run_sync(repo, live, include=['notes.md'])
            self.assertEqual('incomplete', report['result'])
            self.assertEqual('commit', report['failed_step'])
            self.assertEqual(head, self.git(repo, 'rev-parse', 'HEAD'))
            self.assertEqual('', self.git(repo, 'diff', '--cached', '--name-only'))
            hook.unlink()
            self.assertEqual('synced', self.run_sync(repo, live)['result'])
            self.assertEqual(self.git(repo, 'rev-parse', 'HEAD'), self.git(remote, 'rev-parse', 'refs/heads/main'))

    def test_failed_push_does_not_authorize_edited_content_on_retry(self):
        with tempfile.TemporaryDirectory() as temp:
            repo, live, remote = self.setup_git(Path(temp))
            path = repo / 'notes.md'
            path.write_text('reviewed change')
            hook = remote / 'hooks/pre-receive'
            hook.write_text('#!/bin/sh\nexit 1\n')
            hook.chmod(0o755)
            self.assertEqual('incomplete', self.run_sync(repo, live, include=['notes.md'])['result'])
            path.write_text('new unreviewed change')
            hook.unlink()
            self.assertEqual('incomplete', self.run_sync(repo, live)['result'])
            self.assertNotEqual(self.git(repo, 'rev-parse', 'HEAD'), self.git(remote, 'rev-parse', 'refs/heads/main'))

    def test_preexisting_staged_work_is_never_consumed(self):
        with tempfile.TemporaryDirectory() as temp:
            repo, live, _ = self.setup_git(Path(temp))
            (repo / 'notes.md').write_text('work belonging to someone else')
            self.git(repo, 'add', 'notes.md')
            before = self.git(repo, 'diff', '--cached')
            self.assertEqual('incomplete', self.run_sync(repo, live, include=['notes.md'])['result'])
            self.assertEqual(before, self.git(repo, 'diff', '--cached'))

    def test_exact_paths_include_deletion_and_literal_metacharacters(self):
        with tempfile.TemporaryDirectory() as temp:
            repo, live, _ = self.setup_git(Path(temp))
            (repo / ' leading [x].md').write_text('reviewed')
            (repo / '.gitignore').unlink()
            # Keep generated render files ignored without changing publication scope.
            (repo / '.git/info/exclude').write_text('render/\n')
            report = self.run_sync(repo, live, include=[' leading [x].md', '.gitignore'])
            self.assertEqual('synced', report['result'])
            self.assertEqual('', self.git(repo, 'status', '--porcelain'))

    def test_unsafe_include_and_secret_fail_before_publication(self):
        with tempfile.TemporaryDirectory() as temp:
            repo, live, remote = self.setup_git(Path(temp))
            head = self.git(repo, 'rev-parse', 'HEAD')
            for name in ('../outside.md', '.git/config', 'skills'):
                self.assertEqual('incomplete', self.run_sync(repo, live, include=[name])['result'])
            (repo / 'notes.md').write_text('sk' + '-' + 'x' * 30)
            self.assertEqual('incomplete', self.run_sync(repo, live, include=['notes.md'])['result'])
            self.assertEqual(head, self.git(remote, 'rev-parse', 'refs/heads/main'))


    def test_unpublished_prior_commit_is_not_silently_pushed(self):
        with tempfile.TemporaryDirectory() as temp:
            repo, live, remote = self.setup_git(Path(temp))
            remote_head = self.git(remote, 'rev-parse', 'refs/heads/main')
            (repo / 'unrelated.md').write_text('not approved by this operation')
            self.git(repo, 'add', 'unrelated.md')
            self.git(repo, 'commit', '-m', 'unreviewed prior work')
            self.assertEqual('incomplete', self.run_sync(repo, live)['result'])
            self.assertEqual(remote_head, self.git(remote, 'rev-parse', 'refs/heads/main'))

    def test_retry_preserves_staged_alternate_content_on_selected_path(self):
        with tempfile.TemporaryDirectory() as temp:
            repo, live, remote = self.setup_git(Path(temp))
            path = repo / 'notes.md'
            path.write_text('reviewed change')
            hook = remote / 'hooks/pre-receive'
            hook.write_text('#!/bin/sh\nexit 1\n')
            hook.chmod(0o755)
            self.assertEqual('incomplete', self.run_sync(repo, live, include=['notes.md'])['result'])
            hook.unlink()
            path.write_text('alternate staged work')
            self.git(repo, 'add', 'notes.md')
            path.write_text('reviewed change')
            staged = self.git(repo, 'diff', '--cached')
            self.assertEqual('incomplete', self.run_sync(repo, live)['result'])
            self.assertEqual(staged, self.git(repo, 'diff', '--cached'))

    def test_agent_edit_during_prerequisite_check_is_not_adopted(self):
        with tempfile.TemporaryDirectory() as temp:
            repo, live, remote = self.setup_git(Path(temp))
            path = live / 'kept/SKILL.md'
            path.write_text(path.read_text() + '\ninitial requested edit\n')
            head = self.git(repo, 'rev-parse', 'HEAD')
            def check(*_):
                path.write_text(path.read_text() + '\nunreviewed during check\n')
                return []
            with patch.object(self.reconcile, '_run_checks', side_effect=check):
                report = self.reconcile.complete_sync(repo, machine='test', recovery_roots={}, skill_roots=[live])
            self.assertEqual('incomplete', report['result'])
            self.assertEqual(head, self.git(remote, 'rev-parse', 'refs/heads/main'))
            self.assertNotIn('unreviewed', (repo / 'skills/kept/SKILL.md').read_text())

    def test_last_gate_failure_happens_before_push(self):
        with tempfile.TemporaryDirectory() as temp:
            repo, live, remote = self.setup_git(Path(temp))
            head = self.git(remote, 'rev-parse', 'refs/heads/main')
            (repo / 'notes.md').write_text('reviewed')
            count = 0
            def check(*_):
                nonlocal count
                count += 1
                if count == 3:
                    raise RuntimeError('last gate failed')
                return []
            with patch.object(self.reconcile, '_run_checks', side_effect=check):
                report = self.reconcile.complete_sync(repo, machine='test', recovery_roots={},
                                                      skill_roots=[live], include=['notes.md'])
            self.assertEqual('incomplete', report['result'])
            self.assertEqual('verify', report['failed_step'])
            self.assertEqual(head, self.git(remote, 'rev-parse', 'refs/heads/main'))

    def test_new_unmanaged_skill_in_second_root_is_not_ignored(self):
        import shutil
        with tempfile.TemporaryDirectory() as temp:
            repo, live, remote = self.setup_git(Path(temp))
            other = Path(temp) / 'second'
            shutil.copytree(live, other)
            (repo / 'notes.md').write_text('reviewed')
            count = 0
            def check(*_):
                nonlocal count
                count += 1
                if count == 2:
                    (other / 'rogue').mkdir()
                    (other / 'rogue/SKILL.md').write_text('unreviewed new owner')
                return []
            head = self.git(repo, 'rev-parse', 'HEAD')
            with patch.object(self.reconcile, '_run_checks', side_effect=check):
                report = self.reconcile.complete_sync(repo, machine='test', recovery_roots={},
                                                      skill_roots=[live, other], include=['notes.md'])
            self.assertEqual('incomplete', report['result'])
            self.assertEqual(head, self.git(remote, 'rev-parse', 'refs/heads/main'))

    def test_capture_rejects_non_policy_recovery_file_without_deleting_it(self):
        with tempfile.TemporaryDirectory() as temp:
            repo, live, remote = self.setup_git(Path(temp))
            root = repo / 'recovery/current'
            roots = {host: Path(temp) / host for host in ('hermes', 'codex', 'omp')}
            for path in roots.values():
                path.mkdir()
                (path / 'config.json').write_text('{"value": "baseline"}')
            policy = {'schema_version': 1, 'machine': 'test', 'public_safe': True,
                      'hosts': {host: {'artifacts': [{'id': 'settings', 'kind': 'config',
                                'source': 'config.json', 'snapshot': f'hosts/{host}/config.json',
                                'format': 'json', 'strategy': 'merge', 'include': ['value']}]}
                                for host in roots}}
            (repo / 'recovery.json').write_text(json.dumps(policy))
            self.reconcile.recovery.snapshot(repo / 'recovery.json', root, roots, repo_root=repo)
            rogue = root / 'rogue.txt'
            rogue.write_text('unowned file')
            report = self.run_sync(repo, live, capture_recovery=True)
            self.assertEqual('incomplete', report['result'])
            self.assertIn('unexpected recovery files', report['reason'])
            self.assertEqual('unowned file', rogue.read_text())

    def test_retry_rejects_changed_custom_recovery_directories(self):
        with tempfile.TemporaryDirectory() as temp:
            repo, live, remote = self.setup_git(Path(temp))
            (repo / 'notes.md').write_text('reviewed')
            hook = remote / 'hooks/pre-receive'
            hook.write_text('#!/bin/sh\nexit 1\n')
            hook.chmod(0o755)
            self.assertEqual('incomplete', self.run_sync(repo, live, include=['notes.md'])['result'])
            hook.unlink()
            with patch.object(self.reconcile, '_run_checks', return_value=[]):
                report = self.reconcile.complete_sync(repo, machine='test', skill_roots=[live],
                                                      recovery_roots={'hermes': Path(temp) / 'different'})
            self.assertEqual('incomplete', report['result'])
            self.assertIn('different settings directories', report['reason'])


if __name__ == '__main__':
    unittest.main()
