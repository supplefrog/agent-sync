"""Explicit receipt review resumes a real retained deployed Git transaction."""
from pathlib import Path
import hashlib
import importlib.util
import json
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import test_reconcile as fixtures
import test_worktree_sync as ready_fixtures
import sync_git


class ReceiptContinuationTests(unittest.TestCase):
    setUp = ready_fixtures.WorktreeSyncTests.setUp
    fixture = ready_fixtures.WorktreeSyncTests.fixture
    git = ready_fixtures.WorktreeSyncTests.git
    setup_git = ready_fixtures.WorktreeSyncTests.setup_git
    worker = ready_fixtures.WorktreeSyncTests.worker
    binding_fixture = ready_fixtures.WorktreeSyncTests.binding_fixture
    extra_owner = ready_fixtures.WorktreeSyncTests.extra_owner

    def fixture_checks(self, repo, commands):
        return ['fixture checks'] if commands else []

    def run_ready(self, tool, worker, ready, live, **kwargs):
        with patch.object(tool.reconcile, '_run_checks', side_effect=self.fixture_checks):
            return tool.ready_sync(worker, ready, machine='test', skill_roots=[live], **kwargs)

    def prepare(self, root):
        repo, live, remote = self.setup_git(root)
        self.binding_fixture(repo, live)
        worker = self.worker(repo, 'receipt-worker')
        target = worker / 'skills/kept/fixture.txt'
        target.write_bytes(b'Explicit selected owner update.\n')
        self.git(worker, 'add', '.')
        self.git(worker, 'commit', '-m', 'selected owner update')
        ready = self.git(worker, 'rev-parse', 'HEAD')
        tool = fixtures.load_tool('worktree_sync')
        predicted = 'reconciliation/requests/' + 'a' * 64 + '.json'
        # Exercise a real retained transaction from before private operational
        # storage. The repaired producer no longer creates this legacy refusal.
        baseline = '88f7c44dab8bf1f0f7ba942d83da501de6b01d67'
        legacy_raw = subprocess.run(['git', '-C', str(Path(__file__).resolve().parents[1]),
            'show', baseline + ':tools/reconcile.py'], capture_output=True, check=True).stdout
        legacy_source = root / 'legacy-source'
        legacy_path = legacy_source / 'tools/reconcile.py'
        legacy_path.parent.mkdir(parents=True)
        legacy_path.write_bytes(legacy_raw)
        schema = legacy_source / 'contracts/change-request.schema.json'
        schema.parent.mkdir()
        schema.write_bytes(subprocess.run(['git', '-C', str(Path(__file__).resolve().parents[1]),
            'show', baseline + ':contracts/change-request.schema.json'], capture_output=True, check=True).stdout)
        spec = importlib.util.spec_from_file_location('legacy_receipt_producer', legacy_path)
        legacy = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(legacy)
        with patch.object(tool, 'reconcile', legacy):
            result = self.run_ready(tool, worker, ready, live, adopt=['kept'], include=[predicted])
        self.assertEqual('incomplete', result['result'], result)
        self.assertIn('publication paths differ', result['reason'], result)
        common = sync_git.common_dir(repo)
        raw = (common / 'agent-signal-integration.json').read_bytes()
        journal = json.loads(raw)
        lane = Path(journal['integration_repo'])
        self.assertTrue(journal['deployment_started'])
        self.assertIsNone(sync_git.read_pending(lane))
        generated = next(n for n in sync_git.changed(lane) if n.startswith('reconciliation/requests/'))
        request = {'schema_version': 1, 'kind': 'reviewed-generated-receipt',
                   'attempt': journal['attempt'], 'journal_sha256': hashlib.sha256(raw).hexdigest(),
                   'ready': ready, 'base': journal['base'], 'request_path': generated,
                   'files': sync_git.identities(lane, sync_git.changed(lane)),
                   'include': sorted(journal['receipt']['options']['include'] + [generated]),
                   'live': {str(live): {'managed_state_sha256': self.fleet.sha256_file(live / self.fleet.STATE_FILE),
                                       'owners': {'kept': self.fleet.installed_hash(live / 'kept')}}},
                   'review': {'decision': 'accept-generated-receipt', 'reason': 'Reviewed fixture operation and exact artifacts.',
                              'reviewer_ref': 'synthetic-fixture-source-review'}}
        return repo, live, remote, worker, tool, request, raw, lane

    def augment(self, tool, worker, request):
        # Application checks are a fixture boundary; receipt, Git, bindings,
        # installed bytes, journal and publication gates remain real.
        with patch.object(tool.reconcile, '_run_checks', side_effect=self.fixture_checks):
            return tool.augment_deployed_receipt(worker, request)

    def private_ready_fixture(self, root):
        repo, live, remote = self.setup_git(root)
        worker = self.worker(repo, 'private-receipt-worker')
        (worker / 'skills/kept/fixture.txt').write_bytes(b'Private receipt selected change.\n')
        self.git(worker, 'add', '.')
        self.git(worker, 'commit', '-m', 'selected owner change')
        return repo, live, remote, worker, fixtures.load_tool('worktree_sync'), self.git(worker, 'rev-parse', 'HEAD')

    def test_required_private_ready_completion_retains_reference(self):
        with tempfile.TemporaryDirectory() as temp:
            repo, live, remote, worker, tool, ready = self.private_ready_fixture(Path(temp))
            result = self.run_ready(tool, worker, ready, live, adopt=['kept'])
            self.assertEqual('synced', result['result'], result)
            reference = result['operational_receipt']
            self.assertEqual('private', reference['storage'])
            self.assertEqual(result['request_id'], reference['request_id'])
            self.assertEqual(reference['sha256'], hashlib.sha256(Path(reference['path']).read_bytes()).hexdigest())
            self.assertEqual('', self.git(remote, 'ls-tree', 'main', '--',
                'reconciliation/requests/' + reference['request_id'] + '.json'))
            self.assertFalse((sync_git.common_dir(repo) / 'agent-signal-integration.json').exists())

    def test_ready_private_evidence_loss_retains_published_recovery_without_push_replay(self):
        cases = ('missing-body', 'corrupt-body', 'missing-reference', 'missing-requirement',
                 'missing-publisher-state', 'final-readback', 'published-retry')
        for failure in cases:
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as temp:
                root = Path(temp).resolve()
                repo, live, remote, worker, tool, ready = self.private_ready_fixture(root)
                original_finish = tool._finish_published
                original_rollout = tool._rollout_targets
                retained = {}
                def capture(lane):
                    pending = sync_git.read_pending(lane)
                    self.assertEqual(2, pending['schema_version'])
                    self.assertIs(True, pending['operational_receipt_required'])
                    reference = tool.reconcile._operational_receipt_state(lane, pending)
                    body = Path(reference['path']).resolve()
                    self.assertTrue(body.is_relative_to(root))
                    pending_path = sync_git.git_dir(lane) / 'agent-signal-sync.json'
                    retained.update(lane=lane, body=body, body_raw=body.read_bytes(),
                        pending_path=pending_path, pending_raw=pending_path.read_bytes(), commit=pending['commit'])
                    return pending
                def finish(*args, **kwargs):
                    pending = capture(args[3])
                    if failure in {'missing-body', 'published-retry'}:
                        retained['body'].unlink()
                    elif failure == 'corrupt-body':
                        retained['body'].write_bytes(retained['body_raw'] + b'changed')
                    elif failure in {'missing-reference', 'missing-requirement'}:
                        pending.pop('operational_receipt' if failure == 'missing-reference' else 'operational_receipt_required')
                        retained['pending_path'].write_text(json.dumps(pending))
                    elif failure == 'missing-publisher-state':
                        retained['pending_path'].unlink()
                    return original_finish(*args, **kwargs)
                def rollout(*args, **kwargs):
                    result = original_rollout(*args, **kwargs)
                    if failure == 'final-readback':retained['body'].unlink()
                    return result
                with patch.object(tool, '_finish_published', side_effect=finish), patch.object(tool, '_rollout_targets', side_effect=rollout):
                    result = self.run_ready(tool, worker, ready, live, adopt=['kept'])
                self.assertEqual('incomplete', result['result'], result)
                journal_path = sync_git.common_dir(repo) / 'agent-signal-integration.json'
                journal = json.loads(journal_path.read_bytes())
                self.assertEqual('published', journal['phase'])
                self.assertEqual(retained['commit'], self.git(remote, 'rev-parse', 'main'))
                self.assertEqual('Private receipt selected change.', self.git(remote, 'show', 'main:skills/kept/fixture.txt'))
                if failure != 'missing-publisher-state':self.assertIsNotNone(sync_git.read_pending(retained['lane']))
                if failure == 'published-retry':
                    with patch.object(sync_git, 'git', wraps=sync_git.git) as calls:
                        retry = self.run_ready(tool, worker, ready, live, adopt=['kept'])
                    self.assertEqual('incomplete', retry['result'], retry)
                    self.assertFalse(any('push' in call.args[1:] for call in calls.call_args_list))
                    self.assertTrue(journal_path.is_file())
                    # Restore exact retained fixture evidence, then qualify a
                    # normal published retry. Never recreate a successful push.
                    retained['body'].write_bytes(retained['body_raw'])
                    with patch.object(sync_git, 'git', wraps=sync_git.git) as calls:
                        completed = self.run_ready(tool, worker, ready, live, adopt=['kept'])
                    self.assertEqual('synced', completed['result'], completed)
                    self.assertFalse(any('push' in call.args[1:] for call in calls.call_args_list))
                    self.assertEqual(retained['commit'], self.git(remote, 'rev-parse', 'main'))
                    self.assertFalse(journal_path.exists())

    def test_own_pending_unlink_crash_reuses_durable_exact_completion(self):
        with tempfile.TemporaryDirectory() as temp:
            repo, live, remote, worker, tool, ready = self.private_ready_fixture(Path(temp))
            journal_path = sync_git.common_dir(repo) / 'agent-signal-integration.json'
            original_unlink = Path.unlink
            observed = {}
            def interrupt(path, *args, **kwargs):
                if path == journal_path:
                    journal = json.loads(path.read_bytes())
                    retained = journal['publisher_completion_state']
                    self.assertIsNone(sync_git.read_pending(Path(journal['integration_repo'])))
                    reference = tool.reconcile._operational_receipt_state(Path(journal['integration_repo']), retained)
                    body = Path(reference['path'])
                    observed.update(body=body, raw=body.read_bytes(), commit=retained['commit'])
                    raise OSError('fixture crash after own inner pending unlink')
                return original_unlink(path, *args, **kwargs)
            with patch.object(Path, 'unlink', interrupt):
                first = self.run_ready(tool, worker, ready, live, adopt=['kept'])
            self.assertEqual('incomplete', first['result'], first)
            self.assertTrue(journal_path.exists())
            self.assertEqual(observed['commit'], self.git(remote, 'rev-parse', 'main'))
            observed['body'].unlink()
            with patch.object(sync_git, 'git', wraps=sync_git.git) as calls:
                lost = self.run_ready(tool, worker, ready, live, adopt=['kept'])
            self.assertEqual('incomplete', lost['result'], lost)
            self.assertTrue(journal_path.exists())
            self.assertFalse(any('push' in call.args[1:] for call in calls.call_args_list))
            observed['body'].write_bytes(observed['raw'])
            with patch.object(sync_git, 'git', wraps=sync_git.git) as calls:
                final = self.run_ready(tool, worker, ready, live, adopt=['kept'])
            self.assertEqual('synced', final['result'], final)
            self.assertEqual(observed['commit'], final['commit'])
            self.assertFalse(any('push' in call.args[1:] for call in calls.call_args_list))
            self.assertFalse(journal_path.exists())
            self.assertEqual('Private receipt selected change.', self.git(remote, 'show', 'main:skills/kept/fixture.txt'))

    def test_ready_source_only_work_without_operational_selection_needs_no_receipt(self):
        with tempfile.TemporaryDirectory() as temp:
            repo, live, remote = self.setup_git(Path(temp))
            worker = self.worker(repo, 'no-operation-worker')
            (worker / 'fixture-note.txt').write_bytes(b'Ordinary source change.\n')
            self.git(worker, 'add', '.')
            self.git(worker, 'commit', '-m', 'source change without owner operation')
            ready = self.git(worker, 'rev-parse', 'HEAD')
            tool = fixtures.load_tool('worktree_sync')
            result = self.run_ready(tool, worker, ready, live, include=['fixture-note.txt'])
            self.assertEqual('synced', result['result'], result)
            self.assertNotIn('operational_receipt', result)
            self.assertNotIn('request_id', result)

    def test_review_retains_evidence_is_idempotent_and_normal_retry_publishes(self):
        with tempfile.TemporaryDirectory() as temp:
            repo, live, remote, worker, tool, request, raw, lane = self.prepare(Path(temp))
            head, installed, source = self.git(remote, 'rev-parse', 'main'), fixtures.digest(live), fixtures.digest(lane)
            result = self.augment(tool, worker, request)
            self.assertEqual('reviewed', result['result'])
            self.assertEqual(head, self.git(remote, 'rev-parse', 'main'))
            self.assertEqual(installed, fixtures.digest(live))
            self.assertEqual(source, fixtures.digest(lane))
            archive = sync_git.common_dir(repo) / ('agent-signal-receipt-review-' + request['attempt'])
            self.assertEqual(raw, (archive / 'original-journal.json').read_bytes())
            journal_path = sync_git.common_dir(repo) / 'agent-signal-integration.json'
            reviewed = journal_path.read_bytes()
            self.assertEqual('unchanged', self.augment(tool, worker, request)['result'])
            self.assertEqual(reviewed, journal_path.read_bytes())
            final = self.run_ready(tool, worker, request['ready'], live, adopt=['kept'], include=request['include'])
            self.assertEqual('synced', final['result'], final)
            self.assertEqual('Explicit selected owner update.', self.git(remote, 'show', 'main:skills/kept/fixture.txt'))
            self.assertEqual(b'Explicit selected owner update.\n', (live / 'kept/fixture.txt').read_bytes())
            self.assertEqual([], self.fleet.verify_snapshot(Path(final['published_repo']) / 'render/fleet', live))

    def test_invalid_review_refuses_without_journal_source_live_or_remote_mutation(self):
        for failure in ('journal', 'scope', 'source', 'extra', 'live', 'live-rebound',
                        'receipt', 'duplicate-artifact', 'policy', 'pending', 'remote', 'marker'):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as temp:
                repo, live, remote, worker, tool, request, raw, lane = self.prepare(Path(temp))
                if failure == 'journal': request['journal_sha256'] = 'b' * 64
                if failure == 'scope': request['include'].append('unreviewed.txt')
                if failure == 'source':
                    (lane / 'skills/kept/fixture.txt').write_bytes(b'Changed after initial review.\n')
                    request['files'] = sync_git.identities(lane, sync_git.changed(lane))
                if failure == 'extra':
                    (lane / 'extra.txt').write_bytes(b'unrelated')
                    request['files'] = sync_git.identities(lane, sync_git.changed(lane))
                if failure == 'live': request['live'][str(live)]['managed_state_sha256'] = 'b' * 64
                if failure == 'live-rebound':
                    (live / 'kept/fixture.txt').write_bytes(b'Unreviewed installed content.\n')
                    request['live'][str(live)]['owners']['kept'] = self.fleet.installed_hash(live / 'kept')
                if failure in ('receipt', 'duplicate-artifact'):
                    path = lane / request['request_path']
                    value = json.loads(path.read_bytes())
                    if failure == 'receipt': value['owners'] = ['other']
                    else: value['artifacts'].append(value['artifacts'][0])
                    path.write_text(json.dumps(value))
                    request['files'] = sync_git.identities(lane, sync_git.changed(lane))
                if failure == 'policy':
                    path = lane / 'host-deltas.json'
                    value = json.loads(path.read_bytes()); value['entries'][0]['required'] = True
                    path.write_text(json.dumps(value))
                    request['files'] = sync_git.identities(lane, sync_git.changed(lane))
                if failure == 'pending': (sync_git.git_dir(lane) / 'agent-signal-sync.json').write_text('null')
                if failure == 'remote':
                    self.git(repo, 'commit', '--allow-empty', '-m', 'independent remote advancement')
                    self.git(repo, 'push', 'origin', 'main')
                if failure == 'marker':
                    path = sync_git.common_dir(repo) / 'agent-signal-published.json'
                    value = json.loads(path.read_bytes()); value['head'] = 'b' * 40
                    path.write_text(json.dumps(value))
                before = (fixtures.digest(lane), fixtures.digest(live), self.git(remote, 'rev-parse', 'main'))
                with self.assertRaises((sync_git.SyncBlocked, ValueError, RuntimeError)):
                    self.augment(tool, worker, request)
                self.assertEqual(raw, (sync_git.common_dir(repo) / 'agent-signal-integration.json').read_bytes())
                self.assertEqual(before, (fixtures.digest(lane), fixtures.digest(live), self.git(remote, 'rev-parse', 'main')))

    def test_archive_before_transition_interruption_retries_exact_review(self):
        with tempfile.TemporaryDirectory() as temp:
            repo, live, remote, worker, tool, request, raw, lane = self.prepare(Path(temp))
            with patch.object(tool, '_atomic', side_effect=RuntimeError('interrupted before journal replacement')):
                with self.assertRaisesRegex(RuntimeError, 'interrupted'):
                    self.augment(tool, worker, request)
            self.assertEqual(raw, (sync_git.common_dir(repo) / 'agent-signal-integration.json').read_bytes())
            self.assertEqual('reviewed', self.augment(tool, worker, request)['result'])

    def test_new_path_during_checks_refuses_before_transition(self):
        with tempfile.TemporaryDirectory() as temp:
            repo, live, remote, worker, tool, request, raw, lane = self.prepare(Path(temp))
            head, installed = self.git(remote, 'rev-parse', 'main'), fixtures.digest(live)
            def concurrent_change(*args, **kwargs):
                (lane / 'concurrent.txt').write_bytes(b'Concurrent work must remain intact.\n')
                return ['fixture checks']
            with patch.object(tool.reconcile, '_run_checks', side_effect=concurrent_change):
                with self.assertRaisesRegex(sync_git.SyncBlocked, 'before transition'):
                    tool.augment_deployed_receipt(worker, request)
            self.assertEqual(raw, (sync_git.common_dir(repo) / 'agent-signal-integration.json').read_bytes())
            self.assertEqual(head, self.git(remote, 'rev-parse', 'main'))
            self.assertEqual(installed, fixtures.digest(live))
            self.assertEqual(b'Concurrent work must remain intact.\n', (lane / 'concurrent.txt').read_bytes())

    def test_altered_writer_claims_reject_even_with_fresh_review_hashes(self):
        with tempfile.TemporaryDirectory() as temp:
            repo, live, remote, worker, tool, request, raw, lane = self.prepare(Path(temp))
            path = lane / request['request_path']
            original = json.loads(path.read_bytes())
            head, installed = self.git(remote, 'rev-parse', 'main'), fixtures.digest(live)
            for key, value in (('$schema', '../unreviewed.json'), ('risk', 'high'),
                               ('disposition', 'rejected'), ('checks', ['unexecuted claimed check'])):
                with self.subTest(key=key):
                    body = dict(original); body[key] = value
                    path.write_text(json.dumps(body))
                    request['files'] = sync_git.identities(lane, sync_git.changed(lane))
                    before = fixtures.digest(lane)
                    with self.assertRaisesRegex(sync_git.SyncBlocked, 'canonical completed selected operation'):
                        self.augment(tool, worker, request)
                    self.assertEqual(raw, (sync_git.common_dir(repo) / 'agent-signal-integration.json').read_bytes())
                    self.assertEqual(before, fixtures.digest(lane))
                    self.assertEqual(head, self.git(remote, 'rev-parse', 'main'))
                    self.assertEqual(installed, fixtures.digest(live))


if __name__ == '__main__': unittest.main()
