"""Pure consistency checks for recorded evaluation evidence, not execution proof.

The supplied suite is the decision oracle. Decision and receipt semantics belong
to eval.py; this module reuses them rather than maintaining a second rulebook.
Only documented result/run locations are traversed. Missing attempt evidence is
reported explicitly, including for interrupted or otherwise truthful failures.
"""
from __future__ import annotations

import importlib.util
import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any

_spec = importlib.util.spec_from_file_location("_evidence_evaluator", Path(__file__).with_name("eval.py"))
assert _spec and _spec.loader
evaluator = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(evaluator)
import evaluation_runtime as runtime

ARTIFACT_KEYS = ("candidate_sha256", "baseline_candidate_sha256", "suite_sha256", "harness_sha256", "candidate_prompt_sha256", "baseline_prompt_sha256")
STACK_KEYS = (
    "model", "provider", "reasoning", "tool_policy", "prompt_assembly",
    "context_policy", "equivalence_group", "judge_model", "judge_provider",
    "judge_reasoning", "judge_tool_policy", "judge_panel", "runtime_lane",
)
SIDES = ("baseline", "candidate")


def native_accounting_claim(contract, review, source_bytes):
    """Supported pre-spend claim, distinct from future receipt completeness.

    This native collector observes its own invocation, not surrounding app
    inference. Script availability cannot establish absence of that inference.
    """
    contract=contract if isinstance(contract,dict) else {}
    review=review if isinstance(review,dict) else {}
    source_bytes=source_bytes if isinstance(source_bytes,dict) else {}
    gaps=[];claim=contract.get('accounting_claim')
    if not isinstance(claim,dict):
        gaps.append('explicit pre-run accounting/reporting scope required')
    else:
        if (set(claim)!={'scope','purpose','outside_invocation_costs','basis'}
                or claim.get('scope')!='instrumented-native-invocations'
                or claim.get('purpose')!='bounded-experiment'
                or claim.get('outside_invocation_costs')!='not-collected'):
            gaps.append('native transport cannot admit whole-workflow completeness/adoption claims; only explicitly scoped invocation experiments are qualified')
        basis=claim.get('basis',{})
        data=source_bytes.get(basis.get('sha256')) if isinstance(basis,dict) else None
        if (not isinstance(data,bytes) or hashlib.sha256(data).hexdigest()!=basis.get('sha256')
                or not isinstance(basis.get('excerpt'),str) or not basis['excerpt']
                or basis['excerpt'].encode() not in data):
            gaps.append('accounting scope lacks supplied source-bound capability/limitation evidence')
        if review.get('accounting_claim_scope')!='instrumented-native-invocations':
            gaps.append('independent pre-run review did not acknowledge the restricted accounting claim')
    return {'ready':not gaps,'gaps':gaps,'scope':'instrumented-native-invocations',
        'reporting_label':'Bounded experiment: instrumented native invocation usage; surrounding app coordination, support and setup costs are outside this collector.',
        'whole_workflow_complete':False,'whole_workflow_adoption_supported':False,
        'future_receipts_complete':None,
        'permitted_conclusions':['bounded functionality/semantic observations','recorded native invocation usage'],
        'limit':'Actual invocation receipts still require reconciliation. A later full-workflow claim needs separately qualified outside-invocation observability; no historical recovery or guessed zero is assumed.'}


def output_review_readiness(binding, contract, review, source_bytes):
    """Require case-specific collection/schema controls before native spend.

    Consume recorded bytes only; never import/execute receipt-selected paths.
    Independent review still owns semantic adequacy and control relevance.
    """
    binding=binding if isinstance(binding,dict) else {}
    contract=contract if isinstance(contract,dict) else {}
    review=review if isinstance(review,dict) else {}
    source_bytes=source_bytes if isinstance(source_bytes,dict) else {}
    gaps=[];declared=contract.get('output_review')
    if not isinstance(declared,dict):
        return {'ready':False,'gaps':['source-bound output collector/schema qualification required']}
    if declared.get('output_kind') not in ('text','program','artifact','rendered-product'):
        gaps.append('unknown output review kind')
    values={}
    for name in ('collector_sha256','schema_sha256','qualification_sha256'):
        value=declared.get(name);data=source_bytes.get(value) if isinstance(value,str) else None
        if not isinstance(data,bytes) or len(data)>1024*1024 or hashlib.sha256(data).hexdigest()!=value:
            gaps.append('missing/stale output review '+name)
        else:values[name]=data
    try:
        q=json.loads(values.get('qualification_sha256',b'null'))
        if not isinstance(q,dict):raise ValueError('qualification object required')
        if any(q.get(k)!=declared.get(k) for k in ('collector_sha256','schema_sha256','output_kind')):
            gaps.append('collection controls belong to different collector/schema/kind')
        if q.get('case_project_sha256')!=binding.get('project_sha256'):
            gaps.append('collection controls do not qualify this actual case/project')
        if review.get('collection_qualification_sha256')!=declared.get('qualification_sha256'):
            gaps.append('independent review did not bind collection qualification')
        admission_key=declared.get('admission_key')
        if not isinstance(admission_key,str) or not admission_key or len(admission_key)>64:
            raise ValueError('explicit collector admission field required')
        invocation=declared.get('invocation')
        if (not isinstance(invocation,dict) or invocation.get('kind')!='python-script-input-schema'
                or not re.fullmatch(r'[0-9a-f]{64}',invocation.get('interpreter_sha256',''))):
            raise ValueError('reviewed collector invocation required')
        dependencies=invocation.get('dependencies')
        if not isinstance(dependencies,dict):raise ValueError('explicit collector dependency inventory required')
        controls=q.get('controls',[])
        if not isinstance(controls,list) or not controls:raise ValueError('executed collection controls required')
        expected=set();inputs=set()
        for control in controls:
            want=control.get('expected_admission');got=control.get('observed_admission')
            if type(want) is not bool or type(got) is not bool or want is not got:
                gaps.append('collection counterexample did not receive its required outcome')
            else:expected.add(want)
            for key in ('input_sha256','output_sha256'):
                value=control.get(key);data=source_bytes.get(value) if isinstance(value,str) else None
                if not isinstance(data,bytes) or hashlib.sha256(data).hexdigest()!=value:
                    gaps.append('collection control input/output bytes missing or stale')
            output=json.loads(source_bytes.get(control.get('output_sha256'),b'null'))
            if not isinstance(output,dict) or type(output.get(admission_key)) is not bool or output[admission_key] is not got:
                gaps.append('recorded collection outcome disagrees with executed output')
            if control.get('input_sha256') in inputs:gaps.append('duplicate collection control input')
            inputs.add(control.get('input_sha256'))
            execution=control.get('execution',{})
            argv=execution.get('argv');cwd=Path(execution.get('cwd',''))
            # The supported recipe is deliberately narrow: Python runs the
            # collector as its script, receiving the input and schema as files.
            # Presence anywhere in argv/the project does not prove invocation.
            if (not isinstance(argv,list) or len(argv)!=4 or not cwd.is_absolute()
                    or any(not isinstance(arg,str) for arg in argv)
                    or argv[1].startswith('-')):
                raise ValueError('collector command must be interpreter, script, input, schema')
            paths=[str((Path(arg) if Path(arg).is_absolute() else cwd/arg).resolve()) for arg in argv]
            argument_hashes=[invocation['interpreter_sha256'],declared['collector_sha256'],
                      control.get('input_sha256'),declared['schema_sha256']]
            if len(set(paths))!=4 or any(execution.get('entry_sources',{}).get(path)!=value for path,value in zip(paths,argument_hashes)):
                gaps.append('collector invocation/script/input/schema differs from captured command files')
            for name,value in dependencies.items():
                if (not isinstance(name,str) or Path(name).is_absolute() or '..' in Path(name).parts
                        or execution.get('source_tree_before',{}).get(name)!=value
                        or not isinstance(source_bytes.get(value),bytes)
                        or hashlib.sha256(source_bytes[value]).hexdigest()!=value):
                    gaps.append('collector dependency source missing or stale')
            if (execution.get('termination')!='returned' or execution.get('exit_code')!=0
                    or execution.get('source_unchanged') is not True
                    or execution.get('entry_sources_unchanged') is not True
                    or execution.get('stdout_sha256')!=control.get('output_sha256')):
                gaps.append('collection controls lack executed source/output linkage')
        if expected!={True,False}:gaps.append('collection needs an adequate acceptance and meaningful broken rejection')
    except (KeyError,TypeError,ValueError,AttributeError):gaps.append('malformed collection qualification')
    return {'ready':not gaps,'gaps':sorted(set(gaps)),
            'scope':'Recorded case/collector/schema controls; not authenticated execution or automatic semantic proof'}


def receiver_assignment(assignment, source_bytes):
    """Resolve a receiver's slot against the frozen four-session plan."""
    ref=assignment['invocation_scope_sha256'];raw=source_bytes[ref]
    if hashlib.sha256(raw).hexdigest()!=ref:raise ValueError('Changed invocation scope')
    slots=json.loads(raw)['session_ids_reserved']
    names={'coordinator-base','coordinator-treatment','receiver-base','receiver-treatment'}
    if set(slots)!=names or len(set(slots.values()))!=4 or any(not isinstance(v,str) or not v for v in slots.values()):
        raise ValueError('Session assignments must be distinct and complete')
    slot=assignment['receiver_slot']
    if slot not in ('receiver-base','receiver-treatment') or assignment['receiver_run_id']!=slots[slot]:
        raise ValueError('Receiver slot/run differs from frozen assignment')
    producer='coordinator-base' if slot=='receiver-base' else 'coordinator-treatment'
    return {'receiver_slot':slot,'receiver_run_id':slots[slot],'producer_slot':producer,'producer_run_id':slots[producer]}


def fresh_receiver_input(task, producer_bytes, source_bytes, common_tree, assignment):
    """Join exact completed coordinator output to a new receiver, not its history.

    Private receipts stay with the controller; only final text enters the task.
    This is captured linkage, never authenticated execution or semantic proof.
    """
    from evaluation_measurement import digest
    expected=receiver_assignment(assignment,source_bytes)
    producer=json.loads(producer_bytes)
    final=producer.get('final_response')
    if (producer.get('ok') is not True or producer.get('model_launched') is not True
            or producer.get('assembly_only') is not False
            or producer.get('session_boundary',{}).get('role')!='coordinator'
            or not isinstance(final,str) or not final.strip() or len(final.encode())>65536):
        raise ValueError('Receiver requires a completed captured coordinator, not assembly or a replacement answer')
    ref=producer['request_recording'];raw=source_bytes[ref['manifest_sha256']]
    if ref.get('complete') is not True or hashlib.sha256(raw).hexdigest()!=ref['manifest_sha256']:
        raise ValueError('Coordinator request recording missing or changed')
    manifest=json.loads(raw);value=hashlib.sha256(final.encode()).hexdigest()
    run=manifest['binding']
    if (manifest.get('complete') is not True
            or run.get('run_id')!=expected['producer_run_id'] or run.get('arm')!=expected['producer_slot']
            or hashlib.sha256(json.dumps(run,sort_keys=True).encode()).hexdigest()!=ref['run_binding_sha256']
            or not any(b['kind']=='final-response' and b['sha256']==value and b['bytes']==len(final.encode()) for b in manifest['blobs'])
            or source_bytes.get(value)!=final.encode()
            or producer.get('final_response_sha256')!=value
            or producer['session_boundary'].get('common_tree_sha256')!=digest(common_tree)):
        raise ValueError('Coordinator final bytes/common evidence do not match captured producer')
    joined=task+'\n\n<coordinator-continuation-data>\n'+json.dumps(final,ensure_ascii=False)+'\n</coordinator-continuation-data>'
    return joined,{'producer_receipt_sha256':hashlib.sha256(producer_bytes).hexdigest(),
        'producer_manifest_sha256':ref['manifest_sha256'],'producer_run_id':run['run_id'],
        'arm':run['arm'],'final_response_sha256':value,'common_tree_sha256':digest(common_tree),
        'receiver_task_sha256':hashlib.sha256(task.encode()).hexdigest(),'receiver_assignment':assignment}


def skill_question_readiness(binding,contract,qualification,review,source_bytes):
    """Separate named-skill effect, discovery and transport calibration."""
    from evaluation_usage import skill_body
    binding=binding if isinstance(binding,dict) else {};contract=contract if isinstance(contract,dict) else {}
    qualification=qualification if isinstance(qualification,dict) else {};review=review if isinstance(review,dict) else {};source_bytes=source_bytes if isinstance(source_bytes,dict) else {}
    gaps=[];stage=contract.get('evaluation_stage');spec=contract.get('skill_evaluation')
    if contract.get('tool_scope') is not None and (contract['tool_scope'] not in ('read-only-existing-unittest','read-only-evidence')
            or review.get('tool_scope')!=contract['tool_scope']):
        gaps.append('study tool scope must be supported and acknowledged by the source-bound review')
    if stage not in ('skill-actor','skill-review','transport-calibration','continuation-receiver'):
        gaps.append('explicit evaluation stage required; availability cannot stand in for skill effect')
    if review.get('evaluation_stage')!=stage or review.get('user_intent_fit')!='supported':
        gaps.append('independent review must reconcile experiment stage with actual user intent')
    if stage=='continuation-receiver':
        try:
            from evaluation_measurement import digest
            selected=contract['continuation_binding'];raw=source_bytes[selected['producer_receipt_sha256']]
            if hashlib.sha256(raw).hexdigest()!=selected['producer_receipt_sha256']:raise ValueError()
            task=source_bytes[selected['receiver_task_sha256']].decode('utf-8')
            assignment=contract['receiver_assignment']
            joined,actual=fresh_receiver_input(task,raw,source_bytes,qualification['project_before'],assignment)
            if (actual!=selected or qualification['task_input']!=joined or binding.get('catalog')!=[]
                    or spec is not None or contract.get('tool_scope')!='read-only-evidence'
                    or review.get('continuation_binding_sha256')!=digest(selected)
                    or review.get('receiver_assignment_sha256')!=digest(assignment)):
                raise ValueError()
        except (KeyError,ValueError,TypeError,AttributeError):
            gaps.append('fresh receiver requires exact corresponding completed coordinator output/common evidence and reviewed input binding')
    if stage=='skill-review':
        ref=contract.get('upstream_exposure_sha256');raw=source_bytes.get(ref)
        try:
            if not isinstance(raw,bytes) or hashlib.sha256(raw).hexdigest()!=ref:raise ValueError()
            exposure=json.loads(raw);subjects=exposure['subjects']
            if len(subjects)!=2 or {s['contract']['skill_evaluation']['arm'] for s in subjects}!={'baseline','treatment'}:raise ValueError()
            if len({s['contract']['skill_evaluation']['target_entry_sha256'] for s in subjects})!=1:raise ValueError()
            # Collector-owned private selection joins exposure to the exact
            # anonymous project being admitted, not any qualified old pair.
            selection_ref=contract.get('review_selection_sha256')
            selected_raw=source_bytes.get(selection_ref)
            if (not isinstance(selected_raw,bytes) or len(selected_raw)>4*1024*1024
                    or hashlib.sha256(selected_raw).hexdigest()!=selection_ref
                    or review.get('review_selection_sha256')!=selection_ref):raise ValueError()
            selection=json.loads(selected_raw)
            from evaluation_measurement import digest
            packet=qualification['project_before']
            if (selection['reviewer_task_sha256']!=binding['task_sha256']
                    or selection['packet_tree_sha256']!=binding['project_sha256']
                    or digest(packet)!=binding['project_sha256']):raise ValueError()
            deliveries=selection['deliveries']
            if (len(deliveries)!=2 or {d['label'] for d in deliveries}!={'A','B'}
                    or len({d['manifest_sha256'] for d in deliveries})!=2):raise ValueError()
            run_ids=set();cases=set();plans=set();oracles=set();paths=set()
            for subject in subjects:
                checked=skill_effect_exposure(subject['contract'],subject['native'],source_bytes[subject['manifest_sha256']],source_bytes)
                if not checked['qualified'] or not checked['continue_skill_effect_review']:raise ValueError()
                manifest=json.loads(source_bytes[subject['manifest_sha256']]);run=manifest['binding']
                delivery=next(d for d in deliveries if d['manifest_sha256']==subject['manifest_sha256'])
                if delivery['binding']!=run:raise ValueError()
                run_ids.add(run['run_id']);cases.add(run['case_id']);plans.add(run['plan_sha256']);oracles.add(run['oracle_sha256'])
                recording=subject['native']['request_recording']
                checks_ref=delivery['output_checks_sha256'];checks_raw=source_bytes[checks_ref]
                if hashlib.sha256(checks_raw).hexdigest()!=checks_ref or recording.get('output_checks_sha256')!=checks_ref:raise ValueError()
                checks=json.loads(checks_raw);outcome=checks['outcome']
                if (checks['manifest_sha256']!=subject['manifest_sha256'] or checks['binding']!=run
                        or outcome['oracle_sha256']!=run['oracle_sha256']
                        or outcome['final_tree_sha256']!=digest(delivery['final_tree'])):raise ValueError()
                # This supported lane preserves exact application/response
                # bytes. An aliased view needs its separately audited mapping;
                # arbitrary substituted bytes are never presumed equivalent.
                prefix=delivery['label']+'/source/'
                expected={prefix+name:value for name,value in delivery['final_tree'].items()}
                expected[delivery['label']+'/explanation.txt']=outcome['final_response_sha256']
                if not delivery['final_tree'] or any(packet.get(name)!=h for name,h in expected.items()):raise ValueError()
                if any(name in paths for name in expected):raise ValueError()
                paths.update(expected)
            if len(run_ids)!=2 or len(cases)!=1 or len(plans)!=1 or len(oracles)!=1:raise ValueError()
            if any(name.startswith(('A/source/','B/source/')) and name not in paths for name in packet):raise ValueError()
        except (ValueError,TypeError,AttributeError,KeyError,StopIteration):gaps.append('skill-effect reviewer requires qualified exposure joined to this selected A/B output packet and task')
    if stage!='skill-actor':return {'ready':not gaps,'gaps':gaps,'stage':stage}
    try:
        if not isinstance(spec,dict):raise ValueError('declared skill question/exposure required')
        question=spec.get('question');arm=spec.get('arm');entry=source_bytes.get(spec.get('target_entry_sha256'))
        if question not in ('applied-skill-effect','natural-discovery','availability-policy') or arm not in ('baseline','treatment'):
            raise ValueError('unknown skill question/arm')
        if not isinstance(entry,bytes) or hashlib.sha256(entry).hexdigest()!=spec['target_entry_sha256']:raise ValueError('target source missing')
        if spec.get('qualification_boundary'):
            if (question!='natural-discovery' or arm!='treatment' or spec['qualification_boundary']!='before-material-action'
                    or review.get('discovery_boundary')!=spec['qualification_boundary']):
                gaps.append('discovery action boundary requires reviewed one-arm natural qualification scope')
        body=skill_body(entry);target_present=any(f.get('entry_sha256')==spec['target_entry_sha256'] for f in binding.get('catalog',[]))
        if target_present!=(arm=='treatment'):gaps.append('target catalog/absence differs from intended arm')
        exposed=body in qualification.get('task_input','').replace('\r\n','\n')
        if question=='applied-skill-effect':
            if spec.get('exposure')!='controlled-body':gaps.append('applied-skill-effect requires controlled complete body exposure, not optional discovery')
            if exposed!=(arm=='treatment'):gaps.append('controlled target body absent from treatment or contaminates baseline prepared input')
        else:
            if spec.get('exposure')!='native-discovery' or exposed:gaps.append('discovery/availability must not silently inject target body')
            if question=='natural-discovery' and spec.get('outcome_scope')!='discovery-only':gaps.append('discovery probe cannot preclaim applied-skill outcome evidence')
            if question=='availability-policy':
                ref=spec.get('explicit_user_scope',{});data=source_bytes.get(ref.get('sha256'))
                if not isinstance(data,bytes) or hashlib.sha256(data).hexdigest()!=ref.get('sha256') or not ref.get('excerpt') or ref['excerpt'].encode() not in data:
                    gaps.append('availability-policy needs explicit source-bound user scope; generic skill evaluation permission is insufficient')
        if review.get('skill_question')!=question:gaps.append('independent review did not accept the exact skill question')
    except (ValueError,KeyError,TypeError,AttributeError) as exc:gaps.append('skill question unqualified: '+str(exc))
    return {'ready':not gaps,'gaps':gaps,'stage':stage}


