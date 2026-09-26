"""Scoped fleet updates and concurrent-file/state preservation."""
from pathlib import Path
import importlib.util, json, tempfile, unittest
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('candidate', ROOT / 'tools/fleet.py')
fleet = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fleet)

class ScopedFleetTests(unittest.TestCase):

    def fixture(self, root):
        repo = root / 'repo'
        for name in ('chosen', 'other'):
            (repo / 'skills' / name).mkdir(parents=True)
            (repo / 'skills' / name / 'SKILL.md').write_text(name)
        (repo / 'registry.json').write_text(json.dumps({'schema_version': 1, 'skills': [{'name': n, 'status': 'admitted'} for n in ('chosen', 'other')]}))
        out = repo / 'render/fleet'
        fleet.render_snapshot(repo, out)
        dest = root / 'live'
        fleet.apply_snapshot(out, dest)
        return (repo, out, dest)

    def test_scoped_overlay_and_apply_preserve_unrelated_dirty_source_live_and_state(self):
        with tempfile.TemporaryDirectory() as t:
            repo, out, dest = self.fixture(Path(t))
            before = json.loads((dest / fleet.STATE_FILE).read_text())['skills']['other']
            record = fleet.load_manifest(out)['skills']['other']
            (repo / 'skills/chosen/SKILL.md').write_text('selected new')
            (repo / 'skills/other/SKILL.md').write_text('unapproved source')
            (dest / 'other/SKILL.md').write_text('local edit')
            fleet.render_snapshot(repo, out, names={'chosen'})
            self.assertEqual(fleet.load_manifest(out)['skills']['other'], record)
            self.assertEqual((out / 'skills/other/SKILL.md').read_text(), 'other')
            actions = fleet.apply_snapshot(out, dest, names={'chosen'})
            self.assertEqual({a['name'] for a in actions}, {'chosen'})
            self.assertEqual((dest / 'other/SKILL.md').read_text(), 'local edit')
            self.assertEqual(json.loads((dest / fleet.STATE_FILE).read_text())['skills']['other'], before)
            self.assertEqual(fleet.verify_snapshot(out, dest, names={'chosen'}), [])
            self.assertTrue(fleet.verify_snapshot(out, dest))

    def test_scope_rejects_missing_staged_and_invalid_names(self):
        with tempfile.TemporaryDirectory() as t:
            repo, out, dest = self.fixture(Path(t))
            data = json.loads((repo / 'registry.json').read_text())
            data['skills'][0]['status'] = 'staged'
            (repo / 'registry.json').write_text(json.dumps(data))
            for names in ({'chosen'}, {'missing'}, {'../escape'}):
                with self.assertRaises(RuntimeError):
                    fleet.render_snapshot(repo, out, names=names)
            with self.assertRaises(RuntimeError):
                fleet.apply_snapshot(out, dest, names={'missing'})

    def test_destination_race_during_staging_preserves_concurrent_edit(self):
        with tempfile.TemporaryDirectory() as t:
            repo, out, dest = self.fixture(Path(t))
            (repo / 'skills/chosen/SKILL.md').write_text('new')
            fleet.render_snapshot(repo, out, names={'chosen'})
            original = fleet.shutil.copytree

            def racing(*args, **kwargs):
                result = original(*args, **kwargs)
                (dest / 'chosen/SKILL.md').write_text('concurrent')
                return result
            with patch.object(fleet.shutil, 'copytree', side_effect=racing), self.assertRaisesRegex(RuntimeError, 'destination changed'):
                fleet.apply_snapshot(out, dest, names={'chosen'})
            self.assertEqual((dest / 'chosen/SKILL.md').read_text(), 'concurrent')
            self.assertFalse(list(dest.glob('.*.fleet-old-*')))

    def test_state_race_preserves_new_state(self):
        with tempfile.TemporaryDirectory() as t:
            repo, out, dest = self.fixture(Path(t))
            (repo / 'skills/chosen/SKILL.md').write_text('new')
            fleet.render_snapshot(repo, out, names={'chosen'})
            original = fleet.shutil.copytree

            def racing(*args, **kwargs):
                result = original(*args, **kwargs)
                (dest / fleet.STATE_FILE).write_text(json.dumps({'schema_version': 1, 'skills': {}, 'concurrent': True}))
                return result
            with patch.object(fleet.shutil, 'copytree', side_effect=racing), self.assertRaisesRegex(RuntimeError, 'managed state changed'):
                fleet.apply_snapshot(out, dest, names={'chosen'})
            self.assertTrue(json.loads((dest / fleet.STATE_FILE).read_text())['concurrent'])
            self.assertEqual((dest / 'chosen/SKILL.md').read_text(), 'chosen')

    def test_rollback_conflict_retains_backup_and_concurrent_edit(self):
        with tempfile.TemporaryDirectory() as t:
            repo, out, dest = self.fixture(Path(t))
            (repo / 'skills/chosen/SKILL.md').write_text('new')
            fleet.render_snapshot(repo, out, names={'chosen'})

            def failed_state(*args, **kwargs):
                (dest / 'chosen/SKILL.md').write_text('concurrent after install')
                raise OSError('state failed')
            with patch.object(fleet, 'atomic_json', side_effect=failed_state), self.assertRaisesRegex(RuntimeError, 'rollback conflict'):
                fleet.apply_snapshot(out, dest, names={'chosen'})
            self.assertEqual((dest / 'chosen/SKILL.md').read_text(), 'concurrent after install')
            backups = list(dest.glob('.chosen.fleet-old-*'))
            self.assertEqual(len(backups), 1)
            self.assertEqual((backups[0] / 'SKILL.md').read_text(), 'chosen')

    def test_scoped_preflight_ignores_other_drift_but_rejects_selected_collision(self):
        with tempfile.TemporaryDirectory() as t:
            repo, out, dest = self.fixture(Path(t))
            other = Path(t) / 'second'
            other.mkdir()
            (dest / 'other/SKILL.md').write_text('unrelated drift')
            (other / 'chosen').write_text('collision')
            with self.assertRaisesRegex(RuntimeError, 'collision'):
                fleet.apply_destinations(out, [dest, other], names={'chosen'})
            self.assertEqual((dest / 'other/SKILL.md').read_text(), 'unrelated drift')

    def test_scoped_apply_preserves_retired_managed_record(self):
        with tempfile.TemporaryDirectory() as t:
            repo, out, dest = self.fixture(Path(t))
            before = json.loads((dest / fleet.STATE_FILE).read_text())['skills']['other']
            data = json.loads((repo / 'registry.json').read_text())
            data['skills'][1]['status'] = 'staged'
            (repo / 'registry.json').write_text(json.dumps(data))
            fleet.render_snapshot(repo, out)
            fleet.apply_snapshot(out, dest, names={'chosen'})
            self.assertEqual(json.loads((dest / fleet.STATE_FILE).read_text())['skills']['other'], before)
            self.assertTrue((dest / 'other/SKILL.md').exists())
            self.assertEqual(fleet.verify_snapshot(out, dest, names={'chosen'}), [])

    def test_render_does_not_overwrite_nested_snapshot_edit_during_staging(self):
        with tempfile.TemporaryDirectory() as t:
            repo, out, dest = self.fixture(Path(t))
            (repo / 'skills/chosen/SKILL.md').write_text('selected new')
            nested = out / 'skills/chosen/SKILL.md'
            original = fleet.atomic_json

            def write(path, data):
                original(path, data)
                if path.name == fleet.MANIFEST_FILE and path.parent.name.startswith('.fleet.stage-'):
                    nested.write_text('concurrent snapshot edit')
            with patch.object(fleet, 'atomic_json', side_effect=write), self.assertRaisesRegex(RuntimeError, 'destination changed'):
                fleet.render_snapshot(repo, out, names={'chosen'})
            self.assertEqual('concurrent snapshot edit', nested.read_text())

    def test_generic_directory_identity_binds_nested_files_without_skill(self):
        with tempfile.TemporaryDirectory() as t:
            directory = Path(t) / 'aggregate'
            nested = directory / 'nested'
            nested.mkdir(parents=True)
            file = nested / 'artifact.json'
            file.write_text('before')
            identity = fleet.path_identity(directory)
            file.write_text('after')
            self.assertNotEqual(identity, fleet.path_identity(directory))

    def test_managed_state_changed_while_reading_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as t:
            repo, out, dest = self.fixture(Path(t))
            (repo / 'skills/chosen/SKILL.md').write_text('selected new')
            fleet.render_snapshot(repo, out, names={'chosen'})
            original = fleet.load_state

            def read(path):
                state = original(path)
                updated = dict(state)
                updated['actor'] = 'concurrent state'
                (dest / fleet.STATE_FILE).write_text(json.dumps(updated))
                return state
            with patch.object(fleet, 'load_state', side_effect=read), self.assertRaisesRegex(RuntimeError, 'while reading'):
                fleet.apply_snapshot(out, dest, names={'chosen'})
            self.assertEqual('concurrent state', json.loads((dest / fleet.STATE_FILE).read_text())['actor'])
            self.assertEqual('chosen', (dest / 'chosen/SKILL.md').read_text())
if __name__ == '__main__':
    unittest.main()
