import importlib.util,json,hashlib,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('schema_history_workflow',ROOT/'skills/dynamic-workflows/scripts/workflow_state.py')
workflow=importlib.util.module_from_spec(spec)
spec.loader.exec_module(workflow)

class SchemaHistoryTests(unittest.TestCase):
    def test_raw_historical_schema_is_admitted_and_tampering_refused(self):
        current=ROOT/'skills/openai-delegation-route-research/references/route-task-v3.schema.json'
        historical=next((current.parent/'schema-history').glob('*.json'))
        raw=historical.read_bytes(); identity=hashlib.sha256(raw).hexdigest()
        self.assertEqual(workflow._admitted_source(identity,current,'schema-history','schema')[0],raw)
        with tempfile.TemporaryDirectory() as name:
            fake=Path(name)/'schema.json';fake.write_bytes(b'{}')
            history=fake.parent/'schema-history';history.mkdir();(history/(identity+'.json')).write_bytes(b'{}')
            with self.assertRaises(workflow.PlanError):workflow._admitted_source(identity,fake,'schema-history','schema')
    def test_historical_validator_remains_exact(self):
        skill=ROOT/'skills/openai-delegation-route-research'
        old=next((skill/'references/schema-history').glob('*.json')).read_bytes()
        materializer=skill/'scripts/task_request.py'
        module=workflow.load_task_materializer_bytes(materializer.read_bytes(),materializer,old)
        self.assertEqual(module._VALIDATOR.schema,json.loads(old))
        self.assertNotIn('execution_request',module._VALIDATOR.schema['properties']['budget']['properties'])

if __name__=='__main__':unittest.main()
