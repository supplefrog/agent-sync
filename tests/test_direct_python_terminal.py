"""Task-local backend mechanics; no native agent, auth or denied-path probe."""
from fixture_workspace import configure
configure()
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from types import ModuleType, SimpleNamespace
from unittest import mock
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
import evaluation_hermes_worker as worker


class DirectTerminalTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name).resolve()

    def call(self, command, **kwargs):
        return json.loads(worker.direct_python_terminal({'command':command, **kwargs}, self.root, 30))

    def test_real_stdlib_test_failure_then_success_without_shell(self):
        source=self.root/'test_program.py'
        source.write_text('import unittest\nclass Check(unittest.TestCase):\n def test_value(self): self.assertEqual(1,2)\n')
        bad=self.call('python -m unittest -v')
        self.assertEqual(bad['exit_code'],1);self.assertFalse(bad['success'])
        source.write_text(source.read_text().replace('1,2','2,2'))
        good=self.call('python -m unittest -v')
        self.assertEqual(good['exit_code'],0);self.assertTrue(good['success'])
        self.assertIn('Ran 1 test',good['output'])
        self.assertEqual(good['backend'],'direct-python-argv')

    def test_existing_guard_and_bounded_argv_environment_are_preserved(self):
        for command,options in [('python -c print(1)',{}),('python -m unittest;whoami',{}),
                                ('python -m unittest',{'background':True}),('ls ../',{}),
                                ('python -m pytest --basetemp=/outside',{})]:
            with self.subTest(command=command),mock.patch.object(worker.subprocess,'run',side_effect=AssertionError('denied command launched')):
                self.assertFalse(self.call(command,**options)['success'])
        completed=type('Result',(),{'stdout':'ok','stderr':'','returncode':0})()
        with mock.patch.dict(os.environ,{'API_KEY':'MUST_NOT_PASS','OPENAI_API_KEY':'MUST_NOT_PASS'}),mock.patch.object(worker.subprocess,'run',return_value=completed) as run:
            self.assertTrue(self.call('python -m unittest -v')['success'])
        self.assertEqual(run.call_args.args[0],[sys.executable,'-B','-m','unittest','-v'])
        self.assertFalse(run.call_args.kwargs['shell'])
        self.assertNotIn('OPENAI_API_KEY',run.call_args.kwargs['env'])
        self.assertEqual(run.call_args.kwargs['cwd'],self.root)

    def test_workdir_listing_and_timeout_are_bounded(self):
        child=self.root/'tests';child.mkdir();(child/'sample.py').write_text('value=1')
        self.assertEqual(self.call('pwd',workdir='tests')['output'],str(child))
        self.assertEqual(self.call('ls',workdir='tests')['output'],'sample.py')
        with mock.patch.object(worker.subprocess,'run',side_effect=AssertionError('unbounded timeout launched')):
            self.assertFalse(self.call('python -m unittest',timeout=999)['success'])
            self.assertFalse(self.call('python -m unittest',timeout=True)['success'])

    def test_direct_config_disables_only_disposable_bash_probe_and_retains_no_install(self):
        with mock.patch.dict(os.environ,{'HERMES_DISABLE_LAZY_INSTALLS':'1'}):
            worker.prepare_study_config(str(self.root),direct_backend=True)
        config=json.loads((self.root/'config.yaml').read_bytes())
        self.assertIs(config['agent']['environment_probe'],False)
        worker.verify_no_install_config(config)

    def test_registered_handler_preserves_native_guard_refusal_and_registration_readback(self):
        calls=[]
        class Rejected(Exception):
            result_json='{"success":false,"error":"native refusal"}'
        registry=SimpleNamespace()
        def register(**kwargs): registry.entry=SimpleNamespace(**kwargs)
        registry.register=register;registry.get_entry=lambda _name:registry.entry
        terminal=ModuleType('tools.terminal_tool');terminal._Rejected=Rejected
        terminal.TERMINAL_SCHEMA={'name':'terminal','parameters':{'type':'object',
            'properties':{'timeout':{'type':'integer','description':'Default 180; foreground max 600','minimum':1}}}}
        terminal._get_env_config=lambda:{'env_type':'local'}
        terminal._pre_exec_block=lambda *args,**kw:calls.append('native lifecycle/workdir guard')
        terminal._run_approval_guards=lambda *args,**kw:calls.append(('native approval',kw['force']))
        registry_module=ModuleType('tools.registry');registry_module.registry=registry;registry_module.__file__=__file__
        tools=ModuleType('tools');tools.__path__=[];tools.terminal_tool=terminal
        scope=ModuleType('tools.terminal_scope');scope.enforce_no_refusal=lambda:calls.append('native scope')
        approval=ModuleType('agent.terminal_approval_batch');approval.validate_prepared_terminal=lambda args:calls.append('prepared arguments')
        deadline=ModuleType('agent.deadline')
        def bounded(fn,*args,**kw):fn();return SimpleNamespace(timed_out=False)
        deadline.run_bounded_sync=bounded
        modules={'tools':tools,'tools.terminal_tool':terminal,'tools.registry':registry_module,
                 'tools.terminal_scope':scope,'agent.terminal_approval_batch':approval,'agent.deadline':deadline}
        with mock.patch.dict(sys.modules,modules),mock.patch.object(worker,'direct_python_terminal',return_value='{"success":true}') as execute:
            metadata,verify=worker.install_direct_terminal({'fixture':str(self.root),'timeout':30})
            timeout_schema=registry.entry.schema['parameters']['properties']['timeout']
            self.assertEqual((timeout_schema['default'],timeout_schema['maximum']),(30,30))
            self.assertIn('default 30',timeout_schema['description'])
            self.assertNotIn('180',timeout_schema['description'])
            self.assertNotIn('maximum',terminal.TERMINAL_SCHEMA['parameters']['properties']['timeout'])
            self.assertTrue(json.loads(registry.entry.handler({'command':'python -m unittest'}))['success'])
            self.assertEqual(calls,['native scope','prepared arguments','native lifecycle/workdir guard',('native approval',False)])
            execute.assert_called_once();execute.reset_mock()
            scope.enforce_no_refusal=mock.Mock(side_effect=RuntimeError('scope unavailable'))
            self.assertFalse(json.loads(registry.entry.handler({'command':'python -m unittest'}))['success'])
            execute.assert_not_called()
            registry.entry=SimpleNamespace(handler=None)
            with self.assertRaises(RuntimeError):verify()
            self.assertEqual(metadata['name'],'direct-python-argv')

    def test_registered_default_and_explicit_session_boundary_match_advertisement(self):
        registry=SimpleNamespace()
        registry.register=lambda **kw:setattr(registry,'entry',SimpleNamespace(**kw))
        registry.get_entry=lambda name:registry.entry
        terminal=ModuleType('tools.terminal_tool')
        terminal.TERMINAL_SCHEMA={'name':'terminal','parameters':{'type':'object','properties':{
            'timeout':{'type':'integer','description':'Default 180; foreground max 600','minimum':1}}}}
        terminal._Rejected=type('Rejected',(Exception,),{})
        terminal._get_env_config=lambda:{'env_type':'local'}
        terminal._pre_exec_block=mock.Mock()
        terminal._run_approval_guards=mock.Mock()
        tools=ModuleType('tools');tools.__path__=[];tools.terminal_tool=terminal
        registry_module=ModuleType('tools.registry');registry_module.registry=registry;registry_module.__file__=__file__
        scope=ModuleType('tools.terminal_scope');scope.enforce_no_refusal=mock.Mock()
        approval=ModuleType('agent.terminal_approval_batch');approval.validate_prepared_terminal=mock.Mock()
        deadline=ModuleType('agent.deadline')
        def bounded(fn,*args,**kwargs):fn();return SimpleNamespace(timed_out=False)
        deadline.run_bounded_sync=bounded
        modules={'tools':tools,'tools.terminal_tool':terminal,'tools.registry':registry_module,
                 'tools.terminal_scope':scope,'agent.terminal_approval_batch':approval,'agent.deadline':deadline}
        with mock.patch.dict(sys.modules,modules),mock.patch.object(worker.time,'monotonic',return_value=10), \
             mock.patch.object(worker,'direct_python_terminal',return_value='{"success":true}') as execute:
            worker.install_direct_terminal({'fixture':str(self.root),'timeout':150})
            handler=registry.entry.handler
            for args in ({'command':'python -m unittest'}, {'command':'python -m unittest','timeout':150}):
                self.assertTrue(json.loads(handler(args))['success'])
                self.assertEqual(execute.call_args.args[0]['timeout'],150)
            for timeout in (151,180,0,True):
                execute.reset_mock()
                rejected=json.loads(handler({'command':'python -m unittest','timeout':timeout}))
                self.assertEqual(rejected['error'],'Invalid bounded timeout')
                execute.assert_not_called()
            self.assertEqual(terminal._run_approval_guards.call_count,2)
            self.assertTrue(all(call.kwargs['force'] is False for call in terminal._run_approval_guards.call_args_list))


if __name__=='__main__':unittest.main()
