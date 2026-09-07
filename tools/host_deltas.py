#!/usr/bin/env python
"""Validate and read back public-safe host-native Agent Signal deltas."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import jsonschema

try:
    import fleet
    import recovery
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import fleet  # type: ignore
    import recovery  # type: ignore

Runner = Callable[[list[str]], tuple[int, str]]

ALLOWED_COMMAND_READBACKS = frozenset(
    {
        ("hermes", "--version"),
        ("codex", "--version"),
        ("omp", "--version"),
        ("hermes", "hooks", "list"),
        ("codex", "plugin", "list", "--json"),
        ("omp", "plugin", "list"),
        ("omp", "config", "get", "enabledProviders", "--json"),
        ("hermes", "curator", "status"),
    }
)


def _canonical_json(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def _validate_unique_ids(manifest: Mapping[str, Any]) -> None:
    ids = [str(item["id"]) for item in manifest.get("entries", [])]
    excluded = [str(item["id"]) for item in manifest.get("exclusions", [])]
    if len(ids) != len(set(ids)):
        raise RuntimeError("duplicate host-delta entry id")
    if len(excluded) != len(set(excluded)):
        raise RuntimeError("duplicate host-delta exclusion id")


def _canonical_fleet_digest(repo: Path) -> str:
    selected = {
        name: item
        for name, item in fleet.registry(repo).items()
        if item.get("status") == "admitted"
    }
    records: dict[str, dict[str, Any]] = {}
    for name in sorted(selected):
        source = repo / "skills" / name
        if not source.is_dir():
            raise RuntimeError(f"admitted skill source is missing: {source}")
        records[name] = fleet.directory_record(source)
    manifest = {
        "schema_version": 1,
        "registry_sha256": fleet.sha256_file(repo / "registry.json"),
        "skills": records,
    }
    # Match fleet.atomic_json exactly so an existing rendered manifest has the
    # same identity, without requiring ignored render output in a fresh clone.
    data = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def _bound_artifact_digest(source_identity: str, repo: Path) -> str | None:
    if source_identity.startswith("recovery-artifact:"):
        target = repo / "recovery" / "current" / "manifest.json"
        if not target.is_file():
            raise RuntimeError(f"host-delta binding target is missing: {target.relative_to(repo)}")
        return fleet.sha256_file(target)
    if source_identity.startswith("fleet:"):
        return _canonical_fleet_digest(repo)
    if not source_identity.startswith("repository:"):
        return None

    relative = source_identity.removeprefix("repository:")
    if (
        not relative
        or relative.startswith("/")
        or "\\" in relative
        or ":" in relative
        or any(part in {"", ".", ".."} for part in relative.split("/"))
    ):
        raise RuntimeError(f"invalid repository host-delta binding: {source_identity}")
    target = (repo / relative).resolve()
    try:
        target.relative_to(repo)
    except ValueError as exc:
        raise RuntimeError(f"repository host-delta binding escapes the repository: {source_identity}") from exc
    if not target.is_file():
        raise RuntimeError(f"host-delta binding target is missing: {target.relative_to(repo)}")
    return fleet.sha256_file(target)


def _validate_bindings(manifest: Mapping[str, Any], repo: Path) -> None:
    """Bind reproducible delta identities to the exact declared artifacts."""

    for item in manifest.get("entries", []):
        source_identity = str(item["source_identity"])
        digest = _bound_artifact_digest(source_identity, repo)
        if digest is None:
            continue
        expected = f"sha256:{digest}"
        actual = str(item["version_or_hash"])
        if actual != expected:
            raise RuntimeError(
                f"host-delta binding mismatch for {item['id']}: expected {expected}, got {actual}"
            )


def _validate_command_readbacks(manifest: Mapping[str, Any]) -> None:
    for item in manifest.get("entries", []):
        readback = item["readback"]
        if readback["kind"] != "command":
            continue
        argv = tuple(str(value) for value in readback["argv"])
        if argv not in ALLOWED_COMMAND_READBACKS:
            raise RuntimeError(
                f"unapproved host-delta command readback for {item['id']}: {' '.join(argv)}"
            )


def _load_manifest_unbound(path: Path, repo: Path) -> dict[str, Any]:
    """Load and validate manifest data without checking artifact hashes."""

    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"cannot load host-delta manifest: {exc}") from exc
    try:
        recovery._assert_public_safe(_canonical_json(manifest), label="host-deltas.json")
    except recovery.RecoveryError as exc:
        raise RuntimeError(f"host-delta manifest is not public-safe: {exc}") from exc
    schema_path = repo / "contracts" / "host-deltas.schema.json"
    if not schema_path.is_file():
        schema_path = Path(__file__).resolve().parents[1] / "contracts" / "host-deltas.schema.json"
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"cannot load host-delta schema: {exc}") from exc
    errors = sorted(
        jsonschema.Draft202012Validator(schema).iter_errors(manifest),
        key=lambda item: list(item.absolute_path),
    )
    if errors:
        error = errors[0]
        location = ".".join(str(part) for part in error.absolute_path) or "<root>"
        raise RuntimeError(f"host-delta schema: {location}: {error.message}")
    _validate_unique_ids(manifest)
    _validate_command_readbacks(manifest)
    return manifest


def load_manifest(path: str | Path, repo: str | Path) -> dict[str, Any]:
    """Load one schema-valid manifest and reject private or stale material."""

    path = Path(path)
    repo = Path(repo).resolve()
    manifest = _load_manifest_unbound(path, repo)
    _validate_bindings(manifest, repo.resolve())
    return manifest


def refresh_bindings(
    path: str | Path,
    repo: str | Path,
    *,
    source_prefixes: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Refresh deterministic artifact hashes, then validate the written manifest."""

    path = Path(path)
    repo = Path(repo).resolve()
    manifest = _load_manifest_unbound(path, repo)
    prefixes = tuple(source_prefixes or ())
    for item in manifest["entries"]:
        source_identity = str(item["source_identity"])
        if prefixes and not source_identity.startswith(prefixes):
            continue
        digest = _bound_artifact_digest(source_identity, repo)
        if digest is not None:
            item["version_or_hash"] = f"sha256:{digest}"
    fleet.atomic_json(path, manifest)
    return load_manifest(path, repo)


