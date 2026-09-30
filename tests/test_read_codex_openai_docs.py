import importlib.util
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO=Path(__file__).resolve().parents[1]
HELPER=Path(os.environ.get('OPENAI_DOCS_READER',REPO/'recovery/current/hosts/hermes/skills/research/research-source-operations/scripts/read_codex_openai_docs.py'))
spec=importlib.util.spec_from_file_location('docs_reader',HELPER)
reader=importlib.util.module_from_spec(spec);spec.loader.exec_module(reader)

class ReaderTests(unittest.TestCase):
    def package(self,home):
        root=home/'skills/.system/openai-docs';(root/'references').mkdir(parents=True)
        (root/'SKILL.md').write_text('---\nname: "openai-docs"\n---\nRead a selected route.\n')
        (root/'LICENSE.txt').write_text('Apache License 2.0\n')
        (root.parent/'.codex-system-skills.marker').write_text('version-one\n')
        (root/'references/model-migration.md').write_text('Preserve exact model; verify current source.\n')
        return root
    def test_reads_root_and_selected_reference_without_mutation(self):
        with tempfile.TemporaryDirectory() as temp:
            home=Path(temp);root=self.package(home);before={str(p):p.read_bytes() for p in home.rglob('*') if p.is_file()}
            r=reader.read_source(home);self.assertEqual(r['content'],(root/'SKILL.md').read_bytes().decode());self.assertFalse(r['source_copied'])
            r=reader.read_source(home,'references/model-migration.md');self.assertIn('Preserve exact model',r['content']);self.assertFalse(r['source_executed'])
            self.assertEqual(before,{str(p):p.read_bytes() for p in home.rglob('*') if p.is_file()})
    def test_next_read_follows_replaced_installed_package(self):
        with tempfile.TemporaryDirectory() as temp:
            home=Path(temp);root=self.package(home);a=reader.read_source(home)
            (root/'SKILL.md').write_text('---\nname: openai-docs\n---\nNew procedure from new installed bundle.\n')
            (root.parent/'.codex-system-skills.marker').write_text('version-two\n')
            b=reader.read_source(home);self.assertNotEqual(a['file_sha256'],b['file_sha256']);self.assertEqual(b['codex_bundle_marker'],'version-two')
            self.assertIn('New procedure',b['content'])
    def test_missing_source_wrong_package_and_bad_reference_are_explicit(self):
        with tempfile.TemporaryDirectory() as temp:
            home=Path(temp)
            with self.assertRaises((OSError,ValueError)):reader.read_source(home)
            root=self.package(home)
            for path in ['../auth.json','/etc/passwd','LICENSE.txt']:
                with self.assertRaises(ValueError):reader.read_source(home,path)
            (root/'SKILL.md').write_text('---\nname: unrelated\n---\nWrong owner.\n')
            with self.assertRaisesRegex(ValueError,'expected OpenAI'):reader.read_source(home)
    def test_concurrent_update_and_oversize_reads_are_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            home=Path(temp);root=self.package(home)
            with mock.patch.object(reader,'_marker',side_effect=['before','after']):
                with self.assertRaisesRegex(ValueError,'changed during reading'):reader.read_source(home)
            (root/'references/model-migration.md').write_bytes(b'a'*(reader.MAX_BYTES+1))
            with self.assertRaisesRegex(ValueError,'bounded read'):reader.read_source(home,'references/model-migration.md')
    def test_environment_home_is_honored(self):
        with tempfile.TemporaryDirectory() as temp:
            home=Path(temp);root=self.package(home)
            with mock.patch.dict(os.environ,{'CODEX_HOME':str(home)}):
                self.assertEqual(Path(reader.read_source()['path']),root/'SKILL.md')

if __name__=='__main__':unittest.main()
