"""Exercise the actual public native-package restore without using live homes."""
from __future__ import annotations

import ast
import json
from pathlib import Path
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))
import recovery


INVENTORY = json.loads((REPO / "recovery/hermes-local-inventory.json").read_text(encoding="utf-8"))
PACKAGES = {"skills/" + item["path"]: len(item["files"]) for item in INVENTORY["packages"]}


class NativeSkillRecoveryTests(unittest.TestCase):
    def test_reviewed_packages_restore_completely_without_private_state(self):
        manifest = recovery.verify_snapshot(REPO / "recovery.json", REPO / "recovery/current")
        selected = [a for a in manifest["artifacts"] if a["host"] == "hermes" and a["source"].startswith("skills/") and a["source"] != "skills/.bundled_manifest"]
        for prefix, count in PACKAGES.items():
            files = [a for a in selected if a["source"].startswith(prefix + "/")]
            self.assertEqual(count, len(files), prefix)
            self.assertIn(prefix + "/SKILL.md", [a["source"] for a in files])
        self.assertEqual(sum(PACKAGES.values()), len(selected))
        with tempfile.TemporaryDirectory() as temp:
            roots = {host: Path(temp) / host for host in ("hermes", "codex", "omp")}
            planned = recovery.restore(REPO / "recovery.json", REPO / "recovery/current", roots,
                                       repo_root=REPO)
            self.assertFalse(planned["conflicts"])
            self.assertFalse(any(p.exists() for p in roots.values()))
            result = recovery.restore(REPO / "recovery.json", REPO / "recovery/current", roots,
                                      repo_root=REPO, apply=True)
            self.assertFalse(result["conflicts"])
            runtime = [a for a in manifest["artifacts"] if a["host"] == "hermes" and a["source"].startswith("plugins/hermes-lcm/")]
            self.assertEqual(len(INVENTORY["native_plugins"]["hermes-lcm"]["runtime_files"]), len(runtime))
            for item in selected + runtime:
                expected = (REPO / "recovery/current" / item["snapshot"]).read_text(encoding="utf-8")
                expected = recovery._expand(expected, roots, REPO)
                restored = roots["hermes"] / item["source"]
                self.assertEqual(expected, restored.read_text(encoding="utf-8"), item["source"])
                if restored.suffix == ".py":
                    ast.parse(restored.read_text(encoding="utf-8"), filename=item["source"])
            config = recovery._read_config(roots["hermes"] / "config.yaml", "yaml")
            self.assertTrue({"arxiv", "llm-operations", "collective-wisdom-install"}.issubset(config["skills"]["disabled"]))
            self.assertEqual(INVENTORY["skill_selection"]["disabled"], config["skills"]["disabled"])
            self.assertEqual(INVENTORY["plugin_selection"], config["plugins"])
            self.assertTrue((roots["hermes"] / "skills/.bundled_manifest").is_file())
            self.assertFalse((roots["hermes"] / "plugins/hermes-lcm/lcm.db").exists())
            powerpoint = roots["hermes"] / "skills/productivity/document-files/references/powerpoint"
            self.assertIn("MIT License", (powerpoint / "LICENSE").read_text(encoding="utf-8"))
            self.assertTrue((powerpoint / "scripts/pptx_create.py").is_file())
            self.assertTrue((powerpoint / "advanced/vendor/provenance.json").is_file())
            for excluded in ("LICENSE.txt", "editing.md", "pptxgenjs.md", "scripts/office",
                             "current-tests.xml", "advanced/node_modules", "advanced/dependency-tree.json",
                             "advanced/vendor/pptxgenjs-4.0.1-no-image-size.tgz"):
                self.assertFalse((powerpoint / excluded).exists(), excluded)
            self.assertIs(config["curator"]["enabled"], False)
            for name in ("sessions", "memories", ".env", "auth.json", "state.db", "logs", "cache"):
                self.assertFalse((roots["hermes"] / name).exists(), name)
            again = recovery.restore(REPO / "recovery.json", REPO / "recovery/current", roots,
                                     repo_root=REPO)
            self.assertEqual([], again["changes"])
            self.assertEqual([], again["conflicts"])

    def test_native_snapshot_has_no_untracked_support_payload(self):
        manifest = recovery.verify_snapshot(REPO / "recovery.json", REPO / "recovery/current")
        expected = {a["snapshot"] for a in manifest["artifacts"] if a["host"] == "hermes" and a["source"].startswith("skills/")}
        directory = REPO / "recovery/current/hosts/hermes/skills"
        actual = {p.relative_to(REPO / "recovery/current").as_posix() for p in directory.rglob("*") if p.is_file()}
        self.assertEqual(expected, actual)


if __name__ == "__main__":
    unittest.main()
