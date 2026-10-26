"""Closed one-correction admission; no assertion of behavioral improvement."""
from pathlib import Path
from unittest import mock
import copy,importlib.util,json,os,subprocess,sys,unittest
ROOT=Path(__file__).resolve().parents[1]
BASELINE='4533fce339f6b188411c9ac0ddf77a883b006015'
sys.path.insert(0,str(ROOT/'tools'))
import instruction_changes as current
import sync_git
changes=current
if os.environ.get('AUDIENCE_BASELINE_CONSUMER'):
 spec=importlib.util.spec_from_file_location('old_instruction_changes',os.environ['AUDIENCE_BASELINE_CONSUMER'])
 changes=importlib.util.module_from_spec(spec);spec.loader.exec_module(changes)

class MemoryPath:
 def __init__(self,files,name=''):self.files,self.name=files,name
 def __truediv__(self,name):return MemoryPath(self.files,self.name+'/'+name if self.name else name)
 def is_file(self):return self.name in self.files
 def read_bytes(self):return self.files[self.name]
 def write_bytes(self,data):self.files[self.name]=data
 def unlink(self):del self.files[self.name]

class PublicAudienceCorrectionTests(unittest.TestCase):
 def setUp(self):
  # In-memory decision controls avoid filesystem-dependent fixtures.
  self.repo=MemoryPath({})
  self.targets=set(current.PUBLIC_AUDIENCE_PAIR);self.paths=self.targets|current.CONTRACTS
  self.old={n:subprocess.check_output(['git','-C',str(ROOT),'show',BASELINE+':'+n]) for n in self.paths}
  for n in self.paths:
   (self.repo/n).write_bytes((ROOT/n).read_bytes())
  self.row={'change_kind':'public-audience-correction','basis':'user-correction','public_audience_acceptance':copy.deepcopy(current.PUBLIC_AUDIENCE_ACCEPTANCE)}
  self.recon=[{'requirement_change':True,'artifacts':{n:{} for n in self.paths}}]
  patch=mock.patch.object(changes,'_before',side_effect=lambda _s,_b,n:self.old.get(n));patch.start();self.addCleanup(patch.stop)
 def run_gate(self,name='surfaces/core.md',owner='surfaces/core.md'):
  return changes.correction_eligibility(self.repo,ROOT,name,owner,self.row,BASELINE,self.paths,self.recon)
 def rejects(self):
  with self.assertRaises(sync_git.SyncBlocked):self.run_gate()
 def test_exact_pair_qualifies_without_behavior_proof(self):
  for n in self.targets:
   result=self.run_gate(n,current.PUBLIC_AUDIENCE_PAIR[n][0])
   self.assertTrue(result['eligible']);self.assertFalse(result['behavioral_proof']);self.assertFalse(result['approval_authenticated'])
 def test_each_changed_source_byte_rejected(self):
  for n in self.targets:
   with self.subTest(n=n):
    p=self.repo/n;raw=p.read_bytes();p.write_bytes(raw+b'changed');self.rejects();p.write_bytes(raw)
 def test_each_stale_baseline_rejected(self):
  for n in self.targets:
   with self.subTest(n=n):
    raw=self.old[n];self.old[n]=raw+b'stale';self.rejects();self.old[n]=raw
 def test_missing_selected_pair_rejected(self):
  self.paths.remove('skills/humanizer/SKILL.md');self.rejects()
 def test_missing_actual_source_rejected(self):
  (self.repo/'skills/humanizer/SKILL.md').unlink();self.rejects()
 def test_wrong_owner_or_target_rejected(self):
  for n,o in [('surfaces/core.md','skills/humanizer'),('skills/other/SKILL.md','skills/other')]:
   with self.assertRaises(sync_git.SyncBlocked):self.run_gate(n,o)
 def test_wrong_basis_rejected(self):
  self.row['basis']='mechanical-maintenance';self.rejects()
 def test_decision_and_freeze_bindings_required(self):
  for k in current.PUBLIC_AUDIENCE_ACCEPTANCE:
   old=copy.deepcopy(self.row);self.row['public_audience_acceptance'].pop(k);self.rejects();self.row=old
 def test_numeric_true_is_not_boolean_acceptance(self):
  self.row['public_audience_acceptance']['no_behavioral_improvement_claim']=1;self.rejects()
 def test_unchanged_contract_or_missing_reconciliation_rejected(self):
  self.recon=[];self.rejects();self.recon=[{'requirement_change':True,'artifacts':{n:{} for n in self.paths}}]
  for n in current.CONTRACTS:(self.repo/n).write_bytes(self.old[n])
  self.rejects()
 def test_behavior_claims_rejected(self):
  for k in ['behavior_measurements','task_contract']:
   self.row[k]={};self.rejects();self.row.pop(k)
 def test_default_user_correction_is_not_generic_waiver(self):
  self.row.pop('change_kind');self.assertIsNone(self.run_gate())

if __name__=='__main__':unittest.main()
