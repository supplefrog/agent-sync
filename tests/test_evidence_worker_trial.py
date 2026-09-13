"""Evidence trials retain hard gates without demanding a semantic oracle."""
import copy
import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / 'skills/openai-delegation-route-research'

def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

class EvidenceTrialTests(unittest.TestCase):
    def setUp(self):
        self.selector = load('route_selector')
        self.catalog = json.loads((ROOT / 'references/current-task-route-catalog.json').read_text())
        self.c = next(c for c in self.catalog['candidates'] if c['id'] == 'hermes-astra-medium-tools')
        self.catalog['candidates'] = [self.c]
        self.request = {
            'schema_version': 3, 'task_class': 'source-review',
            'requirements': {'context_tokens': 12000, 'model': self.c['route']['model'], 'reasoning_effort': self.c['route']['reasoning_effort'], 'tools': ['read_file', 'search_files'], 'task_contract_sha256': 'a' * 64},
            'verifier': {'kind': 'independent-review', 'coverage': 'complete', 'independent': True, 'scope': 'artifact-effects', 'evidence': {'locator': 'fixture-review', 'sha256': 'b' * 64}},
            'effects': 'none', 'failure_cost': 'low', 'deterministic': None,
            'budget': {'objective': 'quota', 'allow_api_spend': False, 'api_remaining': None, 'api_reserve': 0, 'quotas': {}, 'unknown_cost_policy': 'explicit_preference', 'preference_order': [self.c['id']], 'parent_available': True, 'attempt_cap': 1, 'attempts_used': 0, 'fallback_route_id': None, 'fallback_route_sha256': None,
                'evidence_trial': {'authorized': True, 'max_requests': 12, 'placement_reason': 'Isolate source inspection from parent context', 'accept_unknown_quota': True}}
        }

    def decide(self, request=None):
        task = load('task_request').materialize(request or self.request, task_id='fixture-trial', host='hermes', transport='hermes-delegate', input_descriptor={'goal': 'source review'}, as_of=self.c['availability']['observed_at'])
        return self.selector.decide_route_v3(self.catalog, task)

    def test_read_only_semantic_trial_with_unknown_quota(self):
        decision = self.decide()
        self.assertEqual(decision['outcome'], 'selected_model')
        self.assertEqual(decision['qualification'], 'provisional-evidence-trial')
        self.assertNotIn('minimum comparable', decision['resource_claim'])

    def test_nearby_hard_failures_remain_closed(self):
        cases = [
            (('effects',), 'reversible'), (('failure_cost',), 'high'),
            (('requirements', 'tools'), ['terminal']),
            (('verifier', 'coverage'), 'partial'),
            (('budget', 'evidence_trial', 'authorized'), False),
            (('budget', 'evidence_trial', 'accept_unknown_quota'), False),
            (('budget', 'parent_available'), False),
            (('budget', 'attempt_cap'), 2),
            (('budget', 'quotas'), {'codex-main': {'unit': 'percentage-points', 'remaining': 0, 'reserve': 0}}),
            (('budget', 'quotas'), {'codex-main': {'unit': 'percentage-points', 'remaining': None, 'reserve': 1}}),
            (('budget', 'quotas'), {'codex-main': {'unit': 'tokens', 'remaining': 100, 'reserve': 0}}),
        ]
        for keys, value in cases:
            with self.subTest(keys=keys, value=value):
                request = copy.deepcopy(self.request)
                target = request
                for key in keys[:-1]:
                    target = target[key]
                target[keys[-1]] = value
                self.assertNotEqual(self.decide(request)['outcome'], 'selected_model')

    def test_no_opt_in_preserves_old_policy(self):
        del self.request['budget']['evidence_trial']
        self.assertEqual(self.decide()['outcome'], 'keep_parent')

    def test_regression_and_paid_route_still_excluded(self):
        self.c['quality'] = [{'task_class': 'source-review', 'task_contract_sha256': 'a'*64, 'verifier_sha256': 'b'*64, 'route_sha256': self.selector.digest(self.c['route']), 'status': 'regression', 'scope': 'artifact-effects', 'evidence': self.request['verifier']['evidence']}]
        self.assertEqual(self.decide()['outcome'], 'keep_parent')
        self.c['quality'] = []
        self.c['cost']['billing'] = 'api'
        self.assertEqual(self.decide()['outcome'], 'keep_parent')

if __name__ == '__main__':
    unittest.main()
