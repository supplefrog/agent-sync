"""Allowlisted observations from existing Hermes native lifecycle hooks.

Public receipts contain no request bodies, diagnostic text, credentials or sessions.
An explicitly configured evaluator-owned archive can retain new task requests.
Native lifecycle events alone cannot prove complete usage. The bounded
program reconciler requires matching wire/lifecycle counters, unchanged installed
sources and independently observed zero central auxiliary dispatches.
"""
import hashlib
import time
import json
import os
import threading
from pathlib import Path
from evaluation_measurement import TOKEN_KEYS, counter, seconds

HOOKS = ('pre_api_request', 'post_api_request', 'api_request_error',
         'pre_auxiliary_call', 'post_auxiliary_call')
BASE_NATIVE_SOURCES = ('agent/client_lifecycle.py', 'agent/codex_runtime.py', 'agent/auxiliary_client.py',
    'agent/auxiliary_hooks.py', 'agent/relay_llm.py', 'agent/turn_api_request.py',
    'agent/turn_response_intake.py', 'agent/api_request_hooks.py')
DEADLINE_NATIVE_SOURCES = ('agent/interrupt_control.py', 'agent/conversation_loop.py')


class NativeUsageObserver:
    def __init__(self, limit=512):
        self.events = []
        self.dropped = 0
        self.limit = limit
        self.http_events = []
        self.http_dropped = 0
        self.clients_hooked = 0
        self.clients_unsupported = 0
        self.observation_errors = 0
        self.sdk_retry_limits = []
        self._restores = []
        self.auxiliary_dispatches = None
        self.exposure_events = []
        self.body_probes = []
        self.native_sources_before = None
        self.native_source_root = None
        self.recording = None
        self._recording_root = None
        self._recording_secrets = ()
        self._checkpoint_lock = threading.RLock()

    def checkpoint(self):
        """Durable allowlisted partial counters; never a completion certificate."""
        if self.recording is None or self._recording_root is None:
            return
        try:
            with self._checkpoint_lock:
                data = {'version': 1, 'binding': dict(self.recording['binding']),
                    'complete': False, 'whole_system_complete': False,
                    'execution_authenticated': False,
                    'events': list(self.events), 'http_events': list(self.http_events),
                    'dropped_events': self.dropped, 'http_dropped': self.http_dropped,
                    'observation_errors': self.observation_errors,
                    'exposure_events': list(self.exposure_events),
                    'blobs': list(self.recording['blobs']),
                    'errors': list(self.recording['errors']),
                    'native_sources_before': self.native_sources_before,
                    'sdk_retry_limits': list(self.sdk_retry_limits),
                    'auxiliary_dispatches': self.auxiliary_dispatches,
                    'cleanup': 'unknown until final receipt',
                    'inflight_usage': None}
                raw = json.dumps(data, sort_keys=True).encode('utf-8')
                if any(secret in raw for secret in self._recording_secrets):
                    raise ValueError('unsafe partial counters')
                temp = self._recording_root / 'lifecycle-checkpoint.new'
                target = self._recording_root / 'lifecycle-checkpoint.json'
                if temp.is_symlink() or target.is_symlink():
                    raise ValueError('unexpected checkpoint link')
                with temp.open('wb') as stream:
                    stream.write(raw)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temp, target)
        except Exception:
            self.observation_errors += 1

    def enable_recording(self, directory, binding, *, forbidden=()):
        """Opt-in private retention; never infer a location or change permissions."""
        root = Path(directory)
        if not root.is_absolute() or root.parent.resolve() != root.parent or not root.parent.is_dir():
            raise ValueError('Recording needs an existing canonical evaluator-owned parent')
        required = ('run_id', 'case_id', 'arm', 'plan_sha256', 'task_sha256', 'oracle_sha256')
        if not isinstance(binding, dict) or any(not binding.get(k) for k in required):
            raise ValueError('Missing recording run/check binding')
        for key in required[3:]:
            if len(binding[key]) != 64 or any(c not in '0123456789abcdef' for c in binding[key]):
                raise ValueError('Invalid recording source identity')
        root.mkdir()  # Exclusive: no implicit resume, overwrite, fallback or ACL change.
        self._recording_root = root
        self._recording_secrets = tuple(value.encode() for value in forbidden if value)
        self.recording = {'version': 1, 'binding': {k: binding[k] for k in required}, 'blobs': [], 'errors': []}
        self.checkpoint()

    def _retain(self, kind, data, **metadata):
        if self.recording is None:
            return
        try:
            if not isinstance(data, bytes) or any(secret in data for secret in self._recording_secrets):
                raise ValueError('unsafe recording payload')
            if kind == 'final-request':
                body = json.loads(data)
                def credential_field(value):
                    if isinstance(value, dict):
                        return any(str(k).lower() in ('authorization', 'api_key', 'access_token', 'refresh_token')
                                   or credential_field(v) for k, v in value.items())
                    return isinstance(value, list) and any(credential_field(v) for v in value)
                if credential_field(body):
                    raise ValueError('credential field in recording payload')
            digest = hashlib.sha256(data).hexdigest()
            name = f'{len(self.recording["blobs"]):06d}-{kind}.bin'
            with (self._recording_root / name).open('xb') as stream:
                stream.write(data)
            self.recording['blobs'].append({'file': name, 'kind': kind, 'sha256': digest,
                                            'bytes': len(data), **metadata})
            self.checkpoint()
        except Exception as exc:
            self.recording['errors'].append('recording-' + type(exc).__name__)

    def record_prompts(self, assembled, task):
        if self.recording is not None:
            self._retain('assembled-prompt', assembled.encode('utf-8'))
            self._retain('task-input', task.encode('utf-8'))

    def finish_recording(self):
        """Write a private manifest once; export only identities, never paths/text."""
        if self.recording is None:
            return None
        manifest = self.recording
        kinds = [b['kind'] for b in manifest['blobs']]
        requests = kinds.count('final-request')
        task = next((b for b in manifest['blobs'] if b['kind'] == 'task-input'), {})
        complete = (not manifest['errors'] and kinds.count('assembled-prompt') == kinds.count('task-input') == 1
                    and task.get('sha256') == manifest['binding']['task_sha256'] and requests > 0
                    and requests == sum(e['phase'] == 'request' for e in self.http_events)
                    and not self.http_dropped and not self.observation_errors and not self.clients_unsupported)
        manifest.update(complete=complete, execution_authenticated=False)
        self.checkpoint()
        raw = json.dumps(manifest, sort_keys=True, ensure_ascii=False).encode('utf-8')
        try:
            with (self._recording_root / 'manifest.json').open('xb') as stream:
                stream.write(raw)
            identity = hashlib.sha256(raw).hexdigest()
        except Exception as exc:
            manifest['errors'].append('manifest-' + type(exc).__name__)
            complete, identity = False, None
        return {'manifest_sha256': identity, 'run_binding_sha256': hashlib.sha256(json.dumps(
                    manifest['binding'], sort_keys=True).encode()).hexdigest(),
                'complete': complete, 'final_request_count': requests, 'errors': list(manifest['errors']),
                'execution_authenticated': False}

    def source_hashes(self):
        if self.native_source_root is None: return None
        names = BASE_NATIVE_SOURCES + DEADLINE_NATIVE_SOURCES
        return {name: hashlib.sha256((self.native_source_root/name).read_bytes()).hexdigest() for name in names}

    def watch_auxiliary_dispatches(self):
        """Count installed central aux dispatch entries, including no-route bypass.

        No arguments, clients, credentials or responses are read. Nonzero aux
        dispatches conservatively retain unverified usage; zero is observed.
        """
        from agent import auxiliary_client as module
        self.native_source_root = Path(module.__file__).resolve().parents[1]
        self.native_sources_before = self.source_hashes()
        names = ('_relay_sync_completion', '_relay_async_completion', '_relay_sync_stream')
        if not all(callable(getattr(module, name, None)) for name in names):
            raise RuntimeError('Installed auxiliary dispatch seams unavailable')
        self.auxiliary_dispatches = {name: 0 for name in names}
        for name in names:
            original = getattr(module, name)
            if name == '_relay_async_completion':
                async def wrapped(*args, _name=name, _original=original, **kwargs):
                    self.auxiliary_dispatches[_name] += 1
                    return await _original(*args, **kwargs)
            else:
                def wrapped(*args, _name=name, _original=original, **kwargs):
                    self.auxiliary_dispatches[_name] += 1
                    return _original(*args, **kwargs)
            setattr(module, name, wrapped)
            self._restores.append(lambda name=name, original=original: setattr(module, name, original))

    def watch_request_clients(self, agent):
        """Attach public HTTPX events at the installed task-local client seam.

        No client is replaced and no URL, headers or response content is read.
        Exact request-body retention is confined to the explicit private archive.
        Events count local dispatches, not provider-internal work.
        """
        original = getattr(agent, '_create_request_openai_client', None)
        if not callable(original):
            self.clients_unsupported += 1
            return
        seen, registrations, pending = set(), [], {}
        def record(phase, value):
            try:
                if len(self.http_events) >= self.limit:
                    self.http_dropped += 1
                    return
                request = value if phase == 'request' else value.request
                if phase == 'request':
                    ident = 1 + sum(e['phase'] == 'request' for e in self.http_events)
                    pending[id(request)] = (ident, time.monotonic())
                    self.http_events.append({'phase': phase, 'attempt': ident, 'status': None, 'seconds': None})
                    if self.recording is not None:
                        self._retain('final-request', request.content, physical_attempt=ident)
                else:
                    ident, started = pending.pop(id(request), (None, None))
                    self.http_events.append({'phase': phase, 'attempt': ident,
                        'status': counter(value.status_code),
                        'seconds': time.monotonic() - started if started is not None else None})
                self.checkpoint()
            except Exception:
                self.observation_errors += 1
        def watched(*args, **kwargs):
            client = original(*args, **kwargs)
            underlying = getattr(client, '_client', None)
            if id(underlying) in seen:
                return client
            seen.add(id(underlying))
            from httpx import Client
            hooks = getattr(underlying, 'event_hooks', None)
            if not isinstance(underlying, Client) or not isinstance(hooks, dict):
                self.clients_unsupported += 1
                return client
            self.sdk_retry_limits.append(counter(getattr(client, 'max_retries', None)))
            for phase in ('request', 'response'):
                callback = lambda value, phase=phase: record(phase, value)
                hooks[phase].append(callback)
                registrations.append((hooks[phase], callback))
            self.clients_hooked += 1
            return client
        agent._create_request_openai_client = watched
        def restore():
            agent._create_request_openai_client = original
            for hooks, callback in registrations:
                if callback in hooks:
                    hooks.remove(callback)
        self._restores.append(restore)

    def close(self):
        errors = []
        for restore in reversed(self._restores):
            try:
                restore()
            except Exception as exc:
                errors.append('usage-client-hook-cleanup-' + type(exc).__name__)
        self._restores.clear()
        return errors

    def callback(self, name):
        def capture(**payload):
            if len(self.events) >= self.limit:
                self.dropped += 1
                return
            request_id = payload.get('api_request_id')
            usage = payload.get('usage')
            usage = usage if isinstance(usage, dict) else None
            if name == 'pre_api_request':
                request = payload.get('request', {})
                body = request.get('body', {}) if isinstance(request, dict) else {}
                tools = body.get('tools', []) if isinstance(body, dict) else []
                def texts(value):
                    if isinstance(value, str): return [value]
                    if isinstance(value, dict): return [text for item in value.values() for text in texts(item)]
                    if isinstance(value, list): return [text for item in value for text in texts(item)]
                    return []
                material = '\n'.join(texts(payload.get('request_messages')) + texts(payload.get('system_prompt')))
                schemas = json.dumps(tools, sort_keys=True, default=str)
                self.exposure_events.append({'request_sha256': hashlib.sha256(material.encode()).hexdigest(),
                    'tool_schema_sha256': hashlib.sha256(schemas.encode()).hexdigest(),
                    'tool_count': len(tools) if isinstance(tools,list) else 0,
                    'optional_body_present': any(probe in material for probe in self.body_probes),
                    'terminal_contract_present': 'Fixture terminal boundary:' in schemas})
            self.events.append({'hook': name,
                'request_sha256': hashlib.sha256(request_id.encode()).hexdigest() if isinstance(request_id, str) and request_id else None,
                'retry_index': counter(payload.get('retry_count')),
                'seconds': seconds(payload.get('api_duration')),
                'failed': name == 'api_request_error' or bool(payload.get('error_type')),
                'streaming': payload.get('streaming') is True,
                'usage_present': usage is not None,
                'tokens': {key: counter(usage.get(key)) if usage else None for key in TOKEN_KEYS}})
            self.checkpoint()
        return capture

    def snapshot(self):
        return {'source': 'native-Hermes-lifecycle-hooks', 'events': list(self.events),
                'dropped_events': self.dropped, 'provider_physical_attempts_verified': False,
                'whole_system_complete': False,
                'auxiliary_dispatches': dict(self.auxiliary_dispatches) if self.auxiliary_dispatches is not None else None,
                'exposure_events': list(self.exposure_events),
                'native_sources_before': self.native_sources_before,
                'native_sources_after': self.source_hashes(),
                'native_http': {'source': 'native-request-client-HTTPX-events',
                    'clients_hooked': self.clients_hooked, 'unsupported_clients': self.clients_unsupported,
                    'sdk_retry_limits': list(self.sdk_retry_limits), 'events': list(self.http_events),
                    'dropped_events': self.http_dropped, 'observation_errors': self.observation_errors,
                    'scope': 'main-agent local HTTP dispatches; response hook precedes stream consumption; auxiliary clients and provider-internal work excluded'},
                'limits': ['Native loop and auxiliary hook events; internal SDK/stream retry completeness unverified.',
                           'Failed or streamed auxiliary calls can omit usage; missing tokens remain unknown.']}


