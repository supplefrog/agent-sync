"""Prepared job consistency at the real pilot CLI dispatch boundary, offline."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import evaluation_artifact_pilot as pilot


class PlanBoundary(unittest.TestCase):
    def prepare(self, root):
        fixture = root / 'fixture'
        fixture.mkdir()
        (fixture / 'app.txt').write_text('original')
        guide = root / 'guide.md'
        guide.write_text('Exercise the artifact.')
        oracle = root / 'oracle.py'
        oracle.write_text('raise SystemExit(0)')
        spec = {'purpose': 'runtime-smoke', 'arms': [{'id': 'a', 'instructions': str(guide)}],
                'cases': [{'id': 'c', 'fixture': str(fixture), 'prompt': 'Repair the artifact.'}],
                'max_workers': 1, 'max_iterations': 4, 'timeout': 30, 'quota_remaining': 10,
                'workspace_root': str(root / 'work'), 'oracle': str(oracle)}
        suite = root / 'suite.json'
        suite.write_text(json.dumps(spec))
        out = root / 'out'
        pilot.main(['prepare', '--suite', str(suite), '--out', str(out)])
        return out, json.loads((out / 'plan.json').read_text())

    def test_inconsistent_jobs_rejected_before_runtime_discovery(self):
        for mutation in ('extra', 'missing', 'arm', 'case', 'prompt', 'instructions', 'fixture', 'tree'):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as directory:
                out, plan = self.prepare(Path(directory))
                job = plan['jobs'][0]
                if mutation == 'extra':
                    plan['jobs'].append(copy.deepcopy(job))
                elif mutation == 'missing':
                    plan['jobs'].clear()
                elif mutation == 'tree':
                    Path(job['fixture'], 'app.txt').write_text('changed')
                else:
                    job[mutation] = 'changed'
                (out / 'plan.json').write_text(json.dumps(plan))
                with patch.object(pilot, 'native_executable', side_effect=AssertionError('runtime reached')) as native:
                    with self.assertRaisesRegex(ValueError, 'Prepared'):
                        pilot.main(['run', '--out', str(out)])
                    native.assert_not_called()

    def test_valid_prepared_plan_reaches_runtime_boundary(self):
        with tempfile.TemporaryDirectory() as directory:
            out, _ = self.prepare(Path(directory))
            with patch.object(pilot, 'native_executable', side_effect=RuntimeError('offline boundary')) as native:
                with self.assertRaisesRegex(RuntimeError, 'offline boundary'):
                    pilot.main(['run', '--out', str(out)])
                native.assert_called_once()


if __name__ == '__main__':
    unittest.main()
