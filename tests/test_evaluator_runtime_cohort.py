"""Caller, selected-runtime and compressed recording controls; no native launch."""
import gzip
import hashlib
import importlib.metadata
import inspect
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import httpx
import evaluation_runtime as runtime
import evaluation_hermes_worker as worker
import evaluation_artifact_pilot as pilot
import evaluation_guarded_clients
from evaluation_send_lease import AttemptStopped, Binding, SendLease, decoded_final_body
from evaluation_usage import NativeUsageObserver, bind_recorded_output

sha = lambda raw: hashlib.sha256(raw).hexdigest()


class RuntimeContract(unittest.TestCase):
    def test_actual_caller_imports_and_keyword_signature(self):
        from evaluation_runtime import catalog_exposure, require_paid_intervention, require_receiver_dispatch
        self.assertEqual(catalog_exposure([]), [])
        self.assertTrue(callable(require_paid_intervention) and callable(require_receiver_dispatch))
        inspect.signature(runtime.run_native_skill_study).bind('task', ROOT, 1, [],
            agent='hermes', intervention_clearance=None, request_recording=None)
        self.assertIs(pilot.native_hermes_runtime, runtime.native_hermes_runtime)

    def test_missing_clearance_stops_before_allocation_or_process(self):
        with patch.object(runtime.tempfile, 'mkdtemp', side_effect=AssertionError('Unexpected allocation')), \
             patch.object(runtime.subprocess, 'Popen', side_effect=AssertionError('Unexpected launch')):
            with self.assertRaisesRegex(ValueError, 'requires source-bound pretrial'):
                runtime.run_native_skill_study('task', ROOT, 1, [], agent='hermes')

    def test_supported_coding_context_is_off_and_no_install_stays_required(self):
        with tempfile.TemporaryDirectory(prefix='agent-sync-cohort-config-') as tmp:
            with patch.dict(os.environ, {'HERMES_DISABLE_LAZY_INSTALLS': '1'}):
                worker.prepare_study_config(tmp, evidence_only=True)
            value = json.loads((Path(tmp) / 'config.yaml').read_bytes())
            self.assertEqual(value['agent'], {'environment_probe': False, 'coding_context': 'off'})
            worker.verify_no_install_config(value)
        with patch.dict(os.environ, {'HERMES_DISABLE_LAZY_INSTALLS': '0'}):
            with self.assertRaisesRegex(ValueError, 'before native imports'):
                worker.prepare_study_config('unused', evidence_only=True)

    def pm_fixture(self, temporary, missing=False):
        base = Path(temporary)
        source = base / 'hermes-agent'
        for folder in ['pm', 'hermes_cli', '.venv/Scripts', 'selected']:
            (source / folder).mkdir(parents=True)
        (base / 'bin').mkdir()
        exe = base / 'bin/hermes.exe'; exe.write_bytes(b'')
        for name in ['run_agent.py', 'hermes_cli/auth_codex.py', '.venv/Scripts/python.exe']:
            (source / name).write_bytes(b'')
        (source / 'hermes_constants.py').write_text('def get_default_hermes_root(): return None\n')
        (source / 'pm/environments.py').write_text(
            'from hermes_constants import get_default_hermes_root\n'
            'def project_python(root): return root / "selected/python.exe"\n')
        if not missing: (source / 'selected/python.exe').write_bytes(b'')
        return source, exe

    def test_pm_selection_takes_precedence_over_existing_old_venv(self):
        with tempfile.TemporaryDirectory(prefix='agent-sync-cohort-pm-') as tmp, patch.dict(sys.modules):
            sys.modules.pop('hermes_constants', None)
            source, exe = self.pm_fixture(tmp)
            python, found = runtime.native_hermes_runtime(str(exe))
            self.assertEqual((python, found), (source / 'selected/python.exe', source))

    def test_missing_pm_selection_does_not_fall_back_to_old_venv(self):
        with tempfile.TemporaryDirectory(prefix='agent-sync-cohort-pm-') as tmp, patch.dict(sys.modules):
            sys.modules.pop('hermes_constants', None)
            _, exe = self.pm_fixture(tmp, missing=True)
            with self.assertRaisesRegex(ValueError, 'Selected native Hermes interpreter unavailable'):
                runtime.native_hermes_runtime(str(exe))

    def test_gzip_and_unknown_codec_boundaries(self):
        raw = b'{"input":[]}'
        request = httpx.Request('POST', 'https://qualification.invalid/mock',
                               content=gzip.compress(raw), headers={'content-encoding': 'gzip'})
        self.assertEqual(decoded_final_body(request), raw)
        request.headers['content-encoding'] = 'unknown'
        with self.assertRaisesRegex(AttemptStopped, 'Unsupported body encoding'):
            decoded_final_body(request)


