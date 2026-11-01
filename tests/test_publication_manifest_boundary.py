"""File-free publisher controls; Git/staging/native execution are not exercised."""
from pathlib import Path
from contextlib import ExitStack, nullcontext
import json
import sys
import unittest
from unittest.mock import Mock, patch

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
        saved=Mock();written=Mock()
        def no_op_sync(*args,**kwargs):
            path=reconcile._write_request(REPO,record)
            self.assertEqual(path,REPO/REQUEST)
            return {'result':'applied','request_id':record['request_id']}
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
                'prepare_candidate':lambda *a,**k:nullcontext((REPO,'checked-tree')),
                'publication_candidate':lambda *a,**k:nullcontext((REPO,'checked-tree')),
                'publish':publisher,'save_pending':saved,
            }.items():stack.enter_context(patch.object(sync_git,name,value))
            stack.enter_context(patch.object(instruction_changes,'check',return_value=[]))
            stack.enter_context(patch.object(reconcile.fleet,'render_snapshot'))
            stack.enter_context(patch.object(reconcile.fleet,'atomic_json',written))
            result=reconcile._scoped_complete_sync(REPO,machine='local-windows',adopt=[],recovery_roots={},skill_roots=None,capture_recovery=False,include=include,message='fixture only')
        written.assert_called_once()
        return result,publisher,saved,include

    def test_noop_generated_receipt_stops_before_publisher_state(self):
        result,publisher,saved,_=self.run_scoped()
        self.assertEqual(result['result'],'incomplete')
        self.assertIn('publication paths differ from reviewed manifest; unexpected=',result['reason'])
        publisher.assert_not_called();saved.assert_not_called()

    def test_explicit_noop_receipt_remains_publishable_with_bound_scope(self):
        result,publisher,saved,include=self.run_scoped(explicit=True)
        self.assertEqual(result['result'],'published',result)
        publisher.assert_called_once()
        pending=saved.call_args.args[1]
        self.assertEqual(set(pending['approved_paths']),set(include))
        self.assertEqual(set(pending['files']),set(include))


if __name__=='__main__':unittest.main()
