"""Pure decision and integration-call controls; no fixtures, native writes or network."""
import importlib.util
import json
import copy
from pathlib import Path
import sys
import unittest
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import patch, Mock

root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'tools'))
import worktree_sync as m


class ChangedSettingsTests(unittest.TestCase):
    def test_only_changed_values_and_types_matter(self):
        old={'compression':{'native':True},'unrelated':1}
        new={'compression':{'native':False},'unrelated':1}
        self.assertTrue(m._changed_config_matches(old,new,{'compression':{'native':False},'unrelated':'user change'}))
        self.assertFalse(m._changed_config_matches(old,new,{'compression':{'native':True}}))
        self.assertFalse(m._changed_config_matches(old,new,{'compression':{'native':0}}))

    def test_missing_new_and_deleted_settings(self):
        self.assertFalse(m._changed_config_matches({}, {'tools':{'enabled':True}},{}))
        self.assertTrue(m._changed_config_matches({}, {'tools':{'enabled':True}}, {'tools':{'enabled':True,'unrelated':3}}))
        self.assertTrue(m._changed_config_matches({'removed':1},{},{}))
        self.assertFalse(m._changed_config_matches({'removed':1},{},{'removed':1}))

    def test_plugin_delta_does_not_replay_unrelated_arrays(self):
        old={'plugins':{'enabled':['keep','lcm'],'disabled':['old']}}
        new={'plugins':{'enabled':['keep'],'disabled':['old','lcm']}}
        self.assertTrue(m._changed_config_matches(old,new,{'plugins':{'enabled':['personal'],'disabled':['lcm','other']}}))
        self.assertFalse(m._changed_config_matches(old,new,{'plugins':{'enabled':['lcm'],'disabled':['lcm']}}))
        self.assertFalse(m._changed_config_matches(old,new,{'plugins':{'enabled':[],'disabled':[]}}))


class NativeReadbackTests(unittest.TestCase):
    def fixture(self):
        name='recovery/current/hosts/hermes/config.json'
        journal={'published_repo':'managed-published-source','last_result':{'commit':'revision'},'receipt':{'options':{'recovery_roots':{'hermes':'configured-root'}}}}
        artifact={'snapshot':'hosts/hermes/config.json','source':'config.yaml','kind':'config','format':'yaml'}
        recovery=SimpleNamespace(_load_policy=Mock(return_value={}),verify_snapshot=Mock(return_value={}),
            _policy_artifacts=Mock(return_value=[('hermes',artifact)]),
            _selected_roots=Mock(return_value=(('hermes',),{'hermes':Path('configured-root')})),
            _safe_join=Mock(return_value=Path('configured-root/config.yaml')),
            _file_identity=Mock(return_value='same'),_target_home=Mock(return_value=Path('configured-home')),_expand=lambda v,*a,**k:v,
            _read_config=Mock(return_value={'mode':'new','personal':True}))
        def git(*args):
            return json.dumps({'mode':'old' if '^:' in args[-1] else 'new'})
        return name,journal,recovery,git

    def read(self,journal,recovery,git,names):
        with patch.object(m,'_names',return_value=names),patch.object(m.sync_git,'git',side_effect=git):
            return m._native_destination_completion(Path('source'),journal,recovery_module=recovery)

    def test_saved_verified_does_not_claim_loaded(self):
        name,j,r,g=self.fixture();result=self.read(j,r,g,[name])
        self.assertTrue(result['saved_verified']);self.assertIsNone(result['loaded_verified'])
        r.verify_snapshot.assert_called_once();r._read_config.assert_called_once()

    def test_stale_and_offline_targets_stay_pending_then_resume(self):
        name,j,r,g=self.fixture();r._read_config.return_value={'mode':'old'}
        self.assertFalse(self.read(j,r,g,[name])['saved_verified'])
        r._read_config.side_effect=OSError('offline')
        result=self.read(j,r,g,[name]);self.assertFalse(result['saved_verified'])
        self.assertIn('offline',result['targets'][name]['reason'])
        r._read_config.side_effect=None;r._read_config.return_value={'mode':'new'}
        self.assertTrue(self.read(j,r,g,[name])['saved_verified'])
        self.assertTrue(self.read(j,r,g,[name])['saved_verified'])

    def test_missing_roots_changed_during_read_and_unknown_artifact(self):
        name,j,r,g=self.fixture();r._selected_roots.side_effect=KeyError('missing root')
        self.assertFalse(self.read(j,r,g,[name])['saved_verified'])
        r._selected_roots.side_effect=None;r._file_identity.side_effect=['before','after']
        self.assertFalse(self.read(j,r,g,[name])['saved_verified'])
        self.assertFalse(self.read(j,r,g,['recovery/current/not-in-policy'])['saved_verified'])

    def test_no_snapshot_change_is_not_a_native_configuration_claim(self):
        name,j,r,g=self.fixture();result=self.read(j,r,g,[])
        self.assertTrue(result['saved_verified']);self.assertEqual({},result['targets'])
        r._load_policy.assert_not_called()


