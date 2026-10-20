"""Native artifact continuation retains full suite and immutable prior attempts."""
from fixture_workspace import configure
configure()
import copy
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import evaluation_artifact_pilot as pilot
import evaluation_runtime as runtime

class ContinuationTests(unittest.TestCase):
    def fixture(self,root):
        source=root/'source';source.mkdir();(source/'app.txt').write_text('defective')
        skill=root/'skill';skill.mkdir();(skill/'SKILL.md').write_text('---\nname: fixture\ndescription: test\n---\nBody')
        oracle=root/'oracle.py';oracle.write_text('print("unused")')
        archive=root/'archive';archive.mkdir()
        spec={'purpose':'native-skill-study','agent':'hermes','provider':'openai-codex',
            'model':'fixture','reasoning':'medium','max_workers':1,'max_iterations':4,'timeout':30,
            'quota_remaining':1,'workspace_root':str(root/'actors'),'oracle':str(oracle),
            'request_recording_parent':str(archive),
            'arms':[{'id':'base','instructions':None},{'id':'candidate','instructions':str(skill/'SKILL.md')}],
            'cases':[{'id':'case','fixture':str(source),'prompt':'Repair the program.'}]}
        plan=pilot.prepare(spec,root/'original')
        prior=plan['jobs'][0]
        (Path(prior['fixture'])/'app.txt').write_text('repaired')
        report=root/'prior.json'
        report.write_text(json.dumps({'results':[{'id':prior['id'],'case':prior['case'],'arm':prior['arm'],
            'ok':False,'final_tree':pilot.tree(Path(prior['fixture'])),'native':{'failure':'TimeoutExpired'}}]}))
        plan['prior_attempts']=[{'plan':str(root/'original/plan.json'),
            'plan_sha256':pilot.sha(root/'original/plan.json'),'report':str(report),
            'report_sha256':pilot.sha(report),'job_ids':[prior['id']]}]
        return plan,report
    def test_full_suite_with_bound_prior_final_tree_is_valid(self):
        with tempfile.TemporaryDirectory() as temp:
            plan,report=self.fixture(Path(temp))
            before=report.read_bytes()
            pilot.validate_jobs(plan)
            self.assertEqual(len(plan['jobs']),2)
            self.assertEqual(list(pilot.prior_attempts(plan)),[plan['jobs'][0]['id']])
            self.assertEqual(report.read_bytes(),before)
    def test_subset_still_cannot_masquerade_as_full_suite(self):
        with tempfile.TemporaryDirectory() as temp:
            plan,_=self.fixture(Path(temp));plan['jobs']=plan['jobs'][1:]
            with self.assertRaises(ValueError):pilot.validate_jobs(plan)
    def test_unbound_or_changed_prior_and_pending_sources_fail(self):
        for variant in ('receipt','prior-tree','pending-tree','original-job','route','duplicate'):
            with self.subTest(variant=variant),tempfile.TemporaryDirectory() as temp:
                plan,report=self.fixture(Path(temp))
                if variant=='receipt':report.write_text('{}')
                if variant=='prior-tree':(Path(plan['jobs'][0]['fixture'])/'app.txt').write_text('unbound')
                if variant=='pending-tree':(Path(plan['jobs'][1]['fixture'])/'app.txt').write_text('unbound')
                if variant=='original-job':plan['jobs'][0]['prompt']='new unmeasured task'
                if variant=='route':plan['spec']['model']='different'
                if variant=='duplicate':plan['prior_attempts'].append(copy.deepcopy(plan['prior_attempts'][0]))
                with self.assertRaises(ValueError):pilot.validate_jobs(plan)
    def test_only_unattempted_job_executes_and_prior_spend_is_not_replaced(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);plan,report=self.fixture(root)
            old=report.read_bytes();out=root/'continued';out.mkdir()
            def worker(prompt,fixture,*args,**kwargs):
                self.assertEqual(str(fixture),plan['jobs'][1]['fixture'])
                return {'ok':True,'final_response':'done','request_recording':{'complete':True}}
            answer=SimpleNamespace(stdout='{"passed":1,"failed":0,"failures":[]}',stderr='',returncode=0)
            with mock.patch.object(runtime,'run_native_skill_study',side_effect=worker) as invoke,\
                 mock.patch.object(pilot.subprocess,'run',return_value=answer),\
                 mock.patch('evaluation_usage.bind_recorded_output',return_value={'complete':True}):
                result=pilot.run_native_plan(plan,out)
            self.assertEqual(invoke.call_count,1)
            self.assertEqual(result['completed_trials'],1)
            self.assertEqual(result['expected_trials'],1)
            self.assertEqual(result['full_suite_expected_trials'],2)
            self.assertEqual(result['prior_attempt_ids'],[plan['jobs'][0]['id']])
            self.assertFalse(result['admission'])
            self.assertEqual(report.read_bytes(),old)

if __name__=='__main__':unittest.main()
