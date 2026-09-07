"""Actual durable v2 run replay across a staged v3 selector upgrade."""
import copy
import hashlib
import importlib.util
import json
import shutil
import sys
import unittest
import uuid
from pathlib import Path
from unittest import mock

BASE = Path(__file__).resolve().parents[1]
STAGE = BASE
REL = Path('skills/openai-delegation-route-research')
source = STAGE / 'skills/dynamic-workflows/scripts/workflow_state.py'
spec = importlib.util.spec_from_file_location('workflow_consumer_candidate', source)
ws = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ws)

class ConsumerCompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.root = BASE / '.tmp-workflow-router-tests' / uuid.uuid4().hex
        self.root.mkdir(parents=True)
        self.catalog = self.root / 'installed/catalog.json'
        self.selector = self.root / 'installed/route_selector.py'
        self.selector.parent.mkdir()
        self.catalog.write_bytes((STAGE / REL / 'references/current-gpt-catalog.json').read_bytes())
        self.old = (STAGE / REL / 'scripts/selector-history/fcac25bdde0895b46239b7deec662e0711ad63f04a3cb39195ffd5814e2f306c.py').read_bytes()
        self.old_hash = hashlib.sha256(self.old).hexdigest()
        self.selector.write_bytes(self.old)
        self.patch = mock.patch.object(ws, 'default_router_paths', return_value=(self.catalog, self.selector))
        self.patch.start()
        self.task = {'id': 'work', 'prompt': 'Inspect synthetic fixture', 'intelligence_tier': 'routine',
                     'latency_sensitive': False, 'task_class': 'fixture-inspection', 'failure_cost': 'low',
                     'acceptance': ['Return exact fixture content']}

    def tearDown(self):
        self.patch.stop()
        self.root.resolve().relative_to((BASE / '.tmp-workflow-router-tests').resolve())
        shutil.rmtree(self.root)

    def init(self, task=None):
        plan = self.root / 'plan.json'
        plan.write_text(json.dumps({'name': 'compatibility-proof', 'tasks': [task or self.task]}), encoding='utf-8')
        return ws.init_run(plan, self.root / 'runs', {}, target_surface='codex-workflow')

    def upgrade(self):
        archive = self.selector.parent / 'selector-history' / (self.old_hash + '.py')
        archive.parent.mkdir(exist_ok=True)
        archive.write_bytes(self.old)
        self.selector.write_bytes((STAGE / REL / 'scripts/route_selector.py').read_bytes())
        return archive

    def test_explicit_verifier_is_forwarded_and_frozen(self):
        task = copy.deepcopy(self.task)
        task['verifier_plan'] = {'kind': 'artifact-check', 'command': ['fixture-verifier'], 'contract': 'exact fixture'}
        run = self.init(task)
        plan, state = ws.load_run(run)
        self.assertEqual(plan['tasks'][0]['verifier_plan'], task['verifier_plan'])
        self.assertEqual(state['tasks']['work']['decision_receipt']['verifier_plan'], task['verifier_plan'])
        task['verifier_plan']['contract'] = 'caller mutation'
        self.assertNotEqual(plan['tasks'][0]['verifier_plan'], task['verifier_plan'])

    def test_absent_verifier_retains_legacy_none(self):
        run = self.init()
        plan, state = ws.load_run(run)
        self.assertNotIn('verifier_plan', plan['tasks'][0])
        self.assertEqual(state['tasks']['work']['decision_receipt']['verifier_plan'], {'kind': 'none'})

    def test_existing_pin_survives_installed_upgrade_and_catalog_movement(self):
        run = self.init()
        before = ws.task_model(run, 'work')
        original_receipt = ws.load_run(run)[1]['tasks']['work']['decision_receipt']
        self.upgrade()
        changed = json.loads(self.catalog.read_bytes())
        changed['catalog_version'] = 'future-catalog'
        self.catalog.write_text(json.dumps(changed), encoding='utf-8')
        self.assertEqual(ws.task_model(run, 'work'), before)
        self.assertEqual(ws.load_run(run)[1]['tasks']['work']['decision_receipt'], original_receipt)

    def test_mutated_admitted_archive_is_rejected(self):
        run = self.init()
        archive = self.upgrade()
        archive.write_bytes(self.old + b'\n# mutated\n')
        with self.assertRaisesRegex(ws.PlanError, 'historical selector identity changed'):
            ws.task_model(run, 'work')

    def test_missing_archive_does_not_execute_run_snapshot(self):
        run = self.init()
        self.selector.write_bytes((STAGE / REL / 'scripts/route_selector.py').read_bytes())
        with self.assertRaisesRegex(ws.PlanError, 'not admitted'):
            ws.task_model(run, 'work')

    def test_changed_run_selector_does_not_execute(self):
        run = self.init()
        self.upgrade()
        pinned = run / 'route_selector.py'
        pinned.write_bytes(pinned.read_bytes() + b'\nraise AssertionError("untrusted")\n')
        with self.assertRaisesRegex(ws.PlanError, 'Pinned route selector changed'):
            ws.task_model(run, 'work')

    def test_unsupported_v3_request_cannot_be_ignored(self):
        task = copy.deepcopy(self.task)
        task.pop('intelligence_tier')
        task.pop('latency_sensitive')
        task['route_request'] = {'schema_version': 3}
        with self.assertRaisesRegex(ws.PlanError, 'route_request must contain exactly'):
            self.init(task)

    def test_wrong_verifier_shape_is_rejected(self):
        task = copy.deepcopy(self.task)
        task['verifier_plan'] = 'not a verifier object'
        with self.assertRaisesRegex(ws.PlanError, 'requires a routed task and an object'):
            self.init(task)

if __name__ == '__main__':
    unittest.main(verbosity=2)
