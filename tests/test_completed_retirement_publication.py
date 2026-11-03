"""Pure completion/mapping controls; synthetic seams grant no authority.

Record reads and Git objects are explicit unit seams. The release owner also
checks real retained evidence separately, without repeating local retirement.
"""
import copy
import hashlib
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import instruction_changes as ic
import reconcile
import worktree_sync as ws
import sync_git

sha = lambda b: hashlib.sha256(b).hexdigest()
encode = lambda value: json.dumps(value, sort_keys=True).encode()
ORIGINAL_PATHS = {
    'contracts/ownership.json', 'contracts/surface-matrix.json', 'docs/recovery.md',
    'docs/requirement-status.md', 'docs/system-requirements.md',
    'evals/results/outcome-design-retirement-local-20261103.json', 'host-deltas.json',
    'profiles/current-observed-defaults.json', 'recovery/current/hosts/codex/AGENTS.md',
    'recovery/current/hosts/hermes/SOUL.md', 'recovery/current/hosts/omp/AGENTS.md',
    'recovery/current/manifest.json', 'registry.json', 'surfaces/core.md',
    'skills/answer-key-gauntlet/SKILL.md', 'skills/cross-agent-surface-engineering/SKILL.md',
    'skills/instruction-authoring/SKILL.md', 'skills/openai-delegation-route-research/SKILL.md',
    'skills/project-prior-art/SKILL.md', 'tools/instruction_changes.py', 'tools/reconcile.py', 'tools/recovery.py'}


