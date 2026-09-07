"""Concrete filesystem and identity regressions from the neutral source review."""
import hashlib,importlib.util,json,tempfile,unittest
from pathlib import Path
from unittest import mock
from test_fleet import load_fleet,fixture_repo

class FleetRefutationTests(unittest.TestCase):
    def test_render_rejects_source_control_and_unowned_output_without_mutation(self):
        for relative in ('skills','registry.json','.git','unrelated'):
            with self.subTest(relative=relative),tempfile.TemporaryDirectory() as temp:
                repo=fixture_repo(Path(temp));fleet=load_fleet()
                (repo/'.git').mkdir();(repo/'.git'/'HEAD').write_text('synthetic control',encoding='utf-8')
                (repo/'unrelated').mkdir();(repo/'unrelated'/'keep.txt').write_text('synthetic user file',encoding='utf-8')
                before={str(p.relative_to(repo)):p.read_bytes() for p in repo.rglob('*') if p.is_file()}
                with self.assertRaises(RuntimeError): fleet.render_snapshot(repo,repo/relative)
                after={str(p.relative_to(repo)):p.read_bytes() for p in repo.rglob('*') if p.is_file()}
                self.assertEqual(after,before)

    def test_render_rejects_snapshot_with_unowned_extra_file(self):
        with tempfile.TemporaryDirectory() as temp:
            repo=fixture_repo(Path(temp));fleet=load_fleet();out=repo/'render'/'fleet'
            fleet.render_snapshot(repo,out);(out/'keep.txt').write_text('unmanaged',encoding='utf-8')
            with self.assertRaises(RuntimeError): fleet.render_snapshot(repo,out)
            self.assertEqual((out/'keep.txt').read_text(encoding='utf-8'),'unmanaged')

    def test_render_source_copy_race_does_not_commit_wrong_identity(self):
        with tempfile.TemporaryDirectory() as temp:
            repo=fixture_repo(Path(temp));fleet=load_fleet();out=repo/'render'/'fleet'
            original=fleet.shutil.copytree
            def changing_copy(source,target,**kwargs):
                (Path(source)/'SKILL.md').write_text('changed after source validation',encoding='utf-8')
                return original(source,target,**kwargs)
            with mock.patch.object(fleet.shutil,'copytree',side_effect=changing_copy),self.assertRaises(RuntimeError):
                fleet.render_snapshot(repo,out)
            self.assertFalse(out.exists())
            self.assertEqual(list((repo/'render').glob('.*.stage-*')),[])

    def test_render_registry_selection_and_identity_share_one_read(self):
        with tempfile.TemporaryDirectory() as temp:
            repo=fixture_repo(Path(temp));fleet=load_fleet();out=repo/'render'/'fleet'
            raw=(repo/'registry.json').read_bytes();original=fleet.shutil.copytree
            def changing_copy(source,target,**kwargs):
                changed=json.loads(raw);changed['skills'][1]['status']='admitted'
                (repo/'registry.json').write_text(json.dumps(changed),encoding='utf-8')
                return original(source,target,**kwargs)
            with mock.patch.object(fleet.shutil,'copytree',side_effect=changing_copy): result=fleet.render_snapshot(repo,out)
            self.assertEqual(set(result['skills']),{'kept'})
            self.assertEqual(result['registry_sha256'],hashlib.sha256(raw).hexdigest())

    def test_apply_copy_race_preserves_destination(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);repo=fixture_repo(root);fleet=load_fleet();out=repo/'render'/'fleet';dest=root/'live'
            fleet.render_snapshot(repo,out);original=fleet.shutil.copytree
            def changing_copy(source,target,**kwargs):
                result=original(source,target,**kwargs)
                (Path(target)/'SKILL.md').write_text('changed staged bytes',encoding='utf-8');return result
            with mock.patch.object(fleet.shutil,'copytree',side_effect=changing_copy),self.assertRaises(RuntimeError):
                fleet.apply_snapshot(out,dest)
            self.assertEqual(list(dest.iterdir()),[])

    def test_partial_copy_stage_is_cleaned(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);repo=fixture_repo(root);fleet=load_fleet();out=repo/'render'/'fleet';dest=root/'live'
            fleet.render_snapshot(repo,out)
            def partial_copy(source,target,**kwargs):
                Path(target).mkdir();(Path(target)/'partial').write_text('partial',encoding='utf-8');raise OSError('synthetic copy failure')
            with mock.patch.object(fleet.shutil,'copytree',side_effect=partial_copy),self.assertRaises(OSError): fleet.apply_snapshot(out,dest)
            self.assertEqual(list(dest.iterdir()),[])

    def test_apply_manifest_identity_uses_the_planned_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);repo=fixture_repo(root);fleet=load_fleet();out=repo/'render'/'fleet';dest=root/'live'
            fleet.render_snapshot(repo,out);raw=(out/'manifest.json').read_bytes();original=fleet.shutil.copytree
            def changing_copy(source,target,**kwargs):
                changed=json.loads(raw);changed['registry_sha256']='f'*64
                (out/'manifest.json').write_text(json.dumps(changed),encoding='utf-8')
                return original(source,target,**kwargs)
            with mock.patch.object(fleet.shutil,'copytree',side_effect=changing_copy): fleet.apply_snapshot(out,dest)
            state=json.loads((dest/fleet.STATE_FILE).read_text(encoding='utf-8'))
            self.assertEqual(state['manifest_sha256'],hashlib.sha256(raw).hexdigest())

    def test_failed_install_rename_stage_is_cleaned(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);repo=fixture_repo(root);fleet=load_fleet();out=repo/'render'/'fleet';dest=root/'live'
            fleet.render_snapshot(repo,out);original=fleet.os.replace
            def failed_replace(source,target):
                if '.fleet-stage-' in str(source): raise OSError('synthetic install rename failure')
                return original(source,target)
            with mock.patch.object(fleet.os,'replace',side_effect=failed_replace),self.assertRaises(OSError): fleet.apply_snapshot(out,dest)
            self.assertEqual(list(dest.iterdir()),[])

    def test_directory_symlink_is_unlinked_not_rmdir(self):
        fleet=load_fleet();path=mock.Mock()
        path.exists.return_value=True;path.is_symlink.return_value=True;path.is_dir.return_value=True
        with mock.patch.object(fleet,'is_linklike_directory',return_value=True),mock.patch.object(fleet.os,'rmdir') as rmdir:
            fleet.remove_tree(path)
        path.unlink.assert_called_once();rmdir.assert_not_called()

class StandaloneIdentityTests(unittest.TestCase):
    def test_nul_in_standalone_text_cannot_alias_linked_layout(self):
        spec=importlib.util.spec_from_file_location('framing_hash',Path(__file__).resolve().parents[1]/'tools'/'artifact_hash.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as temp:
            a,b=(Path(temp)/name for name in ('a','b'));a.mkdir();b.mkdir()
            p=b'Read [details](details.md).';q=b'a rule'
            (a/'candidate.md').write_bytes(p);(a/'details.md').write_bytes(q)
            (b/'candidate.md').write_bytes(p+b'\0details.md\0'+q)
            self.assertNotEqual(module.candidate_hash(a/'candidate.md'),module.candidate_hash(b/'candidate.md'))

if __name__=='__main__': unittest.main()
