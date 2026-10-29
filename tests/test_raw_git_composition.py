"""Synthetic local repositories only; no release/host/profile/remote operations."""
from pathlib import Path
import copy
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
import uuid
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import sync_git
import worktree_sync as sync


class RawComposition(unittest.TestCase):
    def setUp(self):
        configured=os.environ.get('AGENT_SYNC_TEST_ROOT')
        self.root=Path(configured) if configured else Path(tempfile.gettempdir())/'agent-sync-synthetic-git-controls'
        self.repo=self.root/(self._testMethodName+'-'+uuid.uuid4().hex)
        self.repo.mkdir(parents=True,exist_ok=False)
        self.git('init','-q')
        self.base_files={'.gitattributes':b'*.md text eol=lf\n*.py text eol=lf\n',
            'doc.md':b'base\r\nunchanged\r\n','mixed.py':b'first\r\nsecond\n',
            'removed.md':b'remove\r\n','remote.dat':b'remote baseline\r\n'}
        self.base=self.commit(None,self.base_files)
        self.ready_files={**self.base_files,'doc.md':b'reviewed\r\nunchanged\r\n','added.dat':b'\x00raw\r\n\xff'}
        del self.ready_files['removed.md']
        self.ready=self.commit(self.base,self.ready_files)
        self.selected=['doc.md','removed.md','added.dat']
        self.checkout_raw(self.base,self.base_files)
        self.journal={};self.saved=[]

    def git(self,*args,input=None,env=None):
        return subprocess.check_output(['git','-c','core.longpaths=true','-C',str(self.repo),*args],
            input=input,env=env,stderr=subprocess.STDOUT)

    def commit(self,parent,files):
        index=self.repo/('.git/fixture-index-'+uuid.uuid4().hex)
        env=dict(os.environ,GIT_INDEX_FILE=str(index))
        self.git('read-tree','--empty',env=env)
        for name,data in files.items():
            oid=self.git('hash-object','-w','--stdin',input=data).decode().strip()
            self.git('update-index','--add','--cacheinfo','100644,'+oid+','+name,env=env)
        tree=self.git('write-tree',env=env).decode().strip()
        args=['-c','user.name=Synthetic Fixture','-c','user.email=fixture@invalid','commit-tree',tree]
        if parent:args+=['-p',parent]
        return self.git(*args,input=b'synthetic raw-byte control\n').decode().strip()

    def checkout_raw(self,commit,files):
        # Fixture setup only: build the exact malformed legacy byte/index
        # condition without invoking a product checkout, release or live repair.
        self.git('update-ref','HEAD',commit)
        self.git('read-tree',commit)
        for name,data in files.items():
            path=self.repo/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)

    def save(self):
        self.saved.append(copy.deepcopy(self.journal))

    def stage(self,base=None,ready=None,selected=None):
        return sync._stage_raw_composition(self.repo,base or self.base,
            {'ready':ready or self.ready,'source_base':self.base,'paths':selected or self.selected},
            self.journal,self.save)

    def assert_bytes(self,files):
        for name,data in files.items():self.assertEqual((self.repo/name).read_bytes(),data,name)

    def test_legacy_checkout_failure_and_raw_guard_are_separate(self):
        status=self.git('status','--porcelain').decode()
        self.assertIn('doc.md',status)
        self.assertEqual(sync_git.changed(self.repo),set())
        with self.assertRaises(sync_git.GitFailure) as failure:
            sync._checkout_git(self.repo,'cherry-pick','--no-commit',self.ready)
        self.assertEqual(failure.exception.detail['operation'],'cherry-pick')
        self.assertIn(self.ready,failure.exception.detail['commit_ids'])
        self.assertIn('would be overwritten',failure.exception.detail['stderr'])
        (self.repo/'legacy-failure.private.json').write_text(json.dumps(failure.exception.detail,indent=2)+'\n',encoding='utf-8')
        self.assert_bytes(self.base_files)

    def test_exact_raw_bytes_survive_add_change_delete_and_index_stays_base(self):
        tree=self.stage()
        self.assertEqual(tree,self.git('rev-parse',self.ready+'^{tree}').decode().strip())
        self.assert_bytes(self.ready_files)
        self.assertFalse((self.repo/'removed.md').exists())
        self.assertEqual(self.git('diff','--cached','--name-only'),b'')
        self.assertEqual(self.git('rev-parse','HEAD').decode().strip(),self.base)
        self.assertEqual(set(self.journal['composition_files']),set(self.selected))
        self.assertTrue(self.saved)
        self.assertEqual(self.saved[0]['composition_before']['doc.md'],hashlib.sha256(self.base_files['doc.md']).hexdigest())

    def test_unrelated_remote_bytes_survive(self):
        remote_files={**self.base_files,'remote.dat':b'remote update\r\n'}
        remote=self.commit(self.base,remote_files);self.checkout_raw(remote,remote_files)
        self.stage(base=remote)
        self.assert_bytes({**self.ready_files,'remote.dat':remote_files['remote.dat']})

    def test_raw_rollback_restores_only_owned_bytes(self):
        self.stage();sync._abort_composition(self.repo,self.base,self.journal)
        self.assert_bytes(self.base_files)
        self.assertFalse((self.repo/'added.dat').exists())
        self.assertEqual(sync_git.changed(self.repo),set())

    def test_prior_real_edit_rejected_without_overwrite(self):
        data=b'user change\r\n';(self.repo/'doc.md').write_bytes(data)
        with self.assertRaises(sync_git.SyncBlocked):self.stage()
        self.assertEqual((self.repo/'doc.md').read_bytes(),data)
        sync._abort_composition(self.repo,self.base,self.journal)
        self.assertEqual((self.repo/'doc.md').read_bytes(),data)

    def test_line_ending_only_user_edit_is_real_byte_drift(self):
        data=self.base_files['doc.md'].replace(b'\r\n',b'\n');(self.repo/'doc.md').write_bytes(data)
        with self.assertRaises(sync_git.SyncBlocked):self.stage()
        self.assertEqual((self.repo/'doc.md').read_bytes(),data)

    def test_staged_work_rejected(self):
        (self.repo/'doc.md').write_bytes(b'staged\n');self.git('add','doc.md')
        with self.assertRaises(sync_git.SyncBlocked):self.stage()
        self.assertTrue(self.git('diff','--cached','--name-only'))

    def test_untracked_user_file_rejected(self):
        (self.repo/'user.dat').write_bytes(b'keep')
        with self.assertRaises(sync_git.SyncBlocked):self.stage()
        self.assertEqual((self.repo/'user.dat').read_bytes(),b'keep')

    def test_edit_after_plan_is_not_clobbered_by_rollback(self):
        self.stage();(self.repo/'doc.md').write_bytes(b'concurrent user change')
        with self.assertRaises(sync_git.SyncBlocked):sync._abort_composition(self.repo,self.base,self.journal)
        self.assertEqual((self.repo/'doc.md').read_bytes(),b'concurrent user change')

    def test_source_scope_expansion_rejected(self):
        with self.assertRaisesRegex(sync_git.SyncBlocked,'unselected'):
            self.stage(selected=['doc.md'])
        self.assert_bytes(self.base_files)

    def test_merged_selected_bytes_need_review(self):
        # A clean object merge may not silently change reviewed selected bytes.
        remote_files={**self.base_files,'doc.md':b'base\r\nremote addition\r\n'}
        remote=self.commit(self.base,remote_files);self.checkout_raw(remote,remote_files)
        with self.assertRaises(sync_git.SyncBlocked):self.stage(base=remote)
        self.assert_bytes(remote_files)

    def test_omitted_metadata_uses_original_baseline_not_last_parent(self):
        baseline_files={**self.base_files,'host-deltas.json':b'{"v":0}\n'}
        baseline=self.commit(self.base,baseline_files)
        previous_files={**baseline_files,'host-deltas.json':b'{"v":1}\n'}
        previous=self.commit(baseline,previous_files)
        final_files={**previous_files,'doc.md':b'reviewed\r\n'}
        final=self.commit(previous,final_files)
        sanitized=sync._sanitized_commit(self.repo,final,baseline)
        self.assertEqual(self.git('show',sanitized+':host-deltas.json'),baseline_files['host-deltas.json'])
        self.assertEqual(self.git('show',sanitized+':doc.md'),final_files['doc.md'])

    def lf_index_case(self):
        before={**self.base_files,'doc.md':b'base\nunchanged\n','other.md':b'other\n'}
        base=self.commit(self.base,before)
        after={**before,'doc.md':b'base\r\nunchanged\r\n'}
        self.base=base;self.base_files=before;self.ready_files=after
        self.ready=self.commit(base,after);self.selected=['doc.md']
        self.checkout_raw(base,before)
        self.journal['attempt']='1'*32

    def test_lf_to_crlf_only_change_survives_caller_verify_and_publisher_guards(self):
        self.lf_index_case();tree=self.stage()
        # Git's filtered response omits this raw-different tracked path.
        filtered=self.git('diff','--raw','--no-renames','-z','HEAD','--').decode().split('\0')
        self.assertNotIn('doc.md',filtered)
        files=sync_git.identities(self.repo,sync_git.changed(self.repo))
        self.assertEqual(files,self.journal['composition_files'])
        self.assertEqual(set(files),{'doc.md'})
        self.journal['base']=self.base
        # Only the separate Temp reconstruction is stubbed. The real caller's
        # HEAD/index/path/raw-identity guards run, without a Temp/test retry.
        with patch.object(sync_git,'assert_integration_owner'), \
                patch.object(sync_git,'prepare_candidate',return_value=nullcontext((self.repo,tree))) as reconstruction:
            sync._verify_composition(self.repo,self.journal)
        self.assertEqual(reconstruction.call_args.args[1],files)
        sync_git._scoped_selection_gate(self.repo,{'base':self.base,'files':files})
        self.assertEqual(self.git('diff','--cached','--name-only'),b'')
        self.assert_bytes(self.ready_files)

    def test_lf_to_crlf_prior_user_drift_is_not_hidden(self):
        self.lf_index_case();data=b'base\r\nunchanged\r\n'
        (self.repo/'doc.md').write_bytes(data)
        self.assertNotIn('doc.md',self.git('diff','--name-only').decode().splitlines())
        self.assertIn('doc.md',sync_git.changed(self.repo))
        with self.assertRaises(sync_git.SyncBlocked):self.stage()
        self.assertEqual((self.repo/'doc.md').read_bytes(),data)

    def test_unexpected_raw_equivalent_path_still_blocks_verification(self):
        self.lf_index_case();tree=self.stage();self.journal['base']=self.base
        data=b'other\r\n';(self.repo/'other.md').write_bytes(data)
        self.assertIn('other.md',sync_git.changed(self.repo))
        with patch.object(sync_git,'assert_integration_owner'), \
                patch.object(sync_git,'prepare_candidate',return_value=nullcontext((self.repo,tree))) as reconstruction:
            with self.assertRaises(sync_git.SyncBlocked):sync._verify_composition(self.repo,self.journal)
        reconstruction.assert_not_called()
        self.assertEqual((self.repo/'other.md').read_bytes(),data)


