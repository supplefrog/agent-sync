"""Evaluation-only lease: no native imports, transport replacement or client close.

Private factory acquisition is pinned explicitly. HTTPX hooks/send are per-client.
Trusted controller supplies existing privacy/pixel guard and private body retention.
"""
from dataclasses import dataclass
import hashlib
import gzip
import importlib.metadata
import inspect
import io
from pathlib import Path
import threading

import httpx


class AttemptStopped(RuntimeError):
    pass


MAX_BODY_BYTES = 16 * 1024 * 1024


def _complete_zstd_result(decoded, *, eof, unused_data):
    if (not isinstance(decoded, bytes) or len(decoded) > MAX_BODY_BYTES
            or eof is not True or unused_data != b''):
        raise AttemptStopped('Incomplete, trailing or oversized zstd body')
    return decoded


def _decode_zstd(raw):
    # Native compression.zstd.compress produces one ordinary frame, no dictionary.
    if not raw.startswith(b'\x28\xb5\x2f\xfd'):
        raise AttemptStopped('Unsupported zstd frame')
    try:
        from compression import zstd
    except ImportError as exc:
        raise AttemptStopped('Standard-library zstd unavailable') from exc
    try:
        decoder = zstd.ZstdDecompressor(
            options={zstd.DecompressionParameter.window_log_max: 24})
        decoded = decoder.decompress(raw, max_length=MAX_BODY_BYTES + 1)
        return _complete_zstd_result(decoded, eof=decoder.eof, unused_data=decoder.unused_data)
    except Exception as exc:
        raise AttemptStopped('Invalid or unqualified zstd body') from exc


def decoded_final_body(request):
    """Bounded identity/gzip/stdlib zstd; unsupported codecs fail closed."""
    raw = request.content
    if not isinstance(raw, bytes) or len(raw) > MAX_BODY_BYTES:
        raise AttemptStopped('Encoded body outside bound')
    encoding = request.headers.get('content-encoding', '').strip().lower()
    if encoding in ('', 'identity'):
        return raw
    if encoding == 'zstd':
        return _decode_zstd(raw)
    if encoding != 'gzip':
        raise AttemptStopped('Unsupported body encoding')
    with gzip.GzipFile(fileobj=io.BytesIO(raw), mode='rb') as stream:
        decoded = stream.read(MAX_BODY_BYTES + 1)
    if len(decoded) > MAX_BODY_BYTES:
        raise AttemptStopped('Decoded body outside bound')
    return decoded


@dataclass(frozen=True)
class Binding:
    factory_path: str
    factory_sha256: str
    sdk_type: str
    sdk_distribution: str | None
    sdk_version: str | None
    httpx_version: str
    session_id: str
    response_url: str
    synthetic_only: bool = False


