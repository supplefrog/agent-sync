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


def is_native(spec):
    return spec.get('purpose') in ('native-skill-study', 'native-runtime-smoke')


def native_prompt(spec, case, frozen):
    prompt = case['prompt']
    if spec.get('instruction_exposure', 'native-discovery') == 'explicit-body' and frozen:
        prompt += '\n\n<optional-instruction-exposure>\n' + frozen['prompt_text'] + '\n</optional-instruction-exposure>'
    return prompt


def validate(spec):
    if spec.get('purpose') not in ('runtime-smoke', 'injected-instruction-study', 'native-skill-study', 'native-runtime-smoke'):
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
        if spec.get('prepared_runtime_parent') is not None and spec['agent'] != 'hermes':
            raise ValueError('Explicit prepared runtime parent is supported only by the Hermes adapter')
    if spec['purpose'] in ('runtime-smoke', 'native-runtime-smoke') and len(spec['arms']) * len(spec['cases']) != 1:
        raise ValueError('A runtime smoke is limited to one trial, not a workflow comparison')
    if not 1 <= len(spec['arms']) * len(spec['cases']) <= 12:
        raise ValueError('A pilot is limited to twelve model trials')
    if not 1 <= spec['max_workers'] <= 3 or not 1 <= spec['max_iterations'] <= 64:
        raise ValueError('Invalid worker/iteration ceiling')
    if not 1 <= spec['timeout'] <= 600:
        raise ValueError('Invalid time ceiling')
    if (not isinstance(spec['quota_remaining'], (int, float)) or not 0 < spec['quota_remaining'] <= 100):
        raise ValueError('An observed nonzero subscription quota is required')
    if len({a['id'] for a in spec['arms']}) != len(spec['arms']):
        raise ValueError('Duplicate arm')
    if len({c['id'] for c in spec['cases']}) != len(spec['cases']):
        raise ValueError('Duplicate case')


