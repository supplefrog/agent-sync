"""Eligibility units use an immutable baseline double and fake transport.

No Git or other child process is used. Git publication end-to-end checks remain
separate in test_instruction_changes.py, including their environmental blockers.
"""
from fixture_workspace import configure as configure_test_workspace
configure_test_workspace()
import contextlib,copy,hashlib,io,json,shutil,tempfile,unittest,sys
from pathlib import Path
from unittest import mock
REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO/'tools'))
import instruction_changes as changes
import evaluation_runtime as runtime
import sync_git
import artifact_hash
from test_evaluation_evidence import make_evaluation, attribute_fixture_judges

def sha(b):return hashlib.sha256(b).hexdigest()

class InstructionEligibilityUnitTests(unittest.TestCase):
    def setUp(self):
        self.no_children=mock.patch('subprocess.Popen',side_effect=AssertionError('eligibility unit tests must not start child processes'))
        self.no_children.start(); self.addCleanup(self.no_children.stop)
        root=Path(self.enterContext(tempfile.TemporaryDirectory())); self.repo=root/'repo'; self.repo.mkdir()
        fixture=make_evaluation(root/'transport',outcome='win')
        self.report=fixture['report']; self.suite=fixture['suite']
        (self.repo/'tools').mkdir()
        for name in artifact_hash.HARNESS_SOURCES:
            shutil.copyfile(REPO/'tools'/name,self.repo/'tools'/name)
        (self.repo/'contracts').mkdir(); (self.repo/'profiles').mkdir(); (self.repo/'evals/results').mkdir(parents=True)
        (self.repo/'contracts/instruction-surfaces.json').write_text(json.dumps({'schema_version':2,'surfaces':[{'artifact':'candidate.md','owner':'candidate.md'}]}))
        self.profile={'status':'current-observed','target':{'model':'gpt-6-astra','provider':'openai-codex','reasoning':'xhigh'},'hosts':{'codex':{'model':'gpt-6-astra','provider':'openai-codex','reasoning':'xhigh'}}}
        self.save_profile()
        self.old=fixture['baseline_path'].read_bytes(); self.new=fixture['candidate_path'].read_bytes()
        self.target=self.repo/'candidate.md'; self.target.write_bytes(self.old)
        self.base='immutable-unit-baseline'
        self.baseline={'candidate.md':self.old,
            'contracts/instruction-surfaces.json':(self.repo/'contracts/instruction-surfaces.json').read_bytes()}
        lookup=mock.patch.object(changes,'_before',side_effect=lambda _repo,_base,name:self.baseline.get(name))
        lookup.start(); self.addCleanup(lookup.stop)
        self.target.write_bytes(self.new)
        self.row={'owner':'candidate.md','basis':'observed-deviation','baseline_sufficient':False,
            'deviation':'Fixture comparative failure','evidence':'Synthetic transport fixture; no real model claim',
            'why_instruction':'Exercise eligibility boundary','alternative':'No instruction change',
            'artifacts':{'candidate.md':{'before_sha256':sha(self.old),'after_sha256':sha(self.new)}},
            'task_contract':{'claim':self.suite['claim'],'suite_sha256':fixture['suite_sha256'],
                             'comparison_requirements':self.suite['comparison_requirements']},
            'behavior_measurements':[{'report':'evals/results/report.json','suite':'evals/suite.json',
                'profile_sha256':sha((self.repo/'profiles/current.json').read_bytes()),
                'suite_sha256':fixture['suite_sha256']}]}
        self.suite_raw=fixture['suite_path'].read_bytes()
        (self.repo/'evals/suite.json').write_bytes(self.suite_raw)
        self.save_report(); self.save_receipt()
    def save_profile(self):(self.repo/'profiles/current.json').write_text(json.dumps(self.profile))
    def save_report(self):
        raw=json.dumps(self.report).encode(); (self.repo/'evals/results/report.json').write_bytes(raw)
        self.row['behavior_measurements'][0]['report_sha256']=sha(raw)
    def save_receipt(self):(self.repo/'evals/results/necessity.json').write_text(json.dumps({'instruction_changes':[self.row]}))
    def eligible(self):return changes.measurement_eligibility(self.repo,self.repo,'candidate.md','candidate.md',self.row,self.base)
    def test_quality_win_without_overall_usage_is_excluded(self):
        self.assertFalse(self.eligible()['eligible'], self.eligible())
        with self.assertRaisesRegex(sync_git.SyncBlocked,'instruction excluded'):
            changes.check(self.repo,self.repo,self.base,['candidate.md','evals/results/necessity.json','evals/results/report.json','evals/suite.json'])
    def test_accounting_success_cannot_bypass_outer_source_binding(self):
        # Isolate the existing source/profile/harness boundary from synthetic
        # transport's deliberately incomplete overall-usage receipt.
        attribute_fixture_judges(self.report)
        self.save_report()
        with mock.patch('evaluation_evidence.outcome_efficiency',return_value={'errors':[]}):
            result = self.eligible()
            self.assertTrue(result['eligible'], result)
            self.assertNotIn('measured improvement', result['reason'])
            self.assertIn('retention require owner review', result['reason'])
            self.target.write_bytes(b'UNMEASURED_CHANGE\n')
            self.row['artifacts']['candidate.md']['after_sha256']=sha(self.target.read_bytes())
            self.assertFalse(self.eligible()['eligible'])
    def test_bound_native_artifact_evidence_is_validated_but_never_admitted(self):
        from test_native_artifact_evidence import make_native_evidence
        self.report, plan, _ = make_native_evidence(self.repo/'native-fixture')
        raw=json.dumps(plan).encode(); (self.repo/'evals/suite.json').write_bytes(raw)
        self.row['behavior_measurements'][0]['suite_sha256']=sha(raw)
        self.save_report()
        result=self.eligible()
        self.assertFalse(result['eligible'])
        self.assertTrue(result['artifact_evidence']['consistent'],result)
        self.assertFalse(result['artifact_evidence']['source_bytes_complete'])
        self.assertFalse(result['artifact_evidence']['admission'])
        self.report['admission']=True; self.save_report()
        result=self.eligible()
        self.assertFalse(result['eligible'])
        self.assertFalse(result['artifact_evidence']['consistent'])
    def test_missing_measurement_is_excluded_at_sync_boundary_without_writes(self):
        self.row.pop('behavior_measurements'); self.save_receipt()
        before={p.relative_to(self.repo).as_posix():p.read_bytes() for p in self.repo.rglob('*') if p.is_file() and '.git' not in p.parts}
        with self.assertRaisesRegex(sync_git.SyncBlocked,'instruction excluded'):
            changes.check(self.repo,self.repo,self.base,['candidate.md','evals/results/necessity.json'])
        self.assertEqual(before,{p.relative_to(self.repo).as_posix():p.read_bytes() for p in self.repo.rglob('*') if p.is_file() and '.git' not in p.parts})
    def test_unit_passes_and_malformed_records_cannot_qualify(self):
        for record in ({'tests':60,'passed':True},[],{'decision':{'decision':'admit'}}):
            with self.subTest(record=record):
                self.report=record; self.save_report(); self.assertFalse(self.eligible()['eligible'])
    def test_mismatched_source_task_model_harness_and_missing_host_excluded(self):
        original=copy.deepcopy(self.row)
        for field in ('instruction','task','model','harness','host','record-hash'):
            with self.subTest(field=field):
                self.row=copy.deepcopy(original); self.target.write_bytes(self.new)
                self.profile['hosts']={'codex':dict(self.profile['target'])}; self.save_profile()
                harness=self.repo/'tools/eval.py'; saved=harness.read_bytes()
                if field=='instruction':
                    self.target.write_bytes(b'UNMEASURED_CHANGE\n'); self.row['artifacts']['candidate.md']['after_sha256']=sha(self.target.read_bytes())
                if field=='task':self.row['task_contract']['suite_sha256']='0'*64
                if field=='model':
                    self.profile['hosts']['codex']['model']='new-unmeasured-model'; self.save_profile()
                    self.row['behavior_measurements'][0]['profile_sha256']=sha((self.repo/'profiles/current.json').read_bytes())
                if field=='harness':harness.write_bytes(saved+b'\n# changed harness\n')
                if field=='host':
                    self.profile['hosts']['hermes']=dict(self.profile['target']); self.save_profile()
                    self.row['behavior_measurements'][0]['profile_sha256']=sha((self.repo/'profiles/current.json').read_bytes())
                if field=='record-hash':self.row['behavior_measurements'][0]['report_sha256']='0'*64
                self.assertFalse(self.eligible()['eligible']); harness.write_bytes(saved)
    def test_unchanged_instructions_and_non_instruction_settings_do_not_need_measurement(self):
        self.target.write_bytes(self.old)
        self.assertEqual(changes.check(self.repo,self.repo,self.base,['candidate.md']),[])
        (self.repo/'settings.json').write_text('{}')
        self.assertEqual(changes.check(self.repo,self.repo,self.base,['settings.json']),[])
    def test_inconclusive_or_non_improving_measurement_is_excluded(self):
        self.report['decision']['decision']='inconclusive'; self.save_report()
        self.assertFalse(self.eligible()['eligible'])
    def test_legacy_change_needs_migration_without_disabling_unchanged_source(self):
        (self.repo/'contracts/instruction-surfaces.json').write_text(json.dumps({'schema_version':1}))
        self.target.write_bytes(self.old)
        self.baseline['contracts/instruction-surfaces.json']=(self.repo/'contracts/instruction-surfaces.json').read_bytes()
        base=self.base
        self.assertEqual(changes.check(self.repo,self.repo,base,['candidate.md']),[])
        (self.repo/'skills/legacy').mkdir(parents=True); (self.repo/'skills/legacy/SKILL.md').write_text('new unmeasured instruction')
        with self.assertRaisesRegex(sync_git.SyncBlocked,'migrate ownership/evidence'):
            changes.check(self.repo,self.repo,base,['skills/legacy/SKILL.md'])