def bind_recorded_output(directory, summary, binding, outcome):
    """Check retained bytes, then link this run's existing independent outcome.

    Only an explicit evaluator-owned directory is read. No receipt-selected
    source path or oracle is executed. Public return values contain no payloads.
    """
    root = Path(directory)
    if root.resolve() != root or root.is_symlink():
        raise ValueError('Noncanonical recording directory')
    raw = (root / 'manifest.json').read_bytes()
    if hashlib.sha256(raw).hexdigest() != summary.get('manifest_sha256'):
        raise ValueError('Recording manifest changed or missing')
    manifest = json.loads(raw)
    if manifest['binding'] != binding or summary.get('run_binding_sha256') != hashlib.sha256(
            json.dumps(binding, sort_keys=True).encode()).hexdigest():
        raise ValueError('Recording belongs to a different run or output check')
    for index, blob in enumerate(manifest['blobs']):
        kind = blob['kind']
        if kind not in ('assembled-prompt', 'task-input', 'final-request') or blob['file'] != f'{index:06d}-{kind}.bin':
            raise ValueError('Unsafe recording blob identity')
        path = root / blob['file']
        if path.is_symlink() or path.resolve().parent != root:
            raise ValueError('Linked recording payload')
        data = path.read_bytes()
        if len(data) != blob['bytes'] or hashlib.sha256(data).hexdigest() != blob['sha256']:
            raise ValueError('Retained recording payload changed')
    if outcome.get('oracle_sha256') != binding['oracle_sha256']:
        raise ValueError('Output checks changed')
    checks_complete = (type(outcome.get('oracle_exit_code')) is int and type(outcome.get('task_passed')) is bool
        and all(isinstance(outcome.get(k), str) and len(outcome[k]) == 64
                and all(c in '0123456789abcdef' for c in outcome[k])
                for k in ('oracle_result_sha256', 'final_tree_sha256', 'final_response_sha256')))
    joined = {'manifest_sha256': summary['manifest_sha256'], 'binding': binding,
              'outcome': outcome, 'execution_authenticated': False}
    encoded = json.dumps(joined, sort_keys=True, ensure_ascii=False).encode('utf-8')
    with (root / 'output-checks.json').open('xb') as stream:
        stream.write(encoded)
    return {**summary, 'output_checks_sha256': hashlib.sha256(encoded).hexdigest(),
            'complete': summary.get('complete') is True and manifest.get('complete') is True and checks_complete,
            'execution_authenticated': False}