class CompletionBoundaryTests(unittest.TestCase):
    def test_resume_preserves_explicit_roots_and_only_uses_supported_defaults(self):
        import recovery
        for request,expected in [(None,{'hermes':'default-root'}),
            ({'default_recovery_roots':True},{'hermes':'default-root'}),
            ({'default_recovery_roots':False,'recovery_roots':{}},{}),
            ({'default_recovery_roots':False,'recovery_roots':{'hermes':'selected-root'}},{'hermes':'selected-root'})]:
            with self.subTest(request=request):
                def git(*args):
                    return 'revision refs/heads/main' if args[1]=='ls-remote' else 'revision'
                with patch.object(m,'_primary',return_value=(Path('repo'),Path('common'))), \
                     patch.object(m.sync_git,'lock',return_value=nullcontext()), \
                     patch.object(m.sync_git,'destination',return_value={'remote':'origin','ref':'refs/heads/main','branch':'main'}), \
                     patch.object(m.sync_git,'git',side_effect=git),patch.object(m,'_read',return_value=None), \
                     patch.object(m,'_owned_worktree',return_value=(Path('lane'),Path('marker'),{'head':'revision'})), \
                     patch.object(m.sync_git,'read_pending',return_value=None),patch.object(m.sync_git,'changed',return_value=False), \
                     patch.object(m,'_checkout_git'),patch.object(m,'_atomic'), \
                     patch.object(recovery,'_default_roots',return_value={'hermes':'default-root'}), \
                     patch.object(m,'_finish_published',return_value={'result':'incomplete'}) as finish:
                    result=m.rollout_published(Path('repo'),'revision',request=request)
                self.assertIsNotNone(finish.call_args,result)
                self.assertEqual({k:str(Path(v).resolve()) for k,v in expected.items()},finish.call_args.args[7]['receipt']['options']['recovery_roots'])

    def finish(self,native,source_only=False):
        j={'attempt':'test','last_result':{'commit':'revision','result':'published'},'source_backup':'retained',
           'origin_destinations':[],'receipt':{'options':{'adopt':[]}}}
        def git(*args):
            if args[1]=='ls-remote':return 'revision refs/heads/main'
            return 'revision'
        def roots(*args):j['rollout']={'targets':{'skills':{'verified':True}}};return True
        with patch.object(m.sync_git,'assert_integration_owner'),patch.object(m.sync_git,'read_pending',return_value=None), \
             patch.object(m.sync_git,'git',side_effect=git),patch.object(m.sync_git,'changed',return_value=False), \
             patch.object(m,'_atomic') as save,patch.object(m,'_checkout_git'), \
             patch.object(m.sync_git,'_tree_entries',return_value={}),patch.object(m.sync_git,'_blobs',return_value={}), \
             patch.object(m.reconcile,'_snapshot',return_value=Path('snapshot')),patch.object(m.reconcile.fleet,'render_snapshot'), \
             patch.object(m,'_rollout_targets',side_effect=roots), \
             patch.object(m,'_native_destination_completion',return_value=native,create=True) as check, \
             patch.object(Path,'unlink'):
            result=m._finish_published(Path('repo'),Path('common'),{'remote':'origin','ref':'refs/heads/main'},
                        Path('lane'),Path('published'),Path('marker'),{'head':'revision'},j,source_only=source_only)
        return result,j,check,save

    def test_skills_verified_cannot_hide_stale_settings(self):
        result,j,check,save=self.finish({'saved_verified':False,'targets':{'settings':{'verified':False}}})
        self.assertEqual('incomplete',result['result']);self.assertFalse(result['sync_complete'])
        self.assertEqual('native-saved-verification',result['failed_step'])
        self.assertIn('native_destinations',j);check.assert_called_once()

    def test_all_saved_destinations_complete_without_restart_claim(self):
        result,j,check,save=self.finish({'saved_verified':True,'targets':{'settings':{'verified':True}}})
        self.assertEqual('synced',result['result']);self.assertTrue(result['sync_complete'])
        self.assertIsNone(result['activation_verified'])

    def test_source_only_is_not_all_destination_completion(self):
        result,j,check,save=self.finish({},source_only=True)
        self.assertEqual('published',result['result']);self.assertFalse(result['sync_complete'])
        self.assertIn('resumption_event',result);check.assert_not_called()