class ComparisonReadinessTests(unittest.TestCase):
    def suite(self):return {'cases':[{'prompt':'unanswered task'}],'comparison_requirements':{'interaction':'single-turn','context':'isolated-text-projection','metrics':['outcome_correctness']}}
    def test_observable_question_is_ready(self):self.assertTrue(runtime.comparison_readiness(self.suite())['ready'])
    def test_missing_multiturn_context_usage_and_physical_budget_fail_with_remedy(self):
        for field,value in [('interaction','multi-turn'),('context','full-authored-bundle'),('metrics',['tokens','cost']),('physical_call_cap',10)]:
            with self.subTest(field=field):
                suite=self.suite(); suite['comparison_requirements'][field]=value
                result=runtime.comparison_readiness(suite); self.assertFalse(result['ready']); self.assertTrue(result['remedies'])
        self.assertFalse(runtime.comparison_readiness({'cases':[]})['ready'])
    def test_not_ready_cli_never_creates_runtime_or_calls_model(self):
        import test_evaluation_evidence as fixture
        evaluator=fixture.load_evaluator()
        suite=self.suite(); suite.update(name='multi-turn',cases=[{'id':str(i),'prompt':'task','criteria':['correct']} for i in range(3)])
        suite['comparison_requirements']['interaction']='multi-turn'
        argv=['eval.py','virtual-suite.json','--candidate','absent.md','--model','test','--provider','openai-codex','--equivalence-group','test','--rollback','restore fixture']
        stderr=io.StringIO()
        with mock.patch.object(sys,'argv',argv),mock.patch.object(evaluator,'harness_hash',return_value='0'*64),mock.patch.object(Path,'read_bytes',return_value=json.dumps(suite).encode()),mock.patch.object(evaluator,'run_agent') as called,mock.patch.object(evaluator.tempfile,'mkdtemp') as made,mock.patch.object(runtime,'comparison_readiness',wraps=runtime.comparison_readiness) as readiness,contextlib.redirect_stderr(stderr):
            with self.assertRaises(SystemExit) as stopped:evaluator.main()
            called.assert_not_called(); made.assert_not_called()
        self.assertEqual(stopped.exception.code,2)
        self.assertEqual(stderr.getvalue().strip().splitlines()[-1],
            'eval.py: error: comparison not ready: inline-text lane cannot measure multi-turn adaptation; Use a supported conversation route preserving successive user turns and inspect final artifacts; do not flatten the dialogue into a solved-case prompt.')
        readiness.assert_called_once_with(suite)

