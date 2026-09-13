"""Production entry-point failure controls, with only native boundaries faked."""
import contextlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
import evaluation_artifact_worker as worker


class WorkerFailures(unittest.TestCase):
    def exercise(self, *, leak=False, close_error=False):
        sentinel='SYNTHETIC-CREDENTIAL-CANARY-NOT-A-REAL-TOKEN'
        class Agent:
            session_id='synthetic-parent'
            _delegate_role='leaf'
            valid_tool_names=['terminal']
            def close(self):
                if close_error:raise OSError('synthetic close failure')
        parent,child=Agent(),Agent()
        route={'model':'model'}
        pin={'dispatch':{'kind':'model','route':route},'decision':{'outcome':'selected_model','route':route}}
        plugin=types.SimpleNamespace(
            _private_runtime=lambda:{'build':None,'validate_request':None,'budget_summary':None,'run':None,'list_active':lambda:[]},
            _v3_native_envelope=lambda *args:{}, _select_or_reuse_v3=lambda *args:pin,
            _prepare_child=lambda *args,**kwargs:child, _guard_v3_child=lambda *args:None,
            _sha=lambda value:'0'*64,
            _run_exact_child=lambda *args:{'status':'completed','exit_reason':'completed','summary':sentinel if leak else 'done'})
        constants=types.ModuleType('hermes_constants');constants.set_hermes_home_override=lambda *args:None
        auth=types.ModuleType('hermes_cli.auth_codex');auth.resolve_codex_runtime_credentials=lambda **kwargs:{'base_url':'https://chatgpt.com/backend-api/codex','api_key':sentinel}
        run_agent=types.ModuleType('run_agent');run_agent.AIAgent=lambda **kwargs:parent
        prompt=types.ModuleType('agent.system_prompt');prompt.build_system_prompt=lambda *args:'synthetic safe prompt'
        modules={'hermes_constants':constants,'hermes_cli.auth_codex':auth,'run_agent':run_agent,'agent.system_prompt':prompt}
        previous=Path.cwd();oldpath=list(sys.path)
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);fixture=root/'project';fixture.mkdir();out=root/'result.json'
            job={'output':str(out),'fixture':str(fixture),'native_source':str(root),
                 'credential_owner_home':str(root),'model':'model','reasoning':'medium',
                 'max_iterations':1,'timeout':10,'source':str(root),'id':'one','prompt':'Do the task.',
                 'instructions':'','route_request':{}}
            try:
                with patch.dict(sys.modules,modules),patch.dict(os.environ,{'HERMES_HOME':str(root)}),patch.object(worker,'load',return_value=plugin),patch.object(sys,'stdin',io.StringIO(json.dumps(job))),contextlib.redirect_stdout(io.StringIO()):
                    code=worker.main()
                return code,out.read_text(),sentinel
            finally:
                os.chdir(previous);sys.path[:]=oldpath

    def test_detected_secret_is_not_preserved_in_failure_report(self):
        code,text,sentinel=self.exercise(leak=True)
        self.assertEqual(code,1)
        self.assertNotIn(sentinel,text)

    def test_close_failure_still_writes_a_failed_durable_report(self):
        code,text,_=self.exercise(close_error=True)
        self.assertEqual(code,1)
        self.assertFalse(json.loads(text)['ok'])
        self.assertTrue(json.loads(text)['cleanup_errors'])


if __name__=='__main__':unittest.main()
