"""Scoped publication preserves unrelated work against local Git remotes."""
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import sync_git as sync


class ScopedGitTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name) / 'repo'
        self.repo.mkdir()
        self.remote = Path(self.temp.name) / 'remote.git'
        self.git('init', '-b', 'main')
        self.git('config', 'user.name', 'Scoped Test')
        self.git('config', 'user.email', 'test@example.invalid')
        for name in ('selected.md', 'other.md'):
            (self.repo / name).write_bytes(b'baseline\n')
        self.git('add', '.')
        self.git('commit', '-m', 'baseline')
        subprocess.run(['git', 'init', '--bare', str(self.remote)], check=True, capture_output=True)
        self.git('remote', 'add', 'origin', str(self.remote))
        self.git('push', '-u', 'origin', 'main')
        self.base = self.git('rev-parse', 'HEAD')

    def git(self, *args):
        return sync.git(self.repo, *args)

    def pending(self, paths=('selected.md',)):
        files = sync.identities(self.repo, paths)
        with sync.prepare_candidate(self.repo, files, base=self.base) as (_, tree):
            pass
        result = {'scoped': True, 'base': self.base, 'files': files, 'tree': tree,
                  'message': 'reviewed scoped edit', 'target': sync.destination(self.repo)}
        sync.save_pending(self.repo, result)
        return result

    def publish(self, pending, verify=lambda: None):
        return sync.publish(self.repo, pending, verify=verify)

    def dirty(self):
        (self.repo / 'selected.md').write_bytes(b'reviewed\r\n')
        (self.repo / 'other.md').write_bytes(b'unrelated staged\n')
        self.git('add', 'other.md')
        (self.repo / 'other.md').write_bytes(b'unrelated unstaged\n')
        (self.repo / 'new.md').write_bytes(b'untracked\n')

    def test_scoped_commit_preserves_unrelated_index_and_worktree(self):
        self.dirty()
        before = self.git('ls-files', '--stage', '-z').split('\0')[0]
        pending = self.pending()
        sync.preflight(self.repo, pending['target'], files=pending['files'], scoped=True)
        report = self.publish(pending)
        self.assertEqual('synced', report['result'], report)
        self.assertFalse(report['agents_verified'])
        self.assertEqual(before, self.git('ls-files', '--stage', '-z').split('\0')[0])
        self.assertEqual(b'unrelated unstaged\n', (self.repo / 'other.md').read_bytes())
        self.assertEqual('baseline', self.git('show', 'HEAD:other.md'))
        self.assertEqual(b'reviewed\r\n', sync._raw_git(self.repo, 'show', 'HEAD:selected.md'))
        self.assertEqual(self.git('rev-parse', 'HEAD'), sync.git(self.remote, 'rev-parse', 'main'))

    def test_projected_metadata_publishes_selected_rows_and_keeps_working_guard(self):
        path = self.repo / 'host-deltas.json'
        path.write_text(json.dumps({'selected': 'baseline', 'foreign': 'baseline'}))
        self.git('add', 'host-deltas.json')
        self.git('commit', '-m', 'metadata baseline')
        self.git('push', 'origin', 'main')
        self.base = self.git('rev-parse', 'HEAD')
        path.write_text(json.dumps({'selected': 'reviewed', 'foreign': 'pending'}))
        working = path.read_bytes()
        projected = json.dumps({'selected': 'reviewed', 'foreign': 'baseline'})
        pending = self.pending(('host-deltas.json',))
        pending['publication_overrides'] = {'host-deltas.json': projected}
        with sync.publication_candidate(self.repo, pending) as (_, tree):
            pending['tree'] = tree
        sync.save_pending(self.repo, pending)
        report = self.publish(pending)
        self.assertEqual('synced', report['result'], report)
        self.assertEqual(working, path.read_bytes())
        self.assertEqual({'selected': 'reviewed', 'foreign': 'baseline'},
                         json.loads(self.git('show', 'HEAD:host-deltas.json')))
        self.assertEqual(self.git('rev-parse', 'HEAD'), sync.git(self.remote, 'rev-parse', 'main'))

    def test_projected_metadata_still_blocks_working_races_and_invalid_overrides(self):
        path = self.repo / 'host-deltas.json'
        path.write_text('reviewed metadata')
        pending = self.pending(('host-deltas.json',))
        pending['publication_overrides'] = {'host-deltas.json': 'projected metadata'}
        with sync.publication_candidate(self.repo, pending) as (_, tree):
            pending['tree'] = tree
        path.write_text('concurrent metadata')
        self.assertEqual('incomplete', self.publish(pending)['result'])
        self.assertEqual(self.base, self.git('rev-parse', 'HEAD'))
        pending['publication_overrides'] = {'other.md': 'unselected bytes'}
        with self.assertRaises(sync.SyncBlocked):
            sync.pending_overrides(pending)

    def test_default_preflight_and_selected_staging_still_block(self):
        self.dirty()
        target = sync.destination(self.repo)
        with self.assertRaises(sync.SyncBlocked):
            sync.preflight(self.repo, target)
        self.git('add', 'selected.md')
        before = sync._index_entries(self.repo)
        with self.assertRaises(sync.SyncBlocked):
            sync.preflight(self.repo, target, files={'selected.md': ''}, scoped=True)
        self.assertEqual('incomplete', self.publish(self.pending())['result'])
        self.assertEqual(before, sync._index_entries(self.repo))

    def test_candidate_overrides_deletion_and_dirty_attributes_are_exact(self):
        self.git('config', 'filter.break.clean', 'exit 1')
        (self.repo / '.gitattributes').write_text('*.md filter=break\n')
        files = {'selected.md': hashlib.sha256(b'prospective\r\n').hexdigest(), 'other.md': 'deleted'}
        with sync.prepare_candidate(self.repo, files, overrides={'selected.md': b'prospective\r\n', 'other.md': None}) as (root, tree):
            self.assertEqual(b'prospective\r\n', (root / 'selected.md').read_bytes())
            self.assertFalse((root / 'other.md').exists())
            self.assertFalse((root / '.gitattributes').exists())
            self.assertEqual(b'prospective\r\n', sync._raw_git(self.repo, 'show', tree + ':selected.md'))
        self.assertEqual(b'baseline\n', (self.repo / 'selected.md').read_bytes())
        with self.assertRaises(sync.SyncBlocked):
            with sync.prepare_candidate(self.repo, files, overrides={'selected.md': b'wrong', 'other.md': None}):
                pass

    def test_selected_race_blocks_before_commit(self):
        self.dirty()
        pending = self.pending()
        report = self.publish(pending, lambda: (self.repo / 'selected.md').write_text('race'))
        self.assertEqual('incomplete', report['result'])
        self.assertEqual(self.base, self.git('rev-parse', 'HEAD'))

    def test_hook_failure_preserves_index_and_retry_reuses_scope(self):
        self.dirty()
        pending = self.pending()
        before = sync._index_entries(self.repo)
        hook = self.repo / '.git/hooks/pre-commit'
        hook.write_text('#!/bin/sh\nexit 1\n')
        hook.chmod(0o755)
        report = self.publish(pending)
        self.assertEqual('commit', report['failed_step'])
        self.assertEqual(before, sync._index_entries(self.repo))
        hook.unlink()
        self.assertEqual('synced', self.publish(pending)['result'])

    def test_push_failure_retry_ignores_new_unrelated_work(self):
        self.dirty()
        pending = self.pending()
        hook = self.remote / 'hooks/pre-receive'
        hook.write_text('#!/bin/sh\nexit 1\n')
        hook.chmod(0o755)
        self.assertEqual('push', self.publish(pending)['failed_step'])
        head = self.git('rev-parse', 'HEAD')
        hook.unlink()
        (self.repo / 'newer.md').write_text('unrelated')
        self.assertEqual('synced', self.publish(pending)['result'])
        self.assertEqual(head, self.git('rev-parse', 'HEAD'))

    def test_dirty_allowlist_cannot_authorize_selected_secret(self):
        secret = 'sk-' + 'x' * 30
        (self.repo / 'selected.md').write_text(secret)
        path = self.repo / 'evidence/public-safety-allowlist.json'
        path.parent.mkdir()
        path.write_text(json.dumps({'schema_version': 1, 'findings': [{'path': 'selected.md', 'line': 1,
                        'rule': rule, 'line_sha256': hashlib.sha256(secret.encode()).hexdigest(),
                        'disposition': 'false-positive'} for rule in ('token-prefix', 'recovery-secret-like-value')]}))
        self.assertEqual('incomplete', self.publish(self.pending())['result'])
        self.assertEqual(self.base, self.git('rev-parse', 'HEAD'))

    def test_prior_unpublished_commit_and_remote_change_block(self):
        (self.repo / 'other.md').write_text('prior')
        self.git('add', 'other.md')
        self.git('commit', '-m', 'unpublished')
        with self.assertRaises(sync.SyncBlocked):
            sync.preflight(self.repo, sync.destination(self.repo), files={'selected.md': ''}, scoped=True)
        self.base = self.git('rev-parse', 'HEAD')
        (self.repo / 'selected.md').write_text('reviewed')
        report = self.publish(self.pending())
        self.assertEqual('incomplete', report['result'])
        self.assertIn('remote branch changed', report['reason'])

    def test_private_path_and_unsafe_candidate_path_block(self):
        (self.repo / '.env').write_text('private')
        self.assertEqual('incomplete', self.publish(self.pending(('.env',)))['result'])
        with self.assertRaises(sync.SyncBlocked):
            with sync.prepare_candidate(self.repo, {'../outside': 'deleted'}):
                pass

    def test_remote_advance_and_reset_are_not_overwritten(self):
        (self.repo / 'selected.md').write_text('reviewed')
        pending = self.pending()
        tree = self.git('rev-parse', self.base + '^{tree}')
        advanced = self.git('commit-tree', tree, '-p', self.base, '-m', 'remote change')
        self.git('push', 'origin', advanced + ':refs/heads/race')
        sync.git(self.remote, 'update-ref', 'refs/heads/main', advanced)
        report = self.publish(pending)
        self.assertEqual('push', report['failed_step'], report)
        self.assertEqual(advanced, sync.git(self.remote, 'rev-parse', 'main'))
        older = self.git('commit-tree', tree, '-m', 'remote reset')
        self.git('push', 'origin', older + ':refs/heads/reset')
        sync.git(self.remote, 'update-ref', 'refs/heads/main', older)
        report = self.publish(pending)
        self.assertEqual('push', report['failed_step'], report)
        self.assertEqual(older, sync.git(self.remote, 'rev-parse', 'main'))

    def test_wrong_parent_and_merge_commit_are_rejected(self):
        (self.repo / 'selected.md').write_text('reviewed')
        pending = self.pending()
        other = self.git('commit-tree', pending['tree'], '-m', 'different parent')
        wrong = self.git('commit-tree', pending['tree'], '-p', other, '-m', pending['message'])
        self.git('update-ref', 'HEAD', wrong)
        pending['commit'] = wrong
        self.assertEqual('incomplete', self.publish(pending)['result'])
        merge = self.git('commit-tree', pending['tree'], '-p', self.base, '-p', other,
                         '-m', pending['message'])
        self.git('update-ref', 'HEAD', merge)
        pending['commit'] = merge
        self.assertEqual('incomplete', self.publish(pending)['result'])
        self.assertEqual(self.base, sync.git(self.remote, 'rev-parse', 'main'))

    def test_hook_mutated_tree_and_index_race_block(self):
        self.dirty()
        pending = self.pending()
        hook = self.repo / '.git/hooks/pre-commit'
        hook.write_text('#!/bin/sh\nprintf unreviewed > rogue.md\ngit add rogue.md\n')
        hook.chmod(0o755)
        report = self.publish(pending)
        self.assertEqual('commit', report['failed_step'], report)
        self.assertEqual(self.base, sync.git(self.remote, 'rev-parse', 'main'))

    def test_cas_blocks_remote_change_between_probe_and_push(self):
        from unittest.mock import patch
        (self.repo / 'selected.md').write_text('reviewed')
        pending = self.pending()
        other = self.git('commit-tree', pending['tree'], '-p', self.base, '-m', 'remote race')
        self.git('push', 'origin', other + ':refs/heads/race')
        original = sync.git
        def race(repo, *args, **kwargs):
            if args[0] == 'push':
                original(self.remote, 'update-ref', 'refs/heads/main', other)
            return original(repo, *args, **kwargs)
        with patch.object(sync, 'git', side_effect=race):
            report = self.publish(pending)
        self.assertEqual('push', report['failed_step'], report)
        self.assertEqual(other, sync.git(self.remote, 'rev-parse', 'main'))

    def test_candidate_rejects_baseline_symlink_without_extracting_it(self):
        oid = sync._raw_git(self.repo, 'hash-object', '-w', '--stdin', input=b'../../outside').decode().strip()
        self.git('update-index', '--add', '--cacheinfo', '120000,' + oid + ',link')
        tree = self.git('write-tree')
        with self.assertRaises(sync.SyncBlocked):
            with sync.prepare_candidate(self.repo, {}, base=tree):
                pass

    def test_selected_rename_source_is_staged_overlap(self):
        self.git('mv', 'selected.md', 'renamed.md')
        pending = self.pending()
        report = self.publish(pending)
        self.assertEqual('incomplete', report['result'])
        self.assertIn('overlap staged', report['reason'])

    def test_index_race_during_verification_blocks_without_reset(self):
        (self.repo / 'selected.md').write_text('reviewed')
        pending = self.pending()
        def verify():
            (self.repo / 'other.md').write_text('new staging')
            self.git('add', 'other.md')
        report = self.publish(pending, verify)
        self.assertEqual('incomplete', report['result'])
        self.assertIn('index changed', report['reason'])
        self.assertEqual(self.base, self.git('rev-parse', 'HEAD'))
        self.assertEqual('new staging', self.git('show', ':other.md'))

    def test_real_index_lock_preserves_entries_and_retry_recovers_commit(self):
        self.dirty()
        pending = self.pending()
        before = sync._index_entries(self.repo)
        index_lock = self.repo / '.git/index.lock'
        index_lock.write_bytes(b'owned by another operation')
        report = self.publish(pending)
        self.assertEqual('incomplete', report['result'], report)
        self.assertEqual(before, sync._index_entries(self.repo))
        self.assertEqual(b'owned by another operation', index_lock.read_bytes())
        head = self.git('rev-parse', 'HEAD')
        index_lock.unlink()
        self.assertEqual('synced', self.publish(pending)['result'])
        self.assertEqual(head, self.git('rev-parse', 'HEAD'))

    def test_index_replace_cleanup_does_not_remove_next_operators_lock(self):
        from unittest.mock import patch
        self.dirty()
        before = sync._index_entries(self.repo)
        index_lock = self.repo / '.git/index.lock'
        replace = sync.os.replace
        def next_operator(source, destination):
            replace(source, destination)
            index_lock.write_bytes(b'next operation')
        with patch.object(sync.os, 'replace', side_effect=next_operator):
            sync._reconcile_scoped_index(self.repo, {'selected.md'}, before)
        self.assertEqual(b'next operation', index_lock.read_bytes())
        self.assertEqual(before, sync._index_entries(self.repo))
        index_lock.unlink()


if __name__ == '__main__':
    unittest.main()
