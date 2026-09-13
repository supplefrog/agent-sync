"""Offline gates for the bounded artifact execution lane."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import subprocess

TOOLS = Path(__file__).resolve().parents[1] / 'tools'
sys.path.insert(0, str(TOOLS))
import evaluation_artifact_pilot as pilot
from evaluation_artifact_worker import require_model


class ArtifactPilot(unittest.TestCase):
    def test_success_exit_does_not_accept_invalid_oracle_output(self):
        for output in ('not-json', '{}', '{"passed":0,"failed":0,"failures":[]}',
                       '{"passed":1,"failed":1,"failures":["defect"]}'):
            with self.subTest(output=output), tempfile.TemporaryDirectory() as directory:
                root=Path(directory); fixture=root/'fixture';fixture.mkdir()
                (fixture/'app.py').write_text('print(1)')
                (root/'guide.md').write_text('Exercise the app.')
                (root/'oracle.py').write_text('print(1)')
                spec={**self.spec(),'arms':[{'id':'one','instructions':str(root/'guide.md')}],
                    'cases':[{'id':'case','fixture':str(fixture),'prompt':'Fix the app.'}],
                    'oracle':str(root/'oracle.py'),'workspace_root':str(root/'projects'),
                    'model':'model','reasoning':'medium','protocol':'synthetic','route_id':'route'}
                out=root/'results';plan=pilot.prepare(spec,out)
                self.assertEqual(plan['kind'],'runtime-smoke')
                self.assertFalse(plan['workflow_comparison_supported'])
                plan['kind']='workflow-comparison'
                def boundary(command, **kwargs):
                    if 'input' in kwargs:
                        job=json.loads(kwargs['input'])
                        Path(job['output']).write_text(json.dumps({'ok':True,'native':{},
                            'routing':{'decision':{'outcome':'selected_model'}}}))
                        return subprocess.CompletedProcess(command,0,'','')
                    return subprocess.CompletedProcess(command,0,output,'')
                with patch.object(pilot,'native_hermes_runtime',return_value=(Path(sys.executable),root)), \
                     patch.object(pilot,'native_executable',return_value='synthetic'), \
                     patch.object(pilot.subprocess,'run',side_effect=boundary):
                    result=pilot.run(plan,out)
                self.assertFalse(result['results'][0]['ok'])
                self.assertEqual(result['kind'],'runtime-smoke')
                self.assertFalse(result['workflow_comparison_supported'])

    def spec(self):
        return {'arms':[{'id':'one'}], 'cases':[{'id':'case'}], 'max_workers':1,
                'max_iterations':4, 'timeout':30, 'quota_remaining':10,
                'purpose':'runtime-smoke'}

    def test_scope_required_before_prepare_or_launch(self):
        for purpose in (None, 'workflow-comparison', 'architecture-comparison', ''):
            with self.subTest(purpose=purpose), tempfile.TemporaryDirectory() as directory:
                spec=self.spec();spec['purpose']=purpose
                out=Path(directory)/'uncreated'
                with self.assertRaisesRegex(ValueError, 'purpose'):
                    pilot.validate(spec)
                with self.assertRaisesRegex(ValueError, 'purpose'):
                    pilot.prepare(spec,out)
                self.assertFalse(out.exists())
                with patch.object(pilot.subprocess,'run') as launch:
                    with self.assertRaisesRegex(ValueError, 'purpose'):
                        pilot.run({'spec':spec},out)
                    launch.assert_not_called()

    def test_smoke_does_not_fan_out_a_comparison(self):
        spec=self.spec();spec['arms'].append({'id':'other'})
        with self.assertRaisesRegex(ValueError, 'one trial'):
            pilot.validate(spec)

    def test_explicit_injected_study_is_still_supported(self):
        spec=self.spec();spec['purpose']='injected-instruction-study'
        spec['arms'].append({'id':'other'})
        pilot.validate(spec)

    def test_bounded_input(self):
        pilot.validate(self.spec())
        for key,value in [('max_workers',4),('max_iterations',65),('timeout',601),('quota_remaining',0),('quota_remaining',None)]:
            with self.subTest(key=key):
                spec=self.spec();spec[key]=value
                with self.assertRaises(ValueError):pilot.validate(spec)
        spec=self.spec();spec['cases']=[{'id':str(i)} for i in range(13)]
        with self.assertRaises(ValueError):pilot.validate(spec)

    def test_nonmodel_never_passes_launch_gate(self):
        for kind,outcome in [('parent','keep_parent'),('defer','defer'),('deterministic','execute_deterministic')]:
            with self.subTest(kind=kind):
                with self.assertRaises(ValueError):
                    require_model({'dispatch':{'kind':kind},'decision':{'outcome':outcome}})

    def test_exact_route_required(self):
        pin={'dispatch':{'kind':'model','route':{'model':'one'}},
             'decision':{'outcome':'selected_model','route':{'model':'one'}}}
        self.assertEqual(require_model(pin),pin['decision'])
        pin['dispatch']['route']['model']='two'
        with self.assertRaises(ValueError):require_model(pin)

    def test_freeze_refuses_implicit_reprepare_and_oracle_drift(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); fixture=root/'fixture';fixture.mkdir()
            (fixture/'app.py').write_text('print(1)')
            (root/'guide.md').write_text('Exercise the app.')
            (root/'oracle.py').write_text('print(1)')
            spec={**self.spec(),'arms':[{'id':'one','instructions':str(root/'guide.md')}],
                'cases':[{'id':'case','fixture':str(fixture),'prompt':'Fix the app.'}],
                'oracle':str(root/'oracle.py'),'workspace_root':str(root/'projects')}
            out=root/'results';plan=pilot.prepare(spec,out)
            self.assertEqual(len(plan['jobs']),1)
            with self.assertRaises(ValueError):pilot.prepare(spec,out)
            (root/'oracle.py').write_text('print(2)')
            with self.assertRaisesRegex(ValueError,'Frozen oracle changed'):pilot.run(plan,out)


if __name__ == '__main__':
    unittest.main()
