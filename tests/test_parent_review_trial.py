"""One-attempt semantic review exploration never bypasses exclusions."""
import copy
import importlib.util
import json
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]/'skills/openai-delegation-route-research'
def load(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/'scripts'/f'{name}.py')
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
class ParentReviewTrial(unittest.TestCase):
    def test_positive_and_boundary_exclusions(self):
        selector=load('route_selector'); materializer=load('task_request')
        catalog=json.loads((ROOT/'references/current-task-route-catalog.json').read_text())
        c=catalog['candidates'][0]; route=c['route']; c['quality']=[]
        request={'schema_version':3,'task_class':'bounded-source-review-question-answering',
          'requirements':{'context_tokens':12000,'model':route['model'],'reasoning_effort':route['reasoning_effort'],'tools':[],'task_contract_sha256':'a'*64},
          'verifier':{'kind':'independent-review','coverage':'complete','independent':True,'scope':'independent-review','evidence':{'locator':'synthetic-verifier','sha256':'b'*64}},
          'effects':'none','failure_cost':'low','deterministic':None,
          'budget':{'objective':'quota','allow_api_spend':False,'api_remaining':None,'api_reserve':0,'attempt_cap':1,'attempts_used':0,'fallback_route_id':None,'fallback_route_sha256':None,'parent_available':True,'preference_order':[c['id']],'unknown_cost_policy':'explicit_preference','quotas':{'codex-main':{'remaining':50,'reserve':0,'unit':'percentage-points'}}}}
        task=materializer.materialize(request,task_id='synthetic-trial',host='hermes',transport='hermes-delegate',input_descriptor={'goal':'synthetic source review'},as_of=c['availability']['observed_at'])
        result=selector.decide_route_v3(catalog,task)
        self.assertEqual(result['outcome'],'selected_model')
        self.assertEqual(result['qualification'],'provisional-parent-review-trial')
        cases=[('effects',('effects',),'reversible'),('tools',('requirements','tools'),['read_file']),('risk',('failure_cost',),'high'),('partial',('verifier','coverage'),'partial'),('dependent',('verifier','independent'),False),('schema',('verifier','kind'),'schema-only'),('two-attempts',('budget','attempt_cap'),2),('no-parent',('budget','parent_available'),False),('no-preference',('budget','preference_order'),[]),('ambiguous',('budget','preference_order'),[c['id'],'other']),('effort',('requirements','reasoning_effort'),'medium')]
        for label,keys,value in cases:
            with self.subTest(label=label):
                t=copy.deepcopy(task); target=t
                for key in keys[:-1]:target=target[key]
                target[keys[-1]]=value
                self.assertNotEqual(selector.decide_route_v3(catalog,t)['outcome'],'selected_model')
        c['quality']=[{'task_class':task['task_class'],'task_contract_sha256':'a'*64,'verifier_sha256':'b'*64,'route_sha256':selector.digest(route),'status':'regression','scope':'independent-review','evidence':request['verifier']['evidence']}]
        self.assertNotEqual(selector.decide_route_v3(catalog,task)['outcome'],'selected_model')
if __name__=='__main__':unittest.main()
