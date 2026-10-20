"""No model/network: deadline unblocks native seam and partial usage survives kill."""
from fixture_workspace import configure
configure()
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest import mock

TOOLS=Path(__file__).resolve().parents[1]/'tools'
sys.path.insert(0,str(TOOLS))
import evaluation_hermes_worker as worker
from evaluation_usage import NativeUsageObserver

class DeadlineTests(unittest.TestCase):
    def test_blocked_native_call_unwinds_and_cannot_claim_success(self):
        owner=threading.get_ident()
        calls=[]
        wake=threading.Event()
        class Agent:
            def interrupt(self,**kwargs):calls.append(('interrupt',threading.get_ident(),kwargs))
            def _drain_transports_after_abandonment(self,**kwargs):
                calls.append(('shutdown',threading.get_ident(),kwargs));wake.set()
            def run_conversation(self,prompt):
                self.waited=wake.wait(2)
                return {'completed':True,'api_calls':1}
        agent=Agent()
        result,receipt=worker.run_with_deadline(agent,'task',.02)
        self.assertTrue(agent.waited)
        self.assertFalse(result['completed'])
        self.assertTrue(result['interrupted'])
        self.assertEqual([c[0] for c in calls],['interrupt','shutdown'])
        self.assertTrue(all(c[1]!=owner for c in calls))
        self.assertTrue(receipt['fired']);self.assertTrue(receipt['timer_settled'])
        self.assertEqual(receipt['errors'],[])
    def test_success_cancels_timer_and_does_not_interrupt(self):
        class Agent:
            interrupt=mock.Mock()
            _drain_transports_after_abandonment=mock.Mock()
            def run_conversation(self,prompt):return {'completed':True,'api_calls':1}
        agent=Agent()
        result,receipt=worker.run_with_deadline(agent,'task',10)
        self.assertTrue(result['completed']);self.assertFalse(receipt['fired'])
        agent.interrupt.assert_not_called();agent._drain_transports_after_abandonment.assert_not_called()
    def test_missing_native_cancel_support_fails_before_conversation(self):
        agent=mock.Mock(spec=['run_conversation'])
        with self.assertRaisesRegex(RuntimeError,'interruption seams'):
            worker.run_with_deadline(agent,'task',1)
        agent.run_conversation.assert_not_called()
    def test_interrupt_failure_still_attempts_safe_shutdown(self):
        wake=threading.Event()
        class Agent:
            def interrupt(self,**kwargs):raise ValueError('must not export SECRET')
            def _drain_transports_after_abandonment(self,**kwargs):wake.set()
            def run_conversation(self,prompt):
                if not wake.wait(2):raise AssertionError('did not unblock')
                return {'completed':False}
        _,receipt=worker.run_with_deadline(Agent(),'task',.02)
        self.assertEqual(receipt['errors'],['interrupt-ValueError'])
        self.assertNotIn('SECRET',json.dumps(receipt))

class CheckpointTests(unittest.TestCase):
    def binding(self):return {'run_id':'synthetic','case_id':'case','arm':'base',
        'plan_sha256':'1'*64,'task_sha256':hashlib.sha256(b'task').hexdigest(),'oracle_sha256':'2'*64}
    def test_completed_usage_and_inflight_unknown_survive_abrupt_process_exit(self):
        with tempfile.TemporaryDirectory() as temp:
            archive=Path(temp)/'requests'
            code='''import json,os,sys
sys.path.insert(0,sys.argv[1])
from evaluation_usage import NativeUsageObserver
observer=NativeUsageObserver()
observer.enable_recording(sys.argv[2],json.loads(sys.argv[3]),forbidden=('SENSITIVE_SENTINEL',))
observer.record_prompts('system','task')
observer.callback('post_api_request')(api_request_id='safe',usage={'input_tokens':7,'output_tokens':3,'total_tokens':10},response='SENSITIVE_SENTINEL')
observer.callback('pre_api_request')(api_request_id='unfinished',request={'body':{'tools':[]}},request_messages=['SENSITIVE_SENTINEL'])
os._exit(9)
'''
            proc=subprocess.run([sys.executable,'-B','-c',code,str(TOOLS),str(archive),json.dumps(self.binding())],
                                capture_output=True,text=True,timeout=15)
            self.assertEqual(proc.returncode,9,proc.stderr)
            raw=(archive/'lifecycle-checkpoint.json').read_text()
            data=json.loads(raw)
            self.assertEqual(data['events'][0]['tokens']['total_tokens'],10)
            self.assertFalse(data['events'][1]['usage_present'])
            self.assertIsNone(data['events'][1]['tokens']['total_tokens'])
            self.assertFalse(data['complete']);self.assertFalse(data['whole_system_complete'])
            self.assertEqual(data['binding'],self.binding())
            self.assertNotIn('SENSITIVE_SENTINEL',raw)
            self.assertFalse((archive/'manifest.json').exists())
    def test_checkpoint_write_failure_prevents_precision(self):
        with tempfile.TemporaryDirectory() as temp:
            observer=NativeUsageObserver()
            observer.enable_recording(Path(temp)/'requests',self.binding())
            with mock.patch('evaluation_usage.os.replace',side_effect=OSError('private detail')):
                observer.callback('post_api_request')(usage={'total_tokens':10})
            self.assertGreater(observer.observation_errors,0)
            self.assertFalse(observer.finish_recording()['complete'])

if __name__=='__main__':unittest.main()
