import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import install
import evaluation_runtime


class HermesNativeSelection(unittest.TestCase):
    def test_selected_runtime_is_used_without_lazy_install(self):
        selected = Path('selected-runtime/python.exe')
        source = Path('native-source')
        value = {'names': ['required'], 'body_reads': {'required': True}, 'root_configured': True}
        with patch.object(evaluation_runtime, 'native_executable', return_value='hermes-native'), \
             patch.object(evaluation_runtime, 'native_hermes_runtime', return_value=(selected, source)) as resolver, \
             patch.object(install.subprocess, 'run', return_value=SimpleNamespace(returncode=0, stdout=json.dumps(value))) as run:
            result = install.verify_fleet_discovery('hermes', Path('root'), ['required'], ['retired'])
        self.assertTrue(result['verified'])
        resolver.assert_called_once_with('hermes-native')
        args, options = run.call_args
        self.assertEqual(args[0][0], str(selected))
        self.assertEqual(args[0][4], str(source))
        self.assertEqual(options['env']['HERMES_DISABLE_LAZY_INSTALLS'], '1')
        self.assertEqual(result['runtime_python'], str(selected))

    def test_missing_cli_and_broken_selection_never_fall_back(self):
        for executable in (None, 'hermes-native'):
            with self.subTest(executable=executable), \
                 patch.object(evaluation_runtime, 'native_executable', return_value=executable), \
                 patch.object(evaluation_runtime, 'native_hermes_runtime', side_effect=ValueError('broken native selection')) as resolver, \
                 patch.object(install.subprocess, 'run') as run:
                result = install.verify_fleet_discovery('hermes', Path('root'), ['required'], [])
                self.assertFalse(result['verified'])
                run.assert_not_called()
                self.assertEqual(resolver.call_count, int(executable is not None))

    def test_selected_runtime_still_rejects_wrong_catalogue_body_or_root(self):
        for value in (
            {'names': [], 'body_reads': {'required': True}, 'root_configured': True},
            {'names': ['required'], 'body_reads': {'required': False}, 'root_configured': True},
            {'names': ['required'], 'body_reads': {'required': True}, 'root_configured': False},
            {'names': ['required', 'retired'], 'body_reads': {'required': True}, 'root_configured': True},
        ):
            with self.subTest(value=value), \
                 patch.object(evaluation_runtime, 'native_executable', return_value='hermes-native'), \
                 patch.object(evaluation_runtime, 'native_hermes_runtime', return_value=(Path('selected'), Path('source'))), \
                 patch.object(install.subprocess, 'run', return_value=SimpleNamespace(returncode=0, stdout=json.dumps(value))):
                self.assertFalse(install.verify_fleet_discovery('hermes', Path('root'), ['required'], ['retired'])['verified'])


if __name__ == '__main__':
    unittest.main()
