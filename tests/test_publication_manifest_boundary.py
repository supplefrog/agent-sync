"""File-free publisher controls; Git/staging/native execution are not exercised."""
from pathlib import Path
from contextlib import ExitStack, nullcontext
import json
import sys
import unittest
from unittest.mock import Mock, patch
import hashlib
import io
import ast
import inspect

REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO/'tools'))
import reconcile
import sync_git
import instruction_changes

REQUEST='reconciliation/requests/abe7674338cc29b82f0f6495ca59743b8a38a199eebbe8ab211891472ff72c8d.json'


class ManifestBoundary(unittest.TestCase):
    def test_generated_path_needs_explicit_selection(self):
        with self.assertRaisesRegex(sync_git.SyncBlocked,'unexpected='+REQUEST):
            sync_git.assert_publication_paths(REPO,['host-deltas.json'],['host-deltas.json',REQUEST])

    def test_explicit_receipt_selection_is_valid(self):
        sync_git.assert_publication_paths(REPO,['host-deltas.json',REQUEST],{REQUEST:'digest','host-deltas.json':'digest'})

    def test_missing_or_duplicate_manifest_fails(self):
        for manifest in (None,['host-deltas.json','host-deltas.json']):
            with self.subTest(manifest=manifest), self.assertRaises(sync_git.SyncBlocked):
                sync_git.assert_publication_paths(REPO,manifest,['host-deltas.json'])

    def test_missing_selected_path_fails(self):
        with self.assertRaisesRegex(sync_git.SyncBlocked,'missing=host-deltas.json'):
            sync_git.assert_publication_paths(REPO,['host-deltas.json',REQUEST],[REQUEST])

    def test_resume_scope_checked_before_git_or_identity_reads(self):
        for manifest in (None,['host-deltas.json']):
            with self.subTest(manifest=manifest), patch.object(sync_git,'git') as git, patch.object(sync_git,'identities') as identities:
                with self.assertRaises(sync_git.SyncBlocked):
                    sync_git._scoped_selection_gate(REPO,{'approved_paths':manifest,'files':{'host-deltas.json':'a',REQUEST:'b'}})
                git.assert_not_called();identities.assert_not_called()

    def run_scoped(self,*,explicit=False):
        # Actual observed no-op receipt: equal before/after hashes, no checks,
        # no skill deployment. Validate/write it through the actual writer;
        # atomic_json is intercepted so the test never changes the source tree.
        record=json.loads((REPO/REQUEST).read_bytes())
        self.assertEqual(record['artifacts'][0]['before_sha256'],record['artifacts'][0]['after_sha256'])
        self.assertEqual(record['operation'],'refresh-artifact-bindings')
        include=['host-deltas.json']+([REQUEST] if explicit else [])
        publisher=Mock(return_value={'result':'published','commit':'f'*40})
        saved=Mock();virtual={}
        written=Mock(side_effect=lambda path,value:virtual.__setitem__(str(path),reconcile._json_bytes(value)))
        private_written=Mock(side_effect=lambda path,raw:virtual.__setitem__(str(path),raw))
        original_read=Path.read_bytes
        def no_op_sync(*args,**kwargs):
            self.assertEqual(set(kwargs['public_receipts']),set(include))
            path=reconcile._write_request(REPO,record,public_receipts=kwargs['public_receipts'])
            self.assertEqual(path==REPO/REQUEST,explicit)
            return {'result':'applied','request_id':record['request_id'],
                    'operational_receipt':reconcile._request_reference(REPO,path,record['request_id'])}
        with ExitStack() as stack:
            replacements={
                'sync':no_op_sync,'_owner_binding_preflight':lambda *a,**k:{'repository:tools/reconcile.py'},
                '_scope_dependencies':lambda *a,**k:{'stable':'binding'},
                '_prepare_candidate_bindings':lambda *a,**k:None,
                '_candidate_commands':lambda *a,**k:[],
                '_run_candidate_checks':lambda *a,**k:None,
            }
            for name,value in replacements.items():stack.enter_context(patch.object(reconcile,name,value))
            for name,value in {
                'lock':lambda *a,**k:nullcontext(), 'read_pending':lambda *a:None,
                'assert_integration_owner':lambda *a:None,'assert_ready_source':lambda *a:None,
                'destination':lambda *a:{'branch':'main','remote':'origin','ref':'refs/heads/main'},
                'preflight':lambda *a,**k:None,'git':lambda *a,**k:'a'*40,
                'changed':lambda *a,**k:set(),
                'common_dir':lambda *a:REPO/'.git',
                'prepare_candidate':lambda *a,**k:nullcontext((REPO,'checked-tree')),
                'publication_candidate':lambda *a,**k:nullcontext((REPO,'checked-tree')),
                'publish':publisher,'save_pending':saved,
            }.items():stack.enter_context(patch.object(sync_git,name,value))
            stack.enter_context(patch.object(instruction_changes,'check',return_value=[]))
            stack.enter_context(patch.object(reconcile.fleet,'render_snapshot'))
            stack.enter_context(patch.object(reconcile.fleet,'atomic_json',written))
            stack.enter_context(patch.object(reconcile,'_store_private_request',private_written))
            stack.enter_context(patch.object(Path,'read_bytes',lambda p:virtual[str(p)] if str(p) in virtual else original_read(p)))
            result=reconcile._scoped_complete_sync(REPO,machine='local-windows',adopt=[],recovery_roots={},skill_roots=None,capture_recovery=False,include=include,message='fixture only')
        if explicit:written.assert_called_once();private_written.assert_not_called()
        else:private_written.assert_called_once();written.assert_not_called()
        return result,publisher,saved,include

    def test_noop_operational_receipt_is_retained_without_widening_publication(self):
        result,publisher,saved,_=self.run_scoped()
        self.assertEqual(result['result'],'published',result)
        publisher.assert_called_once()
        pending=saved.call_args.args[1]
        self.assertEqual(set(pending['approved_paths']),{'host-deltas.json'})
        self.assertEqual(set(pending['files']),{'host-deltas.json'})
        self.assertEqual(pending['operational_receipt']['storage'],'private')

    def test_explicit_noop_receipt_remains_publishable_with_bound_scope(self):
        result,publisher,saved,include=self.run_scoped(explicit=True)
        self.assertEqual(result['result'],'published',result)
        publisher.assert_called_once()
        pending=saved.call_args.args[1]
        self.assertEqual(set(pending['approved_paths']),set(include))
        self.assertEqual(set(pending['files']),set(include))

    def test_private_receipt_body_drift_or_public_downgrade_rejects(self):
        record=json.loads((REPO/REQUEST).read_bytes());raw=reconcile._json_bytes(record)
        with patch.object(sync_git,'common_dir',return_value=REPO/'.git'):
            path=reconcile._private_request_path(REPO,record['request_id'],hashlib.sha256(raw).hexdigest())
            reference={'request_id':record['request_id'],'storage':'private','path':str(path),'sha256':hashlib.sha256(raw).hexdigest()}
            result={'request_id':record['request_id'],'operational_receipt':reference}
            with patch.object(Path,'read_bytes',return_value=raw):
                self.assertEqual(reconcile._publication_receipt_paths(REPO,result,[]),set())
                with self.assertRaisesRegex(RuntimeError,'storage'):
                    reconcile._publication_receipt_paths(REPO,result,[REQUEST])
            with patch.object(Path,'read_bytes',return_value=raw+b'changed'):
                with self.assertRaisesRegex(RuntimeError,'bytes changed'):
                    reconcile._publication_receipt_paths(REPO,result,[])

    def test_missing_reference_and_forged_path_fail_before_body_read(self):
        rid=REQUEST.rsplit('/',1)[1][:-5]
        with self.assertRaisesRegex(RuntimeError,'reference missing'):
            reconcile._publication_receipt_paths(REPO,{'request_id':rid},[])
        reference={'request_id':rid,'storage':'private','path':'unrelated','sha256':'a'*64}
        with patch.object(sync_git,'common_dir',return_value=REPO/'.git'),patch.object(Path,'read_bytes') as read:
            with self.assertRaisesRegex(RuntimeError,'storage'):
                reconcile._publication_receipt_paths(REPO,{'request_id':rid,'operational_receipt':reference},[])
            read.assert_not_called()

    def test_content_addressed_store_retains_prior_records_and_refuses_collision(self):
        files={}
        class Stream(io.BytesIO):
            def __init__(self,path):super().__init__();self.path=path
            def close(self):
                if not self.closed:files[self.path]=self.getvalue()
                super().close()
            def fileno(self):return 123
        def open_path(path,mode):
            self.assertEqual(mode,'xb')
            if str(path) in files:raise FileExistsError()
            return Stream(str(path))
        a=REPO/'private-fixture'/'first.json';b=REPO/'private-fixture'/'second.json'
        with patch.object(Path,'mkdir'),patch.object(Path,'open',open_path),patch.object(Path,'read_bytes',lambda p:files[str(p)]),patch.object(reconcile.os,'fsync'):
            reconcile._store_private_request(a,b'first')
            reconcile._store_private_request(b,b'second')
            reconcile._store_private_request(a,b'first')
            with self.assertRaisesRegex(RuntimeError,'collision'):
                reconcile._store_private_request(a,b'foreign')
        self.assertEqual(files,{str(a):b'first',str(b):b'second'})

    def test_transaction_and_broad_publisher_forward_scope_without_implicit_paths(self):
        tree=ast.parse((REPO/'tools/reconcile.py').read_text(encoding='utf-8'))
        sync=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='sync')
        calls=[n for n in ast.walk(sync) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='_decision_receipt']
        self.assertEqual(len(calls),5)
        self.assertTrue(all(any(k.arg=='public_receipts' for k in n.keywords) for n in calls))
        for name in ['_scoped_complete_sync','_complete_source_sync']:
            node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==name)
            calls=[n for n in ast.walk(node) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='sync']
            self.assertTrue(calls)
            self.assertTrue(all(any(k.arg=='public_receipts' for k in n.keywords) for n in calls))
            self.assertNotIn('selected.add(f"reconciliation/requests/',ast.unparse(node))

    def test_standalone_writer_compatibility_is_not_publication_authority(self):
        record=json.loads((REPO/REQUEST).read_bytes())
        with patch.object(reconcile.fleet,'atomic_json') as written,patch.object(reconcile,'_store_private_request') as private:
            self.assertEqual(reconcile._write_request(REPO,record),REPO/REQUEST)
            written.assert_called_once();private.assert_not_called()

    def actual_unchanged(self, *, public=False, damage=None):
        """Run the producer body with virtual storage, not a stubbed sync result."""
        virtual={};original_read=Path.read_bytes
        rid=reconcile._request_id('local-windows',['owner'],['a'*64])
        relative=reconcile._request_relative(rid)
        def save(path,raw):
            if damage=='missing':return
            virtual[str(path)]=b'{}' if damage=='corrupt' else raw
        def read(path):
            if str(path) in virtual:return virtual[str(path)]
            if rid in str(path):raise FileNotFoundError('virtual evidence missing')
            return original_read(path)
        forbidden=Mock(side_effect=AssertionError('unchanged operation entered mutation path'))
        marker=Mock()
        with ExitStack() as stack:
            for name,value in {
                '_selected_owners':lambda *a:{'owner'},'_destinations':lambda *a:[],
                '_snapshot':lambda *a:REPO/'render/fleet',
                '_skill_state':lambda *a:{'name':'owner','mode':'unchanged','canonical_sha256':'a'*64},
                '_assert_skill_public_safe':lambda *a:None,
                '_agent_scope_identities':lambda *a:{},'_mutation_identity':lambda *a:None,
                '_store_private_request':save,'_copy_optional':forbidden,'_run_checks':forbidden,
                '_copy_binding_source':forbidden,
            }.items():stack.enter_context(patch.object(reconcile,name,value))
            # This control selects no binding work, independently of whether the
            # enclosing test checkout has a real host-delta manifest.
            stack.enter_context(patch.object(reconcile.host_deltas,'_load_manifest_unbound',return_value={'entries':[]}))
            stack.enter_context(patch.object(reconcile.tempfile,'TemporaryDirectory',return_value=nullcontext(str(REPO/'virtual-workspace'))))
            stack.enter_context(patch.object(reconcile.fleet,'atomic_json',lambda p,v:save(p,reconcile._json_bytes(v))))
            stack.enter_context(patch.object(reconcile.fleet,'render_snapshot',forbidden))
            stack.enter_context(patch.object(reconcile.fleet,'apply_snapshot',forbidden))
            stack.enter_context(patch.object(reconcile.recovery,'snapshot',forbidden))
            stack.enter_context(patch.object(sync_git,'common_dir',return_value=REPO/'.git'))
            stack.enter_context(patch.object(sync_git,'assert_ready_source'))
            stack.enter_context(patch.object(sync_git,'identities',return_value={}))
            stack.enter_context(patch.object(sync_git,'mark_integration_deployment_started',marker))
            stack.enter_context(patch.object(Path,'read_bytes',read))
            result=inspect.unwrap(reconcile.sync)(REPO,adopt=['owner'],recovery_roots={},
                check_commands=[],public_receipts=[relative] if public else [],
                ready_input={'files':{},'agent_identities':{},'attempt':'virtual-attempt'})
            if damage:return result
            self.assertEqual(result['result'],'unchanged')
            self.assertFalse(result['mutation_performed'])
            self.assertEqual(result['operational_receipt']['storage'],'repository' if public else 'private')
            self.assertEqual(reconcile._publication_receipt_paths(REPO,result,[relative] if public else []),{relative} if public else set())
            record=json.loads(read(Path(result['operational_receipt']['path'])))
            self.assertEqual(record['result'],'unchanged')
            self.assertEqual(record['disposition'],'unchanged')
            self.assertTrue(all(row['status']=='skipped' for row in record['phases'] if row['name'] in {'canonicalize','render','validate','deploy'}))
            marker.assert_not_called();forbidden.assert_not_called()
        return result

    def test_actual_producer_noop_skips_mutation_in_private_and_public_storage(self):
        for public in (False,True):
            with self.subTest(public=public):self.actual_unchanged(public=public)

    def test_actual_producer_missing_or_corrupt_evidence_cannot_report_unchanged(self):
        for public in (False,True):
            for damage in ('missing','corrupt'):
                with self.subTest(public=public,damage=damage),self.assertRaises((FileNotFoundError,RuntimeError,reconcile.jsonschema.ValidationError)):
                    self.actual_unchanged(public=public,damage=damage)

    def broad_resume(self, *, damage=None, legacy=False, no_operation=False):
        record=json.loads((REPO/REQUEST).read_bytes());raw=reconcile._json_bytes(record)
        virtual={};original_read=Path.read_bytes;pushed=[];checks=[]
        with ExitStack() as stack:
            stack.enter_context(patch.object(sync_git,'common_dir',return_value=REPO/'.git'))
            path=reconcile._private_request_path(REPO,record['request_id'],hashlib.sha256(raw).hexdigest())
            virtual[str(path)]=raw
            reference={'request_id':record['request_id'],'path':str(path),'storage':'private','sha256':hashlib.sha256(raw).hexdigest()}
            state={'schema_version':2,'owners':['owner'],'machine':'local-windows','destinations':[],
                'recovery_roots':{},'capture_recovery':False,'agent_identities':{},
                'operational_receipt_required':True,'operational_receipt':reference,
                'base':'a'*40,'files':{'host-deltas.json':'b'*64}}
            if legacy:
                state.update(schema_version=1);state.pop('operational_receipt_required');state.pop('operational_receipt')
            if no_operation:state.update(owners=[],operational_receipt_required=False,operational_receipt=None)
            if damage=='missing-reference':state.pop('operational_receipt')
            if damage=='null-reference':state['operational_receipt']=None
            if damage=='missing-requirement':state.pop('operational_receipt_required')
            if damage=='empty-reference':state['operational_receipt']={}
            def read(p):
                if str(p)==str(path):
                    if str(p) not in virtual:raise FileNotFoundError('virtual evidence removed')
                    return virtual[str(p)]
                return original_read(p)
            def run_checks(*args):
                checks.append(True)
                if damage=='body-removed-during-checks':virtual.pop(str(path),None)
                if damage=='body-altered-during-checks':virtual[str(path)]=raw+b'changed'
                if damage=='reference-removed-during-checks':state.pop('operational_receipt',None)
                return []
            def publisher(repo,pending,*,verify,readback):
                verify();verify();pushed.append(True)
                if damage=='body-removed-before-final-readback':virtual.pop(str(path),None)
                readback()
                return {'result':'published','commit':'f'*40}
            for obj,name,value in [
                (sync_git,'read_pending',lambda *a:state),(sync_git,'lock',lambda *a,**k:nullcontext()),
                (sync_git,'assert_integration_owner',lambda *a:None),(sync_git,'publish',publisher),
                (reconcile,'_reconciliation_intent',lambda **k:{'scoped':False}),
                (reconcile,'_destinations',lambda *a:[]),(reconcile,'_agent_identities',lambda *a:{}),
                (reconcile,'_snapshot',lambda *a:REPO/'render/fleet'),(reconcile,'_run_checks',run_checks),
                (reconcile.capability_intake,'fleet_findings',lambda *a,**k:[]),
                (reconcile.fleet,'registry',lambda *a:{}),(reconcile.fleet,'load_manifest',lambda *a:{'skills':{}}),
                (instruction_changes,'check',lambda *a:[]),(Path,'read_bytes',read),
            ]:stack.enter_context(patch.object(obj,name,value))
            result=reconcile._complete_source_sync(REPO,recovery_roots={},capture_recovery=False,scoped=False)
        return result,pushed,checks,reference

    def test_broad_resume_rechecks_private_evidence_after_verification(self):
        for damage in ('body-removed-during-checks','body-altered-during-checks','reference-removed-during-checks'):
            with self.subTest(damage=damage):
                result,pushed,checks,_=self.broad_resume(damage=damage)
                self.assertEqual(result['result'],'incomplete',result)
                self.assertTrue(checks);self.assertEqual(pushed,[])

    def test_broad_resume_rejects_missing_new_required_evidence_before_publisher(self):
        for damage in ('missing-reference','null-reference','missing-requirement','empty-reference'):
            with self.subTest(damage=damage):
                result,pushed,checks,_=self.broad_resume(damage=damage)
                self.assertEqual(result['result'],'incomplete',result)
                self.assertEqual(pushed,[]);self.assertEqual(checks,[])

    def test_broad_final_readback_cannot_claim_completion_after_evidence_loss(self):
        result,pushed,checks,_=self.broad_resume(damage='body-removed-before-final-readback')
        self.assertEqual(result['result'],'incomplete',result)
        self.assertEqual(pushed,[True]);self.assertTrue(checks)

    def test_receipt_requirement_covers_capture_and_binding_and_rejects_false_flags(self):
        for selector in ({'owners':['owner']},{'capture_recovery':True},{'scoped':True,'binding_identities':['repository:tools/reconcile.py']}):
            state={'schema_version':2,'owners':[],'capture_recovery':False,'operational_receipt_required':True,
                'operational_receipt':None,'files':{},'approved_paths':[],**selector}
            with self.subTest(selector=selector),self.assertRaisesRegex(RuntimeError,'required operational receipt missing'):
                reconcile._operational_receipt_state(REPO,state)
            state['operational_receipt_required']=False
            with self.subTest(selector=selector),self.assertRaisesRegex(RuntimeError,'requirement is missing or inconsistent'):
                reconcile._operational_receipt_state(REPO,state)

    def test_broad_completion_retains_required_reference_and_explicit_legacy_noop_compatibility(self):
        result,pushed,checks,reference=self.broad_resume()
        self.assertEqual(result['result'],'published',result);self.assertEqual(pushed,[True])
        self.assertEqual(result['operational_receipt'],reference)
        self.assertEqual(result['request_id'],reference['request_id'])
        for options in ({'legacy':True},{'no_operation':True}):
            with self.subTest(options=options):
                result,pushed,_,_=self.broad_resume(**options)
                self.assertEqual(result['result'],'published',result);self.assertEqual(pushed,[True])
                self.assertNotIn('operational_receipt',result)

    def test_scoped_resume_rejects_missing_required_reference_before_publisher(self):
        for value in ('missing',None):
            state={'schema_version':2,'scoped':True,'owners':['owner'],'machine':'local-windows',
                'destinations':[],'recovery_roots':{},'capture_recovery':False,'dependencies':{},
                'binding_identities':[],'operational_receipt_required':True,'approved_paths':['host-deltas.json'],
                'files':{'host-deltas.json':'a'*64}}
            if value is None:state['operational_receipt']=None
            with ExitStack() as stack:
                publisher=Mock()
                for obj,name,replacement in [
                    (sync_git,'lock',lambda *a,**k:nullcontext()),(sync_git,'read_pending',lambda *a:state),
                    (sync_git,'assert_integration_owner',lambda *a:None),(sync_git,'publish',publisher),
                    (reconcile,'_selected_owners',lambda *a:{'owner'}),(reconcile,'_destinations',lambda *a:[]),
                ]:stack.enter_context(patch.object(obj,name,replacement))
                result=reconcile._scoped_complete_sync(REPO,machine='local-windows',adopt=['owner'],
                    recovery_roots={},skill_roots=None,capture_recovery=False,include=[],message='virtual')
                self.assertEqual(result['result'],'incomplete',result);publisher.assert_not_called()


if __name__=='__main__':unittest.main()
