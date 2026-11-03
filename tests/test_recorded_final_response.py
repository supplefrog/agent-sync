"""Real recording producer/binder controls; synthetic data, no native calls."""
import ast
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from evaluation_usage import NativeUsageObserver, bind_recorded_output

sha = lambda data: hashlib.sha256(data).hexdigest()


class RecordedFinalResponse(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='agent-sync-response-control-')
        self.parent = Path(self.temporary.name).resolve()
        assert self.parent.is_relative_to(Path(tempfile.gettempdir()).resolve())
        self.addCleanup(self.temporary.cleanup)
        self.directory = self.parent / 'recording'
        self.response = b'Synthetic completed output.'
        task = b'Synthetic task.'
        self.binding = dict(run_id='synthetic-run', case_id='synthetic-case', arm='B',
                            plan_sha256=sha(b'plan'), task_sha256=sha(task), oracle_sha256=sha(b'oracle'))
        self.observer = NativeUsageObserver()
        self.observer.enable_recording(self.directory, self.binding)
        self.observer.record_prompts('Synthetic assembled prompt.', task.decode())
        self.observer._retain('final-request', b'{"input":[]}')
        self.observer.http_events.append({'phase': 'request'})
        self.outcome = dict(oracle_sha256=self.binding['oracle_sha256'], oracle_exit_code=0,
                            outcome_schema_version=2, deterministic_invariants_passed=True,
                            task_passed=None, oracle_result_sha256=sha(b'checks'),
                            final_tree_sha256=sha(b'tree'), final_response_sha256=sha(self.response))

    def emit_worker_response(self):
        tree = ast.parse((ROOT / 'tools/evaluation_hermes_worker.py').read_text(encoding='utf-8'))
        matches = [node for node in ast.walk(tree) if isinstance(node, ast.If)
                   and "usage_observer._retain('final-response'" in ast.unparse(node)
                   and 'tool_scope == EVIDENCE_SCOPE' in ast.unparse(node.test)]
        self.assertEqual(len(matches), 1)
        env = dict(tool_scope='synthetic-evidence', EVIDENCE_SCOPE='synthetic-evidence',
                   usage_observer=self.observer, native={'final_response': self.response.decode()})
        exec(compile(ast.Module(body=matches, type_ignores=[]), 'actual-worker-response-handoff', 'exec'), env)

    def finish(self):
        summary = self.observer.finish_recording()
        self.assertTrue(summary['complete'])
        return summary

    def bind(self, summary):
        return bind_recorded_output(self.directory, summary, self.binding, self.outcome)

    def test_worker_response_archive_binds_exact_outcome(self):
        self.emit_worker_response()
        result = self.bind(self.finish())
        self.assertTrue(result['complete'])
        self.assertFalse(result['execution_authenticated'])
        joined = json.loads((self.directory / 'output-checks.json').read_bytes())
        self.assertEqual(joined['outcome']['final_response_sha256'], sha(self.response))

    def test_legacy_archive_without_response_remains_supported(self):
        self.assertTrue(self.bind(self.finish())['complete'])

    def test_duplicate_response_is_rejected(self):
        self.emit_worker_response(); self.emit_worker_response()
        with self.assertRaisesRegex(ValueError, 'Duplicate retained final response'):
            self.bind(self.finish())
        self.assertFalse((self.directory / 'output-checks.json').exists())

    def test_tampered_response_body_is_rejected(self):
        self.emit_worker_response(); summary = self.finish()
        (self.directory / '000003-final-response.bin').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'payload changed'):
            self.bind(summary)

    def test_wrong_outcome_response_digest_is_rejected(self):
        self.emit_worker_response(); summary = self.finish()
        self.outcome['final_response_sha256'] = sha(b'other response')
        with self.assertRaisesRegex(ValueError, 'final response differs'):
            self.bind(summary)

    def test_wrong_run_is_rejected(self):
        self.emit_worker_response(); summary = self.finish()
        self.binding['run_id'] = 'different-run'
        with self.assertRaisesRegex(ValueError, 'different run'):
            self.bind(summary)

    def test_unknown_blob_kind_is_still_rejected(self):
        self.observer._retain('unknown-kind', b'synthetic')
        with self.assertRaisesRegex(ValueError, 'Unsafe recording blob identity'):
            self.bind(self.finish())

    def test_response_filename_is_still_bound(self):
        self.emit_worker_response(); summary = self.finish()
        manifest = json.loads((self.directory / 'manifest.json').read_bytes())
        manifest['blobs'][-1]['file'] = 'response.bin'
        raw = json.dumps(manifest, sort_keys=True).encode()
        (self.directory / 'manifest.json').write_bytes(raw)
        summary['manifest_sha256'] = sha(raw)
        with self.assertRaisesRegex(ValueError, 'Unsafe recording blob identity'):
            self.bind(summary)


if __name__ == '__main__':
    unittest.main()