def reconcile_program_usage(usage):
    """Strict, bounded native program scope: complete responses, no aux dispatch.

    No provider billing or coordinator-study claim. Any retry/aux/error/drop or
    missing source/usage observation prevents completeness; never estimate it.
    """
    ledger = usage.get('lifecycle', {})
    http = ledger.get('native_http', {})
    events = ledger.get('events', [])
    posts = [e for e in events if e.get('hook') == 'post_api_request']
    calls = counter(usage.get('api_calls'))
    aux = ledger.get('auxiliary_dispatches')
    requests = [e for e in http.get('events', []) if e.get('phase') == 'request']
    responses = [e for e in http.get('events', []) if e.get('phase') == 'response']
    keys = ('input_tokens','output_tokens','cache_read_tokens','cache_write_tokens','reasoning_tokens','prompt_tokens','total_tokens')
    totals_match = bool(posts) and all(all(counter(e.get('tokens', {}).get(k)) is not None for e in posts)
        and sum(e['tokens'][k] for e in posts) == counter(usage.get('tokens', {}).get(k)) for k in keys)
    source_before = ledger.get('native_sources_before')
    checks = {'completed_usage_reconciled': totals_match and calls == len(posts),
        'outer_requests_reconciled': calls is not None and calls > 0 and sum(e.get('hook') == 'pre_api_request' for e in events) == calls,
        'http_dispatches_reconciled': calls is not None and len(requests) == len(responses) == calls
            and {e.get('attempt') for e in requests} == set(range(1,calls+1))
            and {e.get('attempt') for e in responses} == set(range(1,calls+1)) and all(e.get('status') == 200 for e in responses),
        'sdk_retries_disabled': bool(http.get('sdk_retry_limits')) and all(v == 0 for v in http['sdk_retry_limits']),
        'auxiliary_dispatches_observed_zero': isinstance(aux,dict) and len(aux)==3 and all(type(v) is int and v==0 for v in aux.values()),
        'no_error_or_auxiliary_hook_events': not any(e.get('hook') in ('api_request_error','pre_auxiliary_call','post_auxiliary_call') for e in events),
        'observer_intact': ledger.get('dropped_events') == 0 and http.get('dropped_events') == 0
            and http.get('observation_errors') == 0 and http.get('unsupported_clients') == 0 and (counter(http.get('clients_hooked')) or 0)>0,
        'native_sources_unchanged': isinstance(source_before,dict)
            and set(source_before) in (set(BASE_NATIVE_SOURCES), set(BASE_NATIVE_SOURCES + DEADLINE_NATIVE_SOURCES))
            and all(isinstance(value,str) and len(value)==64 and all(c in '0123456789abcdef' for c in value)
                    for value in source_before.values())
            and source_before == ledger.get('native_sources_after')}
    return {'verified': all(checks.values()), 'checks': checks,
            'scope': 'isolated-Hermes-program-task-model-calls',
            'physical_attempt_count': len(requests),
            'limits': 'Native main and instrumented central auxiliary paths only; program must obey no-network/no-delegation task boundary. No study-coordinator, provider-internal compute, or billing claim.'}
