"""Source-bound, file-free controls for the closed curator maintenance route."""
import ast,hashlib,os,subprocess,unittest
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[1]
BASE='88f7c44dab8bf1f0f7ba942d83da501de6b01d67'
REPO=Path(os.environ.get('AGENT_SYNC_TEST_BASELINE',ROOT))
PRODUCTS=['skills/capability-curator/SKILL.md','skills/capability-curator/references/instruction-retirement.md',
          'skills/cross-agent-surface-engineering/SKILL.md']
CONTRACTS=['docs/system-requirements.md','docs/requirement-status.md']
FIXED=['registry.json','contracts/ownership.json','contracts/instruction-surfaces.json']
class Blocked(RuntimeError):pass
class Bytes:
    def __init__(self,data,name=''):self.data,self.name=data,name
    def __truediv__(self,name):return Bytes(self.data,name)
    def is_file(self):return self.name in self.data
    def read_bytes(self):return self.data[self.name]
def identity(b):return hashlib.sha256(b).hexdigest() if b is not None else 'absent'
class Controls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.before={n:subprocess.run(['git','-C',str(REPO),'show',BASE+':'+n],capture_output=True,check=True).stdout for n in PRODUCTS+CONTRACTS+FIXED}
        cls.after={n:(ROOT/n).read_bytes() for n in cls.before}
        tree=ast.parse((ROOT/'tools/instruction_changes.py').read_text(encoding='utf-8'))
        names={'_hash','_approved_curator_scope_maintenance','correction_eligibility'}
        nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names or
            isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='CONTRACTS' for t in n.targets)]
        cls.scope={'hashlib':hashlib,'sync_git':SimpleNamespace(SyncBlocked=Blocked),'_before':lambda source,base,n:cls.before.get(n)}
        exec(compile(ast.Module(body=nodes,type_ignores=[]),'<actual-curator-dispatcher>','exec'),cls.scope)
        cls.row={'basis':'user-correction','change_kind':'contract-correction','acceptance_classification':'curator-scope-maintenance'}
        cls.records=[{'requirement_change':True,'artifacts':{n:{'before_sha256':identity(cls.before[n]),'after_sha256':identity(cls.after[n])} for n in PRODUCTS+CONTRACTS}}]
    def invoke(self,name=None,owner=None,data=None,row=None,records=None,paths=None):
        name=name or PRODUCTS[0]
        return self.scope['correction_eligibility'](Bytes(self.after if data is None else data),None,name,
            owner or 'skills/'+name.split('/')[1],self.row if row is None else row,BASE,
            PRODUCTS+CONTRACTS if paths is None else paths,self.records if records is None else records)
    def test_exact_three_products_accepted_without_benefit_or_authority_claim(self):
        for name in PRODUCTS:
            r=self.invoke(name=name);self.assertTrue(r['eligible']);self.assertFalse(r['behavioral_proof']);self.assertFalse(r['approval_authenticated'])
    def test_any_changed_product_or_contract_rejects(self):
        for name in PRODUCTS+CONTRACTS:
            with self.subTest(name=name),self.assertRaises(Blocked):self.invoke(data=dict(self.after,**{name:self.after[name]+b'changed'}))
    def test_lifecycle_or_owner_index_change_rejects(self):
        for name in FIXED:
            with self.subTest(name=name),self.assertRaises(Blocked):self.invoke(data=dict(self.after,**{name:self.after[name]+b'changed'}))
    def test_missing_selection_or_reconciliation_rejects(self):
        for name in PRODUCTS+CONTRACTS:
            with self.subTest(name=name),self.assertRaises(Blocked):self.invoke(paths=[n for n in PRODUCTS+CONTRACTS if n!=name])
        with self.assertRaises(Blocked):self.invoke(records=[])
    def test_rehashed_record_does_not_authorize_another_body(self):
        changed=dict(self.after);changed[PRODUCTS[0]]+=b'other'
        records=deepcopy(self.records);records[0]['artifacts'][PRODUCTS[0]]['after_sha256']=identity(changed[PRODUCTS[0]])
        with self.assertRaises(Blocked):self.invoke(data=changed,records=records)
    def test_wrong_baseline_or_duplicate_changed_intent_rejects(self):
        original=self.scope['_before'];self.scope['_before']=lambda source,base,n:b'foreign' if n==PRODUCTS[0] else self.before.get(n)
        try:
            with self.assertRaises(Blocked):self.invoke()
        finally:self.scope['_before']=original
        with self.assertRaises(Blocked):self.invoke(records=self.records*2)
    def test_other_owner_plain_prose_and_benefit_fields_are_not_waived(self):
        self.assertIsNone(self.invoke(owner='skills/other'))
        self.assertIsNone(self.invoke(row={'basis':'user-correction','change_kind':'add-or-change'}))
        for name in ('behavior_measurements','task_contract'):
            with self.subTest(name=name),self.assertRaises(Blocked):self.invoke(row=dict(self.row,**{name:[]}))
    def test_existing_closed_guard_helpers_are_unchanged(self):
        old=subprocess.run(['git','-C',str(REPO),'show',BASE+':tools/instruction_changes.py'],capture_output=True,check=True).stdout
        before=ast.parse(old);after=ast.parse((ROOT/'tools/instruction_changes.py').read_bytes())
        old_functions={n.name:ast.dump(n) for n in before.body if isinstance(n,ast.FunctionDef)}
        new_functions={n.name:ast.dump(n) for n in after.body if isinstance(n,ast.FunctionDef)}
        for name,node in old_functions.items():
            if name!='correction_eligibility':self.assertEqual(node,new_functions[name],name)
if __name__=='__main__':unittest.main()
