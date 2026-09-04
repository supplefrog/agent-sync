from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]


def load_tool(name: str):
    path = REPO / "tools" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"test_{name}_tool", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


def write_skill(root: Path, name: str, body: str = "body") -> None:
    target = root / "skills" / name
    target.mkdir(parents=True, exist_ok=True)
    (target / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: Use when handling {name}.\nlicense: MIT\n---\n\n{body}\n",
        encoding="utf-8",
    )


def digest(root: Path) -> str:
    h = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        h.update(path.relative_to(root).as_posix().encode())
        h.update(b"\0")
        h.update(path.read_bytes())
    return h.hexdigest()


class ReconcileTests(unittest.TestCase):
    def setUp(self) -> None:
        self.reconcile = load_tool("reconcile")
        self.fleet = load_tool("fleet")

    def fixture(self, root: Path) -> tuple[Path, Path]:
        repo = root / "repo"
        live = root / "live"
        write_skill(repo, "kept", "baseline")
        write_skill(repo, "staged", "candidate")
        (repo / "registry.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "skills": [
                        {"name": "kept", "status": "admitted"},
                        {"name": "staged", "status": "staged"},
                    ],
                }
            ),
            encoding="utf-8",
        )
        (repo / "fleet.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "snapshot_root": "render/fleet",
                    "machines": {
                        "test": {
                            "hosts": ["hermes", "codex", "omp"],
                            "skill_roots": [str(live)],
                        }
                    },
                }
            ),
            encoding="utf-8",
        )
        (repo / "recovery.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "machine": "test",
                    "public_safe": True,
                    "hosts": {
                        "hermes": {"artifacts": []},
                        "codex": {"artifacts": []},
                        "omp": {"artifacts": []},
                    },
                }
            ),
            encoding="utf-8",
        )
        (repo / "contracts").mkdir(parents=True)
        (repo / "contracts" / "instruction-surfaces.json").write_text(
            json.dumps({"schema_version": 1, "surfaces": []}), encoding="utf-8"
        )
        (repo / "host-deltas.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "machine": "test",
                    "public_safe": True,
                    "entries": [],
                    "exclusions": [],
                }
            ),
            encoding="utf-8",
        )
        snapshot = repo / "render" / "fleet"
        self.fleet.render_snapshot(repo, snapshot)
        self.fleet.apply_snapshot(snapshot, live)
        return repo, live

    def test_plan_aggregates_every_surface_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repo, live = self.fixture(Path(temp))
            before = digest(Path(temp))

            report = self.reconcile.plan(
                repo,
                machine="test",
                recovery_roots={},
                skill_roots=[live],
                live=False,
            )

            self.assertEqual(before, digest(Path(temp)))
            self.assertFalse(report["mutation_performed"])
            self.assertEqual(
                {"recovery", "fleet", "instructions", "governance", "host-deltas"},
                set(report["surfaces"]),
            )
            self.assertEqual(len(report["findings"]), len({item["finding_id"] for item in report["findings"]}))

    def test_sync_adopts_single_origin_existing_owner_transactionally_and_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repo, live = self.fixture(Path(temp))
            (live / "kept" / "SKILL.md").write_text(
                "---\nname: kept\ndescription: Use when handling kept.\nlicense: MIT\n---\n\nadopted\n",
                encoding="utf-8",
            )

            first = self.reconcile.sync(
                repo,
                machine="test",
                adopt=["kept"],
                recovery_roots={},
                skill_roots=[live],
                check_commands=[],
            )
            second = self.reconcile.sync(
                repo,
                machine="test",
                adopt=["kept"],
                recovery_roots={},
                skill_roots=[live],
                check_commands=[],
            )

            self.assertEqual("applied", first["result"])
            self.assertEqual(first["request_id"], second["request_id"])
            self.assertIn("adopted", (repo / "skills/kept/SKILL.md").read_text(encoding="utf-8"))
            self.assertEqual([], self.fleet.verify_snapshot(repo / "render/fleet", live))
            requests = list((repo / "reconciliation/requests").glob("*.json"))
            self.assertEqual(1, len(requests))
            request = json.loads(requests[0].read_text(encoding="utf-8"))
            self.assertNotIn(str(Path(temp)), json.dumps(request))
            self.assertEqual("completed", request["phase"])
            self.assertEqual("low", request["risk"])
            self.assertEqual("applied", request["disposition"])
            self.assertEqual("fleet", request["source"]["surface"])
            self.assertTrue(request["phases"])

    def test_sync_deploys_canonical_when_render_advanced_ahead_of_managed_live_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repo, live = self.fixture(Path(temp))
            (repo / "skills/kept/SKILL.md").write_text(
                "---\nname: kept\ndescription: Use when handling kept.\nlicense: MIT\n---\n\nintermediate\n",
                encoding="utf-8",
            )
            self.fleet.render_snapshot(repo, repo / "render/fleet")
            (repo / "skills/kept/SKILL.md").write_text(
                "---\nname: kept\ndescription: Use when handling kept.\nlicense: MIT\n---\n\nfinal canonical\n",
                encoding="utf-8",
            )

            report = self.reconcile.sync(
                repo,
                machine="test",
                adopt=["kept"],
                recovery_roots={},
                skill_roots=[live],
                check_commands=[],
            )

            self.assertEqual("applied", report["result"])
            self.assertIn("final canonical", (live / "kept/SKILL.md").read_text(encoding="utf-8"))
            self.assertEqual([], self.fleet.verify_snapshot(repo / "render/fleet", live))

    def test_sync_rejects_concurrent_or_unsafe_live_changes_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repo, live = self.fixture(Path(temp))
            (repo / "skills/kept/SKILL.md").write_text(
                "---\nname: kept\ndescription: Use when handling kept.\nlicense: MIT\n---\n\ncanonical change\n",
                encoding="utf-8",
            )
            (live / "kept/SKILL.md").write_text(
                "---\nname: kept\ndescription: Use when handling kept.\nlicense: MIT\n---\n\nlive change\n",
                encoding="utf-8",
            )
            before_repo = digest(repo / "skills")
            before_live = digest(live)

            report = self.reconcile.sync(
                repo,
                machine="test",
                adopt=["kept"],
                recovery_roots={},
                skill_roots=[live],
                check_commands=[],
            )

            self.assertEqual("review-required", report["result"])
            self.assertEqual(before_repo, digest(repo / "skills"))
            self.assertEqual(before_live, digest(live))
            receipt = json.loads(next((repo / "reconciliation/requests").glob("*.json")).read_text(encoding="utf-8"))
            self.assertEqual("review-required", receipt["disposition"])
            self.assertEqual("review", receipt["risk"])

        with tempfile.TemporaryDirectory() as temp:
            repo, live = self.fixture(Path(temp))
            mock_secret = "sk" + "-mock-not-a-real-secret-value"
            (live / "kept/SKILL.md").write_text(
                f"---\nname: kept\ndescription: Use when handling kept.\nlicense: MIT\n---\n\n{mock_secret}\n",
                encoding="utf-8",
            )
            before_repo = digest(repo / "skills")

            report = self.reconcile.sync(
                repo,
                machine="test",
                adopt=["kept"],
                recovery_roots={},
                skill_roots=[live],
                check_commands=[],
            )

            self.assertEqual("rejected", report["result"])
            self.assertEqual(before_repo, digest(repo / "skills"))
            encoded = json.dumps(report)
            self.assertNotIn(mock_secret, encoded)
            receipt = json.loads(next((repo / "reconciliation/requests").glob("*.json")).read_text(encoding="utf-8"))
            self.assertEqual("rejected", receipt["disposition"])
            self.assertEqual("high", receipt["risk"])
            self.assertNotIn(mock_secret, json.dumps(receipt))

    def test_sync_captures_allowlisted_host_state_and_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repo, live = self.fixture(Path(temp))
            roots: dict[str, Path] = {}
            hosts: dict[str, object] = {}
            for host in ("hermes", "codex", "omp"):
                root = Path(temp) / "hosts" / host
                root.mkdir(parents=True)
                (root / "config.json").write_text(json.dumps({"value": "baseline"}), encoding="utf-8")
                roots[host] = root
                hosts[host] = {
                    "artifacts": [
                        {
                            "id": "settings",
                            "kind": "config",
                            "source": "config.json",
                            "snapshot": f"hosts/{host}/config.json",
                            "format": "json",
                            "strategy": "merge",
                            "include": ["value"],
                        }
                    ]
                }
            (repo / "recovery.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "machine": "test",
                        "public_safe": True,
                        "hosts": hosts,
                    }
                ),
                encoding="utf-8",
            )
            recovery = load_tool("recovery")
            recovery.snapshot(repo / "recovery.json", repo / "recovery/current", roots, repo_root=repo)
            old_recovery_hash = self.fleet.sha256_file(repo / "recovery/current/manifest.json")
            (repo / "host-deltas.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "machine": "test",
                        "public_safe": True,
                        "entries": [
                            {
                                "id": "settings-snapshot",
                                "host": "hermes",
                                "category": "settings",
                                "owner": "agent-signal",
                                "source_identity": "recovery-artifact:hermes:settings",
                                "version_or_hash": f"sha256:{old_recovery_hash}",
                                "enablement": "managed",
                                "prerequisites": [],
                                "desired_state": "captured declarative settings",
                                "required": True,
                                "restore": {"kind": "recovery-artifact", "reference": "hermes:settings"},
                                "readback": {"kind": "none"},
                                "redaction": "public-artifact",
                            }
                        ],
                        "exclusions": [],
                    }
                ),
                encoding="utf-8",
            )
            (roots["hermes"] / "config.json").write_text(json.dumps({"value": "adopted"}), encoding="utf-8")

            first = self.reconcile.sync(
                repo,
                machine="test",
                recovery_roots=roots,
                skill_roots=[live],
                check_commands=[],
                capture_recovery=True,
            )
            second = self.reconcile.sync(
                repo,
                machine="test",
                recovery_roots=roots,
                skill_roots=[live],
                check_commands=[],
                capture_recovery=True,
            )

            self.assertEqual("applied", first["result"])
            self.assertEqual("unchanged", second["result"])
            self.assertEqual(first["request_id"], second["request_id"])
            captured = json.loads((repo / "recovery/current/hosts/hermes/config.json").read_text(encoding="utf-8"))
            self.assertEqual("adopted", captured["value"])
            self.assertEqual([], recovery.restore(repo / "recovery.json", repo / "recovery/current", roots, repo_root=repo)["changes"])
            new_recovery_hash = self.fleet.sha256_file(repo / "recovery/current/manifest.json")
            self.assertNotEqual(old_recovery_hash, new_recovery_hash)
            delta = json.loads((repo / "host-deltas.json").read_text(encoding="utf-8"))
            self.assertEqual(
                f"sha256:{new_recovery_hash}",
                delta["entries"][0]["version_or_hash"],
            )
            load_tool("host_deltas").load_manifest(repo / "host-deltas.json", repo)

    def test_non_admitted_missing_multi_origin_and_linked_changes_are_review_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repo, live = self.fixture(Path(temp))
            for owner in ("staged", "unknown"):
                if owner == "unknown":
                    write_skill(repo, owner, "unregistered")
                before_repo = digest(repo / "skills")
                before_live = digest(live)
                report = self.reconcile.sync(
                    repo,
                    machine="test",
                    adopt=[owner],
                    recovery_roots={},
                    skill_roots=[live],
                    check_commands=[],
                )
                with self.subTest(owner=owner):
                    self.assertEqual("review-required", report["result"])
                    self.assertEqual(before_repo, digest(repo / "skills"))
                    self.assertEqual(before_live, digest(live))

        with tempfile.TemporaryDirectory() as temp:
            repo, live = self.fixture(Path(temp))
            shutil.rmtree(live / "kept")
            before_repo = digest(repo / "skills")
            report = self.reconcile.sync(
                repo,
                machine="test",
                adopt=["kept"],
                recovery_roots={},
                skill_roots=[live],
                check_commands=[],
            )
            self.assertEqual("review-required", report["result"])
            self.assertEqual(before_repo, digest(repo / "skills"))
            self.assertFalse((live / "kept").exists())

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo, live = self.fixture(root)
            second = root / "second-live"
            self.fleet.apply_snapshot(repo / "render/fleet", second)
            (live / "kept/SKILL.md").write_text(
                "---\nname: kept\ndescription: Use when handling kept.\nlicense: MIT\n---\n\nfirst origin\n",
                encoding="utf-8",
            )
            (second / "kept/SKILL.md").write_text(
                "---\nname: kept\ndescription: Use when handling kept.\nlicense: MIT\n---\n\nsecond origin\n",
                encoding="utf-8",
            )
            before_repo = digest(repo / "skills")
            before_first = digest(live)
            before_second = digest(second)
            report = self.reconcile.sync(
                repo,
                machine="test",
                adopt=["kept"],
                recovery_roots={},
                skill_roots=[live, second],
                check_commands=[],
            )
            self.assertEqual("review-required", report["result"])
            self.assertEqual(before_repo, digest(repo / "skills"))
            self.assertEqual(before_first, digest(live))
            self.assertEqual(before_second, digest(second))

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo, live = self.fixture(root)
            external = root / "external.md"
            external.write_text("linked content", encoding="utf-8")
            skill_file = live / "kept/SKILL.md"
            skill_file.unlink()
            try:
                skill_file.symlink_to(external)
            except OSError as exc:
                self.skipTest(f"symbolic links unavailable: {exc}")
            before_repo = digest(repo / "skills")
            report = self.reconcile.sync(
                repo,
                machine="test",
                adopt=["kept"],
                recovery_roots={},
                skill_roots=[live],
                check_commands=[],
            )
            self.assertEqual("review-required", report["result"])
            self.assertEqual(before_repo, digest(repo / "skills"))
            self.assertTrue(skill_file.is_symlink())

    def test_invalid_adopted_skill_rolls_back_and_records_rejection(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repo, live = self.fixture(Path(temp))
            (live / "kept/SKILL.md").write_text("not valid skill frontmatter\n", encoding="utf-8")
            before_canonical = digest(repo / "skills")
            before_live = digest(live)

            report = self.reconcile.sync(
                repo,
                machine="test",
                adopt=["kept"],
                recovery_roots={},
                skill_roots=[live],
                check_commands=[["python", str(REPO / "tools" / "validate.py"), str(repo / "skills/kept")]],
            )

            self.assertEqual("rejected", report["result"])
            self.assertEqual(before_canonical, digest(repo / "skills"))
            self.assertEqual(before_live, digest(live))

    def test_failed_validation_rolls_back_and_records_rejection(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repo, live = self.fixture(Path(temp))
            (live / "kept" / "SKILL.md").write_text(
                "---\nname: kept\ndescription: Use when handling kept.\nlicense: MIT\n---\n\ncandidate\n",
                encoding="utf-8",
            )
            before_canonical = digest(repo / "skills")
            before_live = digest(live)

            report = self.reconcile.sync(
                repo,
                machine="test",
                adopt=["kept"],
                recovery_roots={},
                skill_roots=[live],
                check_commands=[["python", "-c", "raise SystemExit(7)"]],
            )

            self.assertEqual("rejected", report["result"])
            self.assertEqual(before_canonical, digest(repo / "skills"))
            self.assertEqual(before_live, digest(live))
            receipt = json.loads(next((repo / "reconciliation/requests").glob("*.json")).read_text(encoding="utf-8"))
            self.assertEqual("rejected", receipt["disposition"])
            self.assertEqual("failed", next(row["status"] for row in receipt["phases"] if row["name"] == "validate"))

    def test_failed_postflight_restores_every_fleet_mutation_not_only_selected_owner(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repo, live = self.fixture(Path(temp))
            obsolete = live / "obsolete"
            obsolete.mkdir()
            (obsolete / "SKILL.md").write_text(
                "---\nname: obsolete\ndescription: Use when handling obsolete.\nlicense: MIT\n---\n\nold\n",
                encoding="utf-8",
            )
            state_path = live / self.fleet.STATE_FILE
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state["skills"]["obsolete"] = {
                "sha256": self.fleet.directory_record(obsolete)["sha256"]
            }
            self.fleet.atomic_json(state_path, state)
            before = digest(live)

            with patch.object(
                self.reconcile.fleet,
                "verify_snapshot",
                return_value=[{"name": "forced", "status": "drift"}],
            ):
                report = self.reconcile.sync(
                    repo,
                    machine="test",
                    adopt=["kept"],
                    recovery_roots={},
                    skill_roots=[live],
                    check_commands=[],
                )

            self.assertEqual("rejected", report["result"])
            self.assertEqual(before, digest(live))
            self.assertTrue((live / "obsolete/SKILL.md").is_file())


if __name__ == "__main__":
    unittest.main()
