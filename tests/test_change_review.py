from __future__ import annotations
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock
import sys
import os
import contextlib
import io

REPO=Path(os.environ.get('AGENT_SYNC_TEST_REPO',Path(__file__).resolve().parents[1]))
sys.path.insert(0,str(REPO/'tools'))
spec=importlib.util.spec_from_file_location('change_review',Path(os.environ.get('AGENT_SYNC_REVIEW_SOURCE',REPO/'tools/change_review.py')))
review_tool=importlib.util.module_from_spec(spec);spec.loader.exec_module(review_tool)
fixture_spec=importlib.util.spec_from_file_location('evidence_fixture',REPO/'tests/test_evaluation_evidence.py')
fixture_tool=importlib.util.module_from_spec(fixture_spec);fixture_spec.loader.exec_module(fixture_tool)

class ChangeReviewTests(unittest.TestCase):
    def make_repo(self,root):
        repo=root/'repo'; (repo/'skills/kept').mkdir(parents=True)
        (repo/'skills/kept/SKILL.md').write_text('---\nname: kept\ndescription: Inspect model instruction overlap.\nlicense: MIT\n---\nExisting procedure.\n')
        (repo/'skills/neighbor').mkdir()
        (repo/'skills/neighbor/SKILL.md').write_text('---\nname: neighbor\ndescription: Review model instruction boundaries.\nlicense: MIT\n---\nOther procedure.\n')
        (repo/'registry.json').write_text(json.dumps({'schema_version':1,'skills':[{'name':'kept','status':'admitted'}]}))
        (repo/'fleet.json').write_text(json.dumps({'schema_version':1,'snapshot_root':'render/fleet',
            'machines':{'local-windows':{'skill_roots':[]}}}))
        (repo/'profiles').mkdir()
        (repo/'profiles/current.json').write_text(json.dumps({'status':'current-observed','target':{'model':'gpt-6-sol','provider':'openai-codex'},'hosts':{'hermes':{'model':'gpt-6-sol','provider':'openai-codex','reasoning':'medium'},'codex':{'model':'gpt-6-astra','reasoning':'low'}}}))
        (repo/'evals/results').mkdir(parents=True)
        return repo
    def test_advisory_owner_and_overlap_do_not_grant_admission_or_write(self):
        with tempfile.TemporaryDirectory() as temp:
            repo=self.make_repo(Path(temp)); before={str(p):p.read_bytes() for p in repo.rglob('*') if p.is_file()}
            r=review_tool.review(repo,'skills/kept/SKILL.md')
            self.assertEqual(r['owner'],'skills/kept')
            self.assertEqual(r['classification']['disposition'],'checks-required')
            self.assertFalse(r['admission_authority']);self.assertFalse(r['mutation_performed'])
            self.assertEqual(r['catalog']['overlap_candidates'][0]['owner'],'skills/neighbor')
            self.assertTrue(all(x['status']=='missing-current-comparison' for x in r['measurement']['required_routes']))
            self.assertEqual(before,{str(p):p.read_bytes() for p in repo.rglob('*') if p.is_file()})
    def test_target_traversal_and_unknown_host_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            repo=self.make_repo(Path(temp))
            with self.assertRaises(ValueError):review_tool.review(repo,'../secret')
            with self.assertRaises(ValueError):review_tool.review(repo,'skills/kept/SKILL.md',hosts=['unknown'])
    def test_model_alias_and_callability_do_not_cover_current_sol(self):
        with tempfile.TemporaryDirectory() as temp:
            repo=self.make_repo(Path(temp))
            (repo/'evals/results/smoke.json').write_text(json.dumps({'model':'gpt-5.6-sol','result':{'passed':True}}))
            r=review_tool.review(repo,'skills/kept/SKILL.md',hosts=['hermes'])
            self.assertEqual(r['measurement']['required_routes'][0]['model'],'gpt-6-sol')
            self.assertEqual(r['measurement']['required_routes'][0]['status'],'missing-current-comparison')
            self.assertEqual(r['official_model_guidance']['requested_models'],['gpt-6-sol'])
            self.assertFalse(r['official_model_guidance']['sources'])
    def test_actual_producer_report_is_validated_with_independent_suite(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);repo=self.make_repo(root)
            f=fixture_tool.make_evaluation(root/'record',version=3,agent='hermes',judge_agent='codex')
            r=review_tool.review(repo,'skills/kept/SKILL.md',candidate=f['candidate_path'],baseline=f['baseline_path'],hosts=['hermes'],models=['gpt-6-astra'],reports=[f['report_path']],suites=[f['suite_path']])
            observed=r['measurement']['observed_comparisons'][0]
            self.assertEqual(observed['status'],'record-consistent',observed)
            # Recorded Astra/xhigh is not the requested default Sol/medium cell,
            # nor Astra/medium: reasoning and model both remain significant.
            self.assertTrue(all(x['status']=='missing-current-comparison' for x in r['measurement']['required_routes']))
            f['report']['effective_stack']['model']='gpt-6-sol'
            f['report_path'].write_text(json.dumps(f['report']))
            invalid=review_tool.review(repo,'skills/kept/SKILL.md',candidate=f['candidate_path'],baseline=f['baseline_path'],reports=[f['report_path']],suites=[f['suite_path']])
            self.assertEqual(invalid['measurement']['observed_comparisons'][0]['status'],'invalid-record')
    def test_suite_hash_and_candidate_identity_required(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);repo=self.make_repo(root)
            f=fixture_tool.make_evaluation(root/'record',version=3,agent='hermes',judge_agent='codex')
            r=review_tool.review(repo,'skills/kept/SKILL.md',candidate=f['candidate_path'],baseline=f['baseline_path'],reports=[f['report_path']])
            self.assertEqual(r['measurement']['observed_comparisons'][0]['status'],'independent-suite-missing')
            f['candidate_path'].write_text('Different instructions\n')
            r=review_tool.review(repo,'skills/kept/SKILL.md',candidate=f['candidate_path'],baseline=f['baseline_path'],reports=[f['report_path']],suites=[f['suite_path']])
            self.assertEqual(r['measurement']['observed_comparisons'][0]['status'],'different-artifact-or-baseline')
    def test_exact_matching_cell_is_covered_and_tampered_route_is_not(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);repo=self.make_repo(root)
            f=fixture_tool.make_evaluation(root/'record',version=3,agent='hermes',judge_agent='codex')
            profile=json.loads((repo/'profiles/current.json').read_text())
            profile['hosts']['hermes'].update(model='gpt-6-astra',reasoning='xhigh')
            (repo/'profiles/current.json').write_text(json.dumps(profile))
            args=dict(candidate=f['candidate_path'],baseline=f['baseline_path'],hosts=['hermes'],reports=[f['report_path']],suites=[f['suite_path']])
            r=review_tool.review(repo,'skills/kept/SKILL.md',**args)
            self.assertEqual(r['measurement']['required_routes'][0]['status'],'recorded-text-comparison')
            self.assertFalse(r['measurement']['required_routes'][0]['positive_decision_sufficient_in_record'])
            for key,value in [('model','gpt-5.6-sol'),('provider','other-provider'),('reasoning','medium')]:
                changed=json.loads(json.dumps(profile));changed['hosts']['hermes'][key]=value
                (repo/'profiles/current.json').write_text(json.dumps(changed))
                r=review_tool.review(repo,'skills/kept/SKILL.md',**args)
                self.assertEqual(r['measurement']['required_routes'][0]['status'],'missing-current-comparison')
            profile['hosts']['codex'].update(model='gpt-6-astra',reasoning='xhigh')
            (repo/'profiles/current.json').write_text(json.dumps(profile))
            args['hosts']=['codex']
            self.assertEqual(review_tool.review(repo,'skills/kept/SKILL.md',**args)['measurement']['required_routes'][0]['status'],'missing-current-comparison')
    def test_renamed_candidate_is_validated_against_intended_owner(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);repo=self.make_repo(root);p=root/'candidate.md'
            p.write_text('No frontmatter\n')
            r=review_tool.review(repo,'skills/kept/SKILL.md',candidate=p)
            self.assertIn('missing frontmatter description',r['structural_findings'])
            p.write_bytes((repo/'skills/kept/SKILL.md').read_bytes())
            r=review_tool.review(repo,'skills/kept/SKILL.md',candidate=p)
            self.assertEqual(r['structural_findings'],[])
    def test_bounded_single_snapshot_json_and_visible_skipped_records(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);repo=self.make_repo(root);p=root/'large.json'
            p.write_bytes(b'a'*(review_tool.MAX_JSON_BYTES+1))
            with self.assertRaisesRegex(ValueError,'bounded read'):review_tool._read_json_bytes(p)
            (repo/'evals/results/broken.json').write_text('not json')
            (repo/'evals/results/structural.json').write_text('{"result":"pass"}')
            r=review_tool.review(repo,'skills/kept/SKILL.md')
            self.assertEqual(r['measurement']['scan_diagnostics']['unreadable_reports'],1)
            self.assertEqual(r['measurement']['scan_diagnostics']['non_comparative_records'],1)
            p.write_text('{"cases":[]}')
            with mock.patch.object(Path,'read_bytes',side_effect=AssertionError('unbounded second read')):
                raw,parsed=review_tool._read_json_bytes(p)
                self.assertEqual(json.loads(raw),parsed)
    def test_plan_and_pre_edit_review_use_same_criteria(self):
        import reconcile
        with tempfile.TemporaryDirectory() as temp:
            repo=self.make_repo(Path(temp));options=dict(target='skills/kept/SKILL.md',hosts=['hermes'])
            expected=review_tool.review(repo,**options)
            with mock.patch.object(reconcile.capability_intake,'fleet_findings',return_value=[]):
                plan=reconcile.plan(repo,recovery_roots={},review_options=options)
            self.assertEqual(plan['authoring_review'],expected)
            output=io.StringIO()
            with contextlib.redirect_stdout(output):
                code=reconcile.main(['review','--repo',str(repo),'--target',options['target'],'--host','hermes'])
            self.assertEqual(code,0);self.assertEqual(json.loads(output.getvalue()),expected)
    def test_review_options_cannot_be_used_to_publish(self):
        import reconcile
        with mock.patch.object(reconcile,'complete_sync',side_effect=AssertionError('must not publish')):
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                reconcile.main(['sync','--target','skills/kept/SKILL.md'])
    def test_native_owner_is_resolved_and_same_reference_lens_is_available_in_plan(self):
        import reconcile
        with tempfile.TemporaryDirectory() as temp:
            repo=self.make_repo(Path(temp));target='recovery/current/hosts/hermes/skills/research/kept/SKILL.md'
            source=repo/target;source.parent.mkdir(parents=True);source.write_bytes((repo/'skills/kept/SKILL.md').read_bytes())
            (repo/'recovery.json').write_text(json.dumps({'hosts':{'hermes':{'artifacts':[{'id':'native-kept','kind':'text','source':'skills/research/kept/SKILL.md','snapshot':target.removeprefix('recovery/current/')}]}}}))
            options=dict(target=target,reference_skills=[repo/'skills/neighbor/SKILL.md'])
            expected=review_tool.review(repo,**options)
            self.assertEqual(expected['owner'],'recovery:hermes:native-kept')
            self.assertEqual([r['host'] for r in expected['measurement']['required_routes']],['hermes'])
            self.assertTrue(expected['useful_behavior_review']['sources'])
            self.assertFalse(expected['useful_behavior_review']['automatic_semantic_verdict'])
            with mock.patch.object(reconcile.capability_intake,'fleet_findings',return_value=[]):
                actual=reconcile.plan(repo,recovery_roots={},review_options=options)
            self.assertEqual(actual['authoring_review'],expected)
    def test_native_description_hint_exposes_clipping_without_a_quality_verdict(self):
        import recovery
        with tempfile.TemporaryDirectory() as temp:
            home=Path(temp);module=home/'hermes-agent/agent/skill_utils.py';module.parent.mkdir(parents=True)
            module.write_text('SKILL_PROMPT_DESC_LIMIT = 60\n')
            description='paper research '+('x'*55)+' OpenAI model guidance'
            with mock.patch.object(recovery,'_default_roots',return_value={'hermes':home}):
                hint=review_tool.native_catalog_view(description,['hermes'])
            self.assertTrue(hint['truncated']);self.assertNotIn('OpenAI',hint['visible_description'])
            self.assertEqual(hint['status'],'native-source-hint')
            self.assertIn('not observed',hint['limit'])

if __name__=='__main__':unittest.main()