def skill_effect_exposure(contract,native,manifest_bytes,source_bytes):
    """Recorded target context prerequisite; never claims cognitive use."""
    from evaluation_usage import request_contains_skill
    gaps=[];rows=[];spec=contract.get('skill_evaluation',{});question=spec.get('question');arm=spec.get('arm')
    try:
        entry=source_bytes[spec['target_entry_sha256']]
        if hashlib.sha256(entry).hexdigest()!=spec['target_entry_sha256']:raise ValueError('target bytes changed')
        recording=native.get('request_recording',{})
        if recording.get('complete') is not True or hashlib.sha256(manifest_bytes).hexdigest()!=recording.get('manifest_sha256'):raise ValueError('complete exact request manifest required')
        manifest=json.loads(manifest_bytes)
        if manifest.get('complete') is not True:raise ValueError('incomplete request trace')
        binding_hash=hashlib.sha256(json.dumps(manifest['binding'],sort_keys=True).encode()).hexdigest()
        if recording.get('run_binding_sha256')!=binding_hash:raise ValueError('recording belongs to a different run')
        for blob in manifest['blobs']:
            if blob['kind']!='final-request':continue
            raw=source_bytes[blob['sha256']]
            if hashlib.sha256(raw).hexdigest()!=blob['sha256'] or len(raw)!=blob['bytes']:raise ValueError('request bytes missing/changed')
            rows.append({'ordinal':len(rows),'request_sha256':blob['sha256'],'target_body_present':request_contains_skill(raw,entry)})
        if not rows or len(rows)!=recording.get('final_request_count'):raise ValueError('request count incomplete')
        if question not in ('applied-skill-effect','natural-discovery','availability-policy'):gaps.append('unknown skill question')
        if arm=='baseline' and any(r['target_body_present'] for r in rows):gaps.append('target body contaminates baseline')
        elif arm=='treatment' and question=='applied-skill-effect' and not rows[0]['target_body_present']:gaps.append('target complete body absent from initial treatment request')
        elif arm not in ('baseline','treatment'):gaps.append('unknown skill arm')
    except (KeyError,ValueError,TypeError,AttributeError) as exc:gaps.append('target exposure unqualified: '+str(exc))
    return {'question':question,'arm':arm,'qualified':not gaps,'gaps':gaps,'requests':rows,
        'continue_skill_effect_review':not gaps and question=='applied-skill-effect',
        'scope':'applied exposure prerequisite' if question=='applied-skill-effect' else 'discovery/availability observations only; no applied-effect conclusion',
        'cognitive_use_proven':False,'actual_behavior_and_quality_review_required':True}


def intervention_readiness(binding, contract, qualification, review, source_bytes):
    """Compare intended mechanism to observed actor-path exercise and task review.

    No filename presence, label or instruction alone is a functional proof.
    This consumes pretrial evidence; actual use is a separate later observable.
    Source/claim/task judgments remain independently reviewable, not automated.
    """
    import evaluation_measurement as m
    gaps=[]
    measured=trial_measurement_preflight(contract.get('measurement'),qualification.get('project_before',{}),source_bytes)
    gaps.extend(measured['gaps'])
    if review.get('measurement_sha256')!=m.digest(contract.get('measurement')):
        gaps.append('independent fit review does not bind the exact measured behavior/observable')
    question=skill_question_readiness(binding,contract,qualification,review,source_bytes)
    gaps.extend(question['gaps'])
    accounting=native_accounting_claim(contract,review,source_bytes)
    gaps.extend(accounting['gaps'])
    collection=output_review_readiness(binding,contract,review,source_bytes)
    gaps.extend(collection['gaps'])
    try:
        if any(m.sha(binding.get(key)) is None for key in
               ('task_sha256','project_sha256','treatment_sha256','harness_sha256','contract_sha256','user_decision_sha256')):
            gaps.append('intervention binding lacks frozen source/task/harness revisions')
        question=source_bytes.get(binding.get('user_decision_sha256'))
        if (not isinstance(question,bytes) or hashlib.sha256(question).hexdigest()!=binding.get('user_decision_sha256')
                or contract.get('user_decision_sha256')!=binding.get('user_decision_sha256')):
            gaps.append('actual user decision question is missing or replaced by a proxy')
        if qualification.get('binding')!=binding:gaps.append('qualification belongs to different treatment/task/runtime bytes')
        if m.digest(contract)!=binding.get('contract_sha256'):gaps.append('intervention contract changed')
        references=contract.get('source_requirements',[])
        if not references:gaps.append('intended mechanism has no source-grounded contract')
        for ref in references:
            data=source_bytes.get(ref.get('sha256'))
            if (not isinstance(data,bytes) or hashlib.sha256(data).hexdigest()!=ref['sha256']
                    or not ref.get('excerpt') or ref['excerpt'].encode() not in data):
                gaps.append('mechanism requirement not grounded in supplied source bytes')
        operations=contract.get('actor_requests',[])
        if not operations:gaps.append('no task-relevant actor capability exercise')
        native=qualification.get('native',{})
        conditions=binding.get('conditions',{})
        expected_route={k:conditions.get(k) for k in ('model','reasoning')}
        expected_route['provider']='openai-codex'
        if (binding.get('host')!='hermes' or native.get('agent_observed_route')!=expected_route
                or native.get('requested_route')!=expected_route
                or native.get('resource_limits',{}).get('timeout_seconds')!=conditions.get('timeout')
                or native.get('resource_limits',{}).get('max_iterations')!=conditions.get('max_iterations')
                or native.get('terminal_backend',{}).get('name')!=conditions.get('terminal_backend')):
            gaps.append('actual qualification host/route/backend/limits differ from reviewed dispatch')
        catalog=native.get('catalog_evidence',{})
        if (not isinstance(binding.get('catalog'),list)
                or catalog.get('package_frames',[])!=binding.get('catalog')
                or catalog.get('native_catalog_names')!=[f['name'] for f in binding.get('catalog',[])]
                or catalog.get('exact_catalog_verified') is not True):
            gaps.append('actual qualified catalog differs from source-reviewed package exposure')
        for frame in binding.get('catalog',[]):
            from artifact_hash import package_hash_from_files
            if frame.get('package_sha256')!=package_hash_from_files(frame['files']):
                gaps.append('catalog package identity does not match its exact file manifest')
            for name,value in frame['files'].items():
                data=source_bytes.get(value)
                if (not isinstance(data,bytes) or hashlib.sha256(data).hexdigest()!=value
                        or len(data)!=frame.get('file_sizes',{}).get(name)):
                    gaps.append('catalog source bytes missing/changed from independent review')
        transport=native.get('capability_transport_guard',{})
        if (native.get('ok') is not True or native.get('assembly_only') is not True
                or native.get('model_launched') is not False or native.get('api_calls')!=0
                or transport.get('enabled') is not True or transport.get('network_attempts')!=0):
            gaps.append('actor-path qualification did not finish without provider calls')
        if qualification.get('project_before')!=qualification.get('project_after'):
            gaps.append('capability qualification changed the starting project')
        if m.digest(qualification.get('project_before'))!=binding.get('project_sha256'):
            gaps.append('capability exercise belongs to a different initial project')
        if native.get('blocked_requests'):gaps.append('required actor operation blocked by real request gate')
        actual=native.get('capability_probes',[])
        advertised={row.get('function',{}).get('name') for row in native.get('effective_tool_schemas',[])}
        if [row.get('request') for row in actual]!=[row['request'] for row in operations]:
            gaps.append('advertised treatment operations were not actually dispatched through actor executor')
        for expected,observed in zip(operations,actual):
            if expected['request']['tool'] not in advertised:
                gaps.append('required interface not advertised to actor')
            if not expected.get('handler_source_sha256') or observed.get('handler_source_sha256')!=expected['handler_source_sha256']:
                gaps.append('executed adapter differs from source-reviewed treatment implementation')
            handler=source_bytes.get(expected.get('handler_source_sha256'))
            if not isinstance(handler,bytes) or hashlib.sha256(handler).hexdigest()!=expected.get('handler_source_sha256'):
                gaps.append('executed adapter source bytes not supplied for independent fidelity review')
            events=[e for e in native.get('events',[]) if e.get('call_id')=='qualification-'+expected['request']['id']]
            if len(events)!=1 or events[0].get('success') is not True or events[0].get('tool')!=expected['request']['tool']:
                gaps.append('required actor operation did not complete successfully: '+expected['request']['id'])
            contents=observed.get('outputs',[])
            text='\n'.join(str(value) for value in contents)
            if (not contents or not expected.get('required_output')
                    or any(word not in text for word in expected['required_output'])):
                gaps.append('actor operation does not satisfy functional treatment contract: '+expected['request']['id'])
        prepared=qualification.get('task_input','')
        task=source_bytes.get(binding.get('task_sha256'))
        if (not isinstance(task,bytes) or hashlib.sha256(task).hexdigest()!=binding.get('task_sha256')
                or task.decode('utf-8') not in prepared):
            gaps.append('actual task bytes missing from effective prepared input')
        if hashlib.sha256(prepared.encode()).hexdigest()!=native.get('prepared_task_sha256'):
            gaps.append('effective task/guidance input not bound')
        if not contract.get('guidance_fragments') or any(fragment not in prepared for fragment in contract['guidance_fragments']):
            gaps.append('intended treatment guidance absent from actual prepared input')
        # Review is bound to starting evidence, not an outcome-conditioned label.
        expected_review={'binding_sha256':m.digest(binding),'qualification_sha256':m.digest(qualification)}
        if (review.get('reviewed')!=expected_review or not review.get('reviewer')
                or review.get('phase')!='before-actors' or review.get('independent') is not True
                or not isinstance(review.get('findings'),str) or not review['findings'].strip()):
            gaps.append('source-bound independent mechanism/task suitability review missing')
        if review.get('decision')!='accept':gaps.append('pretrial review rejected/reclassified design; resolve scope before spending')
        if not review.get('decision_scope_evidence'):gaps.append('fit to actual user decision question unreviewed')
        if review.get('mechanism_fidelity')!='supported':gaps.append('required treatment behavior omitted or misrepresented')
        if review.get('claim_task_fit')!='supported':gaps.append('task does not support the stated mechanism/claim')
        if review.get('claim_scope')!=contract.get('claim'):gaps.append('reviewed conclusion scope differs from intended claim')
    except (KeyError,TypeError,ValueError,AttributeError) as exc:
        gaps.append('malformed intervention evidence: '+type(exc).__name__)
    return {'ready':not gaps,'gaps':sorted(set(gaps)),'accounting_claim':accounting,
            'actual_usage_required':False,'mechanism_efficacy_proven':False,'execution_authenticated':False,
            'scope':'Pretrial source-grounded fidelity, functional actor-path exercise and independently reviewed task fit; usage remains optional'}


def intervention_conclusion(design, exposure):
    """Do not convert nonselection, access failure or trace gaps into utility."""
    if not design.get('ready'):
        return {'scope':'unqualified integration/task design','mechanism_effect':None,'usage_required':False}
    if design.get('question')=='applied-skill-effect':
        qualified=exposure.get('qualified') is True and exposure.get('continue_skill_effect_review') is True
        return {'scope':'controlled target context verified; actual behavior/quality pending' if qualified else 'skill-effect qualification failed; do not invoke qualitative reviewer',
            'mechanism_effect':None,'continue_skill_effect_review':qualified,'usage_required':True,'natural_discovery_proven':False}
    if exposure.get('trace_complete') is not True:
        return {'scope':'actual use unknown; exposure evidence incomplete','mechanism_effect':None,'usage_required':False}
    if exposure.get('selected') is False:
        return {'scope':'nonselection: skill-effect qualification failed; availability alone does not answer applied effect','mechanism_effect':None,
                'continue_skill_effect_review':False,
                'causal_limit':'No mechanism-use benefit or harm inferred; matched availability-policy outcomes remain reportable separately', 'usage_required':False}
    return {'scope':'mechanism exposure observed; comparative outcome/cost evidence still required',
            'mechanism_effect':None,'usage_required':False}


def adoption_qualification(report, suite):
    try:
        result = _adoption_qualification(report, suite)
    except (KeyError, TypeError, ValueError, AttributeError, IndexError) as exc:
        result = {'ready':False,'gaps':['malformed methodological evidence: '+type(exc).__name__]}
    # Preserve the explicit lane boundary even when other evidence is malformed.
    if isinstance(suite,dict) and any(
            c.get('acceptance_review',{}).get('task_qualification',{}).get('output_kind') != 'text'
            for c in suite.get('cases',[]) if isinstance(c,dict)):
        result['ready']=False
        result['gaps']=sorted(set(result['gaps']+[
            'inline text lane cannot qualify non-text program/artifact/rendered-product claims; use the corresponding source-bound artifact review']))
    return result


