from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import recovery


class OMPRecoveryAuthTests(unittest.TestCase):
    def test_single_default_omp_root_uses_user_home_for_portable_paths(self):
        home = Path.cwd() / 'fixture-home'
        root = home / '.omp' / 'agent'
        self.assertEqual(home, recovery._logical_home({'omp': root}))
        replacements = recovery._path_replacements({'omp': root})
        original = str(home / 'AppData' / 'Local' / 'tool.cmd')
        normalized = recovery._normalize(original, replacements)
        self.assertIn('{{agent-signal:HOME}}', normalized)
        self.assertNotIn(str(home), normalized)

    def test_arbitrary_omp_root_keeps_declared_root_semantics(self):
        root = Path.cwd() / 'fixture-profile'
        self.assertEqual(root, recovery._logical_home({'omp': root}))

    def test_oauth_transport_selector_is_recoverable(self):
        self.assertFalse(recovery._secret_path('providers.openai-codex.auth'))
        recovery._assert_no_secret_paths('oauth', 'providers.openai-codex.auth')
        recovery._assert_no_secret_paths({'providers': {'openai-codex': {'auth': 'oauth'}}}, '')

    def test_auth_exception_cannot_capture_credential_state(self):
        for value in ['api-key', 'arbitrary credential', {'token': 'value'}, ['oauth'], True, None]:
            with self.subTest(value_type=type(value).__name__):
                with self.assertRaisesRegex(recovery.RecoveryError, 'only the oauth'):
                    recovery._assert_no_secret_paths(value, 'providers.openai-codex.auth')
        self.assertTrue(recovery._secret_path('providers.other.auth'))
        self.assertTrue(recovery._secret_path('providers.openai-codex.auth.token'))


if __name__ == '__main__':
    unittest.main()
