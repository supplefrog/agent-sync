from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("render_instructions", ROOT / "tools/render_instructions.py")
renderer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(renderer)


class RenderInstructionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)
        for relative in ("surfaces/core.md", "adapters/codex.json", "adapters/hermes.json"):
            target = self.repo / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / relative, target)
        for path, text in renderer.projections(self.repo).values():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(text.encode("utf-8"))

    def test_render_is_deterministic_and_omits_reference_context(self):
        first = renderer.projections(self.repo)
        self.assertEqual(first, renderer.projections(self.repo))
        self.assertEqual("pass", renderer.verify(self.repo)["status"])
        for _, text in first.values():
            self.assertNotIn("agent-sync-preferences", text)
            self.assertNotIn("## Model preferences", text)
        self.assertIn("[OUTPUT]", first["codex"][1])
        self.assertIn("# Communication", first["hermes"][1])
        self.assertIn("file:///absolute/path", first["hermes"][1])
        self.assertNotIn("file:///absolute/path", first["codex"][1])

    def test_shared_edit_changes_both_projections_and_rejects_old_output(self):
        original = renderer.projections(self.repo)
        source = self.repo / "surfaces/core.md"
        source.write_bytes(source.read_bytes().replace(b"## Communication\n", b"## Communication\nShared fixture correction. ", 1))
        changed = renderer.projections(self.repo)
        for host in renderer.HOSTS:
            self.assertNotEqual(original[host][1], changed[host][1])
        with self.assertRaisesRegex(renderer.RenderError, "differs from its source"):
            renderer.verify(self.repo)

    def test_native_adapter_edit_affects_only_its_host(self):
        original = renderer.projections(self.repo)
        path = self.repo / "adapters/hermes.json"
        value = json.loads(path.read_text(encoding="utf-8"))
        value["instructions"]["projection"]["sections"].append({"label": "Fixture native rule", "text": "Native-only fixture."})
        path.write_text(json.dumps(value), encoding="utf-8")
        changed = renderer.projections(self.repo)
        self.assertEqual(original["codex"], changed["codex"])
        self.assertNotEqual(original["hermes"], changed["hermes"])

    def test_direct_overlay_edit_is_rejected_without_mutation(self):
        path = renderer.projections(self.repo)["codex"][0]
        data = path.read_bytes() + b"Directly appended rule.\n"
        path.write_bytes(data)
        with self.assertRaisesRegex(renderer.RenderError, "generated codex overlay differs"):
            renderer.verify(self.repo)
        self.assertEqual(data, path.read_bytes())

    def test_unknown_shared_reference_does_not_render_either_host(self):
        before = {host: path.read_bytes() for host, (path, _) in renderer.projections(self.repo).items()}
        path = self.repo / "adapters/hermes.json"
        value = json.loads(path.read_text(encoding="utf-8"))
        value["instructions"]["projection"]["sections"][0]["shared"] = "missing"
        path.write_text(json.dumps(value), encoding="utf-8")
        self.assertEqual(1, renderer.main(["render", "--repo", str(self.repo)]))
        for host in renderer.HOSTS:
            original_path = ROOT / "adapters" / f"{host}.json"
            rel = json.loads(original_path.read_text(encoding="utf-8"))["instructions"]["source"]
            self.assertEqual(before[host], (self.repo / rel).read_bytes())

    def test_generated_path_cannot_escape_checkout(self):
        path = self.repo / "adapters/codex.json"
        value = json.loads(path.read_text(encoding="utf-8"))
        value["instructions"]["source"] = "../outside.md"
        path.write_text(json.dumps(value), encoding="utf-8")
        with self.assertRaisesRegex(renderer.RenderError, "unsafe generated path"):
            renderer.projections(self.repo)

    def test_host_cannot_silently_omit_a_shared_rule(self):
        path = self.repo / "adapters/hermes.json"
        value = json.loads(path.read_text(encoding="utf-8"))
        value["instructions"]["projection"]["sections"].pop(0)
        path.write_text(json.dumps(value), encoding="utf-8")
        with self.assertRaisesRegex(renderer.RenderError, "missing shared rules for hermes"):
            renderer.projections(self.repo)

    def test_adapter_only_reconciliation_runs_profile_guard(self):
        import sys
        sys.path.insert(0, str(ROOT / "tools"))
        import reconcile
        commands = reconcile._candidate_commands(ROOT, set(), ["adapters/hermes.json"])
        self.assertTrue(any("instruction_profile.py" in argument for command in commands for argument in command))

    def test_installer_and_doctor_reject_direct_generated_drift(self):
        import sys
        from unittest.mock import patch
        sys.path.insert(0, str(ROOT / "tools"))
        import install
        path = renderer.projections(self.repo)["codex"][0]
        path.write_bytes(path.read_bytes() + b"Unowned rule.\n")
        with patch.object(install, "registry_statuses", return_value={}):
            with self.assertRaisesRegex(RuntimeError, "differs from its source"):
                install.doctor(self.repo, {"codex"})
        with patch.object(sys, "argv", ["install.py", "install", "--repo", str(self.repo), "--agents", "codex"]), patch.object(install, "expose_skills") as expose:
            with self.assertRaisesRegex(RuntimeError, "differs from its source"):
                install.main()
            expose.assert_not_called()


if __name__ == "__main__":
    unittest.main()
