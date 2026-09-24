"""Native diagnostic evidence is deliberately not admission evidence."""
import copy
import hashlib
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import evaluation_evidence as evidence


class NativeDiagnostic(unittest.TestCase):
    def receipt(self):
        sha = hashlib.sha256(b'fixture').hexdigest()
        route = {'model': 'gpt-6-astra', 'provider': 'openai-codex', 'reasoning': 'low'}
        trials = []
        for case in ('edit', 'taste', 'priorities', 'recommend', 'rewrite', 'depth'):
            for arm in ('baseline', 'current'):
                trials.append({'case': case, 'arm': arm, 'completed': True,
                    'requested_route': route, 'observed_route': route,
                    'surrounding_prompt_sha256': sha, 'tools_sha256': sha,
                    'fixture_before_sha256': sha, 'output_sha256': sha,
                    'actions_sha256': sha, 'fixture_after_sha256': sha,
                    'boundary_violations': [], 'cleanup_ok': True, 'api_calls': 1})
        return {'kind': 'native-instruction-diagnostic-v1', 'schema_version': 1,
            'authority': {'admission': False, 'retirement': False, 'cache': False},
            'status': 'complete', 'trial_cap': 12, 'trials': trials,
            'cases': ['edit', 'taste', 'priorities', 'recommend', 'rewrite', 'depth'],
            'artifacts': {k: sha for k in ('suite', 'adapter', 'runtime', 'raw_report')},
            'arms': {arm: {'revision': ('a' if arm == 'baseline' else 'b') * 40,
                          'soul_sha256': hashlib.sha256(arm.encode()).hexdigest(), 'skill_sha256': sha}
                     for arm in ('baseline', 'current')},
            'attempts_started': 12, 'cleanup_ok': True}

    def test_complete_diagnostic_never_grants_authority(self):
        result = evidence.validate_native_diagnostic(self.receipt())
        self.assertTrue(result['valid'], result)
        self.assertFalse(result['admission_eligible'])
        self.assertEqual(result['decision'], 'diagnostic-only')

    def test_rejects_critical_receipt_mutations(self):
        mutations = (
            lambda r: r['authority'].update(admission=True),
            lambda r: r['trials'].pop(),
            lambda r: r['trials'].append(copy.deepcopy(r['trials'][0])),
            lambda r: r['trials'][0].update(surrounding_prompt_sha256='f' * 64),
            lambda r: r['trials'][0].update(tools_sha256='f' * 64),
            lambda r: r['trials'][0].update(fixture_before_sha256='f' * 64),
            lambda r: r['trials'][0]['observed_route'].update(model='different'),
            lambda r: r['trials'][0].update(output_sha256='missing'),
            lambda r: r['trials'][0].update(boundary_violations=['outside fixture']),
            lambda r: r.update(attempts_started=13),
            lambda r: r.update(cleanup_ok=False),
            lambda r: r['arms'].update(current=copy.deepcopy(r['arms']['baseline'])),
        )
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                receipt = copy.deepcopy(self.receipt())
                # Ensure requested and observed do not alias in synthetic control.
                for trial in receipt['trials']:
                    trial['observed_route'] = dict(trial['observed_route'])
                mutate(receipt)
                self.assertFalse(evidence.validate_native_diagnostic(receipt)['valid'])

    def test_malformed_input_fails_closed(self):
        for receipt in (None, [], {}, {'kind': 'native-instruction-diagnostic-v1'}):
            self.assertFalse(evidence.validate_native_diagnostic(receipt)['valid'])


if __name__ == '__main__':
    unittest.main()
