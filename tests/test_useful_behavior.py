import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
import sys

REPO=Path(os.environ.get('AGENT_SYNC_TEST_REPO',Path(__file__).resolve().parents[1]))
sys.path.insert(0,str(REPO/'tools'))
SOURCE=Path(os.environ.get('USEFUL_BEHAVIOR_SOURCE',REPO/'tools/useful_behavior.py'))
spec=importlib.util.spec_from_file_location('useful_behavior',SOURCE)
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

class UsefulBehaviorTests(unittest.TestCase):
    def sources(self,root):
        source=root/'docs-source';(source/'references').mkdir(parents=True)
        (source/'SKILL.md').write_text('---\nname: docs-source\ndescription: Use for docs procedures.\nlicense: MIT\n---\n# Procedure\n\nPreserve the exact requested model rather than choosing a different model.\n\nRead [the route](references/route.md) only when migration is requested.\n')
        (source/'references/route.md').write_text('# Model route\n\nVerify representative behavior and compatibility before calling migration complete.\n')
        candidate=root/'candidate.md';candidate.write_text('Use official web pages for information.\n')
        return source/'SKILL.md',candidate
    def test_website_and_name_are_not_procedure_preservation(self):
        with tempfile.TemporaryDirectory() as temp:
            source,candidate=self.sources(Path(temp))
            candidate.write_text('docs-source may help. See https://example.org/docs.\n')
            r=module.compare_sources(candidate,[source]);s=r['sources'][0]
            self.assertEqual(s['candidate_relationship_hint'],'named-source-only')
            self.assertIn('Make source reuse concrete',s['recommendation']['suggestion'])
            self.assertTrue(any(c['source_file']=='references/route.md' for c in s['behavior_clues']))
            self.assertFalse(r['automatic_semantic_verdict']);self.assertEqual(len(s['alternatives']),4)
    def test_source_reference_can_inherit_without_copying_text(self):
        with tempfile.TemporaryDirectory() as temp:
            source,candidate=self.sources(Path(temp))
            candidate.write_text('Read installed skills/docs-source/SKILL.md and its selected supporting files.\n')
            r=module.compare_sources(candidate,[source.parent]);s=r['sources'][0]
            self.assertEqual(s['candidate_relationship_hint'],'concrete-package-reference')
            self.assertTrue(all(c['status']=='verify-inheritance-and-host-fit' for c in s['behavior_clues']))
            self.assertIn('avoid duplicating',s['recommendation']['suggestion'])
            self.assertTrue(s['clues_are_partial'])
    def test_native_source_changes_are_visible_without_source_writes(self):
        with tempfile.TemporaryDirectory() as temp:
            source,candidate=self.sources(Path(temp));before=source.read_bytes()
            a=module.compare_sources(candidate,[source]);self.assertEqual(before,source.read_bytes())
            source.write_bytes(before+b'\nResolve unspecified targets with the current platform helper only when needed.\n')
            b=module.compare_sources(candidate,[source])
            self.assertNotEqual(a['sources'][0]['source_sha256'],b['sources'][0]['source_sha256'])
            self.assertTrue(any('Resolve unspecified' in c['excerpt'] for c in b['sources'][0]['behavior_clues']))
    def test_missing_reference_is_an_explicit_limit(self):
        with tempfile.TemporaryDirectory() as temp:
            source,candidate=self.sources(Path(temp))
            with self.assertRaises(ValueError):module.compare_sources(candidate,[source.parent/'missing.md'])

if __name__=='__main__':unittest.main()
