#!/usr/bin/env python
"""Render and safely reconcile Agent Signal skills across agent hosts."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import sys
import uuid
from pathlib import Path
from typing import Any

STATE_FILE = ".agent-signal-fleet.json"
MANIFEST_FILE = "manifest.json"
SKILL_NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
TRANSIENT_NAMES = {"__pycache__", ".pytest_cache", ".pytest-cache"}


def is_transient(path: Path, root: Path) -> bool:
    relative = path.relative_to(root)
    return any(part in TRANSIENT_NAMES for part in relative.parts) or path.suffix == ".pyc"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def directory_record(root: Path, *, allow_root_link: bool = False) -> dict[str, Any]:
    """Hash a skill directory and reject links in distributable source."""
    if not allow_root_link and is_linklike_path(root):
        raise RuntimeError(f"skill source is a link or junction: {root}")
    digest = hashlib.sha256()
    files: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink() or (path.is_dir() and is_linklike_directory(path)):
            raise RuntimeError(f"skill source contains a symbolic link or junction: {path}")
        if is_transient(path, root):
            continue
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        file_hash = sha256_file(path)
        files[relative] = file_hash
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(bytes.fromhex(file_hash))
    if "SKILL.md" not in files:
        raise RuntimeError(f"skill has no SKILL.md: {root}")
    return {"sha256": digest.hexdigest(), "files": files}


def registry(repo: Path) -> dict[str, dict[str, Any]]:
    data = json.loads((repo / "registry.json").read_text(encoding="utf-8"))
    if data.get("schema_version") != 1:
        raise RuntimeError("unsupported registry schema")
    items: dict[str, dict[str, Any]] = {}
    for item in data.get("skills", []):
        name = str(item.get("name", ""))
        if not SKILL_NAME_RE.fullmatch(name) or name in items:
            raise RuntimeError(f"invalid or duplicate registry skill: {name!r}")
        items[name] = item
    return items


def atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp-{uuid.uuid4().hex}")
    try:
        temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def is_linklike_path(path: Path) -> bool:
    if not os.path.lexists(path):
        return False
    attributes = getattr(os.lstat(path), "st_file_attributes", 0)
    return os.path.islink(path) or bool(attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))


def is_linklike_directory(path: Path) -> bool:
    return path.is_dir() and is_linklike_path(path)


def validated_snapshot_output(repo: Path, output: Path) -> Path:
    """Return a lexical in-repo output path without following reparse points."""
    repo = repo.resolve()
    candidate = output if output.is_absolute() else repo / output
    candidate = Path(os.path.abspath(candidate))
    try:
        relative = candidate.relative_to(repo)
    except ValueError as exc:
        raise RuntimeError(f"snapshot output must stay inside the repository: {candidate}") from exc
    if not relative.parts:
        raise RuntimeError("snapshot output cannot replace the repository root")

    current = repo
    for part in relative.parts:
        current = current / part
        if os.path.lexists(current) and is_linklike_path(current):
            raise RuntimeError(f"snapshot output path contains a link or junction: {current}")
    try:
        candidate.resolve(strict=False).relative_to(repo)
    except ValueError as exc:
        raise RuntimeError(f"snapshot output must stay inside the repository: {candidate}") from exc
    return candidate


def remove_tree(path: Path) -> None:
    if not (path.exists() or os.path.lexists(path)):
        return
    # pathlib reports some Windows junctions as directories even though shutil
    # correctly treats them as links. Unlink/rmdir the reparse point; never
    # recurse into its source.
    if path.is_dir() and not is_linklike_directory(path):
        shutil.rmtree(path)
    elif path.is_dir():
        os.rmdir(path)
    else:
        path.unlink()


def render_snapshot(repo: Path, output: Path) -> dict[str, Any]:
    """Render admitted repository skills into a deterministic snapshot."""
    repo = repo.resolve()
    output = validated_snapshot_output(repo, output)
    selected = {
        name: item
        for name, item in registry(repo).items()
        if item.get("status") == "admitted"
    }
    stage = output.with_name(f".{output.name}.stage-{uuid.uuid4().hex}")
    remove_tree(stage)
    (stage / "skills").mkdir(parents=True)
    records: dict[str, dict[str, Any]] = {}
    try:
        for name in sorted(selected):
            source = repo / "skills" / name
            if not source.is_dir():
                raise RuntimeError(f"admitted skill source is missing: {source}")
            record = directory_record(source)
            shutil.copytree(
                source,
                stage / "skills" / name,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache", ".pytest-cache"),
            )
            records[name] = record
        manifest = {
            "schema_version": 1,
            "registry_sha256": sha256_file(repo / "registry.json"),
            "skills": records,
        }
        atomic_json(stage / MANIFEST_FILE, manifest)
        previous = output.with_name(f".{output.name}.old-{uuid.uuid4().hex}")
        if output.exists():
            os.replace(output, previous)
        else:
            previous = None
        try:
            os.replace(stage, output)
        except Exception:
            if previous is not None and previous.exists():
                os.replace(previous, output)
            raise
        if previous is not None:
            remove_tree(previous)
        return manifest
    except Exception:
        remove_tree(stage)
        raise


def load_manifest(snapshot: Path) -> dict[str, Any]:
    path = snapshot / MANIFEST_FILE
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != 1 or not isinstance(data.get("skills"), dict):
        raise RuntimeError(f"invalid fleet manifest: {path}")
    for name, expected in data["skills"].items():
        if not SKILL_NAME_RE.fullmatch(name):
            raise RuntimeError(f"invalid skill name in fleet manifest: {name!r}")
        if not isinstance(expected, dict) or not SHA256_RE.fullmatch(str(expected.get("sha256", ""))):
            raise RuntimeError(f"invalid skill record in fleet manifest: {name}")
        source = snapshot / "skills" / name
        if not source.is_dir() or directory_record(source) != expected:
            raise RuntimeError(f"snapshot content does not match manifest: {name}")
    return data


def load_state(destination: Path) -> dict[str, Any]:
    path = destination / STATE_FILE
    if not path.exists():
        return {"schema_version": 1, "skills": {}}
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != 1 or not isinstance(data.get("skills"), dict):
        raise RuntimeError(f"invalid fleet state: {path}")
    for name, record in data["skills"].items():
        if not SKILL_NAME_RE.fullmatch(name):
            raise RuntimeError(f"invalid skill name in fleet state: {name!r}")
        if not isinstance(record, dict) or not SHA256_RE.fullmatch(str(record.get("sha256", ""))):
            raise RuntimeError(f"invalid skill record in fleet state: {name}")
    return data


def installed_hash(path: Path) -> str | None:
    if not path.is_dir():
        return None
    try:
        return str(directory_record(path, allow_root_link=True)["sha256"])
    except (OSError, RuntimeError):
        return None


def plan_snapshot(snapshot: Path, destination: Path) -> list[dict[str, str]]:
    manifest = load_manifest(snapshot)
    state = load_state(destination)
    desired: dict[str, dict[str, Any]] = manifest["skills"]
    managed: dict[str, dict[str, Any]] = state["skills"]
    actions: list[dict[str, str]] = []

    for name in sorted(set(desired) | set(managed)):
        target = destination / name
        present = target.exists() or target.is_symlink()
        current = installed_hash(target)
        wanted = desired.get(name, {}).get("sha256")
        prior = managed.get(name, {}).get("sha256")
        if name in desired:
            if not present:
                action = "add" if prior is None else "repair"
            elif current is None:
                action = "conflict"
            elif prior is None:
                action = "adopt" if current == wanted else "conflict"
            elif current == wanted:
                if is_linklike_directory(target):
                    action = "materialize"
                else:
                    action = "unchanged" if prior == wanted else "reconcile"
            elif current != prior:
                action = "conflict"
            else:
                action = "update"
        else:
            if not present:
                action = "forget"
            elif current == prior:
                action = "remove"
            else:
                action = "conflict"
        actions.append(
            {
                "name": name,
                "action": action,
                "current": current or "missing",
                "prior": str(prior or "unmanaged"),
                "desired": str(wanted or "retired"),
            }
        )
    state_path = destination / STATE_FILE
    if state_path.exists() and state.get("source_snapshot") != str(snapshot.resolve()):
        actions.append(
            {
                "name": STATE_FILE,
                "action": "reconcile-state",
                "current": str(state.get("source_snapshot", "missing")),
                "prior": "state",
                "desired": str(snapshot.resolve()),
            }
        )
    return actions


def apply_snapshot(snapshot: Path, destination: Path) -> list[dict[str, str]]:
    """Apply one snapshot, preserving unmanaged and locally modified skills."""
    manifest = load_manifest(snapshot)
    destination.mkdir(parents=True, exist_ok=True)
    actions = plan_snapshot(snapshot, destination)
    conflicts = [item["name"] for item in actions if item["action"] == "conflict"]
    if conflicts:
        raise RuntimeError("managed skill drift or unmanaged collision: " + ", ".join(conflicts))

    state = {
        "schema_version": 1,
        "source_snapshot": str(snapshot.resolve()),
        "manifest_sha256": sha256_file(snapshot / MANIFEST_FILE),
        "skills": {
            name: {"sha256": record["sha256"]}
            for name, record in sorted(manifest["skills"].items())
        },
    }
    stages: dict[str, Path] = {}
    applied: list[tuple[str, Path, Path | None]] = []
    committed = False
    try:
        # Finish every fallible copy before mutating the destination.
        for item in actions:
            if item["action"] not in {"add", "adopt", "materialize", "repair", "update"}:
                continue
            name = item["name"]
            stage = destination / f".{name}.fleet-stage-{uuid.uuid4().hex}"
            shutil.copytree(snapshot / "skills" / name, stage)
            stages[name] = stage

        for item in actions:
            name, action = item["name"], item["action"]
            target = destination / name
            if action in {"add", "adopt", "materialize", "repair", "update"}:
                old: Path | None = None
                if target.exists() or target.is_symlink():
                    old = destination / f".{name}.fleet-old-{uuid.uuid4().hex}"
                    os.replace(target, old)
                try:
                    os.replace(stages.pop(name), target)
                except Exception:
                    if old is not None and old.exists():
                        os.replace(old, target)
                    raise
                applied.append(("replace", target, old))
            elif action == "remove":
                old = destination / f".{name}.fleet-old-{uuid.uuid4().hex}"
                os.replace(target, old)
                applied.append(("remove", target, old))

        atomic_json(destination / STATE_FILE, state)
        committed = True
    finally:
        if not committed:
            for kind, target, old in reversed(applied):
                if kind == "replace":
                    remove_tree(target)
                if old is not None and old.exists():
                    os.replace(old, target)
        for stage in stages.values():
            remove_tree(stage)

    # State is committed; old directories are now disposable, not backups.
    for _, _, old in applied:
        if old is not None:
            remove_tree(old)
    return actions


def preflight_destinations(
    snapshot: Path, destinations: list[Path]
) -> list[tuple[Path, list[dict[str, str]]]]:
    planned = [(destination, plan_snapshot(snapshot, destination)) for destination in destinations]
    conflicts = [
        f"{destination}:{item['name']}"
        for destination, actions in planned
        for item in actions
        if item["action"] == "conflict"
    ]
    if conflicts:
        raise RuntimeError("managed skill drift or unmanaged collision: " + ", ".join(conflicts))
    return planned


def apply_destinations(
    snapshot: Path, destinations: list[Path]
) -> list[tuple[Path, list[dict[str, str]]]]:
    """Preflight every destination before mutating the first one."""
    preflight_destinations(snapshot, destinations)
    return [(destination, apply_snapshot(snapshot, destination)) for destination in destinations]


def verify_snapshot(snapshot: Path, destination: Path) -> list[dict[str, str]]:
    manifest = load_manifest(snapshot)
    state = load_state(destination)
    findings: list[dict[str, str]] = []
    if state.get("source_snapshot") != str(snapshot.resolve()):
        findings.append({"name": STATE_FILE, "status": "source-drift"})
    if state.get("manifest_sha256") != sha256_file(snapshot / MANIFEST_FILE):
        findings.append({"name": STATE_FILE, "status": "manifest-drift"})
    for name, expected in sorted(manifest["skills"].items()):
        current = installed_hash(destination / name)
        if current is None:
            findings.append({"name": name, "status": "missing"})
        elif current != expected["sha256"]:
            findings.append({"name": name, "status": "drift"})
        elif state["skills"].get(name, {}).get("sha256") != expected["sha256"]:
            findings.append({"name": name, "status": "untracked"})
    for name in sorted(set(state["skills"]) - set(manifest["skills"])):
        findings.append({"name": name, "status": "retired-managed"})
    return findings


def variables() -> dict[str, str]:
    return {
        "HOME": str(Path.home()),
        "SHARED_SKILLS_HOME": str(Path.home() / ".agents" / "skills"),
        "HERMES_HOME": str(
            Path(os.environ.get("HERMES_HOME", os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local")))
            / ("" if os.environ.get("HERMES_HOME") else "hermes")
        ),
        "CODEX_HOME": str(Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))),
        "OMP_HOME": str(Path.home() / ".omp" / "agent"),
    }


def resolve_template(value: str) -> Path:
    return Path(value.format_map(variables())).expanduser().resolve()


def load_fleet(repo: Path) -> dict[str, Any]:
    data = json.loads((repo / "fleet.json").read_text(encoding="utf-8"))
    if data.get("schema_version") != 1 or not isinstance(data.get("machines"), dict):
        raise RuntimeError("invalid fleet.json")
    snapshot_root = data.get("snapshot_root")
    if not isinstance(snapshot_root, str) or not snapshot_root:
        raise RuntimeError("invalid fleet snapshot_root")
    candidate = Path(snapshot_root)
    if (
        candidate.is_absolute()
        or "\\" in snapshot_root
        or any(part in {"", ".", ".."} for part in candidate.parts)
    ):
        raise RuntimeError("fleet snapshot_root must be a safe relative path")
    return data


def print_actions(actions: list[dict[str, str]], destination: Path) -> None:
    print(f"[{destination}]")
    if not actions:
        print("  no managed skills")
    for item in actions:
        print(f"  {item['action']:9} {item['name']}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("render", "diff", "apply", "verify"))
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--machine", default="local-windows")
    args = parser.parse_args(argv)
    repo = args.repo.resolve()
    config = load_fleet(repo)
    snapshot = validated_snapshot_output(repo, repo / config["snapshot_root"])

    if args.action == "render":
        result = render_snapshot(repo, snapshot)
        print(f"rendered {len(result['skills'])} admitted skills -> {snapshot}")
        return 0

    machine = config["machines"].get(args.machine)
    if machine is None:
        raise RuntimeError(f"unknown machine: {args.machine}")
    roots = sorted({resolve_template(value) for value in machine["skill_roots"]}, key=str)
    if not snapshot.exists():
        raise RuntimeError(f"snapshot missing; run render first: {snapshot}")

    failures = 0
    if args.action == "apply":
        for destination, actions in apply_destinations(snapshot, roots):
            print_actions(actions, destination)
        return 0

    for destination in roots:
        if args.action == "diff":
            actions = plan_snapshot(snapshot, destination)
            print_actions(actions, destination)
            failures += any(item["action"] == "conflict" for item in actions)
        else:
            findings = verify_snapshot(snapshot, destination)
            print(f"[{destination}]")
            if findings:
                for item in findings:
                    print(f"  {item['status']:15} {item['name']}")
                failures += 1
            else:
                print("  PASS snapshot and managed state match")
    return 1 if failures else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
