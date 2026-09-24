"""One-use native assembly preflight. There is deliberately no inference command.

Private snapshots/traces live under .evals; public exports are an allowlist.
An assembly observation is not Desktop parity, a behavioral result, or admission.
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
import uuid

from evaluation_runtime import runtime_environment

AUTHORITY = {'admission': False, 'retirement': False, 'cache': False}
ARMS = ('baseline', 'current')
SOUL = 'recovery/current/hosts/hermes/SOUL.md'
SKILL = 'skills/conversational-communication/SKILL.md'
BLOCKERS = (
    'live-profile-and-personal-context-not-attested',
    'desktop-plugin-and-connector-initialization-not-attested',
    'native-authenticated-route-not-attested',
    'complete-per-request-provenance-not-attested',
    'model-tool-effect-containment-not-attested',
)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def encode(value):
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + '\n').encode('utf-8')


def save_new(path, value):
    """Do not overwrite evidence, even following a failed or interrupted attempt."""
    with Path(path).open('xb') as stream:
        stream.write(encode(value))
        stream.flush()
        os.fsync(stream.fileno())


def owned(root, relative):
    root = Path(root).resolve()
    name = Path(relative)
    if name.is_absolute() or name.drive or ':' in str(relative) or '..' in name.parts or not name.parts:
        raise ValueError('invalid owned path')
    target = (root / name).resolve()
    if not target.is_relative_to(root) or target == root:
        raise ValueError('path escapes owner')
    # Refuse links/junctions even when they resolve to another run-owned path.
    for part in [root / name, *(root / name).parents]:
        if part == root:
            break
        if part.is_symlink() or (part.exists() and getattr(part.stat(follow_symlinks=False), 'st_file_attributes', 0) & 0x400):
            raise ValueError('link or junction in owned path')
    return target


def verify_files(root, records):
    for relative, expected in records.items():
        target = owned(root, relative)
        if not target.is_file() or digest(target.read_bytes()) != expected:
            raise ValueError('frozen source changed or missing: ' + relative)


def create_episode(root, run_id=None):
    run_id = uuid.uuid4().hex if run_id is None else run_id
    if not isinstance(run_id, str) or re.fullmatch('[0-9a-f]{32}', run_id) is None:
        raise ValueError('invalid run id')
    root = Path(root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    episode = root / run_id
    episode.mkdir()  # exclusive ownership; no exist_ok
    (episode / 'attempts').mkdir()
    save_new(episode / 'owner.json', {'run_id': run_id, 'purpose': 'native-assembly-preflight'})
    return episode


def reserve_probe(episode, arm):
    if arm not in ARMS:
        raise ValueError('only two assembly probes are authorized; not a behavioral trial')
    record = {'arm': arm, 'attempt_id': uuid.uuid4().hex, 'state': 'reserved',
              'kind': 'assembly-only', 'model_requests': 0}
    save_new(episode / 'attempts' / (arm + '.json'), record)
    return record


def probe_environment(source, runtime):
    env = runtime_environment(source, runtime)
    # This probe forbids networking. Proxy URLs may carry credentials, including
    # in lowercase/mixed-case keys preserved by the shared runtime helper.
    env = {key: value for key, value in env.items() if not key.upper().endswith('_PROXY')}
    # Loading is permitted only from the fresh staged home. Do not suppress the
    # rules we are measuring, and do not alter the existing evaluator helper.
    for key in ('HERMES_IGNORE_RULES', 'HERMES_IGNORE_USER_CONFIG'):
        env.pop(key, None)
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    env['HERMES_TELEMETRY_ENABLED'] = 'false'
    return env


def equal_except_declared(left, right, spans):
    """Only explicitly declared unique text spans may differ (not whole SOULs)."""
    for index, span in enumerate(spans):
        marker = f'<DECLARED-{index}>'
        if marker in left or marker in right:
            raise ValueError('projection marker collision')
        for text, key in ((left, 'baseline'), (right, 'current')):
            if not span[key] or text.count(span[key]) != 1:
                raise ValueError('ambiguous or missing declared span')
        left = left.replace(span['baseline'], marker, 1)
        right = right.replace(span['current'], marker, 1)
    return left == right


def locate_sources(prompt, fragments):
    records = []
    for fragment in fragments:
        text = fragment['text']
        if not text:
            continue
        offset = 0
        while (start := prompt.find(text, offset)) >= 0:
            end = start + len(text)
            records.append({'source': fragment['source'], 'start': start, 'end': end,
                            'sha256': digest(text.encode('utf-8')),
                            'attribution': 'observed-renderer-fragment-not-causal'})
            offset = end
    return records


def git(repo, *args):
    return subprocess.run(['git', '-C', str(repo), *args], check=True, capture_output=True, timeout=60).stdout


def revision(repo, value):
    if not isinstance(value, str) or not re.fullmatch('[0-9a-f]{7,40}', value):
        raise ValueError('revision must be a literal hexadecimal commit id')
    return git(repo, 'rev-parse', '--verify', value + '^{commit}').decode().strip()


def prepare(repo, spec, native, python, root):
    repo, native, python = Path(repo).resolve(), Path(native).resolve(), Path(python).resolve()
    if spec.get('trial_cap') != 12 or len(spec.get('cases', [])) != 6:
        raise ValueError('the authorized six-case initial scope changed')
    if not python.is_file() or not (native / 'run_agent.py').is_file():
        raise ValueError('native interpreter/source unavailable')
    revisions = {arm: revision(repo, spec[arm + '_revision']) for arm in ARMS}
    candidates = {arm: {path: git(repo, 'show', revisions[arm] + ':' + path)
                         for path in (SOUL, SKILL)} for arm in ARMS}
    if candidates['baseline'] == candidates['current']:
        raise ValueError('identical instruction arms')
    episode = create_episode(root)
    sources = {}

    def stage(name, data):
        path = owned(episode, name)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as stream:
            stream.write(data)
        sources[name] = digest(data)

    for arm in ARMS:
        stage('sources/' + arm + '/SOUL.md', candidates[arm][SOUL])
        stage('sources/' + arm + '/communication.md', candidates[arm][SKILL])
    # Freeze the same tracked surrounding skill tree for both arms. It is a
    # repository snapshot, NOT a claim to reproduce every installed skill/plugin.
    archive = git(repo, 'archive', '--format=tar', revisions['current'], '--', 'skills')
    with tarfile.open(fileobj=io.BytesIO(archive)) as tree:
        for member in tree:
            if member.isdir():
                continue
            if not member.isfile():
                raise ValueError('linked/non-file skill source is unsupported')
            stage('sources/surrounding/' + member.name, tree.extractfile(member).read())
    stage('sources/surrounding/AGENTS.md', git(repo, 'show', revisions['current'] + ':AGENTS.md'))
    stage('suite.json', encode(spec))
    changes = {path: ''.join(difflib.unified_diff(
        candidates['baseline'][path].decode('utf-8').splitlines(keepends=True),
        candidates['current'][path].decode('utf-8').splitlines(keepends=True),
        fromfile='baseline/' + path, tofile='current/' + path)) for path in (SOUL, SKILL)}
    stage('candidate-diff.json', encode(changes))
    native_files = {}
    for name in git(native, 'ls-files', '-z', '--', '*.py').decode('utf-8').split('\0'):
        if name and (native / name).is_file():
            native_files[name] = digest((native / name).read_bytes())
    harness = {name: digest((Path(__file__).parent / name).read_bytes()) for name in (
        'evaluation_native_diagnostic.py', 'evaluation_native_worker.py', 'evaluation_runtime.py')}
    manifest = {'run_id': episode.name, 'schema_version': 1, 'kind': 'native-assembly-preflight',
        'authority': AUTHORITY, 'revisions': revisions, 'sources': sources,
        'native_source': str(native), 'python': str(python), 'python_sha256': digest(python.read_bytes()),
        'native_revision': git(native, 'rev-parse', 'HEAD').decode().strip(),
        'native_files': native_files, 'harness': harness, 'route': spec['route'],
        'preflight_probe_cap': 2, 'behavioral_trial_cap': 12, 'launch_permitted': False,
        'limitations': list(BLOCKERS)}
    save_new(episode / 'manifest.json', manifest)
    save_new(episode / 'manifest-binding.json', {'sha256': digest((episode / 'manifest.json').read_bytes())})
    return episode


def load_manifest(episode):
    manifest_path = episode / 'manifest.json'
    binding = json.loads((episode / 'manifest-binding.json').read_text(encoding='utf-8'))
    if digest(manifest_path.read_bytes()) != binding['sha256']:
        raise ValueError('manifest changed')
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    if manifest['run_id'] != episode.name or manifest['launch_permitted'] is not False:
        raise ValueError('episode identity or launch authority changed')
    verify_files(episode, manifest['sources'])
    verify_files(Path(manifest['native_source']), manifest['native_files'])
    verify_files(Path(__file__).parent, manifest['harness'])
    if digest(Path(manifest['python']).read_bytes()) != manifest['python_sha256']:
        raise ValueError('native interpreter changed')
    return manifest


def public_receipt(private, bindings):
    observations = [{key: observation[key] for key in
        ('arm', 'assembled', 'prompt_sha256', 'tools_sha256', 'source_spans', 'error_type',
         'boundary_reason', 'process_reaped', 'runtime_removed')
        if key in observation} for observation in private['observations']]
    return {'kind': 'native-instruction-preflight-v1', 'schema_version': 1,
        'run_id': private['run_id'], 'authority': dict(AUTHORITY),
        'status': 'blocked-before-inference', 'launch_permitted': False,
        'model_requests': private['model_requests'], 'behavioral_trials': 0,
        'cleanup_ok': private['cleanup_ok'], 'blockers': sorted(set(private['blockers'])),
        'observations': observations, 'artifacts': bindings}


def validate_preflight(report):
    errors = []
    try:
        if (report['kind'] != 'native-instruction-preflight-v1' or report['schema_version'] != 1
                or report['authority'] != AUTHORITY or report['launch_permitted'] is not False
                or report['status'] != 'blocked-before-inference' or report['cleanup_ok'] is not True
                or type(report['model_requests']) is not int or report['model_requests'] != 0
                or type(report['behavioral_trials']) is not int or report['behavioral_trials'] != 0
                or not re.fullmatch('[0-9a-f]{32}', report['run_id'])
                or not report['blockers'] or not report['artifacts']):
            errors.append('invalid preflight scope or lifecycle')
        if any(not isinstance(value, str) or not re.fullmatch('[0-9a-f]{64}', value)
               for value in report['artifacts'].values()):
            errors.append('invalid artifact binding')
        observations = report['observations']
        if not isinstance(observations, list) or not 1 <= len(observations) <= len(ARMS):
            errors.append('missing or invalid observations')
        else:
            seen = set()
            for observation in observations:
                arm = observation['arm']
                if arm not in ARMS or arm in seen:
                    errors.append('invalid or duplicate observation arm')
                seen.add(arm)
                if any(type(observation[key]) is not bool for key in
                       ('assembled', 'process_reaped', 'runtime_removed')):
                    errors.append('invalid observation lifecycle types')
                for key in ('prompt_sha256', 'tools_sha256'):
                    if key in observation and (not isinstance(observation[key], str)
                            or re.fullmatch('[0-9a-f]{64}', observation[key]) is None):
                        errors.append('invalid observation digest')
                if 'source_spans' in observation and (type(observation['source_spans']) is not int
                        or observation['source_spans'] < 0):
                    errors.append('invalid source span count')
                for key in ('error_type', 'boundary_reason'):
                    if key in observation and not isinstance(observation[key], str):
                        errors.append('invalid observation error type')
            cleanup = all(item['process_reaped'] is True and item['runtime_removed'] is True
                          for item in observations)
            if report['cleanup_ok'] is not cleanup:
                errors.append('cleanup contradicts observations')
    except (KeyError, TypeError, ValueError, AttributeError):
        errors.append('malformed preflight')
    return {'valid': not errors, 'errors': errors, 'admission_eligible': False,
            'launch_permitted': False, 'decision': 'diagnostic-only' if not errors else 'inconclusive'}


def run_child(command, job, env, fixture, folder, timeout=90):
    """Parent-owned process receipt, including kill/reap on timeout or interrupt."""
    import psutil
    proc = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, encoding='utf-8', env=env, cwd=fixture)
    state = {'pid': proc.pid, 'timed_out': False, 'reaped': False, 'descendants_seen': []}
    stdout = stderr = ''
    try:
        tracked = psutil.Process(proc.pid)
        state['create_time'] = tracked.create_time()
        save_new(folder / 'process-start.json', state)
        try:
            stdout, stderr = proc.communicate(json.dumps(job), timeout=timeout)
        except subprocess.TimeoutExpired:
            state['timed_out'] = True
    finally:
        # Only this owned process and its observed descendants are eligible.
        descendants = []
        if proc.poll() is None:
            try:
                descendants = psutil.Process(proc.pid).children(recursive=True)
            except psutil.NoSuchProcess:
                pass
            state['descendants_seen'] = [child.pid for child in descendants]
            for child in reversed(descendants):
                try:
                    child.kill()
                except psutil.NoSuchProcess:
                    pass
            proc.kill()
            stdout, stderr = proc.communicate(timeout=10)
        _, alive = psutil.wait_procs(descendants, timeout=10)
        state.update(returncode=proc.returncode, reaped=proc.poll() is not None and not alive,
                     stdout=stdout, stderr=stderr,
                     descendant_scope='assembly worker forbids spawn; not a model-tool sandbox')
        save_new(folder / 'process.json', state)
    return state


def probe_one(episode, manifest, spec, arm):
    attempt = reserve_probe(episode, arm)
    folder = episode / attempt['attempt_id']
    folder.mkdir()
    runtime = folder / 'runtime'
    observation = {'arm': arm, 'assembled': False, 'process_reaped': True, 'worker_started': False}
    try:
        env = probe_environment(dict(os.environ), runtime)
        home = Path(env['HERMES_HOME'])
        fixture = runtime / 'fixture'
        fixture.mkdir()
        (fixture / '.git').mkdir()  # native context discovery stops here
        shutil.copy2(episode / 'sources' / arm / 'SOUL.md', home / 'SOUL.md')
        shutil.copytree(episode / 'sources/surrounding/skills', home / 'skills')
        shutil.copy2(episode / 'sources' / arm / 'communication.md',
                     home / 'skills/conversational-communication/SKILL.md')
        shutil.copy2(episode / 'sources/surrounding/AGENTS.md', fixture / 'AGENTS.md')
        for name, text in spec['cases'][0]['files'].items():
            target = owned(fixture, name)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding='utf-8')
        # Explicit probe config, not the live profile. Missing live layers remain
        # blockers; the safe-mode omission of plugins is never called equivalence.
        config = {'model': {'default': spec['route']['model'], 'provider': spec['route']['provider']},
                  'skills': {'external_dirs': []}, 'terminal': {'backend': 'local'},
                  'agent': {'max_turns': spec['max_iterations']},
                  'compression': {'enabled': False}, 'context': {'engine': 'native'}}
        (home / 'config.yaml').write_text(json.dumps(config), encoding='utf-8')
        env['TERMINAL_CWD'] = str(fixture)
        job = {'mode': 'assemble-only', 'root': str(folder), 'home': str(home),
               'fixture': str(fixture), 'native_source': manifest['native_source'],
               'route': manifest['route'], 'id': attempt['attempt_id']}
        save_new(folder / 'job.json', job)
        observation['worker_started'] = True
        observation['process_reaped'] = False
        process = run_child([manifest['python'], '-B', str(Path(__file__).with_name('evaluation_native_worker.py'))],
                            job, env, fixture, folder)
        observation.update(worker_exit=process['returncode'], process_reaped=process['reaped'])
        worker_path = folder / 'worker.json'
        if worker_path.is_file():
            worker = json.loads(worker_path.read_text(encoding='utf-8'))
            observation.update({key: worker[key] for key in
                ('assembled', 'prompt_sha256', 'tools_sha256', 'source_spans', 'error_type', 'boundary_reason') if key in worker})
            if (worker['model_requests'] != 0 or worker['launch_permitted'] is not False
                    or worker['guard_installed'] is not True or worker['conversation_started'] is not False):
                raise ValueError('invalid assembly-only worker attestation')
        else:
            observation['error_type'] = 'AssemblyTimeout' if process['timed_out'] else 'MissingWorkerReceipt'
    except Exception as exc:
        observation.update(assembled=False, error_type=type(exc).__name__)
    finally:
        try:
            if runtime.exists():
                shutil.rmtree(runtime)
            observation['runtime_removed'] = not runtime.exists()
        except OSError:
            observation['runtime_removed'] = False
        save_new(folder / 'result.json', observation)
    return observation


def probe(episode):
    """Run only the bounded no-inference worker; any incompleteness stays blocked."""
    episode = Path(episode).resolve()
    manifest = load_manifest(episode)
    save_new(episode / 'probe-started.json', {'run_id': episode.name, 'model_requests': 0})
    spec = json.loads((episode / 'suite.json').read_text(encoding='utf-8'))
    observations = []
    for arm in ARMS:
        observation = probe_one(episode, manifest, spec, arm)
        observations.append(observation)
        if not observation['assembled'] or not observation['runtime_removed'] or not observation['process_reaped']:
            break  # do not spend another probe on a known-invalid native path
    cleanup = all(item['runtime_removed'] and item['process_reaped'] for item in observations)
    blockers = list(BLOCKERS)
    if len(observations) != len(ARMS) or not all(item['assembled'] for item in observations):
        blockers.append('native-assembly-incomplete')
    try:
        load_manifest(episode)
    except (ValueError, OSError):
        blockers.append('postflight-artifact-drift')
    private = {'run_id': episode.name, 'observations': observations, 'cleanup_ok': cleanup,
               'blockers': blockers, 'model_requests': 0}
    save_new(episode / 'private-report.json', private)
    bindings = {path.relative_to(episode).as_posix(): digest(path.read_bytes())
                for path in episode.rglob('*.json') if path.is_file()}
    report = public_receipt(private, bindings)
    save_new(episode / 'public-report.json', report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='action', required=True)
    prep = commands.add_parser('prepare')
    for flag in ('repo', 'suite', 'native-source', 'python', 'private-root'):
        prep.add_argument('--' + flag, type=Path, required=True)
    check = commands.add_parser('probe')
    check.add_argument('--episode', type=Path, required=True)
    args = parser.parse_args(argv)
    if args.action == 'prepare':
        episode = prepare(args.repo, json.loads(args.suite.read_text(encoding='utf-8')),
                          args.native_source, args.python, args.private_root)
        print(json.dumps({'episode': str(episode), 'launch_permitted': False}))
    else:
        report = probe(args.episode)
        print(json.dumps({'run_id': report['run_id'], 'validation': validate_preflight(report),
                          'blockers': report['blockers'], 'observations': report['observations']}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