class SendLease:
    """One physical send per native logical request; failures end this attempt.

    Construct after the ordinary bounded AIAgent, before its first conversation.
    Dispose only after normal native owner cleanup/settlement. Never closes SDK.
    """
    def __init__(self, agent, binding, *, guard_body, retain_body):
        self.agent, self.binding = agent, binding
        self.guard_body, self.retain_body = guard_body, retain_body
        self.events, self.claimed, self.clients = [], set(), []
        self.stopped, self.active = False, 0
        self.lock = threading.RLock()
        self.original = getattr(agent, '_create_request_openai_client', None)
        self.wrapper = None
        if (not binding.synthetic_only and
                (binding.sdk_distribution != 'openai' or not binding.sdk_version
                 or not binding.sdk_type.startswith('openai.'))):
            raise AttemptStopped('Production SDK version/type binding required')
        source = inspect.getsourcefile(self.original) if callable(self.original) else None
        if (not source or Path(source).resolve() != Path(binding.factory_path).resolve()
                or hashlib.sha256(Path(source).read_bytes()).hexdigest() != binding.factory_sha256
                or agent.session_id != binding.session_id or not binding.session_id
                or importlib.metadata.version('httpx') != binding.httpx_version):
            raise AttemptStopped('Unqualified source/session/HTTPX binding')
        if binding.sdk_distribution:
            if importlib.metadata.version(binding.sdk_distribution) != binding.sdk_version:
                raise AttemptStopped('Unqualified SDK version')

    def _identity(self):
        request_id = getattr(self.agent, '_current_api_request_id', None)
        if (self.agent.session_id != self.binding.session_id
                or not isinstance(request_id, str) or not request_id):
            raise AttemptStopped('Missing native request identity')
        return self.binding.session_id, request_id

    def _stop(self, reason):
        self.stopped = True
        self.events.append({'kind': 'stopped', 'reason': reason})

    def attach(self):
        if self.wrapper is not None:
            raise AttemptStopped('Lease already attached')
        def acquire(*args, **kwargs):
            with self.lock:
                if self.stopped:
                    raise AttemptStopped('Attempt already ended')
                try:
                    self._identity()
                except AttemptStopped:
                    self._stop('missing-request-identity')
                    raise
            client = self.original(*args, **kwargs)
            wire = getattr(client, '_client', None)
            sdk_type = type(client).__module__ + '.' + type(client).__qualname__
            if (sdk_type != self.binding.sdk_type or getattr(client, 'max_retries', None) != 0
                    or type(wire) is not httpx.Client or not isinstance(wire.event_hooks, dict)):
                self._stop('unsupported-client-shape')
                raise AttemptStopped('Unqualified SDK/HTTPX client')
            for state in self.clients:
                if state['wire'] is wire:
                    self._membership(state)
                    return client
            self._instrument(wire)
            return client
        self.wrapper = acquire
        self.agent._create_request_openai_client = acquire
        return self

    def _membership(self, state):
        wire = state['wire']
        hooks = wire.event_hooks.get('request', [])
        if (wire.send is not state['send'] or not hooks
                or hooks[0] is not state['prepare'] or hooks[-1] is not state['record']):
            self._stop('lease-removed')
            raise AttemptStopped('Observation lease removed')

    def _instrument(self, wire):
        keys = {}
        def prepare(request):
            with self.lock:
                key = self._identity()
                if self.stopped or key in self.claimed:
                    self._stop('repeat-or-ended-before-transport')
                    raise AttemptStopped('Repeated physical request blocked')
                if str(request.url) != self.binding.response_url or request.method != 'POST':
                    self._stop('route-mismatch')
                    raise AttemptStopped('Unqualified route')
                self.claimed.add(key)
                if (request.headers.get('content-encoding', '').strip().lower() not in ('', 'identity')
                        or len(request.content) > MAX_BODY_BYTES):
                    raise AttemptStopped('Initial model body must be bounded identity encoding')
                # Guard before native compression hooks; failures are never advisory.
                self.guard_body(request.content, key)
                # Exact approved bytes avoid relying on a stateful guard being idempotent.
                keys[id(request)] = (key, hashlib.sha256(request.content).hexdigest())
                self.retain_body('model-request', request.content, key)
                self.events.append({'kind': 'claimed-before-transport', 'request_id': key[1]})
        def record(request):
            self._membership(state)
            key = self._identity()
            approved = keys.get(id(request))
            if approved is None or approved[0] != key:
                self._stop('request-identity-changed')
                raise AttemptStopped('Request changed during preparation')
            if request.method != 'POST' or str(request.url) != self.binding.response_url:
                raise AttemptStopped('Final route/method changed')
            decoded = decoded_final_body(request)
            if hashlib.sha256(decoded).hexdigest() != approved[1]:
                raise AttemptStopped('Final decoded body differs from guarded model body')
            self.retain_body('encoded-request', request.content, key)
            self.events.append({'kind': 'encoded-before-transport', 'request_id': key[1],
                                'body_sha256': hashlib.sha256(request.content).hexdigest()})
        original_send = wire.send
        state = {'wire': wire, 'prepare': prepare, 'record': record, 'original_send': original_send}
        def send(request, *args, **kwargs):
            with self.lock:
                self._membership(state)
                if self.stopped:
                    raise AttemptStopped('Attempt ended before send')
                self.active += 1
            try:
                response = original_send(request, *args, **kwargs)
                self.events.append({'kind': 'response-headers', 'status': response.status_code})
                if response.status_code >= 400:
                    self._stop('http-error')
                return response
            except BaseException as exc:
                # Type only: exception strings/headers may contain credentials.
                self._stop('send-' + type(exc).__name__)
                raise
            finally:
                with self.lock:
                    self.active -= 1
        state['send'] = send
        wire.event_hooks['request'].insert(0, prepare)
        wire.event_hooks['request'].append(record)
        wire.send = send
        self.clients.append(state)

    def dispose(self):
        """Release only this observation lease; owner retains client/close ownership."""
        with self.lock:
            if self.active:
                raise AttemptStopped('Send still owned; keep lease until settlement')
            if self.agent._create_request_openai_client is not self.wrapper:
                raise AttemptStopped('Factory ownership changed; do not overwrite')
            for state in self.clients:
                self._membership(state)
            self.agent._create_request_openai_client = self.original
            for state in self.clients:
                wire = state['wire']
                wire.send = state['original_send']
                wire.event_hooks['request'].remove(state['prepare'])
                wire.event_hooks['request'].remove(state['record'])
            self.wrapper = None
