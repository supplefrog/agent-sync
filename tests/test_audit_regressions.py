"""Regressions exposed by the independent Astra surface audit."""
from __future__ import annotations
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def load(name, file):
    spec=importlib.util.spec_from_file_location(name,ROOT/'tools'/file)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

class AuditRegressions(unittest.TestCase):
    def test_string_false_is_invalid_judgment(self):
        evaluator=load('audit_evaluator','eval.py')
        judgment={'a':{'hard_pass':'false','reason':'failed'},'b':{'hard_pass':True,'reason':'passed'},'winner':'B','reason':'B passes'}
        with self.assertRaises(ValueError):
            evaluator.map_judgment(judgment,['baseline','candidate'])

    def test_unknown_winner_is_invalid_not_a_tie(self):
        evaluator=load('audit_evaluator','eval.py')
        judgment={'a':{'hard_pass':True,'reason':'passed'},'b':{'hard_pass':True,'reason':'passed'},'winner':'C','reason':'unsupported label'}
        with self.assertRaises(ValueError):
            evaluator.map_judgment(judgment,['baseline','candidate'])

    def test_shipped_script_changes_capability_identity(self):
        artifacts=load('audit_artifacts','artifact_hash.py')
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            candidate=root/'SKILL.md'
            candidate.write_text('Run `scripts/worker.py`.',encoding='utf-8')
            script=root/'scripts'/'worker.py'
            script.parent.mkdir()
            script.write_text('print("correct")',encoding='utf-8')
            before=artifacts.candidate_hash(candidate)
            script.write_text('print("incorrect")',encoding='utf-8')
            after=artifacts.candidate_hash(candidate)
            self.assertNotEqual(before,after)

    def test_aggregate_rejects_self_declared_success_without_evidence(self):
        gate=load('audit_gate','eval_gate.py')
        report={'agent':'codex','decision':{'decision':'admit'},'effective_stack':{'equivalence_group':'claimed'}}
        result=gate.aggregate([report],['codex'],'admission','restore',{'codex':'a'*64})
        self.assertEqual(result['decision'],'inconclusive')

    def test_changing_loader_invalidates_harness_identity(self):
        artifacts=load('audit_artifacts','artifact_hash.py')
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for name in ('eval.py','artifact_hash.py','evaluation_runtime.py','evaluation_hermes_worker.py','fleet.py'):
                (root/name).write_text('# original',encoding='utf-8')
            before=artifacts.harness_hash(root/'eval.py')
            (root/'artifact_hash.py').write_text('# changed loader',encoding='utf-8')
            self.assertNotEqual(before,artifacts.harness_hash(root/'eval.py'))

if __name__=='__main__':
    unittest.main()
