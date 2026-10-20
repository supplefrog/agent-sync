"""Rollout acceptance uses real files and local Git, never a model."""
from fixture_workspace import configure, provided_workspace
configure()
from pathlib import Path
import json,sys,tempfile,unittest
import io,base64
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import worktree_sync as rollout
import reconcile
import fleet
import install
import test_reconcile as fixtures
import test_sync_completion as completion
import test_worktree_sync as ready_fixtures


class TargetRolloutTests(unittest.TestCase):
    def setUp(self):
        self.tmp=self.enterContext(tempfile.TemporaryDirectory());self.base=Path(self.tmp)
        self.repo=self.base/'repo';self.roots=[self.base/'a',self.base/'b']
        fixtures.write_skill(self.repo,'kept','old body')
        self.put('registry.json',{'schema_version':1,'skills':[{'name':'kept','status':'admitted'}]})
        self.config={'schema_version':1,'snapshot_root':'render/fleet','machines':{
            str(i):{'skill_roots':[str(root)],'hosts':['fixture-native']} for i,root in enumerate(self.roots)}}
        self.put('fleet.json',self.config)
        self.snapshot=self.repo/'render/fleet';fleet.render_snapshot(self.repo,self.snapshot)
        for root in self.roots:fleet.apply_snapshot(self.snapshot,root)
        fixtures.write_skill(self.repo,'kept','new body');fleet.render_snapshot(self.repo,self.snapshot)
        self.journal={'attempt':'fixture-attempt','last_result':{'commit':'fixture-commit'}}
        self.saved=[]
        common=patch.object(rollout.sync_git,'common_dir',return_value=self.base/'common')
        common.start();self.addCleanup(common.stop)

    def put(self,name,value):
        p=self.repo/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(value))

    def save(self):self.saved.append(json.loads(json.dumps(self.journal)))

    def native(self,host,root,required,retired):
        return {'verified':all((root/n/'SKILL.md').is_file() for n in required) and all(not (root/n).exists() for n in retired)}

    def run_rollout(self,native=None):
        return rollout._rollout_targets(self.repo,self.journal,self.save,verify_native=native or self.native)

    def test_all_configured_roots_and_native_views_are_verified(self):
        self.assertTrue(self.run_rollout())
        for root in self.roots:
            self.assertEqual(fleet.verify_snapshot(self.snapshot,root),[])
            self.assertTrue(self.journal['rollout']['targets'][str(root)]['native']['fixture-native']['verified'])

    def test_unavailable_target_does_not_hide_other_success_and_resume_is_idempotent(self):
        apply=fleet.apply_snapshot
        def unavailable(snapshot,root,**options):
            if root==self.roots[0]:raise OSError('fixture target disconnected')
            return apply(snapshot,root,**options)
        with patch.object(fleet,'apply_snapshot',side_effect=unavailable):self.assertFalse(self.run_rollout())
        self.assertIn('new body',(self.roots[1]/'kept/SKILL.md').read_text())
        self.assertIn('old body',(self.roots[0]/'kept/SKILL.md').read_text())
        with patch.object(fleet,'apply_snapshot',wraps=apply) as resumed:
            self.assertTrue(self.run_rollout());self.assertEqual(resumed.call_count,1)
            self.assertEqual(resumed.call_args.args[1],self.roots[0])

    def test_user_drift_is_preserved_while_independent_target_finishes(self):
        changed=self.roots[0]/'kept/SKILL.md';changed.write_text('user edit')
        self.assertFalse(self.run_rollout());self.assertEqual(changed.read_text(),'user edit')
        self.assertTrue(self.journal['rollout']['targets'][str(self.roots[1])]['verified'])

    def test_catalogue_failure_is_partial_and_retry_does_not_reapply_installed_bytes(self):
        self.assertFalse(self.run_rollout(lambda host,root,*args:{'verified':root==self.roots[1]}))
        with patch.object(fleet,'apply_snapshot',side_effect=AssertionError('must not reapply successful copy')):
            self.assertTrue(self.run_rollout())

    def test_native_read_cannot_hide_a_concurrent_installed_change(self):
        def drift(host,root,*args):
            if root==self.roots[0]:(root/'kept/SKILL.md').write_text('concurrent writer')
            return {'verified':True}
        self.assertFalse(self.run_rollout(drift))
        self.assertFalse(self.journal['rollout']['targets'][str(self.roots[0])]['verified'])

    def test_retired_bytes_remain_recoverable_and_executable_support_stays(self):
        fixtures.write_skill(self.repo,'retired','optional prose')
        registry={'schema_version':1,'skills':[{'name':'kept','status':'admitted'},{'name':'retired','status':'admitted'}]}
        self.put('registry.json',registry);fleet.render_snapshot(self.repo,self.snapshot)
        for root in self.roots:fleet.apply_snapshot(self.snapshot,root)
        registry['skills'][1]['status']='retired';self.put('registry.json',registry)
        fleet.render_snapshot(self.repo,self.snapshot)
        self.assertTrue(self.run_rollout())
        for root in self.roots:
            state=self.journal['rollout']['targets'][str(root)]
            self.assertFalse((root/'retired').exists())
            self.assertIn('optional prose',(Path(state['backup'])/'retired/SKILL.md').read_text())
            self.assertTrue((root/'kept/SKILL.md').is_file())
        self.assertTrue((self.repo/'skills/retired/SKILL.md').is_file())

    def test_changed_source_cannot_resume_under_old_receipt(self):
        self.assertTrue(self.run_rollout())
        fixtures.write_skill(self.repo,'kept','different release');fleet.render_snapshot(self.repo,self.snapshot)
        with self.assertRaises(rollout.sync_git.SyncBlocked):self.run_rollout()

    def test_no_targets_is_not_vacuous_completion(self):
        self.config['machines']={};self.put('fleet.json',self.config)
        self.assertFalse(self.run_rollout())

    def test_empty_native_host_selection_cannot_complete(self):
        self.config['machines']['0']['hosts']=[];self.put('fleet.json',self.config)
        self.assertFalse(self.run_rollout())
        self.assertFalse(self.journal['rollout']['targets'][str(self.roots[0])]['verified'])

    def test_already_retired_skill_is_checked_on_later_rollouts(self):
        fixtures.write_skill(self.repo,'retired','preserved source')
        self.put('registry.json',{'schema_version':1,'skills':[{'name':'kept','status':'admitted'},{'name':'retired','status':'retired'}]})
        fleet.render_snapshot(self.repo,self.snapshot)
        def native(host,root,required,retired):
            self.assertIn('retired',retired)
            return {'verified':False,'retired_offered':['retired']}
        self.assertFalse(self.run_rollout(native))

    def test_remote_machine_is_not_verified_through_local_native_processes(self):
        self.journal['receipt']={'options':{'machine':'0'}}
        self.config['machines']['0']['platform']='windows';self.config['machines']['1']['platform']='linux'
        self.put('fleet.json',self.config)
        self.assertFalse(self.run_rollout())
        self.assertTrue(self.journal['rollout']['targets'][str(self.roots[0])]['verified'])
        self.assertIn('transport unavailable',self.journal['rollout']['targets'][str(self.roots[1])]['reason'])


