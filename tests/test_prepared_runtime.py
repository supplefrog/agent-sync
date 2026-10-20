"""Owned runtime preparation only: fake native process, no live/auth call."""
from fixture_workspace import configure as configure_test_workspace
configure_test_workspace()
import json,tempfile,unittest
from pathlib import Path
from unittest import mock
import test_evaluation_runtime as fixtures
runtime=fixtures.runtime

class PreparedRuntimeTests(unittest.TestCase):
    fake_native=fixtures.EvaluationRuntimeTests.fake_native

    def test_explicit_prepared_root_preserves_isolation_controls_and_cleanup(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); prepared=root/'prepared'; prepared.mkdir()
            result,record=self.fake_native(root,'hermes',prepared_runtime=prepared)
            self.assertTrue(result['ok'],result)
            contract=result['runtime_contract']; self.assertEqual(contract['owned_runtime_directory'],str(prepared))
            self.assertEqual(contract['runtime_directory_source'],'explicit-prepared-directory')
            self.assertTrue(contract['controls']['ignore_user_config'])
            self.assertTrue(contract['controls']['credentials_in_memory_only'])
            self.assertTrue(result['route_attestation']['required'])
            payload=json.loads(record['process'].communicate.call_args.kwargs['input'])
            self.assertEqual(Path(payload['runtime_home']),prepared/'hermes')
            self.assertNotEqual(payload['credential_owner_home'],payload['runtime_home'])
            self.assertEqual(record['launches'][0][1]['HERMES_DISABLE_LAZY_INSTALLS'],'1')
            self.assertTrue(contract['cleanup']['state_removed']); self.assertFalse(prepared.exists())

    def test_nonempty_or_fixture_directory_is_rejected_without_mutation(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); fixture=root/'fixture'; fixture.mkdir(); nonempty=root/'prepared'; nonempty.mkdir()
            marker=nonempty/'keep'; marker.write_text('unchanged')
            for candidate in (nonempty,fixture,Path('relative-runtime')):
                with self.subTest(candidate=str(candidate)),mock.patch.object(runtime,'runtime_access_preflight') as preflight:
                    with self.assertRaises(ValueError):runtime.prepared_runtime_directory(candidate,fixture)
                    preflight.assert_not_called()
            self.assertEqual(marker.read_text(),'unchanged')

    def test_preflight_failure_records_owned_path_and_does_not_launch_or_retry(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); prepared=root/'prepared'; prepared.mkdir()
            cleanup={'credentials_removed':True,'state_removed':False,'errors':['synthetic cleanup denial']}
            with mock.patch.object(runtime,'runtime_access_preflight',side_effect=PermissionError('synthetic denied operation')) as access, mock.patch.object(runtime,'cleanup_runtime',return_value=cleanup) as remove:
                result,record=self.fake_native(root,'hermes',prepared_runtime=prepared)
            access.assert_called_once_with(prepared); remove.assert_called_once()
            self.assertEqual(record['launches'],[])
            self.assertEqual(result['failure']['code'],'PermissionError')
            self.assertEqual(result['runtime_contract']['setup_operation'],'runtime-access-preflight')
            self.assertEqual(result['runtime_contract']['owned_runtime_directory'],str(prepared))
            self.assertFalse(result['runtime_contract']['cleanup']['state_removed'])
            self.assertFalse(result['operational_ok'])

    def test_prepared_claim_is_exclusive_even_if_empty_check_races(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); fixture=root/'fixture'; fixture.mkdir(); prepared=root/'prepared'; prepared.mkdir()
            runtime.prepared_runtime_directory(prepared,fixture)
            marker=prepared/'.agent-signal-runtime-owner'; before=marker.read_bytes()
            with mock.patch.object(Path,'iterdir',return_value=iter(())):
                with self.assertRaises(FileExistsError):runtime.prepared_runtime_directory(prepared,fixture)
            self.assertEqual(marker.read_bytes(),before)

    def test_denied_default_allocation_has_no_prepared_root_fallback(self):
        with tempfile.TemporaryDirectory() as temp:
            record={}
            with mock.patch.object(runtime.tempfile,'mkdtemp',side_effect=PermissionError('synthetic allocation denial')) as allocate:
                with self.assertRaises(PermissionError):self.fake_native(Path(temp),'hermes',record_out=record)
            allocate.assert_called_once(); self.assertEqual(record['launches'],[])

    def test_environment_setup_failure_is_distinct_from_access_preflight(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); prepared=root/'prepared'; prepared.mkdir()
            with mock.patch.object(runtime,'runtime_environment',side_effect=PermissionError('synthetic child creation denial')):
                result,record=self.fake_native(root,'hermes',prepared_runtime=prepared)
            self.assertEqual(record['launches'],[])
            self.assertEqual(result['runtime_contract']['setup_operation'],'runtime-environment')
            self.assertEqual(result['failure']['code'],'PermissionError')
            self.assertTrue(result['runtime_contract']['cleanup']['state_removed'])

if __name__=='__main__':unittest.main()
