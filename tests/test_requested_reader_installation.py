"""Exact requested-reader category and actual synthetic read-only CLI behavior."""
from fixture_workspace import configure
configure()
from pathlib import Path
from unittest import mock
import copy,hashlib,json,shutil,subprocess,sys,tempfile,unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import instruction_changes as changes
import fleet,sync_git

class RequestedReaderTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.repo=Path(self.temp.name)
  shutil.copytree(ROOT/'skills/learnharness',self.repo/'skills/learnharness');shutil.copyfile(ROOT/'registry.json',self.repo/'registry.json')
  self.paths=['skills/learnharness/'+n for n in fleet.directory_record(ROOT/'skills/learnharness')['files']]
  self.acceptance={'classification':'requested-read-only-capability','upstream_commit':'6cba9c8c5afe8a63f47ea4ebae6e91d8a205cebb','package_sha256':'3cc55b7c53159b111a0b791e46f65305b8a0449c5d94fccd0c69953520970f32','model_benefit_claim':False,'verified_checks':['source-pin-and-license','package-validation','synthetic-session-and-graph-results','source-bytes-mtimes-tree-unchanged','synthetic-only-no-credentials-network-app','explicit-local-fork-data-dir'],'deployment_checks_required':['native-hermes-codex-omp-catalogue-body','repeat-sync-preserves-source']}
  self.row={'change_kind':'requested-reader','basis':'user-correction','reader_acceptance':self.acceptance}
  patch=mock.patch.object(changes,'_before',return_value=None);patch.start();self.addCleanup(patch.stop)
 def eligible(self,owner='skills/learnharness'):
  return changes.correction_eligibility(self.repo,self.repo,'skills/learnharness/SKILL.md',owner,self.row,'base',self.paths,[])
 def reject(self):
  with self.assertRaises((sync_git.SyncBlocked,RuntimeError)):self.eligible()
 def test_exact_package_qualifies_without_comparative_authority(self):
  result=self.eligible();self.assertTrue(result['eligible']);self.assertFalse(result['behavioral_proof']);self.assertFalse(result['approval_authenticated'])
 def test_acceptance_order_is_not_a_semantic_requirement(self):
  self.acceptance['verified_checks'].reverse();self.assertTrue(self.eligible()['eligible'])
 def test_other_owner_cannot_borrow_classification(self):
  with self.assertRaises(sync_git.SyncBlocked):self.eligible('skills/other')
 def test_source_and_package_pin_are_required(self):
  for key in ['upstream_commit','package_sha256']:
   old=self.acceptance[key];self.acceptance[key]='0'*40;self.reject();self.acceptance[key]=old
 def test_missing_or_duplicate_privacy_acceptance_rejects(self):
  old=list(self.acceptance['verified_checks'])
  for values in [old[:-1],old+[old[0]]]:self.acceptance['verified_checks']=values;self.reject()
 def test_native_loading_and_repeat_requirements_cannot_disappear(self):
  self.acceptance['deployment_checks_required']=[];self.reject()
 def test_changed_reader_and_extra_prompt_cannot_qualify(self):
  f=self.repo/'skills/learnharness/SKILL.md';f.write_bytes(f.read_bytes()+b'\nNew instruction.\n');self.reject()
 def test_existing_deployed_bytes_cannot_use_initial_install_category(self):
  with mock.patch.object(changes,'_before',return_value=b'existing'):self.reject()
 def test_behavioral_claims_remain_on_measured_path(self):
  self.acceptance['model_benefit_claim']=True;self.reject();self.acceptance['model_benefit_claim']=False
  self.row['behavior_measurements']=[]
  with self.assertRaisesRegex(sync_git.SyncBlocked,'behavioral-adoption'):self.eligible()
 def test_other_labels_do_not_supply_installation_authority(self):
  self.row['basis']='mechanical-maintenance';self.reject();self.row['basis']='user-correction';self.row.pop('change_kind');self.assertIsNone(self.eligible())
 def test_all_six_files_and_registry_provenance_required(self):
  self.paths.pop();self.reject();self.paths=['skills/learnharness/'+n for n in fleet.directory_record(ROOT/'skills/learnharness')['files']]
  f=self.repo/'registry.json';r=json.loads(f.read_bytes());next(v for v in r['skills'] if v['name']=='learnharness')['license']='unknown';f.write_bytes(json.dumps(r).encode());self.reject()

class ReaderFunctionalAcceptanceTests(unittest.TestCase):
 def test_explicit_fork_directory_correct_reads_no_writes_and_no_stock_fallback(self):
  with tempfile.TemporaryDirectory() as temporary:
   base=Path(temporary);data=base/'LearnHarness Local/data';(data/'chats').mkdir(parents=True);(data/'graph').mkdir()
   record={'id':'chat_synthetic','title':'Synthetic reader acceptance','version':1,'kind':'practice','createdAt':'2026-01-01T00:00:00Z','updatedAt':'2026-01-01T00:00:00Z','messages':[{'id':'m_user','role':'user','content':'Synthetic learner explanation.'}]}
   (data/'chats/chat_synthetic.json').write_bytes(json.dumps(record).encode())
   nodes=[{'id':n,'name':n,'statement':n,'aliases':[],'createdAt':'2026-01-01T00:00:00Z','provenance':[{'chatId':'chat_synthetic','messageId':'m_user'}]} for n in ['premise_a','premise_b','conclusion']]
   (data/'graph/nodes.jsonl').write_bytes(''.join(json.dumps(n)+'\n' for n in nodes).encode());chain={'id':'chain','premises':['premise_a','premise_b'],'conclusion':'conclusion','createdAt':'2026-01-01T00:00:00Z','provenance':[{'chatId':'chat_synthetic','messageId':'m_user'}]};(data/'graph/chains.jsonl').write_bytes((json.dumps(chain)+'\n').encode())
   snapshot=lambda:{p.relative_to(base).as_posix():(p.read_bytes(),p.stat().st_mtime_ns) if p.is_file() else None for p in base.rglob('*')}
   before=snapshot();scripts=ROOT/'skills/learnharness/scripts'
   def run(script,*args,root=data):
    return subprocess.run([sys.executable,'-B',str(scripts/script),'--data-dir',str(root),'--format','json',*args],capture_output=True,text=True,timeout=15)
   listing=run('sessions.py','list');self.assertEqual(listing.returncode,0,listing.stderr);self.assertEqual(json.loads(listing.stdout)['sessions'][0]['id'],'chat_synthetic')
   reading=run('sessions.py','read','chat_synthetic');self.assertEqual(reading.returncode,0,reading.stderr);self.assertEqual(json.loads(reading.stdout)['record']['messages'][0]['content'],'Synthetic learner explanation.')
   finding=run('graph.py','find','conclusion');self.assertEqual(finding.returncode,0,finding.stderr);self.assertEqual(json.loads(finding.stdout)['records'][0]['id'],'conclusion')
   chains=run('graph.py','chains','--node','conclusion');self.assertEqual(chains.returncode,0,chains.stderr);self.assertEqual(set(json.loads(chains.stdout)['records'][0]['premises']),{'premise_a','premise_b'})
   missing=run('sessions.py','list',root=base/'missing-profile/data');self.assertNotEqual(missing.returncode,0);self.assertFalse((base/'missing-profile').exists());self.assertEqual(snapshot(),before)

if __name__=='__main__':unittest.main()
