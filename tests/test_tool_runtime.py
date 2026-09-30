from pathlib import Path
import importlib.util
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("agent_sync_run", REPO / "tools/run.py")
run = importlib.util.module_from_spec(spec)
spec.loader.exec_module(run)


class ToolRuntimeTests(unittest.TestCase):
    def test_declared_runtime_is_preferred_and_checked_once(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            python = root / ".venv/Scripts/python.exe"
            python.parent.mkdir(parents=True)
            python.touch()
            with mock.patch.object(run.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)) as probe:
                self.assertEqual(str(python), run.runtime(root))
                probe.assert_called_once()
                self.assertEqual(str(python), probe.call_args.args[0][0])

    def test_existing_runtime_without_dependencies_fails_without_install(self):
        with mock.patch.object(run.subprocess, "run", return_value=subprocess.CompletedProcess([], 1)) as probe:
            with self.assertRaisesRegex(RuntimeError, "no dependencies were installed"):
                run.runtime(Path("nonexistent-runtime-fixture"))
            probe.assert_called_once()

    def test_rejects_traversal_or_unknown_tool_before_running(self):
        for name in ("../reconcile", "C:/reconcile", "not_a_real_tool", "run"):
            with self.subTest(name=name), mock.patch.object(run.subprocess, "run") as invoke:
                with self.assertRaises(SystemExit):
                    run.main([name])
                invoke.assert_not_called()

    def test_real_launcher_resolves_declared_dependencies_and_forwards_help(self):
        result = subprocess.run([sys.executable, "-B", str(REPO / "tools/run.py"), "reconcile", "--help"], capture_output=True, text=True)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("--capture-artifact", result.stdout)
