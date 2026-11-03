"""Compose existing UX observer with the reviewed per-logical send lease.

One replacement for the former watcher, never a second nested client lease.
No native import, client construction, transport replacement or client closing.
"""
import hashlib
import inspect
from pathlib import Path
import time

from evaluation_send_lease import Binding,SendLease,AttemptStopped


def attach_guarded_requests(observer, agent):
    root=observer.native_source_root
    expected=(observer.native_sources_before or {}).get('agent/client_lifecycle.py')
    method=getattr(agent,'_create_request_openai_client',None)
    actual=inspect.getsourcefile(method) if callable(method) else None
    if (root is None or not expected or not actual
            or Path(actual).resolve()!=(Path(root)/'agent/client_lifecycle.py').resolve()):
        raise AttemptStopped('Missing installed-source acquisition binding')
    binding=Binding(actual,expected,'openai.OpenAI','openai','2.54.0','0.28.1',
        agent.session_id,'https://chatgpt.com/backend-api/codex/responses')
    pending={}

    def guard(raw,key):
        from types import SimpleNamespace
        observer.guard_skill_request(SimpleNamespace(content=raw))

    def retain(kind,raw,key):
        if observer.recording is None:
            raise AttemptStopped('Qualified private recording required')
        before=(len(observer.recording['blobs']),len(observer.recording['errors']))
        observer._retain('final-request' if kind=='model-request' else 'encoded-request',raw,
                         logical_request_sha256=hashlib.sha256(key[1].encode()).hexdigest())
        if (len(observer.recording['blobs']),len(observer.recording['errors']))!=(before[0]+1,before[1]):
            raise AttemptStopped('Private recording did not retain accepted body')
        if kind=='encoded-request':
            if len(observer.http_events)>=observer.limit:
                observer.http_dropped+=1
                raise AttemptStopped('HTTP observation bound exceeded')
            ordinal=1+sum(e['phase']=='request' for e in observer.http_events)
            if key in pending:raise AttemptStopped('Concurrent request identity')
            pending[key]={'attempt':ordinal,'started':time.monotonic(),
                          'body_sha256':hashlib.sha256(raw).hexdigest()}
            observer.http_events.append({'phase':'request','attempt':ordinal,'status':None,'seconds':None})
            observer.checkpoint()

    class ObservedLease(SendLease):
        def _stop(self, reason):
            super()._stop(reason)
            if observer.measurement_guard_required:
                observer.stop_trial_measurement()

        def __init__(self,*args,**kwargs):
            self.response_hooks=[]
            super().__init__(*args,**kwargs)

        def _instrument(self,wire):
            super()._instrument(wire)
            observer.clients_hooked+=1
            # Base lease rejects every acquired SDK whose retries are not exactly zero.
            observer.sdk_retry_limits.append(0)
            def response(value):
                try:
                    key=self._identity()
                    entry=pending.pop(key)
                    if hashlib.sha256(value.request.content).hexdigest()!=entry['body_sha256']:
                        raise AttemptStopped('HTTP response request identity differs')
                    if len(observer.http_events)>=observer.limit:
                        observer.http_dropped+=1
                        raise AttemptStopped('HTTP response observation bound exceeded')
                    observer.http_events.append({'phase':'response','attempt':entry['attempt'],
                        'status':value.status_code,'seconds':time.monotonic()-entry['started']})
                    observer.checkpoint()
                    if observer.measurement_guard_required:
                        if value.status_code >= 400:
                            self._stop('http-error')
                        from httpx import SyncByteStream
                        original_stream = value.stream
                        lease = self
                        class MeasurementStream(SyncByteStream):
                            def __init__(self): self.closed = False
                            def __iter__(self):
                                try: yield from original_stream
                                except Exception as exc:
                                    lease._stop('stream-' + type(exc).__name__)
                                    raise
                            def close(self):
                                if not self.closed:
                                    self.closed = True
                                    try:
                                        original_stream.close()
                                    except BaseException as exc:
                                        lease._stop('stream-close-' + type(exc).__name__)
                                        raise
                        value.stream = MeasurementStream()
                except BaseException:
                    observer.observation_errors+=1
                    raise
            wire.event_hooks['response'].append(response)
            self.response_hooks.append((wire,response))

        def dispose(self):
            # Native owner must have settled/closed first; this never closes it.
            super().dispose()
            for wire,callback in self.response_hooks:
                if callback not in wire.event_hooks.get('response',[]):
                    raise AttemptStopped('Response observation ownership lost')
                wire.event_hooks['response'].remove(callback)
            self.response_hooks.clear()

    lease=ObservedLease(agent,binding,guard_body=guard,retain_body=retain).attach()
    observer.skill_client_factory_hook_available=True
    return lease