class SafeGitFailure(unittest.TestCase):
    def result(self,stderr,stdout='',code=128):
        return SimpleNamespace(returncode=code,stderr=stderr,stdout=stdout)

    def test_exact_local_command_commit_exit_and_cause_retained(self):
        commit='a'*40
        error=sync_git.GitFailure(Path.cwd(),('-c','core.autocrlf=false','cherry-pick','--no-commit',commit),
            self.result('error: local changes would be overwritten'))
        self.assertEqual(error.detail['command'],'git cherry-pick --no-commit '+commit)
        self.assertEqual(error.detail['exit_code'],128)
        self.assertIn('local changes would be overwritten',str(error))

    def test_sensitive_local_lines_and_absolute_paths_are_redacted(self):
        secret='fixture-only-sensitive-value'
        url='https://example.invalid/repo'
        error=sync_git.GitFailure(Path.cwd(),('merge-tree','--write-tree','b'*40,'c'*40),
            self.result('error: merge failed\nAuthorization: Bearer '+secret+'\n'+url+'\nerror: '+str(Path.cwd()/'private.dat')))
        output=json.dumps(error.detail)
        self.assertNotIn(secret,output);self.assertNotIn(str(Path.cwd()),output)
        self.assertNotIn(url,output)
        self.assertIn('merge failed',output)

    def test_network_helper_output_withheld(self):
        secret='fixture-only-auth-output'
        url='https://example.invalid/repo'
        error=sync_git.GitFailure(Path.cwd(),('fetch',url,secret),self.result(secret))
        self.assertNotIn(secret,json.dumps(error.detail));self.assertNotIn(secret,str(error))
        self.assertNotIn(url,json.dumps(error.detail))

    def test_both_git_wrappers_preserve_failure_and_ready_projection(self):
        for function in (sync_git.git,sync_git._raw_git):
            with self.subTest(function=function.__name__),patch.object(sync_git.subprocess,'run',return_value=self.result('fatal: synthetic conflict')):
                with self.assertRaises(sync_git.GitFailure) as raised:function(Path.cwd(),'merge-tree','--write-tree','d'*40,'e'*40)
                detail=sync._ready_check_failure(raised.exception,Path.cwd())
                self.assertEqual(detail['git_failure']['operation'],'merge-tree')
                self.assertIn('synthetic conflict',detail['git_failure']['stderr'])

    def test_empty_object_merge_output_is_rejected(self):
        with patch.object(sync_git,'git',return_value=''):
            with self.assertRaisesRegex(sync_git.SyncBlocked,'no tree'):
                sync_git.raw_composition(Path('synthetic'),'a'*40,'b'*40,'c'*40,[])

    def test_merge_base_identity_survives_without_unchecked_arguments(self):
        error=sync_git.GitFailure(Path.cwd(),('merge-tree','--write-tree','--merge-base='+'a'*40,
            'b'*40,'c'*40,'unchecked-private-argument'),self.result('fatal: synthetic conflict'))
        self.assertIn('--merge-base='+'a'*40,error.detail['command'])
        self.assertEqual(set(error.detail['commit_ids']),{'a'*40,'b'*40,'c'*40})
        self.assertNotIn('unchecked-private-argument',json.dumps(error.detail))

    def test_merge_failure_rollback_never_resets_or_overwrites_unplanned_files(self):
        journal={};saved=[]
        failure=sync_git.GitFailure(Path('synthetic'),('merge-tree','--write-tree','a'*40,'b'*40),self.result('fatal: synthetic merge failure'))
        def git(repo,*args,**kwargs):return 'a'*40 if args[:1]==('rev-parse',) else ''
        with patch.object(sync_git,'git',side_effect=git) as calls, \
                patch.object(sync_git,'changed',return_value=set()), \
                patch.object(sync_git,'raw_composition',side_effect=failure), \
                patch.object(sync_git,'identities',return_value={}) as identities:
            with self.assertRaises(sync_git.GitFailure):
                sync._stage_raw_composition(Path('synthetic'),'a'*40,
                    {'ready':'b'*40,'source_base':'c'*40,'paths':[]},journal,lambda:saved.append(copy.deepcopy(journal)))
            self.assertEqual(journal['composition_mode'],'raw-tree')
            self.assertEqual(journal['composition_files'],{})
            self.assertEqual(saved,[])
            sync._abort_composition(Path('synthetic'),'a'*40,journal)
            self.assertFalse(any('reset' in call.args or 'cherry-pick' in call.args for call in calls.call_args_list))


