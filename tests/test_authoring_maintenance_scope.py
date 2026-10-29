"""File-free dispatcher controls with actual pinned baseline/candidate bodies."""
from pathlib import Path
from copy import deepcopy
from types import SimpleNamespace
import ast,hashlib,os,subprocess,unittest

ROOT=Path(__file__).resolve().parents[1]
BASE='ab48410f2189ad14b0a82de97c45de45a9036cf2'
BASE_REPO=Path(os.environ.get('AGENT_SYNC_TEST_BASELINE',ROOT))
OWNER='skills/instruction-authoring';GUIDE=OWNER+'/references/item-review-loop.md';ENTRY=OWNER+'/SKILL.md'
PATHS=[ENTRY,GUIDE,'docs/system-requirements.md','docs/requirement-status.md']

class Blocked(RuntimeError):pass

class BytePath:
    def __init__(self,data,name=''):self.data,self.name=data,name
    def __truediv__(self,name):return BytePath(self.data,name)
    def is_file(self):return self.name in self.data
    def read_bytes(self):return self.data[self.name]

def load():
    original={}
    for name in PATHS:
        result=subprocess.run(['git','-C',str(BASE_REPO),'show',BASE+':'+name],capture_output=True)
        if result.returncode:
            tree=subprocess.run(['git','-C',str(BASE_REPO),'ls-tree','-z',BASE,'--',name],capture_output=True,check=True)
            if tree.stdout:raise RuntimeError('Existing baseline blob read failed')
        else:original[name]=result.stdout
    candidate={n:(ROOT/n).read_bytes() for n in PATHS}
    tree=ast.parse((ROOT/'tools/instruction_changes.py').read_text(encoding='utf-8'))
    nodes=[node for node in tree.body if isinstance(node,(ast.FunctionDef,ast.Assign)) and
           (isinstance(node,ast.FunctionDef) and node.name in {'_hash','_approved_item_review_maintenance','correction_eligibility'}
            or isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='CONTRACTS' for t in node.targets))]
    scope={'hashlib':hashlib,'sync_git':SimpleNamespace(SyncBlocked=Blocked),
           '_before':lambda source,base,name:original.get(name)}
    exec(compile(ast.Module(body=nodes,type_ignores=[]),'<actual-dispatcher>','exec'),scope)
    artifacts={n:{'before_sha256':hashlib.sha256(original[n]).hexdigest() if n in original else 'absent',
                  'after_sha256':hashlib.sha256(candidate[n]).hexdigest()} for n in PATHS}
    return original,candidate,scope,[{'requirement_change':True,'artifacts':artifacts}]

class AuthoringMaintenanceScope(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.original,cls.candidate,cls.scope,cls.records=load()
    def invoke(self,*,name=GUIDE,owner=OWNER,candidate=None,paths=None,records=None,row=None):
        return self.scope['correction_eligibility'](BytePath(self.candidate if candidate is None else candidate),None,name,owner,
            {'basis':'user-correction','change_kind':'contract-correction'} if row is None else row,BASE,
            PATHS if paths is None else paths,self.records if records is None else records)
    def test_exact_pair_and_existing_entrypoint_seam(self):
        for name in [GUIDE,ENTRY]:
            result=self.invoke(name=name);self.assertTrue(result['eligible']);self.assertFalse(result['behavioral_proof']);self.assertFalse(result['approval_authenticated'])
    def test_substituted_body_and_intent_rejected(self):
        for name in PATHS:
            changed=dict(self.candidate);changed[name]+=b'\nchanged\n'
            with self.subTest(name=name),self.assertRaises(Blocked):self.invoke(candidate=changed)
    def test_missing_selected_requirement_rejected(self):
        with self.assertRaises(Blocked):self.invoke(paths=[n for n in PATHS if n!='docs/requirement-status.md'])
    def test_missing_or_unbound_changed_intent_rejected(self):
        with self.assertRaises(Blocked):self.invoke(records=[])
        broken=deepcopy(self.records);broken[0]['artifacts'][GUIDE]['after_sha256']='0'*64
        with self.assertRaises(Blocked):self.invoke(records=broken)
    def test_wrong_existing_baseline_rejected(self):
        old=self.scope['_before'];self.scope['_before']=lambda source,base,name:b'foreign' if name==ENTRY else self.original.get(name)
        try:
            with self.assertRaises(Blocked):self.invoke()
        finally:self.scope['_before']=old
    def test_guide_must_be_absent_in_public_baseline(self):
        old=self.scope['_before'];self.scope['_before']=lambda source,base,name:b'existing guide' if name==GUIDE else self.original.get(name)
        try:
            with self.assertRaises(Blocked):self.invoke()
        finally:self.scope['_before']=old
    def test_other_owner_reference_and_plain_prose_not_admitted(self):
        self.assertIsNone(self.invoke(owner='skills/other'))
        with self.assertRaises(Blocked):self.invoke(name=OWNER+'/references/other.md')
        self.assertIsNone(self.invoke(row={'basis':'user-correction','change_kind':'add-or-change'}))
    def test_behavior_claim_cannot_use_maintenance(self):
        with self.assertRaises(Blocked):self.invoke(row={'basis':'user-correction','change_kind':'contract-correction','behavior_measurements':[]})

if __name__=='__main__':unittest.main()