def prepare(spec, out):
    validate(spec)
    if (out / 'plan.json').exists():
        raise ValueError('Plan already exists; use run without preparing again')
    out.mkdir(parents=True, exist_ok=True)
    workroot = Path(spec['workspace_root']).resolve()
    workroot.mkdir(parents=True, exist_ok=True)
    frames = {a['id']: freeze_candidate(Path(a['instructions'])) if a.get('instructions') else None for a in spec['arms']}
    source_trees = {}
    common_catalog = {}
    if is_native(spec):
        source_trees = {case['id']: tree(Path(case['fixture'])) for case in spec['cases']}
        common_catalog = {str(Path(source)): freeze_candidate(Path(source)) for source in spec.get('catalog', [])}
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
                        if sha(origin) != digest:
                            raise ValueError('Catalog source changed before staging')
                        target = destination / relative
                        target.parent.mkdir(parents=True, exist_ok=True)
                        target.write_bytes(origin.read_bytes())
                    staged_skill = destination / 'SKILL.md'
                    if freeze_candidate(staged_skill)['package_sha256'] != frozen_catalog['package_sha256']:
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
                if skill_path not in expected_catalog or freeze_candidate(Path(skill_path))['package_sha256'] != frozen_hash:
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
    import os
    spec = plan['spec']
    validate(spec)
    if sha(spec['oracle']) != plan['oracle_sha256']:
        raise ValueError('Frozen oracle changed')
    if sha(__file__) != plan['controller_sha256'] or sha(Path(__file__).with_name('evaluation_artifact_worker.py')) != plan['worker_sha256']:
        raise ValueError('Frozen execution code changed')
    if sha(Path(__file__).with_name('evaluation_measurement.py')) != plan.get('measurement_sha256'):
        raise ValueError('Frozen measurement projection changed')
    if sha(Path(__file__).with_name('evaluation_usage.py')) != plan.get('usage_observer_sha256'):
        raise ValueError('Frozen usage observer changed')
    validate_jobs(plan)
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
                oracle = subprocess.run([sys.executable, spec['oracle'], str(fixture), item['case']],
                    text=True, capture_output=True, timeout=90)
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
                                    and result['oracle_valid_success'])
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
        worker = run_native_skill_study(item['prompt'], fixture, spec['timeout'], item['catalog'],
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
        if spec.get('instruction_exposure') == 'explicit-body':
            trace = worker.get('native_usage', {}).get('lifecycle', {}).get('exposure_events', [])
            expected_body = next(arm for arm in spec['arms'] if arm['id'] == item['arm']).get('instructions') is not None
            result['exposure_setup_ok'] = bool(trace and trace[0].get('optional_body_present') is expected_body
                and trace[0].get('terminal_contract_present') is True and (trace[0].get('tool_count') or 0)>0)
            if not result['exposure_setup_ok']:
                worker['failure_attribution'] = {'category':'evaluator-setup',
                    'evidence_sha256': hashlib.sha256(json.dumps(trace,sort_keys=True).encode()).hexdigest()}
        (path / 'worker.json').write_text(json.dumps(worker, indent=2)+'\n', encoding='utf-8')
        result['native'] = worker
        try:
            if sha(spec['oracle']) != plan['oracle_sha256']:
                raise ValueError('Frozen oracle changed during execution')
            before = time.monotonic()
            oracle = subprocess.run([sys.executable, spec['oracle'], str(fixture), item['case']], text=True, capture_output=True, timeout=90)
            result['oracle_seconds'] = time.monotonic() - before
            (path / 'oracle-output.txt').write_text(oracle.stdout + oracle.stderr, encoding='utf-8')
            checked = json.loads(oracle.stdout)
            result['oracle'] = checked
            result['oracle_exit_code'] = oracle.returncode
            result['ok'] = bool(worker['ok'] and oracle.returncode == 0 and type(checked.get('passed')) is int and checked['passed'] > 0 and type(checked.get('failed')) is int and checked['failed'] == 0 and checked.get('failures') == [])
        except Exception as exc:
            result['error'] = type(exc).__name__ + ': ' + str(exc)
        result['seconds_including_verification'] = time.monotonic() - started
        result['final_tree'] = tree(fixture)
        if recording:
            from evaluation_measurement import digest
            from evaluation_usage import bind_recorded_output
            try:
                result['request_recording'] = bind_recorded_output(recording['directory'],
                    worker.get('request_recording', {}), recording['binding'],
                    {'oracle_sha256': plan['oracle_sha256'], 'oracle_exit_code': result.get('oracle_exit_code'),
                     'oracle_result_sha256': digest(result.get('oracle')), 'task_passed': result['ok'],
                     'final_tree_sha256': digest(result['final_tree']),
                     'final_response_sha256': hashlib.sha256((worker.get('final_response') or '').encode()).hexdigest()})
                if not result['request_recording']['complete']:
                    result['ok'] = False
            except Exception as exc:
                result['request_recording'] = {'complete': False, 'error_type': type(exc).__name__,
                                               'execution_authenticated': False}
                result['ok'] = False
        (path / 'result.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
        return result
    started = time.monotonic()
    if spec.get('instruction_exposure') == 'explicit-body' or spec.get('request_recording_parent'):
        results = []
        for item in pending:
            result = one(item)
            results.append(result)
            if (spec.get('instruction_exposure') == 'explicit-body' and not result.get('exposure_setup_ok')
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
    attach_measurements(report, plan)
    (out / 'report.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    return report


def attach_completed_review(report, attachment, sources, *, plan=None):
    """Existing artifact lane's offline completed-review consumer, no dispatch."""
    import copy
    from evaluation_evidence import completed_artifact_decision,quality_tradeoff_decision
    result=copy.deepcopy(report)
    decision=completed_artifact_decision(result,attachment,sources)
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


def rendered_review_input(report, out, config):
    """Join supplied human rendered evidence through the existing offline review consumer."""
    import base64
    from evaluation_measurement import digest
    from evaluation_evidence import completed_artifact_decision
    sources={}
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
    decision=completed_artifact_decision(report,attachment,sources)
    if not decision['ready']:raise ValueError('Rendered outcome rejected: '+'; '.join(decision['gaps']))
    out=Path(out);out.mkdir(parents=True,exist_ok=False)
    def save(name,value):
        with (out/name).open('xb') as stream:stream.write((json.dumps(value,indent=2)+'\n').encode())
    save('review-attachment.json',attachment)
    save('review-sources.base64.json',{h:base64.b64encode(b).decode() for h,b in sources.items()})
    save('review-input-check.json',decision)
    followup=attach_completed_review(report,attachment,sources)
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
        result=rendered_review_input(report,out,json.loads(args.operator_input.read_bytes()))
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
