"""Native evidence boundary, not only a selector declaration."""
import types
import unittest
from unittest import mock
from test_v3 import load_plugin

class EvidenceBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.plugin = load_plugin()
        self.child = types.SimpleNamespace(
            tools=[{'function': {'name': name}} for name in ['read_file', 'search_files', 'terminal', 'write_file']],
            valid_tool_names={'read_file', 'search_files', 'terminal', 'write_file'},
            _build_api_kwargs=mock.Mock(return_value={'tools': [
                {'type':'function','name':name, 'description':'', 'strict':False,
                 'parameters':{'type':'object','properties':{}}}
                for name in ['read_file','search_files']]}),
        )
        self.pin = {'request': {'requirements': {'tools': ['read_file', 'search_files']},
                    'budget': {'evidence_trial': {'authorized': True, 'max_requests': 2}}}}

    def test_narrows_actual_tools_and_enforces_request_cap(self):
        with mock.patch.object(self.plugin, '_validate_v3_child'):
            original = self.child._build_api_kwargs
            self.plugin._guard_v3_child(self.child, {}, self.pin)
            self.assertEqual(self.child.valid_tool_names, {'read_file', 'search_files'})
            self.assertEqual({t['function']['name'] for t in self.child.tools}, self.child.valid_tool_names)
            self.child._build_api_kwargs()
            self.child._build_api_kwargs()
            with self.assertRaisesRegex(RuntimeError, 'request cap'):
                self.child._build_api_kwargs()
            self.assertEqual(original.call_count, 2)

    def test_compatibility_probe_precedes_execution_request_budget(self):
        self.child.provider = 'openai-codex'
        self.child.api_mode = 'codex_responses'
        self.child.base_url = 'https://chatgpt.com/backend-api/codex'
        builder = self.child._build_api_kwargs
        builder.return_value.update(model='gpt-test', reasoning={'effort':'medium'})
        route = {'provider':'openai-codex','model':'gpt-test','reasoning_effort':'medium'}
        with mock.patch.object(self.plugin, '_validate_v3_child'), mock.patch.object(self.plugin, '_assert_exact_child_route'):
            self.plugin._install_exact_request_guard(self.child, route)
            self.assertEqual(builder.call_count, 1)  # compatibility only; no transport
            self.plugin._guard_v3_child(self.child, {}, self.pin)
            self.child._build_api_kwargs()
            self.child._build_api_kwargs()
            with self.assertRaisesRegex(RuntimeError, 'request cap'):
                self.child._build_api_kwargs()
            self.assertEqual(builder.call_count, 3)

    def test_same_name_parameter_drift_is_rejected(self):
        self.child._build_api_kwargs.return_value['tools'][0]['parameters'] = {
            'type': 'object', 'properties': {'command': {'type': 'string'}}}
        with mock.patch.object(self.plugin, '_validate_v3_child'):
            self.plugin._guard_v3_child(self.child, {}, self.pin)
            with self.assertRaisesRegex(RuntimeError, 'schema'):
                self.child._build_api_kwargs()

    def test_child_schema_mutation_is_rejected(self):
        with mock.patch.object(self.plugin, '_validate_v3_child'):
            self.plugin._guard_v3_child(self.child, {}, self.pin)
            self.child.tools[0]['function']['description'] = 'Changed after freezing'
            with self.assertRaisesRegex(RuntimeError, 'schema'):
                self.child._build_api_kwargs()

    def test_emitted_tool_drift_is_rejected(self):
        self.child._build_api_kwargs.return_value = {'tools': [{'type':'function','name':'terminal'}]}
        with mock.patch.object(self.plugin, '_validate_v3_child'):
            self.plugin._guard_v3_child(self.child, {}, self.pin)
            with self.assertRaisesRegex(RuntimeError, 'emitted'):
                self.child._build_api_kwargs()

    def test_tool_override_is_rejected(self):
        self.child._build_api_kwargs.return_value = {'tools': [], 'extra_body': {'tools': []}}
        with mock.patch.object(self.plugin, '_validate_v3_child'):
            self.plugin._guard_v3_child(self.child, {}, self.pin)
            with self.assertRaisesRegex(RuntimeError, 'override'):
                self.child._build_api_kwargs()

    def test_does_not_invent_missing_tool(self):
        self.child.tools = []
        self.child.valid_tool_names = set()
        with mock.patch.object(self.plugin, '_validate_v3_child'):
            with self.assertRaisesRegex(RuntimeError, 'unavailable'):
                self.plugin._guard_v3_child(self.child, {}, self.pin)

    def test_does_not_authorize_shell_as_read_only(self):
        self.pin['request']['requirements']['tools'] = ['terminal']
        with mock.patch.object(self.plugin, '_validate_v3_child'):
            with self.assertRaisesRegex(RuntimeError, 'read-only'):
                self.plugin._guard_v3_child(self.child, {}, self.pin)

class LcmCapacityTests(unittest.TestCase):
    def setUp(self):
        from test_v3 import NativeBindingTests
        NativeBindingTests.setUp(self)
        self.child.model = 'gpt-test'
        self.child.provider = 'openai-codex'
        self.child.base_url = ''
        self.child.context_compressor = types.SimpleNamespace(context_length=0, name='lcm')

    def test_auxiliary_lcm_zero_uses_native_metadata(self):
        module = types.ModuleType('agent.model_metadata')
        module.get_model_context_length = mock.Mock(return_value=4096)
        with mock.patch.dict('sys.modules', {'agent.model_metadata': module}):
            self.plugin._validate_v3_child(self.child, self.task, self.pin)
            module.get_model_context_length.assert_called_once()

    def test_low_or_unknown_native_capacity_still_rejected(self):
        module = types.ModuleType('agent.model_metadata')
        for capacity in (0, 127, None):
            module.get_model_context_length = mock.Mock(return_value=capacity)
            with self.subTest(capacity=capacity), mock.patch.dict('sys.modules', {'agent.model_metadata': module}):
                with self.assertRaisesRegex(RuntimeError, 'context capacity'):
                    self.plugin._validate_v3_child(self.child, self.task, self.pin)

    def test_positive_lcm_limit_is_not_overridden(self):
        self.child.context_compressor.context_length = 127
        with self.assertRaisesRegex(RuntimeError, 'context capacity'):
            self.plugin._validate_v3_child(self.child, self.task, self.pin)

if __name__ == '__main__':
    unittest.main()