def _adoption_qualification(report, suite):
    """Necessary methodological gates, never automatic semantic/origin proof."""
    import evaluation_measurement as measurement
    gaps = []
    preflight = evaluator.oracle_preflight(suite)
    gaps.extend(preflight['errors'])
    design=evaluator.text_intervention_review(suite,report.get('input_snapshot',{}).get('candidate') or {},
                                              report.get('input_snapshot',{}).get('baseline'))
    gaps.extend(design['errors'])
    gaps.extend(supporting_evidence_errors(report))
    records = measurement.inline_records(report)
    job = measurement.whole_job_readiness(records, report.get('whole_job_manifest'),
                                          suite.get('whole_job_manifest_sha256'))
    gaps.extend(job['gaps'])
    if set((report.get('whole_job_manifest') or {}).get('arms',[]))!=set(SIDES):
        gaps.append('binary adoption requires exactly baseline/candidate accounting arms')
    if job.get('comparison_view')=='recurring-reuse' and any(
            row.get('trial_validity',{}).get('benchmark_scenario')!='steady-state'
            for row in records if not measurement._auxiliary(row)):
        gaps.append('reuse exclusions do not match actual benchmark scenario')
    efficiency=outcome_efficiency(
        [row for row in records if row.get('identity',{}).get('arm')!='candidate'],
        [row for row in records if row.get('identity',{}).get('arm')!='baseline'],whole_job=job)
    gaps.extend(efficiency['errors'])
    # Runtime/program claims cannot be promoted by final-answer text judges.
    if any(c.get('acceptance_review', {}).get('task_qualification', {}).get('output_kind') != 'text'
           for c in suite.get('cases', [])):
        gaps.append('inline text lane cannot qualify non-text program/artifact/rendered-product claims; use the corresponding source-bound artifact review')
    return {'ready': not gaps, 'gaps': sorted(set(gaps)), 'whole_job': job, 'efficiency':efficiency,
            'scope': 'Necessary recorded gates; reviewer judgment/identity and claim realism are not automatically proven'}


def supporting_evidence_errors(report):
    """Validate an explicit supporting-receipt attachment, not task attempts."""
    import evaluation_measurement as m
    rows=report.get('supporting_receipts',[])
    if not rows and not report.get('supporting_evidence_source'):return []
    errors=[]
    try:
        source=report['supporting_evidence_source']
        if hashlib.sha256(source.encode()).hexdigest()!=report.get('supporting_evidence_sha256'):
            errors.append('supporting source bytes changed')
        data=evaluator.extract_json(source)
        if data.get('binding')!={key:report['artifacts'].get(key) for key in
                ('suite_sha256','candidate_sha256','baseline_candidate_sha256','harness_sha256')}:
            errors.append('supporting receipt task/instruction/harness binding changed')
        if rows!=data.get('receipts'):errors.append('supporting receipts differ from source attachment')
        calls={row['call_id']:row for row in report['whole_job_manifest']['calls']}
        seen=set()
        for item in rows:
            account=item['workflow_accounting'];ident=account['call_id'];declared=calls[ident]
            if ident in seen:errors.append('duplicate supporting receipt')
            seen.add(ident)
            if any(account.get(k)!=declared.get(k) for k in ('run_id','target_arm','cost_class')):
                errors.append('supporting receipt attribution differs from frozen inventory')
            if not item['identity'].get('role') or not item.get('host_version'):
                errors.append('supporting native identity/version missing')
            observed=item['run'].get('agent_observed_route') or item['run'].get('route_attestation',{}).get('observed',{})
            if any(observed.get(k)!=item['route'].get(k) or not observed.get(k) for k in ('model','provider','reasoning')):
                errors.append('supporting native route mismatch')
            if declared.get('route') and declared['route']!=item['route']:
                errors.append('supporting receipt route differs from declared role')
            if m.observed_usage(item['run'],item['host'])['accounting_reconciliation'] is None:
                errors.append('supporting receipt has no complete native usage reconciliation')
    except (KeyError,TypeError,ValueError,AttributeError) as exc:
        errors.append('malformed supporting evidence: '+type(exc).__name__)
    return errors


def artifact_runtime_ok(row, record, spec):
    """Legacy runtime/invariant status, never a semantic task-quality verdict."""
    checked=row.get('oracle', {})
    expected=(record.get('outcome', {}).get('execution_ok') is True and row.get('oracle_exit_code')==0
        and type(checked.get('passed')) is int and checked['passed']>0
        and type(checked.get('failed')) is int and checked['failed']==0 and checked.get('failures')==[])
    provenance=record.get('outcome', {}).get('assessment_dimensions', {}).get('execution_provenance', {})
    if provenance.get('required') is True:
        from evaluation_artifact_pilot import program_matches_final
        expected=bool(expected and program_matches_final(row.get('oracle_execution',{}),row['final_tree']))
    if spec.get('request_recording_parent'):
        expected=expected and row.get('request_recording',{}).get('complete') is True
    return expected


def strict_review_json(text):
    def pairs(items):
        result={}
        for key,value in items:
            if key in result:raise ValueError('duplicate review key')
            result[key]=value
        return result
    def constant(value):raise ValueError('nonfinite review value')
    return json.loads(text,object_pairs_hook=pairs,parse_constant=constant)


def substantive_review(parsed, packet_files, source_bytes):
    """Resolve cited packet evidence and reject internally unsound preference.

    This establishes source consistency, not that a reason is true or a reviewer
    is independent. No receipt-selected path is opened or code executed.
    """
    gaps=[];resolved=[];dimensions={}
    def text_or_list(value,nonempty=False):
        if isinstance(value,str):return bool(value.strip())
        return isinstance(value,list) and (not nonempty or bool(value)) and all(isinstance(v,str) and bool(v.strip()) for v in value)
    def strings(value):
        if isinstance(value,str):return [value]
        if isinstance(value,list):return [text for item in value for text in strings(item)]
        if isinstance(value,dict):return [text for item in value.values() for text in strings(item)]
        return []
    try:
        deliveries=parsed['deliveries']
        if set(deliveries)!={'A','B'}:raise ValueError('two anonymous deliveries required')
        program_key='program_adequacy' if 'program_adequacy' in deliveries['A'] else 'semantic_adequacy'
        handoff_key='handoff_adequacy' if 'handoff_adequacy' in deliveries['A'] else 'explanation_utility'
        preference_keys=('comparative_program_preference','comparative_handoff_preference') if program_key=='program_adequacy' else ('comparative_preference','explanation_preference')
        for label,row in deliveries.items():
            if any(row.get(k) not in ('adequate','inadequate','uncertain') for k in (program_key,handoff_key)):
                gaps.append(label+': adequacy missing/invalid')
            if not text_or_list(row.get('limitations')):
                gaps.append(label+': limitations missing/invalid')
            evidence=row.get('evidence')
            structured=(program_key=='semantic_adequacy' and isinstance(evidence,list) and bool(evidence)
                and all(isinstance(item,dict) and text_or_list(item.get('locations'),True)
                    and isinstance(item.get('reason'),str) and bool(item['reason'].strip())
                    and ('aspect' not in item or isinstance(item['aspect'],str) and bool(item['aspect'].strip())) for item in evidence))
            if not (text_or_list(evidence,True) or structured):gaps.append(label+': evidence missing/invalid')
            count=0
            for text in strings(row.get('evidence')):
                for match in re.finditer(r'(?<![\w/])((?:A|B|starting-source)/[A-Za-z0-9_.@+-]+(?:/[A-Za-z0-9_.@+-]+)*)(?::(\d+)(?:-(\d+))?)?',text):
                    name=match[1].rstrip('.');digest=packet_files.get(name);data=source_bytes.get(digest)
                    if not isinstance(data,bytes) or hashlib.sha256(data).hexdigest()!=digest:
                        gaps.append('unresolved review evidence: '+name);continue
                    if match[2]:
                        start=int(match[2]);end=int(match[3] or start)
                        try:length=len(data.decode('utf-8-sig').splitlines())
                        except UnicodeError:length=0
                        if not 1<=start<=end<=length:
                            gaps.append('out-of-range review evidence: '+name);continue
                    resolved.append({'delivery':label,'path':name,'sha256':digest,'start':match[2],'end':match[3]})
                    if name.startswith(label+'/'):count+=1
            if not count:gaps.append(label+': no resolved own-delivery evidence')
        limits=parsed.get('overall_limits',parsed.get('overall_limitations'))
        if not text_or_list(limits):gaps.append('overall limitations missing/invalid')
        for dimension,key,preference in zip(('program','handoff'),(program_key,handoff_key),preference_keys):
            choice=parsed.get(preference)
            if choice not in ('A','B','tie','inconclusive'):gaps.append('invalid '+dimension+' preference')
            adequate=[label for label in ('A','B') if deliveries[label].get(key)=='adequate']
            if len(adequate)==1 and choice not in (adequate[0],'inconclusive'):
                gaps.append(dimension+': preference contradicts adequacy')
            if choice in ('A','B') and deliveries[choice].get(key)!='adequate':
                gaps.append(dimension+': preferred delivery is not adequate')
            dimensions[dimension]={'preference':choice,'adequacy':{label:deliveries[label].get(key) for label in ('A','B')}}
    except (KeyError,TypeError,ValueError,AttributeError):gaps.append('malformed substantive review')
    return {'ready':not gaps,'gaps':sorted(set(gaps)),'resolved_evidence':resolved,'dimensions':dimensions,
        'semantic_truth_automatically_proven':False}


def rendered_outcome_decision(report, attachment, source_bytes):
    """Join a scoped human judgment to finished renders; never fabricate a judge.

    This checks bindings and consumes explicit semantic assessments. It cannot
    discover omitted requirements, authenticate a human or infer task success
    from a preference. Positive release/efficiency controls remain separate.
    """
    import evaluation_measurement as m
    gaps=[]
    def raw(sha):
        data=source_bytes.get(sha)
        if not isinstance(data,bytes) or hashlib.sha256(data).hexdigest()!=sha:
            raise ValueError('missing/changed outcome evidence: '+str(sha))
        return data
    def doc(sha): return strict_review_json(raw(sha))
    def citation(value):
        excerpt=value.get('excerpt')
        if not isinstance(excerpt,str) or not excerpt.strip() or excerpt not in raw(value['sha256']).decode('utf-8'):
            raise ValueError('outcome citation does not resolve')
    try:
        if attachment.get('output_kind')!='rendered-product': raise ValueError('explicit rendered-product scope required')
        p=doc(attachment['outcome_packet_sha256'])
        if p.get('kind')!='human-rendered-outcome-v1': raise ValueError('unsupported outcome packet')
        # Re-entry receives the wrapper's annotated rows. Bind only the original
        # captured result for BOTH its digest and every source/capture join.
        # Raw outcome_assessment and all unknown/raw fields remain authoritative.
        rows=[{k:v for k,v in row.items()
               if k not in ('completed_review_outcome','completed_outcome_assessment')}
              for row in report['results']]
        ids=[r['id'] for r in rows]
        if len(ids)!=len(set(ids)) or len(ids)<2: raise ValueError('one row per actual invocation required')
        if attachment.get('results_sha256')!=m.digest(rows): raise ValueError('outcome/result binding changed')
        for key in ('product_goal','intervention_description','actor_assignment'): citation(p[key])
        doc(p['assessment_sha256'])
        mapping=doc(p['mapping_sha256']); joins=doc(p['source_joins_sha256'])
        if mapping['source_joins_sha256']!=p['source_joins_sha256']: raise ValueError('mapping/source join changed')
        if {j['id'] for j in joins}!=set(ids) or len(joins)!=len(ids): raise ValueError('incomplete source roster')
        for j in joins:
            r=next(r for r in rows if r['id']==j['id'])
            original=doc(j['report_sha256'])
            if (sum(x==r for x in original['results'])!=1 or m.digest(r['final_tree'])!=j['final_tree_sha256']
                    or j['arm']!=r['arm']):
                raise ValueError('final result/source identity changed')
            if r.get('collection',{}).get('schema_sha256')!=p['assessment_sha256']:
                raise ValueError('assessment differs from collected result schema')
            for sha in r['final_tree'].values(): raw(sha)
        label_ids={}; seen_views=set()
        for view in mapping['views']:
            if view['view'] in seen_views: raise ValueError('duplicate human view identity')
            seen_views.add(view['view'])
            for label in view['map']:
                j=next(j for j in joins if j['id']==label['id'])
                if label['final_tree_sha256']!=j['final_tree_sha256'] or label['arm']!=j['arm']:
                    raise ValueError('label/source identity changed')
                if (view['view'],label['label']) in label_ids: raise ValueError('duplicate human label identity')
                label_ids[(view['view'],label['label'])]=j['id']
        seen=set()
        for cap in mapping['captures']:
            j=next(j for j in joins if j['id']==cap['id'])
            request=doc(cap['request_sha256']); reply=doc(cap['reply_sha256']); delivery=doc(cap['delivery_sha256'])
            raw(cap['capture_sha256'])
            if (cap['final_tree_sha256']!=j['final_tree_sha256'] or request['job_id']!=j['id']
                    or request['artifact_tree_sha256']!=j['final_tree_sha256']
                    or request['artifact_tree']!=next(r for r in rows if r['id']==j['id'])['final_tree']
                    or reply['request_sha256']!=cap['request_sha256'] or reply['request_id']!=request['request_id']
                    or delivery['request_id']!=request['request_id'] or delivery['artifact_tree_sha256']!=j['final_tree_sha256']
                    or reply['state']!=cap['state'] or reply['state_reached'] is not True
                    or reply['capture_sha256']!=cap['capture_sha256'] or delivery['capture_sha256']!=cap['capture_sha256']):
                raise ValueError('render/source/request binding changed')
            seen.add(j['id'])
        if seen!=set(ids): raise ValueError('a judged output has no bound capture')
        human=doc(p['human_judgment_sha256'])
        if human['mapping_sha256']!=p['mapping_sha256']: raise ValueError('stale human judgment mapping')
        raw(human['human_quote_sha256']); raw(human['correction_quote_sha256'])
        if not p.get('human_provenance') or p.get('labels_known') not in (True,False,None):
            raise ValueError('human provenance/label knowledge required')
        # This retained receipt format names two pair views sharing current A.
        # Derive semantic aliases from that actual mapping, never caller choice.
        alias_pairs={'base/B1':('view-1','B'),'current/shared A':('view-1','A'),'edited/B2':('view-2','B')}
        if (set(label_ids)!={('view-1','A'),('view-1','B'),('view-2','A'),('view-2','B')}
                or label_ids[('view-1','A')]!=label_ids[('view-2','A')]
                or p['human_labels']!={name:list(pair) for name,pair in alias_pairs.items()}):
            raise ValueError('human aliases contradict retained pair mapping')
        aliases={name:label_ids[pair] for name,pair in alias_pairs.items()}
        if (len(set(aliases.values()))!=3 or set(aliases.values())!=set(ids)
                or any(next(j for j in joins if j['id']==ident)['arm']!=name.split('/')[0]
                       for name,ident in aliases.items())):
            raise ValueError('human aliases contradict retained arm identities')
        selected=human['selected_visual_copy_direction']
        selected_join=next(j for j in joins if j['id']==selected['id'])
        if (aliases[human['preferred_visual_output']]!=selected['id']
                or any(selected.get(k)!=selected_join[k] for k in ('arm','report_sha256','final_tree_sha256'))):
            raise ValueError('human preferred output contradicts selected artifact')
        preferences=[]
        for relation in human['all_supported_pairwise_preferences']:
            a,b=relation.split(' over ')
            preferences.append({'preferred':aliases[a],'over':aliases[b]})
        unresolved=p['undecided_pair']
        if (human['edited_versus_current']!='undecided' or len(unresolved)!=2 or len(set(unresolved))!=2
                or set(unresolved)!=set(ids)-{selected['id']}):
            raise ValueError('partial-order/undecided judgment changed')
        requirements=p['requirements']
        if not requirements or len({r['id'] for r in requirements})!=len(requirements): raise ValueError('goal requirements missing/duplicated')
        for r in requirements:
            citation(r['goal_citation'])
            if r['goal_citation']['sha256']!=p['product_goal']['sha256']: raise ValueError('requirement not grounded in product description')
            if r['coverage'] not in ('covered','scope-mismatch','unassessed') or r['adequacy'] not in ('adequate','inadequate','unassessed'):
                raise ValueError('explicit coverage/adequacy required')
            if not r['evidence']: raise ValueError('requirement evidence/limit missing')
            for e in r['evidence']: citation(e)
            if r['adequacy']=='adequate' and r['coverage']!='covered': raise ValueError('uncovered outcome cannot pass')
        coverage_failed=any(r['coverage']=='scope-mismatch' for r in requirements)
        # Known scope failure is a terminal non-acceptance, not endless pending.
        # These human preferences alone never establish whole-product adequacy.
        return {'ready':True,'gaps':[], 'execution_complete':all(r.get('ok') is True for r in rows),
            'outcome_coverage':'failed' if coverage_failed else 'partial',
            'finished_result_acceptance':'not-accepted' if coverage_failed else 'not-established',
            'requirements':requirements,'quality_disposition':{'scope':p['judgment_scope'],'preferences':preferences,'undecided_pair':unresolved},
            'deliveries':{i:{'task_passed':None,'reviewed_artifact_adequate':None,'final_source_exactly_reviewed':False,
                'scope':'human visual/copy preference; no whole-product adequacy judgment'} for i in ids},
            'disposition':'do-not-promote-intervention; finish actual product goal' if coverage_failed else 'bounded-human-preference-only',
            'human_provenance':p['human_provenance'],'labels_known':p['labels_known'],'review_identity_authenticated':False,
            'deployment_authority':False,'adoption_authority':False,'whole_workflow_efficiency_qualified':False,
            'source_bound_current_quality':False,'scope':'Description-derived coverage and bound human rendered preference; no causal or release clearance'}
    except (KeyError,TypeError,ValueError,AttributeError,StopIteration) as error:
        gaps.append('malformed rendered outcome: '+str(error))
    return {'ready':False,'gaps':gaps,'finished_result_acceptance':'not-established','deployment_authority':False,'adoption_authority':False}