class CompletionRoutingTests(unittest.TestCase):
    def test_source_publication_alone_cannot_report_synced(self):
        with patch.object(reconcile,'_complete_source_sync',return_value={'result':'synced','commit':'fixture'}), \
             patch.object(rollout,'rollout_published',return_value={'result':'incomplete','rollout_verified':False}) as deployment:
            result=reconcile.complete_sync(Path.cwd(),include=['notes.md'],capture_recovery=False)
        self.assertEqual(result['result'],'incomplete');deployment.assert_called_once()

    def test_source_only_is_explicit_and_does_not_claim_installed_verification(self):
        with patch.object(reconcile,'_complete_source_sync',return_value={'result':'synced','commit':'fixture'}), \
             patch.object(rollout,'rollout_published',side_effect=AssertionError('source-only must not deploy')):
            result=reconcile.complete_sync(Path.cwd(),source_only=True,include=['notes.md'])
        self.assertEqual(result['result'],'published');self.assertFalse(result['installed_verified'])

    def test_source_only_rejects_native_selectors(self):
        with patch.object(reconcile,'_complete_source_sync',side_effect=AssertionError('must not begin native operation')):
            result=reconcile.complete_sync(Path.cwd(),source_only=True,adopt=['kept'])
        self.assertEqual(result['result'],'review-required')


