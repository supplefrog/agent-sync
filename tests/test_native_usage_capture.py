"""No inference: native canonical counters survive the existing worker route."""
from fixture_workspace import configure as configure_test_workspace
configure_test_workspace()
import json,sys,unittest
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest import mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import evaluation_hermes_worker as worker

class NativeUsageCaptureTests(unittest.TestCase):
    def usage(self):return dict(input_tokens=90,output_tokens=30,cache_read_tokens=10,cache_write_tokens=0,reasoning_tokens=20,prompt_tokens=100,completion_tokens=30,total_tokens=130,api_calls=1,estimated_cost_usd=0,cost_status='included',cost_source='none')
    def test_complete_single_response_preserves_counters_without_double_counting(self):
        captured=worker.native_usage(self.usage(),SimpleNamespace(session_api_calls=1,_last_turn_usage={'input_tokens':90,'output_tokens':30}))
        self.assertEqual(captured['tokens']['total_tokens'],130)
        self.assertEqual(captured['tokens']['reasoning_tokens'],20)
        self.assertEqual(captured['coverage']['completed_responses_with_usage'],1)
        self.assertEqual(captured['coverage']['completed_responses_without_usage'],0)
        self.assertTrue(captured['coverage']['completed_response_usage_complete'])
        self.assertFalse(captured['coverage']['complete_for_system_efficiency'])
        self.assertIsNone(captured['cost']['billed_cost_usd'])
    def test_missing_and_partial_usage_never_turn_into_zero_or_complete(self):
        for native in ({},{'api_calls':1,'input_tokens':90},{'api_calls':2,**{k:v for k,v in self.usage().items() if k!='api_calls'}}):
            with self.subTest(native=native):
                captured=worker.native_usage(native,SimpleNamespace())
                self.assertFalse(captured['coverage']['completed_response_usage_complete'])
                self.assertIsNone(captured['coverage']['completed_responses_with_usage'])
                self.assertIsNone(captured['coverage']['completed_responses_without_usage'])
        self.assertIsNone(worker.native_usage({},SimpleNamespace())['tokens']['total_tokens'])
    def test_invalid_and_secret_fields_are_not_exported(self):
        native={'api_key':'synthetic-secret','input_tokens':True,'total_tokens':-1,'estimated_cost_usd':float('nan'),'cost_source':'synthetic-secret','cost_status':{}}
        captured=worker.native_usage(native,SimpleNamespace())
        self.assertNotIn('synthetic-secret',json.dumps(captured)); self.assertIsNone(captured['tokens']['input_tokens']); self.assertIsNone(captured['tokens']['total_tokens']); self.assertIsNone(captured['cost']['estimated_cost_usd'])
    def test_failure_preserves_available_session_usage(self):
        agent=SimpleNamespace(model='test-model',provider='openai-codex',reasoning_config={'effort':'high'},valid_tool_names=[],
            _environment_probe=False,_api_max_retries=1,_auto_recovery_cycles=0,_intent_ack_continuation=False,_empty_guard_enabled=False,
            **{'session_'+k:v for k,v in self.usage().items()},_last_turn_usage={'input_tokens':90,'output_tokens':30})
        agent.run_conversation=mock.Mock(side_effect=RuntimeError('synthetic transport failure'))
        agent._execute_tool_calls=mock.Mock(); agent._execute_tool_calls_sequential=mock.Mock(); agent._execute_tool_calls_concurrent=mock.Mock()
        result=worker.execute_agent({'model':'test-model','reasoning':'high','timeout':1,'prompt':'task','canary':'CANARY'},'synthetic-access',lambda **_kwargs:agent,lambda _agent:'native prompt')
        self.assertFalse(result['ok']); self.assertEqual(result['native_usage']['tokens']['total_tokens'],130)
        self.assertEqual(result['native_usage']['coverage']['failed_attempt_coverage'],'unknown')
    def test_existing_report_preserves_usage_without_inference(self):
        from test_evaluation_evidence import make_evaluation
        usage=worker.native_usage(self.usage(),SimpleNamespace(session_api_calls=1,_last_turn_usage={'input_tokens':90,'output_tokens':30}))
        with tempfile.TemporaryDirectory() as temp:
            fixture=make_evaluation(Path(temp),native_usage=usage)
        self.assertEqual(fixture['report']['results'][0]['candidate']['native_usage'],usage)

if __name__=='__main__':unittest.main()
