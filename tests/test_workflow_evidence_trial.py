"""Hermes workflow opt-in boundary; no actual model requests."""
import copy,importlib.util,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('workflow_evidence_selector',ROOT/'skills/openai-delegation-route-research/scripts/route_selector.py')
router=importlib.util.module_from_spec(spec)
spec.loader.exec_module(router)

def request(transport='hermes-workflow'):
    return {'requirements':{'host':'hermes','transport':transport,'tools':['read_file','search_files'],'model':None,'reasoning_effort':None},
        'verifier':{'kind':'independent-review','independent':True,'coverage':'complete','scope':'artifact-effects'},
        'effects':'none','failure_cost':'low','continuation':None,
        'budget':{'evidence_trial':{'authorized':True,'max_requests':5,'accept_unknown_quota':True},
            'parent_available':True,'attempt_cap':1,'attempts_used':0,'fallback_route_id':None,'fallback_route_sha256':None,
            'allow_api_spend':False,'unknown_cost_policy':'explicit_preference','preference_order':['bounded-workflow']}}

class WorkflowEvidenceTrialTests(unittest.TestCase):
    def test_workflow_and_direct_are_admissible(self):
        for surface in ['hermes-workflow','hermes-delegate']:
            self.assertTrue(router.evidence_trial_admissible(request(surface)))
    def test_other_host_or_transport_is_not_admitted(self):
        for key,value in [('host','codex'),('transport','codex-workflow'),('transport','omp-workflow')]:
            task=request(); task['requirements'][key]=value
            self.assertFalse(router.evidence_trial_admissible(task))
    def test_nearby_unsafe_or_unbounded_cases_stay_blocked(self):
        mutations=[('effects','reversible'),('failure_cost','medium'),('continuation',{})]
        for key,value in mutations:
            task=request();task[key]=value
            self.assertFalse(router.evidence_trial_admissible(task))
        for key,value in [('parent_available',False),('attempt_cap',2),('attempts_used',1),('allow_api_spend',True),('fallback_route_id','other')]:
            task=request();task['budget'][key]=value
            self.assertFalse(router.evidence_trial_admissible(task))
        task=request();task['requirements']['tools']=['terminal']
        self.assertFalse(router.evidence_trial_admissible(task))
        task=request();task['budget']['evidence_trial']['authorized']=False
        self.assertFalse(router.evidence_trial_admissible(task))
        task=request();task['verifier']['coverage']='partial'
        self.assertFalse(router.evidence_trial_admissible(task))
    def test_missing_opt_in_is_not_admitted(self):
        task=request();task['budget'].pop('evidence_trial')
        self.assertFalse(router.evidence_trial_admissible(task))

if __name__=='__main__': unittest.main()
