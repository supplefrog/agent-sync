"""Offline checks for a diagnostic that must never authorize inference."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import evaluation_native_diagnostic as diagnostic
from evaluation_native_worker import AssemblyGuard, ProbeBoundary, observer


class PreflightContract(unittest.TestCase):
    def test_environment_loads_only_staged_config_without_disabling_rules(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = diagnostic.probe_environment({'PATH': 'system-path', 'SECRET_TOKEN': 'private',
                'HERMES_HOME': 'live', 'HERMES_IGNORE_RULES': '1'}, Path(tmp))
            self.assertNotIn('SECRET_TOKEN', env)
            self.assertNotIn('HERMES_IGNORE_RULES', env)
            self.assertNotIn('HERMES_IGNORE_USER_CONFIG', env)
            self.assertEqual(Path(env['HERMES_HOME']), Path(tmp) / 'hermes')
            self.assertEqual(env['PYTHONDONTWRITEBYTECODE'], '1')

    def test_episode_cannot_be_reused_or_escape_owner(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = diagnostic.create_episode(root, 'a' * 32)
            with self.assertRaises(FileExistsError):
                diagnostic.create_episode(root, 'a' * 32)
            for bad in ('../escape', 'A' * 32, '', 'a' * 31):
                with self.subTest(bad=bad), self.assertRaises(ValueError):
                    diagnostic.create_episode(root, bad)
            self.assertEqual(first.parent, root.resolve())

    def test_network_forbidden_probe_strips_all_proxy_case_variants(self):
        source = {'PATH': 'system-path'}
        for name in ('HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'NO_PROXY'):
            for key in (name, name.lower(), name.title()):
                source[key] = 'http://fixture-user:fixture-password@proxy.invalid:8080'
        with tempfile.TemporaryDirectory() as tmp:
            env = diagnostic.probe_environment(source, Path(tmp))
        self.assertEqual(env['PATH'], source['PATH'])
        self.assertFalse(any(key.upper().endswith('_PROXY') for key in env))
        self.assertNotIn('fixture-password', json.dumps(env))

    def test_attempt_is_reserved_before_launch_and_never_reused(self):
        with tempfile.TemporaryDirectory() as tmp:
            episode = diagnostic.create_episode(Path(tmp))
            first = diagnostic.reserve_probe(episode, 'baseline')
            self.assertEqual(first['state'], 'reserved')
            self.assertEqual(first['model_requests'], 0)
            with self.assertRaises(FileExistsError):
                diagnostic.reserve_probe(episode, 'baseline')
            diagnostic.reserve_probe(episode, 'current')
            with self.assertRaises(ValueError):
                diagnostic.reserve_probe(episode, 'replacement')
            self.assertEqual(len(list((episode / 'attempts').glob('*.json'))), 2)

    def test_exact_projection_does_not_hide_other_instruction_changes(self):
        left = 'common prefix\nold sentence\nshared suffix'
        right = 'common prefix\nnew sentence\nshared suffix'
        spans = [{'baseline': 'old sentence', 'current': 'new sentence'}]
        self.assertTrue(diagnostic.equal_except_declared(left, right, spans))
        self.assertFalse(diagnostic.equal_except_declared(left, right + '\nrogue rule', spans))
        self.assertFalse(diagnostic.equal_except_declared(left, right, []))
        with self.assertRaises(ValueError):
            diagnostic.equal_except_declared(left + left, right, spans)

    def test_source_spans_are_actual_substrings_not_hash_only_claims(self):
        prompt = 'header\nNative source text\nfooter'
        records = diagnostic.locate_sources(prompt, [{'source': 'native:function', 'text': 'Native source text'}])
        item = records[0]
        self.assertEqual(prompt[item['start']:item['end']], 'Native source text')
        self.assertEqual(item['sha256'], diagnostic.digest(b'Native source text'))
        missing = diagnostic.locate_sources(prompt, [{'source': 'unloaded:skill', 'text': 'not present'}])
        self.assertEqual(missing, [])

    def test_private_bindings_are_recomputed_and_path_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'source.md').write_text('actual', encoding='utf-8')
            records = {'source.md': diagnostic.digest(b'actual')}
            diagnostic.verify_files(root, records)
            (root / 'source.md').write_text('changed', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'changed'):
                diagnostic.verify_files(root, records)
            with self.assertRaises(ValueError):
                diagnostic.verify_files(root, {'../outside': '0' * 64})
            with self.assertRaises(ValueError):
                diagnostic.verify_files(root, {'missing': '0' * 64})

    def test_public_export_is_allowlisted_and_blocked_is_valid_evidence(self):
        private = {'run_id': 'a' * 32, 'observations': [{'arm': 'baseline', 'assembled': True,
            'raw_prompt': 'private prompt', 'api_key': 'DO-NOT-EXPORT', 'path': 'C:/private',
            'prompt_sha256': 'b' * 64, 'process_reaped': True, 'runtime_removed': True}], 'cleanup_ok': True,
            'blockers': ['full-native-context-not-attested'], 'model_requests': 0}
        public = diagnostic.public_receipt(private, {'manifest.json': 'c' * 64})
        text = json.dumps(public)
        for secret in ('DO-NOT-EXPORT', 'private prompt', 'C:/private'):
            self.assertNotIn(secret, text)
        self.assertEqual(public['status'], 'blocked-before-inference')
        self.assertFalse(public['launch_permitted'])
        self.assertEqual(public['model_requests'], 0)
        self.assertTrue(diagnostic.validate_preflight(public)['valid'])
        self.assertFalse(diagnostic.validate_preflight(public)['admission_eligible'])
        for field, value in [('launch_permitted', True), ('model_requests', 1), ('cleanup_ok', False)]:
            changed = copy.deepcopy(public)
            changed[field] = value
            self.assertFalse(diagnostic.validate_preflight(changed)['valid'])

    def test_observations_require_consistent_typed_cleanup_evidence(self):
        observation = {'arm': 'baseline', 'assembled': False,
                       'process_reaped': True, 'runtime_removed': True,
                       'error_type': 'ProbeBoundary', 'boundary_reason': 'subprocess-attempt'}
        report = diagnostic.public_receipt({'run_id': 'a' * 32, 'observations': [observation],
            'cleanup_ok': True, 'blockers': ['native-assembly-incomplete'], 'model_requests': 0},
            {'manifest.json': 'b' * 64})
        self.assertTrue(diagnostic.validate_preflight(report)['valid'])  # legitimate early stop
        changed = copy.deepcopy(report)
        del changed['observations']
        self.assertFalse(diagnostic.validate_preflight(changed)['valid'])
        for observations in (None, [], {}, [None], [observation, observation]):
            with self.subTest(observations=observations):
                changed = copy.deepcopy(report)
                changed['observations'] = observations
                self.assertFalse(diagnostic.validate_preflight(changed)['valid'])
        for field, value in (('arm', 'unknown'), ('arm', None), ('assembled', 0),
                ('process_reaped', False), ('runtime_removed', False),
                ('process_reaped', 1), ('runtime_removed', 'true'),
                ('prompt_sha256', 'invalid'), ('tools_sha256', 42),
                ('source_spans', True), ('source_spans', -1),
                ('error_type', []), ('boundary_reason', {})):
            with self.subTest(field=field, value=value):
                changed = copy.deepcopy(report)
                changed['observations'][0][field] = value
                self.assertFalse(diagnostic.validate_preflight(changed)['valid'])
        for field in ('arm', 'assembled', 'process_reaped', 'runtime_removed'):
            with self.subTest(missing=field):
                changed = copy.deepcopy(report)
                del changed['observations'][0][field]
                self.assertFalse(diagnostic.validate_preflight(changed)['valid'])
        changed = copy.deepcopy(report)
        changed['observations'].append(dict(observation, arm='current'))
        self.assertTrue(diagnostic.validate_preflight(changed)['valid'])

    def test_no_run_command_is_available(self):
        result = subprocess.run([sys.executable, diagnostic.__file__, 'run'], capture_output=True,
                                text=True, timeout=10)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('invalid choice', result.stderr)

    def test_worker_rejects_inference_job_before_native_imports(self):
        worker = Path(diagnostic.__file__).with_name('evaluation_native_worker.py')
        result = subprocess.run([sys.executable, str(worker)], input='{"run":true}\n',
                                capture_output=True, text=True, timeout=10)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('inference is unsupported', result.stderr)

    def test_audit_boundary_cannot_be_swallowed_as_ordinary_exception(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            violations = []
            guard = AssemblyGuard(root, root, violations)
            for event, args in (
                ('socket.connect', (None, ('example.invalid', 443))),
                ('subprocess.Popen', ('python', [], '.', {})),
                ('open', (root / '.env', 'r', 0)),
                ('open', (root.parent / 'unowned', 'w', os.O_WRONLY)),
                ('os.rename', (root / 'source', root.parent / 'escape', -1, -1)),
            ):
                with self.subTest(event=event), self.assertRaises(ProbeBoundary):
                    guard(event, args)
            self.assertEqual(len(violations), 5)
            self.assertFalse(issubclass(ProbeBoundary, Exception))
            guard('open', (root / 'owned', 'w', os.O_WRONLY))

    def test_real_child_audit_guard_blocks_write_before_effect(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            private = root / 'owned'
            private.mkdir()
            outside = root / 'must-not-exist'
            script = (f'import sys; from pathlib import Path; sys.path.insert(0, {str(Path(diagnostic.__file__).parent)!r}); '
                      'from evaluation_native_worker import AssemblyGuard, ProbeBoundary; '
                      f'root=Path({str(private)!r}); sys.addaudithook(AssemblyGuard(root,root,[])); '
                      f'Path({str(outside)!r}).write_text("forbidden")')
            result = subprocess.run([sys.executable, '-c', script], capture_output=True, text=True, timeout=10)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('outside-owned-write', result.stderr)
            self.assertFalse(outside.exists())

    def test_observer_preserves_native_return_value(self):
        records = []
        def native():
            return (['actual source'], True)
        wrapped = observer(native, records)
        self.assertEqual(wrapped(), native())
        self.assertEqual(records[0]['text'], 'actual source')
        self.assertTrue(records[0]['source'].endswith(':native'))

    def test_local_hostname_lookup_is_not_a_network_connection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            violations = []
            guard = AssemblyGuard(root, root, violations)
            guard('socket.gethostname', ())
            self.assertEqual(violations, [])
            with self.assertRaises(ProbeBoundary):
                guard('socket.getaddrinfo', ('example.invalid', 443, 0, 0, 0))

    def test_process_timeout_is_reaped_and_recorded(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = diagnostic.run_child([sys.executable, '-c', 'import time; time.sleep(30)'],
                {}, dict(os.environ), root, root, timeout=0.25)
            self.assertTrue(result['timed_out'])
            self.assertTrue(result['reaped'])
            self.assertIsNotNone(result['returncode'])
            persisted = json.loads((root / 'process.json').read_text())
            self.assertEqual(persisted['pid'], result['pid'])
            self.assertTrue(persisted['reaped'])

    def test_staging_failure_preserves_attempt_and_removes_runtime(self):
        with tempfile.TemporaryDirectory() as tmp:
            episode = diagnostic.create_episode(Path(tmp))
            # Missing source produces a real staging failure, not a model failure.
            result = diagnostic.probe_one(episode, {}, {}, 'baseline')
            self.assertFalse(result['assembled'])
            self.assertFalse(result['worker_started'])
            self.assertTrue(result['runtime_removed'])
            self.assertTrue(result['process_reaped'])
            self.assertTrue((episode / 'attempts/baseline.json').is_file())
            self.assertEqual(result['error_type'], 'FileNotFoundError')

    def test_malformed_preflight_never_becomes_authority(self):
        for report in (None, [], {}, {'kind': 'native-instruction-preflight-v1'}):
            with self.subTest(report=report):
                self.assertFalse(diagnostic.validate_preflight(report)['valid'])
                self.assertFalse(diagnostic.validate_preflight(report)['launch_permitted'])


if __name__ == '__main__':
    unittest.main()
