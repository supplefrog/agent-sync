"""Recording mechanics through real HTTPX hooks, with no network or models."""
from fixture_workspace import configure
configure()
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import httpx
from evaluation_usage import NativeUsageObserver, bind_recorded_output
import evaluation_artifact_pilot as pilot
import evaluation_runtime as runtime
import evaluation_hermes_worker as worker_module
import evaluation_measurement as measurement


class RequestRecordingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.task = 'Explain the public fixture: café.\n'
        self.binding = {'run_id': 'new-run', 'case_id': 'case', 'arm': 'base',
            'task_sha256': hashlib.sha256(self.task.encode()).hexdigest(),
            'plan_sha256': '1'*64, 'oracle_sha256': '2'*64}

    def recorder(self, name='private-archive', **kwargs):
        observer = NativeUsageObserver(**kwargs)
        observer.enable_recording(self.root / name, self.binding, forbidden=('FAKE_CREDENTIAL',))
        observer.record_prompts('ASSEMBLED\nSystem café', self.task)
        self.addCleanup(observer.close)
        return observer

    def send(self, observer, bodies):
        received = []
        def transport(request):
            received.append(request.content)
            return httpx.Response(200, json={'ok': True})
        client = httpx.Client(transport=httpx.MockTransport(transport))
        self.addCleanup(client.close)
        wrapper = SimpleNamespace(_client=client, max_retries=0)
        agent = SimpleNamespace(_create_request_openai_client=lambda: wrapper)
        observer.watch_request_clients(agent)
        agent._create_request_openai_client()
        for body in bodies:
            client.post('https://example.invalid', json=body,
                        headers={'Authorization': 'Bearer FAKE_CREDENTIAL'})
        return received

    def outcome(self):
        return {'oracle_sha256': '2'*64, 'oracle_exit_code': 0,
                'oracle_result_sha256': '3'*64, 'final_tree_sha256': '4'*64,
                'final_response_sha256': '5'*64, 'task_passed': True}

    def test_exact_assembly_task_and_final_bytes_include_late_additions_every_request(self):
        o = self.recorder()
        o.callback('pre_api_request')(request_messages=[{'role': 'user', 'content': self.task}])
        bodies = [{'input': [{'role': 'user', 'content': self.task}], 'instructions': 'LATE system',
                   'tools': [{'name': 'LATE tool'}], 'late_field': {'present': True}},
                  {'input': [{'role': 'tool', 'content': 'later tool result'}], 'tools': []}]
        wire = self.send(o, bodies)
        summary = o.finish_recording()
        self.assertTrue(summary['complete'], summary)
        root = self.root / 'private-archive'
        manifest = json.loads((root / 'manifest.json').read_bytes())
        self.assertEqual((root / manifest['blobs'][0]['file']).read_bytes(), 'ASSEMBLED\nSystem café'.encode())
        self.assertEqual((root / manifest['blobs'][1]['file']).read_bytes(), self.task.encode())
        requests = [b for b in manifest['blobs'] if b['kind'] == 'final-request']
        self.assertEqual([b['physical_attempt'] for b in requests], [1, 2])
        self.assertEqual([(root / b['file']).read_bytes() for b in requests], wire)
        self.assertNotIn('FAKE_CREDENTIAL', ''.join(p.read_text() for p in root.iterdir()))
        self.assertNotIn('LATE', json.dumps(o.snapshot()) + json.dumps(summary))
        joined = bind_recorded_output(root, summary, self.binding, self.outcome())
        self.assertTrue(joined['complete']); self.assertFalse(joined['execution_authenticated'])

    def test_credential_body_is_refused_without_redacting_or_exporting_it(self):
        for index, body in enumerate(({'input': 'FAKE_CREDENTIAL'}, {'api_key': 'another-secret'})):
            o = self.recorder('archive'+str(index)); self.send(o, [body])
            result = o.finish_recording()
            self.assertFalse(result['complete']); self.assertTrue(result['errors'])
            for path in (self.root / ('archive'+str(index))).iterdir():
                self.assertNotIn('FAKE_CREDENTIAL', path.read_text())
                self.assertNotIn('another-secret', path.read_text())

    def test_corrected_terminal_bound_reaches_final_http_body_unchanged(self):
        native={'name':'terminal','parameters':{'type':'object','properties':{
            'timeout':{'type':'integer','description':'Default 180; foreground max 600','minimum':1}}}}
        schema=worker_module.bounded_terminal_schema(native,150)
        agent=SimpleNamespace(tools=[{'type':'function','function':schema}])
        worker_module.advertise_study_terminal(agent)
        function=agent.tools[0]['function']
        # Responses serializes function schema at the tool's top level.
        body={'input':self.task,'tools':[{'type':'function',**function}]}
        observer=self.recorder()
        sent=self.send(observer,[body])
        self.assertTrue(observer.finish_recording()['complete'])
        observed=json.loads(sent[0])['tools'][0]['parameters']['properties']['timeout']
        self.assertEqual(observed['default'],150)
        self.assertEqual(observed['maximum'],150)
        self.assertEqual(observed['minimum'],1)
        self.assertIn('default 150; maximum 150',observed['description'])
        self.assertNotIn('180',observed['description'])
        self.assertNotIn('background',observed['description'])
        self.assertEqual(native['parameters']['properties']['timeout']['description'],'Default 180; foreground max 600')

    def test_dropped_or_unsupported_capture_cannot_claim_completeness(self):
        o = self.recorder(limit=1)
        self.send(o, [{'input': 'one'}, {'input': 'two'}])
        self.assertFalse(o.finish_recording()['complete'])
        o = self.recorder('unsupported'); o.watch_request_clients(SimpleNamespace())
        self.assertFalse(o.finish_recording()['complete'])

    def test_empty_and_wrong_task_recordings_are_incomplete(self):
        o = self.recorder(); self.assertFalse(o.finish_recording()['complete'])
        o = self.recorder('wrong-task'); o.recording['binding']['task_sha256'] = '0'*64
        self.send(o, [{'input': self.task}]); self.assertFalse(o.finish_recording()['complete'])

    def test_write_failure_is_a_gap_and_archive_cannot_be_reused(self):
        o = self.recorder()
        with mock.patch.object(Path, 'open', side_effect=PermissionError('PRIVATE_PATH')):
            self.send(o, [{'input': 'body'}])
        self.assertFalse(o.finish_recording()['complete'])
        with self.assertRaises(FileExistsError): self.recorder()
        self.assertNotIn('PRIVATE_PATH', json.dumps(o.recording))

    def test_output_binding_rejects_changed_blobs_replayed_runs_and_changed_checks(self):
        o = self.recorder(); self.send(o, [{'input': self.task}]); summary = o.finish_recording()
        root = self.root / 'private-archive'
        wrong = {**self.binding, 'run_id': 'other-run'}
        with self.assertRaises(ValueError): bind_recorded_output(root, summary, wrong, self.outcome())
        with self.assertRaises(ValueError): bind_recorded_output(root, summary, self.binding, {**self.outcome(), 'oracle_sha256': '9'*64})
        (root / '000002-final-request.bin').write_bytes(b'changed')
        with self.assertRaises(ValueError): bind_recorded_output(root, summary, self.binding, self.outcome())

    def test_path_escape_and_exclusive_output_check_write(self):
        o = self.recorder(); self.send(o, [{'input': self.task}]); summary = o.finish_recording()
        root = self.root / 'private-archive'
        bind_recorded_output(root, summary, self.binding, self.outcome())
        with self.assertRaises(FileExistsError): bind_recorded_output(root, summary, self.binding, self.outcome())
        with self.assertRaises(ValueError): NativeUsageObserver().enable_recording(Path('relative'), self.binding)

    def test_incomplete_worker_recording_is_failed_and_missing_output_checks_are_incomplete(self):
        o = self.recorder()
        receipt = {'ok': True, 'model_launched': True, 'native_usage': {}}
        worker_module.finalize_usage_receipt(receipt, o, [], None)
        self.assertFalse(receipt['ok']); self.assertFalse(receipt['request_recording']['complete'])
        self.assertNotIn('ASSEMBLED', json.dumps(receipt))
        o = self.recorder('complete'); self.send(o, [{'input': self.task}]); summary = o.finish_recording()
        outcome = self.outcome(); outcome['oracle_exit_code'] = None
        self.assertFalse(bind_recorded_output(self.root/'complete', summary, self.binding, outcome)['complete'])

    def test_new_native_plan_refuses_missing_archive_before_worker(self):
        with mock.patch.object(runtime, 'run_native_skill_study', side_effect=AssertionError('worker must not start')):
            with self.assertRaisesRegex(ValueError, 'request_recording_parent'):
                pilot.run_native_plan({'spec': {'agent': 'hermes'}}, self.root)

    def test_recording_gap_cannot_qualify_as_a_quality_success(self):
        row = measurement.observation({'ok': True, 'operational_ok': True,
                'request_recording': {'complete': False, 'payload': 'PRIVATE_TEXT'}}, {}, {'passed': True})
        self.assertIn('required prompt/request recording or output-check binding incomplete',
                      measurement.quality_eligibility(row)['reasons'])
        self.assertNotIn('PRIVATE_TEXT', json.dumps(row))

    def test_failed_independent_outcome_stays_negative_with_complete_recording(self):
        o = self.recorder(); self.send(o, [{'input': self.task}]); summary = o.finish_recording()
        outcome = {**self.outcome(), 'oracle_exit_code': 1, 'task_passed': False}
        joined = bind_recorded_output(self.root/'private-archive', summary, self.binding, outcome)
        self.assertTrue(joined['complete'])  # Complete evidence is not successful behavior.
        saved = json.loads((self.root/'private-archive/output-checks.json').read_bytes())
        self.assertFalse(saved['outcome']['task_passed'])

    def test_controller_joins_pair_to_own_oracle_and_keeps_admission_false(self):
        fixture = self.root / 'fixture'; fixture.mkdir(); (fixture / 'worker.py').write_text('value=1')
        oracle = self.root / 'oracle.py'; oracle.write_text('# withheld independent test')
        skill = self.root / 'skill'; skill.mkdir(); (skill / 'SKILL.md').write_text('---\nname: fixture\ndescription: test\n---\nBody')
        private = self.root / 'archive-parent'; private.mkdir()
        spec = {'purpose': 'native-skill-study', 'agent': 'hermes', 'provider': 'openai-codex',
            'terminal_backend': 'direct-python-argv',
            'model': 'gpt-6.1-sol', 'reasoning': 'medium', 'max_workers': 1, 'max_iterations': 4,
            'timeout': 30, 'quota_remaining': 1, 'workspace_root': str(self.root / 'actors'),
            'request_recording_parent': str(private), 'oracle': str(oracle),
            'arms': [{'id': 'base', 'instructions': None}, {'id': 'candidate', 'instructions': str(skill / 'SKILL.md')}],
            'cases': [{'id': 'case', 'fixture': str(fixture), 'prompt': self.task}]}
        out = self.root / 'report'; plan = pilot.prepare(spec, out)
        def worker(prompt, *args, request_recording, **kwargs):
            self.assertEqual(kwargs['terminal_backend'], 'direct-python-argv')
            o = NativeUsageObserver(); o.enable_recording(request_recording['directory'], request_recording['binding'])
            o.record_prompts('synthetic assembled', prompt); self.send(o, [{'input': prompt}])
            return {'ok': True, 'request_recording': o.finish_recording(), 'final_response': 'answer',
                    'terminal_backend': {'name':'direct-python-argv','registration_verified':True}}
        answer = SimpleNamespace(stdout='{"passed":1,"failed":0,"failures":[]}', stderr='', returncode=0)
        with mock.patch.object(runtime, 'run_native_skill_study', side_effect=worker), mock.patch.object(pilot.subprocess, 'run', return_value=answer):
            report = pilot.run(plan, out)
        self.assertEqual(len(report['results']), 2); self.assertFalse(report['admission'])
        for row in report['results']:
            self.assertTrue(row['ok'], row); self.assertTrue(row['request_recording']['complete'])
            joined = json.loads((private / ('requests-' + row['id']) / 'output-checks.json').read_bytes())
            self.assertEqual(joined['binding']['run_id'], row['id'])
            self.assertEqual(joined['outcome']['oracle_sha256'], plan['oracle_sha256'])


if __name__ == '__main__': unittest.main()
