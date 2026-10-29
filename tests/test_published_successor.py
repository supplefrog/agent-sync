"""File-free controls for the bounded published-partial continuation mechanism."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import unittest
import os
import uuid
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
import worktree_sync as sync


class PublishedSuccessor(unittest.TestCase):
    def setUp(self):
        options = {'machine': 'local-windows', 'skill_roots': None, 'recovery_roots': {},
                   'include': ['tools/example.py'], 'adopt': [], 'message': 'selected successor'}
        target = {'remote': 'origin', 'ref': 'refs/heads/main', 'branch': 'main'}
        self.old = {'phase': 'published', 'deployment_started': True, 'attempt': 'a'*32,
                    'integration_repo': 'synthetic-lane',
                    'receipt': {'options': copy.deepcopy(options), 'target': copy.deepcopy(target)},
                    'last_result': {'result': 'published', 'remote_verified': True, 'commit': 'b'*40},
                    'rollout': {'targets': {'root-a': {'phase': 'blocked', 'verified': False,
                                                     'reason': 'intentional local owner'},
                                            'root-b': {'phase': 'verified', 'verified': True}}}}
        self.receipt = {'ready': 'c'*40, 'options': options, 'target': target}
        self.states = {'root-a': 'd'*64, 'root-b': 'e'*64}
        self.request = {'schema_version': 1, 'attempt': 'a'*32, 'journal_sha256': 'f'*64,
                        'published_commit': 'b'*40, 'successor_ready': 'c'*40,
                        'successor_options_sha256': sync._canonical_hash(options),
                        'target_states': copy.deepcopy(self.states)}

    def call(self):
        return sync._successor_binding(self.old, 'f'*64, self.request, self.receipt, self.states)

    def rejected(self):
        with self.assertRaises(sync.sync_git.SyncBlocked): self.call()

    def test_exact_partial_carries_all_targets_without_relabeling(self):
        original = copy.deepcopy(self.old)
        binding = self.call()
        self.assertEqual(binding['targets'], self.old['rollout']['targets'])
        self.assertFalse(binding['sync_complete'])
        self.assertEqual(self.old, original)

    def test_wrong_journal_rejected(self):
        self.request['journal_sha256'] = '0'*64; self.rejected()

    def test_different_successor_rejected(self):
        self.request['successor_ready'] = '0'*40; self.rejected()

    def test_options_substitution_rejected(self):
        self.receipt['options']['adopt'] = ['instruction-authoring']; self.rejected()

    def test_destination_substitution_rejected(self):
        self.receipt['target']['remote'] = 'another'; self.rejected()

    def test_target_scope_change_rejected(self):
        self.receipt['options']['skill_roots'] = ['other-root']
        self.request['successor_options_sha256'] = sync._canonical_hash(self.receipt['options'])
        self.rejected()

    def test_removed_old_target_rejected(self):
        del self.request['target_states']['root-b']; self.rejected()

    def test_actual_target_drift_rejected(self):
        self.states['root-a'] = '0'*64; self.rejected()

    def test_uncertain_applying_target_rejected(self):
        self.old['rollout']['targets']['root-a']['phase'] = 'applying'; self.rejected()

    def test_unpublished_attempt_rejected(self):
        self.old['phase'] = 'reconciling'; self.rejected()

    def test_complete_old_attempt_not_reclassified(self):
        self.old['rollout']['targets']['root-a']['verified'] = True; self.rejected()

    def test_unknown_authority_fields_not_accepted(self):
        self.request['waive_review'] = True; self.rejected()

    def test_carried_target_absence_or_failure_stays_incomplete(self):
        journal = {'predecessors': [self.call()]}
        self.assertEqual(sync._carried_target_holds(journal, {'root-a': {'verified': True}}), ['root-b'])
        self.assertEqual(sync._carried_target_holds(journal, {'root-a': {'verified': False},
                                                             'root-b': {'verified': True}}), ['root-a'])
        self.assertEqual(sync._carried_target_holds(journal, {'root-a': {'verified': True},
                                                             'root-b': {'verified': True}}), [])

    def test_source_only_rejected_before_qualification_or_mutation(self):
        with patch.object(sync, '_qualify') as qualify, patch.object(sync, '_begin_published_successor') as begin:
            result = sync.ready_sync('.', 'c'*40, source_only=True, continue_published=self.request)
        self.assertEqual(result['result'], 'incomplete')
        qualify.assert_not_called(); begin.assert_not_called()

    def test_repeated_binding_is_idempotent_and_does_not_mutate_inputs(self):
        snapshot = json.dumps([self.old, self.request, self.receipt, self.states], sort_keys=True)
        self.assertEqual(self.call(), self.call())
        self.assertEqual(snapshot, json.dumps([self.old, self.request, self.receipt, self.states], sort_keys=True))

    def test_new_successor_uses_normal_qualification(self):
        with patch.object(sync, '_qualify', return_value=self.receipt) as qualify:
            result = sync._ready_receipt(None, self.receipt['ready'], self.receipt['options'], self.old, self.request)
        self.assertEqual(result, self.receipt)
        qualify.assert_called_once()

    def test_published_successor_retry_reuses_exact_bound_qualification(self):
        current = {'phase': 'published', 'continuation_request_sha256': sync._canonical_hash(self.request),
                   'receipt': self.receipt}
        with patch.object(sync, '_qualify') as qualify:
            result = sync._ready_receipt(None, self.receipt['ready'], self.receipt['options'], current, self.request)
        self.assertEqual(result, self.receipt)
        qualify.assert_not_called()

    def test_retry_cannot_expand_selection(self):
        current = {'continuation_request_sha256': sync._canonical_hash(self.request), 'receipt': self.receipt}
        options = copy.deepcopy(self.receipt['options']); options['adopt'] = ['another-owner']
        with self.assertRaises(sync.sync_git.SyncBlocked):
            sync._ready_receipt(None, self.receipt['ready'], options, current, self.request)

    def test_retained_archive_substitution_rejected(self):
        common = Path('virtual-common')
        raw = json.dumps(self.old).encode()
        row = self.call()
        row['journal_sha256'] = hashlib.sha256(raw).hexdigest()
        row['archive'] = str(common/('agent-signal-integration-predecessor-' + row['attempt']))
        row['native_obligations'] = []
        journal = {'predecessors': [row]}
        with patch.object(Path, 'read_bytes', return_value=raw), patch.object(Path, 'is_symlink', return_value=False), \
                patch.object(sync, '_publication_native_obligations', return_value=[]):
            sync._validate_predecessors(common, journal)
        changed = copy.deepcopy(self.old)
        changed['rollout']['targets'].pop('root-a')
        with patch.object(Path, 'read_bytes', return_value=json.dumps(changed).encode()), patch.object(Path, 'is_symlink', return_value=False):
            with self.assertRaises(sync.sync_git.SyncBlocked):
                sync._validate_predecessors(common, journal)

    def test_ready_plan_checks_continuation_without_starting_it(self):
        with patch.object(sync, '_qualify', return_value=self.receipt), \
                patch.object(sync, '_published_successor_preflight', return_value=(self.old, b'old', self.call(), None, None)) as preflight, \
                patch.object(sync, '_begin_published_successor') as begin:
            result = sync.ready_plan('.', 'c'*40, continue_published=self.request)
        self.assertEqual(result['result'], 'ready')
        preflight.assert_called_once(); begin.assert_not_called()


class ReleaseGate(unittest.TestCase):
    def interrupted(self):
        return {'schema_version': 1, 'phase': 'reconciling', 'deployment_started': False,
                'last_result': None, 'receipt': {'target': {}, 'options': {'adopt': [], 'include': ['tools/example.py']}},
                'origin_destinations': [], 'composition_files': {'tools/example.py': 'd'*64},
                'composed_tree': 'a'*40}

    def classified(self):
        receipt = {'ready': 'a'*40, 'source_base': 'b'*40, 'source_commits': ['a'*40],
                   'target': {}, 'options': {'adopt': ['example'], 'include': []}}
        result = {'result': 'review-required', 'reason': 'selected owner missing, unadmitted, or conflicting',
                  'owners': ['example'], 'ready': receipt['ready'], 'base': receipt['source_base'],
                  'source_base': receipt['source_base'], 'source_commits': receipt['source_commits'],
                  'integration_repo': 'lane', 'published_repo': 'published'}
        return {'schema_version': 1, 'phase': 'reconciling', 'deployment_started': False,
                'last_result': result, 'receipt': receipt, 'base': receipt['source_base'],
                'integration_repo': 'lane', 'published_repo': 'published'}

    def invoke(self, original):
        return sync._release_preflight(None, None, original, None, None, None)

    def test_inherited_interruption_cannot_release(self):
        original = self.interrupted(); original['predecessors'] = [{'targets': {'root': {'verified': False}}}]
        with patch.object(sync.sync_git, 'destination') as destination:
            with self.assertRaisesRegex(sync.sync_git.SyncBlocked, 'inherited published obligations'):
                self.invoke(original)
        destination.assert_not_called()

    def test_inherited_owner_rejection_cannot_release(self):
        original = self.classified(); original['predecessors'] = [{'targets': {'root': {'verified': False}}}]
        with patch.object(sync.sync_git, 'destination') as destination:
            with self.assertRaisesRegex(sync.sync_git.SyncBlocked, 'inherited published obligations'):
                self.invoke(original)
        destination.assert_not_called()

    def test_genuine_interruption_keeps_existing_admission(self):
        original = self.interrupted()
        self.assertEqual(sync._release_source_kind(original), 'interrupted-include-only')
        # Stop at the first Git-dependent check: this verifies only admission,
        # never a real release or filesystem qualification.
        with patch.object(sync.sync_git, 'destination', side_effect=LookupError('existing Git checks reached')):
            with self.assertRaisesRegex(LookupError, 'existing Git checks reached'):
                self.invoke(original)

    def test_genuine_owner_rejection_keeps_existing_admission(self):
        original = self.classified()
        self.assertEqual(sync._release_source_kind(original), 'owner-classification')
        with patch.object(sync.sync_git, 'destination', side_effect=LookupError('existing Git checks reached')):
            with self.assertRaisesRegex(LookupError, 'existing Git checks reached'):
                self.invoke(original)


class NativeObligations(unittest.TestCase):
    def setUp(self):
        self.old = 'b'*40; self.current = 'c'*40
        self.name = 'recovery/current/hosts/hermes/config.json'
        self.artifact = {'id': 'settings', 'source': 'config.json', 'snapshot': 'hosts/hermes/config.json',
                         'kind': 'config', 'format': 'json'}
        self.policy = {'hosts': {'hermes': {'artifacts': [self.artifact]}}}
        self.blobs = {(self.old, 'recovery.json'): json.dumps(self.policy).encode(),
                      (self.current, 'recovery.json'): json.dumps(self.policy).encode(),
                      (self.old+'^', self.name): b'{"setting":1}',
                      (self.old, self.name): b'{"setting":2}',
                      (self.current+'^', self.name): b'{"setting":2}',
                      (self.current, self.name): b'{"setting":2}'}
        self.changed = {self.old: [self.name], self.current: []}
        self.saved = {'setting': 1, 'personal': 'preserved'}
        self.reads = 0
        def read(*args):
            self.reads += 1
            return self.saved
        self.recovery = SimpleNamespace(
            _load_policy=lambda path: self.policy, verify_snapshot=lambda *args: None,
            _policy_artifacts=lambda policy: [('hermes', self.artifact)],
            _selected_roots=lambda roots, hosts: (None, {'hermes': Path('synthetic-home')}),
            _safe_join=lambda *args, **kwargs: Path('synthetic-target'),
            _file_identity=lambda path: ('stable',), _target_home=lambda *args: Path('synthetic-home'),
            _expand=lambda value, *args, **kwargs: value, _read_config=read)

    def names(self, lane, *args):
        assert args[:2] == ('diff', '--name-only')
        return self.changed[args[-1]]

    def git(self, lane, *args):
        assert args[:2] == ('ls-tree', '--name-only')
        return self.name

    def fresh(self, native_phase_reached=False, missing_binding=False):
        with patch.object(sync, '_names', side_effect=self.names), \
                patch.object(sync, '_committed_bytes', side_effect=lambda lane, commit, name: self.blobs[(commit, name)]), \
                patch.object(sync.sync_git, 'git', side_effect=self.git):
            obligations = sync._publication_native_obligations(Path('synthetic-lane'), self.old)
            predecessor = {'published_commit': self.old}
            if not missing_binding: predecessor['native_obligations'] = obligations
            if native_phase_reached:
                predecessor['native_destinations'] = {'saved_verified': False, 'targets': {self.name: {'verified': False}}}
            journal = {'last_result': {'commit': self.current}, 'predecessors': [predecessor],
                       'receipt': {'options': {'recovery_roots': {}}, 'paths': self.changed[self.current]},
                       'published_repo': 'synthetic-published'}
            return sync._native_destination_completion(Path('synthetic-lane'), journal, recovery_module=self.recovery)

    def test_tool_only_successor_preserves_stale_obligation_when_native_never_reached(self):
        result = self.fresh()
        self.assertFalse(result['saved_verified']); self.assertEqual(self.reads, 1)
        self.assertIn(self.name, result['targets'])

    def test_tool_only_successor_preserves_stale_obligation_when_native_already_failed(self):
        self.assertFalse(self.fresh(native_phase_reached=True)['saved_verified'])
        self.assertEqual(self.reads, 1)

    def test_fresh_readback_discharges_inherited_value_without_loading_claim(self):
        self.saved['setting'] = 2
        result = self.fresh()
        self.assertTrue(result['saved_verified']); self.assertIsNone(result['loaded_verified'])
        self.assertEqual(self.saved['personal'], 'preserved')

    def test_missing_source_binding_stays_incomplete(self):
        result = self.fresh(missing_binding=True)
        self.assertFalse(result['saved_verified']); self.assertEqual(self.reads, 0)

    def test_selected_successor_can_change_desired_value(self):
        self.changed[self.current] = [self.name]
        self.blobs[(self.current, self.name)] = b'{"setting":3}'
        self.saved['setting'] = 3
        self.assertTrue(self.fresh()['saved_verified'])

    def test_unselected_desired_value_change_stays_incomplete(self):
        self.blobs[(self.current, self.name)] = b'{"setting":3}'
        self.saved['setting'] = 3
        self.assertFalse(self.fresh()['saved_verified'])

    def test_selected_revert_still_checks_the_previously_changed_key(self):
        self.changed[self.current] = [self.name]
        self.blobs[(self.current, self.name)] = b'{"setting":1}'
        self.saved['setting'] = 3
        self.assertFalse(self.fresh()['saved_verified'])
        self.saved['setting'] = 1
        self.assertTrue(self.fresh()['saved_verified'])


class SourceConflictSuccessor(unittest.TestCase):
    def setUp(self):
        options={'machine':'local-windows','skill_roots':None,'recovery_roots':{},
                 'include':['old.py'],'adopt':[],'message':'old reviewed source'}
        target={'remote':'origin','branch':'main','ref':'refs/heads/main'}
        self.targets={'root-a':{'phase':'blocked','verified':False},'root-b':{'phase':'verified','verified':True}}
        self.predecessor={'attempt':'1'*32,'journal_sha256':'a'*64,'published_commit':'1'*40,
            'targets':copy.deepcopy(self.targets),'sync_complete':False,'target_states':{'root-a':'a','root-b':'b'},
            'native_obligations':[],'source_backups':'preserve-backup','archive':'fixture-archive'}
        self.old={'schema_version':1,'attempt':'2'*32,'phase':'source-conflict','deployment_started':False,
            'base':'1'*40,'reason':'retained local composition failure','conflicts':[],
            'receipt':{'ready':'2'*40,'target':target,'options':options},
            'predecessors':[copy.deepcopy(self.predecessor)],'published_repo':'fixture-published',
            'integration_repo':'fixture-integration','continuation_request_sha256':'e'*64}
        self.receipt={'ready':'3'*40,'target':copy.deepcopy(target),'options':{**copy.deepcopy(options),
            'include':['old.py','repair.py'],'message':'new reviewed source'}}
        self.states={'root-a':'4'*64,'root-b':'5'*64};self.digest='6'*64
        self.request={'schema_version':1,'attempt':self.old['attempt'],'journal_sha256':self.digest,
            'published_commit':self.old['base'],'successor_ready':self.receipt['ready'],
            'successor_options_sha256':sync._canonical_hash(self.receipt['options']),'target_states':copy.deepcopy(self.states)}

    def bind(self):return sync._successor_binding(self.old,self.digest,self.request,self.receipt,self.states)

    def test_exact_failure_binding_preserves_all_inputs_and_targets(self):
        before=copy.deepcopy(self.old);bound=self.bind()
        self.assertEqual(self.old,before);self.assertTrue(bound['source_failure'])
        self.assertEqual(bound['targets'],self.targets);self.assertFalse(bound['sync_complete'])
        self.assertEqual(bound['failed_ready'],self.old['receipt']['ready'])

    def test_stale_or_mismatched_request_fields_reject(self):
        for key,value in [('attempt','9'*32),('journal_sha256','9'*64),('published_commit','9'*40),
                          ('successor_ready','9'*40),('successor_options_sha256','9'*64),('target_states',{'root-a':'x'})]:
            with self.subTest(field=key):
                original=copy.deepcopy(self.request);self.request[key]=value
                with self.assertRaises(sync.sync_git.SyncBlocked):self.bind()
                self.request=original

    def test_same_failed_ready_is_not_new_successor(self):
        self.receipt['ready']=self.old['receipt']['ready'];self.request['successor_ready']=self.receipt['ready']
        with self.assertRaises(sync.sync_git.SyncBlocked):self.bind()

    def test_changed_target_content_rejects(self):
        self.states['root-a']='9'*64
        with self.assertRaises(sync.sync_git.SyncBlocked):self.bind()

    def test_destination_or_scope_redirection_rejects(self):
        for field,value in [('machine','other'),('skill_roots',['elsewhere']),('recovery_roots',{'other':'elsewhere'}),
                            ('adopt',['unselected']),('include',['repair.py'])]:
            with self.subTest(field=field):
                original=copy.deepcopy(self.receipt['options']);self.receipt['options'][field]=value
                self.request['successor_options_sha256']=sync._canonical_hash(self.receipt['options'])
                with self.assertRaises(sync.sync_git.SyncBlocked):self.bind()
                self.receipt['options']=original
        self.request['successor_options_sha256']=sync._canonical_hash(self.receipt['options'])
        self.receipt['target']['remote']='other'
        with self.assertRaises(sync.sync_git.SyncBlocked):self.bind()

    def test_unsettled_deployed_or_unsupported_failure_rejects(self):
        for field,value in [('deployment_started',True),('deployment_started',None),('conflicts',['unresolved']),
                            ('last_result',{'result':'published'}),('reason',''),('predecessors',[]),('schema_version',True)]:
            with self.subTest(field=field):
                original=copy.deepcopy(self.old);self.old[field]=value
                with self.assertRaises(sync.sync_git.SyncBlocked):self.bind()
                self.old=original

    def test_different_inherited_published_base_rejects(self):
        self.old['predecessors'][0]['published_commit']='9'*40
        with self.assertRaises(sync.sync_git.SyncBlocked):self.bind()

    def test_older_published_bases_keep_their_target_obligations(self):
        older={**copy.deepcopy(self.predecessor),'attempt':'0'*32,'published_commit':'0'*40,
               'targets':{'root-older':{'phase':'blocked','verified':False}}}
        self.old['predecessors'].insert(0,older)
        self.states['root-older']='7'*64;self.request['target_states']=copy.deepcopy(self.states)
        before=copy.deepcopy(self.old['predecessors'])
        binding=self.bind()
        self.assertEqual(set(binding['targets']),{'root-older','root-a','root-b'})
        self.assertEqual(self.old['predecessors'],before)

    def test_new_request_qualifies_and_exact_resumed_request_reuses_receipt(self):
        with patch.object(sync,'_qualify',return_value=self.receipt) as qualify:
            self.assertEqual(sync._ready_receipt(Path('fixture'),self.receipt['ready'],self.receipt['options'],self.old,self.request),self.receipt)
        qualify.assert_called_once()
        resumed={'receipt':copy.deepcopy(self.receipt),'continuation_request_sha256':sync._canonical_hash(self.request)}
        with patch.object(sync,'_qualify') as qualify:
            self.assertEqual(sync._ready_receipt(Path('fixture'),self.receipt['ready'],self.receipt['options'],resumed,self.request),self.receipt)
        qualify.assert_not_called()

    def fixture(self):
        configured=os.environ.get('AGENT_SYNC_TEST_ROOT')
        fixture_root=Path(configured) if configured else Path(__file__).resolve().parents[2]/'offline-rebind-fixtures'
        root=fixture_root/('source-rebind-'+uuid.uuid4().hex)
        common=root/'common';common.mkdir(parents=True)
        lane=common/'agent-signal-integration-worktree';lane.mkdir()
        published=common/'agent-signal-published';published.mkdir()
        (common/'agent-signal-integration-worktree.json').write_text('{}')
        (common/'agent-signal-published.json').write_text('{}')
        admin=common/'admin';admin.mkdir()
        old=copy.deepcopy(self.old);old['published_repo']=str(published);old['integration_repo']=str(lane)
        archive=common/('agent-signal-integration-predecessor-'+self.predecessor['attempt']);archive.mkdir()
        previous={'attempt':self.predecessor['attempt'],'phase':'published','last_result':{'commit':old['base']},
            'rollout':{'targets':copy.deepcopy(self.targets)},'integration_repo':str(lane)}
        data=json.dumps(previous).encode();(archive/'journal.json').write_bytes(data)
        old['predecessors'][0].update(archive=str(archive),journal_sha256=hashlib.sha256(data).hexdigest())
        raw=json.dumps(old).encode();(common/'agent-signal-integration.json').write_bytes(raw)
        request={**copy.deepcopy(self.request),'journal_sha256':hashlib.sha256(raw).hexdigest()}
        bound=sync._successor_binding(old,hashlib.sha256(raw).hexdigest(),request,self.receipt,self.states)
        return common,lane,admin,old,raw,request,bound

    def begin(self,scope,states=None):
        common,lane,admin,old,raw,request,bound=scope
        with patch.object(sync,'_primary',return_value=(common.parent,common)), \
                patch.object(sync,'_published_successor_preflight',return_value=(old,raw,copy.deepcopy(bound),lane,None)), \
                patch.object(sync.sync_git,'git_dir',return_value=admin), \
                patch.object(sync,'_continuation_root_state',side_effect=lambda path:(states or self.states)[str(path)]):
            return sync._begin_published_successor_unlocked(Path('fixture'),self.receipt,request)

    def test_offline_archive_preserves_failed_journal_and_published_obligations(self):
        scope=self.fixture();common,lane,admin,old,raw,request,bound=scope
        successor=self.begin(scope)
        archive=common/('agent-signal-integration-source-failure-'+old['attempt'])
        self.assertEqual((archive/'journal.json').read_bytes(),raw)
        self.assertEqual(successor['phase'],'successor-pending');self.assertFalse(successor['deployment_started'])
        self.assertEqual(successor['predecessors'],old['predecessors'])
        self.assertEqual(successor['receipt'],self.receipt)
        self.assertEqual(successor['source_failures'][0]['failed_ready'],old['receipt']['ready'])
        with patch.object(sync,'_publication_native_obligations',return_value=[]):sync._validate_predecessors(common,successor)
        self.assertEqual(sync._carried_target_holds(successor,{'root-a':{'verified':True}}),['root-b'])
        self.assertEqual((common/'agent-signal-integration.json').read_text(),json.dumps(successor,indent=2)+'\n')

    def test_existing_failed_archive_mismatch_preserves_active_journal(self):
        scope=self.fixture();common,_,_,old,raw,_,_=scope
        archive=common/('agent-signal-integration-source-failure-'+old['attempt']);archive.mkdir()
        (archive/'journal.json').write_bytes(b'other evidence')
        with self.assertRaises(sync.sync_git.SyncBlocked):self.begin(scope)
        self.assertEqual((common/'agent-signal-integration.json').read_bytes(),raw)

    def test_target_drift_after_archive_does_not_replace_active_journal(self):
        scope=self.fixture();common,_,_,old,raw,_,_=scope
        with self.assertRaises(sync.sync_git.SyncBlocked):self.begin(scope,{**self.states,'root-a':'changed'})
        self.assertEqual((common/'agent-signal-integration.json').read_bytes(),raw)
        self.assertEqual((common/('agent-signal-integration-source-failure-'+old['attempt'])/'journal.json').read_bytes(),raw)

    def test_dropped_inherited_obligation_or_changed_archive_rejects(self):
        scope=self.fixture();common=scope[0];successor=self.begin(scope)
        with patch.object(sync,'_publication_native_obligations',return_value=[]):
            bad=copy.deepcopy(successor);bad['predecessors']=[]
            with self.assertRaises(sync.sync_git.SyncBlocked):sync._validate_predecessors(common,bad)
            archive=Path(successor['source_failures'][0]['archive'])/'journal.json';archive.write_bytes(b'changed')
            with self.assertRaises(sync.sync_git.SyncBlocked):sync._validate_predecessors(common,successor)

    def test_failed_source_history_cannot_use_predeployment_release(self):
        with self.assertRaisesRegex(sync.sync_git.SyncBlocked,'inherited published obligations'):
            sync._release_preflight(Path('fixture'),Path('fixture'),{'source_failures':[{'attempt':'2'*32}]},None,None,None)

    def test_changed_failed_backup_reference_rejects(self):
        scope=self.fixture();successor=self.begin(scope)
        successor['source_failures'][0]['source_backups']='different-backup'
        with patch.object(sync,'_publication_native_obligations',return_value=[]):
            with self.assertRaises(sync.sync_git.SyncBlocked):sync._validate_predecessors(scope[0],successor)

    def test_preflight_rejects_dirty_pending_git_operation_and_stale_lineage(self):
        for case in ('dirty','pending','git-operation','lineage'):
            with self.subTest(case=case):
                scope=self.fixture();common,lane,admin,old,raw,request,bound=scope
                if case=='git-operation':(admin/'CHERRY_PICK_HEAD').write_text('uncertain')
                if case=='pending':(admin/'agent-signal-sync.json').write_text('{"unsettled":true}')
                def git(repo,*args,**kwargs):
                    if args[:1]==('rev-parse',):return old['base']
                    if args[:1]==('ls-remote',):return old['base']+'\trefs/heads/main'
                    if case=='lineage' and args[:3]==('merge-base','--is-ancestor',old['receipt']['ready']):
                        raise sync.sync_git.SyncBlocked('not a descendant')
                    return ''
                def owned(primary,common_dir,target,name,branch):
                    return common/name,None,{'head':old['base']}
                with patch.object(sync,'_primary',return_value=(common.parent,common)), \
                        patch.object(sync,'_publication_native_obligations',return_value=[]), \
                        patch.object(sync,'_continuation_root_state',side_effect=lambda path:self.states[str(path)]), \
                        patch.object(sync.sync_git,'destination',return_value=self.receipt['target']), \
                        patch.object(sync,'_owned_worktree',side_effect=owned), \
                        patch.object(sync.sync_git,'changed',return_value={'user.py'} if case=='dirty' else set()), \
                        patch.object(sync.sync_git,'git',side_effect=git), \
                        patch.object(sync.sync_git,'git_dir',return_value=admin), \
                        patch.object(sync.sync_git,'read_pending',return_value={'unsettled':True} if case=='pending' else None):
                    with self.assertRaises(sync.sync_git.SyncBlocked):sync._published_successor_preflight(Path('fixture'),self.receipt,request)
                self.assertEqual((common/'agent-signal-integration.json').read_bytes(),raw)


    def clean_preflight(self,scope):
        common,lane,admin,old,raw,request,bound=scope
        def git(repo,*args,**kwargs):
            if args[:1]==('rev-parse',):return old['base']
            if args[:1]==('ls-remote',):return old['base']+'\trefs/heads/main'
            return ''
        with patch.object(sync,'_primary',return_value=(common.parent,common)), \
                patch.object(sync,'_publication_native_obligations',return_value=[]), \
                patch.object(sync,'_continuation_root_state',side_effect=lambda path:self.states[str(path)]), \
                patch.object(sync.sync_git,'destination',return_value=self.receipt['target']), \
                patch.object(sync,'_owned_worktree',side_effect=lambda p,c,t,name,b:(common/name,None,{'head':old['base']})), \
                patch.object(sync.sync_git,'changed',return_value=set()), \
                patch.object(sync.sync_git,'git',side_effect=git), \
                patch.object(sync.sync_git,'git_dir',return_value=admin), \
                patch.object(sync.sync_git,'read_pending',side_effect=AssertionError('source-failure gate must not decode a receipt')):
            return sync._published_successor_preflight(Path('fixture'),self.receipt,request)

    def test_absent_receipt_admits_without_decoding(self):
        result=self.clean_preflight(self.fixture())
        self.assertIsNone(result[-1]);self.assertTrue(result[2]['source_failure'])

    def test_empty_object_receipt_presence_rejects_before_decoding(self):
        scope=self.fixture();(scope[2]/'agent-signal-sync.json').write_text('{}')
        with self.assertRaises(sync.sync_git.SyncBlocked):self.clean_preflight(scope)
        self.assertEqual((scope[0]/'agent-signal-integration.json').read_bytes(),scope[4])

    def test_json_null_receipt_presence_rejects_before_decoding(self):
        scope=self.fixture();(scope[2]/'agent-signal-sync.json').write_text('null')
        with self.assertRaises(sync.sync_git.SyncBlocked):self.clean_preflight(scope)
        self.assertEqual((scope[0]/'agent-signal-integration.json').read_bytes(),scope[4])

    def test_receipt_directory_presence_rejects_before_decoding(self):
        scope=self.fixture();(scope[2]/'agent-signal-sync.json').mkdir()
        with self.assertRaises(sync.sync_git.SyncBlocked):self.clean_preflight(scope)

    def test_dangling_link_metadata_is_presence(self):
        scope=self.fixture()
        with patch.object(sync.sync_git,'git_dir',return_value=scope[2]), \
                patch.object(Path,'lstat',return_value=SimpleNamespace(st_mode=0o120777)):
            with self.assertRaises(sync.sync_git.SyncBlocked):sync._require_absent_inner_receipt(scope[1])

    def test_receipt_metadata_error_rejects_without_fallback(self):
        scope=self.fixture()
        with patch.object(sync.sync_git,'git_dir',return_value=scope[2]), \
                patch.object(Path,'lstat',side_effect=PermissionError('synthetic unreadable metadata')) as query:
            with self.assertRaises(sync.sync_git.SyncBlocked):sync._require_absent_inner_receipt(scope[1])
        query.assert_called_once()

    def test_missing_receipt_parent_is_not_known_absence(self):
        scope=self.fixture()
        with patch.object(sync.sync_git,'git_dir',return_value=scope[0]/'missing-admin'):
            with self.assertRaises(sync.sync_git.SyncBlocked):sync._require_absent_inner_receipt(scope[1])

    def test_late_receipt_presence_preserves_active_failed_journal(self):
        scope=self.fixture();common,lane,admin,old,raw,request,bound=scope
        def states(path):
            (admin/'agent-signal-sync.json').write_text('{}')
            return self.states[str(path)]
        with patch.object(sync,'_primary',return_value=(common.parent,common)), \
                patch.object(sync,'_published_successor_preflight',return_value=(old,raw,copy.deepcopy(bound),lane,None)), \
                patch.object(sync.sync_git,'git_dir',return_value=admin), \
                patch.object(sync,'_continuation_root_state',side_effect=states):
            with self.assertRaises(sync.sync_git.SyncBlocked):
                sync._begin_published_successor_unlocked(Path('fixture'),self.receipt,request)
        self.assertEqual((common/'agent-signal-integration.json').read_bytes(),raw)
        self.assertEqual((admin/'agent-signal-sync.json').read_text(),'{}')


if __name__ == '__main__':
    unittest.main()