class ReviewRegressionTests(unittest.TestCase):
    def test_s1_type_changes_at_every_container_depth(self):
        for before,desired,current in [({'cap':True},{'cap':1},{'cap':True}),
            ({'cap':False},{'cap':0},{'cap':False}),
            ({'nested':{'cap':True}},{'nested':{'cap':1}},{'nested':{'cap':True}}),
            ({'nested':[{'cap':False}]},{'nested':[{'cap':0}]},{'nested':[{'cap':False}]})]:
            with self.subTest(desired=desired):
                self.assertFalse(m._changed_config_matches(before,desired,current))
                self.assertTrue(m._changed_config_matches(before,desired,desired))
        self.assertTrue(m._changed_config_matches({'same':True,'cap':0},{'same':True,'cap':1},
                                                {'same':'unrelated user change','cap':1}))

    def test_s1_exact_native_readback_reaches_incomplete_finish(self):
        helper=NativeReadbackTests();name,j,r,g=helper.fixture()
        r._read_config.return_value={'cap':True}
        def wire(*args):return json.dumps({'cap':True if '^:' in args[-1] else 1})
        native=helper.read(j,r,wire,[name])
        self.assertFalse(native['saved_verified'])
        result,_,_,_=CompletionBoundaryTests().finish(native)
        self.assertEqual('incomplete',result['result']);self.assertFalse(result['sync_complete'])

    def test_s2_real_home_expansion_and_stable_source_anchor(self):
        import recovery
        helper=NativeReadbackTests()
        for target in [Path.cwd()/'synthetic-never-created/AppData/Local/hermes',
                       Path.cwd()/'synthetic-never-created/.hermes']:
            with self.subTest(target=str(target)):
                name,j,r,g=helper.fixture();roots={'hermes':target}
                r._selected_roots.return_value=(('hermes',),roots)
                r._target_home=recovery._target_home;r._expand=recovery._expand
                home=recovery._target_home(roots,['hermes'])
                marker=recovery._PORTABLE_PLACEHOLDERS
                before={'path':'old','origin':'old'}
                desired={'path':marker['HOME']+'/.agents/skills',
                         'origin':marker['AGENT_SIGNAL_ROOT']+'/render/fleet'}
                expected=recovery._expand(desired,roots,Path(j['published_repo']),home=home)
                r._read_config.return_value=expected
                def wire(*args):return json.dumps(before if '^:' in args[-1] else desired)
                self.assertTrue(helper.read(j,r,wire,[name])['saved_verified'])
                wrong=recovery._expand(desired,roots,Path('temporary-integration-lane'))
                self.assertNotEqual(expected,wrong)
                r._read_config.return_value=wrong
                self.assertFalse(helper.read(j,r,wire,[name])['saved_verified'])

    def test_s3_new_membership_lists_preserve_personal_entries(self):
        for name in ['enabled','disabled']:
            with self.subTest(name=name):
                desired={'plugins':{name:['wanted']}}
                self.assertTrue(m._changed_config_matches({},desired,{'plugins':{name:['wanted','personal']}}))
                self.assertTrue(m._changed_config_matches({'plugins':{}},desired,{'plugins':{name:['personal','wanted']}}))
                self.assertFalse(m._changed_config_matches({},desired,{'plugins':{name:['personal']}}))
                self.assertFalse(m._changed_config_matches({'plugins':{name:None}},desired,{'plugins':{name:['wanted','personal']}}))
                self.assertFalse(m._changed_config_matches({},desired,{'plugins':{name:['wanted',True]}}))


