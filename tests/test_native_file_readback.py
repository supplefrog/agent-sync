"""Exact native-file observations for recoverable local source patches."""
from pathlib import Path
import hashlib
import importlib.util
import json
import tempfile
import unittest

REPO=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('native_readback_tool',REPO/'tools/host_deltas.py')
tool=importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)


class NativeFileReadbackTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        (self.root/'contracts').mkdir()
        (self.root/'contracts/host-deltas.schema.json').write_bytes((REPO/'contracts/host-deltas.schema.json').read_bytes())
        patch=b'synthetic recovery delta'
        (self.root/'repair.patch').write_bytes(patch)
        self.native=self.root/'native.py'
        self.native.write_bytes(b'expected native bytes')
        self.entry={'id':'synthetic-native','host':'hermes','category':'plugin','owner':'native-source',
                    'source_identity':'repository:repair.patch','version_or_hash':'sha256:'+hashlib.sha256(patch).hexdigest(),
                    'enablement':'installed','prerequisites':[],'desired_state':'Exact native source present','required':True,
                    'restore':{'kind':'manual-prerequisite','reference':'apply the declared source patch'},
                    'readback':{'kind':'file','path':'hermes:native.py','sha256':hashlib.sha256(self.native.read_bytes()).hexdigest()},
                    'redaction':'public-artifact'}

    def verify(self, *, restored=False):
        path=self.root/'host-deltas.json'
        path.write_text(json.dumps({'schema_version':1,'machine':'synthetic','public_safe':True,'entries':[self.entry],'exclusions':[]}),encoding='utf-8')
        def no_command(_):
            raise AssertionError('File verification must not launch a process')
        return tool.verify(path,self.root,roots={'hermes':self.root},runner=no_command,restored_ids={'synthetic-native'} if restored else set())

    def test_expected_bytes_verify(self):
        self.assertTrue(self.verify()['passed'])

    def test_existing_file_with_wrong_bytes_fails(self):
        self.native.write_bytes(b'wrong but present bytes')
        result=self.verify()
        self.assertFalse(result['passed'])
        self.assertEqual('failed',result['entries'][0]['status'])

    def test_restored_marker_cannot_hide_drift(self):
        self.native.write_bytes(b'wrong but present bytes')
        self.assertFalse(self.verify(restored=True)['passed'])

    def test_missing_file_fails(self):
        self.native.unlink()
        self.assertFalse(self.verify()['passed'])

    def test_legacy_presence_readback_remains_compatible(self):
        self.entry['readback'].pop('sha256')
        self.native.write_bytes(b'legacy arbitrary bytes')
        self.assertTrue(self.verify()['passed'])

    def test_text_predicate_still_applies_after_hash(self):
        self.entry['readback']['contains']='not in expected bytes'
        self.assertFalse(self.verify()['passed'])

    def test_malformed_hash_or_non_file_hash_is_rejected(self):
        for value in ('0'*63,'G'*64,True):
            with self.subTest(hash=value):
                self.entry['readback']['sha256']=value
                with self.assertRaisesRegex(RuntimeError,'host-delta schema'):
                    self.verify()
        self.entry['readback']={'kind':'none','sha256':'0'*64}
        with self.assertRaisesRegex(RuntimeError,'host-delta schema'):
            self.verify()

if __name__=='__main__':
    unittest.main()
