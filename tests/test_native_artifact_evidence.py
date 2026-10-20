"""Synthetic source/receipt validation; no native execution or admission claim."""
from fixture_workspace import configure
configure()
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import artifact_hash
import evaluation_artifact_pilot as pilot
import evaluation_measurement as measurement
from evaluation_evidence import validate_artifact_evidence


def make_native_evidence(root):
    fixture = root / 'fixture'; fixture.mkdir(parents=True)
    (fixture / 'app.txt').write_bytes(b'fixture')
    skill = root / 'skill'; skill.mkdir()
    (skill / 'SKILL.md').write_bytes(b'---\nname: fixture\ndescription: Synthetic only\n---\nFixture body\n')
    oracle = root / 'oracle.py'; oracle.write_bytes(b'# synthetic oracle source; never executed\n')
    spec = {'purpose': 'native-skill-study', 'agent': 'hermes', 'model': 'gpt-6-sol',
            'provider': 'openai-codex', 'reasoning': 'medium',
            'arms': [{'id': 'base', 'instructions': None}, {'id': 'candidate', 'instructions': str(skill / 'SKILL.md')}],
            'cases': [{'id': 'task', 'fixture': str(fixture), 'prompt': 'Synthetic task', 'prerequisites_sha256': '8'*64}],
            'catalog': [], 'workspace_root': str(root / 'work'), 'oracle': str(oracle),
            'max_workers': 1, 'max_iterations': 4, 'timeout': 30, 'quota_remaining': 1}
    plan = pilot.prepare(spec, root / 'out')
    # Explicit synthetic fixture metadata, not a historical runtime observation.
    plan['measurement_sha256'] = pilot.sha(ROOT / 'tools/evaluation_measurement.py')
    plan['usage_observer_sha256'] = pilot.sha(ROOT / 'tools/evaluation_usage.py')
    rows = []
    for job in plan['jobs']:
        native = {'ok': True, 'model_launched': True, 'host_version': 'synthetic-v1',
                  'agent_observed_route': {key: spec[key] for key in ('model', 'provider', 'reasoning')},
                  'catalog_evidence': {'prompt_sha256': hashlib.sha256(b'synthetic assembled prompt').hexdigest(),
                                       'exact_catalog_verified': True},
                  'cleanup': {'state_removed': True, 'errors': []}, 'final_response': 'synthetic'}
        rows.append({'id': job['id'], 'arm': job['arm'], 'case': job['case'], 'ok': True,
                     'native': native, 'oracle_exit_code': 0,
                     'oracle': {'passed': 1, 'failed': 0, 'failures': []}, 'final_tree': job['initial_tree']})
    report = {'kind': 'native-skill-study', 'workflow_comparison_supported': False,
              'admission': False, 'results': rows, 'completed_trials': 2, 'expected_trials': 2}
    corpus = [oracle, ROOT / 'tools/evaluation_artifact_pilot.py', ROOT / 'tools/evaluation_artifact_worker.py',
              ROOT / 'tools/evaluation_hermes_worker.py', ROOT / 'tools/evaluation_runtime.py',
              ROOT / 'tools/evaluation_measurement.py', ROOT / 'tools/evaluation_usage.py']
    corpus += [path for path in root.rglob('*') if path.is_file()]
    source_bytes = {hashlib.sha256(path.read_bytes()).hexdigest(): path.read_bytes() for path in corpus}
    source_bytes[hashlib.sha256(b'synthetic assembled prompt').hexdigest()] = b'synthetic assembled prompt'
    return report, plan, source_bytes


class NativeArtifactEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.enterContext(mock.patch('subprocess.Popen', side_effect=AssertionError('no child/model/oracle execution')))
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.report, self.plan, self.sources = make_native_evidence(self.root)

    def check(self, sources=True):
        with mock.patch.object(Path, 'read_bytes', side_effect=AssertionError('validator must not open recorded paths')):
            return validate_artifact_evidence(self.report, self.plan,
                                             source_bytes=self.sources if sources else None)

    def test_consistent_supplied_bytes_validate_without_admission_or_live_proof(self):
        result = self.check()
        self.assertEqual(result['errors'], [])
        self.assertTrue(result['source_bytes_complete'], result['source_gaps'])
        self.assertTrue(result['consistent'])
        self.assertFalse(result['admission'])
        self.assertFalse(result['positive_decision_sufficient'])
        self.assertFalse(result['execution_authenticated'])
        self.assertTrue(result['admission_blockers'])
        self.assertTrue(result['runtime_gaps'])  # Assembled system prompt is not the user task.
        self.assertFalse(result['usage_readiness']['ready'])  # Missing usage is never zero.

    def test_missing_bytes_are_explicit_gaps_not_authenticity(self):
        result = self.check(sources=False)
        self.assertTrue(result['consistent'])
        self.assertFalse(result['source_bytes_complete'])
        self.assertTrue(result['source_gaps'])

    def test_failed_task_is_consistent_negative_evidence(self):
        row = self.report['results'][0]
        row['oracle'] = {'passed': 0, 'failed': 1, 'failures': ['synthetic task failure']}
        row['ok'] = False
        result = self.check()
        self.assertTrue(result['consistent'], result['errors'])
        self.assertFalse(result['records'][0]['outcome']['quality_passed'])
        self.assertFalse(result['admission'])

    def test_wrong_bytes_and_package_identity_are_rejected(self):
        digest = self.plan['oracle_sha256']; self.sources[digest] = b'changed'
        self.assertFalse(self.check()['consistent'])
        self.sources[digest] = (self.root / 'oracle.py').read_bytes()
        self.plan['candidate_snapshots']['candidate']['package_sha256'] = '0'*64
        self.assertIn('candidate/candidate: package identity mismatch', self.check()['errors'])

    def test_package_hash_reuses_freezer_identity(self):
        snapshot = self.plan['candidate_snapshots']['candidate']
        self.assertEqual(snapshot['package_sha256'], artifact_hash.package_hash_from_files(snapshot['files']))

    def test_false_authority_and_saved_projection_relabeling_rejected(self):
        self.report['admission'] = True
        self.assertFalse(self.check()['consistent'])
        self.report['admission'] = False
        self.report['measurements'] = measurement.artifact_records(self.report, self.plan)
        self.assertTrue(self.check()['consistent'])
        self.report['measurements'][0]['outcome']['task_passed'] = False
        self.assertIn('saved native measurements differ from raw receipt projection', self.check()['errors'])

    def test_duplicate_missing_and_mismatched_results_rejected(self):
        original = copy.deepcopy(self.report)
        for change in ('duplicate', 'missing', 'arm'):
            self.report = copy.deepcopy(original)
            if change == 'duplicate': self.report['results'][1] = copy.deepcopy(self.report['results'][0])
            if change == 'missing': self.report['results'].pop()
            if change == 'arm': self.report['results'][0]['arm'] = 'candidate'
            with self.subTest(change=change): self.assertFalse(self.check()['consistent'])

    def test_prompt_route_and_fixture_drift_rejected(self):
        original = copy.deepcopy(self.report)
        for change in ('prompt', 'route', 'fixture'):
            self.report = copy.deepcopy(original)
            row = self.report['results'][0]
            if change == 'prompt': row['native']['catalog_evidence']['prompt_sha256'] = 'not-a-digest'
            if change == 'route': row['native']['agent_observed_route']['model'] = 'other'
            if change == 'fixture': self.plan['jobs'][0]['initial_tree']['app.txt'] = '0'*64
            with self.subTest(change=change): self.assertFalse(self.check()['consistent'])

    def test_catalog_and_outcome_contradictions_rejected(self):
        original = copy.deepcopy(self.report)
        self.report['results'][0]['ok'] = False
        self.assertIn('native outcome contradicts raw execution/oracle receipts', self.check()['errors'])
        self.report = original
        self.plan['jobs'][1]['catalog_frames'].clear()
        self.assertIn('prepared native catalog binding mismatch', self.check()['errors'])

    def test_undeclared_initial_sources_and_escaping_catalog_rejected(self):
        self.plan['jobs'][0]['initial_tree']['unrecorded-context.md'] = '0'*64
        self.assertIn('native initial tree contains missing, changed or undeclared sources', self.check()['errors'])
        self.plan['jobs'][0]['initial_tree'].pop('unrecorded-context.md')
        job = self.plan['jobs'][1]
        digest = next(iter(job['catalog_frames'].values()))
        for location in ('C:\\outside\\SKILL.md', str(Path(job['fixture']) / '.agents/skills/../SKILL.md')):
            job['catalog_frames'] = {location: digest}
            job['catalog'] = list(job['catalog_frames'])
            with self.subTest(location=location): self.assertFalse(self.check()['consistent'])

    def test_unsafe_manifest_and_malformed_plan_are_rejected_without_io(self):
        original = copy.deepcopy(self.plan)
        self.plan['case_source_trees']['task']['../escape'] = '0'*64
        self.assertFalse(self.check()['consistent'])
        self.plan = original
        self.plan['jobs'] = None
        self.assertFalse(self.check()['consistent'])


if __name__ == '__main__':
    unittest.main()