def completed_artifact_decision(report, attachment, source_bytes, *, plan=None):
    """Consume frozen packet-bound substantive review, without granting rollout.

    Historical replays may establish reviewed-view quality while final-source
    projection or execution provenance remains limited; no backfilled proof.
    """
    measured=trial_review_gate(report,plan,source_bytes)
    if not measured['valid']:
        return {'ready':False,'gaps':measured['gaps'],'measurement_validity':measured,
            'deliveries':{},'quality_disposition':{},'diagnostic_review_only':True,
            'source_bound_current_quality':False,'adoption_authority':False,'deployment_authority':False,
            'scope':'Trial measurement invalid/unassessed; retain raw review, no effect inference'}
    if attachment.get('review_kind') == 'human-rendered-outcome':
        return {**rendered_outcome_decision(report, attachment, source_bytes),'measurement_validity':measured}
    import evaluation_measurement as m
    gaps=[];assessment={};outcomes={}
    def blob(key):
        value=attachment[key];data=source_bytes.get(value)
        if not isinstance(data,bytes) or hashlib.sha256(data).hexdigest()!=value:raise ValueError(key+' bytes unavailable/changed')
        return data
    try:
        if attachment.get('output_kind') not in ('program','text'):
            gaps.append('nonvisual completed-review consumer requires explicit program/text scope; rendered capture/review remains separate')
        packet=strict_review_json(blob('packet_sha256'));review=strict_review_json(blob('review_sha256'));seal=strict_review_json(blob('review_freeze_sha256'))
        for name,value in seal.get('files',{}).items():
            data=source_bytes.get(value)
            if not isinstance(data,bytes) or hashlib.sha256(data).hexdigest()!=value:gaps.append('frozen review member missing/changed: '+name)
        native_hash=seal.get('files',{}).get(attachment.get('native_file'))
        native_data=source_bytes.get(native_hash)
        if not isinstance(native_data,bytes) or hashlib.sha256(native_data).hexdigest()!=native_hash:
            gaps.append('frozen native review receipt missing/changed')
        else:
            native=strict_review_json(native_data)
            if native.get('ok') is not True:gaps.append('reviewer runtime did not complete')
            reply=native.get('final_response')
            if not isinstance(reply,str) or not reply.strip():gaps.append('retained native judgment text missing')
            else:
                authoritative=strict_review_json(reply)
                if authoritative!=review.get('parsed'):gaps.append('parsed review contradicts retained native judgment')
                for name,value in seal.get('files',{}).items():
                    if name.upper().endswith('-RAW.TXT') or name==attachment.get('raw_judgment_file'):
                        if strict_review_json(source_bytes[value])!=authoritative:gaps.append('frozen raw judgment contradicts native reply: '+name)
        if review.get('readonly') is not True or review.get('both_sources_read') is not True:
            gaps.append('reviewer observation/read-only evidence missing')
        if not (review.get('recording_complete') is True or review.get('request_recording',{}).get('complete') is True):
            gaps.append('reviewer request recording incomplete')
        if seal.get('phase')!='before-unblinding':gaps.append('review not frozen before unblinding')
        if seal.get('files',{}).get(attachment['review_file'])!=attachment['review_sha256']:
            gaps.append('raw review differs from freeze')
        if attachment['packet_sha256'] not in (seal.get('packet_sha256'),*seal.get('files',{}).values()):
            gaps.append('review freeze does not bind packet')
        manifest=packet['files']
        for name,value in manifest.items():
            data=source_bytes.get(value)
            if not isinstance(data,bytes) or hashlib.sha256(data).hexdigest()!=value:gaps.append('packet bytes missing/changed: '+name)
        raw_results=[{key:value for key,value in row.items() if key not in ('completed_review_outcome','completed_outcome_assessment')}
                     for row in report['results']]
        if attachment.get('results_sha256')!=m.digest(raw_results):gaps.append('review attachment/result binding changed')
        if set(attachment['label_to_result'])!={'A','B'} or len(set(attachment['label_to_result'].values()))!=2:
            gaps.append('ambiguous delivery mapping')
        assessment=substantive_review(review['parsed'],manifest,source_bytes);gaps.extend(assessment['gaps'])
        for label,ident in attachment['label_to_result'].items():
            row=next(r for r in report['results'] if r['id']==ident)
            viewed={name[len(label+'/source/'):]:value for name,value in manifest.items() if name.startswith(label+'/source/')}
            exact=row.get('final_tree')==viewed
            adequate=assessment['dimensions'].get('program',{}).get('adequacy',{}).get(label)=='adequate'
            dimensions=row.get('outcome_assessment',{})
            runtime=(row.get('runtime_completed',dimensions.get('runtime_completed',row.get('native',{}).get('ok'))) is True
                and row.get('deterministic_invariants_passed',dimensions.get('deterministic_invariants_passed')) is True)
            outcomes[ident]={'reviewed_artifact_adequate':adequate,'final_source_exactly_reviewed':exact,
                'task_passed':bool(adequate and runtime) if exact and runtime else None,
                'scope':'exact final source plus recorded runtime/invariants' if exact and runtime else 'frozen reviewed view; execution/projection linkage not promoted'}
    except (KeyError,TypeError,ValueError,AttributeError,StopIteration) as error:gaps.append('malformed completed review: '+str(error))
    ready=not gaps
    if not ready:
        for row in outcomes.values():row['task_passed']=None
    return {'ready':ready,'gaps':sorted(set(gaps)),'quality_disposition':assessment.get('dimensions',{}),
        'deliveries':outcomes,'packet_source_consistent':ready,'execution_authenticated':False,
        'deployment_authority':False,'adoption_authority':False,'whole_workflow_efficiency_qualified':False,
        'legacy_efficiency':report.get('legacy_efficiency'),
        'source_bound_current_quality':bool(ready and outcomes and all(row['final_source_exactly_reviewed'] for row in outcomes.values())),
        'scope':'Bounded artifact quality; no skill-wide retirement, fresh-receiver or complete cost proof'}


def quality_tradeoff_decision(quality, policy, source_bytes):
    """Current source-bound quality preference, alongside legacy efficiency."""
    quality=quality if isinstance(quality,dict) else {}
    source_bytes=source_bytes if isinstance(source_bytes,dict) else {}
    valid=False
    if isinstance(policy,dict):
        raw=source_bytes.get(policy.get('source_sha256'))
        valid=(isinstance(raw,bytes) and hashlib.sha256(raw).hexdigest()==policy.get('source_sha256')
            and policy.get('allow_more_tokens_for_better_quality') is True
            and isinstance(policy.get('excerpt'),str) and bool(policy['excerpt'].strip())
            and policy['excerpt'] in raw.decode('utf-8',errors='replace'))
    return {'policy_source_verified':valid,'quality_recommendation_sufficient':bool(valid and quality.get('ready') and quality.get('source_bound_current_quality',True)),
        'quality_disposition':quality.get('quality_disposition'), 'legacy_efficiency_independent':True,
        'unknown_cost_is_zero':False,'deployment_authority':False,'adoption_authority':False}


def validate_artifact_evidence(report: dict, plan: dict, *, source_bytes: dict | None = None) -> dict:
    """Validate bound native leaf receipts without executing paths or oracles.

    source_bytes maps SHA256 to explicitly supplied bytes. No recorded pathname
    is opened. Source completeness covers declared bytes only, never execution
    origin, source-to-request attribution, oracle adequacy or publication.
    """
    import artifact_hash
    import evaluation_measurement as measurement
    from pathlib import PurePosixPath, PureWindowsPath
    errors, gaps, runtime_gaps, bindings, records = [], [], [], [], []
    blockers = ['pre-spend fidelity clearance is enforced separately; this read-only projection does not reauthenticate it',
                'recorded sources and receipts do not authenticate source-to-execution provenance',
                'leaf case/arm coverage does not establish required acceptance trials or workflow coverage']
    def require(condition, message):
        if not condition:
            errors.append(message)
    def bind(label, value):
        if measurement.sha(value) is None:
            gaps.append(label + ': recorded source hash unavailable')
            return
        data = supplied.get(value)
        matched = isinstance(data, bytes) and hashlib.sha256(data).hexdigest() == value
        bindings.append({'source': label, 'sha256': value, 'bytes_matched': matched})
        if data is None:
            gaps.append(label + ': source bytes not supplied')
        elif not matched:
            errors.append(label + ': supplied source bytes mismatch')
    def files(label, values):
        require(isinstance(values, dict) and bool(values), label + ': missing file manifest')
        for name, value in values.items():
            require(isinstance(name, str) and bool(name) and '\\' not in name
                    and not name.startswith('/') and ':' not in name
                    and all(part not in ('', '.', '..') for part in name.split('/')),
                    label + ': unsafe manifest path')
            require(measurement.sha(value) is not None, label + ': invalid file hash')
            bind(label + '/' + name, value)
    def frame(label, value):
        require(value.get('identity_format') == 'fleet-package-v1', label + ': unsupported package identity')
        manifest = value['files']
        files(label, manifest)
        require('SKILL.md' in manifest, label + ': missing SKILL.md')
        require(artifact_hash.package_hash_from_files(manifest) == value.get('package_sha256'),
                label + ': package identity mismatch')
        if value.get('projection')=='native-catalog':
            require(value.get('prompt_text') is None,label+': native inventory cannot claim injected prompt')
            require(value.get('entry_sha256')==manifest.get('SKILL.md'),label+': native entry identity mismatch')
        else:
            prompt = value['prompt_text']
            require(hashlib.sha256(prompt.encode('utf-8')).hexdigest() == value.get('prompt_sha256'),
                    label + ': prompt projection hash mismatch')
    try:
        supplied = {} if source_bytes is None else source_bytes
        require(isinstance(supplied, dict), 'source bytes must be an explicit hash map')
        for value, data in supplied.items():
            require(measurement.sha(value) is not None and isinstance(data, bytes)
                    and hashlib.sha256(data).hexdigest() == value, 'supplied source hash/bytes mismatch')
        require(report['kind'] == plan['kind'] == plan['spec']['purpose'] == 'native-skill-study',
                'unsupported or mismatched native artifact kind')
        require(report.get('admission') is False and report.get('workflow_comparison_supported') is False
                and plan.get('workflow_comparison_supported') is False,
                'native artifact authority must remain diagnostic only')
        spec = plan['spec']
        arms = {row['id']: row for row in spec['arms']}
        cases = {row['id']: row for row in spec['cases']}
        require(len(arms) == len(spec['arms']) and len(cases) == len(spec['cases'])
                and 1 <= len(arms) * len(cases) <= 12, 'invalid native case/arm coverage')
        jobs, rows = plan['jobs'], report['results']
        require(len(jobs) == len(arms) * len(cases) == len(rows), 'incomplete native job/result coverage')
        require(type(report.get('completed_trials')) is int and type(report.get('expected_trials')) is int
                and report['completed_trials'] == report['expected_trials'] == len(jobs), 'native trial counts mismatch')
        job_ids = [job['id'] for job in jobs]
        require(len(set(job_ids)) == len(jobs) and [row['id'] for row in rows] == job_ids,
                'duplicate, missing or reordered native results')
        require({(job['case'], job['arm']) for job in jobs} == {(case, arm) for case in cases for arm in arms},
                'native case/arm job mapping mismatch')
        for key in ('oracle_sha256', 'controller_sha256', 'worker_sha256', 'native_hermes_worker_sha256',
                    'runtime_sha256', 'measurement_sha256', 'usage_observer_sha256'):
            bind(key, plan.get(key))
        require(set(plan['candidate_snapshots']) == set(arms), 'candidate snapshot arm coverage mismatch')
        for arm, snapshot in plan['candidate_snapshots'].items():
            require((snapshot is None) == (arms[arm].get('instructions') is None), 'candidate absence mismatch')
            if snapshot is not None:
                frame('candidate/' + arm, snapshot)
        for name, snapshot in plan.get('common_catalog_snapshots', {}).items():
            frame('common-catalog/' + str(len(bindings)), snapshot)
        require(set(plan.get('common_catalog_snapshots', {})) == set(spec.get('catalog', [])),
                'common native catalog source coverage mismatch')
        require(set(plan['case_source_trees']) == set(cases), 'fixture source case coverage mismatch')
        for case, manifest in plan['case_source_trees'].items():
            files('fixture/' + case, manifest)
        for job, row in zip(jobs, rows):
            require(row['arm'] == job['arm'] and row['case'] == job['case'], 'native result case/arm mismatch')
            require(all(job['initial_tree'].get(name) == value for name, value in plan['case_source_trees'][job['case']].items()),
                    'native job differs from frozen fixture source')
            files('final-artifact/' + row['id'], row['final_tree'])
            native = row['native']
            route = {key: spec.get(key) for key in ('model', 'provider', 'reasoning')}
            require(all(isinstance(value, str) and value for value in route.values())
                    and all(native.get('agent_observed_route', {}).get(key) == value for key, value in route.items()),
                    'native observed route mismatch or missing')
            expected_catalog = [snapshot['package_sha256'] for snapshot in plan.get('common_catalog_snapshots', {}).values()]
            snapshot = plan['candidate_snapshots'][job['arm']]
            if snapshot and spec.get('instruction_exposure') != 'explicit-body':
                expected_catalog.append(snapshot['package_sha256'])
            require(sorted(job['catalog_frames'].values()) == sorted(expected_catalog)
                    and len(job['catalog']) == len(set(job['catalog']))
                    and set(job['catalog']) == set(job['catalog_frames']), 'prepared native catalog binding mismatch')
            known_frames = list(plan.get('common_catalog_snapshots', {}).values()) + ([snapshot] if snapshot else [])
            frames_by_hash = {value['package_sha256']: value for value in known_frames}
            expected_tree = dict(plan['case_source_trees'][job['case']])
            path_type = PureWindowsPath if '\\' in job['fixture'] or ':' in job['fixture'] else PurePosixPath
            for location, value in job['catalog_frames'].items():
                relative = path_type(location).relative_to(path_type(job['fixture']))
                require(len(relative.parts) == 4 and relative.parts[:2] == ('.agents', 'skills')
                        and relative.parts[2] not in ('.', '..') and relative.parts[-1] == 'SKILL.md',
                        'native catalog location is outside declared skill staging')
                prefix = relative.parent.as_posix()
                expected_tree.update({prefix + '/' + name: digest for name, digest in frames_by_hash[value]['files'].items()})
            require(job['initial_tree'] == expected_tree, 'native initial tree contains missing, changed or undeclared sources')
            # The worker hashes build_prompt(agent), not job['prompt']. These
            # are different inputs; the recorded hash cannot bind the user task.
            assembled = native.get('catalog_evidence', {}).get('prompt_sha256')
            require(measurement.sha(assembled) is not None, 'native assembled prompt hash unavailable')
            bind('native-assembled-prompt/' + row['id'], assembled)
            if native.get('prepared_task_sha256')!=hashlib.sha256(job['prompt'].encode()).hexdigest():
                runtime_gaps.append('native user-task input has no separately recorded matching hash')
            require(cases[job['case']]['prompt'] in job['prompt'], 'prepared job omits declared case prompt')
            if snapshot and spec.get('instruction_exposure') == 'explicit-body':
                require(snapshot['prompt_text'] in job['prompt'], 'prepared job omits declared explicit candidate projection')
            if native.get('host_version') is None:
                runtime_gaps.append('native host version not recorded')
            if native.get('model_launched') is not True:
                runtime_gaps.append('native model launch not recorded')
            if native.get('catalog_evidence', {}).get('exact_catalog_verified') is not True:
                runtime_gaps.append('exact native catalog observation unavailable')
            lifecycle = native.get('native_usage', {}).get('lifecycle', {})
            observed_sources = lifecycle.get('native_sources_before', {})
            if not observed_sources:
                runtime_gaps.append('native implementation source fingerprints not recorded')
            else:
                require(observed_sources == lifecycle.get('native_sources_after'), 'native implementation sources changed during run')
                for index, value in enumerate(observed_sources.values()):
                    bind('native-implementation/' + row['id'] + '/' + str(index), value)
        records = measurement.artifact_records(report, plan,source_bytes=supplied)
        for row, record in zip(rows, records):
            expected_ok = artifact_runtime_ok(row,record,plan['spec'])
            if row.get('exposure_setup_ok') is False:
                expected_ok = False
            require(type(row.get('oracle_exit_code')) is int and type(row.get('ok')) is bool
                    and row['ok'] == expected_ok, 'native outcome contradicts raw execution/oracle receipts')
        if 'measurements' in report:
            require(report['measurements'] == records, 'saved native measurements differ from raw receipt projection')
    except (KeyError, TypeError, ValueError, AttributeError, IndexError) as exc:
        errors.append('malformed native artifact evidence: ' + type(exc).__name__)
    completed=(completed_artifact_decision(report,report['completed_review'],supplied,plan=plan)
        if isinstance(report.get('completed_review'),dict) else {'ready':False,'gaps':['substantive completed review pending']})
    return {'errors': sorted(set(errors)), 'source_gaps': sorted(set(gaps)), 'runtime_gaps': sorted(set(runtime_gaps)),
            'consistent': not errors, 'source_bytes_complete': not errors and not gaps,
            'source_bindings': bindings, 'records': records,
            'usage_readiness': measurement.acceptance_readiness(records),
            'admission': False, 'positive_decision_sufficient': False,
            'execution_authenticated': False, 'admission_blockers': blockers,
            'completed_review_decision':completed,'quality_positive_decision_sufficient':bool(completed.get('source_bound_current_quality') and not errors),
            'deployment_authority':False,'legacy_admission_scope':'Historical full admission remains separate from artifact quality'}


