"""Ready integration uses real Git worktrees, a local remote, and fleet installs."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import json
import shutil
import tempfile
import unittest
from unittest.mock import patch

import test_reconcile as fixtures
import test_sync_completion as completion
import test_scoped_reconcile as scoped_fixtures
import sync_git


class WorktreeSyncTests(unittest.TestCase):
    setUp = completion.CompleteSyncTests.setUp
    fixture = completion.CompleteSyncTests.fixture
    git = completion.CompleteSyncTests.git
    setup_git = completion.CompleteSyncTests.setup_git
    extra_owner = scoped_fixtures.ScopedReconcileTests.extra_owner
    binding_fixture = scoped_fixtures.ScopedReconcileTests.binding_fixture

    def adapter(self):
        return fixtures.load_tool('worktree_sync')

    def worker(self, repo, name):
        target = repo.parent / name
        self.git(repo, 'worktree', 'add', '-b', name, str(target), 'HEAD')
        return target

    def commit(self, repo, name, content):
        target = repo / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding='utf-8')
        self.git(repo, 'add', '--', name)
        self.git(repo, 'commit', '-m', 'ready ' + name)
        return self.git(repo, 'rev-parse', 'HEAD')

    def run_ready(self, adapter, repo, ready, live, **kwargs):
        with patch.object(adapter.reconcile, '_run_checks', return_value=['fixture checks']):
            return adapter.ready_sync(repo, ready, machine='test', skill_roots=[live], **kwargs)

    def snapshot(self, repo):
        return (self.git(repo, 'rev-parse', 'HEAD'), self.git(repo, 'symbolic-ref', 'HEAD'),
                (sync_git.git_dir(repo) / 'index').read_bytes(),
                {str(path.relative_to(repo)): path.read_bytes() for path in repo.rglob('*')
                 if path.is_file() and '.git' not in path.parts and path.name != '.git'})

    def test_ready_workers_integrate_latest_and_preserve_source_wip(self):
        adapter = self.adapter()
        with tempfile.TemporaryDirectory() as temporary:
            repo, live, remote = self.setup_git(Path(temporary))
            a, b = self.worker(repo, 'a'), self.worker(repo, 'b')
            ready_a = self.commit(a, 'a.md', 'ready A\n')
            (b / 'b.md').write_text('unfinished B\n')
            (b / 'staged.md').write_text('staged B\n')
            self.git(b, 'add', 'staged.md')
            before_a, before_b = self.snapshot(a), self.snapshot(b)
            result = self.run_ready(adapter, a, ready_a, live, include=['a.md'])
            self.assertEqual('synced', result['result'], result)
            self.assertEqual(before_a, self.snapshot(a))
            self.assertEqual(before_b, self.snapshot(b))
            self.assertEqual('ready A', self.git(remote, 'show', 'main:a.md'))
            # Finish only B's selected file while preserving unrelated staged work.
            self.git(b, 'reset', '--mixed', 'HEAD')
            ready_b = self.commit(b, 'b.md', 'ready B\n')
            before_b = self.snapshot(b)
            result_b = self.run_ready(adapter, b, ready_b, live, include=['b.md'])
            self.assertEqual('synced', result_b['result'], result_b)
            self.assertEqual(before_b, self.snapshot(b))
            self.assertEqual('ready A', self.git(remote, 'show', 'main:a.md'))
            self.assertEqual('ready B', self.git(remote, 'show', 'main:b.md'))

    def test_same_file_disjoint_hunks_use_git_three_way_merge(self):
        adapter = self.adapter()
        with tempfile.TemporaryDirectory() as temporary:
            repo, live, remote = self.setup_git(Path(temporary))
            original = '\n'.join('line ' + str(i) for i in range(20)) + '\n'
            self.commit(repo, 'shared.md', original)
            self.git(repo, 'push', 'origin', 'main')
            a, b = self.worker(repo, 'a'), self.worker(repo, 'b')
            ready_a = self.commit(a, 'shared.md', original.replace('line 2\n', 'A\n'))
            ready_b = self.commit(b, 'shared.md', original.replace('line 17\n', 'B\n'))
            self.assertEqual('synced', self.run_ready(adapter, a, ready_a, live, include=['shared.md'])['result'])
            result = self.run_ready(adapter, b, ready_b, live, include=['shared.md'])
            self.assertEqual('synced', result['result'], result)
            final = self.git(remote, 'show', 'main:shared.md')
            self.assertIn('\nA\n', final)
            self.assertIn('\nB\n', final)

    def test_real_conflict_preserves_workers_and_live_and_later_ready_succeeds(self):
        adapter = self.adapter()
        with tempfile.TemporaryDirectory() as temporary:
            repo, live, remote = self.setup_git(Path(temporary))
            a, b, c = (self.worker(repo, name) for name in ('a', 'b', 'c'))
            name = 'skills/kept/SKILL.md'
            original = (a / name).read_text()
            ready_a = self.commit(a, name, original.replace('baseline', 'version A'))
            ready_b = self.commit(b, name, original.replace('baseline', 'version B'))
            ready_c = self.commit(c, 'c.md', 'independent\n')
            self.assertEqual('synced', self.run_ready(adapter, a, ready_a, live, adopt=['kept'])['result'])
            before_b, before_live = self.snapshot(b), (live / 'kept/SKILL.md').read_bytes()
            before_remote = self.git(remote, 'rev-parse', 'main')
            result = self.run_ready(adapter, b, ready_b, live, adopt=['kept'])
            self.assertEqual('conflict', result['result'], result)
            self.assertEqual([name], result['conflicts'])
            self.assertEqual(before_b, self.snapshot(b))
            self.assertEqual(before_live, (live / 'kept/SKILL.md').read_bytes())
            self.assertEqual(before_remote, self.git(remote, 'rev-parse', 'main'))
            result = self.run_ready(adapter, c, ready_c, live, include=['c.md'])
            self.assertEqual('synced', result['result'], result)

    def test_pending_retries_exact_scope_without_replaying_source_wip(self):
        adapter = self.adapter()
        with tempfile.TemporaryDirectory() as temporary:
            repo, live, remote = self.setup_git(Path(temporary))
            worker = self.worker(repo, 'a')
            ready = self.commit(worker, 'a.md', 'ready\n')
            with patch.object(adapter.reconcile, 'complete_sync', return_value={'result': 'incomplete', 'reason': 'injected stop'}):
                result = self.run_ready(adapter, worker, ready, live, include=['a.md'])
            self.assertEqual('incomplete', result['result'])
            published = sync_git.common_dir(repo) / 'agent-signal-published'
            self.assertFalse((published / 'a.md').exists())
            self.assertEqual(self.git(remote, 'rev-parse', 'main'), self.git(published, 'rev-parse', 'HEAD'))
            (worker / 'a.md').write_text('new unfinished edit\n')
            before = self.snapshot(worker)
            wrong = self.run_ready(adapter, worker, ready, live, include=['a.md', 'other.md'])
            self.assertEqual('incomplete', wrong['result'])
            self.assertIn('same exact', wrong['reason'])
            result = self.run_ready(adapter, worker, ready, live, include=['a.md'])
            self.assertEqual('synced', result['result'], result)
            self.assertEqual('ready', self.git(remote, 'show', 'main:a.md'))
            self.assertEqual(before, self.snapshot(worker))
            self.assertFalse((sync_git.common_dir(repo) / 'agent-signal-integration.json').exists())
            state = json.loads((live / self.fleet.STATE_FILE).read_text())
            self.assertEqual(str(published / 'render/fleet'), state['source_snapshot'])

    def test_unselected_path_and_unadmitted_owner_fail_before_lane_creation(self):
        adapter = self.adapter()
        with tempfile.TemporaryDirectory() as temporary:
            repo, live, _ = self.setup_git(Path(temporary))
            worker = self.worker(repo, 'a')
            ready = self.commit(worker, 'other.md', 'unselected\n')
            result = self.run_ready(adapter, worker, ready, live, adopt=['kept'])
            self.assertEqual('incomplete', result['result'])
            self.assertIn('unselected path', result['reason'])
            self.assertFalse((sync_git.common_dir(repo) / 'agent-signal-published').exists())
            ready = self.commit(worker, 'skills/staged/SKILL.md', (worker / 'skills/staged/SKILL.md').read_text() + '\nchange')
            result = self.run_ready(adapter, worker, ready, live, adopt=['staged'], include=['other.md'])
            self.assertIn('admitted', result['reason'])

    def test_plan_does_not_fetch_create_or_modify_source(self):
        adapter = self.adapter()
        with tempfile.TemporaryDirectory() as temporary:
            repo, live, _ = self.setup_git(Path(temporary))
            worker = self.worker(repo, 'a')
            ready = self.commit(worker, 'a.md', 'ready\n')
            before = self.snapshot(worker)
            with patch.object(adapter.reconcile, '_run_checks', return_value=['fixture checks']):
                result = adapter.ready_plan(worker, ready, include=['a.md'], machine='test', skill_roots=[live])
            self.assertEqual('ready', result['result'], result)
            self.assertEqual(before, self.snapshot(worker))
            self.assertFalse((sync_git.common_dir(repo) / 'agent-signal-published').exists())

    def test_aggregate_metadata_hashes_are_recomputed_on_composed_source(self):
        adapter = self.adapter()
        with tempfile.TemporaryDirectory() as temporary:
            repo, live, remote = self.setup_git(Path(temporary))
            self.extra_owner(repo, live)
            shutil.copyfile(fixtures.REPO / 'contracts/host-deltas.schema.json', repo / 'contracts/host-deltas.schema.json')
            manifest = json.loads((repo / 'host-deltas.json').read_text())
            manifest['entries'].append({'id': 'fleet', 'host': 'codex', 'category': 'native-skill',
                'owner': 'fleet-sync', 'source_identity': 'fleet:rendered admitted fleet',
                'version_or_hash': 'sha256:' + adapter.reconcile.host_deltas._canonical_fleet_digest(repo),
                'enablement': 'managed', 'prerequisites': [], 'desired_state': 'installed', 'required': False,
                'restore': {'kind': 'fleet', 'reference': 'rendered admitted fleet'},
                'readback': {'kind': 'fleet'}, 'redaction': 'public-artifact'})
            self.commit(repo, 'host-deltas.json', json.dumps(manifest))
            self.git(repo, 'add', 'contracts/host-deltas.schema.json')
            self.git(repo, 'commit', '-m', 'schema')
            self.git(repo, 'push', 'origin', 'main')
            a, b = self.worker(repo, 'a'), self.worker(repo, 'b')
            ready = []
            for worker, owner, digit in ((a, 'kept', 'a'), (b, 'other', 'b')):
                name = 'skills/' + owner + '/SKILL.md'
                (worker / name).write_text((worker / name).read_text() + '\nready ' + owner + '\n')
                changed = json.loads((worker / 'host-deltas.json').read_text())
                changed['entries'][0]['version_or_hash'] = 'sha256:' + digit * 64
                (worker / 'host-deltas.json').write_text(json.dumps(changed))
                self.git(worker, 'add', name, 'host-deltas.json')
                self.git(worker, 'commit', '-m', 'source plus generated metadata')
                ready.append(self.git(worker, 'rev-parse', 'HEAD'))
            for worker, owner, commit in ((a, 'kept', ready[0]), (b, 'other', ready[1])):
                result = self.run_ready(adapter, worker, commit, live, adopt=[owner])
                self.assertEqual('synced', result['result'], result)
            published = json.loads(self.git(remote, 'show', 'main:host-deltas.json'))
            lane = Path(result['published_repo'])
            self.assertEqual('sha256:' + adapter.reconcile.host_deltas._canonical_fleet_digest(lane),
                             published['entries'][0]['version_or_hash'])
            self.assertIn('ready kept', self.git(remote, 'show', 'main:skills/kept/SKILL.md'))
            self.assertIn('ready other', self.git(remote, 'show', 'main:skills/other/SKILL.md'))

    def test_selected_same_source_readback_policy_is_not_stripped(self):
        adapter = self.adapter()
        with tempfile.TemporaryDirectory() as temporary:
            repo, live, _ = self.setup_git(Path(temporary))
            self.binding_fixture(repo, live)
            worker = self.worker(repo, 'a')
            manifest = json.loads((worker / 'host-deltas.json').read_text())
            manifest['entries'][0]['readback']['sha256'] = 'f' * 64
            ready = self.commit(worker, 'host-deltas.json', json.dumps(manifest))
            result = self.run_ready(adapter, worker, ready, live, adopt=['kept'])
            self.assertEqual('incomplete', result['result'])
            self.assertIn('explicit host-deltas.json review', result['reason'])
            self.assertFalse((sync_git.common_dir(repo) / 'agent-signal-published').exists())

    def test_origin_failure_retries_published_receipt_without_redeployment(self):
        adapter = self.adapter()
        with tempfile.TemporaryDirectory() as temporary:
            repo, live, remote = self.setup_git(Path(temporary))
            worker = self.worker(repo, 'a')
            ready = self.commit(worker, 'a.md', 'ready\n')
            with patch.object(adapter.reconcile.fleet, 'migrate_source_origin', side_effect=RuntimeError('injected origin failure')):
                result = self.run_ready(adapter, worker, ready, live, include=['a.md'])
            self.assertEqual('incomplete', result['result'], result)
            self.assertTrue(result['publication_verified'])
            pushed = self.git(remote, 'rev-parse', 'main')
            journal = json.loads((sync_git.common_dir(repo) / 'agent-signal-integration.json').read_text())
            self.assertEqual('published', journal['phase'])
            self.assertEqual(pushed, journal['last_result']['commit'])
            self.git(repo, 'fetch', 'origin', 'main')
            external = repo.parent / 'external'
            self.git(repo, 'worktree', 'add', '-b', 'external', str(external), 'FETCH_HEAD')
            successor = self.commit(external, 'external.md', 'independent remote successor\n')
            self.git(external, 'push', 'origin', 'HEAD:main')
            (worker / 'a.md').write_text('next unfinished change\n')
            before = self.snapshot(worker)
            with patch.object(adapter.reconcile, 'complete_sync', side_effect=AssertionError('published retry must not deploy again')):
                result = self.run_ready(adapter, worker, ready, live, include=['a.md'])
            self.assertEqual('synced', result['result'], result)
            self.assertEqual(successor, self.git(remote, 'rev-parse', 'main'))
            self.assertEqual(pushed, self.git(Path(result['published_repo']), 'rev-parse', 'HEAD'))
            self.assertFalse((Path(result['published_repo']) / 'external.md').exists())
            self.assertEqual(before, self.snapshot(worker))

    def test_common_lock_contends_across_real_worktrees(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo, _, _ = self.setup_git(Path(temporary))
            a, b = self.worker(repo, 'a'), self.worker(repo, 'b')
            self.assertEqual(sync_git.common_dir(a), sync_git.common_dir(b))
            self.assertNotEqual(sync_git.git_dir(a), sync_git.git_dir(b))
            def competing_operator():
                try:
                    with sync_git.lock(b, timeout=0):
                        return 'incorrectly acquired'
                except sync_git.SyncBlocked as exc:
                    return str(exc)
            with sync_git.lock(a), ThreadPoolExecutor(max_workers=1) as pool:
                self.assertIn('another sync', pool.submit(competing_operator).result(timeout=10))
            with sync_git.lock(b, timeout=0):
                pass

    def test_pending_composition_rejects_edited_and_extra_source_bytes(self):
        adapter = self.adapter()
        with tempfile.TemporaryDirectory() as temporary:
            repo, live, remote = self.setup_git(Path(temporary))
            worker = self.worker(repo, 'a')
            ready = self.commit(worker, 'a.md', 'ready\n')
            with patch.object(adapter.reconcile, 'complete_sync', return_value={'result': 'incomplete', 'reason': 'before inner pending'}):
                result = self.run_ready(adapter, worker, ready, live, include=['a.md'])
            self.assertEqual('incomplete', result['result'])
            lane = Path(result['integration_repo'])
            before_remote = self.git(remote, 'rev-parse', 'main')
            (lane / 'a.md').write_text('unreviewed integration edit\n')
            with patch.object(adapter.reconcile, 'complete_sync', side_effect=AssertionError('drift must block before reconciliation')):
                result = self.run_ready(adapter, worker, ready, live, include=['a.md'])
            self.assertEqual('incomplete', result['result'], result)
            self.assertIn('composition changed', result['reason'])
            self.assertEqual(before_remote, self.git(remote, 'rev-parse', 'main'))
            self.assertEqual('unreviewed integration edit\n', (lane / 'a.md').read_text())
            (lane / 'a.md').write_text('ready\n')
            (lane / 'extra.md').write_text('unselected integration edit\n')
            with patch.object(adapter.reconcile, 'complete_sync', side_effect=AssertionError('extra file must block before reconciliation')):
                result = self.run_ready(adapter, worker, ready, live, include=['a.md'])
            self.assertEqual('incomplete', result['result'], result)
            self.assertIn('composition changed', result['reason'])
            self.assertTrue((lane / 'extra.md').exists())
            self.assertEqual(before_remote, self.git(remote, 'rev-parse', 'main'))

    def test_exact_registry_include_cannot_admit_staged_owner(self):
        adapter = self.adapter()
        with tempfile.TemporaryDirectory() as temporary:
            repo, live, remote = self.setup_git(Path(temporary))
            worker = self.worker(repo, 'a')
            registry = json.loads((worker / 'registry.json').read_text())
            for row in registry['skills']:
                if row['name'] == 'staged':
                    row['status'] = 'admitted'
            ready = self.commit(worker, 'registry.json', json.dumps(registry))
            result = self.run_ready(adapter, worker, ready, live, include=['registry.json'])
            self.assertEqual('incomplete', result['result'], result)
            self.assertIn('admission or lifecycle', result['reason'])
            published = json.loads(self.git(remote, 'show', 'main:registry.json'))
            self.assertEqual('staged', next(row['status'] for row in published['skills'] if row['name'] == 'staged'))
            self.assertFalse((sync_git.common_dir(repo) / 'agent-signal-integration-worktree').exists())

    def test_real_publisher_completion_crash_never_redeploys_selected_live_drift(self):
        adapter = self.adapter()
        class SimulatedProcessCrash(BaseException):
            pass
        with tempfile.TemporaryDirectory() as temporary:
            repo, live, remote = self.setup_git(Path(temporary))
            worker = self.worker(repo, 'a')
            name = 'skills/kept/SKILL.md'
            ready = self.commit(worker, name, (worker / name).read_text() + '\nchecked ready\n')
            complete = adapter.reconcile.complete_sync
            def crash_after_real_completion(*args, **kwargs):
                result = complete(*args, **kwargs)
                self.assertEqual('synced', result['result'], result)
                raise SimulatedProcessCrash()
            with patch.object(adapter.reconcile, 'complete_sync', side_effect=crash_after_real_completion):
                with self.assertRaises(SimulatedProcessCrash):
                    self.run_ready(adapter, worker, ready, live, adopt=['kept'])
            pushed = self.git(remote, 'rev-parse', 'main')
            lane = sync_git.common_dir(repo) / 'agent-signal-integration-worktree'
            pending = sync_git.read_pending(lane)
            self.assertEqual('synced', pending['completion']['result'])
            self.assertEqual(pushed, pending['completion']['commit'])
            checked_live = (live / 'kept/SKILL.md').read_bytes()
            (live / 'kept/SKILL.md').write_bytes(checked_live + b'\nunreviewed live edit\n')
            changed_live = (live / 'kept/SKILL.md').read_bytes()
            with patch.object(adapter.reconcile, 'complete_sync', side_effect=AssertionError('completed publication must not deploy again')):
                result = self.run_ready(adapter, worker, ready, live, adopt=['kept'])
            self.assertEqual('incomplete', result['result'], result)
            self.assertIn('selected installed owners changed', result['reason'])
            self.assertEqual(pushed, self.git(remote, 'rev-parse', 'main'))
            self.assertEqual(changed_live, (live / 'kept/SKILL.md').read_bytes())
            (live / 'kept/SKILL.md').write_bytes(checked_live)
            with patch.object(adapter.reconcile, 'complete_sync', side_effect=AssertionError('unchanged completion retry must only finish publication')):
                result = self.run_ready(adapter, worker, ready, live, adopt=['kept'])
            self.assertEqual('synced', result['result'], result)
            self.assertEqual(pushed, self.git(remote, 'rev-parse', 'main'))
            self.assertEqual(checked_live, (live / 'kept/SKILL.md').read_bytes())
            self.assertIsNone(sync_git.read_pending(lane))

    def test_ready_source_cannot_adopt_unchanged_selected_owner_live_drift(self):
        adapter = self.adapter()
        with tempfile.TemporaryDirectory() as temporary:
            repo, live, remote = self.setup_git(Path(temporary))
            worker = self.worker(repo, 'a')
            ready = self.commit(worker, 'a.md', 'ready source\n')
            original_source = (worker / 'skills/kept/SKILL.md').read_bytes()
            target = live / 'kept/SKILL.md'
            target.write_bytes(target.read_bytes() + b'\nunreviewed live edit\n')
            live_before, remote_before = target.read_bytes(), self.git(remote, 'rev-parse', 'main')
            with patch.object(adapter.reconcile, 'complete_sync', side_effect=AssertionError('live-origin adoption must stop before reconcile')):
                result = self.run_ready(adapter, worker, ready, live, adopt=['kept'], include=['a.md'])
            self.assertEqual('incomplete', result['result'], result)
            self.assertIn('cannot adopt an unreviewed live origin', result['reason'])
            self.assertEqual(remote_before, self.git(remote, 'rev-parse', 'main'))
            self.assertEqual(live_before, target.read_bytes())
            self.assertEqual(original_source, (worker / 'skills/kept/SKILL.md').read_bytes())

    def test_failed_ready_push_blocks_primary_publication_until_exact_retry(self):
        adapter = self.adapter()
        with tempfile.TemporaryDirectory() as temporary:
            repo, live, remote = self.setup_git(Path(temporary))
            worker = self.worker(repo, 'a')
            ready = self.commit(worker, 'a.md', 'checked ready\n')
            before_remote = self.git(remote, 'rev-parse', 'main')
            original_git = adapter.sync_git.git
            def fail_push(git_repo, *args, **kwargs):
                if args and args[0] == 'push':
                    raise sync_git.SyncBlocked('injected ready push failure')
                return original_git(git_repo, *args, **kwargs)
            with patch.object(adapter.sync_git, 'git', side_effect=fail_push):
                result = self.run_ready(adapter, worker, ready, live, include=['a.md'])
            self.assertEqual('incomplete', result['result'], result)
            self.assertEqual('push', result['failed_step'])
            (repo / 'b.md').write_text('independent primary work\n')
            primary_before = self.snapshot(repo)
            blocked = self.reconcile.complete_sync(repo, machine='test', skill_roots=[live],
                        recovery_roots={}, include=['b.md'], scoped=True, capture_recovery=False)
            self.assertEqual('incomplete', blocked['result'], blocked)
            self.assertEqual(before_remote, self.git(remote, 'rev-parse', 'main'))
            self.assertEqual(primary_before, self.snapshot(repo))
            result = self.run_ready(adapter, worker, ready, live, include=['a.md'])
            self.assertEqual('synced', result['result'], result)
            self.assertEqual('checked ready', self.git(remote, 'show', 'main:a.md'))
            self.assertEqual(primary_before, self.snapshot(repo))

    def test_include_only_real_completion_crash_finishes_same_commit(self):
        adapter = self.adapter()
        class SimulatedProcessCrash(BaseException):
            pass
        with tempfile.TemporaryDirectory() as temporary:
            repo, live, remote = self.setup_git(Path(temporary))
            worker = self.worker(repo, 'a')
            ready = self.commit(worker, 'a.md', 'checked source only\n')
            complete = adapter.reconcile.complete_sync
            def crash_after_completion(*args, **kwargs):
                result = complete(*args, **kwargs)
                self.assertEqual('synced', result['result'], result)
                raise SimulatedProcessCrash()
            with patch.object(adapter.reconcile, 'complete_sync', side_effect=crash_after_completion):
                with self.assertRaises(SimulatedProcessCrash):
                    self.run_ready(adapter, worker, ready, live, include=['a.md'])
            pushed = self.git(remote, 'rev-parse', 'main')
            lane = sync_git.common_dir(repo) / 'agent-signal-integration-worktree'
            self.assertEqual({}, sync_git.read_pending(lane)['agent_identities'])
            with patch.object(adapter.reconcile, 'complete_sync', side_effect=AssertionError('include-only completion retry must not deploy')):
                result = self.run_ready(adapter, worker, ready, live, include=['a.md'])
            self.assertEqual('synced', result['result'], result)
            self.assertTrue(result['completion_recovered'])
            self.assertFalse(result['installed_verified'])
            self.assertEqual(pushed, self.git(remote, 'rev-parse', 'main'))
            self.assertIsNone(sync_git.read_pending(lane))
            origin = json.loads((live / self.fleet.STATE_FILE).read_text())['source_snapshot']
            self.assertEqual(str(Path(result['published_repo']) / 'render/fleet'), origin)


    def test_inner_ready_capture_rejects_source_race_after_outer_check(self):
        adapter = self.adapter()
        with tempfile.TemporaryDirectory() as temporary:
            repo, live, remote = self.setup_git(Path(temporary))
            worker = self.worker(repo, 'a')
            ready = self.commit(worker, 'a.md', 'checked ready\n')
            before = self.git(remote, 'rev-parse', 'main')
            original = adapter.reconcile.complete_sync
            def racing_complete(lane, **options):
                (lane / 'a.md').write_bytes(b'unreviewed injected source race\n')
                return original(lane, **options)
            with patch.object(adapter.reconcile, 'complete_sync', side_effect=racing_complete):
                result = self.run_ready(adapter, worker, ready, live, include=['a.md'])
            self.assertEqual('incomplete', result['result'], result)
            self.assertIn('frozen ready', result['reason'])
            self.assertEqual(before, self.git(remote, 'rev-parse', 'main'))
            self.assertFalse((live / 'a.md').exists())
            lane = sync_git.common_dir(repo) / 'agent-signal-integration-worktree'
            self.assertEqual(b'unreviewed injected source race\n', (lane / 'a.md').read_bytes())

    def test_native_defaults_honor_pending_ready_before_preparation(self):
        import runtime_defaults
        with tempfile.TemporaryDirectory() as temporary:
            repo, live, remote = self.setup_git(Path(temporary))
            before = self.git(remote, 'rev-parse', 'main')
            (sync_git.common_dir(repo) / 'agent-signal-integration.json').write_text(json.dumps(
                {'attempt': 'other-attempt', 'integration_repo': str(repo.parent / 'integration')}))
            with patch.object(runtime_defaults, 'prepare_defaults') as prepare:
                result = self.reconcile.complete_defaults_sync(repo, hosts=['codex'], machine='test', skill_roots=[live])
            self.assertEqual('incomplete', result['result'], result)
            self.assertIn('ready integration is pending', result['reason'])
            prepare.assert_not_called()
            self.assertEqual(before, self.git(remote, 'rev-parse', 'main'))

    def test_actual_sync_rejects_canonical_race_before_live_mutation(self):
        adapter = self.adapter()
        with tempfile.TemporaryDirectory() as temporary:
            repo, live, remote = self.setup_git(Path(temporary))
            worker = self.worker(repo, 'a')
            source = 'skills/kept/SKILL.md'
            ready = self.commit(worker, source, (worker / source).read_text() + '\nchecked source change\n')
            before = self.git(remote, 'rev-parse', 'main')
            live_before = (live / 'kept/SKILL.md').read_bytes()
            original = adapter.reconcile.sync
            def racing_sync(lane, **options):
                (lane / source).write_bytes((lane / source).read_bytes() + b'\nunreviewed deployment race\n')
                return original(lane, **options)
            with patch.object(adapter.reconcile, 'sync', side_effect=racing_sync):
                result = self.run_ready(adapter, worker, ready, live, adopt=['kept'])
            self.assertEqual('incomplete', result['result'], result)
            self.assertIn('frozen ready', result['reason'])
            self.assertEqual(before, self.git(remote, 'rev-parse', 'main'))
            self.assertEqual(live_before, (live / 'kept/SKILL.md').read_bytes())


    def test_raw_legacy_blobs_do_not_block_owned_worktree_publication(self):
        adapter = self.adapter()
        with tempfile.TemporaryDirectory() as temporary:
            repo, live, remote = self.setup_git(Path(temporary))
            (repo / '.gitattributes').write_bytes(b'*.md text eol=lf\n')
            self.git(repo, 'add', '.gitattributes')
            raw = b'legacy committed CRLF\r\n'
            oid = sync_git._raw_git(repo, 'hash-object', '-w', '--stdin', input=raw).decode().strip()
            self.git(repo, 'update-index', '--add', '--cacheinfo', '100644', oid, 'legacy.md')
            self.git(repo, 'commit', '-m', 'legacy raw blob under text attributes')
            (repo / 'legacy.md').write_bytes(raw)
            self.git(repo, 'push', 'origin', 'main')
            worker = self.worker(repo, 'a')
            ready = self.commit(worker, 'a.md', 'checked ready\n')
            result = self.run_ready(adapter, worker, ready, live, include=['a.md'])
            self.assertEqual('synced', result['result'], result)
            for name in ['integration_repo', 'published_repo']:
                self.assertEqual(raw, (Path(result[name]) / 'legacy.md').read_bytes())
                self.assertFalse(sync_git.changed(Path(result[name])))


if __name__ == '__main__':
    unittest.main()
