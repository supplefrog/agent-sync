"""Synthetic mechanism checks only; no model, auth or provider execution."""
from fixture_workspace import configure
configure()
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import evaluation_measurement as m
import evaluation_artifact_pilot as pilot
import evaluation_runtime as runtime
import evaluation_hermes_worker as hermes_worker
from evaluation_usage import NativeUsageObserver
from test_evaluation_evidence import make_evaluation
import test_evaluation_runtime as native_fixtures


class MeasurementTests(unittest.TestCase):
    fake_native = native_fixtures.EvaluationRuntimeTests.fake_native

    def test_supported_disposable_lsp_controls_prevent_automatic_installs(self):
        with mock.patch.dict(hermes_worker.os.environ,{'HERMES_DISABLE_LAZY_INSTALLS':'1'}),tempfile.TemporaryDirectory() as temp:
            hermes_worker.prepare_study_config(temp)
            config=json.loads((Path(temp)/'config.yaml').read_text())
            hermes_worker.verify_no_install_config(config)
            self.assertEqual(config,{'lsp':{'enabled':False,'install_strategy':'off'}})
            config['lsp']['enabled']=True
            with self.assertRaises(RuntimeError):hermes_worker.verify_no_install_config(config)

    def test_complete_retry_attempt_is_counted_and_development_requires_evidence(self):
        good=self.complete_record(45);retry=copy.deepcopy(good)
        retry['identity']['attempt']=0;retry['outcome']['execution_ok']=False
        after=self.complete_record(35)
        pair=m.compare_records([retry,good],[after])['pairs'][0]
        self.assertTrue(pair['conditional_efficiency_eligible'])
        self.assertEqual(pair['token_delta_after_minus_before']['total_tokens'],-55)
        support=copy.deepcopy(after);support['identity']['role']='coordinator'
        support['workflow_accounting']={'call_id':'study','cost_class':'development'}
        self.assertTrue(m.workflow_usage(after,[after,support])['gaps'])
        support['workflow_accounting']['exclusion_evidence_sha256']='7'*64
        self.assertEqual(m.workflow_usage(after,[after,support])['tokens']['total_tokens'],35)

    def test_recurring_support_is_added_once_to_matched_task_total(self):
        before=self.complete_record(45);after=self.complete_record(35)
        support=copy.deepcopy(after);support['identity'].update(arm='judge',role='judge-0')
        support['usage']['tokens']['total_tokens']=100
        checked=m.compare_records([before],[after,support,support])
        self.assertEqual(len(checked['pairs']),1)
        self.assertTrue(checked['pairs'][0]['conditional_efficiency_eligible'])
        self.assertEqual(checked['pairs'][0]['token_delta_after_minus_before']['total_tokens'],90)
        self.assertEqual(m.reliability_summary([after,support,support])['supporting_call_count'],1)
        self.assertEqual(m.workflow_usage(after,[after,support,support])['physical_attempt_count'],2)

    def test_recurring_coordinator_missing_usage_cannot_hide(self):
        good=self.complete_record();support=copy.deepcopy(good)
        support['identity']['role']='coordinator'
        support['usage']['tokens']['total_tokens']=None
        self.assertFalse(m.acceptance_readiness([good,support])['ready'])
        self.assertTrue(m.precise_usage_gaps(good,[good,support]))
        self.assertEqual(m.reliability_summary([good,support])['supporting_call_count'],1)

    def test_accounting_requires_declared_calls_and_proved_setup_exclusion(self):
        good=self.complete_record();good['workflow_accounting']={'call_id':'leaf','required_call_ids':['leaf','parent']}
        self.assertFalse(m.acceptance_readiness([good])['ready'])
        parent=copy.deepcopy(good);parent['identity']['role']='parent'
        parent['workflow_accounting']={'call_id':'parent','cost_class':'one-time-setup'}
        self.assertFalse(m.acceptance_readiness([good,parent])['ready'])
        parent['workflow_accounting'].update(exclusion_evidence_sha256='7'*64,reuse_evidence_sha256='8'*64)
        self.assertTrue(m.acceptance_readiness([good,parent])['ready'])
        parent['workflow_accounting']['cost_class']='recurring'
        parent['usage']['tokens']['total_tokens']=100
        total=m.workflow_usage(good,[good,parent,parent])
        self.assertEqual(total['tokens']['total_tokens'],145)
        conflict=copy.deepcopy(parent);conflict['usage']['tokens']['total_tokens']=101
        self.assertTrue(m.workflow_usage(good,[good,parent,conflict])['gaps'])

    def test_explicit_exposure_is_separate_and_catalog_tools_remain_matched(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);fixture=root/'fixture';fixture.mkdir();(fixture/'x.py').write_text('x=1')
            package=root/'skill';package.mkdir();skill=package/'SKILL.md';skill.write_text('---\nname: skill\ndescription: Debug\n---\nExisting frozen body')
            oracle=root/'oracle.py';oracle.write_text('pass')
            archive=root/'request-archive';archive.mkdir()
            spec={'purpose':'native-skill-study','agent':'hermes','provider':'openai-codex','model':'gpt-6.1-sol','reasoning':'medium',
                'instruction_exposure':'explicit-body','arms':[{'id':'base','instructions':None},{'id':'exposed','instructions':str(skill)}],
                'cases':[{'id':'task','prompt':'Repair the program','fixture':str(fixture)}],'workspace_root':str(root/'jobs'),
                'oracle':str(oracle),'request_recording_parent':str(archive),'max_workers':1,'max_iterations':24,'timeout':150,'quota_remaining':1}
            plan=pilot.prepare(spec,root/'out');pilot.validate_jobs(plan)
            base,treatment=plan['jobs']
            self.assertEqual(base['prompt'],'Repair the program')
            self.assertIn('Existing frozen body',treatment['prompt'])
            self.assertEqual(base['catalog'],treatment['catalog'])
            self.assertEqual(base['initial_tree'],treatment['initial_tree'])
            fake={'ok':True,'cleanup':{'state_removed':True,'errors':[]},'native_usage':{'lifecycle':{'exposure_events':[]}}}
            oracle_result=type('R',(),{'stdout':'{"passed":1,"failed":0,"failures":[]}','stderr':'','returncode':0})()
            with mock.patch.object(runtime,'run_native_skill_study',return_value=fake) as native, mock.patch.object(pilot.subprocess,'run',return_value=oracle_result):
                report=pilot.run(plan,root/'out')
            self.assertEqual(native.call_count,1)
            self.assertEqual(report['completed_trials'],1)
            self.assertFalse(report['results'][0]['exposure_setup_ok'])
            treatment['prompt']='tampered'
            with self.assertRaises(ValueError):pilot.validate_jobs(plan)

    def test_outbound_exposure_records_hashes_and_actual_schema_contract_only(self):
        observer=NativeUsageObserver();observer.body_probes=['KNOWN\nBODY']
        observer.callback('pre_api_request')(request_messages=[{'content':'KNOWN\nBODY'}],system_prompt='PRIVATE_CONTENT',
            request={'body':{'tools':[{'function':{'description':hermes_worker.TERMINAL_CONTRACT}}]}})
        seen=observer.snapshot()['exposure_events'][0]
        self.assertTrue(seen['optional_body_present']);self.assertTrue(seen['terminal_contract_present'])
        self.assertNotIn('PRIVATE_CONTENT',json.dumps(observer.snapshot()))
        agent=type('Agent',(),{'tools':[{'function':{'name':'terminal','description':'original'}}]})()
        hermes_worker.advertise_study_terminal(agent)
        self.assertTrue(agent.tools[0]['function']['description'].startswith('Fixture terminal boundary:'))
        shape=hermes_worker.rejection_shape('terminal',{'command':'cd C:\\fixture && python -m unittest'})
        self.assertTrue(shape['shell_composition']);self.assertTrue(shape['cd_prefix'])
        self.assertNotIn('C:',json.dumps(shape))

    def test_bounded_native_usage_requires_all_reconciliation_controls(self):
        from evaluation_usage import reconcile_program_usage
        values={key:0 for key in m.TOKEN_KEYS};values.update(input_tokens=2,output_tokens=1,prompt_tokens=2,completion_tokens=1,total_tokens=3)
        sources={name:'0'*64 for name in ('agent/client_lifecycle.py','agent/codex_runtime.py',
            'agent/auxiliary_client.py','agent/auxiliary_hooks.py','agent/relay_llm.py',
            'agent/turn_api_request.py','agent/turn_response_intake.py','agent/api_request_hooks.py')}
        usage={'source':'native-Hermes-canonical-session-counters','api_calls':1,'tokens':values,
            'coverage':{'session_completed_responses':1,'aggregate_fields_present':True},
            'lifecycle':{'source':'native-Hermes-lifecycle-hooks','dropped_events':0,
                'events':[{'hook':'pre_api_request'},{'hook':'post_api_request','tokens':values,'usage_present':True}],
                'auxiliary_dispatches':{'_relay_sync_completion':0,'_relay_async_completion':0,'_relay_sync_stream':0},
                'native_sources_before':sources,'native_sources_after':sources,
                'native_http':{'sdk_retry_limits':[0],'clients_hooked':1,'unsupported_clients':0,'dropped_events':0,'observation_errors':0,
                    'events':[{'phase':'request','attempt':1},{'phase':'response','attempt':1,'status':200}]}}}
        self.assertTrue(reconcile_program_usage(usage)['verified'])
        expanded=copy.deepcopy(usage)
        expanded_sources={**sources,'agent/interrupt_control.py':'1'*64,'agent/conversation_loop.py':'2'*64}
        expanded['lifecycle']['native_sources_before']=expanded_sources
        expanded['lifecycle']['native_sources_after']=copy.deepcopy(expanded_sources)
        self.assertTrue(reconcile_program_usage(expanded)['verified'])
        for invalid in ({str(i):'0'*64 for i in range(8)},
                        {**sources,'agent/interrupt_control.py':'1'*64},
                        {**expanded_sources,'agent/conversation_loop.py':'not-a-hash'}):
            bad=copy.deepcopy(expanded)
            bad['lifecycle']['native_sources_before']=invalid
            bad['lifecycle']['native_sources_after']=copy.deepcopy(invalid)
            self.assertFalse(reconcile_program_usage(bad)['verified'])
        for change in ('auxiliary','stream-retry','source-drift','missing-usage','observer-drop'):
            bad=copy.deepcopy(usage)
            if change=='auxiliary':bad['lifecycle']['auxiliary_dispatches']['_relay_sync_completion']=1
            if change=='stream-retry':bad['lifecycle']['native_http']['events'].append({'phase':'request','attempt':2})
            if change=='source-drift':bad['lifecycle']['native_sources_after']={}
            if change=='missing-usage':bad['tokens']['total_tokens']=None
            if change=='observer-drop':bad['lifecycle']['dropped_events']=1
            self.assertFalse(reconcile_program_usage(bad)['verified'],change)

    def complete_record(self, total=45, trial=0):
        """Synthetic complete producer contract; native collectors cannot issue it."""
        context={**self.context(),'attempt_history_complete':True,'prerequisites_sha256':'8'*64,'host_version':'fixture-v1','trial':trial}
        run={**self.codex(),'operational_ok':True,'agent_observed_route':context['route']}
        row=m.observation(run,context,{'passed':True})
        row['usage']['tokens']['total_tokens']=total
        row['usage']['provider_physical_attempt_count']=1
        row['usage']['coverage']['whole_system_complete']=True
        row['harness']['effective_initial_tool_schema_sha256']='5'*64
        return row

    def failed_record(self, trial=1, category='workflow'):
        return m.observation({'ok':False,'operational_ok':True,
            'failure_attribution':{'category':category,'evidence_sha256':'7'*64}},
            {**self.context(),'trial':trial,'attempt_history_complete':True},{'passed':False})

    def test_quality_gate_excludes_failed_missing_usage_but_retains_failure_denominator(self):
        good=self.complete_record();failed=self.failed_record()
        checked=m.acceptance_readiness([good,failed])
        self.assertTrue(checked['ready'],checked)
        self.assertEqual(checked['reliability']['valid_task_run_count'],2)
        self.assertEqual(checked['reliability']['quality_success_rate'],0.5)
        self.assertEqual(len(checked['reliability']['excluded_attempts']),1)
        unknown=self.complete_record();unknown['usage']['tokens']['total_tokens']=None
        self.assertFalse(m.acceptance_readiness([unknown,failed])['ready'])

    def test_conditional_comparison_requires_quality_complete_usage_and_matched_coverage(self):
        before=[self.complete_record(),self.failed_record()]
        after=[self.complete_record(35),self.failed_record()]
        result=m.compare_records(before,after)
        eligible=[pair for pair in result['pairs'] if pair['conditional_efficiency_eligible']]
        self.assertEqual(len(eligible),1)
        self.assertEqual(eligible[0]['token_delta_after_minus_before']['total_tokens'],-10)
        excluded=[pair for pair in result['pairs'] if not pair['conditional_efficiency_eligible']]
        self.assertTrue(all(value is None for value in excluded[0]['token_delta_after_minus_before'].values()))
        self.assertEqual(result['reliability']['before']['quality_success_rate'],0.5)
        self.assertIn('not all-attempt',result['conditional_efficiency']['scope'])
        missing_case=self.complete_record(trial=2);missing_case['identity']['case_id']='another-case'
        drift=m.compare_records(before,after+[missing_case])
        self.assertFalse(drift['conditional_efficiency']['equivalent_case_coverage'])
        asymmetric=m.compare_records(before,[self.complete_record(),self.complete_record(trial=1)])
        self.assertFalse(asymmetric['conditional_efficiency']['equivalent_case_coverage'])

    def test_qualifying_run_cannot_discard_internal_retry_or_judge_usage(self):
        good=self.complete_record();good['identity']['attempt']=2
        retry=self.failed_record(trial=0)
        self.assertFalse(m.acceptance_readiness([retry,good])['ready'])
        self.assertEqual(m.reliability_summary([retry,good])['task_run_count'],1)
        judge=self.failed_record(trial=0);judge['identity'].update(arm='judge',role='judge-0')
        self.assertFalse(m.acceptance_readiness([good,judge])['ready'])
        self.assertEqual(m.reliability_summary([good,judge])['supporting_call_count'],1)

    def test_evaluator_setup_is_invalid_and_unknown_attribution_stays_unresolved(self):
        setup=m.observation({'ok':False,'failure':{'kind':'isolation','source':'runtime-control','code':'PermissionError'},
            'runtime_contract':{'phase':'setup','setup_operation':'runtime-access-preflight'}},self.context())
        self.assertEqual(setup['trial_validity']['status'],'invalid-setup')
        good=self.complete_record(trial=1)
        ready=m.acceptance_readiness([setup,good]);self.assertTrue(ready['ready'],ready)
        self.assertEqual(ready['reliability']['valid_task_run_count'],1)
        self.assertEqual(ready['reliability']['invalid_setup_run_count'],1)
        unknown=m.observation({'ok':False,'failure':{'kind':'runtime','source':'runtime-control','code':'unclassified-native-error'}},self.context())
        self.assertEqual(unknown['trial_validity']['status'],'unresolved')
        self.assertFalse(m.acceptance_readiness([unknown,good])['ready'])

    def test_one_time_setup_needs_fresh_reuse_evidence_and_cold_start_is_explicit(self):
        run={'ok':False,'performance':{'workflow_repair_count':1,'human_intervention_count':1,'human_wait_seconds':20},
             'failure_attribution':{'category':'one-time-workflow-setup','evidence_sha256':'7'*64}}
        unresolved=m.observation(run,self.context())
        self.assertEqual(unresolved['trial_validity']['status'],'unresolved')
        run['failure_attribution']['reuse_evidence_sha256']='6'*64
        steady=m.observation(run,self.context())
        self.assertEqual(steady['trial_validity']['status'],'one-time-setup')
        self.assertEqual(m.reliability_summary([steady])['valid_task_run_count'],0)
        cold=m.observation(run,{**self.context(),'benchmark_scenario':'cold-start'})
        self.assertEqual(cold['trial_validity']['status'],'valid')
        self.assertEqual(cold['performance']['human_wait_seconds'],20)
        recurring=copy.deepcopy(run);recurring['failure_attribution']['category']='workflow'
        recurring['performance']['workflow_retry_count']=2
        charged=m.observation(recurring,self.context())
        self.assertEqual(charged['trial_validity']['status'],'valid')
        self.assertEqual(charged['performance']['workflow_retry_count'],2)
        self.assertEqual(charged['performance']['human_intervention_count'],1)

    def test_prerequisite_and_scenario_drift_cannot_be_precise_equivalent_trials(self):
        good=self.complete_record();drift=copy.deepcopy(good)
        drift['trial_validity']['prerequisites_sha256']='9'*64
        self.assertEqual(m.compare_records([good],[drift])['pairs'],[])
        drift=copy.deepcopy(good);drift['trial_validity']['benchmark_scenario']='cold-start'
        self.assertEqual(m.compare_records([good],[drift])['pairs'],[])
        drift=copy.deepcopy(good);drift['usage']['coverage']['whole_system_complete']=False
        checked=m.compare_records([good],[drift])
        self.assertFalse(checked['pairs'][0]['conditional_efficiency_eligible'])

    def test_successful_output_with_unattributed_guard_friction_is_not_workflow_weakness(self):
        run={**self.codex(),'operational_ok':True,'native_seconds':12,
             'blocked_requests':[{'tool':'terminal','reason':'fixture command gate'}]}
        row=m.observation(run,self.context(),{'passed':True})
        self.assertTrue(row['outcome']['task_passed'])
        self.assertEqual(row['trial_validity']['status'],'unresolved')
        self.assertEqual(row['performance']['native_conversation_seconds'],12)
        self.assertIsNone(row['performance']['workflow_elapsed_seconds'])
        self.assertEqual(m.reliability_summary([row])['observed_quality_passed_run_count'],1)
        self.assertEqual(m.reliability_summary([row])['valid_task_run_count'],0)
        run['failure_attribution']={'category':'workflow','evidence_sha256':'7'*64}
        reviewed=m.observation(run,self.context(),{'passed':True})
        self.assertEqual(reviewed['trial_validity']['status'],'valid')

    def test_native_http_observer_is_allowlisted_and_never_implies_complete_usage(self):
        observer=NativeUsageObserver()
        observer.http_events=[{'phase':'request','attempt':1,'status':None,'seconds':None,'headers':'PRIVATE'},
                              {'phase':'response','attempt':1,'status':200,'seconds':0.5,'body':'PRIVATE'}]
        observer.sdk_retry_limits=[0]
        observer.clients_hooked=1
        run={'native_usage':{'lifecycle':observer.snapshot()}}
        record=m.observation(run,{'case':'fixture','arm':'base'})
        exported=json.dumps(record)
        self.assertNotIn('PRIVATE',exported)
        self.assertIn('native-request-client-HTTPX-events',exported)
        self.assertFalse(record['usage']['coverage']['whole_system_complete'])

    def test_native_runtime_smoke_reaches_existing_worker_without_optional_instructions(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); fixture=root/'project';fixture.mkdir();(fixture/'app.py').write_text('value=1')
            oracle=root/'oracle.py';oracle.write_text('pass')
            private=root/'prepared-parent';private.mkdir()
            archive=root/'request-archive';archive.mkdir()
            spec={'purpose':'native-runtime-smoke','agent':'hermes','provider':'openai-codex','model':'gpt-6.1-sol','reasoning':'medium',
                  'arms':[{'id':'base','instructions':None}],'cases':[{'id':'program','prompt':'Repair the program','fixture':str(fixture)}],
                  'workspace_root':str(root/'jobs'),'prepared_runtime_parent':str(private),'request_recording_parent':str(archive),'oracle':str(oracle),
                  'max_workers':1,'max_iterations':6,'timeout':90,'quota_remaining':1}
            out=root/'out';plan=pilot.prepare(spec,out);pilot.validate_jobs(plan)
            worker={'ok':True,'cleanup':{'state_removed':True,'errors':[]}}
            fake_oracle=type('Result',(),{'stdout':'{"passed":0,"failed":0,"failures":[]}', 'stderr':'', 'returncode':0})()
            with mock.patch.object(runtime,'run_native_skill_study',return_value=worker) as called, mock.patch.object(pilot.subprocess,'run',return_value=fake_oracle):
                report=pilot.run(plan,out)
            self.assertEqual(called.call_args.kwargs['model'],'gpt-6.1-sol')
            self.assertEqual(called.call_args.args[3],[])
            self.assertTrue(called.call_args.kwargs['prepared_runtime'].is_relative_to(private))
            self.assertFalse(report['results'][0]['ok'])  # Empty oracle is never success.
            self.assertFalse(report['admission'])

    def test_native_program_action_evidence_records_actual_failure_without_output(self):
        with tempfile.TemporaryDirectory() as temp:
            fixture = Path(temp).resolve(); catalog = fixture/'catalog'
            event = hermes_worker.study_tool_event('id','terminal',{'command':'python -m unittest'},
                {'exit_code':1,'error':None,'output':'PRIVATE_OUTPUT'},fixture,catalog)
        self.assertFalse(event['success'])
        self.assertEqual(event['exit_code'],1)
        self.assertEqual(event['command'],'python -m unittest')
        self.assertNotIn('PRIVATE_',json.dumps(event))

    def test_worker_cleanup_failure_retains_observed_usage_and_failed_receipt(self):
        observer = NativeUsageObserver()
        observer.callback('post_api_request')(usage={'input_tokens': 7, 'output_tokens': 3})
        receipt = {'ok': True, 'native_usage': {'tokens': {'input_tokens': 7}}, 'route_attestation': {'ok': True, 'errors': []}}
        lease, canary = mock.Mock(), mock.Mock()
        lease.dispose.side_effect = OSError('PRIVATE_ERROR')
        canary.unlink.side_effect = PermissionError('PRIVATE_PATH')
        hermes_worker.finalize_usage_receipt(receipt, observer, [lease], canary)
        self.assertFalse(receipt['ok'])
        self.assertFalse(receipt['route_attestation']['ok'])
        self.assertEqual(receipt['native_usage']['tokens']['input_tokens'], 7)
        self.assertEqual(len(receipt['worker_cleanup_errors']), 2)
        self.assertNotIn('PRIVATE_', json.dumps(receipt))

    def test_completed_multi_response_coverage_uses_actual_hook_usage_without_global_claim(self):
        for missing in (False,True):
            observer=NativeUsageObserver()
            observer.callback('post_api_request')(usage={'input_tokens':5,'output_tokens':3})
            observer.callback('post_api_request')(usage=None if missing else {'input_tokens':7,'output_tokens':2})
            receipt={'ok':True,'native_usage':{'api_calls':2,'coverage':{'session_completed_responses':2,'aggregate_fields_present':True}}}
            hermes_worker.finalize_usage_receipt(receipt,observer,[],None)
            coverage=receipt['native_usage']['coverage']
            self.assertEqual(coverage['completed_responses_with_usage'],1 if missing else 2)
            self.assertEqual(coverage['completed_responses_without_usage'],1 if missing else 0)
            self.assertEqual(coverage['completed_response_usage_complete'],not missing)
            self.assertFalse(receipt['native_usage']['lifecycle']['whole_system_complete'])

    def test_pre_metadata_failure_keeps_available_usage_and_stays_failed(self):
        usage = {'source': 'native-Hermes-canonical-session-counters', 'tokens': {'input_tokens': 19}, 'api_calls': 1}
        def missing_metadata(text):
            result = json.loads(text)
            result.pop('route_attestation', None)
            result['native_usage'] = usage
            return result
        with tempfile.TemporaryDirectory() as temp:
            with mock.patch.object(native_fixtures.evaluator, 'extract_json', side_effect=missing_metadata):
                result, record = self.fake_native(Path(temp), 'hermes')
        self.assertFalse(result['ok'])
        self.assertFalse(result['execution_ok'])
        self.assertEqual(result['native_usage'], usage)
        self.assertEqual(result['failure']['code'], 'ValueError')

    def test_selected_current_model_is_forwarded_without_running_native(self):
        seen = []
        def process(command, **kwargs):
            job = json.loads(kwargs['input']); seen.append(job)
            route = {key: job[key] for key in ('model', 'reasoning')}
            return type('Result', (), {'returncode': 0, 'stdout': json.dumps({'ok': True, 'requested_route': route})})()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); fixture = root/'fixture'; fixture.mkdir()
            with mock.patch.object(runtime, 'native_executable', return_value='synthetic-hermes'), \
                 mock.patch.object(runtime, 'native_hermes_runtime', return_value=(Path('synthetic-python'), root)), \
                 mock.patch.object(runtime.subprocess, 'run', side_effect=process):
                prepared = root/'prepared'; prepared.mkdir()
                result = runtime.run_native_skill_study('task', fixture, 20, [], agent='hermes', max_iterations=4,
                                                       model='gpt-6.1-sol', reasoning='high', prepared_runtime=prepared)
        self.assertTrue(result['ok'], result)
        self.assertEqual(len(seen), 1)
        self.assertEqual((seen[0]['model'], seen[0]['reasoning']), ('gpt-6.1-sol', 'high'))
        self.assertFalse(prepared.exists())

    def test_omp_native_stats_are_observable_not_complete_or_billed(self):
        run = {'native_omp_stats_source': 'get_session_stats', 'native_omp_stats': {
               'tokens': {'input': 30, 'output': 5, 'cacheRead': 9, 'reasoning': 2, 'total': 44},
               'sessionFile': 'PRIVATE_PATH', 'sessionId': 'PRIVATE_SESSION', 'cost': 99}}
        record = m.observation(run, {**self.context(), 'host': 'omp'})
        self.assertEqual(record['usage']['tokens']['total_tokens'], 44)
        self.assertIsNone(record['usage']['native_completed_response_count'])
        self.assertFalse(record['usage']['coverage']['whole_system_complete'])
        self.assertNotIn('PRIVATE_', json.dumps(record))
        self.assertIsNone(record['usage']['billed_cost_usd'])

    def test_acceptance_refuses_unknown_overall_accounting_even_good_outcome(self):
        record = m.observation({**self.codex(), 'operational_ok': True}, {**self.context(), 'attempt_history_complete': True}, {'passed': True})
        readiness = m.acceptance_readiness([record])
        self.assertFalse(readiness['ready'])
        self.assertTrue(any('overall token coverage' in gap for gap in readiness['gaps']))

    def test_projection_error_preserves_raw_evidence_for_export(self):
        report = {'attempt_ledger': [], 'results': [], 'important_failure': 'retained'}
        with mock.patch.object(m, 'inline_records', side_effect=ValueError('PRIVATE_ERROR_SENTINEL')):
            m.attach_measurements(report)
        self.assertEqual(report['important_failure'], 'retained')
        self.assertFalse(report['measurement_status']['projection_ok'])
        self.assertNotIn('PRIVATE_ERROR_SENTINEL', json.dumps(report))

    def test_native_hook_projection_keeps_errors_aux_usage_missing_and_redacts(self):
        observer = NativeUsageObserver(limit=4)
        observer.callback('pre_api_request')(api_request_id='PRIVATE_ID', retry_count=0, request={'api_key': 'PRIVATE_KEY'})
        observer.callback('api_request_error')(error={'message': 'PRIVATE_ERROR'}, api_duration=0.2)
        observer.callback('post_auxiliary_call')(usage={'input_tokens': 9, 'output_tokens': 2}, error_type=None)
        observer.callback('post_api_request')(usage=None)
        observer.callback('pre_api_request')()
        seen = observer.snapshot()
        self.assertEqual(seen['dropped_events'], 1)
        self.assertIsNone(seen['events'][1]['tokens']['input_tokens'])
        self.assertEqual(seen['events'][2]['tokens']['input_tokens'], 9)
        self.assertFalse(seen['whole_system_complete'])
        self.assertNotIn('PRIVATE_', json.dumps(seen))
        seen['secret'] = 'PRIVATE_PAYLOAD'
        seen['events'][0]['raw_request'] = 'PRIVATE_PAYLOAD'
        record = m.observation({'native_usage': {'lifecycle': seen}}, {**self.context(), 'host': 'hermes'})
        self.assertNotIn('PRIVATE_', json.dumps(record))

    def context(self):
        return {'host': 'codex', 'case_id': 'task', 'arm': 'current', 'role': 'candidate', 'trial': 0, 'attempt': 1,
                'task_sha256': '1'*64, 'verifier_sha256': '2'*64, 'harness_sha256': '3'*64,
                'instruction_sha256': '4'*64, 'runtime_lane': 'test', 'tool_policy': 'none', 'context_policy': 'fresh',
                'route': {'model': 'test', 'provider': 'openai-codex', 'reasoning': 'medium'}}

    def codex(self):
        return {'ok': True, 'seconds': 2.0, 'output': 'answer', 'native_events': [
            {'type': 'turn.completed', 'usage': {'input_tokens': 40, 'cached_input_tokens': 25, 'output_tokens': 5}}]}

    def test_codex_subset_categories_are_never_added_and_calls_unknown(self):
        record = m.observation(self.codex(), self.context(), {'passed': True})
        usage = record['usage']
        self.assertEqual(usage['tokens']['input_tokens'], 40)
        self.assertEqual(usage['tokens']['cache_read_tokens'], 25)
        self.assertIsNone(usage['tokens']['total_tokens'])
        self.assertIsNone(usage['native_completed_response_count'])
        self.assertIsNone(usage['provider_physical_attempt_count'])
        self.assertFalse(usage['coverage']['whole_system_complete'])

    def test_unknown_invalid_partial_and_unsupported_native_telemetry(self):
        run = self.codex()
        run['native_events'][0]['usage'].update(input_tokens=True, output_tokens=-1)
        record = m.observation(run, self.context())
        self.assertIsNone(record['usage']['tokens']['input_tokens'])
        self.assertFalse(record['usage']['coverage']['completed_response_usage_complete'])
        run['native_events'].append(copy.deepcopy(run['native_events'][0]))
        self.assertEqual(m.observation(run, self.context())['usage']['source'], 'unavailable')
        self.assertEqual(m.observation(run, {**self.context(), 'host': 'omp'})['usage']['source'], 'unavailable')

    def test_hermes_preserves_failure_usage_without_quality_or_billing(self):
        run = {'ok': False, 'native_usage': {'source': 'native-Hermes-canonical-session-counters',
               'tokens': {'input_tokens': 10, 'total_tokens': 17, 'output_tokens': 7}, 'api_calls': 1,
               'cost': {'billed_cost_usd': 99}, 'coverage': {'completed_response_usage_complete': False}}}
        record = m.observation(run, {**self.context(), 'host': 'hermes'}, {'passed': True})
        self.assertEqual(record['usage']['tokens']['total_tokens'], 17)
        self.assertIsNone(record['usage']['billed_cost_usd'])
        self.assertIsNone(record['outcome']['task_passed'])

    def test_private_payloads_only_have_output_hash_not_text(self):
        run = {**self.codex(), 'output': 'PRIVATE_RESPONSE_SENTINEL', 'stderr': 'PRIVATE_DIAGNOSTIC_SENTINEL',
               'api_key': 'PRIVATE_CREDENTIAL_SENTINEL', 'session_id': 'PRIVATE_SESSION_SENTINEL'}
        raw = json.dumps(m.observation(run, self.context()))
        self.assertNotIn('PRIVATE_', raw)

    def test_attempt_ledger_includes_judges_failures_orphans_once(self):
        with tempfile.TemporaryDirectory() as temp:
            fixture = make_evaluation(Path(temp))
            report = fixture['report']
            original = copy.deepcopy(report)
            rows = m.inline_records(report)
            self.assertEqual(report, original)
            self.assertEqual(len(rows), len(report['attempt_ledger']))
            self.assertTrue(any(row['identity']['arm'] == 'judge' for row in rows))
            report['attempt_ledger'].append({'case_id': 'orphan', 'trial': 9, 'role': 'candidate', 'attempt': 1, 'ok': False})
            orphan = m.inline_records(report)[-1]
            self.assertIsNone(orphan['outcome']['task_passed'])
            self.assertEqual(orphan['usage']['source'], 'unavailable')
            self.assertEqual(len(report['measurements']), len(original['attempt_ledger']))

    def test_historical_projection_is_pure_and_cannot_claim_retry_history(self):
        report = {'results': [{'id': 'x', 'trial': 0, 'baseline': self.codex(), 'candidate': self.codex()}], 'attempt_ledger': []}
        original = copy.deepcopy(report)
        rows = m.inline_records(report)
        self.assertEqual(report, original)
        self.assertEqual(len(rows), 2)
        self.assertFalse(any(row['retries']['history_complete'] for row in rows))

    def test_model_regression_pins_harness_instruction_task_and_verifier(self):
        a = m.observation(self.codex(), self.context(), {'passed': True})
        new = {**self.context(), 'route': {'model': 'new-model', 'provider': 'openai-codex', 'reasoning': 'medium'}}
        b = m.observation(self.codex(), new, {'passed': False})
        checked = m.compare_records([a], [b], changed='model')
        self.assertEqual(len(checked['pairs']), 1)
        self.assertEqual(checked['pairs'][0]['task_passed'], {'before': True, 'after': False})
        for field in ('harness_sha256', 'instruction_sha256', 'task_sha256', 'verifier_sha256'):
            drift = m.observation(self.codex(), {**new, field: '9'*64})
            self.assertEqual(m.compare_records([a], [drift], changed='model')['pairs'], [])

    def test_retry_duplicates_and_missing_usage_never_yield_savings(self):
        a = m.observation(self.codex(), self.context())
        b = m.observation({'ok': True}, self.context())
        checked = m.compare_records([a], [b])
        self.assertTrue(all(value is None for value in checked['pairs'][0]['token_delta_after_minus_before'].values()))
        self.assertIsNone(checked['pairs'][0]['whole_system_efficiency_verdict'])
        self.assertEqual(m.compare_records([a, a], [b])['pairs'], [])

    def test_three_arm_native_plan_preserves_common_catalog_and_frozen_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            fixture = root/'fixture'; fixture.mkdir(); (fixture/'source.py').write_text('value=1\n')
            arms = [{'id': 'base', 'instructions': None}]
            for arm in ('current', 'trimmed'):
                package = root/arm/'instruction-authoring'; package.mkdir(parents=True)
                (package/'SKILL.md').write_text('---\nname: instruction-authoring\ndescription: Author instructions\n---\n'+arm)
                arms.append({'id': arm, 'instructions': str(package/'SKILL.md')})
            oracle = root/'oracle.py'; oracle.write_text('pass')
            spec = {'purpose': 'native-skill-study', 'agent': 'hermes', 'model': 'gpt-6-sol', 'provider': 'openai-codex', 'reasoning': 'medium',
                    'arms': arms, 'cases': [{'id': 'actual', 'prompt': 'Repair source', 'fixture': str(fixture)}],
                    'workspace_root': str(root/'jobs'), 'oracle': str(oracle), 'max_workers': 1, 'max_iterations': 8, 'timeout': 90, 'quota_remaining': 1}
            with mock.patch('subprocess.Popen', side_effect=AssertionError('offline preparation cannot launch')):
                plan = pilot.prepare(spec, root/'out'); pilot.validate_jobs(plan)
            self.assertEqual(len(plan['jobs']), 3)
            self.assertEqual(next(job for job in plan['jobs'] if job['arm'] == 'base')['catalog'], [])
            self.assertEqual({job['prompt'] for job in plan['jobs']}, {'Repair source'})
            self.assertFalse(plan['workflow_comparison_supported'])
            plan['jobs'][1]['catalog_frames']['tampered'] = '0'*64
            with self.assertRaises(ValueError): pilot.validate_jobs(plan)


if __name__ == '__main__': unittest.main()
