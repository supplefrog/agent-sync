"""Real local Git fixtures; no transport, deployment, or model calls."""
from pathlib import Path
import hashlib
import json
import os
import sys
import tempfile
import unittest
import uuid
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import sync_git
import worktree_sync as coordinator


class IntegrationReleaseTests(unittest.TestCase):
    def setUp(self):
        # Explicitly provisioned Windows fixtures are retained for inspection.
        # Ordinary CI uses the standard temporary-directory lifetime.
        if os.environ.get('AGENT_SYNC_TEST_WORKSPACE'):
            root = Path(os.environ['AGENT_SYNC_TEST_WORKSPACE']).resolve()
            self.root = root / uuid.uuid4().hex
            self.root.mkdir()
        else:
            temporary = tempfile.TemporaryDirectory()
            self.addCleanup(temporary.cleanup)
            self.root = Path(temporary.name)
        self.repo = self.root / 'source'
        self.repo.mkdir()
        git = sync_git.git
        git(self.repo, 'init', '-b', 'main')
        git(self.repo, 'config', 'user.name', 'Fixture')
        git(self.repo, 'config', 'user.email', 'fixture@example.invalid')
        git(self.repo, 'config', 'core.autocrlf', 'false')
        git(self.repo, 'remote', 'add', 'origin', str(self.root / 'unused-remote'))
        git(self.repo, 'config', 'branch.main.remote', 'origin')
        git(self.repo, 'config', 'branch.main.merge', 'refs/heads/main')
        (self.repo / 'kept.txt').write_bytes(b'baseline\n')
        (self.repo / 'deleted.txt').write_bytes(b'original\n')
        git(self.repo, 'add', '.')
        git(self.repo, 'commit', '-m', 'fixture baseline')
        self.base = git(self.repo, 'rev-parse', 'HEAD')
        self.common = sync_git.common_dir(self.repo)
        self.target = sync_git.destination(self.repo)
        self.lane = self.common / 'agent-signal-integration-worktree'
        self.published = self.common / 'agent-signal-published'
        for lane, branch in ((self.lane, coordinator.INTEGRATION_BRANCH), (self.published, coordinator.BRANCH)):
            git(self.repo, 'worktree', 'add', '-b', branch, str(lane), 'HEAD')
            git(self.repo, 'config', 'branch.' + branch + '.remote', 'origin')
            git(self.repo, 'config', 'branch.' + branch + '.merge', 'refs/heads/main')
            coordinator._atomic(self.common / (lane.name + '.json'), {
                'schema_version': 1, 'common_repo': str(self.common), 'target': self.target, 'head': self.base})
        (self.lane / 'kept.txt').write_bytes(b'candidate\r\n')
        (self.lane / 'deleted.txt').unlink()
        (self.lane / 'added.bin').write_bytes(b'\x00\xffcandidate')
        git(self.lane, 'add', '.')
        tree = git(self.lane, 'write-tree')
        git(self.lane, 'reset', '--mixed', self.base)
        self.attempt = 'a' * 32
        receipt = {'ready': self.base, 'source_base': self.base, 'source_commits': [self.base],
                   'target': self.target, 'options': {'adopt': ['kept']}}
        self.journal = {'schema_version': 1, 'attempt': self.attempt, 'phase': 'reconciling',
                        'deployment_started': False,
                        'receipt': receipt, 'base': self.base, 'integration_repo': str(self.lane),
                        'published_repo': str(self.published), 'composition_files': sync_git.identities(self.lane, sync_git.changed(self.lane)),
                        'composed_tree': tree, 'origin_destinations': [], 'last_result': {
                            'result': 'review-required', 'reason': 'selected owner missing, unadmitted, or conflicting',
                            'owners': ['kept'], 'ready': self.base, 'base': self.base,
                            'source_base': self.base, 'source_commits': [self.base],
                            'integration_repo': str(self.lane), 'published_repo': str(self.published),
                            'measurements': {'checks': []}}}
        self.journal_path = self.common / 'agent-signal-integration.json'
        self.save()
        self.original = self.journal_path.read_bytes()
        self.before = self.snapshot(self.lane)
        (self.repo / 'unfinished.txt').write_bytes(b'unrelated source edit')
        (self.published / 'kept.txt').write_bytes(b'unrelated published edit')
        self.source_before = self.snapshot(self.repo)
        self.published_before = self.snapshot(self.published)

    def save(self):
        coordinator._atomic(self.journal_path, self.journal)

    def snapshot(self, root):
        return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*')
                if p.is_file() and '.git' not in p.relative_to(root).parts}

    def release(self):
        return coordinator.release_predeployment(self.repo, self.attempt)

    def assert_refused(self):
        before = self.journal_path.read_bytes()
        lane_before = self.snapshot(self.lane)
        result = self.release()
        self.assertEqual('review-required', result['result'], result)
        self.assertEqual(before, self.journal_path.read_bytes())
        self.assertEqual(lane_before, self.snapshot(self.lane))
        self.assertFalse((self.common / ('agent-signal-released-' + self.attempt)).exists())

    def test_release_retains_all_bytes_index_journals_and_source(self):
        index = (sync_git.git_dir(self.lane) / 'index').read_bytes()
        result = self.release()
        self.assertEqual('released', result['result'], result)
        archive = Path(result['archive'])
        retained = Path(result['retained_worktree'])
        self.assertEqual(self.original, (archive / 'attempt.json').read_bytes())
        self.assertEqual(self.before, self.snapshot(retained))
        # Git may refresh index stat metadata during worktree move; its tree stays exact.
        self.assertEqual(sync_git.git(retained, 'write-tree'), sync_git.git(retained, 'rev-parse', self.base + '^{tree}'))
        self.assertTrue(index)
        self.assertFalse(self.journal_path.exists())
        self.assertTrue((archive / 'release.json').is_file())
        self.assertTrue((archive / 'integration-marker.json').is_file())
        self.assertFalse(self.lane.exists())
        self.assertEqual(self.source_before, self.snapshot(self.repo))
        self.assertEqual(self.published_before, self.snapshot(self.published))
        sync_git.assert_integration_owner(self.repo)
        self.assertEqual('', sync_git.git(self.repo, 'for-each-ref', '--format=%(refname)', 'refs/heads/' + coordinator.INTEGRATION_BRANCH))
        # A new lane can be created with the released branch and original path.
        sync_git.git(self.repo, 'worktree', 'add', '-b', coordinator.INTEGRATION_BRANCH, str(self.lane), self.base)
        self.assertEqual(set(), sync_git.changed(self.lane))

    def test_wrong_attempt_and_invalid_attempt_refused(self):
        for attempt in ('b' * 32, '../outside'):
            self.assertEqual('review-required', coordinator.release_predeployment(self.repo, attempt)['result'])
        self.assertEqual(self.original, self.journal_path.read_bytes())

    def test_deployed_or_empty_publisher_receipt_refused(self):
        (sync_git.git_dir(self.lane) / 'agent-signal-sync.json').write_bytes(b'{}')
        self.assert_refused()

    def test_published_inner_receipt_refused(self):
        (sync_git.git_dir(self.published) / 'agent-signal-sync.json').write_bytes(b'{}')
        self.assert_refused()

    def test_publication_result_or_unknown_result_fields_refused(self):
        for key in ('commit', 'installed_verified', 'completion', 'unexpected'):
            with self.subTest(key=key):
                self.journal['last_result'][key] = 'uncertain'
                self.save()
                self.assert_refused()
                del self.journal['last_result'][key]

    def test_unknown_or_published_phase_refused(self):
        for phase in ('published', 'composed', 'composing', 'unknown'):
            with self.subTest(phase=phase):
                self.journal['phase'] = phase
                self.save()
                self.assert_refused()

    def test_later_rejection_and_completed_checks_refused(self):
        self.journal['last_result']['reason'] = 'some later failure'
        self.save()
        self.assert_refused()
        self.journal['last_result']['reason'] = 'selected owner missing, unadmitted, or conflicting'
        self.journal['last_result']['measurements']['checks'] = ['ran']
        self.save()
        self.assert_refused()

    def test_unbound_result_refused(self):
        self.journal['last_result']['ready'] = 'b' * 40
        self.save()
        self.assert_refused()

    def test_edited_composition_refused(self):
        (self.lane / 'kept.txt').write_bytes(b'concurrent edit')
        self.assert_refused()

    def test_extra_file_refused(self):
        (self.lane / 'extra.txt').write_bytes(b'concurrent extra')
        self.assert_refused()

    def test_staged_change_refused(self):
        sync_git.git(self.lane, 'add', 'kept.txt')
        self.assert_refused()

    def test_git_operation_refused(self):
        (sync_git.git_dir(self.lane) / 'CHERRY_PICK_HEAD').write_text(self.base)
        self.assert_refused()

    def test_frozen_tree_mismatch_refused(self):
        self.journal['composed_tree'] = sync_git.git(self.repo, 'rev-parse', self.base + '^{tree}')
        self.save()
        self.assert_refused()

    def test_published_head_moved_refused(self):
        sync_git.git(self.published, 'commit', '--allow-empty', '-m', 'uncertain publication')
        self.assert_refused()

    def test_changed_marker_refused(self):
        marker = self.common / 'agent-signal-integration-worktree.json'
        value = json.loads(marker.read_bytes())
        value['head'] = 'b' * 40
        coordinator._atomic(marker, value)
        self.assert_refused()

    def test_archive_collision_refused(self):
        archive, _, _ = coordinator._release_paths(self.common, self.attempt)
        archive.mkdir()
        (archive / 'foreign').write_text('preserve')
        result = self.release()
        self.assertEqual('review-required', result['result'])
        self.assertEqual('preserve', (archive / 'foreign').read_text())
        self.assertEqual(self.original, self.journal_path.read_bytes())

    def test_lock_contention_refused(self):
        with patch.object(sync_git, 'lock', side_effect=sync_git.SyncBlocked('another sync is running')):
            self.assert_refused()

    def test_interrupted_moves_resume_and_block_other_publication(self):
        for step in ('branch', 'worktree'):
            # Each invocation of this parameterized test needs its own fixture.
            if step == 'worktree':
                self.setUp()
            real_git = sync_git.git
            stopped = False
            def fail_after(repo, *args, **kwargs):
                nonlocal stopped
                result = real_git(repo, *args, **kwargs)
                if args[0] == step and not stopped:
                    stopped = True
                    raise sync_git.SyncBlocked('injected interruption after ' + step)
                return result
            with patch.object(sync_git, 'git', side_effect=fail_after):
                result = self.release()
            self.assertEqual('review-required', result['result'], result)
            with self.assertRaisesRegex(sync_git.SyncBlocked, 'release is pending'):
                sync_git.assert_integration_owner(self.repo)
            blocked = coordinator.ready_sync(self.repo, self.base, adopt=['kept'])
            self.assertIn('release is pending', blocked['reason'])
            result = self.release()
            self.assertEqual('released', result['result'], result)
            self.assertEqual(self.original, (Path(result['archive']) / 'attempt.json').read_bytes())

    def test_drift_after_interruption_is_retained_and_refused(self):
        real_git = sync_git.git
        def fail_after(repo, *args, **kwargs):
            result = real_git(repo, *args, **kwargs)
            if args[0] == 'branch':
                raise sync_git.SyncBlocked('injected interruption')
            return result
        with patch.object(sync_git, 'git', side_effect=fail_after):
            self.release()
        (self.lane / 'kept.txt').write_bytes(b'late edit')
        result = self.release()
        self.assertEqual('review-required', result['result'])
        self.assertEqual(b'late edit', (self.lane / 'kept.txt').read_bytes())
        self.assertEqual('releasing', json.loads(self.journal_path.read_bytes())['phase'])

    def test_interrupted_marker_move_resumes(self):
        real_rename = Path.rename
        def fail_after(path, target):
            result = real_rename(path, target)
            if path.name == 'agent-signal-integration-worktree.json':
                raise OSError('injected interruption after marker move')
            return result
        with patch.object(Path, 'rename', fail_after):
            result = self.release()
        self.assertEqual('review-required', result['result'])
        self.assertEqual('released', self.release()['result'])

    def test_interrupted_completion_write_resumes(self):
        real_atomic = coordinator._atomic
        def fail_after(path, value):
            real_atomic(path, value)
            if value.get('phase') == 'released':
                raise OSError('injected interruption after completion write')
        with patch.object(coordinator, '_atomic', fail_after):
            result = self.release()
        self.assertEqual('review-required', result['result'])
        with self.assertRaisesRegex(sync_git.SyncBlocked, 'release is pending'):
            sync_git.assert_integration_owner(self.repo)
        self.assertEqual('released', self.release()['result'])

    def test_tampered_retained_journal_refused(self):
        real_git = sync_git.git
        def fail_after(repo, *args, **kwargs):
            result = real_git(repo, *args, **kwargs)
            if args[0] == 'branch':
                raise sync_git.SyncBlocked('injected interruption')
            return result
        with patch.object(sync_git, 'git', side_effect=fail_after):
            self.release()
        archive, _, _ = coordinator._release_paths(self.common, self.attempt)
        with (archive / 'attempt.json').open('ab') as handle:
            handle.write(b' ')
        result = self.release()
        self.assertEqual('review-required', result['result'])
        self.assertIn('evidence identity changed', result['reason'])

    def test_legacy_or_deployment_started_attempt_refused(self):
        for value in ('absent', True, None, 0):
            if value == 'absent':
                self.journal.pop('deployment_started', None)
            else:
                self.journal['deployment_started'] = value
            self.save()
            self.assert_refused()

    def legacy_qualification(self):
        self.journal.pop('deployment_started', None)
        live = self.root / 'live'
        live.mkdir()
        (live / 'kept').mkdir()
        (live / 'kept' / 'SKILL.md').write_bytes(b'fixture installed owner')
        (live / coordinator.reconcile.fleet.STATE_FILE).write_bytes(b'{"fixture":"state"}')
        self.journal['origin_destinations'] = [str(live)]
        self.save()
        self.original = self.journal_path.read_bytes()
        evidence = {}
        for role in ('execution', 'supplement', 'state', 'remote', 'remote_checkpoint', 'checkpoint'):
            path = self.root / (role + '.json')
            path.write_bytes(json.dumps({'fixture_role': role}).encode())
            evidence[role] = {'file': path.name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
        proof = {'schema_version': 1, 'kind': 'reviewed-legacy-predeployment',
                 'journal_sha256': hashlib.sha256(self.original).hexdigest(),
                 'binding': {key: self.journal[key] for key in ('attempt', 'base', 'composed_tree')},
                 'evidence': evidence, 'original_sync_command_id': 'fixture-original',
                 'checkpoint_command_id': 'fixture-checkpoint',
                 'review': {'decision': 'qualified-predeployment', 'reason': 'Fixture reviewed history.',
                            'reviewer_ref': 'fixture-review', 'coverage_end': 'fixture-checkpoint',
                            'no_retry_since_checkpoint': 'Fixture controlled owner; no later sync.'},
                 'live': [{'root': str(live),
                           'managed_state_sha256': coordinator.reconcile.fleet.sha256_file(live / coordinator.reconcile.fleet.STATE_FILE),
                           'owners': {'kept': coordinator.reconcile.fleet.directory_record(live / 'kept')['sha256']}}]}
        proof['binding']['ready'] = self.journal['receipt']['ready']
        path = self.root / 'receipt.json'
        path.write_bytes((json.dumps(proof, indent=2) + '\n').encode())
        return path, proof, live

    def test_reviewed_legacy_release_retains_six_evidence_files_and_no_false_marker(self):
        path, proof, live = self.legacy_qualification()
        live_before = self.snapshot(live)
        result = coordinator.release_predeployment(self.repo, self.attempt, path)
        self.assertEqual('released', result['result'], result)
        archive = Path(result['archive'])
        self.assertEqual(self.original, (archive / 'attempt.json').read_bytes())
        self.assertNotIn('deployment_started', json.loads((archive / 'attempt.json').read_bytes()))
        self.assertNotIn('deployment_started', json.loads((archive / 'release.json').read_bytes()))
        self.assertEqual(path.read_bytes(), (archive / 'qualification' / 'receipt.json').read_bytes())
        for record in proof['evidence'].values():
            self.assertEqual((self.root / record['file']).read_bytes(), (archive / 'qualification' / record['file']).read_bytes())
        self.assertEqual(live_before, self.snapshot(live))
        self.assertEqual(self.before, self.snapshot(Path(result['retained_worktree'])))

    def test_qualification_cannot_override_any_explicit_marker(self):
        path, _, _ = self.legacy_qualification()
        for value in (True, None, 0, False):
            self.journal['deployment_started'] = value
            self.save()
            before = self.journal_path.read_bytes()
            result = coordinator.release_predeployment(self.repo, self.attempt, path)
            self.assertEqual('review-required', result['result'], result)
            self.assertEqual(before, self.journal_path.read_bytes())

    def test_qualification_binding_missing_role_review_and_evidence_drift_refused(self):
        path, proof, _ = self.legacy_qualification()
        original_proof = path.read_bytes()
        for field in ('journal_sha256', 'binding', 'review', 'evidence'):
            changed = json.loads(original_proof)
            changed.pop(field)
            path.write_bytes(json.dumps(changed).encode())
            result = coordinator.release_predeployment(self.repo, self.attempt, path)
            self.assertEqual('review-required', result['result'], result)
            self.assertEqual(self.original, self.journal_path.read_bytes())
        path.write_bytes(original_proof)
        (self.root / proof['evidence']['execution']['file']).write_bytes(b'changed after review')
        result = coordinator.release_predeployment(self.repo, self.attempt, path)
        self.assertEqual('review-required', result['result'], result)
        self.assertFalse((self.common / ('agent-signal-released-' + self.attempt)).exists())

    def test_qualification_live_scope_and_state_drift_refused(self):
        path, proof, live = self.legacy_qualification()
        for field in ('root', 'owners', 'managed_state_sha256'):
            changed = json.loads(path.read_bytes())
            changed['live'][0][field] = {} if field == 'owners' else 'changed'
            other = self.root / 'other-proof.json'
            other.write_bytes(json.dumps(changed).encode())
            result = coordinator.release_predeployment(self.repo, self.attempt, other)
            self.assertEqual('review-required', result['result'], result)
            self.assertEqual(self.original, self.journal_path.read_bytes())
        (live / 'kept' / 'SKILL.md').write_bytes(b'concurrent live edit')
        result = coordinator.release_predeployment(self.repo, self.attempt, path)
        self.assertEqual('review-required', result['result'], result)
        self.assertEqual(b'concurrent live edit', (live / 'kept' / 'SKILL.md').read_bytes())

    def test_qualified_retry_uses_retained_evidence_after_original_files_disappear(self):
        path, proof, _ = self.legacy_qualification()
        real_git = sync_git.git
        def fail_after(repo, *args, **kwargs):
            result = real_git(repo, *args, **kwargs)
            if args[0] == 'branch':
                raise sync_git.SyncBlocked('fixture interrupted after branch move')
            return result
        with patch.object(sync_git, 'git', side_effect=fail_after):
            result = coordinator.release_predeployment(self.repo, self.attempt, path)
        self.assertEqual('review-required', result['result'])
        self.assertEqual('releasing', json.loads(self.journal_path.read_bytes())['phase'])
        path.unlink()
        for record in proof['evidence'].values():
            (self.root / record['file']).unlink()
        result = self.release()
        self.assertEqual('released', result['result'], result)

    def test_qualification_retention_failure_leaves_active_journal_untouched_and_resumes(self):
        path, _, _ = self.legacy_qualification()
        retain = coordinator._retain_release_bytes
        def fail_during(target, data):
            if target.name == 'supplement.json':
                target.write_bytes(data[:4])
                raise OSError('fixture interrupted evidence copy')
            retain(target, data)
        with patch.object(coordinator, '_retain_release_bytes', side_effect=fail_during):
            result = coordinator.release_predeployment(self.repo, self.attempt, path)
        self.assertEqual('review-required', result['result'])
        self.assertEqual(self.original, self.journal_path.read_bytes())
        self.assertEqual('released', coordinator.release_predeployment(self.repo, self.attempt, path)['result'])

    def test_qualified_retry_refuses_tampered_retained_evidence(self):
        path, proof, _ = self.legacy_qualification()
        real_git = sync_git.git
        def fail_after(repo, *args, **kwargs):
            result = real_git(repo, *args, **kwargs)
            if args[0] == 'branch':
                raise sync_git.SyncBlocked('fixture interrupted after branch move')
            return result
        with patch.object(sync_git, 'git', side_effect=fail_after):
            coordinator.release_predeployment(self.repo, self.attempt, path)
        archive, _, _ = coordinator._release_paths(self.common, self.attempt)
        (archive / 'qualification' / proof['evidence']['execution']['file']).write_bytes(b'changed')
        result = self.release()
        self.assertEqual('review-required', result['result'], result)
        self.assertEqual('releasing', json.loads(self.journal_path.read_bytes())['phase'])

    def test_qualification_malformed_objects_and_redirected_names_refused(self):
        path, proof, _ = self.legacy_qualification()
        malformed = [[], dict(proof, review=[]), dict(proof, evidence=[]), dict(proof, live=[{'owners': []}])]
        for name in ('../outside.json', 'receipt.json'):
            value = json.loads(json.dumps(proof))
            value['evidence']['execution']['file'] = name
            malformed.append(value)
        for value in malformed:
            path.write_bytes(json.dumps(value).encode())
            result = coordinator.release_predeployment(self.repo, self.attempt, path)
            self.assertEqual('review-required', result['result'], result)
            self.assertEqual(self.original, self.journal_path.read_bytes())

    def test_qualified_retry_refuses_removed_proof_binding(self):
        path, _, _ = self.legacy_qualification()
        real_git = sync_git.git
        def fail_after(repo, *args, **kwargs):
            result = real_git(repo, *args, **kwargs)
            if args[0] == 'branch':
                raise sync_git.SyncBlocked('fixture interrupted after branch move')
            return result
        with patch.object(sync_git, 'git', side_effect=fail_after):
            coordinator.release_predeployment(self.repo, self.attempt, path)
        journal = json.loads(self.journal_path.read_bytes())
        del journal['release']['qualification_sha256']
        coordinator._atomic(self.journal_path, journal)
        for supplied in (None, path):
            result = coordinator.release_predeployment(self.repo, self.attempt, supplied)
            self.assertEqual('review-required', result['result'], result)
            self.assertIn('missing its release binding', result['reason'])
        archive, _, _ = coordinator._release_paths(self.common, self.attempt)
        retained = archive / 'qualification'
        detached = self.root / 'detached-fixture-evidence'
        self.assertTrue(retained.resolve().is_relative_to(self.root))
        self.assertTrue(detached.resolve().is_relative_to(self.root))
        retained.rename(detached)  # Preserve bytes while simulating lost archive.
        for supplied in (None, path):
            result = coordinator.release_predeployment(self.repo, self.attempt, supplied)
            self.assertEqual('review-required', result['result'], result)
            self.assertIn('missing its release binding', result['reason'])

    def test_empty_archive_and_partial_original_copy_resume(self):
        for partial in (b'', self.original[:65]):
            if partial:
                self.setUp()
            archive, _, _ = coordinator._release_paths(self.common, self.attempt)
            archive.mkdir()
            if partial:
                (archive / 'attempt.json').write_bytes(self.original[:65])
            result = self.release()
            self.assertEqual('released', result['result'], result)
            self.assertEqual(self.original, (archive / 'attempt.json').read_bytes())

    def test_started_marker_is_durable_and_monotonic(self):
        sync_git.mark_integration_deployment_started(self.lane, self.attempt)
        self.assertIs(True, json.loads(self.journal_path.read_bytes())['deployment_started'])
        original = self.journal_path.read_bytes()
        sync_git.mark_integration_deployment_started(self.lane, self.attempt)
        self.assertEqual(original, self.journal_path.read_bytes())
        self.assert_refused()

    def test_low_level_ready_sync_marks_before_later_work(self):
        core = coordinator.reconcile.sync.__wrapped__.__wrapped__
        with patch.object(coordinator.reconcile, '_selected_owners', return_value=['kept']), \
             patch.object(coordinator.reconcile, '_snapshot', return_value=self.lane / 'render'), \
             patch.object(coordinator.reconcile, '_destinations', return_value=[]), \
             patch.object(coordinator.reconcile, '_agent_scope_identities', return_value={}), \
             patch.object(coordinator.reconcile, '_skill_state', side_effect=RuntimeError('stop after mark')):
            with self.assertRaisesRegex(RuntimeError, 'stop after mark'):
                core(self.lane, adopt=['kept'], ready_input={'attempt': self.attempt,
                    'files': self.journal['composition_files'], 'agent_identities': {}})
        self.assertIs(True, json.loads(self.journal_path.read_bytes())['deployment_started'])
        self.assert_refused()

    def test_failed_marker_write_prevents_later_work(self):
        core = coordinator.reconcile.sync.__wrapped__.__wrapped__
        with patch.object(coordinator.reconcile, '_selected_owners', return_value=['kept']), \
             patch.object(coordinator.reconcile, '_snapshot', return_value=self.lane / 'render'), \
             patch.object(coordinator.reconcile, '_destinations', return_value=[]), \
             patch.object(coordinator.reconcile, '_agent_scope_identities', return_value={}), \
             patch.object(sync_git.os, 'replace', side_effect=OSError('injected marker persistence failure')), \
             patch.object(coordinator.reconcile, '_skill_state') as later_work:
            with self.assertRaisesRegex(OSError, 'persistence failure'):
                core(self.lane, adopt=['kept'], ready_input={'attempt': self.attempt,
                    'files': self.journal['composition_files'], 'agent_identities': {}})
            later_work.assert_not_called()
        self.assertIs(False, json.loads(self.journal_path.read_bytes())['deployment_started'])

    def test_outer_result_write_preserves_started_marker(self):
        self.journal['receipt']['options'] = coordinator._options(['kept'], [], 'local-windows', None, None,
            'chore: integrate checked ready change')
        self.journal['receipt']['paths'] = ['kept.txt']
        self.save()
        def started_then_rejected(lane, **kwargs):
            sync_git.mark_integration_deployment_started(lane, self.attempt)
            return {'result': 'review-required', 'owners': ['kept'],
                    'reason': 'selected owner missing, unadmitted, or conflicting'}
        with patch.object(coordinator, '_verify_composition'), \
             patch.object(coordinator.reconcile, '_destinations', return_value=[]), \
             patch.object(coordinator.reconcile, '_snapshot', return_value=self.lane / 'render'), \
             patch.object(coordinator.reconcile, '_skill_state', return_value={'mode': 'deploy-canonical'}), \
             patch.object(coordinator.reconcile, 'complete_sync', side_effect=started_then_rejected):
            result = coordinator.ready_sync(self.repo, self.base, adopt=['kept'])
        self.assertEqual('review-required', result['result'], result)
        self.assertIs(True, json.loads(self.journal_path.read_bytes())['deployment_started'])
        self.assert_refused()

    def test_interruption_inside_git_move_keeps_publication_blocked(self):
        real_git = sync_git.git
        def interrupted_git(repo, *args, **kwargs):
            if args[:2] == ('worktree', 'move'):
                old, new = Path(args[2]), Path(args[3])
                self.assertTrue(old.resolve().is_relative_to(self.common))
                self.assertTrue(new.resolve().is_relative_to(self.common))
                old.rename(new)  # Simulate Git stopping before its backlink update.
                raise sync_git.SyncBlocked('injected interruption inside Git move')
            return real_git(repo, *args, **kwargs)
        with patch.object(sync_git, 'git', side_effect=interrupted_git):
            result = self.release()
        self.assertEqual('review-required', result['result'])
        result = self.release()
        self.assertEqual('review-required', result['result'])
        self.assertIn('registration backlink differs', result['reason'])
        self.assertEqual('releasing', json.loads(self.journal_path.read_bytes())['phase'])
        with self.assertRaisesRegex(sync_git.SyncBlocked, 'release is pending'):
            sync_git.assert_integration_owner(self.repo)
        archive, retained, _ = coordinator._release_paths(self.common, self.attempt)
        self.assertEqual(self.before, self.snapshot(retained))
        self.assertEqual(self.original, (archive / 'attempt.json').read_bytes())
        # Only this proven-owned fixture's native registration is repaired.
        # Release itself refuses uncertainty and never performs that repair.
        real_git(self.repo, 'worktree', 'repair', str(retained))
        self.assertEqual('released', self.release()['result'])


if __name__ == '__main__':
    unittest.main()