class OwnerPreservationTests(unittest.TestCase):
    def test_unselected_unpublished_update_remove_or_repair_are_held(self):
        state={'source_snapshot':'published/render/fleet','skills':{'instruction-authoring':{'source_snapshot':'private-candidate/render/fleet'}}}
        for kind in ['update','remove','repair']:
            self.assertEqual(['instruction-authoring'],m._unpublished_owner_updates([{'name':'instruction-authoring','action':kind}],state,'published/render/fleet'))

    def test_common_public_origin_and_explicit_selection_remain_supported(self):
        action=[{'name':'owner','action':'update'}]
        state={'source_snapshot':'published/render/fleet','skills':{'owner':{}}}
        self.assertEqual([],m._unpublished_owner_updates(action,state,'published/render/fleet'))
        state['skills']['owner']['source_snapshot']='private/render/fleet'
        self.assertEqual([],m._unpublished_owner_updates(action,state,'published/render/fleet',['owner']))
        self.assertEqual([],m._unpublished_owner_updates([{'name':'owner','action':'unchanged'}],state,'published/render/fleet'))

    def test_real_rollout_stops_before_backup_apply_or_catalogue(self):
        fleet=m.reconcile.fleet;snapshot=Path('published/render/fleet');root=Path('native-root')
        journal={'attempt':'test','last_result':{'commit':'commit'},'receipt':{'options':{'adopt':[]}},
                 'rollout':{'commit':'commit','manifest_sha256':'digest','targets':{str(root):{'required':[],'retired':[],'hosts':['hermes']}}}}
        state={'source_snapshot':str(snapshot),'skills':{'instruction-authoring':{'source_snapshot':'private/render/fleet'}}}
        action=[{'name':'instruction-authoring','action':'update','current':'new','prior':'new','desired':'old'}]
        with patch.object(m.reconcile,'_snapshot',return_value=snapshot), \
             patch.object(fleet,'load_manifest',return_value={'skills':{'instruction-authoring':{'sha256':'old'}}}), \
             patch.object(fleet,'sha256_file',return_value='digest'), \
             patch.object(Path,'read_bytes',return_value=json.dumps({'skills':[]}).encode()), \
             patch.object(fleet,'load_fleet',return_value={'machines':{'local-windows':{'skill_roots':[str(root)],'hosts':['hermes']}}}), \
             patch.object(fleet,'resolve_template',return_value=root),patch.object(fleet,'_path_locks',return_value=nullcontext()), \
             patch.object(fleet,'plan_snapshot',return_value=action),patch.object(fleet,'load_state',return_value=state), \
             patch.object(m.sync_git,'common_dir',return_value=Path('common')), \
             patch.object(Path,'mkdir',side_effect=AssertionError('must not create backup for prohibited owner write')), \
             patch.object(fleet,'apply_snapshot',side_effect=AssertionError('must not replace unpublished owner')) as apply:
            native=Mock(side_effect=AssertionError('no catalogue call after blocked owner'))
            self.assertFalse(m._rollout_targets(Path('published'),journal,lambda:None,verify_native=native))
        apply.assert_not_called();native.assert_not_called()
        target=journal['rollout']['targets'][str(root)]
        self.assertEqual('blocked',target['phase']);self.assertFalse(target['verified'])
        self.assertIn('unpublished managed owners',target['reason'])


class InterruptedSourceEligibility(unittest.TestCase):
    def original(self):
        return {'schema_version':1,'phase':'reconciling','deployment_started':False,
                'receipt':{'options':{'adopt':[],'include':['tools/owner.py']}},
                'origin_destinations':[],'composition_files':{'tools/owner.py':'b'*64},'composed_tree':'a'*40}

    def test_only_frozen_include_only_pre_publisher_interruption_is_new_kind(self):
        j=self.original();self.assertEqual('interrupted-include-only',m._release_source_kind(j))
        j['last_result']=None;self.assertEqual('interrupted-include-only',m._release_source_kind(j))
        j['last_result']={'result':'review-required','reason':'selected owner missing, unadmitted, or conflicting'}
        self.assertEqual('owner-classification',m._release_source_kind(j))

    def test_deployment_results_missing_evidence_and_unrelated_selection_do_not_qualify(self):
        changes=[lambda j:j.update(deployment_started=True),lambda j:j.pop('deployment_started'),
                 lambda j:j.update(phase='published'),lambda j:j.update(last_result={'result':'published'}),
                 lambda j:j['receipt']['options'].update(adopt=['owner']),lambda j:j.update(origin_destinations=['other']),
                 lambda j:j.update(composition_files={}),lambda j:j.update(composed_tree=None),
                 lambda j:j['receipt']['options'].update(include=['other']),lambda j:j['receipt'].update(options=None)]
        for i,mutate in enumerate(changes):
            with self.subTest(case=i):
                j=self.original();mutate(j);self.assertNotEqual('interrupted-include-only',m._release_source_kind(j))


if __name__=='__main__':unittest.main()