def outcome_efficiency(before: list[dict], after: list[dict], *, whole_job=None, quality=None, quality_policy=None, source_bytes=None) -> dict:
    """Qualify recorded equal-or-better outcomes at no greater overall tokens.

    Callers retain their source, oracle and harness checks. This consistency
    result grants neither publication authority nor execution authentication.
    Inputs must be freshly projected from the bound raw receipts, not a saved
    comparison's eligibility booleans.
    """
    import evaluation_measurement as measurement
    errors = []
    comparison = None
    job_delta=None
    if not isinstance(whole_job,dict) or whole_job.get('ready') is not True:
        errors.append('closed attributed whole-job cost qualification unavailable')
    else:
        from fractions import Fraction
        try:
            totals=whole_job['comparison_tokens_by_arm']
            if set(totals)!=set(SIDES):raise ValueError('binary comparison attribution domain differs')
            actual={side:Fraction(totals[side]['numerator'],totals[side]['denominator']) for side in SIDES}
            delta=actual['candidate']-actual['baseline']
            job_delta={'numerator':delta.numerator,'denominator':delta.denominator}
            if delta>0:errors.append('candidate whole-job cost exceeds baseline including job-level support/review')
        except (KeyError,TypeError,ValueError,ZeroDivisionError):
            errors.append('per-arm whole-job cost attribution missing')
    try:
        for row in before + after:
            if row.get('record_sha256') != measurement.digest({
                    key: value for key, value in row.items() if key != 'record_sha256'}):
                errors.append('measurement projection digest mismatch')
            if measurement.sha(row.get('provenance', {}).get('evidence_sha256')) is None:
                errors.append('measurement source receipt binding missing')
        comparison = measurement.compare_records(before, after)
        pairs = comparison['pairs']
        if not pairs or not comparison['conditional_efficiency']['equivalent_case_coverage']:
            errors.append('quality-qualified matched case/trial coverage is incomplete')
        for side, records in (('baseline', before), ('candidate', after)):
            ready = measurement.acceptance_readiness(records)
            errors.extend(side + ': ' + gap for gap in ready['gaps'])
        for pair in pairs:
            if not pair['conditional_efficiency_eligible']:
                errors.append('matched task lacks quality-qualified complete overall usage')
            delta = pair['token_delta_after_minus_before']['total_tokens']
            if type(delta) is not int or delta > 0:
                errors.append('matched task must use equal or fewer overall tokens')
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        errors.append('malformed efficiency evidence: ' + type(exc).__name__)
    current=quality_tradeoff_decision(quality or {},quality_policy or {},source_bytes or {})
    return {'eligible': not errors, 'errors': sorted(set(errors)),
            'legacy_efficiency':{'eligible':not errors,'errors':sorted(set(errors)),'rule':'equal-or-fewer complete overall tokens'},
            'current_quality_recommendation':current,
            'comparison': comparison,'whole_job_cost_delta_candidate_minus_baseline':job_delta, 'execution_authenticated': False,
            'behavioral_proof': False}


def instruction_improvement(report: dict, suite: dict, *, suite_sha256: str,
                            harness_sha256: str, route: dict) -> list[str]:
    """Require a positive measured difference as well as nonregression/accounting.

    Mechanical eligibility does not establish claim coverage, practical benefit,
    comparability or retention authority. Those remain owner review decisions.
    """
    if not isinstance(report, dict) or not isinstance(suite, dict):
        return ['behavioral measurement and task contract must be objects']
    checked = validate_report(report, suite)
    errors = list(checked['errors'])
    errors.extend(adoption_qualification(report, suite)['gaps'])
    readiness = runtime.comparison_readiness(suite)
    recorded = report.get('comparison_readiness', {})
    if not readiness['ready'] or recorded.get('ready') is not True or recorded.get('requirements') != suite.get('comparison_requirements'):
        errors.append('measurement question did not pass matching readiness')
    cases = suite.get('cases', [])
    minimum = report.get('decision_rule', {}).get('min_trials')
    maximum = report.get('decision_rule', {}).get('max_trials')
    # The validator recomputes contiguous complete trials and checks stopping
    # after every trial. Sequential minima are lower bounds; v3 stability is an
    # exact plan. Do not independently reinterpret a recorded stop decision.
    completed_trials = len(checked['computed_summary'].get('trial_scores', []))
    trial_coverage = (type(minimum) is int and type(maximum) is int
                      and 1 <= minimum <= completed_trials <= maximum
                      and len(report.get('results', [])) == len(cases) * completed_trials)
    if suite.get('schema_version') == 3:
        trial_coverage = trial_coverage and completed_trials == suite.get('stability', {}).get('trials')
    if (report.get('decision_mode') != 'admission' or not checked['evidence_complete']
            or (checked['computed_decision'] or {}).get('decision') not in ('admit', 'inconclusive')
            or checked['operational_errors'] or checked['unpaired_attempts']
            or report.get('selected_case_ids') != [case.get('id') for case in cases]
            or not trial_coverage):
        errors.append('no sufficient full-suite outcome comparison')
    summary = checked['computed_summary']
    if any(summary.get(key, 0) for key in ('candidate_losses', 'candidate_hard_failures',
            'judge_errors', 'judge_disagreements', 'candidate_receipt_failures', 'route_attestation_failures')):
        errors.append('measurement must preserve outcomes without recorded regressions')
    import evaluation_measurement as measurement
    for row in report.get('attempt_ledger', []):
        if str(row.get('role', '')).startswith('judge') and row.get('workflow_accounting', {}).get('target_arm') not in SIDES:
            errors.append('shared judge needs explicit target arm; no guessed allocation')
    records = measurement.inline_records(report)
    expected = {(row.get('id'), row.get('trial')) for row in report.get('results', [])}
    for side in SIDES:
        observed = {(row['identity']['case_id'], row['identity']['trial']) for row in records
                    if row['identity']['role'] == side}
        if observed != expected:
            errors.append('efficiency projection does not cover measured case/trial outcomes')
    # Supporting calls accompany both views; ambiguous shared judges fail closed
    # unless the original receipts explicitly attribute them to an arm.
    before = [row for row in records if row['identity']['arm'] != 'candidate']
    after = [row for row in records if row['identity']['arm'] != 'baseline']
    efficiency = outcome_efficiency(before, after, whole_job=adoption_qualification(report,suite).get('whole_job'))
    errors.extend(efficiency['errors'])
    # Noninferiority alone is not improvement. Preserve the existing admission
    # decision's quality threshold; do not promote individual wins or an
    # inconclusive quality decision into a supported outcome gain. A strict
    # token saving can qualify only through complete matched accounting.
    token_gain = (not efficiency['errors'] and any(
        pair['token_delta_after_minus_before']['total_tokens'] < 0
        for pair in (efficiency.get('comparison') or {}).get('pairs', [])))
    quality_gain = (checked['computed_decision'] or {}).get('decision') == 'admit'
    if not quality_gain and not token_gain:
        errors.append('no supported outcome gain or complete overall-token saving; '
                      'noninferiority is not improvement or retention authority')
    errors.extend(instruction_binding_errors(report,suite_sha256,harness_sha256,route))
    return sorted(set(errors))


def instruction_binding_errors(report,suite_sha256,harness_sha256,route):
    """Applicability is shared by legacy cost and current quality decisions."""
    errors=[];artifacts=report.get('artifacts',{})
    if artifacts.get('suite_sha256')!=suite_sha256:errors.append('measurement task contract mismatch')
    if artifacts.get('harness_sha256')!=harness_sha256:errors.append('measurement harness is outdated or mismatched')
    if report.get('agent')!=route.get('host') or any(report.get('effective_stack',{}).get(k)!=route.get(k) for k in ('model','provider','reasoning')):
        errors.append('measurement does not match the current model route')
    return errors


def instruction_quality_decision(report, suite, *, suite_sha256, harness_sha256, route):
    """Preserve strict legacy advice alongside the user's bounded quality rule."""
    legacy=instruction_improvement(report,suite,suite_sha256=suite_sha256,harness_sha256=harness_sha256,route=route)
    checked=validate_report(report,suite)
    applicability=instruction_binding_errors(report,suite_sha256,harness_sha256,route)
    ready=(not applicability and checked.get('evidence_complete') is True and checked.get('attempt_evidence_complete') is True
        and not checked['errors'] and not checked['operational_errors'] and not checked.get('unpaired_attempts')
        and report.get('decision_mode')=='admission'
        and report.get('selected_case_ids')==[c.get('id') for c in suite.get('cases',[])]
        and (checked.get('computed_decision') or {}).get('decision')=='admit')
    text=suite.get('quality_policy_source','');policy=suite.get('quality_decision_policy',{})
    sources={hashlib.sha256(text.encode()).hexdigest():text.encode()} if isinstance(text,str) else {}
    current=quality_tradeoff_decision({'ready':ready,'quality_disposition':checked.get('computed_decision')},policy,sources)
    return {'legacy_improvement_errors':legacy,'applicability_errors':applicability,'current_quality_recommendation':current,
        'deployment_authority':False,'adoption_authority':False,
        'overall_costs':report.get('overall_tokens',report.get('adoption_qualification',{}).get('whole_job',{}).get('overall_tokens'))}


def execution_ok(run: dict[str, Any]) -> bool:
    """Historical reports used overall ok; current reports separate cleanup."""
    return run.get("execution_ok", run.get("ok")) is True


