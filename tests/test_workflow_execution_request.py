"""Explicit execution does not claim task quality or widen native authorization."""
import copy, unittest
import test_evidence_worker_trial as baseline
load=baseline.load

class ExecutionRequestTests(unittest.TestCase):
    def setUp(self):
        baseline.EvidenceTrialTests.setUp(self)
        self.catalog['task_preferences'] = {}
        self.c['route']['transport']='hermes-workflow'
        self.c['route']['model']='gpt-6-sol'
        self.c['route']['reasoning_effort']='low'
        self.c['availability']['tools_verified']=['read_file','write_file','terminal']
        self.c['availability']['allowed_effects']=['none','reversible']
        self.c['quality']=[]
        self.c['availability']['route_sha256']=self.selector.digest(self.c['route'])
        self.request['requirements'].update(model='gpt-6-sol',reasoning_effort='low',tools=['read_file','write_file','terminal'])
        self.request['effects']='reversible'
        self.request['failure_cost']='high'
        self.request['budget']['execution_request']=self.request['budget'].pop('evidence_trial')
    def decide(self,request=None):
        task=load('task_request').materialize(request or self.request,task_id='execution',host='hermes',transport='hermes-workflow',input_descriptor={'goal':'edit owned files and run checks'},as_of=self.c['availability']['observed_at'])
        return self.selector.decide_route_v3(self.catalog,task)
    def test_full_execution_selected_without_quality_claim(self):
        decision=self.decide()
        self.assertEqual(decision['outcome'],'selected_model')
        self.assertEqual(decision['qualification'],'parent-authorized-execution')
    def test_required_boundaries(self):
        cases=[(('effects',),'irreversible'),(('requirements','model'),None),(('verifier','scope'),'independent-review'),(('verifier','independent'),False),(('budget','execution_request','authorized'),False),(('budget','execution_request','accept_unknown_quota'),False),(('budget','parent_available'),False),(('budget','attempt_cap'),2),(('budget','allow_api_spend'),True),(('budget','unknown_cost_policy'),'task_preference'),(('budget','quotas'),{'codex-main':{'unit':'percentage-points','remaining':None,'reserve':1}})]
        for keys,value in cases:
            with self.subTest(keys=keys):
                request=copy.deepcopy(self.request); target=request
                for key in keys[:-1]: target=target[key]
                target[keys[-1]]=value
                try:
                    decision=self.decide(request)
                except self.selector.RouteSelectionError:
                    continue
                self.assertNotEqual(decision['outcome'],'selected_model')
    def test_conflicting_lane_and_preference_are_refused(self):
        request=copy.deepcopy(self.request)
        request['budget']['evidence_trial']=request['budget']['execution_request'].copy()
        self.assertNotEqual(self.decide(request)['outcome'],'selected_model')
        request=copy.deepcopy(self.request)
        request['budget']['preference_order']=['different']
        self.assertNotEqual(self.decide(request)['outcome'],'selected_model')
    # Inherited tests describe the historical read-only lane, not this lane.
    test_read_only_semantic_trial_with_unknown_quota=None
    test_nearby_hard_failures_remain_closed=None
    def test_no_opt_in_preserves_old_policy(self):
        del self.request['budget']['execution_request']
        self.assertEqual(self.decide()['outcome'],'keep_parent')
    def test_regression_and_paid_route_still_excluded(self):
        self.c['cost']['billing']='api'
        self.assertEqual(self.decide()['outcome'],'keep_parent')

if __name__=='__main__':unittest.main()

