"""Allowlisted observations from existing Hermes native lifecycle hooks.

Public receipts contain no request bodies, diagnostic text, credentials or sessions.
An explicitly configured evaluator-owned archive can retain new task requests.
Native lifecycle events alone cannot prove complete usage. The bounded
program reconciler requires matching wire/lifecycle counters, unchanged installed
sources and independently observed zero central auxiliary dispatches.
"""
import hashlib
import copy
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


def skill_body(entry):
    text=entry.decode('utf-8-sig').replace('\r\n','\n')
    body=text.split('---',2)[-1].strip() if text.startswith('---') else text.strip()
    if not body:raise ValueError('Empty target skill body')
    return body


def request_contains_skill(raw, entry):
    """Exact body in supported Responses model-visible text, not metadata.

    Opaque reasoning, tool arguments, schemas and diagnostic fields are not
    instruction exposure. Unsupported envelopes fail closed in both consumers.
    """
    if not isinstance(raw,bytes) or len(raw)>16*1024*1024:raise ValueError('Bounded request bytes required')
    body=skill_body(entry)
    def visible_string(value,depth=0):
        if depth>16:raise ValueError('Nested request exceeds exposure bound')
        if isinstance(value,str):
            result=[value]
            if value.lstrip().startswith(('{','[')):
                try:decoded=json.loads(value)
                except ValueError:decoded=None
                if decoded is not None:result+=visible_string(decoded,depth+1)
            return result
        # Decoding is confined to an already model-visible text/tool output.
        if isinstance(value,list):return [s for v in value for s in visible_string(v,depth+1)]
        if isinstance(value,dict):return [s for v in value.values() for s in visible_string(v,depth+1)]
        return []
    def content(value):
        if isinstance(value,str):return visible_string(value)
        if not isinstance(value,list):raise ValueError('Unsupported Responses content')
        result=[]
        for part in value:
            if not isinstance(part,dict):raise ValueError('Unsupported Responses text part')
            kind=part.get('type')
            if kind in ('input_text','output_text','text'):
                if not isinstance(part.get('text'),str):raise ValueError('Missing visible text')
                result+=visible_string(part['text'])
            elif kind not in ('input_image','input_file','output_image','refusal'):
                raise ValueError('Unsupported Responses content type')
        return result
    request=json.loads(raw)
    if not isinstance(request,dict) or 'input' not in request:raise ValueError('Supported Responses input required')
    texts=[]
    if request.get('instructions') is not None:
        if not isinstance(request['instructions'],str):raise ValueError('Unsupported instructions')
        texts+=visible_string(request['instructions'])
    items=request['input']
    if isinstance(items,str):texts+=visible_string(items)
    elif isinstance(items,list):
        for item in items:
            if not isinstance(item,dict):raise ValueError('Unsupported Responses item')
            kind=item.get('type')
            if kind=='message' or kind is None and 'role' in item:
                if item.get('role') not in ('system','developer','user','assistant'):raise ValueError('Unsupported message role')
                texts+=content(item.get('content'))
            elif kind=='function_call_output':texts+=content(item.get('output'))
            elif kind not in ('reasoning','function_call','item_reference','computer_call','computer_call_output'):
                raise ValueError('Unsupported Responses input type')
    else:raise ValueError('Unsupported Responses input')
    return any(body in text.replace('\r\n','\n') for text in texts)


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
        self.skill_context = None
        self.skill_context_events = []
        self._initial_skill_context_qualified = False
        self.skill_client_factory_hook_available = False
        self.discovery = None
        self.study_path_roots = None
        self.study_path_events = []
        self.measurement_guard_required = False
        self.measurement_stopped = False

    def require_study_path_scope(self, roots):
        """Case-local Windows locator boundary, not a general PII detector."""
        import ntpath,re
        values=[str(Path(p).resolve()).replace('\\','/') for p in roots]
        if not values or any(not re.match(r'^[A-Za-z]:/',p) or re.search(r'[\s`\"<>|?*]',p) for p in values):
            raise ValueError('Study locator scope requires bounded unquoted absolute Windows roots')
        self.study_path_roots=tuple(ntpath.normcase(ntpath.normpath(p)) for p in values)

    def audit_study_paths(self, text):
        if self.study_path_roots is None:return
        import re,ntpath
        normalized=text.replace('\\','/').lower()
        for match in re.finditer(r'(?<![a-z0-9])[a-z]:/',normalized):
            rest=normalized[match.start():]
            # Only the literal native documentation examples are exempt.
            parts=rest.split('/',3)
            if len(parts)==4 and parts[:3]==['c:','users','<user>'] and re.match('(?:\\.\\.\\.)?(?=[\\s`\\".,)]|$)',parts[3]):continue
            token=re.match(r'[^\s`\"<>|?*]+',rest).group(0).rstrip(',);]')
            # A terminal dot/parent component is path syntax, not prose punctuation.
            if token.endswith('.') and token.rsplit('/',1)[-1] not in ('.','..'):
                token=token[:-1].rstrip(',);]')
            if token.split('/')==['c:','users','x']:continue
            if ':' in token[2:] or '\x00' in token:
                raise RuntimeError('Unsupported Windows locator; transport blocked')
            candidate=ntpath.normcase(ntpath.normpath(token))
            owned=False
            for root in self.study_path_roots:
                try:owned=owned or ntpath.commonpath((root,candidate))==root
                except ValueError:pass
            if not owned:raise RuntimeError('Non-contained Windows locator in study request; transport blocked')
        # Keep the POSIX-only audit separate from parsed Windows user roots.
        posix_parts=normalized.split('/')
        position=0
        while position+2<len(posix_parts):
            if posix_parts[position].endswith('c:') and posix_parts[position+1]=='users':
                posix_parts[position:position+3]=[posix_parts[position][:-2]+posix_parts[position+2]]
            else:position+=1
        if re.search(r'(?<![:\w/])/(?:home|users)/[^<\s]','/'.join(posix_parts)):
            raise RuntimeError('Unqualified user-home locator in study request; transport blocked')

    def require_discovery_before_action(self,entry):
        self.require_initial_skill_context(entry,False)
        self.skill_context['mode']='discovery-before-material-action'
        self.discovery={'stopped':False,'reason':None,'latest_visible_body':False,
                        'material_dispatches':0,'material_completions':0,'events':[],
                        'interrupt_requested':False,'interrupt_errors':[]}

    def stop_discovery(self,reason):
        if self.discovery is None:return
        if not self.discovery['stopped']:
            self.discovery.update(stopped=True,reason=reason)
        self.checkpoint()

    @staticmethod
    def discovery_material(name,args):
        import re
        return name in ('write_file','patch') or name=='terminal' and not re.fullmatch(
            r'(?:pwd|ls|dir)(?: [A-Za-z0-9_. /=-]+)?',str(args.get('command','')))

    def discovery_tool_completed(self,name,parsed,args=None):
        """Fatal tool/setup uncertainty stops; observed failing tests remain data."""
        if self.discovery is None:return
        result=parsed if isinstance(parsed,dict) else {}
        fatal=bool(not result or result.get('error') or result.get('permission_denied')
                   or result.get('status') in ('denied','permission-denied','unknown-execution'))
        material=self.discovery_material(name,args or {})
        if name=='terminal':
            observed=(type(result.get('exit_code')) is int and result['exit_code']>=0
                      and isinstance(result.get('output'),str) and result.get('backend')=='direct-python-argv')
        elif name in ('write_file','patch'):
            observed=result.get('verified') is True or result.get('success') is True
            fatal=bool(fatal or result.get('success') is False or result.get('verified') is False)
        else:observed=result.get('success') is not False
        if fatal or not observed:
            self.stop_discovery('native-tool-failure-or-unknown-execution')
        elif material and not self.discovery['stopped']:
            self.discovery['material_completions']+=1
        self.checkpoint()

    def discovery_tool_boundary(self,name,args):
        """Existing pre-tool hook consumes observed request state, not model claims."""
        if self.discovery is None:return None
        state=self.discovery
        if state['stopped']:return 'Discovery qualification stopped; no further tool dispatch permitted'
        material=self.discovery_material(name,args)
        if not material:return None
        allowed=state['latest_visible_body'] is True
        state['events'].append({'tool':name,'request_ordinal':len(self.skill_context_events)-1,'allowed':allowed})
        if not allowed:
            self.stop_discovery('material-action-before-visible-target-body')
            return 'Discovery qualification ended before material action: target body not delivered in a subsequent model-visible request'
        state['material_dispatches']+=1
        self.checkpoint()
        return None

    def require_initial_skill_context(self, entry, expected_present):
        if not isinstance(entry,bytes) or type(expected_present) is not bool:raise ValueError('Explicit target bytes/presence required')
        skill_body(entry)
        self.skill_context={'entry':entry,'entry_sha256':hashlib.sha256(entry).hexdigest(),'expected_present':expected_present}

    def require_trial_measurement_guard(self):
        self.measurement_guard_required = True

    def stop_trial_measurement(self):
        self.measurement_stopped = True
        self.checkpoint()

    def guard_skill_request(self, request):
        """HTTPX request event: raises BEFORE transport on wrong initial exposure."""
        if self.measurement_stopped:raise RuntimeError('Trial measurement stopped before transport')
        if self.study_path_roots is not None:
            # Decode JSON escapes; audit all model-visible text fields including
            # instructions, tools and subsequent results, never URL/credentials.
            def texts(value):
                if isinstance(value,str):yield value
                elif isinstance(value,dict):
                    for item in value.values():yield from texts(item)
                elif isinstance(value,list):
                    for item in value:yield from texts(item)
            self.audit_study_paths('\n'.join(texts(json.loads(request.content))))
            self.study_path_events.append({'accepted':True})
        if self.skill_context is None:return
        if len(self.skill_context_events)>=self.limit:raise RuntimeError('Target exposure event bound exceeded; provider transport blocked')
        expected=self.skill_context['expected_present']
        try:present=request_contains_skill(request.content,self.skill_context['entry']);error=None
        except Exception:present=None;error='target context could not be verified'
        first=not self._initial_skill_context_qualified
        if self.discovery is not None:
            accepted=not self.discovery['stopped'] and present is not None and (not first or present is False)
            self.discovery['latest_visible_body']=bool(accepted and not first and present)
        else:accepted=(present is expected) if first or not expected else present is not None
        self.skill_context_events.append({'request_ordinal':len(self.skill_context_events),
            'target_entry_sha256':self.skill_context['entry_sha256'],'body_present':present,'initial':first,'accepted':accepted,'error':error})
        self.checkpoint()
        if not accepted:raise RuntimeError('Unqualified initial target-skill exposure; provider transport blocked')
        self._initial_skill_context_qualified = True

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
                    'target_skill_context_events':list(self.skill_context_events),
                    'trial_measurement_stopped':self.measurement_stopped,
                    'discovery_qualification':self.discovery,
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
        """Use the existing source/version-bound plain/encoded request lease."""
        from evaluation_guarded_clients import attach_guarded_requests
        lease = attach_guarded_requests(self, agent)
        self.request_send_lease = lease
        self._restores.append(lease.dispose)


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
                'target_skill_context_events':list(self.skill_context_events),
                    'trial_measurement_stopped':self.measurement_stopped,
                'discovery_qualification':copy.deepcopy(self.discovery),
                'target_skill_context_guard':{'configured':self.skill_context is not None,'client_factory_hook_available':self.skill_client_factory_hook_available,
                    'target_entry_sha256':self.skill_context['entry_sha256'] if self.skill_context else None,
                    'expected_initial_presence':self.skill_context['expected_present'] if self.skill_context else None,
                    'scope':'Pre-transport target-context prerequisite; not cognitive use or model-quality proof'},
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
    if sum(b.get('kind') == 'final-response' for b in manifest['blobs']) > 1:
        raise ValueError('Duplicate retained final response')
    paired_requests = set()
    for index, blob in enumerate(manifest['blobs']):
        kind = blob['kind']
        if kind not in ('assembled-prompt', 'task-input', 'final-request', 'encoded-request', 'final-response') or blob['file'] != f'{index:06d}-{kind}.bin':
            raise ValueError('Unsafe recording blob identity')
        path = root / blob['file']
        if path.is_symlink() or path.resolve().parent != root:
            raise ValueError('Linked recording payload')
        data = path.read_bytes()
        if len(data) != blob['bytes'] or hashlib.sha256(data).hexdigest() != blob['sha256']:
            raise ValueError('Retained recording payload changed')
        if kind == 'final-response':
            if blob['sha256'] != outcome.get('final_response_sha256'):
                raise ValueError('Retained final response differs from output check')
        if kind == 'encoded-request':
            previous = manifest['blobs'][index - 1] if index else {}
            logical = blob.get('logical_request_sha256')
            if (not isinstance(logical, str) or len(logical) != 64
                    or any(c not in '0123456789abcdef' for c in logical)
                    or previous.get('kind') != 'final-request'
                    or previous.get('logical_request_sha256') != logical
                    or logical in paired_requests):
                raise ValueError('Encoded request has no unique matching plain request')
            paired_requests.add(logical)
    # The selected send lease marks each accepted plain request with its logical
    # identity. Complete archives must retain its corresponding encoded bytes.
    # Legacy plain-only archives have no such metadata. Incomplete diagnostics
    # may end before encoding; they remain incomplete rather than losing evidence.
    if manifest.get('complete') is True:
        for index, blob in enumerate(manifest['blobs']):
            if blob['kind'] == 'final-request' and 'logical_request_sha256' in blob:
                following = manifest['blobs'][index + 1] if index + 1 < len(manifest['blobs']) else {}
                if (following.get('kind') != 'encoded-request'
                        or following.get('logical_request_sha256') != blob['logical_request_sha256']):
                    raise ValueError('Complete recording lacks adjacent encoded request pair')
    if outcome.get('oracle_sha256') != binding['oracle_sha256']:
        raise ValueError('Output checks changed')
    outcome_complete = (type(outcome.get('deterministic_invariants_passed')) is bool
        and (outcome.get('task_passed') is None or outcome.get('task_passed') is False)) if outcome.get('outcome_schema_version') == 2 else type(outcome.get('task_passed')) is bool
    checks_complete = (type(outcome.get('oracle_exit_code')) is int and outcome_complete
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