def validate_report(report: dict[str, Any], suite: dict[str, Any] | None) -> dict[str, Any]:
    """Recompute integrity and decision sufficiency without reading report paths.

Callers bind supplied suite/artifact bytes to hashes independently. Successful
validation means the recorded evidence is internally consistent, not authentic.
"""
    result: dict[str, Any] = {
        "errors": [], "computed_decision": None, "computed_summary": {},
        "runs": [], "physical_attempts": 0, "positive_decision_sufficient": False,
        "operational_errors": [], "evidence_complete": False,
        "host_run_counts": {"codex": 0, "hermes": 0}, "scope": None,
        "limitations": [], "attempt_evidence_complete": True,
        "unpaired_attempts": 0,
    }
    errors = result["errors"]
    if isinstance(report,dict) and 'measurement_source_bundle' in report:
        try:
            import evaluation_measurement as measurement
            result['measurement_projection']=measurement.inline_records(report)
        except (ValueError,TypeError,AttributeError) as exc:
            errors.append('measurement source projection failed: '+type(exc).__name__)
    errors.extend(supporting_evidence_errors(report))

    def require(condition: bool, message: str) -> None:
        if not condition:
            errors.append(message)

    def same(actual: Any, expected: Any, message: str) -> None:
        def matches(left: Any, right: Any) -> bool:
            if isinstance(right, bool):
                return type(left) is bool and left == right
            if isinstance(right, dict):
                return isinstance(left, dict) and left.keys() == right.keys() and all(matches(left[key], value) for key, value in right.items())
            if isinstance(right, list):
                return isinstance(left, list) and len(left) == len(right) and all(matches(a, b) for a, b in zip(left, right))
            if type(right) in (int, float):
                return type(left) in (int, float) and left == right
            return left == right
        require(matches(actual, expected), message)

    if not isinstance(report, dict):
        errors.append("report must be an object")
        return result
    if not isinstance(suite, dict):
        errors.append("actual suite is required for evidence recomputation")
        return result
    try:
        evaluator.validate_suite(suite)
    except (ValueError, TypeError, KeyError, AttributeError) as exc:
        errors.append(f"invalid suite: {exc}")
        return result
    try:
        schema = report.get("schema_version")
        require(schema in (2, 3), "unsupported report schema")
        same(schema, evaluator.suite_report_version(suite), "suite/report schema mismatch")
        same(report.get("suite"), suite.get("name"), "suite name mismatch")
        if "oracle_preflight" in report or any("acceptance_review" in case for case in suite.get("cases", [])):
            reviewed_oracle = evaluator.oracle_preflight(suite)
            require(reviewed_oracle["ready"], "declared oracle review fails mechanical preflight")
            same(report.get("oracle_preflight"), reviewed_oracle, "oracle preflight receipt mismatch")
        mode = report.get("decision_mode")
        require(mode in ("admission", "retirement"), "invalid decision mode")
        require(schema != 3 or mode == "admission", "v3 supports admission only")
        status = report.get("status")
        require(status in ("complete", "failed", "interrupted"), "report has no final execution status")
        abnormal = status in ("failed", "interrupted")
        if abnormal:
            result["operational_errors"].append(f"evaluation {status} before normal completion")
        harness_integrity = report.get("harness_integrity", {})
        if abnormal and harness_integrity.get("unchanged") is not False:
            require(bool(report.get("failure" if status == "failed" else "interruption")), "missing execution failure detail")
        for key in ARTIFACT_KEYS:
            require(bool(re.fullmatch(r"[0-9a-f]{64}", str(report.get("artifacts", {}).get(key, "")))), f"missing or malformed artifact: {key}")
        artifacts = report.get("artifacts", {})
        snapshot = report["input_snapshot"]
        suite_source = snapshot["suite_source"]
        same(evaluator.extract_json(suite_source), suite, "frozen suite differs from supplied suite")
        same(hashlib.sha256(suite_source.encode("utf-8")).hexdigest(), artifacts.get("suite_sha256"), "frozen suite hash mismatch")
        for side, package_key, prompt_key in (("candidate", "candidate_sha256", "candidate_prompt_sha256"), ("baseline", "baseline_candidate_sha256", "baseline_prompt_sha256")):
            source = snapshot.get(side)
            format_key = "candidate_identity_format" if side == "candidate" else "baseline_candidate_identity_format"
            if source is None and side == "baseline" and report.get("baseline_candidate") is None:
                same(artifacts.get(package_key), hashlib.sha256(b"").hexdigest(), "empty baseline hash mismatch")
                same(artifacts.get(prompt_key), hashlib.sha256(b"").hexdigest(), "empty baseline prompt hash mismatch")
                if format_key in artifacts:
                    same(artifacts[format_key], "empty-input-sha256", "empty baseline identity format mismatch")
                continue
            same(source.get("projection"), "inline-linked-text-only", f"{side}: unknown prompt projection")
            same(source.get("package_sha256"), artifacts.get(package_key), f"{side}: frozen package hash mismatch")
            same(source.get("prompt_sha256"), artifacts.get(prompt_key), f"{side}: frozen prompt hash mismatch")
            same(hashlib.sha256(source["prompt_text"].encode("utf-8")).hexdigest(), artifacts.get(prompt_key), f"{side}: prompt text hash mismatch")
            if format_key in artifacts:
                same(artifacts[format_key], source.get("identity_format"), f"{side}: source identity format mismatch")
        require(type(harness_integrity.get("unchanged")) is bool, "missing harness integrity result")
        if harness_integrity.get("unchanged"):
            same(harness_integrity.get("final_sha256"), artifacts.get("harness_sha256"), "harness integrity hash mismatch")
        else:
            require(status == "failed", "changed or unverified harness is not recorded as failed")
            result["operational_errors"].append("harness changed or final integrity check failed")
        stack = report["effective_stack"]
        for key in STACK_KEYS:
            if key == "runtime_lane" and stack.get(key) is None:
                continue
            require(isinstance(stack.get(key), str) and bool(stack[key].strip()), f"missing effective stack: {key}")
        require(stack.get("route_attestation_required") is True, "route attestation not required")
        require(stack.get("tool_policy") in ("none", "safe", "full"), "invalid generation tool policy")
        runtime_lane = stack.get("runtime_lane")
        require(runtime_lane in (None, "inline-text-no-tools-v1"), "unsupported producer runtime lane")
        if runtime_lane == "inline-text-no-tools-v1":
            same(stack.get("context_policy"), "fresh-session-per-output", "context_policy differs from producer execution")
            same(stack.get("prompt_assembly"),
                 "isolated-anonymous-artifact-v3" if schema == 3 else "isolated-explicit-artifact-v2",
                 "prompt_assembly differs from producer execution")
        judge_policy = "none" if runtime_lane == "inline-text-no-tools-v1" else "safe"
        same(stack.get("judge_tool_policy"), judge_policy, "judge tool policy differs from producer plan")
        if runtime_lane and status == "complete":
            same(stack.get("tool_policy"), "none", "generation tool policy differs from no-tools producer plan")
        same(stack.get("judge_reasoning"), stack.get("reasoning"), "judge reasoning differs from producer plan")
        require(report.get("agent") in ("codex", "hermes"), "invalid generation host")
        require(report.get("judge_agent") in ("codex", "hermes"), "invalid judge host")
        require(schema != 3 or evaluator.v3_route_supported(report.get("agent"), report.get("judge_agent")), "unsupported v3 generation/judge route")
        same(stack.get("judge_panel"), "two-order-swapped-plus-bounded-tiebreak" if schema == 3 else "two-order-swapped", "judge panel mismatch")

        cases = suite["cases"]
        case_ids = [case["id"] for case in cases]
        require(all(isinstance(case_id, str) and case_id for case_id in case_ids), "invalid suite case identity")
        same(report.get("suite_cases"), [{"id": case["id"], "kind": case.get("kind")} for case in cases], "suite case declaration mismatch")
        selected = report.get("selected_case_ids")
        require(isinstance(selected, list) and bool(selected), "no selected cases")
        if not isinstance(selected, list) or not selected:
            return result
        require(len(set(selected)) == len(selected) and all(case_id in case_ids for case_id in selected), "unknown or duplicated selected case")
        same(selected, [case_id for case_id in case_ids if case_id in selected], "selected cases are out of suite order")
        selected_cases = {case["id"]: case for case in cases if case["id"] in selected}
        full_suite = selected == case_ids
        result["scope"] = evaluator.evaluation_scope(suite, selected)
        result["scope"]["runtime_lane"] = runtime_lane or "historical-unspecified"
        if not runtime_lane:
            result["scope"]["evaluated_projection"] = "historical-unspecified"
            result["scope"]["package_behavior_exercised"] = None
        if "scope" in report:
            same(report["scope"], result["scope"], "recorded evaluation scope mismatch")

        rule_data = report["decision_rule"]
        for key in ("min_trials", "max_trials", "max_agent_runs"):
            require(type(rule_data.get(key)) is int and rule_data[key] > 0, f"invalid decision rule: {key}")
        low, high, cap = (rule_data[key] for key in ("min_trials", "max_trials", "max_agent_runs"))
        require(1 <= low <= high, "invalid trial bounds")
        require(cap >= len(selected) * (5 if schema == 3 else 4) * low, "run budget is smaller than the declared minimum trial plan")
        require(type(rule_data.get("alpha")) in (int, float) and math.isfinite(rule_data["alpha"]) and 0 < rule_data["alpha"] < 1, "invalid decision rule: alpha")
        require(type(rule_data.get("margin")) in (int, float) and math.isfinite(rule_data["margin"]) and 0 <= rule_data["margin"] < 1, "invalid decision rule: margin")
        same(rule_data.get("score_range"), [-1, 1], "score range mismatch")
        if schema == 3:
            same(report.get("stability"), suite["stability"], "stability contract mismatch")
            require(low == high == suite["stability"]["trials"], "trial plan differs from suite stability contract")
        rule = evaluator.DecisionRule(rule_data["alpha"], rule_data["margin"], low, high)

        rows = report.get("results")
        if not isinstance(rows, list):
            errors.append("results must be an array")
            return result
        require(bool(rows) or abnormal, "no observations")
        require(len(rows) <= len(selected) * high, "trial coverage exceeds declared plan")
        require(abnormal or len(rows) % len(selected) == 0, "incomplete trial coverage")
        seeds = report.get("seeds")
        require(isinstance(seeds, list) and all(type(seed) is int for seed in seeds), "invalid trial seeds")
        if not isinstance(seeds, list):
            return result
        expected_ledger: list[dict[str, Any]] = []

        def check_observation(run: dict[str, Any], label: str, judge: bool = False) -> None:
            require(type(run.get("ok")) is bool, f"{label}: missing run outcome")
            require(isinstance(run.get("output"), str), f"{label}: missing output evidence")
            att = run.get("route_attestation", {})
            require(att.get("required") is True or (not run.get("ok") and run.get("run_budget_exhausted")), f"{label}: route attestation not required")
            observed, requested = att.get("observed", {}), att.get("requested", {})
            host = report.get("judge_agent" if judge else "agent")
            route_errors = []
            for key in ("model", "provider", "reasoning"):
                expected = stack.get("judge_" + key if judge else key)
                accepted = {expected}
                if key == "provider" and host == "codex" and expected == "openai-codex":
                    accepted.add("openai")
                if observed.get(key) not in accepted or observed.get(key) is None:
                    route_errors.append(key)
                if requested:
                    same(requested.get(key), expected, f"{label}: requested {key} mismatch")
            policy = stack.get("judge_tool_policy" if judge else "tool_policy")
            if requested and "tool_policy" in requested:
                same(requested["tool_policy"], policy, f"{label}: requested tool policy mismatch")
            if policy == "none" and (host == "hermes" or runtime_lane) and observed.get("tool_calls_count") != 0:
                route_errors.append("tool_calls_count")
            if att.get("ok") is True:
                require(not route_errors, f"{label}: observed route mismatch: {', '.join(route_errors)}")
                require(not att.get("errors"), f"{label}: successful attestation contains errors")
            else:
                require(not execution_ok(run), f"{label}: successful execution has failed route attestation")
            if execution_ok(run):
                same(run.get("returncode"), 0, f"{label}: successful execution has nonzero return code")
            if run.get("evidence_incomplete") is True:
                require(not execution_ok(run) and run.get("ok") is False, f"{label}: incomplete attempt claims success")
                result["attempt_evidence_complete"] = False
                result["limitations"].append("an invocation ended without complete native output/route evidence")
                if run.get("operational_ok") is not True:
                    result["operational_errors"].append(f"{label}: incomplete invocation has unverified cleanup/operation state")
                return
            if not runtime_lane:
                require(not run.get("runtime_contract") and "native_events" not in run and "native_result_metadata" not in run, f"{label}: native evidence has no declared runtime lane")
                return
            if run.get("run_budget_exhausted") and run.get("attempt_count") == 0:
                return
            contract = run.get("runtime_contract")
            require(isinstance(contract, dict), f"{label}: current runtime evidence missing")
            if not isinstance(contract, dict):
                return
            for key, expected in {
                "lane": runtime_lane, "tool_policy": "none", "credential_owner": host,
                "credentials_outside_fixture": True, "personal_config_copied": False,
                "global_session_cleanup_authority": False, "cross_host_credential_fallback": False,
                "tool_schema_absence_verified": False,
            }.items():
                same(contract.get(key), expected, f"{label}: runtime contract mismatch: {key}")
            same(run.get("session_ids"), [], f"{label}: native lane claims global session ownership")
            same(run.get("session_receipt_error"), None, f"{label}: native lane uses global session receipts")
            cleanup = contract.get("cleanup", {})
            for key in ("credentials_removed", "state_removed"):
                require(type(cleanup.get(key)) is bool, f"{label}: missing native cleanup field: {key}")
            require(isinstance(cleanup.get("errors"), list), f"{label}: missing native cleanup errors")
            clean = cleanup.get("credentials_removed") is True and cleanup.get("state_removed") is True and cleanup.get("errors") == []
            if not clean:
                result["operational_errors"].append(f"{label}: native credential/state cleanup failed or is unverified")
                require(run.get("ok") is not True, f"{label}: successful run contradicts native cleanup failure")
            if "operational_ok" in run:
                same(run["operational_ok"], clean, f"{label}: operational outcome contradicts cleanup")
            if "execution_ok" in run:
                require(type(run["execution_ok"]) is bool, f"{label}: malformed execution outcome")
                same(run.get("ok"), run["execution_ok"] and clean, f"{label}: overall outcome contradicts execution/operation outcomes")
            controls = contract.get("controls", {})
            isolation = contract.get("prompt_isolation", {})
            observation = contract.get("tool_observation", {})
            if isolation.get("verified") is True:
                same(isolation.get("contamination"), [], f"{label}: verified isolation contains contamination")
                same(isolation.get("tool_schema_absence_verified"), False, f"{label}: unsupported isolation tool-schema claim")
                if "canary_absent" in isolation:
                    same(isolation["canary_absent"], True, f"{label}: verified isolation contains canary")
                if "native_tool_names" in isolation:
                    same(isolation["native_tool_names"], [], f"{label}: verified isolation contains native tools")
            # Setup failures may have no native result. A successful execution
            # must carry and satisfy every declared no-tools control.
            if execution_ok(run):
                same(att.get("provider_resolved_identity_verified"), False, f"{label}: unsupported provider identity claim")
                same(observation.get("tool_schema_absence_verified"), False, f"{label}: unsupported tool-schema absence claim")
                for key, expected in {"ignore_user_config": True, "fresh_user_home": True, "fresh_runtime_home": True}.items():
                    same(controls.get(key), expected, f"{label}: runtime control mismatch: {key}")
                same(isolation.get("verified"), True, f"{label}: prompt isolation is unverified")
                same(isolation.get("contamination"), [], f"{label}: prompt isolation contamination")
                require(bool(re.fullmatch(r"[0-9a-f]{64}", str(isolation.get("sha256", "")))), f"{label}: missing prompt isolation hash")
            if host == "codex":
                if execution_ok(run):
                    for key, expected in {"project_doc_max_bytes": 0, "personality": "none", "web_search": "disabled", "model_provider": "openai", "approval_policy": "never", "sandbox": "read-only", "native_events": "json", "session_logging": "disposable-home-only"}.items():
                        same(controls.get(key), expected, f"{label}: Codex control mismatch: {key}")
                    require(set(runtime.CODEX_DISABLED_FEATURES) <= set(controls.get("disabled_features", [])), f"{label}: Codex disabled-feature controls incomplete")
                native = run.get("native_events")
                if isinstance(native, list):
                    recomputed_events = runtime.codex_events("\n".join(json.dumps(event) for event in native), evaluator.extract_json, expected_output=run["output"])
                    expected_observation = {key: value for key, value in recomputed_events.items() if key not in {"events", "thread_id"}}
                    same(observation, expected_observation, f"{label}: native event observation mismatch")
                    expected_count = recomputed_events["tool_activity_count"] if recomputed_events["ok"] else None
                    same(observed.get("tool_calls_count"), expected_count, f"{label}: native Codex tool count mismatch")
                    if not recomputed_events["ok"]:
                        require(not execution_ok(run) and att.get("ok") is not True, f"{label}: successful execution contradicts native events")
                    if (run.get("failure") or {}).get("kind") == "provider-transient":
                        same(run["failure"], recomputed_events.get("failure"), f"{label}: retryable failure contradicts native transport evidence")
                else:
                    require(not execution_ok(run), f"{label}: completed native events missing")
            else:
                if execution_ok(run):
                    for key, expected in {"adapter": "native-AIAgent-API", "safe_mode": True, "toolsets": "none", "ignore_rules": True, "skip_context_files": True, "skip_memory": True, "load_soul_identity": False, "skip_background_review": True, "fallback_model": None, "save_trajectories": False, "credentials_in_memory_only": True, "credential_refresh_if_expiring": False}.items():
                        same(controls.get(key), expected, f"{label}: Hermes control mismatch: {key}")
                    same(isolation.get("native_tool_names"), [], f"{label}: native Hermes tools are not empty")
                    same(observation.get("execution_blocker_installed"), True, f"{label}: native tool blocker missing")
                    same(contract.get("output_source"), "native-AIAgent-final-response", f"{label}: unexpected Hermes output source")
                if "assembled_prompt" in isolation:
                    assembled, canary = isolation["assembled_prompt"], isolation.get("canary")
                    require(isinstance(assembled, str) and isinstance(canary, str) and bool(canary), f"{label}: malformed isolation source")
                    same(hashlib.sha256(assembled.encode()).hexdigest(), isolation.get("sha256"), f"{label}: isolation source hash mismatch")
                    canary_absent = canary not in assembled
                    same(isolation.get("canary_absent"), canary_absent, f"{label}: isolation canary contradiction")
                    require(not execution_ok(run) or canary_absent and not any(marker in assembled for marker in runtime.CONTEXT_MARKERS), f"{label}: successful execution contains personal context")
                elif execution_ok(run):
                    errors.append(f"{label}: Hermes isolation source missing")
                if observation:
                    count = observation.get("tool_activity_count")
                    require(type(count) is int and count >= 0, f"{label}: malformed native tool count")
                    same(observed.get("tool_calls_count"), count, f"{label}: native Hermes tool count mismatch")
                    same(observation.get("ok"), count == 0, f"{label}: native tool observation outcome mismatch")
                    require(not execution_ok(run) or count == 0, f"{label}: successful execution contains prohibited tools")
                metadata = run.get("native_result_metadata", {})
                if metadata:
                    complete = metadata.get("completed") is True and not any(metadata.get(key) for key in ("failed", "interrupted", "partial"))
                    require(not execution_ok(run) or complete, f"{label}: successful execution contradicts native completion")
                    if execution_ok(run) or metadata.get("final_response") is not None:
                        same(metadata.get("final_response"), run.get("output"), f"{label}: native Hermes final response mismatch")
                    for key in ("model", "provider"):
                        if metadata.get(key) is not None:
                            same(metadata[key], requested.get(key), f"{label}: native result {key} mismatch")
                else:
                    require(not execution_ok(run), f"{label}: native Hermes completion metadata missing")

        def check_run(run: dict[str, Any], label: str, judge: bool = False, *, identity: dict[str, Any]) -> None:
            result["runs"].append(run)
            host = report.get("judge_agent" if judge else "agent")
            result["host_run_counts"][host] += 1
            require(type(run.get("attempt_count")) is int and run["attempt_count"] >= 0, f"{label}: invalid attempt count")
            attempts = run.get("attempt_count", 0)
            result["physical_attempts"] += attempts
            require(attempts > 0 or run.get("run_budget_exhausted") is True, f"{label}: unexecuted run has no budget failure")
            if run.get("run_budget_exhausted"):
                require(not execution_ok(run) and report.get("run_count") == cap, f"{label}: budget exhaustion contradicts execution/count")
            check_observation(run, label, judge)
            history = run.get("attempts", [])
            require(isinstance(history, list) and len(history) == attempts, f"{label}: attempt history count mismatch")
            retries = rule_data.get("transient_retries_per_run", 0)
            require(type(retries) is int and retries >= 0 and attempts <= retries + 1, f"{label}: retry budget mismatch")
            same(run.get("transient_retry_count", 0), max(0, attempts - 1), f"{label}: retry count mismatch")
            for index, attempt in enumerate(history):
                same(attempt.get("attempt"), index + 1, f"{label}: nonsequential attempt identity")
                complete_attempt = "output" in attempt and "route_attestation" in attempt
                if not complete_attempt and not runtime_lane:
                    if attempts > 1:
                        result["attempt_evidence_complete"] = False
                        result["limitations"].append("historical attempt history is abbreviated; retry transitions cannot be fully verified")
                    if index == len(history) - 1:
                        for key in ("ok", "returncode", "output"):
                            if key in attempt:
                                same(attempt[key], run.get(key), f"{label}: last historical attempt {key} mismatch")
                    continue
                require(complete_attempt, f"{label}: incomplete retry evidence")
                if not complete_attempt:
                    continue
                payload = evaluator.attempt_result(attempt)
                expected_ledger.append({**identity, "attempt": index + 1, "transient": attempt.get("transient"), **payload})
                check_observation(payload, f"{label} attempt {index + 1}", judge)
                transient = evaluator.transient_provider_failure(payload)
                same(attempt.get("transient"), transient, f"{label}: retry classification mismatch")
                if index < len(history) - 1:
                    require(transient and not execution_ok(payload), f"{label}: prohibited retry transition")
                else:
                    same(payload, evaluator.attempt_result(run), f"{label}: final result differs from last attempt")

        recomputed = []
        for index, row in enumerate(rows):
            case_id = selected[index % len(selected)]
            trial = index // len(selected)
            case = selected_cases[case_id]
            label = f"trial {trial} case {case_id}"
            same(row.get("id"), case_id, f"{label}: incomplete or reordered case coverage")
            require(type(row.get("trial")) is int, f"{label}: invalid trial index")
            same(row.get("trial"), trial, f"{label}: noncontiguous trial coverage")
            same(row.get("kind"), case.get("kind"), f"{label}: case kind mismatch")
            require(trial < len(seeds) and row.get("seed") == seeds[trial], f"{label}: seed mismatch")
            order = row["order"]
            require(isinstance(order, list) and len(order) == 2 and set(order) == set(SIDES), f"{label}: invalid anonymous order")
            deterministic = {}
            for side in SIDES:
                check_run(row[side], f"{label} {side}", identity={"trial": trial, "case_id": case_id, "role": side})
                output = row[side]["output"]
                deterministic[side] = evaluator.structured_receipt_check(case, output, suite["receipt_schema"]) if schema == 3 else evaluator.deterministic(case, output)
            recorded_det = deterministic if schema == 3 else {side: deterministic[side][1] for side in SIDES}
            same(row.get("deterministic"), recorded_det, f"{label}: deterministic checks mismatch")
            judges = row["judgments"]
            require(isinstance(judges, list) and len(judges) in ((2, 3) if schema == 3 else (2,)), f"{label}: incomplete judge panel")
            winners, passes, judge_errors = [], [], []
            criterion_ids = [item["id"] for item in case.get("semantic_criteria", [])]
            pair_disagreement = None
            for judge_index, judgment_row in enumerate(judges):
                judge_order = judgment_row["order"]
                if judge_index < 2:
                    same(judge_order, order if judge_index == 0 else list(reversed(order)), f"{label}: judge pair is not order swapped")
                else:
                    require(schema == 3 and judgment_row.get("role") == "tiebreak", f"{label}: unexpected extra judge")
                    require(bool(pair_disagreement and (pair_disagreement["winner"] or pair_disagreement["criteria"])) and not judge_errors, f"{label}: unjustified tiebreak")
                run = judgment_row["run"]
                check_run(run, f"{label} judge {judge_index}", judge=True, identity={"trial": trial, "case_id": case_id, "role": f"judge-{judge_index}" if judge_index < 2 else "judge-tiebreak"})
                try:
                    if not execution_ok(run) or not run.get("route_attestation", {}).get("ok"):
                        route_messages = run.get("route_attestation", {}).get("errors", [])
                        prefix = "tiebreak judge run failed" if judge_index == 2 else "judge run failed"
                        raise ValueError(prefix + (": " + "; ".join(route_messages) if route_messages else ""))
                    judgment = evaluator.extract_json(run["output"])
                    winner, mapped = evaluator.map_v3_judgment(judgment, judge_order, criterion_ids) if schema == 3 else evaluator.map_judgment(judgment, judge_order)
                    same(judgment_row.get("judgment"), judgment, f"{label}: recorded judgment differs from output")
                    winners.append(winner)
                    passes.append(mapped)
                except (ValueError, TypeError, KeyError) as exc:
                    same(judgment_row.get("judgment"), {"raw": run["output"]}, f"{label}: failed judgment raw output mismatch")
                    judge_errors.append(str(exc))
                if judge_index == 1 and schema == 3:
                    pair_disagreement = evaluator.v3_disagreement(winners, passes)
            same(row.get("judge_errors"), judge_errors, f"{label}: judge errors mismatch")
            if schema == 3:
                raw = pair_disagreement or evaluator.v3_disagreement(winners, passes)
                needs_third = (raw["winner"] or raw["criteria"]) and not judge_errors
                require(len(judges) == 3 or not needs_third, f"{label}: required tiebreak missing")
            outcome = evaluator.effective_judgment_result(
                winners, passes,
                {side: deterministic[side]["pass"] if schema == 3 else deterministic[side][0] for side in SIDES},
                criterion_ids if schema == 3 else None,
            )
            winner, hard_pass = outcome["winner"], outcome["hard_pass"]
            raw, detail = outcome["raw_disagreement"], outcome["disagreement"]
            computed_row = {
                **row, "deterministic": recorded_det, "hard_pass": hard_pass, "eligibility": outcome["eligibility"],
                "winner": winner, "score": 1 if winner == "candidate" else -1 if winner == "baseline" else 0,
                "judge_errors": judge_errors, "raw_judge_disagreement": bool(raw["winner"] or raw["criteria"]),
                "judge_disagreement": bool(detail["winner"] or detail["criteria"]), "judge_disagreement_detail": detail,
            }
            if schema == 3:
                computed_row.update(candidate_receipt_pass=bool(deterministic["candidate"]["pass"]), candidate_hard_pass=bool(hard_pass["candidate"]))
            for key in ("hard_pass", "eligibility", "winner", "score", "raw_judge_disagreement", "judge_disagreement", "judge_disagreement_detail", *(("candidate_receipt_pass", "candidate_hard_pass") if schema == 3 else ())):
                same(row.get(key), computed_row[key], f"{label}: {key} mismatch")
            recomputed.append(computed_row)

        ledger = report.get("attempt_ledger")
        if ledger is not None:
            require(isinstance(ledger, list), "attempt ledger must be an array")
            normal = [{key: entry.get(key) for key in ("trial", "case_id", "role", "attempt", "transient")} | evaluator.attempt_result(entry) for entry in ledger]
            same(normal[:len(expected_ledger)], expected_ledger, "attempt ledger contradicts paired result history")
            orphans = normal[len(expected_ledger):]
            require(not orphans or abnormal, "complete report has unpaired native attempts")
            roles = ["baseline", "candidate", "judge-0", "judge-1", "judge-tiebreak"]
            previous_role, previous_attempt = -1, None
            for entry in orphans:
                trial, case_id = len(rows) // len(selected), selected[len(rows) % len(selected)]
                require(trial < high and entry["trial"] == trial and entry["case_id"] == case_id, "unpaired attempt lies outside the next incomplete case")
                require(entry["role"] in roles, "unknown unpaired attempt role")
                role_index = roles.index(entry["role"])
                same_role = role_index == previous_role
                require(same_role or role_index == previous_role + 1, "unpaired attempt roles are out of order")
                expected_index = previous_attempt["attempt"] + 1 if same_role else 1
                same(entry["attempt"], expected_index, "unpaired retry sequence mismatch")
                require(type(entry["attempt"]) is int and 1 <= entry["attempt"] <= rule_data.get("transient_retries_per_run", 0) + 1, "unpaired retry exceeds its plan")
                if same_role:
                    require(evaluator.transient_provider_failure(previous_attempt), "prohibited unpaired retry transition")
                payload = evaluator.attempt_result(entry)
                check_observation(payload, f"unpaired trial {trial} case {case_id} {entry['role']} attempt {entry['attempt']}", judge=role_index >= 2)
                same(entry["transient"], evaluator.transient_provider_failure(payload), "unpaired retry classification mismatch")
                previous_role, previous_attempt = role_index, entry
            result["physical_attempts"] += len(orphans)
            result["unpaired_attempts"] = len(orphans)
            if orphans:
                result["attempt_evidence_complete"] = False
                result["limitations"].append("native attempts are retained for an incomplete case; no case-level verdict is claimed for them")
        attempts = result["physical_attempts"]
        same(report.get("run_count"), attempts, "physical run count mismatch or missing attempt evidence")
        require(attempts <= cap, "physical run budget exceeded")
        completed_trials = len(rows) // len(selected)
        require(len(seeds) == completed_trials if not abnormal else completed_trials <= len(seeds) <= completed_trials + 1, "trial seed coverage mismatch")
        trial_scores = []
        expected = None
        for trial in range(completed_trials):
            through_trial = recomputed[: (trial + 1) * len(selected)]
            trial_rows = through_trial[trial * len(selected):]
            scores = evaluator.decision_scores(trial_rows)
            trial_scores.append(sum(scores) / len(scores) if scores else 0.0)
            expected = evaluator.v3_stability_decision(through_trial, suite["stability"], trial + 1) if schema == 3 else evaluator.sequential_decision(mode, evaluator.decision_scores(through_trial), rule, trial + 1)
            failed = any(not execution_ok(item["baseline"]) or not execution_ok(item["candidate"]) or item["judge_errors"] for item in through_trial)
            if failed:
                expected["decision"] = "harness-failure"
            elif schema == 2 and any(item["eligibility"]["candidate"] == "fail" for item in through_trial):
                expected["decision"] = "reject" if mode == "admission" else "retain"
            elif schema == 2 and any(item["judge_disagreement"] for item in through_trial) and expected["decision"] != "continue":
                expected["decision"] = "inconclusive"
            require(expected["decision"] == "continue" or trial + 1 == completed_trials, "observations continue after a terminal decision")
        if result["unpaired_attempts"]:
            require(expected is None or expected["decision"] == "continue", "unpaired attempts follow a terminal comparison decision")
        if abnormal:
            if harness_integrity.get("unchanged") is False:
                reason = "harness integrity could not be checked" if harness_integrity.get("error") else "harness changed during evaluation"
                require(bool(harness_integrity.get("error")) or harness_integrity.get("final_sha256") != artifacts.get("harness_sha256"), "harness failure lacks differing hash or check error")
            else:
                reason = "exception" if status == "failed" else "interrupted"
            expected = {"decision": "harness-failure", "reason": reason}
        elif expected is not None and expected["decision"] == "continue":
            # The producer may stop between trials when its remaining run budget
            # cannot reserve the next full generation/panel batch.
            require(cap - attempts < len(selected) * (5 if schema == 3 else 4), "evaluation stopped before its declared trial/budget bound")
            expected["decision"] = "inconclusive"
        if expected is not None:
            expected = evaluator.scope_decision(expected, full_suite)
        result["computed_decision"] = expected
        same(report.get("decision"), expected, "declared decision differs from recomputed evidence")
        summary = {
            "candidate_wins": sum(row["winner"] == "candidate" for row in recomputed),
            "candidate_losses": sum(row["winner"] == "baseline" for row in recomputed),
            "ties": sum(row["winner"] == "tie" for row in recomputed),
            "candidate_hard_failures": sum(row["eligibility"]["candidate"] == "fail" for row in recomputed),
            "judge_errors": sum(bool(row["judge_errors"]) for row in recomputed),
            "judge_disagreements": sum(row["judge_disagreement"] for row in recomputed),
            "raw_judge_disagreements": sum(row["raw_judge_disagreement"] for row in recomputed),
            "criterion_disagreements": sum(bool(row["judge_disagreement_detail"].get("criteria")) for row in recomputed),
            "raw_criterion_disagreements": sum(bool(row["judge_disagreement_detail"].get("raw", {}).get("criteria")) for row in recomputed),
            "candidate_receipt_failures": sum(not row.get("candidate_receipt_pass", row["hard_pass"]["candidate"]) for row in recomputed),
            "route_attestation_failures": sum(run.get("route_attestation", {}).get("ok") is not True for run in result["runs"]),
            "trial_scores": trial_scores,
        }
        result["computed_summary"] = summary
        for key, value in summary.items():
            same(report.get("summary", {}).get(key), value, f"summary {key} mismatch")
        positive = expected is not None and expected["decision"] in ("admit", "retire")
        if positive:
            require(full_suite and completed_trials >= low, "positive decision lacks full suite/trial coverage")
        lifecycle = report.get("session_lifecycle", {})
        policy = lifecycle.get("policy")
        require(policy in ("retain-evidence", "delete-after-durable-report"), "missing or unsupported lifecycle policy")
        for key in ("created", "deleted", "remaining", "protected", "errors"):
            require(isinstance(lifecycle.get(key), list), f"missing lifecycle field: {key}")
            if key != "errors" and isinstance(lifecycle.get(key), list):
                require(all(isinstance(value, str) and value for value in lifecycle[key]) and len(set(lifecycle[key])) == len(lifecycle[key]), f"invalid or duplicate lifecycle sessions: {key}")
        created, deleted, remaining, protected = (set(lifecycle.get(key, [])) for key in ("created", "deleted", "remaining", "protected"))
        require(deleted <= created and remaining <= created and protected <= created, "lifecycle contains uncreated sessions")
        require(not (deleted & protected), "lifecycle deleted a protected session")
        if runtime_lane:
            require(not (created or deleted or remaining or protected), "native no-tools lane claims global session lifecycle authority")
        if policy == "retain-evidence":
            require(not deleted and remaining == created - protected, "retained session accounting mismatch")
        else:
            if remaining:
                result["operational_errors"].append("evaluator sessions remain")
            if deleted != created - protected:
                result["operational_errors"].append("session deletion is incomplete")
        if lifecycle.get("errors"):
            result["operational_errors"].append("session cleanup reported errors")
        workspace = report.get("workspace_lifecycle")
        if workspace is not None:
            same(workspace.get("policy"), "remove-after-durable-report", "workspace lifecycle policy mismatch")
            outcome = workspace.get("outcome")
            require(outcome in ("removed", "retained-report-write-failure", "cleanup-failed"), "workspace lifecycle outcome missing or invalid")
            require(isinstance(workspace.get("errors"), list), "workspace lifecycle errors missing")
            if outcome == "removed":
                require(workspace.get("path") is None and not workspace.get("errors"), "removed workspace has contradictory retention/error evidence")
            else:
                require(isinstance(workspace.get("path"), str) and bool(workspace["path"]), "retained workspace path missing")
                result["operational_errors"].append("evaluation workspace retained or cleanup failed")
        exported = report.get("report_export")
        if exported is not None:
            require(type(exported.get("written")) is bool and isinstance(exported.get("errors"), list), "report export outcome missing")
            if exported.get("written") is not True or exported.get("errors"):
                result["operational_errors"].append("requested report export failed or is unverified")
        for host, probe in report.get("version_probes", {}).items():
            if probe.get("ok") is not True or probe.get("errors"):
                result["operational_errors"].append(f"{host}: native version probe failed or is unverified")
            if probe.get("errors"):
                require(probe.get("ok") is not True, f"{host}: successful version probe contains errors")
            cleanup = probe.get("cleanup", {})
            clean = cleanup.get("credentials_removed") is True and cleanup.get("state_removed") is True and cleanup.get("errors") == []
            if not clean:
                result["operational_errors"].append(f"{host}: native version probe cleanup failed or is unverified")
                require(probe.get("ok") is not True, f"{host}: successful version probe contradicts cleanup")
            if host == report.get("agent"):
                same(report.get("agent_version"), probe.get("version"), "generation version differs from native version receipt")
            if host == report.get("judge_agent"):
                same(report.get("judge_version"), probe.get("version"), "judge version differs from native version receipt")
        if "operational_ok" in report:
            same(report["operational_ok"], not result["operational_errors"], "report operational outcome contradicts recorded operations")
        if positive:
            result['adoption_qualification'] = adoption_qualification(report, suite)
        result["positive_decision_sufficient"] = (positive and not errors and not result["operational_errors"]
            and result["attempt_evidence_complete"] and result['adoption_qualification']['ready'])
        result["evidence_complete"] = not errors and result["attempt_evidence_complete"]
    except (AttributeError, KeyError, TypeError, ValueError, IndexError, ZeroDivisionError) as exc:
        errors.append(f"malformed evidence: {type(exc).__name__}: {exc}")
    result["errors"] = sorted(set(errors))
    result["operational_errors"] = sorted(set(result["operational_errors"]))
    result["limitations"] = sorted(set(result["limitations"]))
    return result