class CompletedRetirementPublication(unittest.TestCase):
    def setUp(self):
        self.owner = 'outcome-first-workflow-design'
        self.survivors = {'answer-key-gauntlet', 'cross-agent-surface-engineering', 'instruction-authoring',
                          'openai-delegation-route-research', 'project-prior-art'}
        self.base, self.original, self.old = ic._RETIREMENT_PROPAGATION_BASE, ic._RETIREMENT_ORIGINAL_SOURCE, ic._RETIREMENT_ORIGINAL_BASE
        self.ready = '4' * 40
        self.files = ORIGINAL_PATHS | ic._RETIREMENT_PUBLICATION_ADDITIONS
        self.blobs = {(rev, name): (rev + name).encode() for rev in (self.old, self.original, self.base, self.ready) for name in self.files}
        instructions = {'surfaces/core.md', *('skills/' + n + '/SKILL.md' for n in self.survivors)}
        for name in instructions | {'contracts/surface-matrix.json'}:
            self.blobs[self.base, name] = self.blobs[self.old, name]
            self.blobs[self.ready, name] = self.blobs[self.original, name]
        for name, key, identity in [('registry.json', 'skills', 'name'), ('contracts/ownership.json', 'capabilities', 'id')]:
            for rev in (self.old, self.original, self.base, self.ready):
                self.blobs[rev, name] = encode({key: [{identity: self.owner, 'status': 'retired' if rev in (self.original, self.ready) else 'admitted'},
                    {identity: 'leanrea', 'status': 'withheld' if rev in (self.base, self.ready) else 'admitted'}]})
        self.records = {}
        def ref(name, value):
            pointer = {'path': str((ROOT / 'synthetic-private' / name).resolve()), 'sha256': sha(encode(value))}
            self.records[pointer['path']] = value
            return pointer
        self.ref = ref
        decision, coverage = ref('decision', {'decision': 'retire'}), ref('coverage', {'covered': True})
        authority = ref('authority', {'kind': 'user-directed-skill-retirement', 'owner': self.owner,
                    'decision': 'retire', 'source_commit': self.original})
        references = ref('references', {'complete': True, 'owner': self.owner, 'source_commit': self.original,
                                     'retirement_authority': authority})
        actions = {name: {'action': 'remove' if name == self.owner else 'update'} for name in self.survivors | {self.owner}}
        request = {'kind': 'reviewed-skill-retirement-v1', 'machine': 'local-windows', 'owner': self.owner,
                   'source_commit': self.original, 'git_recovery': {'commit': self.old},
                   'source_files': {n: sha(self.blobs[self.original, n]) for n in ORIGINAL_PATHS},
                   'expected_actions': actions, 'evidence': {'decision': decision, 'coverage': coverage, 'references': references}}
        scope = reconcile._retirement_review_scope(request)
        review = ref('review', {'schema_version': 1, 'kind': 'reviewed-retirement-operation', 'verdict': 'PASS',
                               'scope_sha256': scope, 'decision': decision, 'coverage': coverage})
        request['evidence']['operation_review'] = review
        request_ref = ref('request', request)
        self.common = ROOT / 'synthetic-common'
        applied = {'result': 'retired-local', 'owner': self.owner, 'source_commit': self.original,
                   'request_sha256': request_ref['sha256'], 'actions': actions,
                   'admission': [{'path': n, 'owner': n.rsplit('/', 1)[0]} for n in instructions]}
        applied_ref = ref('applied', applied)
        retained = {'path': str((self.common / 'agent-signal-retirements' / (request_ref['sha256'] + '.json')).resolve()),
                    'sha256': sha(encode(applied))}
        self.records[retained['path']] = copy.deepcopy(applied)
        native = ref('native', {'status': 'verified', 'scope_sha256': scope, 'source_commit': self.original,
              'native_catalogues_verified': True, 'retired_directory_absent': True,
              'retired_state_entry_absent': True, 'installed_snapshot_clean': True})
        readbacks = {}
        for host in ('codex', 'hermes', 'omp'):
            readbacks[host] = ref(host, {'host': host, 'verified': True, 'loading_verified': True,
                                      'retired_offered': [], 'required_present': sorted(self.survivors)})
        self.completed = {'status': 'local retirement verified', 'owner': self.owner, 'source_commit': self.original,
            'remaining_local_retirement_gate': None, 'uncertain_operations': False,
            'shared_package_directory_absent': True, 'managed_state_entry_absent': True, 'installed_snapshot_verified': True,
            'execution_request': request_ref, 'scope_sha256': scope, 'review': review, 'apply_return': applied_ref,
            'retained_operation_receipt': retained, 'native_finish': native, 'native_readbacks': readbacks}
        completion = ref('completion', self.completed); completion['sha256'] = ic._COMPLETED_RETIREMENT_SHA256
        self.proof = {'schema_version': 1, 'kind': 'completed-retirement-publication', 'completion': completion,
                      'base_commit': self.base, 'ready_commit': self.ready,
                      'files': {n: {'before_sha256': sha(self.blobs[self.base, n]), 'after_sha256': sha(self.blobs[self.ready, n])} for n in self.files}}
        self.patches = [patch.object(ic, '_completed_retirement_record', side_effect=lambda r: self.records[r['path']]),
                        patch.object(ic, '_before', side_effect=lambda source, rev, name: self.blobs[rev, name]),
                        patch.object(sync_git, 'common_dir', return_value=self.common),
                        patch.object(sync_git, 'git', side_effect=self.git)]
        for seam in self.patches: seam.start(); self.addCleanup(seam.stop)

    def git(self, source, *args):
        if args[0] == 'merge-base': return ''
        if args[:2] == ('diff', '--name-only'):
            return '\n'.join(sorted(ORIGINAL_PATHS if args[2:] == (self.old, self.original) else self.files))
        raise AssertionError(args)

    def validate(self):
        return ic.completed_retirement_publication(None, ROOT, self.base, self.files, self.proof, ready=self.ready)

    def test_valid_completed_mapping_preserves_model_selection(self):
        self.assertEqual(self.validate()['owner'], self.owner)
        self.assertFalse(self.validate()['publication_authorized'])

    def test_incomplete_or_foreign_completion_rejected(self):
        self.completed['status'] = 'applying'
        with self.assertRaises(sync_git.SyncBlocked): self.validate()

    def test_wrong_operation_review_rejected(self):
        self.records[self.completed['review']['path']]['verdict'] = 'FAIL'
        with self.assertRaises(sync_git.SyncBlocked): self.validate()

    def test_missing_native_verification_rejected(self):
        self.records[self.completed['native_readbacks']['omp']['path']]['verified'] = False
        with self.assertRaises(sync_git.SyncBlocked): self.validate()

    def test_unrelated_public_path_rejected(self):
        self.proof['files']['unrelated.txt'] = {'before_sha256': None, 'after_sha256': '0' * 64}
        with self.assertRaises(sync_git.SyncBlocked): self.validate()

    def test_self_consistent_changed_instruction_rejected(self):
        name = 'surfaces/core.md'; self.blobs[self.ready, name] = b'new unrelated guidance'
        self.proof['files'][name]['after_sha256'] = sha(self.blobs[self.ready, name])
        with self.assertRaises(sync_git.SyncBlocked): self.validate()

    def test_another_lifecycle_selection_rejected(self):
        name = 'registry.json'; value = json.loads(self.blobs[self.ready, name]); value['skills'][1]['status'] = 'admitted'
        self.blobs[self.ready, name] = encode(value); self.proof['files'][name]['after_sha256'] = sha(self.blobs[self.ready, name])
        with self.assertRaises(sync_git.SyncBlocked): self.validate()

    def test_foreign_retained_store_rejected(self):
        self.completed['retained_operation_receipt']['path'] = str(ROOT / 'foreign-store.json')
        with self.assertRaises(sync_git.SyncBlocked): self.validate()

    def test_stale_base_or_ready_rejected(self):
        self.proof['base_commit'] = self.old
        with self.assertRaises(sync_git.SyncBlocked): self.validate()

    def test_completion_window_requires_unchanged_private_proof(self):
        journal = {'receipt': {'options': {'retirement_publication': self.proof}},
                   'retirement_publication_required': True,
                   'retirement_publication_sha256': ws._canonical_hash(self.proof)}
        with patch.object(ic, 'completed_retirement_publication') as verified:
            ws._verify_retirement_publication(ROOT, journal); verified.assert_called_once()
            del journal['receipt']['options']['retirement_publication']
            with self.assertRaises(sync_git.SyncBlocked): ws._verify_retirement_publication(ROOT, journal)

    def test_legacy_completion_has_no_new_evidence_requirement(self):
        with patch.object(ic, 'completed_retirement_publication') as verified:
            ws._verify_retirement_publication(ROOT, {})
            verified.assert_not_called()


