from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import jsonschema

REPO = Path(__file__).resolve().parents[1]


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


class ToolTests(unittest.TestCase):
    def test_registry_skills_validate(self):
        result = subprocess.run(
            [sys.executable, str(REPO / "tools" / "validate.py")],
            cwd=REPO,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_vtt_rolling_captions_are_deduplicated(self):
        cleaner = load(
            "clean_vtt",
            REPO / "skills" / "learn-from-youtube" / "scripts" / "clean_vtt.py",
        )
        sample = """WEBVTT

00:00:01.000 --> 00:00:03.000
hello world

00:00:03.000 --> 00:00:05.000
hello world this works
"""
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "sample.vtt"
            path.write_text(sample, encoding="utf-8")
            segments = cleaner.parse_vtt(path)
        self.assertEqual([item["text"] for item in segments], ["hello world", "this works"])

    def test_eval_suite_has_unique_case_ids(self):
        suite = json.loads((REPO / "evals" / "capability-admission.json").read_text(encoding="utf-8"))
        ids = [case["id"] for case in suite["cases"]]
        self.assertGreaterEqual(len(ids), 3)
        self.assertEqual(len(ids), len(set(ids)))


    def test_eval_judge_uses_only_case_criteria(self):
        evaluator = load("eval_tool", REPO / "tools" / "eval.py")
        prompt = evaluator.judge_prompt(
            {"claim": "broad claim", "criteria": ["unrelated shared criterion"]},
            {"prompt": "do the task", "criteria": ["case criterion"]},
            "answer a",
            "answer b",
        )
        self.assertIn("case criterion", prompt)
        self.assertNotIn("unrelated shared criterion", prompt)
        self.assertNotIn("broad claim", prompt)

    def test_retirement_ties_remove_but_admission_ties_do_not_promote(self):
        evaluator = load("eval_tool_decision", REPO / "tools" / "eval.py")
        self.assertTrue(evaluator.decision_pass("retirement", 0, 0, 0, 0))
        self.assertFalse(evaluator.decision_pass("admission", 0, 0, 0, 0))
        self.assertFalse(evaluator.decision_pass("retirement", 2, 1, 0, 0))

    def test_installer_preserves_unrelated_skills(self):
        installer = load("install_tool", REPO / "tools" / "install.py")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo_skills = root / "repo-skills"
            source = repo_skills / "candidate"
            source.mkdir(parents=True)
            (source / "SKILL.md").write_text("---\nname: candidate\ndescription: test\n---\n", encoding="utf-8")
            target = root / "installed"
            unrelated = target / "unrelated"
            unrelated.mkdir(parents=True)
            (unrelated / "SKILL.md").write_text("keep", encoding="utf-8")

            staged = repo_skills / "staged"
            staged.mkdir()
            (staged / "SKILL.md").write_text("---\nname: staged\ndescription: test\n---\n", encoding="utf-8")

            statuses = installer.expose_skills(repo_skills, False, target, {"candidate"})

            self.assertTrue((unrelated / "SKILL.md").is_file())
            self.assertEqual((target / "candidate").resolve(), source.resolve())
            self.assertFalse((target / "staged").exists())
            self.assertEqual(statuses[0][0], "candidate")

    def test_installer_accepts_matching_rendered_skill_copy(self):
        installer = load("install_tool_matching_copy", REPO / "tools" / "install.py")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source"
            target = root / "target"
            source.mkdir()
            target.mkdir()
            (source / "SKILL.md").write_text("same", encoding="utf-8")
            (target / "SKILL.md").write_text("same", encoding="utf-8")

            self.assertEqual(installer.expose_skill(source, target, False), "matching")

    def test_installer_ignores_generated_python_cache(self):
        installer = load("install_tool_cache", REPO / "tools" / "install.py")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source"
            target = root / "target"
            source.mkdir()
            target.mkdir()
            (source / "SKILL.md").write_text("same", encoding="utf-8")
            (target / "SKILL.md").write_text("same", encoding="utf-8")
            cache = source / "__pycache__"
            cache.mkdir()
            (cache / "generated.pyc").write_bytes(b"generated")

            self.assertTrue(installer.same_tree(source, target))

    def test_installer_rejects_tree_with_extra_empty_directory(self):
        installer = load("install_tool_tree_shape", REPO / "tools" / "install.py")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source"
            target = root / "target"
            source.mkdir()
            target.mkdir()
            (source / "SKILL.md").write_text("same", encoding="utf-8")
            (target / "SKILL.md").write_text("same", encoding="utf-8")
            (target / "extra-empty").mkdir()

            self.assertFalse(installer.same_tree(source, target))
            with self.assertRaisesRegex(RuntimeError, "different skill"):
                installer.expose_skill(source, target, False)

    @unittest.skipUnless(sys.platform == "win32", "Windows junction behavior")
    def test_installer_rejects_external_junction_as_matching_copy(self):
        installer = load("install_tool_junction_copy", REPO / "tools" / "install.py")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source"
            outside = root / "outside"
            target = root / "target"
            source.mkdir()
            outside.mkdir()
            (source / "SKILL.md").write_text("same", encoding="utf-8")
            (outside / "SKILL.md").write_text("same", encoding="utf-8")
            created = subprocess.run(
                ["cmd", "/c", "mklink", "/J", str(target), str(outside)],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(created.returncode, 0, created.stdout + created.stderr)

            self.assertFalse(installer.same_tree(source, target))
            with self.assertRaisesRegex(RuntimeError, "different skill"):
                installer.expose_skill(source, target, False)

    def test_adapters_are_declarative_and_repo_sources_exist(self):
        for host in ("codex", "hermes", "omp"):
            adapter = json.loads((REPO / "adapters" / f"{host}.json").read_text(encoding="utf-8"))
            self.assertEqual(adapter["host"], host)
            self.assertEqual(adapter["skills"]["selection"], "registry:admitted")
            self.assertTrue((REPO / adapter["instructions"]["source"]).is_file())
            self.assertTrue((REPO / adapter["skills"]["source"]).is_dir())
            self.assertIn("{", adapter["instructions"]["target"])

    def test_manual_merge_surface_checks_current_profile_without_installing_staged_skills(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp) / "home"
            codex_home = home / ".codex"
            codex_home.mkdir(parents=True)
            (codex_home / "AGENTS.md").write_bytes(
                (REPO / "recovery" / "current" / "hosts" / "codex" / "AGENTS.md").read_bytes()
            )
            env = os.environ.copy()
            env.update(
                {
                    "HOME": str(home),
                    "USERPROFILE": str(home),
                    "CODEX_HOME": str(codex_home),
                }
            )
            result = subprocess.run(
                [sys.executable, str(REPO / "tools" / "install.py"), "--repo", str(REPO), "--agents", "codex"],
                cwd=REPO,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("codex surface: manual-merge", result.stdout)
        self.assertIn("PASS codex manual-merge markers", result.stdout)
        self.assertNotIn("PASS admitted skill capability-curator", result.stdout)

    def test_hermes_manual_merge_declares_verifiable_markers(self):
        adapter = json.loads((REPO / "adapters" / "hermes.json").read_text(encoding="utf-8"))
        self.assertEqual(adapter["instructions"]["strategy"], "manual-merge")
        self.assertEqual(
            adapter["instructions"]["required_markers"],
            ["# Identity", "# Style", "# Judgment", "# Defaults"],
        )

    def test_routing_adapters_share_contract_and_declare_supported_surfaces(self):
        shared = {
            "catalog_schema": "skills/openai-delegation-route-research/references/gpt-route-catalog.schema.json",
            "task_schema": "skills/openai-delegation-route-research/references/route-task.schema.json",
            "selection_contract": "skills/openai-delegation-route-research/references/selection-contract.md",
            "aux_schema": "skills/openai-delegation-route-research/references/aux-models.schema.json",
            "aux_assignments": "skills/openai-delegation-route-research/references/current-aux-models.json",
            "selector": "skills/openai-delegation-route-research/scripts/route_selector.py",
            "receipt_schema": "skills/openai-delegation-route-research/references/route-decision.schema.json",
        }
        required_fields = {"provider", "model", "reasoning_effort", "decision_receipt"}
        schema = json.loads((REPO / "adapters" / "schema.json").read_text(encoding="utf-8"))
        for host in ("hermes", "codex", "omp"):
            adapter = json.loads((REPO / "adapters" / f"{host}.json").read_text(encoding="utf-8"))
            jsonschema.Draft202012Validator(schema).validate(adapter)
            routing = adapter["routing"]
            self.assertEqual({key: routing[key] for key in shared}, shared)
            for path in shared.values():
                self.assertTrue((REPO / path).is_file(), f"{host}: missing {path}")

        hermes = json.loads((REPO / "adapters" / "hermes.json").read_text(encoding="utf-8"))["routing"]
        self.assertEqual(hermes["executable_adapter"], "tools/route_adapter.py")
        self.assertTrue((REPO / hermes["executable_adapter"]).is_file())
        self.assertTrue(hermes["surfaces"])
        for surface in hermes["surfaces"]:
            self.assertEqual(set(surface["required_fields"]), required_fields)
            self.assertTrue(surface["target_surface"])
            self.assertTrue(surface["pinning"])

        expected_surface = {"codex": "codex-workflow", "omp": "omp-workflow"}
        for host in ("codex", "omp"):
            routing = json.loads((REPO / "adapters" / f"{host}.json").read_text(encoding="utf-8"))["routing"]
            self.assertEqual(routing["status"], "automatic-selection-active-workflow")
            self.assertNotIn("executable_adapter", routing)
            self.assertEqual(len(routing["surfaces"]), 1)
            surface = routing["surfaces"][0]
            self.assertEqual(surface["target_surface"], expected_surface[host])
            self.assertEqual(set(surface["required_fields"]), required_fields)
            self.assertTrue(surface["pinning"])
            self.assertEqual(routing["unsupported_surfaces"], [])


    def test_public_check_rejects_private_material_and_ignores_raw_runs(self):
        public_check = load("public_check", REPO / "tools" / "public_check.py")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "README.md").write_text("portable", encoding="utf-8")
            (root / "private.md").write_text("source C:\\Users\\Someone\\notes", encoding="utf-8")
            (root / ".evals").mkdir()
            raw_secret = "password=" + "'not-for-public'"
            (root / ".evals" / "raw.txt").write_text(raw_secret, encoding="utf-8")
            (root / ".worktrees").mkdir()
            (root / ".worktrees" / "private.md").write_text("C:\\Users\\Someone\\notes", encoding="utf-8")
            (root / "routing.md").write_text("high-risk-architecture-provider", encoding="utf-8")
            findings = public_check.scan(root)
        self.assertEqual([(str(path), rule) for path, _, rule in findings], [("private.md", "windows-user-path")])

    def test_public_check_distinguishes_a_posix_home_path_from_regex_source(self):
        public_check = load("public_check_posix", REPO / "tools" / "public_check.py")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "actual.md").write_text("source /" + "home/alice/", encoding="utf-8")
            (root / "guard.py").write_text(r'pattern = r"/home/[^/\\s]+/"', encoding="utf-8")
            findings = public_check.scan(root)
        self.assertEqual([(str(path), rule) for path, _, rule in findings], [("actual.md", "posix-user-path")])

    def test_eval_summary_rejects_stale_artifact_hashes(self):
        summarizer = load("summarize_eval", REPO / "tools" / "summarize_eval.py")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            candidate = root / "SKILL.md"
            suite = root / "suite.json"
            harness = root / "eval.py"
            report = root / "raw.json"
            out = root / "summary.json"
            candidate.write_text("candidate", encoding="utf-8")
            suite.write_text("{}", encoding="utf-8")
            harness.write_text("pass", encoding="utf-8")
            report.write_text(
                json.dumps(
                    {
                        "suite": "x",
                        "agent": "codex",
                        "agent_version": "1",
                        "timestamp_utc": "now",
                        "artifacts": {
                            "candidate_sha256": "stale",
                            "suite_sha256": summarizer.sha256(suite),
                            "harness_sha256": summarizer.sha256(harness),
                        },
                        "summary": {},
                        "results": [],
                    }
                ),
                encoding="utf-8",
            )
            rc = summarizer.main(
                [
                    str(report),
                    "--candidate", str(candidate),
                    "--suite", str(suite),
                    "--harness", str(harness),
                    "--status", "staged",
                    "--decision", "keep staged",
                    "--out", str(out),
                ]
            )
        self.assertEqual(rc, 1)
        self.assertFalse(out.exists())

    def test_candidate_hash_and_prompt_include_linked_references(self):
        artifacts = load("artifact_hash", REPO / "tools" / "artifact_hash.py")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "references").mkdir()
            candidate = root / "SKILL.md"
            reference = root / "references" / "contract.md"
            candidate.write_text("Read [the contract](references/contract.md).", encoding="utf-8")
            reference.write_text("first rule", encoding="utf-8")
            first = artifacts.candidate_hash(candidate)
            prompt = artifacts.candidate_prompt_text(candidate)
            reference.write_text("changed rule", encoding="utf-8")
            second = artifacts.candidate_hash(candidate)
        self.assertIn("first rule", prompt)
        self.assertNotEqual(first, second)


if __name__ == "__main__":
    unittest.main()