class ReadyRolloutRegressionTests(unittest.TestCase):
    setUp=completion.CompleteSyncTests.setUp
    fixture=completion.CompleteSyncTests.fixture
    git=completion.CompleteSyncTests.git
    setup_git=completion.CompleteSyncTests.setup_git
    worker=ready_fixtures.WorktreeSyncTests.worker
    commit=ready_fixtures.WorktreeSyncTests.commit

    def test_include_only_source_update_repairs_the_stale_installed_target(self):
        adapter=fixtures.load_tool('worktree_sync')
        with provided_workspace() as temporary:
            repo,live,remote=self.setup_git(Path(temporary))
            name='skills/kept/fixture.txt';(repo/name).write_text('old')
            self.fleet.render_snapshot(repo,repo/'render/fleet');self.fleet.apply_snapshot(repo/'render/fleet',live)
            self.git(repo,'add',name);self.git(repo,'commit','-m','baseline asset');self.git(repo,'push','origin','main')
            worker=self.worker(repo,'worker');ready=self.commit(worker,name,'new')
            with patch.object(adapter.reconcile,'_run_checks',return_value=['fixture checks']):
                result=adapter.ready_sync(worker,ready,machine='test',skill_roots=[live],include=[name])
            self.assertEqual(result['result'],'synced',result)
            self.assertEqual((live/'kept/fixture.txt').read_text(),'new')
            self.assertTrue(result['rollout_verified'])

    def test_deliberate_source_only_is_labeled_and_can_resume_installed_rollout(self):
        adapter=fixtures.load_tool('worktree_sync')
        with provided_workspace() as temporary:
            repo,live,remote=self.setup_git(Path(temporary))
            name='skills/kept/fixture.txt';(repo/name).write_text('old')
            self.fleet.render_snapshot(repo,repo/'render/fleet');self.fleet.apply_snapshot(repo/'render/fleet',live)
            self.git(repo,'add',name);self.git(repo,'commit','-m','baseline asset');self.git(repo,'push','origin','main')
            worker=self.worker(repo,'worker');ready=self.commit(worker,name,'new')
            with patch.object(adapter.reconcile,'_run_checks',return_value=['fixture checks']):
                result=adapter.ready_sync(worker,ready,machine='test',skill_roots=[live],include=[name],source_only=True)
            self.assertEqual(result['result'],'published',result)
            self.assertEqual((live/'kept/fixture.txt').read_text(),'old')
            self.assertFalse(result['rollout_verified'])
            self.assertFalse((repo/'.git/agent-signal-integration.json').exists())
            resumed=adapter.rollout_published(worker,result['commit'],machine='test')
            self.assertEqual(resumed['result'],'synced',resumed)
            self.assertEqual((live/'kept/fixture.txt').read_text(),'new')


