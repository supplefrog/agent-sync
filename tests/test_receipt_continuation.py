"""Explicit receipt review resumes a real retained deployed Git transaction."""
from pathlib import Path
import hashlib
import json
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
        result = self.run_ready(tool, worker, ready, live, adopt=['kept'], include=[predicted])
        self.assertEqual('incomplete', result['result'], result)
        self.assertIn('publication paths differ', result['reason'])
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
