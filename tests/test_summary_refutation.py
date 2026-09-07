import hashlib,importlib.util,json,tempfile,unittest
from pathlib import Path
from unittest import mock
ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location('refuted_summary',ROOT/'tools'/'summarize_eval.py')
summarizer=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(summarizer)

def historical_report():
    return {'suite':'historical','agent':'codex','agent_version':'codex-cli 0.1','timestamp_utc':'then',
            'artifacts':{key:'a'*64 for key in ('candidate_sha256','suite_sha256','harness_sha256')},
            'summary':{'candidate_hard_failures':1},'results':[],
            'decision':{'decision':'reject','reason':'candidate failure'},
            'effective_stack':{'runtime_lane':'inline-text-no-tools-v1'},
            'input_snapshot':{'candidate':{'projection':'inline-linked-text-only'}},
            'suite_case_ids':['one','two'],'selected_case_ids':['one']}

class SummaryRefutationTests(unittest.TestCase):
    def current_summary(self, root, **kwargs):
        from test_evaluation_evidence import make_evaluation
        fixture=make_evaluation(root,**kwargs);out=root/'summary.json'
        rc=summarizer.main([str(fixture['report_path']),'--candidate',str(fixture['candidate_path']),
                           '--suite',str(fixture['suite_path']),'--artifact-policy','current',
                           '--status','verified','--decision','admit','--out',str(out)])
        self.assertEqual(rc,0)
        return json.loads(out.read_text(encoding='utf-8'))

    def test_current_negative_and_positive_are_derived_from_actual_evidence(self):
        for outcome,expected in [('early-failure','reject'),('win','admit')]:
            with self.subTest(outcome=outcome),tempfile.TemporaryDirectory() as temp:
                result=self.current_summary(Path(temp),outcome=outcome)
                self.assertEqual(result['decision'],expected)
                self.assertEqual(result['status'],'evidence-validated')
                self.assertEqual(result['scope']['runtime_lane'],'inline-text-no-tools-v1')
                self.assertFalse(result['scope']['package_behavior_exercised'])
                self.assertEqual(result['positive_decision_sufficient'],expected=='admit')

    def test_current_cleanup_failure_cannot_publish_positive_admission(self):
        with tempfile.TemporaryDirectory() as temp:
            result=self.current_summary(Path(temp),outcome='win',cleanup_failure=True)
            self.assertEqual(result['status'],'operational-failure')
            self.assertEqual(result['decision'],'inconclusive')
            self.assertFalse(result['positive_decision_sufficient'])
            self.assertTrue(result['operational_errors'])

    def test_editorial_words_cannot_relabel_a_recorded_negative_as_admission(self):
        report=historical_report()
        result=summarizer.compact(report,'verified','admit','a'*64,'recorded-hashes-only')
        self.assertNotEqual(result['status'],'verified')
        self.assertNotEqual(result['decision'],'admit')
        self.assertEqual(result['editorial_status'],'verified')
        self.assertEqual(result['recommendation'],'admit')
        self.assertEqual(result['recorded_decision_detail']['decision'],'reject')

    def test_archival_positive_is_a_recorded_claim_and_scope_survives(self):
        report=historical_report();report['decision']['decision']='admit'
        result=summarizer.compact(report,'verified','admit','a'*64,'recorded-hashes-only')
        self.assertIsNone(result['decision'])
        self.assertEqual(result['scope']['runtime_lane'],'inline-text-no-tools-v1')
        self.assertFalse(result['scope']['package_behavior_exercised'])
        self.assertFalse(result['scope']['full_suite'])

    def test_recorded_cli_reads_and_hashes_identical_report_bytes_once(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'raw.json';out=Path(temp)/'summary.json'
            raw=json.dumps(historical_report()).encode();path.write_bytes(raw)
            original=Path.read_bytes;original_text=Path.read_text;reads=[]
            def read_bytes(candidate):
                if candidate==path:
                    reads.append(candidate)
                    return original(candidate)
                return original(candidate)
            def read_text(candidate,*args,**kwargs):
                value=original_text(candidate,*args,**kwargs)
                if candidate==path: path.write_bytes(b'{"different":true}')
                return value
            with mock.patch.object(Path,'read_bytes',read_bytes),mock.patch.object(Path,'read_text',read_text):
                rc=summarizer.main([str(path),'--artifact-policy','recorded','--status','verified','--decision','admit','--out',str(out)])
            self.assertEqual(rc,0)
            result=json.loads(out.read_text(encoding='utf-8'))
            self.assertEqual(result['raw_report_sha256'],hashlib.sha256(raw).hexdigest())
            self.assertEqual(len(reads),1)
            self.assertIsNone(result['decision'])

if __name__=='__main__': unittest.main()