class SyntheticSdk:
    max_retries = 0
    def __init__(self, wire): self._client = wire


class SyntheticAgent:
    session_id = 'synthetic-session'
    _current_api_request_id = 'synthetic-request'
    def __init__(self, wire): self.sdk = SyntheticSdk(wire)
    def _create_request_openai_client(self): return self.sdk


class CompressedRecording(unittest.TestCase):
    def exercise(self, *, altered=False, unsupported=False):
        from compression import zstd
        with tempfile.TemporaryDirectory(prefix='agent-sync-cohort-recording-') as tmp:
            archive = Path(tmp).resolve() / 'archive'
            observer = NativeUsageObserver()
            binding = dict(run_id='synthetic-run', case_id='synthetic-case', arm='B',
                plan_sha256=sha(b'plan'), task_sha256=sha(b'task'), oracle_sha256=sha(b'oracle'))
            observer.enable_recording(archive, binding)
            observer.record_prompts('synthetic prompt', 'task')
            physical = []
            def sink(request):
                physical.append(request.content)
                return httpx.Response(200, content=b'ok')
            def encode(request):
                raw = b'{"changed":true}' if altered else request.content
                request._content = zstd.compress(raw)
                request.headers['content-encoding'] = 'unknown' if unsupported else 'zstd'
                request.headers['content-length'] = str(len(request.content))
            wire = httpx.Client(transport=httpx.MockTransport(sink), event_hooks={'request': [encode]})
            agent = SyntheticAgent(wire)
            origin = inspect.getsourcefile(agent._create_request_openai_client)
            lease_binding = Binding(origin, sha(Path(origin).read_bytes()),
                type(agent.sdk).__module__ + '.' + type(agent.sdk).__qualname__, None, None,
                importlib.metadata.version('httpx'), agent.session_id,
                'https://qualification.invalid/mock', synthetic_only=True)
            def retain(kind, raw, key):
                observer._retain('final-request' if kind == 'model-request' else 'encoded-request', raw,
                    logical_request_sha256=sha(key[1].encode()))
                if kind == 'encoded-request': observer.http_events.append({'phase': 'request'})
            lease = SendLease(agent, lease_binding,
                guard_body=lambda raw, key: observer.guard_skill_request(SimpleNamespace(content=raw)),
                retain_body=retain).attach()
            try:
                acquired = agent._create_request_openai_client()
                if altered or unsupported:
                    with self.assertRaises(AttemptStopped):
                        acquired._client.post('https://qualification.invalid/mock', content=b'{"input":[]}')
                    self.assertEqual(physical, [])
                    return
                acquired._client.post('https://qualification.invalid/mock', content=b'{"input":[]}')
                self.assertEqual(len(physical), 1)
                response = b'synthetic response'; observer._retain('final-response', response)
                summary = observer.finish_recording()
                outcome = dict(oracle_sha256=binding['oracle_sha256'], oracle_exit_code=0,
                    outcome_schema_version=2, deterministic_invariants_passed=True, task_passed=None,
                    oracle_result_sha256=sha(b'checks'), final_tree_sha256=sha(b'tree'),
                    final_response_sha256=sha(response))
                self.assertTrue(bind_recorded_output(archive, summary, binding, outcome)['complete'])
                manifest = json.loads((archive / 'manifest.json').read_bytes())
                self.assertEqual([b['kind'] for b in manifest['blobs']][-3:],
                                 ['final-request', 'encoded-request', 'final-response'])
                with self.assertRaisesRegex(AttemptStopped, 'Repeated physical request blocked'):
                    acquired._client.post('https://qualification.invalid/mock', content=b'{"input":[]}')
                self.assertEqual(len(physical), 1)
            finally:
                lease.dispose()
                wire.close()

    def test_actual_zstd_lease_recording_and_binder_compose(self): self.exercise()
    def test_changed_decoded_body_is_rejected_before_transport(self): self.exercise(altered=True)
    def test_unknown_encoded_body_is_rejected_before_transport(self): self.exercise(unsupported=True)


if __name__ == '__main__': unittest.main()
