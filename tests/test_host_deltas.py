from __future__ import annotations

import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path

import jsonschema

REPO = Path(__file__).resolve().parents[1]


def load_tool(name: str):
    path = REPO / "tools" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"test_{name}_tool", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


class HostDeltaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tool = load_tool("host_deltas")

    def test_repository_manifest_matches_schema_and_is_public_safe(self) -> None:
        manifest = json.loads((REPO / "host-deltas.json").read_text(encoding="utf-8"))
        schema = json.loads((REPO / "contracts/host-deltas.schema.json").read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator(schema).validate(manifest)
        loaded = self.tool.load_manifest(REPO / "host-deltas.json", REPO)
        self.assertEqual({"hermes", "codex", "omp"}, {entry["host"] for entry in loaded["entries"]})
        categories = {entry["category"] for entry in loaded["entries"]}
        self.assertTrue(
            {
                "runtime",
                "settings",
                "instructions",
                "hook",
                "plugin",
                "mcp-tool",
                "native-skill",
                "curator",
            }.issubset(categories)
        )
        for entry in loaded["entries"]:
            self.assertTrue(entry["source_identity"])
            self.assertTrue(entry["version_or_hash"])
            self.assertIn(
                entry["enablement"],
                {"installed", "enabled", "disabled", "absent", "inherited", "managed"},
            )
            self.assertIsInstance(entry["prerequisites"], list)
        omp_instructions = next(entry for entry in loaded["entries"] if entry["id"] == "omp-instructions")
        self.assertEqual("absent", omp_instructions["enablement"])
        self.assertEqual("OMP's opt-out Codex discovery provider remains disabled", omp_instructions["desired_state"])
        self.assertEqual(
            ["omp", "config", "get", "enabledProviders", "--json"],
            omp_instructions["readback"]["argv"],
        )
        self.assertEqual("codex", omp_instructions["readback"]["not_contains"])

    def test_manifest_rejects_secret_values_and_absolute_user_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = root / "host-deltas.json"
            base = {
                "schema_version": 1,
                "machine": "test",
                "public_safe": True,
                "entries": [],
                "exclusions": [],
            }
            for value in (
                "sk" + "-mock-not-a-real-secret-value",
                "C:" + "/Users/private/plugin",
            ):
                payload = json.loads(json.dumps(base))
                payload["exclusions"] = [{"id": "bad", "host": "hermes", "category": "private-state", "reason": value}]
                path.write_text(json.dumps(payload), encoding="utf-8")
                with self.subTest(value=value):
                    with self.assertRaisesRegex(RuntimeError, "public-safe"):
                        self.tool.load_manifest(path, root)

    def test_manifest_rejects_a_stale_bound_artifact_hash(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "host-deltas.json"
            manifest = json.loads((REPO / "host-deltas.json").read_text(encoding="utf-8"))
            bound = next(
                item
                for item in manifest["entries"]
                if item["source_identity"].startswith("repository:")
            )
            bound["version_or_hash"] = "sha256:" + ("0" * 64)
            path.write_text(json.dumps(manifest), encoding="utf-8")

            with self.assertRaisesRegex(RuntimeError, "host-delta binding mismatch"):
                self.tool.load_manifest(path, REPO)

    def test_manifest_rejects_missing_or_unapproved_command_readbacks(self) -> None:
        manifest = json.loads((REPO / "host-deltas.json").read_text(encoding="utf-8"))
        command = next(item for item in manifest["entries"] if item["readback"]["kind"] == "command")
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "host-deltas.json"
            for argv in (None, ["python", "-c", "raise SystemExit(0)"]):
                candidate = json.loads(json.dumps(manifest))
                selected = next(item for item in candidate["entries"] if item["id"] == command["id"])
                if argv is None:
                    selected["readback"].pop("argv")
                else:
                    selected["readback"]["argv"] = argv
                path.write_text(json.dumps(candidate), encoding="utf-8")
                with self.subTest(argv=argv):
                    with self.assertRaisesRegex(RuntimeError, "host-delta schema"):
                        self.tool.load_manifest(path, REPO)

    def test_fleet_binding_is_valid_in_a_fresh_clone_without_render_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            fresh = Path(temp) / "fresh"
            fresh.mkdir()
            shutil.copy2(REPO / "registry.json", fresh / "registry.json")
            shutil.copytree(REPO / "skills", fresh / "skills")
            manifest = {
                "schema_version": 1,
                "machine": "test",
                "public_safe": True,
                "entries": [
                    {
                        "id": "portable-fleet",
                        "host": "hermes",
                        "category": "native-skill",
                        "owner": "agent-signal",
                        "source_identity": "fleet:canonical admitted skills",
                        "version_or_hash": f"sha256:{self.tool._canonical_fleet_digest(REPO)}",
                        "enablement": "managed",
                        "prerequisites": [],
                        "desired_state": "admitted skills are reconstructable",
                        "required": True,
                        "restore": {"kind": "fleet", "reference": "render and apply"},
                        "readback": {"kind": "none"},
                        "redaction": "public-artifact",
                    }
                ],
                "exclusions": [],
            }
            path = fresh / "host-deltas.json"
            path.write_text(json.dumps(manifest), encoding="utf-8")

            loaded = self.tool.load_manifest(path, fresh)

            self.assertEqual("portable-fleet", loaded["entries"][0]["id"])
            self.assertFalse((fresh / "render").exists())

    def test_canonical_fleet_binding_matches_rendered_manifest_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            fresh = Path(temp) / "fresh"
            fresh.mkdir()
            shutil.copy2(REPO / "registry.json", fresh / "registry.json")
            shutil.copytree(REPO / "skills", fresh / "skills")
            snapshot = fresh / "render" / "fleet"

            self.tool.fleet.render_snapshot(fresh, snapshot)

            self.assertEqual(
                self.tool._canonical_fleet_digest(fresh),
                self.tool.fleet.sha256_file(snapshot / "manifest.json"),
            )
            self.assertNotIn(b"\r\n", (snapshot / "manifest.json").read_bytes())

    def test_verify_distinguishes_all_declared_recovery_statuses(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            manifest = {
                "schema_version": 1,
                "machine": "test",
                "public_safe": True,
                "entries": [
                    {
                        "id": "present",
                        "host": "hermes",
                        "category": "runtime",
                        "owner": "host-runtime",
                        "desired_state": "present",
                        "required": True,
                        "restore": {"kind": "prerequisite", "reference": "install Hermes"},
                        "readback": {"kind": "command", "argv": ["hermes", "--version"], "contains": "0.21.0"},
                        "redaction": "metadata-only",
                    },
                    {
                        "id": "missing",
                        "host": "codex",
                        "category": "plugin",
                        "owner": "host-native",
                        "desired_state": "enabled",
                        "required": False,
                        "restore": {"kind": "manual-prerequisite", "reference": "restore local marketplace"},
                        "readback": {"kind": "command", "argv": ["codex", "plugin", "list", "--json"], "contains": "wanted"},
                        "redaction": "metadata-only",
                    },
                    {
                        "id": "failed",
                        "host": "omp",
                        "category": "runtime",
                        "owner": "host-runtime",
                        "desired_state": "required OMP runtime is present",
                        "required": True,
                        "restore": {"kind": "prerequisite", "reference": "install OMP"},
                        "readback": {"kind": "command", "argv": ["omp", "--version"], "contains": "17.2.13"},
                        "redaction": "metadata-only",
                    },
                ],
                "exclusions": [
                    {"id": "sessions", "host": "hermes", "category": "private-state", "reason": "private runtime history"}
                ],
            }
            for item in manifest["entries"]:
                item.update(
                    {
                        "source_identity": f"test:{item['id']}",
                        "version_or_hash": "version:test",
                        "enablement": "managed",
                        "prerequisites": [],
                    }
                )
            path = root / "host-deltas.json"
            path.write_text(json.dumps(manifest), encoding="utf-8")

            def runner(argv: list[str]):
                if argv[0] == "hermes":
                    return 0, "Hermes Agent 0.21.0"
                return 127, "missing"

            report = self.tool.verify(path, root, runner=runner, restored_ids={"present"})
            by_id = {item["id"]: item for item in report["entries"]}
            self.assertEqual("restored", by_id["present"]["status"])
            self.assertEqual("prerequisite-missing", by_id["missing"]["status"])
            self.assertEqual("failed", by_id["failed"]["status"])
            self.assertEqual("excluded-private", report["exclusions"][0]["status"])
            self.assertFalse(report["passed"])

    def test_current_snapshot_restores_declarative_state_and_reports_missing_native_prerequisites(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            roots = {
                "hermes": base / "homes" / "hermes",
                "codex": base / "homes" / "codex",
                "omp": base / "homes" / "omp",
            }
            for root in roots.values():
                root.mkdir(parents=True)

            recovery_plan = self.tool.recovery.restore(
                REPO / "recovery.json",
                REPO / "recovery" / "current",
                roots,
                apply=False,
                repo_root=REPO,
            )
            self.assertTrue(recovery_plan["changes"])
            self.assertFalse(recovery_plan["conflicts"])
            self.tool.recovery.restore(
                REPO / "recovery.json",
                REPO / "recovery" / "current",
                roots,
                apply=True,
                repo_root=REPO,
            )

            fleet_repo = base / "fleet-repo"
            fleet_repo.mkdir()
            shutil.copy2(REPO / "registry.json", fleet_repo / "registry.json")
            shutil.copytree(REPO / "skills", fleet_repo / "skills")
            fleet_snapshot = fleet_repo / "render" / "fleet"
            shared_skills = base / "shared-skills"
            self.tool.fleet.render_snapshot(fleet_repo, fleet_snapshot)
            self.tool.fleet.apply_snapshot(fleet_snapshot, shared_skills)

            clean = self.tool.recovery.restore(
                REPO / "recovery.json",
                REPO / "recovery" / "current",
                roots,
                apply=False,
                repo_root=REPO,
            )
            self.assertEqual([], clean["changes"])
            self.assertEqual([], clean["conflicts"])
            self.assertEqual([], self.tool.fleet.verify_snapshot(fleet_snapshot, shared_skills))

            changed_references = {
                f"{item['host']}:{item['id']}" for item in recovery_plan["changes"]
            }
            manifest = self.tool.load_manifest(REPO / "host-deltas.json", REPO)
            restored_ids = {
                item["id"]
                for item in manifest["entries"]
                if (
                    item["restore"]["kind"] == "recovery-artifact"
                    and item["restore"]["reference"] in changed_references
                )
                or item["restore"]["kind"] == "fleet"
            }

            def runner(argv: list[str]):
                command = " ".join(argv)
                outputs = {
                    "hermes --version": "Hermes Agent 0.21.0",
                    "hermes hooks list": "No shell hooks configured",
                    "hermes curator status": "curator: ENABLED",
                    "codex --version": "codex-cli 0.153.4",
                    "codex plugin list --json": "[]",
                    "omp --version": "OMP 18.1.10",
                    "omp plugin list": "No plugins installed",
                    "omp config get enabledProviders --json": '{"enabledProviders":[]}',
                }
                return (0, outputs[command]) if command in outputs else (127, "missing")

            report = self.tool.verify(
                REPO / "host-deltas.json",
                REPO,
                runner=runner,
                roots=roots,
                skill_roots=[shared_skills],
                fleet_snapshot=fleet_snapshot,
                restored_ids=restored_ids,
            )
            # Native source patches are explicit prerequisites, not declarative
            # artifacts. Empty fake host roots must not be called fully restored.
            missing_native = {
                item["id"] for item in manifest["entries"]
                if item["restore"]["kind"] == "manual-prerequisite"
                and item["readback"]["kind"] == "file"
                and "sha256" in item["readback"]
            }
            failed = {item["id"] for item in report["entries"] if item["status"] == "failed"}
            self.assertEqual(missing_native, failed, report)
            self.assertEqual(not missing_native, report["passed"], report)
            statuses = {item["status"] for item in report["entries"]}
            self.assertIn("restored", statuses)
            self.assertIn("verified", statuses)
            self.assertTrue(all(item["status"] == "excluded-private" for item in report["exclusions"]))


if __name__ == "__main__":
    unittest.main()
