"""Raw treatment fidelity; pure checks, no native process or model call."""
import base64
import copy
import hashlib
import json
from pathlib import Path
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import evaluation_evidence as evidence
import evaluation_hermes_worker as worker
from evaluation_usage import NativeUsageObserver,skill_body

ENTRY=b'---\nname: example\ndescription: Source analysis\n---\nUse the original supported tools and verify the result.'
KEY=hashlib.sha256(ENTRY).hexdigest()

def study_job(assembly=False):
    return {'purpose':'native-skill-study','assembly_only':assembly,
      'intervention_clearance':{'contract':{'skill_evaluation':{
        'question':'applied-skill-effect','arm':'treatment','target_entry_sha256':KEY,'exposure':'controlled-body'}},
        'source_bytes':{KEY:base64.b64encode(ENTRY).decode()}}}

class RawTreatmentFidelity(unittest.TestCase):
    def test_real_entry_and_absent_baseline(self):
        contract=study_job()['intervention_clearance']['contract']
        contract.update(evaluation_stage='skill-actor',source_requirements=[{'sha256':KEY,'excerpt':'original supported tools'}])
        review={'evaluation_stage':'skill-actor','user_intent_fit':'supported','skill_question':'applied-skill-effect'}
        body=skill_body(ENTRY)
        self.assertTrue(evidence.skill_question_readiness({'catalog':[{'entry_sha256':KEY}]},contract,{'task_input':body},review,{KEY:ENTRY})['ready'])
        baseline=copy.deepcopy(contract);baseline['skill_evaluation']['arm']='baseline'
        self.assertTrue(evidence.skill_question_readiness({'catalog':[]},baseline,{'task_input':'same scenario'},review,{KEY:ENTRY})['ready'])
        self.assertFalse(evidence.skill_question_readiness({'catalog':[]},contract,{'task_input':'replacement guide'},review,{KEY:ENTRY})['ready'])
        contract['source_requirements']=[]
        self.assertFalse(evidence.skill_question_readiness({'catalog':[{'entry_sha256':KEY}]},contract,{'task_input':body},review,{KEY:ENTRY})['ready'])

    def test_direct_entry_cannot_be_relabelled(self):
        def no_factory(**kwargs):self.fail('Native construction must not occur')
        for purpose in (None,'native-runtime-smoke','native-tool-study'):
            value=study_job();value.pop('purpose')
            if purpose is not None:value['purpose']=purpose
            with self.subTest(purpose=purpose),self.assertRaisesRegex(ValueError,'requires native-skill-study purpose'):
                worker.execute_skill_study(value,None,no_factory,lambda agent:'',NativeUsageObserver())
        for assembly in (0,'false',None):
            value=study_job();value['assembly_only']=assembly
            with self.subTest(assembly=assembly),self.assertRaisesRegex(ValueError,'must be boolean'):
                worker.prepare_skill_study_entry(value,NativeUsageObserver())

    def test_paid_entry_requires_required_and_ready(self):
        for result in ({'required':False},{'required':True,'ready':False}):
            with patch.object(worker,'require_worker_study_admission',return_value=result),self.assertRaisesRegex(ValueError,'Required ready'):
                worker.prepare_skill_study_entry(study_job(),NativeUsageObserver())
        observer=NativeUsageObserver()
        with patch.object(worker,'require_worker_study_admission',return_value={'required':True,'ready':True}) as gate:
            worker.prepare_skill_study_entry(study_job(),observer)
            self.assertEqual(gate.call_count,1)
        self.assertEqual(observer.skill_context['entry'],ENTRY)
        forged=study_job();forged['_checked_study_admission']=True
        with patch.object(worker,'require_worker_study_admission',side_effect=ValueError('unqualified')) as gate:
            with self.assertRaisesRegex(ValueError,'unqualified'):
                worker.prepare_skill_study_entry(forged,NativeUsageObserver())
            self.assertEqual(gate.call_count,1)

    def test_assembly_discovery_initializes_without_paid_admission(self):
        value=study_job(True)
        value['intervention_clearance']['contract']['skill_evaluation'].update(
            question='natural-discovery',exposure='native-discovery',qualification_boundary='before-material-action')
        observer=NativeUsageObserver()
        with patch.object(worker,'require_worker_study_admission',side_effect=AssertionError('No paid gate on assembly')):
            worker.prepare_skill_study_entry(value,observer)
        self.assertIsNotNone(observer.discovery)
        self.assertFalse(observer.skill_context['expected_present'])
        value['intervention_clearance']['contract']['skill_evaluation']['qualification_boundary']='after-action'
        with self.assertRaisesRegex(ValueError,'Discovery qualification boundary'):
            worker.prepare_skill_study_entry(value,NativeUsageObserver())

    def test_actual_raw_body_and_baseline_absence(self):
        request=lambda text:SimpleNamespace(content=json.dumps({'input':[{'role':'user','content':text}]}).encode())
        observer=NativeUsageObserver();worker.configure_study_exposure(study_job(),observer)
        observer.guard_skill_request(request(skill_body(ENTRY)))
        observer=NativeUsageObserver();worker.configure_study_exposure(study_job(),observer)
        with self.assertRaises(RuntimeError):observer.guard_skill_request(request('replacement guide'))
        value=study_job();value['intervention_clearance']['contract']['skill_evaluation']['arm']='baseline'
        observer=NativeUsageObserver();worker.configure_study_exposure(value,observer)
        with self.assertRaises(RuntimeError):observer.guard_skill_request(request(skill_body(ENTRY)))

    def test_actual_interfaces_match_qualification(self):
        schemas=[{'type':'function','function':{'name':'product_query','parameters':{'type':'object'}}},
                 {'type':'function','function':{'name':'read_file','parameters':{'type':'object'}}}]
        value={'assembly_only':False,'intervention_clearance':{'qualification':{'native':{'effective_tool_schemas':schemas}}}}
        worker.require_qualified_study_interfaces(value,list(reversed(schemas)))
        with self.assertRaises(ValueError):worker.require_qualified_study_interfaces(value,[schemas[1]])
        changed=copy.deepcopy(schemas);changed[0]['function']['parameters']={'type':'string'}
        with self.assertRaises(ValueError):worker.require_qualified_study_interfaces(value,changed)

    def test_package_is_not_rewritten(self):
        frame={'package_sha256':'original','entry_sha256':KEY,'files':{'SKILL.md':KEY},'file_sizes':{'SKILL.md':len(ENTRY)}}
        value={'catalog':[{'path':'example/SKILL.md','package_sha256':'original','body_sha256':KEY,'files':frame['files'],'file_sizes':frame['file_sizes']}]}
        with patch('artifact_hash.freeze_candidate',return_value=frame):worker.require_study_packages_unchanged(value)
        changed={**frame,'entry_sha256':hashlib.sha256(b'replacement').hexdigest()}
        with patch('artifact_hash.freeze_candidate',return_value=changed),self.assertRaises(RuntimeError):worker.require_study_packages_unchanged(value)

    def test_setup_failure_has_no_product_verdict(self):
        result=evidence.intervention_conclusion({'ready':False},{'selected':False})
        self.assertIsNone(result['product_quality_passed'])
        self.assertIsNone(result['mechanism_effect'])
        self.assertIn('cancel',result['next_action'])

if __name__=='__main__':unittest.main()
