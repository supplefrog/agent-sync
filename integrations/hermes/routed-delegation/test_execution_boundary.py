import types,unittest
from unittest import mock
from test_v3 import load_plugin

class ExecutionBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.plugin=load_plugin()
        names=['read_file','write_file','terminal']
        self.child=types.SimpleNamespace(tools=[{'function':{'name':n}} for n in names],valid_tool_names=set(names),_build_api_kwargs=mock.Mock(return_value={'tools':[{'type':'function','name':n,'description':'','strict':False,'parameters':{'type':'object','properties':{}}} for n in names]}))
        self.child._get_transport=lambda:types.SimpleNamespace(_last_wire_aliases={})
        self.pin={'request':{'requirements':{'tools':names},'budget':{'execution_request':{'authorized':True,'max_requests':2}}}}
    def test_preserves_full_tools_and_caps_requests(self):
        original=self.child.tools.copy()
        with mock.patch.object(self.plugin,'_validate_v3_child'):
            self.plugin._guard_v3_child(self.child,{},self.pin)
            self.assertEqual(self.child.tools,original)
            self.child._build_api_kwargs();self.child._build_api_kwargs()
            with self.assertRaisesRegex(RuntimeError,'request cap'):self.child._build_api_kwargs()
    def test_cannot_narrow_or_invent_tools(self):
        self.pin['request']['requirements']['tools']=['read_file']
        with mock.patch.object(self.plugin,'_validate_v3_child'),self.assertRaisesRegex(RuntimeError,'inherited native tools'):
            self.plugin._guard_v3_child(self.child,{},self.pin)
    def test_conflicting_lane_or_missing_authorization_rejected(self):
        self.pin['request']['budget']['execution_request']['authorized']=False
        with self.assertRaisesRegex(RuntimeError,'authorization'):self.plugin._guard_v3_child(self.child,{},self.pin)
        self.pin['request']['budget']['evidence_trial']={}
        with self.assertRaisesRegex(RuntimeError,'mutually exclusive'):self.plugin._guard_v3_child(self.child,{},self.pin)
    def test_schema_drift_rejected(self):
        with mock.patch.object(self.plugin,'_validate_v3_child'):
            builder=self.child._build_api_kwargs
            self.plugin._guard_v3_child(self.child,{},self.pin)
            builder.return_value['tools'][1]['parameters']={'type':'object','properties':{'new':{'type':'string'}}}
            with self.assertRaisesRegex(RuntimeError,'schema'):self.child._build_api_kwargs()
    def native_builder(self):
        from agent.codex_responses_adapter import _responses_tools
        from agent.transports.codex import _alias_wire_tools
        emitted, aliases=_alias_wire_tools(_responses_tools(self.child.tools),
            {'provider':'openai-codex','base_url':'https://chatgpt.com/backend-api/codex','is_codex_backend':True},
            is_xai_responses=False,is_codex_backend=True)
        self.transport._last_wire_aliases=aliases
        return {'tools':emitted}
    def test_native_alias_projection_preserves_tools_and_strict_schema(self):
        self.child.provider='openai-codex';self.child.base_url='https://chatgpt.com/backend-api/codex'
        self.transport=types.SimpleNamespace(_last_wire_aliases={})
        self.child._get_transport=lambda:self.transport
        for name in ['tool_search','hermes_tool_search','tool_describe','tool_call']:
            self.child.tools.append({'function':{'name':name,'strict':True}})
            self.child.valid_tool_names.add(name)
        self.pin['request']['requirements']['tools']=sorted(self.child.valid_tool_names)
        self.child._build_api_kwargs=self.native_builder
        with mock.patch.object(self.plugin,'_validate_v3_child'):
            self.plugin._guard_v3_child(self.child,{},self.pin)
            result=self.child._build_api_kwargs()
            self.assertEqual(self.child.valid_tool_names,set(self.pin['request']['requirements']['tools']))
            self.assertIn('tool_search',self.transport._last_wire_aliases.values())
            self.assertEqual(len(result['tools']),len(self.child.tools))
            self.assertTrue(next(t for t in result['tools'] if t['name']=='tool_call')['strict'])
    def test_wrong_native_alias_map_rejected(self):
        self.transport=types.SimpleNamespace(_last_wire_aliases={'wrong':'terminal'})
        self.child._get_transport=lambda:self.transport
        with mock.patch.object(self.plugin,'_validate_v3_child'):
            self.plugin._guard_v3_child(self.child,{},self.pin)
            with self.assertRaisesRegex(RuntimeError,'aliases'):self.child._build_api_kwargs()

if __name__=='__main__':unittest.main()