def validate_native_diagnostic(report: Any) -> dict[str, Any]:
    """Check a bounded native comparison receipt, never an admission decision.

    Hash syntax/equality checks attest receipt consistency only. The producer must
    preserve raw sources for independent hash recomputation and semantic review.
    This entry point is intentionally not called by validate_report or eval_gate.
    """
    errors: list[str] = []

    def require(condition, message):
        if not condition:
            errors.append(message)

    def digest(value):
        return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None

    try:
        require(report['kind'] == 'native-instruction-diagnostic-v1', 'wrong diagnostic kind')
        require(report['schema_version'] == 1, 'unsupported diagnostic version')
        require(report['authority'] == dict(admission=False, retirement=False, cache=False),
                'diagnostic cannot grant governance authority')
        require(report['status'] == 'complete', 'comparison is incomplete')
        cases, trials = report['cases'], report['trials']
        require(isinstance(cases, list) and len(cases) == 6 and len(set(cases)) == 6,
                'six distinct cases required')
        require(report['trial_cap'] == 12 and type(report['attempts_started']) is int
                and report['attempts_started'] == len(trials) == 12, 'physical trial budget mismatch')
        require(report['cleanup_ok'] is True, 'cleanup unverified')
        for key in ('suite', 'adapter', 'runtime', 'raw_report'):
            require(digest(report['artifacts'][key]), f'invalid {key} binding')
        for arm in ('baseline', 'current'):
            identity = report['arms'][arm]
            require(re.fullmatch(r'[0-9a-f]{40}', identity['revision']) is not None,
                    f'{arm}: invalid revision')
            for key in ('soul_sha256', 'skill_sha256'):
                require(digest(identity[key]), f'{arm}: invalid {key}')
        require(any(report['arms']['baseline'][key] != report['arms']['current'][key]
                    for key in ('soul_sha256', 'skill_sha256')), 'identical instruction arms')
        pairs = {(case, arm) for case in cases for arm in ('baseline', 'current')}
        require([(t['case'], t['arm']) for t in trials].__len__() == len(pairs)
                and {(t['case'], t['arm']) for t in trials} == pairs, 'case/arm coverage mismatch')
        routes = set()
        for trial in trials:
            label = f"{trial['case']}/{trial['arm']}"
            require(trial['completed'] is True, f'{label}: execution incomplete')
            require(trial['cleanup_ok'] is True, f'{label}: cleanup unverified')
            require(trial['boundary_violations'] == [], f'{label}: scope violation')
            require(type(trial['api_calls']) is int and trial['api_calls'] > 0,
                    f'{label}: missing API-call accounting')
            route = trial['requested_route']
            require(all(isinstance(route[k], str) and route[k] for k in ('model', 'provider', 'reasoning')),
                    f'{label}: route incomplete')
            require(route == trial['observed_route'], f'{label}: route mismatch')
            routes.add(tuple(route[k] for k in ('model', 'provider', 'reasoning')))
            for key in ('surrounding_prompt_sha256', 'tools_sha256', 'fixture_before_sha256',
                        'output_sha256', 'actions_sha256', 'fixture_after_sha256'):
                require(digest(trial[key]), f'{label}: invalid {key}')
        require(len(routes) == 1, 'route differs between trials')
        for case in cases:
            pair = [t for t in trials if t['case'] == case]
            if len(pair) == 2:
                for key in ('surrounding_prompt_sha256', 'tools_sha256', 'fixture_before_sha256'):
                    require(pair[0][key] == pair[1][key], f'{case}: unequal {key}')
    except (KeyError, TypeError, ValueError, AttributeError):
        errors.append('malformed diagnostic evidence')
    return {'valid': not errors, 'errors': sorted(set(errors)),
            'admission_eligible': False, 'decision': 'diagnostic-only' if not errors else 'inconclusive'}