def _codex_executable() -> str | None:
    direct = shutil.which("codex")
    if direct:
        return direct
    local = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    candidates = sorted((local / "OpenAI" / "Codex" / "bin").glob("*/codex.exe"))
    return str(candidates[-1]) if candidates else None


def _resolve_argv(argv: Sequence[str]) -> list[str]:
    resolved = list(argv)
    if not resolved:
        return resolved
    if resolved[0] == "codex":
        executable = _codex_executable()
        if executable:
            resolved[0] = executable
    return resolved


def _run(argv: list[str]) -> tuple[int, str]:
    try:
        completed = subprocess.run(
            _resolve_argv(argv), capture_output=True, text=True, check=False, timeout=45
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 127, type(exc).__name__
    output = "\n".join(part for part in (completed.stdout, completed.stderr) if part)
    return completed.returncode, output


def _artifact_clean(
    reference: str,
    *,
    repo: Path,
    roots: Mapping[str, str | Path],
    plan: Mapping[str, Any] | None,
) -> bool:
    if ":" not in reference:
        return False
    host, artifact_id = reference.split(":", 1)
    if plan is None:
        plan = recovery.restore(
            repo / "recovery.json",
            repo / "recovery" / "current",
            roots,
            apply=False,
            repo_root=repo,
        )
    return not any(
        str(item.get("host")) == host and str(item.get("id")) == artifact_id
        for key in ("changes", "conflicts")
        for item in plan.get(key, [])
    )


def verify(
    manifest_path: str | Path,
    repo: str | Path,
    *,
    runner: Runner | None = None,
    roots: Mapping[str, str | Path] | None = None,
    skill_roots: Sequence[str | Path] | None = None,
    fleet_snapshot: str | Path | None = None,
    restored_ids: set[str] | None = None,
) -> dict[str, Any]:
    """Read back each declared delta without returning private command output.

    ``restored_ids`` is supplied only by a successful bootstrap transaction. It
    changes a successful readback from ``verified`` to ``restored``; it never
    turns a failed readback into success.
    """

    repo = Path(repo).resolve()
    manifest = load_manifest(manifest_path, repo)
    runner = runner or _run
    restored_ids = restored_ids or set()
    resolved_roots: Mapping[str, str | Path] = roots or recovery._default_roots()
    recovery_plan: Mapping[str, Any] | None = None
    if any(item["readback"]["kind"] == "recovery-artifact" for item in manifest["entries"]):
        recovery_plan = recovery.restore(
            repo / "recovery.json",
            repo / "recovery" / "current",
            resolved_roots,
            apply=False,
            repo_root=repo,
        )

    fleet_findings: list[dict[str, str]] | None = None
    entries: list[dict[str, Any]] = []
    required_failed = False
    for item in manifest["entries"]:
        readback = item["readback"]
        kind = readback["kind"]
        success = False
        available = True
        if kind == "command":
            argv = list(readback.get("argv", []))
            code, output = runner(argv)
            available = code not in {126, 127}
            success = code == 0
            if "contains" in readback:
                success = success and str(readback["contains"]) in output
            if "not_contains" in readback:
                success = success and str(readback["not_contains"]) not in output
        elif kind == "recovery-artifact":
            success = _artifact_clean(
                str(readback.get("reference", "")),
                repo=repo,
                roots=resolved_roots,
                plan=recovery_plan,
            )
        elif kind == "fleet":
            if fleet_findings is None:
                config = fleet.load_fleet(repo)
                snapshot = (
                    Path(fleet_snapshot).resolve()
                    if fleet_snapshot is not None
                    else fleet.validated_snapshot_output(repo, repo / str(config["snapshot_root"]))
                )
                if skill_roots is None:
                    machine = config["machines"].get(manifest["machine"])
                    raw_roots = machine.get("skill_roots", []) if isinstance(machine, Mapping) else []
                    destinations = [fleet.resolve_template(str(value)) for value in raw_roots]
                else:
                    destinations = [Path(value).resolve() for value in skill_roots]
                fleet_findings = [
                    finding
                    for destination in destinations
                    for finding in fleet.verify_snapshot(snapshot, destination)
                ]
            success = not fleet_findings
        elif kind == "file":
            raw = str(readback.get("path", ""))
            if raw.startswith("repo:"):
                target = repo / raw.removeprefix("repo:")
            elif ":" in raw:
                host, relative = raw.split(":", 1)
                target = Path(resolved_roots[host]) / relative
            else:
                target = repo / raw
            success = target.is_file()
            if success and "sha256" in readback:
                success = fleet.sha256_file(target) == readback["sha256"]
            if success and "contains" in readback:
                success = str(readback["contains"]) in target.read_text(encoding="utf-8")
        elif kind == "none":
            success = True

        if success:
            status = "restored" if item["id"] in restored_ids else "verified"
        elif not item["required"] and (
            not available or item["restore"]["kind"] == "manual-prerequisite"
        ):
            status = "prerequisite-missing"
        else:
            status = "failed"
            if item["required"]:
                required_failed = True
        entries.append(
            {
                "id": item["id"],
                "host": item["host"],
                "category": item["category"],
                "required": item["required"],
                "status": status,
            }
        )

    exclusions = [
        {
            "id": item["id"],
            "host": item["host"],
            "category": item["category"],
            "status": "excluded-private",
        }
        for item in manifest["exclusions"]
    ]
    return {
        "schema_version": 1,
        "machine": manifest["machine"],
        "passed": not required_failed,
        "entries": entries,
        "exclusions": exclusions,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("verify",))
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args(argv)
    manifest = args.manifest or args.repo / "host-deltas.json"
    report = verify(manifest, args.repo)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, KeyError, ValueError, RuntimeError, recovery.RecoveryError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