class EvidenceRecordReader(unittest.TestCase):
    def test_existing_json_body_requires_its_actual_digest(self):
        path = ROOT / 'registry.json'
        value = ic._completed_retirement_record({'path': str(path), 'sha256': sha(path.read_bytes())})
        self.assertIsInstance(value, dict)

    def test_changed_digest_rejects_existing_body(self):
        with self.assertRaises(sync_git.SyncBlocked):
            ic._completed_retirement_record({'path': str(ROOT / 'registry.json'), 'sha256': '0' * 64})

    def test_missing_body_does_not_become_completion(self):
        with self.assertRaises(sync_git.SyncBlocked):
            ic._completed_retirement_record({'path': str(ROOT / 'absent-retirement-proof.json'), 'sha256': '0' * 64})


class SourceOnlyAdmissionBoundaries(unittest.TestCase):
    def test_completed_retirement_cannot_preview_another_continuation(self):
        with patch.object(ws, '_qualify') as qualify, patch.object(ws, '_ready_check_failure', return_value={}):
            result = ws.ready_plan(ROOT, 'unused', retirement_publication={}, continue_published={})
            self.assertEqual(result['result'], 'review-required')
            self.assertIn('cannot continue another', result['reason'])
            qualify.assert_not_called()

    def test_source_range_retains_requirement_if_new_markers_are_lost(self):
        journal = {'receipt': {'paths': ['registry.json'], 'source_base': 'a' * 40, 'ready': 'b' * 40, 'options': {}}}
        def source(repo, *args):
            status = 'admitted' if args[-1].startswith('a' * 40) else 'retired'
            return json.dumps({'skills': [{'name': 'outcome-first-workflow-design', 'status': status}]})
        with patch.object(sync_git, 'git', side_effect=source):
            with self.assertRaises(sync_git.SyncBlocked): ws._verify_retirement_publication(ROOT, journal)

    def test_later_registry_change_does_not_reopen_completed_retirement(self):
        journal = {'receipt': {'paths': ['registry.json'], 'source_base': 'a' * 40, 'ready': 'b' * 40, 'options': {}}}
        value = json.dumps({'skills': [{'name': 'outcome-first-workflow-design', 'status': 'retired'}]})
        with patch.object(sync_git, 'git', return_value=value):
            ws._verify_retirement_publication(ROOT, journal)

    def test_invalid_source_reference_never_reaches_git(self):
        journal = {'receipt': {'paths': ['registry.json'], 'source_base': '--output=forbidden-output', 'ready': 'b' * 40}}
        with patch.object(sync_git, 'git') as read:
            with self.assertRaises(sync_git.SyncBlocked): ws._verify_retirement_publication(ROOT, journal)
            read.assert_not_called()


class CompletedPublicationCli(unittest.TestCase):
    def invoke(self, action, roots):
        import contextlib
        import io
        import reconcile
        argv = [action, '--repo', str(ROOT), '--ready', 'b' * 40,
                '--include', 'registry.json', '--retirement-request', 'private-proof.json']
        if action == 'sync': argv.append('--source-only')
        if roots: argv.extend(['--root', 'omp=' + str(ROOT)])
        operation = 'ready_plan' if action == 'plan' else 'ready_sync'
        defaults = {'omp': ROOT}
        with patch.object(reconcile.recovery, '_parse_roots', return_value=defaults), \
             patch.object(Path, 'read_bytes', return_value=b'{}'), \
             patch.object(ws, operation, return_value={'result': 'synced'}) as dispatch, \
             contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(reconcile.main(argv), 0)
        return dispatch.call_args.kwargs

    def test_plan_does_not_select_default_native_roots(self):
        self.assertEqual(self.invoke('plan', False)['recovery_roots'], {})

    def test_source_only_sync_does_not_select_default_native_roots(self):
        self.assertEqual(self.invoke('sync', False)['recovery_roots'], {})

    def test_explicit_native_root_is_retained_for_existing_rejection(self):
        self.assertEqual(self.invoke('plan', True)['recovery_roots'], {'omp': ROOT})


if __name__ == '__main__': unittest.main()