# Inserted verbatim into the existing evaluation_evidence module by prepare_patch.
def trial_oracle_validity(oracle, execution, returncode):
    """Usable tests follow the existing 0/pass, 1/product-failure protocol."""
    valid = (isinstance(oracle, dict) and isinstance(execution, dict)
        and execution.get('source_unchanged') is True and type(returncode) is int
        and returncode in (0, 1) and type(oracle.get('passed')) is int
        and type(oracle.get('failed')) is int and oracle['passed'] >= 0 and oracle['failed'] >= 0
        and oracle['passed'] + oracle['failed'] > 0
        and isinstance(oracle.get('failures'), list)
        and all(isinstance(f, str) and bool(f.strip()) for f in oracle['failures'])
        and len(oracle['failures']) == oracle['failed']
        and not oracle.get('error') and not oracle.get('errors')
        and returncode == (1 if oracle['failed'] else 0))
    return {'valid': bool(valid), 'product_quality_passed': None}


def trial_measurement_sources(measurement, fixture):
    """Read only a bounded declared input inside the existing task fixture."""
    from pathlib import PurePosixPath
    observable = measurement.get('observable', {}) if isinstance(measurement, dict) else {}
    if not isinstance(observable, dict) or observable.get('kind') != 'tool-read':
        return {}
    name = observable.get('path')
    if (not isinstance(name, str) or not name or '\\' in name or ':' in name
            or PurePosixPath(name).is_absolute() or '..' in PurePosixPath(name).parts):
        raise ValueError('Measurement path must be an owned relative input')
    root = Path(fixture).resolve(); target = root/name
    if target.is_symlink() or not target.resolve().is_relative_to(root) or target.stat().st_size > 16*1024*1024:
        raise ValueError('Measurement input outside existing fixture/source bound')
    raw = target.read_bytes()
    return {hashlib.sha256(raw).hexdigest(): raw}


def trial_measurement_preflight(measurement, project, source_bytes):
    """Bind intended outcome/behavior to a supported observable before spend."""
    gaps = []
    if not isinstance(measurement, dict):
        return {'valid': False, 'status': 'invalid', 'gaps': ['measurement contract missing']}
    if any(not isinstance(measurement.get(k), str) or not measurement[k].strip()
           for k in ('outcome', 'measured_behavior')):
        gaps.append('intended outcome and measured behavior required')
    observed = measurement.get('observable', {})
    if not isinstance(observed, dict) or observed.get('kind') not in ('completion', 'tool-read'):
        gaps.append('unsupported observable; qualify the evidence route before launch')
    elif observed['kind'] == 'tool-read':
        from pathlib import PurePosixPath
        path = observed.get('path', '')
        markers = observed.get('required_content')
        target = source_bytes.get(observed.get('source_sha256'))
        if (not isinstance(path, str) or not path or '\\' in path or ':' in path
                or PurePosixPath(path).is_absolute() or '..' in PurePosixPath(path).parts
                or project.get(path) != observed.get('source_sha256')
                or not isinstance(target, bytes)
                or hashlib.sha256(target).hexdigest() != observed.get('source_sha256')):
            gaps.append('observable input is not the exact available frozen source')
        if (not isinstance(markers, list) or not markers
                or any(not isinstance(m, str) or not m or not isinstance(target, bytes)
                       or m.encode('utf-8') not in target for m in markers)):
            gaps.append('tool-read needs source-grounded content evidence, not a filename alone')
    return {'valid': not gaps, 'status': 'ready' if not gaps else 'invalid', 'gaps': gaps}


def trial_target_matches(measurement, name, args, fixture=None):
    import posixpath
    observed = measurement['observable']
    if observed['kind'] != 'tool-read' or name != 'read_file':
        return False
    raw = args.get('path') if isinstance(args, dict) else None
    if not isinstance(raw, str):
        return False
    path = posixpath.normpath(raw.replace('\\', '/'))
    root = posixpath.normpath(str(fixture).replace('\\', '/')) if fixture else None
    if root and path.casefold().startswith(root.rstrip('/').casefold() + '/'):
        path = path[len(root.rstrip('/'))+1:]
    return path.casefold() == observed['path'].casefold() if root and ':' in root else path == observed['path']


def trial_tool_observation(measurement, name, args, output, *, fixture=None, actual_sha=None):
    """Runtime evidence only. Pending means no dependency may yet be admitted."""
    observed = measurement['observable']
    if not trial_target_matches(measurement,name,args,fixture):
        return {'status': 'pending'}
    if actual_sha != observed['source_sha256']:
        return {'status': 'invalid', 'reason': 'observable-source-changed'}
    if (not isinstance(output, dict) or output.get('error') or output.get('not_found')
            or output.get('success') is False or output.get('is_binary') or output.get('is_image')):
        return {'status': 'invalid', 'reason': 'required-behavior-tool-failed'}
    content = output.get('content')
    if not isinstance(content, str) or not content.strip():
        return {'status': 'invalid', 'reason': 'required-content-unobserved'}
    if not all(marker in content for marker in observed['required_content']):
        return {'status': 'pending', 'reason': 'required-content-not-yet-observed'}
    return {'status': 'exercised', 'source_sha256': actual_sha}


def trial_measurement_verdict(measurement, native, manifest_bytes, source_bytes,
                              expected_binding, project, *, fixture=None):
    """Recompute validity from bound raw records; never trust a result's flag.

    The oracle/quality result is deliberately not consulted: an exercised test
    may validly produce an inferior or failing product.
    """
    gaps = list(trial_measurement_preflight(measurement, project, source_bytes)['gaps'])
    exercised = False
    runtime_failure = False
    try:
        if (native.get('ok') is not True or native.get('blocked_requests')
                or native.get('turn_deadline', {}).get('fired')
                or native.get('measurement_runtime', {}).get('invalid')):
            gaps.append('runtime/test-control failure; diagnose before dependent trials')
            runtime_failure = True
        recording = native['request_recording']
        if (recording.get('complete') is not True or not isinstance(manifest_bytes, bytes)
                or hashlib.sha256(manifest_bytes).hexdigest() != recording.get('manifest_sha256')):
            raise ValueError('complete exact recording missing')
        manifest = json.loads(manifest_bytes)
        if manifest.get('complete') is not True or manifest.get('binding') != expected_binding:
            raise ValueError('recording belongs to a different trial')
        requests = []
        for blob in manifest['blobs']:
            if blob['kind'] != 'final-request':
                continue
            raw = source_bytes[blob['sha256']]
            if len(raw) != blob['bytes'] or hashlib.sha256(raw).hexdigest() != blob['sha256']:
                raise ValueError('recorded request changed')
            requests.append(json.loads(raw))
        if not requests or len(requests) != recording.get('final_request_count'):
            raise ValueError('recorded request inventory incomplete')
        if not gaps and measurement['observable']['kind'] == 'completion':
            exercised = isinstance(native.get('final_response'), str) and bool(native['final_response'].strip())
        elif not gaps:
            calls = {}; outputs = {}
            for request in requests:
                for item in request.get('input', []):
                    if item.get('type') not in ('function_call', 'function_call_output'):
                        continue
                    ident = item['call_id']
                    selected = calls if item['type'] == 'function_call' else outputs
                    if ident in selected and selected[ident] != item:
                        raise ValueError('conflicting repeated call identity')
                    selected[ident] = item
            observed = measurement['observable']
            for ident, call in calls.items():
                if ident not in outputs:
                    continue
                args = json.loads(call['arguments']) if isinstance(call['arguments'], str) else call['arguments']
                if not trial_target_matches(measurement,call['name'],args,fixture):
                    continue
                raw = outputs[ident]['output']
                try:reply = json.loads(raw) if isinstance(raw, str) else raw
                except (ValueError,TypeError):reply = None
                proof = trial_tool_observation(measurement, call['name'], args, reply,
                    fixture=fixture, actual_sha=project.get(observed['path']))
                if proof['status'] == 'invalid':
                    gaps.append(proof['reason'])
                exercised = exercised or proof['status'] == 'exercised'
    except (KeyError, ValueError, TypeError, AttributeError, UnicodeDecodeError):
        gaps.append('bound observation unavailable or inconsistent')
        runtime_failure = True
    if not exercised:
        gaps.append('intended measured behavior not exercised')
    valid = not gaps
    return {'valid': valid, 'status': 'valid' if valid else 'invalid',
        'measurement_exercised': exercised, 'gaps': sorted(set(gaps)),
        'continue_dependent_trials': valid, 'product_quality_passed': None,
        'failure_scope': None if valid else 'runtime' if runtime_failure else 'case',
        'repair_and_requalification_required': not valid, 'rerun_authority': False}


def trial_closed_verdict(row, binding, source_bytes):
    """Join the existing final recording, response, oracle and closure receipts.

    This checks supplied evidence consistency, not execution authentication or
    product adequacy. A bound, well-formed failing oracle remains a valid test.
    """
    import evaluation_measurement as m
    gaps=[]
    try:
        native=row['native']; prior=native['request_recording']; final=row['request_recording']
        cleanup=native['cleanup']; state=native['measurement_runtime']
        if (type(native.get('returncode')) is not int or native['returncode'] != 0
                or cleanup.get('state_removed') is not True
                or cleanup.get('credentials_removed') is not True
                or cleanup.get('errors') != [] or native.get('worker_cleanup_errors') != []
                or state.get('invalid') is not False or state.get('stop_errors') != []
                or native.get('failure') or native.get('pending_operation')):
            raise ValueError('runtime stop/closure not clean')
        if (final.get('complete') is not True
                or final.get('manifest_sha256') != prior['manifest_sha256']
                or final.get('final_request_count') != prior['final_request_count']
                or final.get('run_binding_sha256') != hashlib.sha256(json.dumps(binding,sort_keys=True).encode()).hexdigest()):
            raise ValueError('final recording missing or inconsistent')
        ref=final['output_checks_sha256']; raw=source_bytes[ref]
        if not isinstance(raw,bytes) or hashlib.sha256(raw).hexdigest()!=ref:
            raise ValueError('bound output checks unavailable')
        checks=json.loads(raw)
        response=native['final_response']
        if not isinstance(response,str) or not response.strip():raise ValueError('response missing')
        assessment=row['outcome_assessment']
        if assessment.get('runtime_completed') is not True:
            raise ValueError('outcome reports an incomplete runtime')
        expected={'oracle_sha256':binding['oracle_sha256'],
            'oracle_exit_code':row['oracle_exit_code'], 'oracle_result_sha256':m.digest(row['oracle']),
            'outcome_schema_version':2,
            'deterministic_invariants_passed':assessment['deterministic_invariants_passed'],
            'task_passed':assessment['task_passed'], 'final_tree_sha256':m.digest(row['final_tree']),
            'final_response_sha256':hashlib.sha256(response.encode('utf-8')).hexdigest()}
        if (checks != {'manifest_sha256':prior['manifest_sha256'], 'binding':binding,
                       'outcome':expected,'execution_authenticated':False}
                or type(expected['deterministic_invariants_passed']) is not bool
                or (expected['task_passed'] is not None and expected['task_passed'] is not False)):
            raise ValueError('response/output evidence does not join')
        execution=row['oracle_execution']; code=row['oracle_exit_code']
        if not trial_oracle_validity(row['oracle'],execution,code)['valid']:
            raise ValueError('oracle protocol unusable')
        if (execution.get('termination')!='returned' or type(execution.get('exit_code')) is not int
                or execution['exit_code']!=code or execution.get('entry_sources_unchanged') is not True
                or execution.get('source_tree_before')!=row['final_tree']
                or execution.get('source_tree_after')!=row['final_tree']
                or not isinstance(row['final_tree'],dict)
                or any(not isinstance(name,str) or not name or not isinstance(ref,str)
                       or len(ref)!=64 or any(c not in '0123456789abcdef' for c in ref)
                       for name,ref in row['final_tree'].items())
                or execution.get('cwd')!=execution.get('captured_fixture')
                or execution.get('origin')!='controller-observed-subprocess'):
            raise ValueError('oracle did not finish against the final tree')
        for key in ('stdout','stderr'):
            if (not isinstance(execution.get(key),str)
                    or hashlib.sha256(execution[key].encode('utf-8')).hexdigest()!=execution.get(key+'_sha256')):
                raise ValueError('oracle stream changed')
        if json.loads(execution['stdout'])!=row['oracle']:
            raise ValueError('oracle result differs from executed stdout')
        if expected['deterministic_invariants_passed'] is not (code==0):
            raise ValueError('invariant projection contradicts the oracle')
        entry=execution['entry_sources']; argv=execution['argv']
        if (not isinstance(argv,list) or len(argv)!=4 or argv[2]!=execution['captured_fixture']
                or argv[3]!=binding['case_id'] or entry.get(argv[1])!=binding['oracle_sha256']):
            raise ValueError('different oracle invocation')
        oracle_source=source_bytes[binding['oracle_sha256']]
        if not isinstance(oracle_source,bytes) or hashlib.sha256(oracle_source).hexdigest()!=binding['oracle_sha256']:
            raise ValueError('bound oracle source absent')
    except (KeyError,TypeError,ValueError,AttributeError,UnicodeDecodeError):
        gaps.append('closed trial output/oracle/closure evidence missing or inconsistent')
    return {'valid':not gaps,'gaps':gaps,'product_quality_passed':None,
            'execution_authenticated':False}


def trial_review_gate(report, plan, source_bytes):
    """Default completed-review gate, using the frozen plan and raw observations."""
    rows = []
    if not isinstance(plan, dict):
        return {'valid': False, 'gaps': ['frozen measured-behavior plan required; historical review is diagnostic only']}
    try:
        import evaluation_measurement as m
        ids = [row['id'] for row in report['results']]
        if len(ids) != len(set(ids)) or set(ids) != {job['id'] for job in plan['jobs']}:
            raise ValueError('dependent comparison outcomes missing or duplicated')
        for row in report['results']:
            job = next(j for j in plan['jobs'] if j['id'] == row['id'])
            case = next(c for c in plan['spec']['cases'] if c['id'] == job['case'])
            measurement = case['intervention_contracts'][job['arm']]['measurement']
            native = row['native']; recording = native['request_recording']
            binding = {'run_id':job['id'], 'case_id':job['case'], 'arm':job['arm'],
                'plan_sha256':m.digest(plan), 'task_sha256':hashlib.sha256(job['prompt'].encode()).hexdigest(),
                'oracle_sha256':plan['oracle_sha256']}
            checked = trial_measurement_verdict(measurement, native,
                source_bytes.get(recording.get('manifest_sha256')), source_bytes, binding,
                plan['case_source_trees'][job['case']], fixture=job['fixture'])
            closed=trial_closed_verdict(row,binding,source_bytes)
            if not closed['valid']:
                checked={**checked,'valid':False,'status':'invalid','continue_dependent_trials':False,
                    'failure_scope':'runtime','repair_and_requalification_required':True,
                    'gaps':sorted(set(checked['gaps']+closed['gaps']))}
            rows.append(checked)
    except (KeyError, TypeError, ValueError, AttributeError, StopIteration):
        return {'valid': False, 'gaps': ['frozen measurement/evidence join missing; no positive inference']}
    return {'valid': bool(rows) and all(r['valid'] for r in rows), 'rows': rows,
            'gaps': sorted({g for r in rows for g in r['gaps']})}
