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
        for host, target in (
            ("codex", "{CODEX_HOME}/AGENTS.md"),
            ("hermes", "{HERMES_HOME}/SOUL.md"),
            ("omp", "{CODEX_HOME}/AGENTS.md"),
        ):
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
                        "omp": {"cli_version": "17.2.13"},
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
        (repo / "contracts" / "ownership.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "supported_hosts": ["codex", "hermes", "omp"],
                    "capabilities": [
                        {
                            "id": "capability-curator",
                            "owner": "skills/capability-curator",
                            "status": "staged",
                            "selection_state": "unresolved",
                            "selection_evidence": [],
                            "selection_reason": "staged",
                        },
                        {
                            "id": "surface-convergence",
                            "owner": "skills/surface-convergence",
                            "status": "admitted" if admitted else "staged",
                            "selection_state": "selected" if admitted else "unresolved",
                            "selection_evidence": ["evals/results/surface-convergence-run.json"] if admitted else [],
                            "selection_reason": "fixture decision",
                        },
                    ],
                    "retired_artifacts": [
                        {
                            "path": "integrations/hermes/cc-dynamic-workflows",
                            "replacement": "skills/surface-convergence",
                            "reason": "duplicate owner",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        (repo / "contracts" / "ownership.schema.json").write_text(
            (REPO / "contracts" / "ownership.schema.json").read_text(encoding="utf-8"),
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
        (repo / "evals" / "results" / "surface-convergence-run.json").write_text(
            json.dumps({"suite": "surface-convergence"}), encoding="utf-8"
        )
        return repo

    def test_valid_check(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = self._fixture_repo(Path(temp))
            with patch("shutil.which", side_effect=lambda name: name), patch("subprocess.run") as run:
                run.side_effect = [
                    subprocess.CompletedProcess(["hermes", "--version"], 0, stdout="hermes 0.19.0\n", stderr=""),
                    subprocess.CompletedProcess(["codex", "--version"], 0, stdout="codex 0.146.0-alpha.3.1\n", stderr=""),
                    subprocess.CompletedProcess(["omp", "--version"], 0, stdout="omp/17.2.13\n", stderr=""),
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
                    subprocess.CompletedProcess(["omp", "--version"], 0, stdout="omp/17.2.13\n", stderr=""),
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

    def test_unregistered_portable_skill_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = self._fixture_repo(Path(temp))
            extra = repo / "skills" / "shadow-owner"
            extra.mkdir()
            (extra / "SKILL.md").write_text("---\nname: shadow-owner\n---\n", encoding="utf-8")

            errors = self.audit.validate_repo(repo)

            self.assertIn("unregistered portable skill: shadow-owner", errors)

    def test_skill_entrypoint_under_integration_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = self._fixture_repo(Path(temp))
            integration = repo / "integrations" / "hermes" / "duplicate"
            integration.mkdir(parents=True)
            (integration / "SKILL.md").write_text("---\nname: duplicate\n---\n", encoding="utf-8")

            errors = self.audit.validate_repo(repo)

            self.assertTrue(any(error.startswith("skill entrypoint outside canonical skills tree:") for error in errors))

    def test_unsupported_adapter_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = self._fixture_repo(Path(temp))
            (repo / "adapters" / "obsolete.json").write_text("{}", encoding="utf-8")

            errors = self.audit.validate_repo(repo)

            self.assertIn("adapter set differs from supported hosts: obsolete", errors)

    def test_retired_artifact_cannot_reappear(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = self._fixture_repo(Path(temp))
            retired = repo / "integrations" / "hermes" / "cc-dynamic-workflows"
            retired.mkdir(parents=True)

            errors = self.audit.validate_repo(repo)

            self.assertIn("retired artifact reappeared: integrations/hermes/cc-dynamic-workflows", errors)

    def test_admitted_owner_requires_selected_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = self._fixture_repo(Path(temp), admitted=True)
            ownership_path = repo / "contracts" / "ownership.json"
            ownership = json.loads(ownership_path.read_text(encoding="utf-8"))
            ownership["capabilities"][1]["selection_state"] = "unresolved"
            ownership["capabilities"][1]["selection_evidence"] = []
            ownership_path.write_text(json.dumps(ownership), encoding="utf-8")

            errors = self.audit.validate_repo(repo)

            self.assertIn("admitted capability lacks selected evidence: surface-convergence", errors)

    def test_duplicate_capability_owner_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = self._fixture_repo(Path(temp))
            ownership_path = repo / "contracts" / "ownership.json"
            ownership = json.loads(ownership_path.read_text(encoding="utf-8"))
            ownership["capabilities"].append(dict(ownership["capabilities"][0]))
            ownership_path.write_text(json.dumps(ownership), encoding="utf-8")

            errors = self.audit.validate_repo(repo)

            self.assertIn("duplicate ownership capabilities: capability-curator", errors)

    def test_ownership_schema_is_enforced(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = self._fixture_repo(Path(temp))
            ownership_path = repo / "contracts" / "ownership.json"
            ownership = json.loads(ownership_path.read_text(encoding="utf-8"))
            ownership["capabilities"][0]["unexpected"] = True
            ownership_path.write_text(json.dumps(ownership), encoding="utf-8")

            errors = self.audit.validate_repo(repo)

            self.assertTrue(any(error.startswith("ownership schema:") for error in errors))

    def test_selection_evidence_cannot_escape_results(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = self._fixture_repo(Path(temp), admitted=True)
            ownership_path = repo / "contracts" / "ownership.json"
            ownership = json.loads(ownership_path.read_text(encoding="utf-8"))
            ownership["capabilities"][1]["selection_evidence"] = [
                "evals/results/../../evidence/findings.json"
            ]
            ownership_path.write_text(json.dumps(ownership), encoding="utf-8")

            errors = self.audit.validate_repo(repo)

            self.assertIn("invalid selection evidence for capability: surface-convergence", errors)

    def test_selection_evidence_must_bind_to_capability(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = self._fixture_repo(Path(temp), admitted=True)
            unrelated = repo / "evals" / "results" / "unrelated.json"
            unrelated.write_text(json.dumps({"suite": "different-capability"}), encoding="utf-8")
            ownership_path = repo / "contracts" / "ownership.json"
            ownership = json.loads(ownership_path.read_text(encoding="utf-8"))
            ownership["capabilities"][1]["selection_evidence"] = [
                "evals/results/unrelated.json"
            ]
            ownership_path.write_text(json.dumps(ownership), encoding="utf-8")

            errors = self.audit.validate_repo(repo)

            self.assertIn("selection evidence is not bound to capability: surface-convergence", errors)


if __name__ == "__main__":
    unittest.main()
