"""Bounded artifact pilot front end for eval.py; not an admission evaluator.

Reuse candidate freezing, runtime isolation, and the routed native worker.
The suite supplies its independently executed oracle. No model judge, promotion,
retries, fallback, configuration mutation, or new workflow scheduler lives here.
"""
from __future__ import annotations
import argparse
import datetime as dt
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from artifact_hash import freeze_candidate
from evaluation_runtime import runtime_environment, native_executable, native_hermes_runtime, hermes_owner_home


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def tree(root):
    return {p.relative_to(root).as_posix(): sha(p) for p in sorted(root.rglob('*'))
            if p.is_file() and '__pycache__' not in p.parts and '.git' not in p.parts}


def run_bound_program(argv, fixture, timeout, *, env=None, evidence_dir=None, cwd=None):
    """Prospective file/command/result binding, not cryptographic execution proof.

    Uses the existing subprocess boundary. Saves exact pre-execution project
    bytes when the controller supplies an evidence directory. No inferred logs.
    """
    fixture = Path(fixture).resolve()
    workdir=Path(cwd).resolve() if cwd is not None else fixture
    if not workdir.is_dir() or not workdir.is_relative_to(fixture):
        raise ValueError('Execution cwd must remain within the captured fixture')
    before = tree(fixture)
    payloads = {name:(fixture/name).read_bytes() for name in before}
    if sum(map(len,payloads.values())) > 32 * 1024 * 1024:
        raise ValueError('Program evidence source exceeds explicit 32MiB bound')
    if any(hashlib.sha256(data).hexdigest()!=before[name] for name,data in payloads.items()):
        raise ValueError('Program source changed while capturing')
    entries=[Path(p) if Path(p).is_absolute() else workdir/p for p in argv if isinstance(p,str)]
    entry_sources = {str(p.resolve()):sha(p) for p in entries if p.is_file()}
    receipt = {'argv':list(argv),'cwd':str(workdir),'captured_fixture':str(fixture),'source_tree_before':before,
               'entry_sources':entry_sources,'timeout_seconds':timeout,
               'execution_authenticated':False,'origin':'controller-observed-subprocess',
               'source_scope':'project files excluding .git/__pycache__, explicit argv files; imported external dependencies not attested'}
    if evidence_dir is not None:
        evidence_dir = Path(evidence_dir)
        evidence_dir.mkdir(exist_ok=False)
        (evidence_dir/'source').mkdir()
        for name,data in payloads.items():
            target=evidence_dir/'source'/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
        for value in entry_sources:
            data=Path(value).read_bytes()
            if hashlib.sha256(data).hexdigest()!=entry_sources[value]:raise ValueError('Program entry changed')
            (evidence_dir/entry_sources[value]).write_bytes(data)
    started=time.monotonic()
    if tree(fixture)!=before or any(not Path(p).is_file() or sha(p)!=h for p,h in entry_sources.items()):
        raise ValueError('Program source changed before dispatch')
    try:
        proc=subprocess.run(argv,cwd=workdir,env=env,text=True,capture_output=True,timeout=timeout,encoding='utf-8',errors='replace')
        receipt['termination']='returned'
    except subprocess.TimeoutExpired as exc:
        def decoded(value):return value.decode('utf-8',errors='replace') if isinstance(value,bytes) else value or ''
        proc=subprocess.CompletedProcess(argv,None,decoded(exc.stdout),decoded(exc.stderr))
        receipt['termination']='timeout'
    receipt.update(seconds=time.monotonic()-started,exit_code=proc.returncode,
        stdout=proc.stdout,stderr=proc.stderr,source_tree_after=tree(fixture))
    receipt['entry_sources_unchanged']=all(Path(p).is_file() and sha(p)==h for p,h in entry_sources.items())
    receipt['source_unchanged']=before==receipt['source_tree_after'] and receipt['entry_sources_unchanged']
    receipt['stdout_sha256']=hashlib.sha256(proc.stdout.encode()).hexdigest()
    receipt['stderr_sha256']=hashlib.sha256(proc.stderr.encode()).hexdigest()
    if evidence_dir is not None:
        (evidence_dir/'execution.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    return proc,receipt


def program_matches_final(program, final_tree, runtime_files=None):
    """Exact file-set/content match, including deletions and additions.

    Only controller-created fixture markers with their original exact hashes
    may disappear during runtime cleanup. No filename/pattern exception.
    """
    before=program.get('source_tree_before')
    if (program.get('exit_code')!=0 or program.get('termination')!='returned'
            or program.get('source_unchanged') is not True or not isinstance(before,dict)
            or not before or before!=program.get('source_tree_after') or not final_tree):
        return False
    before=dict(before)
    for name,marker in (runtime_files or {}).items():
        if name in final_tree:continue
        import re
        if (name!='AGENTS.md' or not isinstance(marker,dict) or marker.get('purpose')!='generated-hermes-canary'
                or not isinstance(marker.get('content'),str)
                or re.fullmatch(r'EVALUATOR_CONTEXT_CANARY_[0-9a-f]{64}',marker['content']) is None):return False
        expected=hashlib.sha256(marker['content'].encode()).hexdigest()
        if marker.get('sha256')!=expected:return False
        if before.get(name)!=expected:return False
        del before[name]
    return before==final_tree


def intervention_harness_digest():
    from evaluation_measurement import digest
    names=('evaluation_artifact_pilot.py','evaluation_runtime.py','evaluation_hermes_worker.py',
           'evaluation_usage.py','evaluation_measurement.py','evaluation_evidence.py','artifact_hash.py','eval.py')
    return digest({name:sha(Path(__file__).with_name(name)) for name in names})


def intervention_binding(plan, job, contract):
    from evaluation_measurement import digest
    from evaluation_runtime import catalog_exposure
    case=next(c for c in plan['spec']['cases'] if c['id']==job['case'])
    frame=plan.get('candidate_snapshots',{}).get(job['arm'])
    return {'host':plan['spec']['agent'],'catalog':catalog_exposure(job['catalog']),
        'task_sha256':hashlib.sha256(case['prompt'].encode()).hexdigest(),
        'user_decision_sha256':hashlib.sha256(plan['spec']['decision_question'].encode()).hexdigest(),
        'conditions':{k:plan['spec'].get(k) for k in ('timeout','max_iterations','model','reasoning','terminal_backend')},
        'project_sha256':digest(job['initial_tree']),
        'treatment_sha256':frame['package_sha256'] if frame else digest({'optional_target':'absent'}),
        'harness_sha256':intervention_harness_digest(),
        'contract_sha256':digest(contract)}


def require_intervention_qualification(plan):
    """Pre-model admission over bound raw actor-path and independent fit evidence.

    Extends the existing plan/evidence gate; never runs receipt-selected code.
    Probes are collected separately through assembly-only native execution.
    """
    import base64
    from evaluation_evidence import intervention_readiness
    if not is_native(plan['spec']):
        raise ValueError('Unqualified routed artifact dispatch is disabled; use the source-qualified native comparison path')
    results=[]
    for job in plan['jobs']:
        case=next(c for c in plan['spec']['cases'] if c['id']==job['case'])
        attachment=case.get('intervention_evidence',{})
        contract=case.get('intervention_contracts',{}).get(job['arm'])
        if not isinstance(contract,dict) or not attachment.get('path'):
            raise ValueError('Pretrial treatment fidelity and task suitability evidence required; file presence is insufficient')
        from evaluation_evidence import trial_measurement_preflight,trial_measurement_sources
        measured=trial_measurement_preflight(contract.get('measurement'),job['initial_tree'],
            trial_measurement_sources(contract.get('measurement'),job['fixture']))
        if not measured['valid']:raise ValueError('Measurement preflight failed: '+'; '.join(measured['gaps']))
        if plan['spec'].get('agent')!='hermes' or not plan['spec'].get('request_recording_parent'):
            raise ValueError('This lane cannot prove the declared observable without qualified native request recording')
        path=Path(attachment['path'])
        if path.stat().st_size>8*1024*1024 or sha(path)!=attachment.get('sha256'):
            raise ValueError('Frozen intervention evidence missing, changed or oversized')
        evidence=json.loads(path.read_text(encoding='utf-8'))
        sources={key:base64.b64decode(value,validate=True) for key,value in evidence['source_bytes'].items()}
        row=evidence['arms'][job['arm']]
        checked=intervention_readiness(intervention_binding(plan,job,contract),contract,
            row['qualification'],row['review'],sources)
        results.append({'case':job['case'],'arm':job['arm'],**checked,
            'clearance':{'binding':intervention_binding(plan,job,contract),'contract':contract,
                         'qualification':row['qualification'],'review':row['review'],'source_bytes':sources}})
        if not checked['ready']:raise ValueError('Intervention not qualified: '+'; '.join(checked['gaps']))
    return {'required':True,'results':results,'actual_usage_required':True}


def is_native(spec):
    return spec.get('purpose') in ('native-skill-study', 'native-runtime-smoke', 'native-tool-study')


def native_prompt(spec, case, frozen):
    prompt = case['prompt']
    if spec.get('instruction_exposure', 'native-discovery') == 'explicit-body' and frozen:
        prompt += '\n\n<optional-instruction-exposure>\n' + frozen['prompt_text'] + '\n</optional-instruction-exposure>'
    return prompt


def validate(spec):
    if spec.get('purpose') not in ('runtime-smoke', 'injected-instruction-study', 'native-skill-study', 'native-runtime-smoke', 'native-tool-study'):
        raise ValueError('Explicit purpose required: runtime-smoke, injected-instruction-study, native-runtime-smoke or native-skill-study. '
                         'This leaf runner cannot evaluate architecture or delegation workflows.')
    if is_native(spec):
        if spec.get('instruction_exposure', 'native-discovery') not in ('native-discovery', 'explicit-body'):
            raise ValueError('Unknown native instruction exposure')
        if spec.get('instruction_exposure') == 'explicit-body' and spec.get('agent') != 'hermes':
            raise ValueError('Explicit body diagnostic currently supported only on Hermes')
        if spec.get('instruction_exposure') == 'explicit-body' and spec.get('max_workers') != 1:
            raise ValueError('Explicit exposure diagnostic is sequential with setup verification between jobs')
        if (spec.get('agent') not in ('codex', 'hermes') or spec.get('provider') != 'openai-codex'
                or not isinstance(spec.get('model'), str) or not spec['model'].strip()
                or spec.get('reasoning') not in ('low', 'medium', 'high', 'xhigh')):
            raise ValueError('Native skill study requires an explicit codex or hermes host/openai-codex/model/reasoning')
        if spec['purpose'] == 'native-skill-study' and (len(spec['arms']) not in (2, 3) or sum(a.get('instructions') is None for a in spec['arms']) != 1):
            raise ValueError('Native study requires one absent-target baseline and one or two candidates')
        if spec['purpose'] == 'native-runtime-smoke' and (len(spec['arms']) != 1 or spec['arms'][0].get('instructions') is not None or spec.get('catalog')):
            raise ValueError('Native runtime smoke requires one absent optional-skill arm and empty optional catalog')
        if spec['purpose'] == 'native-tool-study':
            from evaluation_tool_study import validate as validate_tool_study
            validate_tool_study(spec)
        if spec.get('prepared_runtime_parent') is not None and spec['agent'] != 'hermes':
            raise ValueError('Explicit prepared runtime parent is supported only by the Hermes adapter')
    if spec['purpose'] in ('runtime-smoke', 'native-runtime-smoke') and len(spec['arms']) * len(spec['cases']) != 1:
        raise ValueError('A runtime smoke is limited to one trial, not a workflow comparison')
    if not 1 <= len(spec['arms']) * len(spec['cases']) <= 12:
        raise ValueError('A pilot is limited to twelve model trials')
    if not 1 <= spec['max_workers'] <= 3 or not 1 <= spec['max_iterations'] <= 64:
        raise ValueError('Invalid worker/iteration ceiling')
    extended = extended_workflow_budget_review(spec)
    if not 1 <= spec['timeout'] <= (extended['seconds'] if extended else 600):
        raise ValueError('Invalid time ceiling')
    if not (spec['purpose']=='native-tool-study' and spec.get('quota_remaining') is None) and (not isinstance(spec['quota_remaining'], (int, float)) or not 0 < spec['quota_remaining'] <= 100):
        raise ValueError('An observed nonzero subscription quota is required')
    if len({a['id'] for a in spec['arms']}) != len(spec['arms']):
        raise ValueError('Duplicate arm')
    if len({c['id'] for c in spec['cases']}) != len(spec['cases']):
        raise ValueError('Duplicate case')


def extended_workflow_budget_review(spec):
    """One explicitly reviewed Hermes pair, not a new default or authority grant."""
    review = spec.get('extended_workflow_budget')
    if review is None: return None
    if (spec.get('purpose') != 'native-skill-study' or spec.get('agent') != 'hermes'
            or spec.get('max_workers') != 1 or len(spec.get('cases', [])) != 1
            or len(spec.get('arms', [])) != 2):
        raise ValueError('Extended workflow budget requires one sequential Hermes skill pair')
    fields = ('case_id','reviewer','authority','adequacy_rationale')
    if not isinstance(review,dict) or any(not isinstance(review.get(k),str) or not review[k].strip() for k in fields):
        raise ValueError('Explicit reviewed extended workflow budget required')
    seconds = review.get('seconds')
    if (type(seconds) is not int or not 600 < seconds <= 1800 or seconds != spec['timeout']
            or review.get('iterations') != spec['max_iterations']
            or review['case_id'] != spec['cases'][0]['id']):
        raise ValueError('Extended workflow budget must bind this case and actual bounded limits')
    workflow_budget_review(spec)
    return {'seconds':seconds,'iterations':spec['max_iterations'],'case_id':review['case_id'],
            'automatic_authorization':False,'semantic_adequacy_automatically_proven':False}


def workflow_budget_review(spec):
    """Validate declared review, not semantic budget adequacy or reviewer identity."""
    comparison = spec.get('purpose') in ('native-skill-study','native-tool-study','injected-instruction-study') and len(spec.get('arms',[])) > 1
    if not comparison: return {'required':False}
    required = ('claim','required_quality','verification_and_revision','adequacy_rationale','reviewer')
    reviews = {}
    for case in spec['cases']:
        review = case.get('workflow_budget')
        if not isinstance(review,dict) or any(not isinstance(review.get(k),str) or not review[k].strip() for k in required):
            raise ValueError('Comparison requires task/claim workflow_budget review including quality, verification/revision and budget adequacy')
        reviews[case['id']] = review
    for arm in spec['arms']:
        if any(k in arm and arm[k] != spec[k] for k in ('timeout','max_iterations')):
            raise ValueError('Workflow budget must give matched arms equal resource limits')
    return {'required':True,'seconds':spec['timeout'],'iterations':spec['max_iterations'],
            'reviews':reviews,'semantic_adequacy_automatically_proven':False}


def artifact_control_preflight(spec, out):
    """Exercise the SAME oracle on independently supplied known artifacts.

    Reviewer still owns task realism, assertion requirements and whether the
    alternatives/defects are substantive. Counts alone cannot prove any of it.
    """
    import ast
    from evaluation_measurement import digest
    results=[]
    for case in spec['cases']:
        review=case.get('task_qualification', {})
        if (any(not isinstance(review.get(k),str) or not review[k].strip() for k in
                ('workload_source','claim','representative_demands','scope_limits','reviewer'))
                or review.get('outcome_driven') is not True or review.get('solution_open') is not True):
            raise ValueError('Reviewed outcome/workload qualification required')
        if review.get('output_kind') not in ('text','program','rendered-product'):
            raise ValueError('Declare actual task output kind for relevant evidence requirements')
        controls=case.get('artifact_controls', [])
        if not isinstance(controls,list) or not controls:raise ValueError('Executed artifact controls required')
        good=set();bad=False
        for index,control in enumerate(controls):
            if (type(control.get('expected_pass')) is not bool
                    or not isinstance(control.get('rationale'),str) or not control['rationale'].strip()):
                raise ValueError('Control needs expected outcome and requirement/risk rationale')
            source=Path(control['fixture']).resolve()
            destination=Path(out)/case['id']/str(index)
            destination.parent.mkdir(parents=True,exist_ok=True)
            proc,receipt=run_bound_program([sys.executable,spec['oracle'],str(source),case['id']],
                source,90,evidence_dir=destination)
            try:value=json.loads(proc.stdout)
            except ValueError:value={}
            if (not isinstance(value,dict) or type(value.get('passed')) is not int or type(value.get('failed')) is not int
                    or value['passed']<0 or value['failed']<0 or value['passed']+value['failed']==0
                    or not isinstance(value.get('failures'),list) or bool(value['failures'])!=(value['failed']>0)
                    or receipt['termination']!='returned' or not receipt['source_unchanged']
                    or (proc.returncode==0)!=(value['failed']==0)):
                raise ValueError('Control oracle crashed, timed out or returned invalid evidence; not a demonstrated rejection')
            passed=proc.returncode==0 and value['failed']==0
            if passed!=control['expected_pass']:raise ValueError('Artifact control contradicts actual oracle')
            # Non-test Python AST distinguishes executable alternatives from
            # comment-only copies. Other languages remain explicitly reviewed.
            class WithoutDocstrings(ast.NodeTransformer):
                def clean(self,node):
                    self.generic_visit(node)
                    if (node.body and isinstance(node.body[0],ast.Expr)
                            and isinstance(node.body[0].value,ast.Constant) and isinstance(node.body[0].value.value,str)):
                        node.body=node.body[1:]
                    return node
                visit_Module=visit_ClassDef=visit_FunctionDef=visit_AsyncFunctionDef=clean
            executable={name:ast.dump(WithoutDocstrings().visit(ast.parse((source/name).read_text(encoding='utf-8'))),include_attributes=False)
                for name in receipt['source_tree_before'] if name.endswith('.py')
                and not Path(name).name.startswith('test')}
            if passed:
                reviewed=control.get('executable_distinctness_review',{})
                peers=sorted(digest(tree(Path(c['fixture']))) for c in controls if c.get('expected_pass') is True)
                decision=('single-implementation-justified' if review.get('alternatives_not_applicable')
                          else 'substantively-different')
                if (reviewed.get('source_tree_sha256')!=digest(receipt['source_tree_before'])
                        or reviewed.get('comparison_source_trees_sha256')!=peers
                        or reviewed.get('oracle_sha256')!=sha(spec['oracle'])
                        or reviewed.get('independent') is not True or not reviewed.get('reviewer')
                        or reviewed.get('decision')!=decision
                        or not isinstance(reviewed.get('rationale'),str) or not reviewed['rationale'].strip()):
                    raise ValueError('Source-bound independent substantive implementation review required for every adequate control')
                non_python={name:value for name,value in receipt['source_tree_before'].items()
                            if not name.endswith('.py')}
                if non_python:
                    reviewed=control.get('executable_distinctness_review', {})
                    from evaluation_measurement import digest
                    if (reviewed.get('source_tree_sha256')!=digest(receipt['source_tree_before'])
                            or reviewed.get('independent') is not True
                            or not isinstance(reviewed.get('rationale'),str) or not reviewed['rationale'].strip()):
                        raise ValueError('Non-Python executable distinction requires source-bound independent review; byte differences alone are insufficient')
                    executable['<independently-reviewed-other-source>']=non_python
                if not executable:raise ValueError('Missing implementation evidence')
                good.add(hashlib.sha256(json.dumps(executable,sort_keys=True).encode()).hexdigest())
            else:bad=True
            results.append({'case':case['id'],'control':index,'passed':passed,'execution':receipt})
        minimum=1 if isinstance(review.get('alternatives_not_applicable'),str) and review['alternatives_not_applicable'].strip() else 2
        if len(good)<minimum or not bad:raise ValueError('Distinct executable adequate alternatives and broken rejection required')
    return {'ready':True,'controls':results,'semantic_adequacy_automatically_proven':False}


def termination_assessment(worker, oracle):
    """Keep final quality distinct from partial artifacts, time and cost coverage."""
    deadline = worker.get('turn_deadline',{}).get('fired') is True
    reason = ('deadline' if deadline else worker.get('termination_reason') or ('returned' if worker.get('ok') else 'runtime_failure_or_unknown'))
    complete = bool(worker.get('ok') and not deadline)
    artifact_pass = bool(isinstance(oracle,dict) and oracle.get('passed',0)>0 and oracle.get('failed')==0 and oracle.get('failures')==[])
    return {'termination_reason':reason,'completed':complete,'censored':not complete,
            'final_quality':'pending-substantive-review' if complete and artifact_pass else 'failed' if complete else 'unassessed-incomplete',
            'artifact_check_pass':artifact_pass,'artifact_scope':'final artifact' if complete else 'partial artifact after termination',
            'assessment_schema_version':2,'runtime_completed':complete,
            'deterministic_invariants_passed':artifact_pass,
            'semantic_adequacy':{'status':'pending','passed':None},
            'comparative_preference':{'status':'not-assessed','winner':None},
            'task_passed':False if complete and not artifact_pass else None,
            'overall_cost_qualification':'requires existing complete root/worker/reviewer/support/failure accounting; unknown is not zero'}


def prepare(spec, out):
    validate(spec)
    workflow_budget_review(spec)
    if spec['purpose']=='native-tool-study':
        from evaluation_tool_study import prepare as prepare_tool_study
        return prepare_tool_study(spec,out)
    if (out / 'plan.json').exists():
        raise ValueError('Plan already exists; use run without preparing again')
    out.mkdir(parents=True, exist_ok=True)
    if len(spec['arms'])>1:
        controls=artifact_control_preflight(spec,out/'oracle-controls')
        (out/'oracle-control-preflight.json').write_text(json.dumps(controls,indent=2)+'\n',encoding='utf-8')
    workroot = Path(spec['workspace_root']).resolve()
    workroot.mkdir(parents=True, exist_ok=True)
    projection = 'native-catalog' if is_native(spec) and spec.get('instruction_exposure') != 'explicit-body' else 'inline-linked-text-only'
    frames = {a['id']: freeze_candidate(Path(a['instructions']), projection=projection) if a.get('instructions') else None for a in spec['arms']}
    source_trees = {}
    common_catalog = {}
    if is_native(spec):
        source_trees = {case['id']: tree(Path(case['fixture'])) for case in spec['cases']}
        common_catalog = {str(Path(source)): freeze_candidate(Path(source), projection='native-catalog') for source in spec.get('catalog', [])}
    jobs = []
    for index, case in enumerate(spec['cases']):
        # Rotate ordering without changing any case/prompt across arms.
        arms = spec['arms'][index % len(spec['arms']):] + spec['arms'][:index % len(spec['arms'])]
        for arm in arms:
            ident = uuid.uuid4().hex
            fixture = workroot / ident
            shutil.copytree(case['fixture'], fixture)
            if is_native(spec):
                if tree(fixture) != source_trees[case['id']]:
                    raise ValueError('Copied fixture differs from shared frozen source')
                sources = [(Path(source), common_catalog[str(Path(source))]) for source in spec.get('catalog', [])]
                if arm.get('instructions') and spec.get('instruction_exposure') != 'explicit-body':
                    sources.append((Path(arm['instructions']), frames[arm['id']]))
                catalog = []
                catalog_frames = {}
                for source, frozen_catalog in sources:
                    if source.name != 'SKILL.md':
                        raise ValueError('Native discovery requires a SKILL.md package')
                    destination = fixture / '.agents' / 'skills' / source.parent.name
                    if destination.exists():
                        raise ValueError('Catalog package name collision')
                    destination.mkdir(parents=True)
                    for relative, digest in frozen_catalog['files'].items():
                        origin = source.parent / relative
                        with origin.open('rb') as stream:
                            data = stream.read(frozen_catalog['file_sizes'][relative] + 1)
                        if hashlib.sha256(data).hexdigest() != digest:
                            raise ValueError('Catalog source changed before staging')
                        target = destination / relative
                        target.parent.mkdir(parents=True, exist_ok=True)
                        target.write_bytes(data)
                    staged_skill = destination / 'SKILL.md'
                    if freeze_candidate(staged_skill, projection='native-catalog')['package_sha256'] != frozen_catalog['package_sha256']:
                        raise ValueError('Catalog source changed while staging')
                    catalog_frames[str(staged_skill)] = frozen_catalog['package_sha256']
                    catalog.append(str(staged_skill))
                instructions = None
            else:
                catalog = []
                catalog_frames = {}
                instructions = frames[arm['id']]['prompt_text']
            prompt = case['prompt'] + '\n\nProject: ' + str(fixture) + '\nWork only in this project. Do not delegate, use network services, or modify parent directories.'
            if is_native(spec):
                prompt = native_prompt(spec, case, frames[arm['id']])
            jobs.append({'catalog_frames': catalog_frames, 'catalog': catalog, 'id': ident, 'arm': arm['id'], 'case': case['id'],
                         'fixture': str(fixture), 'initial_tree': tree(fixture),
                         'instructions': instructions, 'prompt': prompt})
    plan = {'spec': spec, 'jobs': jobs, 'candidate_snapshots': frames,
            'prepared_timestamp_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
            'oracle_sha256': sha(spec['oracle']), 'controller_sha256': sha(__file__),
            'worker_sha256': sha(Path(__file__).with_name('evaluation_artifact_worker.py')),
            'native_hermes_worker_sha256': sha(Path(__file__).with_name('evaluation_hermes_worker.py')),
            'runtime_sha256': sha(Path(__file__).with_name('evaluation_runtime.py')),
            'measurement_sha256': sha(Path(__file__).with_name('evaluation_measurement.py')),
            'usage_observer_sha256': sha(Path(__file__).with_name('evaluation_usage.py')),
            'kind': spec['purpose'], 'workflow_comparison_supported': False,
            'resource_limits': {'timeout_seconds': spec['timeout'],
                                'max_iterations': spec['max_iterations'] if spec.get('agent') == 'hermes' else None,
                                'iteration_limit_enforced': spec.get('agent') == 'hermes'}}
    if is_native(spec):
        plan.update(case_source_trees=source_trees, common_catalog_snapshots=common_catalog)
    if len(spec['arms'])>1:
        plan['oracle_control_preflight_sha256']=sha(out/'oracle-control-preflight.json')
    (out / 'plan.json').write_text(json.dumps(plan, indent=2) + '\n', encoding='utf-8')
    return plan


def prior_attempts(plan):
    """Bind completed attempt receipts; never authorize a retry or grant admission."""
    refs = plan.get('prior_attempts', [])
    if not refs:
        return {}
    if not is_native(plan['spec']):
        raise ValueError('Attempt continuation requires the native artifact owner')
    bound = {}
    jobs = {job['id']: job for job in plan['jobs']}
    for ref in refs:
        if sha(ref['report']) != ref['report_sha256'] or sha(ref['plan']) != ref['plan_sha256']:
            raise ValueError('Prior attempt source binding changed')
        old_plan = json.loads(Path(ref['plan']).read_bytes())
        report = json.loads(Path(ref['report']).read_bytes())
        for key in ('agent', 'provider', 'model', 'reasoning', 'timeout', 'max_iterations', 'instruction_exposure', 'terminal_backend'):
            if old_plan['spec'].get(key) != plan['spec'].get(key):
                raise ValueError('Prior attempt task/runtime route changed')
        for ident in ref['job_ids']:
            rows = [r for r in report['results'] if r['id'] == ident]
            old = [j for j in old_plan['jobs'] if j['id'] == ident]
            if ident in bound or ident not in jobs or len(rows) != 1 or len(old) != 1 or old[0] != jobs[ident]:
                raise ValueError('Prior attempt is missing, duplicated or differs from original job')
            if (rows[0]['arm'], rows[0]['case']) != (jobs[ident]['arm'], jobs[ident]['case']):
                raise ValueError('Prior attempt membership mismatch')
            bound[ident] = rows[0]
    return bound


def validate_jobs(plan):
    """Check the entire launch set before runtime discovery or any trial starts.

    This is consistency validation, not a signature over a hostile controller's
    plan and not evidence that an experiment can distinguish workflows.
    """
    spec = plan['spec']
    if spec['purpose']=='native-tool-study':
        from evaluation_tool_study import validate_prepared
        return validate_prepared(plan)
    cases = {case['id']: case for case in spec['cases']}
    expected = {(arm['id'], case) for arm in spec['arms'] for case in cases}
    jobs = plan['jobs']
    prior = prior_attempts(plan)
    if is_native(spec):
        if set(plan.get('case_source_trees', {})) != set(cases):
            raise ValueError('Shared frozen fixture inventory changed')
        if set(plan.get('common_catalog_snapshots', {})) != {str(Path(source)) for source in spec.get('catalog', [])}:
            raise ValueError('Shared frozen catalog inventory changed')
    if len(jobs) != len(expected):
        raise ValueError('Prepared trial count differs from the declared suite')
    seen_pairs, seen_ids = set(), set()
    workroot = Path(spec['workspace_root']).resolve()
    if spec.get('request_recording_parent'):
        parent = Path(spec['request_recording_parent'])
        if (spec.get('agent') != 'hermes' or not parent.is_absolute() or parent.resolve() != parent.absolute()
                or not parent.is_dir() or parent == Path(parent.anchor)):
            raise ValueError('Request recording needs a caller-provisioned canonical Hermes archive parent')
        for item in jobs:
            fixture = Path(item['fixture']).resolve()
            if parent.is_relative_to(fixture) or fixture.is_relative_to(parent):
                raise ValueError('Request recording parent must be separate from all actor fixtures')
    if spec.get('prepared_runtime_parent'):
        parent = Path(spec['prepared_runtime_parent'])
        if (not parent.is_absolute() or parent == Path(parent.anchor) or parent.resolve() != parent.absolute()
                or not parent.is_dir() or any(parent.iterdir())):
            raise ValueError('Prepared runtime parent must be a fresh caller-provisioned canonical private directory')
        for item in jobs:
            fixture = Path(item['fixture']).resolve()
            if parent.is_relative_to(fixture) or fixture.is_relative_to(parent):
                raise ValueError('Prepared runtime parent must be separate from every model fixture')
    for item in jobs:
        pair = (item['arm'], item['case'])
        ident = item['id']
        if pair not in expected or pair in seen_pairs:
            raise ValueError('Prepared arm/case membership changed')
        if not isinstance(ident, str) or len(ident) != 32 or any(c not in '0123456789abcdef' for c in ident) or ident in seen_ids:
            raise ValueError('Prepared trial identity is invalid or duplicated')
        seen_pairs.add(pair)
        seen_ids.add(ident)
        fixture = Path(item['fixture']).resolve()
        if fixture != workroot / ident or not fixture.is_dir():
            raise ValueError('Prepared fixture location changed')
        prompt = cases[item['case']]['prompt'] + '\n\nProject: ' + item['fixture'] + '\nWork only in this project. Do not delegate, use network services, or modify parent directories.'
        if is_native(spec):
            arm = next(a for a in spec['arms'] if a['id'] == item['arm'])
            prompt = native_prompt(spec, cases[item['case']], plan['candidate_snapshots'][item['arm']])
            sources = [(Path(source), plan['common_catalog_snapshots'][str(Path(source))]) for source in spec.get('catalog', [])]
            if arm.get('instructions') and spec.get('instruction_exposure') != 'explicit-body':
                sources.append((Path(arm['instructions']), plan['candidate_snapshots'][item['arm']]))
            expected_tree = dict(plan['case_source_trees'][item['case']])
            declared_catalog = {}
            for source, frozen in sources:
                relative_root = '.agents/skills/' + source.parent.name + '/'
                staged = str(fixture / relative_root / 'SKILL.md')
                if staged in declared_catalog or any(relative.startswith(relative_root) for relative in expected_tree):
                    raise ValueError('Catalog package name collision')
                declared_catalog[staged] = frozen['package_sha256']
                expected_tree.update({relative_root + relative: digest for relative, digest in frozen['files'].items()})
            expected_catalog = sorted(str(p) for p in (fixture / '.agents' / 'skills').glob('*/SKILL.md'))
            if sorted(item.get('catalog', [])) != expected_catalog or expected_catalog != sorted(declared_catalog):
                raise ValueError('Prepared native catalog changed')
            if item['catalog_frames'] != declared_catalog:
                raise ValueError('Staged native catalog differs from shared frozen package')
            for skill_path, frozen_hash in item['catalog_frames'].items():
                if skill_path not in expected_catalog or freeze_candidate(Path(skill_path), projection='native-catalog')['package_sha256'] != frozen_hash:
                    raise ValueError('Staged native catalog differs from frozen package')
            if item['initial_tree'] != expected_tree:
                raise ValueError('Prepared fixture differs from shared frozen source and catalog')
            if item['instructions'] is not None:
                raise ValueError('Native study cannot inject instructions')
        if item['prompt'] != prompt:
            raise ValueError('Prepared prompt differs from the declared case')
        if not is_native(spec) and item['instructions'] != plan['candidate_snapshots'][item['arm']]['prompt_text']:
            raise ValueError('Prepared instructions differ from the frozen candidate')
        expected_current = prior[ident]['final_tree'] if ident in prior else item['initial_tree']
        if tree(fixture) != expected_current:
            raise ValueError('Prepared fixture contents changed')


def run(plan, out):
    workflow_budget_review(plan['spec'])
    import os
    spec = plan['spec']
    validate(spec)
    if spec['purpose']=='native-tool-study':
        from evaluation_tool_study import validate_prepared,require_native_dispatch
        validate_prepared(plan)
        require_native_dispatch()  # Before runtime discovery, credentials or a model.
    if sha(spec['oracle']) != plan['oracle_sha256']:
        raise ValueError('Frozen oracle changed')
    if sha(__file__) != plan['controller_sha256'] or sha(Path(__file__).with_name('evaluation_artifact_worker.py')) != plan['worker_sha256']:
        raise ValueError('Frozen execution code changed')
    if sha(Path(__file__).with_name('evaluation_measurement.py')) != plan.get('measurement_sha256'):
        raise ValueError('Frozen measurement projection changed')
    if sha(Path(__file__).with_name('evaluation_usage.py')) != plan.get('usage_observer_sha256'):
        raise ValueError('Frozen usage observer changed')
    validate_jobs(plan)
    require_intervention_qualification(plan)  # Before credential/runtime/model dispatch.
    if len(spec['arms'])>1 and sha(out/'oracle-control-preflight.json')!=plan.get('oracle_control_preflight_sha256'):
        raise ValueError('Frozen executed oracle-control preflight changed')
    if is_native(spec):
        if sha(Path(__file__).with_name('evaluation_runtime.py')) != plan['runtime_sha256']:
            raise ValueError('Frozen native runtime changed')
        if spec['agent'] == 'hermes' and sha(Path(__file__).with_name('evaluation_hermes_worker.py')) != plan['native_hermes_worker_sha256']:
            raise ValueError('Frozen native Hermes worker changed')
        return run_native_plan(plan, out)
    python, native = native_hermes_runtime(native_executable('hermes'))
    owner = str(hermes_owner_home(dict(os.environ)))
    source = str(Path(__file__).resolve().parents[1])
    def one(item):
        path = out / item['id']
        if path.exists():
            raise ValueError('Trial output exists: implicit reruns are forbidden')
        path.mkdir()
        fixture = Path(item['fixture'])
        if tree(fixture) != item['initial_tree']:
            raise ValueError('Initial fixture changed')
        runtime = Path(tempfile.mkdtemp(prefix='host-', dir=Path(spec['workspace_root'])))
        env = runtime_environment(dict(os.environ), runtime)
        request = {'schema_version': 3, 'task_class': spec['protocol'],
            'requirements': {'tools': ['patch', 'process_manage', 'read_file', 'search_files', 'terminal', 'write_file'],
                'context_tokens': 16000, 'task_contract_sha256': plan['oracle_sha256'],
                'model': spec['model'], 'reasoning_effort': spec['reasoning']},
            'verifier': {'kind': 'deterministic', 'independent': True, 'coverage': 'complete',
                'scope': 'artifact-effects', 'evidence': {'locator': spec['oracle'], 'sha256': plan['oracle_sha256']}},
            'effects': 'reversible', 'failure_cost': 'low', 'deterministic': None,
            'budget': {'objective': 'quota', 'api_remaining': 0, 'api_reserve': 0, 'allow_api_spend': False,
                'quotas': {'codex-main': {'remaining': spec['quota_remaining'], 'reserve': 0, 'unit': 'percentage-points'}},
                'unknown_cost_policy': 'explicit_preference', 'preference_order': [spec['route_id']],
                'parent_available': True, 'attempt_cap': 1, 'attempts_used': 0,
                'fallback_route_id': None, 'fallback_route_sha256': None}}
        job = {**item, 'output': str(path / 'worker.json'), 'source': source, 'native_source': str(native),
               'credential_owner_home': owner, 'model': spec['model'], 'reasoning': spec['reasoning'],
               'max_iterations': spec['max_iterations'], 'timeout': spec['timeout'], 'route_request': request}
        (path / 'job.json').write_text(json.dumps(job, indent=2) + '\n', encoding='utf-8')
        started = time.monotonic()
        result = {'id': item['id'], 'arm': item['arm'], 'case': item['case'], 'ok': False}
        try:
            proc = subprocess.run([str(python), str(Path(__file__).with_name('evaluation_artifact_worker.py'))],
                input=json.dumps(job), text=True, encoding='utf-8', capture_output=True,
                env=env, cwd=fixture, timeout=spec['timeout'] + 90)
            result['worker_exit_code'] = proc.returncode
            worker_path = path / 'worker.json'
            if not worker_path.is_file():
                result['error'] = 'Worker exited without a durable result'
            else:
                worker = json.loads(worker_path.read_text(encoding='utf-8'))
                result['routing_outcome'] = worker.get('routing', {}).get('decision', {}).get('outcome')
                result['worker_ok'] = worker['ok']
                result['native'] = {k: worker.get('native', {}).get(k) for k in
                                    ('status', 'exit_reason', 'tokens', 'api_calls', 'duration_seconds', 'cost_status')}
                if sha(spec['oracle']) != plan['oracle_sha256']:
                    raise ValueError('Oracle changed during candidate execution')
                oracle, execution = run_bound_program([sys.executable, spec['oracle'], str(fixture), item['case']],
                    fixture,90,evidence_dir=path/'oracle-execution')
                result['oracle_execution'] = execution
                result['oracle_exit_code'] = oracle.returncode
                (path / 'oracle-output.txt').write_text(oracle.stdout + oracle.stderr, encoding='utf-8')
                try:
                    result['oracle'] = json.loads(oracle.stdout)
                except ValueError:
                    result['oracle'] = {'error': 'Invalid oracle output'}
                checked = result['oracle']
                result['oracle_valid_success'] = (
                    isinstance(checked, dict)
                    and type(checked.get('passed')) is int and checked['passed'] > 0
                    and type(checked.get('failed')) is int and checked['failed'] == 0
                    and checked.get('failures') == []
                )
                result['ok'] = bool(worker['ok'] and oracle.returncode == 0
                                    and execution['source_unchanged'] and result['oracle_valid_success'])
        except subprocess.TimeoutExpired:
            result['error'] = 'Bounded worker or oracle timeout; do not infer task failure from missing evidence'
        finally:
            result['seconds_including_verification'] = time.monotonic() - started
            result['final_tree'] = tree(fixture)
            shutil.rmtree(runtime)
            result['isolated_runtime_removed'] = not runtime.exists()
            (path / 'result.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
        print(json.dumps({k: result.get(k) for k in ('arm','case','ok','routing_outcome','seconds_including_verification')}), flush=True)
        return result
    started = time.monotonic()
    with ThreadPoolExecutor(max_workers=spec['max_workers']) as pool:
        results = list(pool.map(one, plan['jobs']))
    report = {'kind': spec['purpose'], 'workflow_comparison_supported': False,
              'timestamp_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
              'results': results, 'seconds': time.monotonic() - started,
              'completed_trials': len(results), 'expected_trials': len(plan['jobs']), 'admission': False}
    from evaluation_measurement import attach_measurements
    attach_measurements(report, plan)
    (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    return report



def run_native_plan(plan, out):
    from evaluation_runtime import run_native_skill_study
    spec = plan['spec']
    workflow_budget_review(spec)
    qualification=require_intervention_qualification(plan)
    if spec.get('agent') == 'hermes' and not spec.get('request_recording_parent'):
        raise ValueError('New Hermes runs require an explicit evaluator-owned request_recording_parent; no fallback')
    prior = prior_attempts(plan)
    pending = [job for job in plan['jobs'] if job['id'] not in prior]
    def one(item):
        path = out / item['id']
        if path.exists():
            raise ValueError('Trial output exists: implicit reruns forbidden')
        path.mkdir()
        fixture = Path(item['fixture'])
        result = {'id': item['id'], 'arm': item['arm'], 'case': item['case'], 'ok': False, 'oracle_seconds': None}
        started = time.monotonic()
        recording = None
        if spec.get('request_recording_parent'):
            from evaluation_measurement import digest
            recording = {'directory': str(Path(spec['request_recording_parent']) / ('requests-' + item['id'])),
                'binding': {'run_id': item['id'], 'case_id': item['case'], 'arm': item['arm'],
                    'plan_sha256': digest(plan), 'task_sha256': hashlib.sha256(item['prompt'].encode()).hexdigest(),
                    'oracle_sha256': plan['oracle_sha256']}}
        prepared = None
        if spec.get('prepared_runtime_parent'):
            # Provisioning/privacy authority belongs to the explicit caller.
            # No alternate allocation is selected if this operation fails.
            parent = Path(spec['prepared_runtime_parent'])
            if not parent.is_absolute() or parent.resolve() != parent.absolute() or not parent.is_dir():
                raise ValueError('Prepared runtime parent must be a caller-provisioned canonical private directory')
            prepared = parent / item['id']
            prepared.mkdir()
        clearance=next(r['clearance'] for r in qualification['results'] if r['case']==item['case'] and r['arm']==item['arm'])
        worker = run_native_skill_study(item['prompt'], fixture, spec['timeout'], item['catalog'],
                                       intervention_clearance=clearance,
                                       agent=spec['agent'], max_iterations=spec['max_iterations'],
                                       model=spec['model'], reasoning=spec['reasoning'], prepared_runtime=prepared,
                                       **({'terminal_backend':spec['terminal_backend']} if spec.get('terminal_backend') else {}),
                                       **({'request_recording': recording} if recording else {}))
        if spec.get('terminal_backend'):
            observed_backend = worker.get('terminal_backend', {})
            result['backend_setup_ok'] = (observed_backend.get('name') == spec['terminal_backend']
                                           and observed_backend.get('registration_verified') is True)
            if not result['backend_setup_ok']:
                worker['ok'] = False
                worker['failure_attribution'] = {'category':'evaluator-setup',
                    'evidence_sha256':hashlib.sha256(json.dumps(observed_backend,sort_keys=True).encode()).hexdigest()}
        skill=clearance.get('contract',{}).get('skill_evaluation')
        if skill:
            from evaluation_evidence import skill_effect_exposure
            try:
                import re
                root=Path(recording['directory']);manifest_bytes=(root/'manifest.json').read_bytes();manifest=json.loads(manifest_bytes)
                sources=dict(clearance['source_bytes'])
                for blob in manifest['blobs']:
                    if blob['kind']!='final-request':continue
                    if not re.fullmatch(r'[0-9]{6}-final-request\.bin',blob['file']):raise ValueError('Unsafe request source')
                    target=root/blob['file']
                    if target.is_symlink() or target.stat().st_size>16*1024*1024:raise ValueError('Request source outside evidence bounds')
                    sources[blob['sha256']]=target.read_bytes()
                result['skill_exposure']=skill_effect_exposure(clearance['contract'],worker,manifest_bytes,sources)
            except (KeyError,TypeError,ValueError,OSError) as exc:
                result['skill_exposure']={'qualified':False,'continue_skill_effect_review':False,'gaps':['Target-specific recorded exposure unavailable: '+type(exc).__name__]}
            result['exposure_setup_ok']=result['skill_exposure']['qualified']
        elif spec.get('instruction_exposure') == 'explicit-body':
            trace = worker.get('native_usage', {}).get('lifecycle', {}).get('exposure_events', [])
            expected_body = next(arm for arm in spec['arms'] if arm['id'] == item['arm']).get('instructions') is not None
            result['exposure_setup_ok'] = bool(trace and trace[0].get('optional_body_present') is expected_body
                and trace[0].get('terminal_contract_present') is True and (trace[0].get('tool_count') or 0)>0)
            if not result['exposure_setup_ok']:
                worker['failure_attribution'] = {'category':'evaluator-setup',
                    'evidence_sha256': hashlib.sha256(json.dumps(trace,sort_keys=True).encode()).hexdigest()}
        (path / 'worker.json').write_text(json.dumps(worker, indent=2)+'\n', encoding='utf-8')
        result['native'] = worker
        from evaluation_evidence import trial_measurement_verdict
        measurement=clearance['contract']['measurement'];sources=dict(clearance['source_bytes'])
        manifest_bytes=None
        try:
            root=Path(recording['directory']);manifest_bytes=(root/'manifest.json').read_bytes();manifest=json.loads(manifest_bytes)
            for blob in manifest['blobs']:
                if blob['kind']!='final-request':continue
                name=blob['file']
                import re
                if not re.fullmatch(r'[0-9]{6}-final-request\.bin',name):raise ValueError('unsafe measurement blob')
                source=root/name
                if source.is_symlink() or source.stat().st_size>16*1024*1024:raise ValueError('unsafe measurement source')
                sources[blob['sha256']]=source.read_bytes()
        except (OSError,KeyError,TypeError,ValueError):manifest_bytes=None
        result['trial_validity']=trial_measurement_verdict(measurement,worker,manifest_bytes,sources,
            recording['binding'],item['initial_tree'],fixture=fixture)
        try:
            if not result['trial_validity']['valid']:raise ValueError('Invalid trial measurement; repair before dependent work')
            if sha(spec['oracle']) != plan['oracle_sha256']:
                raise ValueError('Frozen oracle changed during execution')
            before = time.monotonic()
            oracle, execution = run_bound_program([sys.executable, spec['oracle'], str(fixture), item['case']],
                fixture,90,evidence_dir=path/'oracle-execution')
            result['oracle_execution'] = execution
            result['oracle_seconds'] = time.monotonic() - before
            (path / 'oracle-output.txt').write_text(oracle.stdout + oracle.stderr, encoding='utf-8')
            checked = json.loads(oracle.stdout)
            result['oracle'] = checked
            result['oracle_exit_code'] = oracle.returncode
            from evaluation_evidence import trial_oracle_validity
            if not trial_oracle_validity(checked,execution,oracle.returncode)['valid']:
                raise ValueError('Oracle did not produce a bound usable test result')
            result['ok'] = bool(worker['ok'] and execution['source_unchanged'] and oracle.returncode == 0 and type(checked.get('passed')) is int and checked['passed'] > 0 and type(checked.get('failed')) is int and checked['failed'] == 0 and checked.get('failures') == [])
        except Exception as exc:
            result['error'] = type(exc).__name__ + ': ' + str(exc)
            if result.get('trial_validity',{}).get('valid') is True:
                result['trial_validity']={**result['trial_validity'],'valid':False,'status':'invalid',
                    'gaps':['independent test execution/protocol unqualified'],'continue_dependent_trials':False,
                    'repair_and_requalification_required':True,'failure_scope':'runtime'}
        result['seconds_including_verification'] = time.monotonic() - started
        result['outcome_assessment'] = termination_assessment(worker,result.get('oracle') if result.get('oracle_exit_code') == 0 else None)
        result['ok'] = bool(result['ok'] and result['outcome_assessment']['completed'])
        if result.get('exposure_setup_ok') is False:result['ok']=False
        if result.get('skill_exposure'):
            result['outcome_assessment']['skill_effect_qualification']=result['skill_exposure']
        result['ok_scope'] = 'legacy runtime plus deterministic oracle gate; not completed-task or semantic success'
        result['final_tree'] = tree(fixture)
        programs=worker.get('terminal_backend', {}).get('program_executions', [])
        bound=program_matches_final(result.get('oracle_execution',{}),result['final_tree'])
        case=next(c for c in spec['cases'] if c['id']==item['case'])
        program_required=case.get('task_qualification',{}).get('output_kind')=='program'
        result['outcome_assessment']['execution_provenance']={
            'required':program_required,'final_artifact_program_linked':bound,'execution_authenticated':False,
            'actor_verification_links':[program_matches_final(p,result['final_tree'],worker.get('runtime_generated_fixture_files')) for p in programs],
            'scope':'Independent oracle program binds exact final file set; actor checks separate, external imports not attested'}
        if program_required and not bound: result['ok']=False
        if recording:
            from evaluation_measurement import digest
            from evaluation_usage import bind_recorded_output
            try:
                result['request_recording'] = bind_recorded_output(recording['directory'],
                    worker.get('request_recording', {}), recording['binding'],
                    {'oracle_sha256': plan['oracle_sha256'], 'oracle_exit_code': result.get('oracle_exit_code'),
                     'oracle_result_sha256': digest(result.get('oracle')),
                     'outcome_schema_version':2,
                     'deterministic_invariants_passed':result['outcome_assessment']['deterministic_invariants_passed'],
                     'task_passed':result['outcome_assessment']['task_passed'],
                     'final_tree_sha256': digest(result['final_tree']),
                     'final_response_sha256': hashlib.sha256((worker.get('final_response') or '').encode()).hexdigest()})
                if not result['request_recording']['complete']:
                    result['ok'] = False
            except Exception as exc:
                result['request_recording'] = {'complete': False, 'error_type': type(exc).__name__,
                                               'execution_authenticated': False}
                result['ok'] = False
        if recording and result.get('request_recording',{}).get('complete') is not True:
            result['trial_validity']={**result['trial_validity'],'valid':False,'status':'invalid',
                'gaps':['final output/recording evidence incomplete'],'continue_dependent_trials':False,
                'repair_and_requalification_required':True,'failure_scope':'runtime'}
        (path / 'result.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
        return result
    started = time.monotonic()
    if spec.get('instruction_exposure') == 'explicit-body' or spec.get('request_recording_parent'):
        results = []
        blocked_cases=set()
        for item in pending:
            if item['case'] in blocked_cases:continue
            result = one(item)
            results.append(result)
            if result.get('trial_validity',{}).get('valid') is not True:
                blocked_cases.add(item['case'])
                if result.get('trial_validity',{}).get('failure_scope')=='runtime':break
                continue  # Other independent cases may proceed; this comparison may not.
            if (spec.get('instruction_exposure') == 'explicit-body' and not result.get('exposure_setup_ok')
                    or result.get('skill_exposure',{}).get('qualified') is False
                    or spec.get('terminal_backend') and not result.get('backend_setup_ok')
                    or spec.get('request_recording_parent') and not result.get('request_recording', {}).get('complete')):
                break  # Fix recording/exposure setup before spending further model calls.
    else:
        with ThreadPoolExecutor(max_workers=spec['max_workers']) as pool:
            results = list(pool.map(one, pending))
    report = {'kind': spec['purpose'], 'workflow_comparison_supported': False, 'admission': False,
              'timestamp_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
              'results': results, 'seconds': time.monotonic()-started, 'completed_trials': len(results), 'expected_trials': len(pending),
              'full_suite_expected_trials': len(plan['jobs']),
              'prior_attempt_ids': sorted(prior), 'prior_attempt_refs': plan.get('prior_attempts', []),
              'limits': ['selected leaf skill only', 'provider resolved model identity unverified', 'subscription dollar cost unavailable']}
    from evaluation_measurement import attach_measurements
    report['trial_validity']={'required':True,'valid':bool(results) and len(results)==len(pending) and all(r.get('trial_validity',{}).get('valid') is True for r in results),
        'rerun_authority':False,'scope':'Declared measured behavior exercised; product quality remains separate'}
    report['skill_effect_review_ready']=(len(results)==len(pending) and bool(results)
        and all(row.get('trial_validity',{}).get('valid') is True and row.get('skill_exposure',{}).get('continue_skill_effect_review') is True for row in results))
    attach_measurements(report, plan)
    (out / 'report.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    return report


def attach_completed_review(report, attachment, sources, *, plan=None):
    """Existing artifact lane's offline completed-review consumer, no dispatch."""
    import copy
    from evaluation_evidence import completed_artifact_decision,quality_tradeoff_decision
    result=copy.deepcopy(report)
    decision=completed_artifact_decision(result,attachment,sources,plan=plan)
    result['completed_review']=copy.deepcopy(attachment)
    result['completed_review_decision']=decision
    for row in result['results']:
        reviewed=decision.get('deliveries',{}).get(row['id'])
        if reviewed:
            row['completed_review_outcome']=reviewed
            # Keep the raw captured assessment intact. The separate completed
            # assessment cannot upgrade unknown source/provenance retroactively.
            row['completed_outcome_assessment']={**row.get('outcome_assessment',{}),
                'semantic_adequacy':{'status':'completed' if decision['ready'] else 'unusable-review',
                    'passed':reviewed['reviewed_artifact_adequate'] if decision['ready'] else None},
                'task_passed':reviewed['task_passed'],
                'comparative_preference':decision.get('quality_disposition')}
    result['current_quality_recommendation']=quality_tradeoff_decision(decision,attachment.get('quality_policy',{}),sources)
    result['deployment_authority']=False
    result['adoption_authority']=False
    if plan is not None:
        from evaluation_measurement import attach_measurements
        result['pre_review_measurements']=copy.deepcopy(report.get('measurements'))
        attach_measurements(result,plan,source_bytes=sources)
    return result


def rendered_review_input(report, out, config, *, plan=None, measurement_sources=None):
    """Join supplied human rendered evidence through the existing offline review consumer."""
    import base64
    from evaluation_measurement import digest
    from evaluation_evidence import completed_artifact_decision
    sources=dict(measurement_sources or {})
    root=Path(config['sources_root']).resolve()
    manifest=json.loads(Path(config['sources_manifest']).read_bytes())
    for name, expected in manifest.items():
        path=root/name
        if path.is_symlink() or not path.resolve().is_relative_to(root) or not path.is_file():
            raise ValueError('Manifest member missing/outside root: '+name)
        data=path.read_bytes()
        actual=hashlib.sha256(data).hexdigest()
        if actual!=expected: raise ValueError('Manifest source changed: '+name)
        sources[actual]=data
    packet=Path(config['outcome_packet']).read_bytes();packet_hash=hashlib.sha256(packet).hexdigest();sources[packet_hash]=packet
    if sum(map(len,sources.values()))>32*1024*1024:raise ValueError('Explicit source bundle exceeds32MiB; no truncation')
    attachment={'review_kind':'human-rendered-outcome','output_kind':'rendered-product',
        'outcome_packet_sha256':packet_hash,'results_sha256':digest(report['results'])}
    decision=completed_artifact_decision(report,attachment,sources,plan=plan)
    if not decision['ready']:raise ValueError('Rendered outcome rejected: '+'; '.join(decision['gaps']))
    out=Path(out);out.mkdir(parents=True,exist_ok=False)
    def save(name,value):
        with (out/name).open('xb') as stream:stream.write((json.dumps(value,indent=2)+'\n').encode())
    save('review-attachment.json',attachment)
    save('review-sources.base64.json',{h:base64.b64encode(b).decode() for h,b in sources.items()})
    save('review-input-check.json',decision)
    followup=attach_completed_review(report,attachment,sources,plan=plan)
    followup['completed_outcome_assessment']=decision
    save('report-with-outcome.json',followup)
    return {'attachment':str(out/'review-attachment.json'),'report':str(out/'report-with-outcome.json'),
        'provider_calls':0,'finished_result_acceptance':decision['finished_result_acceptance'],'adoption_authority':False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', 'run','attach-review','review-input'])
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--suite', type=Path)
    parser.add_argument('--input-report',type=Path)
    parser.add_argument('--input-plan',type=Path)
    parser.add_argument('--review-attachment',type=Path)
    parser.add_argument('--source-bundle',type=Path)
    parser.add_argument('--reviewed-output',type=Path)
    parser.add_argument('--operator-input',type=Path)
    args = parser.parse_args(argv)
    out = args.out.resolve()
    if args.action == 'prepare':
        if args.suite is None:
            parser.error('prepare requires --suite')
        result = prepare(json.loads(args.suite.read_text(encoding='utf-8')), out)
        print(json.dumps({'prepared_jobs': len(result['jobs']), 'plan': str(out / 'plan.json')}))
    elif args.action=='review-input':
        if args.operator_input is None:parser.error('review-input requires --operator-input')
        report=json.loads((args.input_report or out/'report.json').read_bytes())
        import base64
        plan=json.loads(args.input_plan.read_bytes()) if args.input_plan else None
        bundle=json.loads(args.source_bundle.read_bytes()) if args.source_bundle else {}
        measurement_sources={k:base64.b64decode(v,validate=True) for k,v in bundle.items()}
        if sum(map(len,measurement_sources.values()))>32*1024*1024:raise ValueError('Measurement source bundle exceeds32MiB')
        result=rendered_review_input(report,out,json.loads(args.operator_input.read_bytes()),plan=plan,measurement_sources=measurement_sources)
        print(json.dumps(result));return 0
    elif args.action=='attach-review':
        import base64
        if any(value is None for value in (args.review_attachment,args.source_bundle,args.reviewed_output)):
            parser.error('attach-review requires --review-attachment, --source-bundle and --reviewed-output')
        if args.reviewed_output.exists():raise FileExistsError('Reviewed successor output must be fresh; raw evidence cannot be overwritten')
        raw=json.loads(args.source_bundle.read_text(encoding='utf-8'))
        sources={key:base64.b64decode(value,validate=True) for key,value in raw.items()}
        if sum(map(len,sources.values()))>32*1024*1024:raise ValueError('Review source bundle exceeds32MiB')
        report=json.loads((args.input_report or out/'report.json').read_text(encoding='utf-8'))
        attachment=json.loads(args.review_attachment.read_text(encoding='utf-8'))
        plan=json.loads(args.input_plan.read_text(encoding='utf-8')) if args.input_plan else None
        if report.get('kind')=='native-skill-study' and plan is None:
            raise ValueError('Native completed-review projection requires its bound input plan')
        result=attach_completed_review(report,attachment,sources,plan=plan)
        with args.reviewed_output.open('x',encoding='utf-8') as stream:json.dump(result,stream,indent=2)
        print(json.dumps({'review_ready':result['completed_review_decision']['ready'],
            'quality_scope':result['completed_review_decision']['scope'],'deployment_authority':False,
            'report':str(args.reviewed_output)}))
        return 0 if result['completed_review_decision']['ready'] else 1
    else:
        result = run(json.loads((out / 'plan.json').read_text(encoding='utf-8')), out)
        print(json.dumps({'completed_trials': result['completed_trials'], 'report': str(out / 'report.json')}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
