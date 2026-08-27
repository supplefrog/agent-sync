from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.audit = load("audit_tool", REPO / "tools" / "audit.py")

    def _fixture_repo(self, root: Path, admitted: bool = True) -> Path:
        repo = root / "repo"
        (repo / "contracts").mkdir(parents=True)
        (repo / "adapters").mkdir(parents=True)
        (repo / "evidence").mkdir(parents=True)
        (repo / "skills" / "capability-curator").mkdir(parents=True)
        (repo / "skills" / "surface-convergence").mkdir(parents=True)
        (repo / "surfaces").mkdir(parents=True)
        (repo / "evals" / "results").mkdir(parents=True)
        (repo / "tools").mkdir(parents=True)
        (repo / "surfaces" / "core.md").write_text("core surface", encoding="utf-8")
        (repo / "tools" / "eval.py").write_text("print('eval')", encoding="utf-8")
        for host, target in (("codex", "{CODEX_HOME}/AGENTS.md"), ("hermes", "{HERMES_HOME}/SOUL.md")):
            (repo / "adapters" / f"{host}.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "host": host,
                        "instructions": {"source": "surfaces/core.md", "target": target},
                        "skills": {
                            "source": "skills",
                            "selection": "registry:admitted",
                            "install_root": "{SHARED_SKILLS_HOME}",
                        },
                    }
                ),
                encoding="utf-8",
            )

        (repo / "registry.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "skills": [
                        {"name": "capability-curator", "status": "staged"},
                        {"name": "surface-convergence", "status": "admitted" if admitted else "staged"},
                    ],
                }
            ),
            encoding="utf-8",
        )
        (repo / "contracts" / "surface-matrix.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "knowledge_ledger": "../evidence/findings.json",
                    "hosts": {
                        "hermes": {"cli_version": "0.19.0"},
                        "codex": {"cli_version": "0.146.0-alpha.3.1"},
                    },
                    "modalitys": [],
                    "modalities": [
                        {"id": "instructions-style", "status": "staged", "portable_artifacts": ["surfaces/core.md"]},
                        {"id": "skills-procedures", "status": "staged", "portable_artifacts": []},
                        {"id": "tools-mcp", "status": "unassessed", "portable_artifacts": []},
                        {"id": "routing-delegation", "status": "unassessed", "portable_artifacts": ["surfaces/core.md"]},
                        {"id": "memory-context", "status": "unassessed", "portable_artifacts": ["evidence/findings.json"]},
                        {"id": "policy-security", "status": "unassessed", "portable_artifacts": []},
                        {"id": "planning-automation", "status": "unassessed", "portable_artifacts": []},
                        {"id": "lifecycle-update", "status": "unassessed", "portable_artifacts": ["tools/eval.py"]},
                    ],
                }
            ),
            encoding="utf-8",
        )
        (repo / "evidence" / "findings.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "records": [
                        {
                            "id": "x",
                            "evidence": [{"kind": "evaluation", "reference": "evals/results/surface-convergence-run.json"}],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        (repo / "skills" / "capability-curator" / "SKILL.md").write_text("---\nname: capability-curator\n---\n", encoding="utf-8")
        (repo / "skills" / "surface-convergence" / "SKILL.md").write_text("---\nname: surface-convergence\n---\n", encoding="utf-8")
        (repo / "evals" / "results" / "surface-convergence-run.json").write_text("{}", encoding="utf-8")
        return repo

    def test_valid_check(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = self._fixture_repo(Path(temp))
            with patch("shutil.which", side_effect=lambda name: name), patch("subprocess.run") as run:
                run.side_effect = [
                    subprocess.CompletedProcess(["hermes", "--version"], 0, stdout="hermes 0.19.0\n", stderr=""),
                    subprocess.CompletedProcess(["codex", "--version"], 0, stdout="codex 0.146.0-alpha.3.1\n", stderr=""),
                ]
                rc = self.audit.main(["check", "--repo", str(repo), "--live"])
            self.assertEqual(rc, 0)

    def test_duplicate_modality(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = self._fixture_repo(Path(temp))
            data = json.loads((repo / "contracts" / "surface-matrix.json").read_text(encoding="utf-8"))
            data["modalities"].append(dict(data["modalities"][0]))
            (repo / "contracts" / "surface-matrix.json").write_text(json.dumps(data), encoding="utf-8")
            rc = self.audit.main(["check", "--repo", str(repo)])
            self.assertEqual(rc, 1)

    def test_missing_artifact(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = self._fixture_repo(Path(temp))
            (repo / "surfaces" / "core.md").unlink()
            rc = self.audit.main(["check", "--repo", str(repo)])
            self.assertEqual(rc, 1)

    def test_snapshot_hashes(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = self._fixture_repo(Path(temp))
            with patch("shutil.which", side_effect=lambda name: name), patch("subprocess.run") as run:
                run.side_effect = [
                    subprocess.CompletedProcess(["hermes", "--version"], 0, stdout="hermes 0.19.0\n", stderr=""),
                    subprocess.CompletedProcess(["codex", "--version"], 0, stdout="codex 0.146.0-alpha.3.1\n", stderr=""),
                ]
                out = repo / "snap.json"
                rc = self.audit.main(["snapshot", "--repo", str(repo), "--out", str(out)])
            self.assertEqual(rc, 0)
            snap = json.loads(out.read_text(encoding="utf-8"))
            self.assertIn("timestamp_utc", snap)
            self.assertEqual(snap["hashes"]["registry.json"], self.audit.sha256_file(repo / "registry.json"))
            self.assertEqual(snap["hashes"]["surfaces/core.md"], self.audit.sha256_file(repo / "surfaces" / "core.md"))
            self.assertEqual(snap["hashes"]["contracts/surface-matrix.json"], self.audit.sha256_file(repo / "contracts" / "surface-matrix.json"))
            self.assertIn("capability-curator", snap["skill_hashes"])


if __name__ == "__main__":
    unittest.main()