class PublishedRepeatTests(unittest.TestCase):
    setUp=completion.CompleteSyncTests.setUp
    fixture=completion.CompleteSyncTests.fixture
    git=completion.CompleteSyncTests.git
    setup_git=completion.CompleteSyncTests.setup_git
    run_sync=completion.CompleteSyncTests.run_sync

    def test_published_provenance_is_recognized_only_without_source_or_target_drift(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo,live,remote=self.setup_git(Path(temporary))
            target=live/'kept/fixture.txt';target.write_text('authorized adopted value')
            first=self.run_sync(repo,live)
            self.assertEqual('synced',first['result'],first)
            commit=self.git(repo,'rev-parse','HEAD')
            self.assertEqual(commit,rollout.unchanged_published(repo,machine='test',skill_roots=[live]))
            repeated=self.run_sync(repo,live)
            self.assertEqual('synced',repeated['result'],repeated)
            self.assertEqual(commit,self.git(remote,'rev-parse','main'))
            source=repo/'skills/kept/fixture.txt';before=source.read_bytes()
            source.write_bytes(before+b'unreviewed source')
            self.assertIsNone(rollout.unchanged_published(repo,machine='test',skill_roots=[live]))
            source.write_bytes(before)
            target.write_bytes(before+b'unreviewed target')
            self.assertIsNone(rollout.unchanged_published(repo,machine='test',skill_roots=[live]))
            target.write_bytes(before)
            state_path=live/fleet.STATE_FILE;state_raw=state_path.read_bytes();state=json.loads(state_raw)
            state['manifest_sha256']='0'*64;state_path.write_text(json.dumps(state))
            self.assertIsNone(rollout.unchanged_published(repo,machine='test',skill_roots=[live]))
            state_path.write_bytes(state_raw);state=json.loads(state_raw)
            state['source_snapshot']=str(repo/'unowned/render/fleet');state_path.write_text(json.dumps(state))
            rejected=self.run_sync(repo,live)
            self.assertEqual('review-required',rejected['result'],rejected)
            self.assertEqual(state['source_snapshot'],json.loads(state_path.read_bytes())['source_snapshot'])
            state_path.write_bytes(state_raw)
            common=rollout.sync_git.common_dir(repo);marker_path=common/'agent-signal-published.json'
            marker=json.loads(marker_path.read_bytes());marker['head']='0'*40;marker_path.write_text(json.dumps(marker))
            self.assertIsNone(rollout.unchanged_published(repo,machine='test',skill_roots=[live]))

    def test_same_command_resumes_offline_target_and_preserves_real_drift(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo,live,remote=self.setup_git(Path(temporary));second=Path(temporary)/'second'
            config=json.loads((repo/'fleet.json').read_bytes())
            config['machines']['test']['skill_roots'].append(str(second))
            (repo/'fleet.json').write_text(json.dumps(config))
            self.fleet.render_snapshot(repo,repo/'render/fleet');self.fleet.apply_snapshot(repo/'render/fleet',second)
            self.git(repo,'add','fleet.json');self.git(repo,'commit','-m','second configured fixture root')
            self.git(repo,'push','origin','main')
            name='skills/kept/fixture.txt';(repo/name).write_text('new published package')
            apply=rollout.reconcile.fleet.apply_snapshot
            def offline(snapshot,root,**options):
                if root==second:raise OSError('fixture disconnected')
                return apply(snapshot,root,**options)
            with patch.object(rollout.reconcile.fleet,'apply_snapshot',side_effect=offline):
                first=self.run_sync(repo,live,include=[name])
            self.assertEqual('incomplete',first['result'],first)
            self.assertTrue(first['publication_verified']);self.assertFalse(first['rollout_verified'])
            commit=self.git(remote,'rev-parse','main')
            self.assertEqual('new published package',(live/'kept/fixture.txt').read_text())
            self.assertNotEqual('new published package',(second/'kept/fixture.txt').read_text())
            different=self.run_sync(repo,live,include=['registry.json'])
            self.assertNotEqual('synced',different['result'],different)
            self.assertEqual(commit,self.git(remote,'rev-parse','main'))
            target=live/'kept/fixture.txt';known=target.read_bytes();target.write_bytes(known+b'user drift')
            partial=self.run_sync(repo,live,include=[name])
            self.assertEqual('incomplete',partial['result'],partial)
            self.assertTrue(target.read_bytes().endswith(b'user drift'))
            self.assertEqual('new published package',(second/'kept/fixture.txt').read_text())
            target.write_bytes(known)
            with patch.object(rollout.reconcile.fleet,'apply_snapshot',wraps=apply) as applied:
                recovered=self.run_sync(repo,live,include=[name])
            self.assertEqual('synced',recovered['result'],recovered)
            self.assertEqual(0,applied.call_count)
            self.assertEqual(commit,self.git(remote,'rev-parse','main'))
            self.assertFalse((rollout.sync_git.common_dir(repo)/'agent-signal-integration.json').exists())


class NativeReadbackTests(unittest.TestCase):
    def setUp(self):
        self.root=Path(self.enterContext(tempfile.TemporaryDirectory()))
        (self.root/'kept').mkdir();self.body=b'---\nname: kept\n---\nFull exact body, not one matching line.\n'
        (self.root/'kept/SKILL.md').write_bytes(self.body)

    def process(self,body=None,path=None,interactive=False):
        class Input(io.StringIO):
            def close(self):self.written=self.getvalue();super().close()
        rows=[{'id':1,'result':{}},{'id':2,'result':{'data':[{'skills':[{'name':'kept','path':str(path or self.root/'kept/SKILL.md'),'enabled':True}]}]}},
              {'id':3,'result':{'dataBase64':base64.b64encode(self.body if body is None else body).decode()}}]
        if interactive:rows[0]={'id':100,'method':'requestApproval','params':{}}
        return SimpleNamespace(stdin=Input(),stdout=io.StringIO(''.join(json.dumps(x)+'\n' for x in rows)),
                               stderr=io.StringIO(''),wait=lambda **kw:0,terminate=lambda:None)

    def test_codex_reads_catalog_and_exact_bytes_without_threads_or_turns(self):
        process=self.process()
        with patch.object(install.subprocess,'Popen',return_value=process):
            value=install._codex_fleet_readback('native-fixture',self.root,['kept'])
        self.assertTrue(value['body_reads']['kept']);self.assertFalse(value['thread_created'])
        requests=[json.loads(x) for x in process.stdin.written.splitlines()]
        self.assertEqual([x['method'] for x in requests],['initialize','initialized','skills/list','fs/readFile'])
        self.assertTrue(requests[2]['params']['forceReload'])

    def test_wrong_source_or_different_bytes_cannot_pass_native_readback(self):
        for process in (self.process(body=b'Full exact body, not one matching line.'),self.process(path=self.root/'other/SKILL.md')):
            with patch.object(install.subprocess,'Popen',return_value=process):
                self.assertFalse(install._codex_fleet_readback('native-fixture',self.root,['kept'])['body_reads']['kept'])

    def test_interactive_request_is_not_automatically_approved(self):
        with patch.object(install.subprocess,'Popen',return_value=self.process(interactive=True)):
            with self.assertRaises(RuntimeError):install._codex_fleet_readback('native-fixture',self.root,['kept'])

    def test_native_retired_offer_prevents_completion(self):
        with patch.object(install.shutil,'which',return_value='native-fixture'),patch.object(install,'_codex_fleet_readback',return_value={
            'names':['kept','retired'],'body_reads':{'kept':True},'catalog_sha256':'0'*64,'thread_created':False}):
            value=install.verify_fleet_discovery('codex',self.root,['kept'],['retired'])
        self.assertFalse(value['verified']);self.assertEqual(value['retired_offered'],['retired'])


if __name__=='__main__':unittest.main()
