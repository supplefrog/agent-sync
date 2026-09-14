"""Bounded artifact pilot front end for eval.py; not an admission evaluator.

Reuse candidate freezing, runtime isolation, and the routed native worker.
The suite supplies its independently executed oracle. No model judge, promotion,
retries, fallback, configuration mutation, or new workflow scheduler lives here.
"""
from __future__ import annotations
import argparse
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


def validate(spec):
    if spec.get('purpose') not in ('runtime-smoke', 'injected-instruction-study'):
        raise ValueError('Explicit purpose required: runtime-smoke or injected-instruction-study. '
                         'This leaf/inline runner cannot evaluate natural discovery or architecture workflows.')
    if spec['purpose'] == 'runtime-smoke' and len(spec['arms']) * len(spec['cases']) != 1:
        raise ValueError('A runtime smoke is limited to one trial, not a workflow comparison')
    if not 1 <= len(spec['arms']) * len(spec['cases']) <= 12:
        raise ValueError('A pilot is limited to twelve model trials')
    if not 1 <= spec['max_workers'] <= 3 or not 1 <= spec['max_iterations'] <= 64:
        raise ValueError('Invalid worker/iteration ceiling')
    if not 1 <= spec['timeout'] <= 600:
        raise ValueError('Invalid time ceiling')
    if not isinstance(spec['quota_remaining'], (int, float)) or not 0 < spec['quota_remaining'] <= 100:
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
    frames = {a['id']: freeze_candidate(Path(a['instructions'])) for a in spec['arms']}
    jobs = []
    for index, case in enumerate(spec['cases']):
        # Rotate ordering without changing any case/prompt across arms.
        arms = spec['arms'][index % len(spec['arms']):] + spec['arms'][:index % len(spec['arms'])]
        for arm in arms:
            ident = uuid.uuid4().hex
            fixture = workroot / ident
            shutil.copytree(case['fixture'], fixture)
            instructions = frames[arm['id']]['prompt_text']
            prompt = case['prompt'] + '\n\nProject: ' + str(fixture) + '\nWork only in this project. Do not delegate, use network services, or modify parent directories.'
            jobs.append({'id': ident, 'arm': arm['id'], 'case': case['id'],
                         'fixture': str(fixture), 'initial_tree': tree(fixture),
                         'instructions': instructions, 'prompt': prompt})
    plan = {'spec': spec, 'jobs': jobs, 'candidate_snapshots': frames,
            'oracle_sha256': sha(spec['oracle']), 'controller_sha256': sha(__file__),
            'worker_sha256': sha(Path(__file__).with_name('evaluation_artifact_worker.py')),
            'kind': spec['purpose'], 'workflow_comparison_supported': False}
    (out / 'plan.json').write_text(json.dumps(plan, indent=2) + '\n', encoding='utf-8')
    return plan


def validate_jobs(plan):
    """Check the entire launch set before runtime discovery or any trial starts.

    This is consistency validation, not a signature over a hostile controller's
    plan and not evidence that an experiment can distinguish workflows.
    """
    spec = plan['spec']
    cases = {case['id']: case for case in spec['cases']}
    expected = {(arm['id'], case) for arm in spec['arms'] for case in cases}
    jobs = plan['jobs']
    if len(jobs) != len(expected):
        raise ValueError('Prepared trial count differs from the declared suite')
    seen_pairs, seen_ids = set(), set()
    workroot = Path(spec['workspace_root']).resolve()
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
        if item['prompt'] != prompt:
            raise ValueError('Prepared prompt differs from the declared case')
        if item['instructions'] != plan['candidate_snapshots'][item['arm']]['prompt_text']:
            raise ValueError('Prepared instructions differ from the frozen candidate')
        if tree(fixture) != item['initial_tree']:
            raise ValueError('Prepared fixture contents changed')


def run(plan, out):
    import os
    spec = plan['spec']
    validate(spec)
    if sha(spec['oracle']) != plan['oracle_sha256']:
        raise ValueError('Frozen oracle changed')
    if sha(__file__) != plan['controller_sha256'] or sha(Path(__file__).with_name('evaluation_artifact_worker.py')) != plan['worker_sha256']:
        raise ValueError('Frozen execution code changed')
    validate_jobs(plan)
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
              'results': results, 'seconds': time.monotonic() - started,
              'completed_trials': len(results), 'expected_trials': len(plan['jobs']), 'admission': False}
    (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', 'run'])
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--suite', type=Path)
    args = parser.parse_args(argv)
    out = args.out.resolve()
    if args.action == 'prepare':
        if args.suite is None:
            parser.error('prepare requires --suite')
        result = prepare(json.loads(args.suite.read_text(encoding='utf-8')), out)
        print(json.dumps({'prepared_jobs': len(result['jobs']), 'plan': str(out / 'plan.json')}))
    else:
        result = run(json.loads((out / 'plan.json').read_text(encoding='utf-8')), out)
        print(json.dumps({'completed_trials': result['completed_trials'], 'report': str(out / 'report.json')}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