class MaskedGitFailure(unittest.TestCase):
    def primary(self):
        return sync_git.GitFailure(Path.cwd(),('read-tree','a'*40),
            SimpleNamespace(returncode=128,stdout='',stderr='fatal: synthetic index.lock access failure'))

    def wrapped(self):
        cleanup=PermissionError('synthetic cleanup denied at '+str(Path.cwd()/'fixture-index'))
        cleanup.__context__=self.primary()
        return cleanup

    def test_cleanup_context_keeps_safe_primary_and_separate_outer_failure(self):
        projected=sync._ready_check_failure(self.wrapped(),Path.cwd())
        self.assertEqual(projected['git_failure']['operation'],'read-tree')
        self.assertEqual(projected['git_failure']['exit_code'],128)
        self.assertIn('index.lock',projected['git_failure']['stderr'])
        self.assertEqual(projected['outer_failure']['type'],'PermissionError')
        self.assertNotIn(str(Path.cwd()),projected['outer_failure']['diagnostic'])

    def test_explicit_cause_keeps_primary(self):
        outer=RuntimeError('synthetic cleanup failed');outer.__cause__=self.primary()
        self.assertEqual(sync._ready_check_failure(outer,Path.cwd())['git_failure']['operation'],'read-tree')

    def test_context_found_even_with_unrelated_explicit_cause(self):
        outer=self.wrapped();outer.__cause__=RuntimeError('fixture-only-private-chain-text')
        projected=sync._ready_check_failure(outer,Path.cwd())
        self.assertIn('git_failure',projected)
        self.assertNotIn('fixture-only-private-chain-text',json.dumps(projected))

    def test_cycle_without_known_failure_stops_without_dumping_chain(self):
        outer=RuntimeError('outer');inner=RuntimeError('private nested text')
        outer.__context__=inner;inner.__context__=outer
        self.assertEqual(sync._ready_check_failure(outer,Path.cwd()),{})

    def test_deep_chain_is_bounded_and_raw_nested_text_is_not_emitted(self):
        outer=RuntimeError('outer');current=outer
        for _ in range(12):
            nested=RuntimeError('fixture-only-private-chain-text');current.__context__=nested;current=nested
        current.__context__=self.primary()
        projected=sync._ready_check_failure(outer,Path.cwd())
        self.assertEqual(projected,{'failure_context_limit_reached':True})
        self.assertNotIn('fixture-only-private-chain-text',json.dumps(projected))

    def test_ready_plan_retains_primary_but_stays_review_required(self):
        with patch.object(sync,'_qualify',side_effect=self.wrapped()):
            result=sync.ready_plan(Path.cwd(),'a'*40)
        self.assertEqual(result['result'],'review-required')
        self.assertEqual(result['git_failure']['operation'],'read-tree')
        self.assertEqual(result['outer_failure']['type'],'PermissionError')
        self.assertNotIn(str(Path.cwd()),result['reason'])

    def test_ready_sync_retains_primary_before_any_mutation(self):
        with patch.object(sync,'_primary',return_value=(Path.cwd(),Path.cwd())), \
                patch.object(sync_git,'git',return_value='a'*40), \
                patch.object(sync,'_read',return_value=None), \
                patch.object(sync,'_ready_receipt',side_effect=self.wrapped()), \
                patch.object(sync,'_begin_published_successor') as begin:
            result=sync.ready_sync(Path.cwd(),'a'*40)
        self.assertEqual(result['result'],'incomplete')
        self.assertEqual(result['git_failure']['operation'],'read-tree')
        self.assertNotIn(str(Path.cwd()),result['reason'])
        begin.assert_not_called()


if __name__=='__main__':unittest.main()
