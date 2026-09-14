"""Task-first ingress and policy tests; fixture routes are not live evidence."""
import copy
import unittest
from test_task_router import ROOT, REL, candidate, catalog, load, ref, router

requests = load('task_first_requests', ROOT / REL / 'scripts/task_request.py')
plugin = load('task_first_plugin', ROOT / 'integrations/hermes/routed-delegation/__init__.py')


def work():
    return {'task_class': 'bounded-source-evidence-review', 'acceptance': 'Check every material claim against the original source; reject unsupported conclusions.',
            'placement_reason': 'Isolate a source-heavy review from parent integration.',
            'tools': ['read_file', 'search_files'], 'context_tokens': 32000,
            'max_requests': 8, 'accept_unknown_quota': True, 'authorized': True,
            'effects': 'none', 'failure_cost': 'low'}


def fixture():
    task = requests.materialize(requests.work_template(work()), task_id='review', host='hermes', transport='hermes-delegate',
                                input_descriptor={'goal': 'Review sources'}, as_of='2026-09-06T12:00:00Z')
    values = []
    for name in ('lean', 'strong'):
        c = candidate(name, total=None)
        c['route'].update(host='hermes', transport='hermes-delegate')
        c['availability'].update(route_sha256=router.digest(c['route']), tools_verified=work()['tools'], context_tokens=64000)
        values.append(c)
    cat = catalog(*values)
    cat['task_preferences'] = {'bounded-source-evidence-review': {'route_ids': ['lean', 'strong'],
        'rationale': 'Synthetic source-review prior; not a measured optimum.', 'evidence': ref('prior')}}
    return cat, task


class TaskFirstTests(unittest.TestCase):
    def test_normal_ingress_does_not_require_a_candidate_or_proof_hashes(self):
        task = plugin._normalize_task({'id': 'review', 'goal': 'Inspect sources', 'work': work()})
        template = task['route_request']
        self.assertIsNone(template['requirements']['model'])
        self.assertIsNone(template['requirements']['reasoning_effort'])
        self.assertEqual(template['budget']['preference_order'], [])
        self.assertEqual(task['toolsets'], ['file'])

    def test_acceptance_survives_normalization_and_denied_trial_stays_parent(self):
        raw = {'id': 'review', 'goal': 'Inspect sources', 'work': work()}
        task = plugin._normalize_task(raw)
        self.assertEqual(task['_work']['acceptance'], raw['work']['acceptance'])
        self.assertIn(raw['work']['acceptance'], task['context'])
        cat, request = fixture()
        request['budget']['evidence_trial']['authorized'] = False
        self.assertEqual(router.decide_route(cat, request)['outcome'], 'keep_parent')

    def test_public_schema_accepts_work_and_rejects_mixed_pins(self):
        import jsonschema
        class Context:
            def __init__(self): self.tools = {}
            def register_hook(self, *args): pass
            def register_tool(self, **kwargs): self.tools[kwargs['name']] = kwargs
        ctx = Context()
        plugin.register(ctx)
        schema = ctx.tools['routed_delegate_task']['schema']['parameters']
        good = {'tasks': [{'id': 'review', 'goal': 'Inspect', 'work': work()}]}
        jsonschema.validate(good, schema)
        for extra in ({'route_request': {}}, {'intelligence_tier': 'routine', 'latency_sensitive': False}):
            bad = copy.deepcopy(good)
            bad['tasks'][0].update(extra)
            with self.assertRaises(jsonschema.ValidationError): jsonschema.validate(bad, schema)
        task = plugin._normalize_task(good['tasks'][0])
        descriptor = plugin._v3_input_descriptor(task, 12)
        self.assertEqual(descriptor['work']['acceptance'], work()['acceptance'])

    def test_task_preference_is_not_current_model_inheritance(self):
        cat, task = fixture()
        for parent in ('fixture-lean', 'fixture-strong'):
            task['input_sha256'] = router.digest({'parent_model': parent, 'goal': 'same review'})
            receipt = router.decide_route(cat, task)
            self.assertEqual(receipt['route_id'], 'lean')
            self.assertEqual(receipt['selection_basis'], 'reviewed_task_preference_unmeasured')
            self.assertNotIn('minimum', receipt['resource_claim'])
            self.assertEqual(router.replay_decision(receipt, cat, task), receipt)

    def test_capability_unavailability_and_regression_beat_preference(self):
        for reason in ('tools', 'expiry', 'regression', 'quota', 'api'):
            cat, task = fixture()
            c = cat['candidates'][0]
            if reason == 'tools': c['availability']['tools_verified'] = []
            if reason == 'expiry': c['availability']['valid_until'] = '2026-09-06T11:00:01Z'
            if reason == 'regression':
                c['quality'] = [{'task_class': task['task_class'], 'task_contract_sha256': task['requirements']['task_contract_sha256'],
                    'verifier_sha256': task['verifier']['evidence']['sha256'], 'route_sha256': router.digest(c['route']),
                    'status': 'regression', 'scope': 'artifact-effects', 'evidence': ref('regression')}]
            if reason == 'quota':
                c['cost']['quota']['bucket'] = 'empty'
                task['budget']['quotas']['empty'] = {'unit': 'fixture-units', 'remaining': 0, 'reserve': 0}
            if reason == 'api': c['cost']['billing'] = 'api'
            with self.subTest(reason=reason):
                result = router.decide_route(cat, task)
                self.assertEqual(result['route_id'], 'strong')
                self.assertIn('lean', result['excluded'])

    def test_unmapped_or_consequential_work_stays_parent(self):
        for change in ({'task_class': 'integration-design'}, {'failure_cost': 'high'}, {'effects': 'reversible'}):
            cat, task = fixture()
            task.update(change)
            self.assertEqual(router.decide_route(cat, task)['outcome'], 'keep_parent')

    def test_no_model_pin_can_masquerade_as_task_selection(self):
        cat, task = fixture()
        task['requirements']['model'] = 'fixture-strong'
        with self.assertRaises(ValueError): router.decide_route(cat, task)
        for extra in ({'model': 'anything'}, {'tools': ['terminal']}, {'acceptance': ''}):
            with self.assertRaises(ValueError): requests.work_template({**work(), **extra})
        with self.assertRaises(ValueError):
            plugin._normalize_task({'id': 'review', 'goal': 'Inspect', 'work': work(), 'route_request': {}})

    def test_missing_policy_and_all_routes_unavailable_do_not_clone_parent(self):
        cat, task = fixture()
        del cat['task_preferences']
        self.assertEqual(router.decide_route(cat, task)['outcome'], 'keep_parent')
        cat, task = fixture()
        for c in cat['candidates']: c['availability']['status'] = 'unverified'
        self.assertEqual(router.decide_route(cat, task)['outcome'], 'keep_parent')


if __name__ == '__main__': unittest.main()