class OracleContractTests(unittest.TestCase):
    def setUp(self):
        import test_evaluation_evidence as fixture
        self.evaluator = fixture.load_evaluator()
        self.no_children = mock.patch('subprocess.Popen', side_effect=AssertionError('oracle preflight must not launch'))
        self.no_children.start(); self.addCleanup(self.no_children.stop)

    def suite(self):
        return {"cases": [{"id": "timeout", "prompt": "Return a positive timeout at most 150; equivalent methods allowed.",
            "must_not_contain": ["unbounded"], "acceptance_review": {
                "reviewer": "synthetic semantic reviewer",
                "assertions": [{"check": "must_not_contain:0", "requirement": "Prompt requires bounded timeout",
                    "constraint": "invariant", "justification": "Reject explicit unbounded behavior"}],
                "controls": [{"id": "alternative", "output": "exclusiveMinimum zero; maximum 150", "deterministic_pass": True,
                    "outcome": "adequate", "alternative": True, "rationale": "Different valid bound representation"},
                    {"id": "broken", "output": "unbounded", "deterministic_pass": False, "outcome": "broken",
                     "alternative": False, "rationale": "Drops the required ceiling"}]}}]}

    def test_valid_alternative_and_broken_control_use_real_checker(self):
        result = self.evaluator.oracle_preflight(self.suite())
        self.assertTrue(result['ready'], result)
        self.assertEqual([c['deterministic_pass'] for c in result['controls']], [True, False])
        self.assertIn('not semantic adequacy proof', result['scope'])

    def test_unmapped_or_duplicated_assertion_and_missing_review_block(self):
        for mutation in ('missing', 'unmapped', 'duplicate', 'source', 'alternatives', 'negative'):
            suite = self.suite(); case = suite['cases'][0]; review = case['acceptance_review']
            if mutation == 'missing': del case['acceptance_review']
            elif mutation == 'unmapped': case['must_contain'] = ['preferred algorithm']
            elif mutation == 'duplicate': review['assertions'] *= 2
            elif mutation == 'source': review['assertions'][0]['requirement'] = ''
            elif mutation == 'alternatives': review['controls'][0]['alternative'] = False
            else: review['controls'] = review['controls'][:1]
            with self.subTest(mutation=mutation): self.assertFalse(self.evaluator.oracle_preflight(suite)['ready'])

    def test_overprescriptive_literal_rejects_valid_control_before_launch(self):
        suite = self.suite(); case = suite['cases'][0]
        case['must_contain'] = ['"minimum":']
        case['acceptance_review']['assertions'].append({"check":"must_contain:0", "requirement":"Positive timeout",
            "constraint":"invariant", "justification":"Deliberately faulty assertion for sensitivity control"})
        self.assertFalse(self.evaluator.oracle_preflight(suite)['ready'])

    def test_control_failure_cannot_be_relabelled_expected_rejection_of_valid_solution(self):
        suite = self.suite(); review = suite['cases'][0]['acceptance_review']
        review['controls'][0].update(output='unbounded', deterministic_pass=False)
        self.assertFalse(self.evaluator.oracle_preflight(suite)['ready'])

    def test_risk_based_no_alternative_and_semantic_boundary_are_explicit(self):
        suite = self.suite(); case = suite['cases'][0]; review = case['acceptance_review']
        review['controls'][0]['alternative'] = False
        review['alternatives_not_applicable'] = 'Exact externally required response token; no method is being scored'
        self.assertTrue(self.evaluator.oracle_preflight(suite)['ready'])
        # Deterministic success does not prove that the semantic reviewer caught
        # this wrong answer. The preflight records, rather than invents, that claim.
        case['criteria'] = ['Answer must be factually correct']
        review['assertions'].append({"check":"criteria:0", "requirement":"Task correctness",
            "constraint":"invariant", "justification":"Semantic reviewer owns correctness"})
        review['controls'][1].update(output='wrong answer with no forbidden literal', deterministic_pass=True)
        result = self.evaluator.oracle_preflight(suite)
        self.assertTrue(result['ready'], result)
        self.assertEqual(result['controls'][1]['reviewed_outcome'], 'broken')

    def test_timeout_incident_semantics_accept_equivalent_layout_and_native_default(self):
        # Reuse the production Draft202012 validator, not literal key matching.
        for budget in (150, 241):
            schemas = [dict(type='number', exclusiveMinimum=0, maximum=budget, default=budget),
                {'allOf':[{'type':'number'}, {'exclusiveMinimum':0}, {'maximum':budget}], 'default':min(180,budget)}]
            for schema in schemas:
                for value in (0.5, 1, budget): self.assertEqual(self.evaluator._schema_reasons(value, schema), [])
                for value in (0, -1, budget+1, True, '1'):
                    self.assertTrue(self.evaluator._schema_reasons(value, schema))
                self.assertGreater(schema['default'], 0); self.assertLessEqual(schema['default'], budget)
            # Original advertised gold minimum=1 falsely rejected a legal fraction.
            self.assertTrue(self.evaluator._schema_reasons(0.5, {'type':'number','minimum':1,'maximum':budget}))
            # Upper-bound weakening and a fixed 180 under budget150 remain broken.
            self.assertFalse(self.evaluator._schema_reasons(budget+1, {'type':'number','exclusiveMinimum':0}))
        self.assertGreater(180, 150)

    def test_timeout_default_policy_is_invariant_not_equal_to_budget(self):
        suite = {'schema_version':3, 'receipt_schema':{'type':'object','required':['status','default'],
            'properties':{'status':{'const':'bounded'},'default':{'type':'number','exclusiveMinimum':0,'maximum':241}}},
            'cases':[{'id':'timeout-default','expected_receipt':{'default':241}, 'acceptance_review':{
                'reviewer':'synthetic reviewer', 'assertions':[{'check':key, 'requirement':'positive default within budget',
                    'constraint':'invariant','justification':'Budget does not require default equality'}
                    for key in ('receipt_schema','expected_receipt:default')],
                'controls':[{'id':'native-default','output':'{"status":"bounded","default":180}',
                    'deterministic_pass':True,'outcome':'adequate','alternative':True,'rationale':'Native180 is legal under241'},
                    {'id':'zero','output':'{"status":"bounded","default":0}', 'deterministic_pass':False,
                     'outcome':'broken','alternative':False,'rationale':'Zero violates positivity'}]}}]}
        self.assertFalse(self.evaluator.oracle_preflight(suite)['ready'])
        case=suite['cases'][0]; case['expected_receipt']={'status':'bounded'}
        case['acceptance_review']['assertions'][1]['check']='expected_receipt:status'
        self.assertTrue(self.evaluator.oracle_preflight(suite)['ready'])

    def test_cli_blocks_missing_review_before_runtime_or_paid_calls(self):
        suite = {"name":"unreviewed", "cases":[{"id":str(i),"prompt":"task","criteria":["correct"]} for i in range(3)],
            "comparison_requirements":{"interaction":"single-turn","context":"isolated-text-projection","metrics":["outcome_correctness"]}}
        argv = ['eval.py','virtual-suite.json','--candidate','absent.md','--model','fixture','--provider','openai-codex',
                '--equivalence-group','fixture','--rollback','restore']
        with mock.patch.object(sys,'argv',argv), mock.patch.object(self.evaluator,'harness_hash',return_value='0'*64), \
             mock.patch.object(Path,'read_bytes',return_value=json.dumps(suite).encode()), \
             mock.patch.object(self.evaluator,'run_agent') as called, mock.patch.object(self.evaluator.tempfile,'mkdtemp') as made, \
             contextlib.redirect_stderr(io.StringIO()) as errors:
            with self.assertRaises(SystemExit) as stopped: self.evaluator.main()
        self.assertEqual(stopped.exception.code, 2); called.assert_not_called(); made.assert_not_called()
        self.assertIn('oracle not ready', errors.getvalue())


