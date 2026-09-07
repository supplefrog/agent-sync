"""Controller input binding at the routing/execution boundary."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('task_request_under_test',ROOT/'skills/openai-delegation-route-research/scripts/task_request.py')
request=importlib.util.module_from_spec(spec);spec.loader.exec_module(request)

def template():
    return {'schema_version':3,'task_class':'bounded-proposal',
            'requirements':{'tools':[],'context_tokens':0,'task_contract_sha256':'a'*64,'model':None,'reasoning_effort':None},
            'verifier':{'kind':'independent-review','independent':True,'coverage':'complete','scope':'artifact-effects',
                        'evidence':{'locator':'synthetic:review-contract','sha256':'b'*64}},
            'effects':'reversible','failure_cost':'low','deterministic':None,
            'budget':{'objective':'quota','api_remaining':None,'api_reserve':0,'allow_api_spend':False,
                      'quotas':{'synthetic-pool':{'unit':'synthetic-unit','remaining':10,'reserve':2}},
                      'unknown_cost_policy':'keep_parent','preference_order':[],'parent_available':True,
                      'attempt_cap':1,'attempts_used':0,'fallback_route_id':None,'fallback_route_sha256':None}}

class TaskRequestTests(unittest.TestCase):
    def bind(self,value=None,descriptor=None,**overrides):
        options={'task_id':'bounded','host':'hermes','transport':'hermes-delegate',
                 'input_descriptor':{'goal':'Inspect one file'} if descriptor is None else descriptor,'as_of':'2026-09-06T00:00:00Z'}
        options.update(overrides)
        return request.materialize(template() if value is None else value,**options)

    def test_actual_native_parameters_all_affect_input_identity(self):
        original={'task_id':'bounded','goal':'Inspect one file','context':None,'toolsets':['terminal'],'role':'leaf','max_iterations':20}
        first=self.bind(descriptor=original)
        encoded=json.dumps(original,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode('utf-8')
        self.assertEqual(hashlib.sha256(encoded).hexdigest(),first['input_sha256'])
        for key,value in {'task_id':'other','goal':'Change one file','context':'More context','toolsets':['none'],'role':'orchestrator','max_iterations':21}.items():
            changed={**original,key:value}
            with self.subTest(field=key):self.assertNotEqual(first['input_sha256'],self.bind(descriptor=changed)['input_sha256'])

    def test_template_cannot_spoof_controller_fields(self):
        for field,value in {'task_id':'other','input_sha256':'c'*64,'as_of':'2020-01-01T00:00:00Z','continuation':None}.items():
            candidate=template();candidate[field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):self.bind(candidate)
        for field in ('host','transport'):
            candidate=template();candidate['requirements'][field]='other'
            with self.subTest(field=field),self.assertRaises(ValueError):self.bind(candidate)

    def test_invalid_or_nonfinite_inputs_are_not_silently_coerced(self):
        for descriptor in ({1:'coerced'}, {'nested':[float('nan')]}, {'nested':float('inf')}, {'tuple':('x',)}, {'object':Path('x')}):
            with self.subTest(type=str(type(descriptor))),self.assertRaises(ValueError):self.bind(descriptor=descriptor)
        for version in (True,3.0,'3'):
            candidate=template();candidate['schema_version']=version
            with self.subTest(version=version),self.assertRaises(ValueError):self.bind(candidate)

    def test_descriptor_order_is_irrelevant_but_json_types_remain_distinct(self):
        self.assertEqual(self.bind(descriptor={'a':1,'b':2})['input_sha256'],self.bind(descriptor={'b':2,'a':1})['input_sha256'])
        self.assertNotEqual(self.bind(descriptor={'x':1})['input_sha256'],self.bind(descriptor={'x':True})['input_sha256'])

    def test_explicit_unknowns_and_caller_data_are_preserved(self):
        source=template();before=copy.deepcopy(source);bound=self.bind(source)
        self.assertEqual(source,before)
        self.assertIsNone(bound['budget']['api_remaining'])
        self.assertIsNone(bound['requirements']['model'])
        self.assertEqual(source['verifier'],bound['verifier'])
        bound['budget']['quotas']['synthetic-pool']['remaining']=0
        self.assertEqual(source,before)

    def test_executor_binds_actual_input_without_changing_its_claimed_protocol(self):
        source=template();source['deterministic']={'executor_id':'synthetic','artifact_sha256':'c'*64,
            'task_contract_sha256':'d'*64,'coverage':'complete','effects':'reversible'}
        bound=self.bind(source)
        self.assertEqual(bound['input_sha256'],bound['deterministic']['input_sha256'])
        self.assertEqual('d'*64,bound['deterministic']['task_contract_sha256'])
        source['deterministic']['input_sha256']='f'*64
        with self.assertRaises(ValueError):self.bind(source)

    def test_invalid_time_and_task_schema_fail_before_dispatch(self):
        with self.assertRaises(ValueError):self.bind(as_of='not-a-date')
        for change in ({'attempt_cap':0},{'allow_api_spend':'false'},{'api_remaining':-1}):
            source=template();source['budget'].update(change)
            with self.subTest(change=change),self.assertRaises(ValueError):self.bind(source)

    def test_refresh_time_is_separate_from_execution_identity(self):
        first=self.bind();second=self.bind(as_of='2026-09-06T00:01:00Z')
        self.assertEqual(first['input_sha256'],second['input_sha256'])
        self.assertNotEqual(first['as_of'],second['as_of'])

if __name__=='__main__':unittest.main()