class CorrectionReviewTests(unittest.TestCase):
    """No inference: narrow review routes must not admit optional prose."""
    def setUp(self):
        self.repo = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.name = 'skills/instruction-authoring/SKILL.md'
        self.owner = 'skills/instruction-authoring'
        self.receipt = 'evals/results/necessity.json'
        self.old = b'# Authoring\n\n## Evaluation discipline\nOld testing contract.\n\n## Completion\nKeep owner verification.\n'
        self.new = self.old.replace(b'Old testing contract.', b'Explicitly corrected testing contract.')
        self.baseline = {
            self.name: self.old,
            'contracts/instruction-surfaces.json': b'{"schema_version":2,"surfaces":[]}',
            **{name: b'Existing intent.\n' for name in changes.CONTRACTS}}
        for name, data in self.baseline.items():
            self.put(name, data)
        self.put('contracts/ownership.json', json.dumps({'capabilities':[{'id':'instruction-authoring','owner':self.owner}]}).encode())
        self.put(self.name, self.new)
        for name in changes.CONTRACTS:
            self.put(name, b'Explicitly corrected intent.\n')
        self.paths = {self.name, *changes.CONTRACTS, self.receipt}
        self.row = {'owner':self.owner,'basis':'user-correction','baseline_sufficient':False,
            'deviation':'User corrected testing-contract policy.','evidence':'Synthetic user-request fixture, no human authentication.',
            'why_instruction':'Owning normative testing contract.','alternative':'Keep existing contract; no optional prose adoption.',
            'change_kind':'contract-correction'}
        lookup = mock.patch.object(changes, '_before', side_effect=lambda _repo,_base,name:self.baseline.get(name))
        lookup.start(); self.addCleanup(lookup.stop)
        scope = mock.patch.object(changes, 'reconciliation_scope', side_effect=lambda *_args:(
            {n for n in self.paths if n != self.receipt and self.baseline.get(n) != (self.repo/n).read_bytes()},
            set(), {self.name,*changes.CONTRACTS}))
        scope.start(); self.addCleanup(scope.stop)
        self.save()

    def put(self, name, data):
        path = self.repo/name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(data)

    def save(self):
        binding = {n:{'before_sha256':sha(self.baseline[n]),'after_sha256':sha((self.repo/n).read_bytes())}
                   for n in {self.name,*changes.CONTRACTS}}
        self.row['artifacts'] = {self.name:binding[self.name]}
        self.dependencies = {'artifacts':binding,'requirement_change':True,'requirement_reason':'Explicit corrected intent.',
            'authority':'Fixture user correction, not automated approval.','checks':'Source-bound fixture regressions.',
            'outcome_review':{k:'Fixture reviewed scope; no behavioral claim.' for k in ('expected','observed','evidence','limitations')},
            'obligations':[{'path':n,'disposition':'updated' if b['before_sha256']!=b['after_sha256'] else 'unchanged',
                            'reason':'Selected instruction/intent correction.'} for n,b in binding.items()],
            'framework_review':{'affected':sorted(binding),'selection_reason':'Existing testing-contract consumers.',
                                'unaffected_reason':'Other authoring procedures preserved.','checks':'Source/contract fixture inspection.'}}
        self.write_receipt()

    def write_receipt(self):
        self.put(self.receipt, json.dumps({'instruction_changes':[self.row],'change_reconciliation':[self.dependencies]}).encode())

    def check(self):
        return changes.check(self.repo,self.repo,'baseline',self.paths)

    def test_explicit_contract_correction_uses_existing_full_review_seam(self):
        with mock.patch.object(changes,'measurement_eligibility',side_effect=AssertionError('No comparison for reviewed contract policy')):
            self.assertTrue(self.check())
        result=changes.correction_eligibility(self.repo,self.repo,self.name,self.owner,self.row,'baseline',self.paths,[self.dependencies])
        self.assertFalse(result['behavioral_proof']);self.assertFalse(result['approval_authenticated'])

    def test_maintenance_label_does_not_exempt_substantive_prose(self):
        self.row.pop('change_kind');self.row['basis']='mechanical-maintenance';self.write_receipt()
        with mock.patch.object(changes,'measurement_eligibility',return_value={'eligible':False,'reason':'instruction excluded'}) as measured:
            with self.assertRaisesRegex(sync_git.SyncBlocked,'instruction excluded'):self.check()
            measured.assert_called_once()

    def test_line_endings_only_pass_but_optional_words_still_need_measurement(self):
        self.put(self.name,self.old.replace(b'\n',b'\r\n'))
        self.row.pop('change_kind');self.row['basis']='mechanical-maintenance';self.save()
        with mock.patch.object(changes,'measurement_eligibility',side_effect=AssertionError('Content identical')):
            self.assertTrue(self.check())
        self.put(self.name,self.new.replace(b'\n',b'\r\n'));self.save()
        with mock.patch.object(changes,'measurement_eligibility',return_value={'eligible':False,'reason':'instruction excluded'}):
            with self.assertRaisesRegex(sync_git.SyncBlocked,'instruction excluded'):self.check()

    def test_content_outside_authorized_section_is_rejected(self):
        self.put(self.name,self.new.replace(b'Keep owner verification.',b'Install optional workflow.'));self.save()
        with self.assertRaisesRegex(sync_git.SyncBlocked,'outside its contract section'):self.check()

    def test_publication_record_correction_keeps_other_obligations(self):
        original_name=self.name;self.name=self.owner+'/references/change-review.md'
        self.old=b'# Review\n\n## Publication necessity record\nOld contract.\n\n## Loading review\nKeep mandatory reads.\n'
        self.new=self.old.replace(b'Old contract.',b'Explicit corrected contract.')
        self.baseline[self.name]=self.old;self.put(self.name,self.new)
        self.paths.remove(original_name);self.paths.add(self.name);self.save()
        self.assertTrue(self.check())
        self.put(self.name,self.new.replace(b'Keep mandatory reads.',b'Optional reads.'));self.save()
        with self.assertRaisesRegex(sync_git.SyncBlocked,'outside its contract section'):self.check()

    def test_other_owner_cannot_use_contract_route(self):
        with self.assertRaisesRegex(sync_git.SyncBlocked,'existing explicit authoring owner'):
            changes.correction_eligibility(self.repo,self.repo,self.name,'skills/optional',self.row,'baseline',self.paths,[self.dependencies])

    def test_behavioral_claim_or_measurement_cannot_hide_in_correction(self):
        original=copy.deepcopy(self.row)
        for key,value in (('behavior_measurements',[]),('task_contract',{'claim':'Better model outcomes'})):
            self.row=copy.deepcopy(original);self.row[key]=value;self.write_receipt()
            with self.subTest(key=key),self.assertRaisesRegex(sync_git.SyncBlocked,'behavioral-adoption claim'):self.check()

    def test_unknown_kind_is_rejected(self):
        self.row['change_kind']='unreviewed-improvement';self.write_receipt()
        with self.assertRaisesRegex(sync_git.SyncBlocked,'invalid instruction change kind'):self.check()

    def test_stale_instruction_binding_is_rejected(self):
        self.row['artifacts'][self.name]['after_sha256']='0'*64;self.write_receipt()
        with self.assertRaises(sync_git.SyncBlocked):self.check()

    def test_correction_requires_changed_bound_intent_and_status(self):
        self.dependencies['requirement_change']=False;self.write_receipt()
        with self.assertRaisesRegex(sync_git.SyncBlocked,'changed, bound intent'):self.check()
        self.put('docs/requirement-status.md',self.baseline['docs/requirement-status.md']);self.save()
        with self.assertRaises(sync_git.SyncBlocked):self.check()

    def test_dependency_review_remains_required_before_exception(self):
        self.dependencies['artifacts'].pop('docs/system-requirements.md');self.write_receipt()
        with self.assertRaisesRegex(sync_git.SyncBlocked,'bound dependency'):self.check()

    def test_maintenance_cannot_borrow_explicit_contract_kind(self):
        self.row['basis']='mechanical-maintenance';self.write_receipt()
        with self.assertRaisesRegex(sync_git.SyncBlocked,'existing explicit authoring owner'):self.check()

    def test_extra_review_label_does_not_exempt_optional_adoption(self):
        self.row.pop('change_kind');self.row['verification_review']={'scope':'author-directed-contract-correction'};self.write_receipt()
        with mock.patch.object(changes,'measurement_eligibility',return_value={'eligible':False,'reason':'instruction excluded'}):
            with self.assertRaisesRegex(sync_git.SyncBlocked,'instruction excluded'):self.check()

    def test_existing_necessity_reasoning_is_required(self):
        original=copy.deepcopy(self.row)
        for field in ('evidence','deviation','why_instruction','alternative'):
            self.row=copy.deepcopy(original);self.row[field]='';self.write_receipt()
            with self.subTest(field=field),self.assertRaisesRegex(sync_git.SyncBlocked,'incomplete architectural reasoning'):self.check()


if __name__=='__main__':unittest.main()
