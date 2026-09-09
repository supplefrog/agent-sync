#!/usr/bin/env python
"""Verify model-qualified standing instruction profiles."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path, PurePosixPath
from typing import Any

import jsonschema

try:
    import instruction_retirement
    import recovery
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import instruction_retirement  # type: ignore
    import recovery  # type: ignore


class ProfileError(RuntimeError):
    pass


def current_profile(repo: Path) -> Path:
    """Resolve the one declared current observation, without a model-name constant."""
    matches = [path for path in sorted((repo / "profiles").glob("*.json"))
               if _load(path).get("status") == "current-observed"]
    if len(matches) != 1:
        raise ProfileError(f"expected exactly one current-observed model profile, found {len(matches)}")
    return matches[0]


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProfileError(f"cannot read JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ProfileError(f"expected object in {path}")
    return value


def _repo_path(repo: Path, value: str, label: str) -> Path:
    pure = PurePosixPath(value)
    if pure.is_absolute() or ".." in pure.parts or "\\" in value:
        raise ProfileError(f"unsafe {label}: {value}")
    path = (repo / Path(*pure.parts)).resolve()
    try:
        path.relative_to(repo.resolve())
    except ValueError as exc:
        raise ProfileError(f"escaping {label}: {value}") from exc
    return path


def _validate(schema_path: Path, value: dict[str, Any], label: str) -> None:
    schema = _load(schema_path)
    validator = jsonschema.Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(value), key=lambda item: list(item.absolute_path))
    if errors:
        first = errors[0]
        location = ".".join(str(part) for part in first.absolute_path) or "<root>"
        raise ProfileError(f"{label} schema: {location}: {first.message}")


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _selector_observations(repo: Path) -> dict[str, dict[str, str]]:
    hermes = _load(repo / "recovery" / "current" / "hosts" / "hermes" / "config.json")
    codex = _load(repo / "recovery" / "current" / "hosts" / "codex" / "config.json")
    omp = _load(repo / "recovery" / "current" / "hosts" / "omp" / "config.json")
    omp_default = str(omp["modelRoles"]["default"])
    omp_provider, _, omp_model = omp_default.partition("/")
    return {
        "hermes": {
            "model": str(hermes["model"]["default"]),
            "provider": str(hermes["model"]["provider"]),
            "reasoning": str(hermes["agent"]["reasoning_effort"]),
        },
        "codex": {
            "model": str(codex["model"]),
            "provider": "openai-codex",
            "reasoning": str(codex["model_reasoning_effort"]),
        },
        "omp": {
            "model": omp_model,
            "provider": omp_provider,
            "reasoning": str(omp["defaultThinkingLevel"]),
        },
    }


def _verify_selector_observations(
    profile: dict[str, Any], observations: dict[str, dict[str, str]]
) -> None:
    for host, observed in observations.items():
        declared = profile["hosts"][host]
        expected = {
            "model": str(declared.get("model", profile["target"]["model"])),
            "provider": str(declared.get("provider", profile["target"]["provider"])),
            "reasoning": declared["reasoning"],
        }
        if observed != expected:
            raise ProfileError(
                f"selector mismatch for {host}: declared={expected} observed={observed}"
            )


def _version_command(host: str) -> list[str]:
    executable = shutil.which(host)
    if executable is None and host == "codex":
        candidates = [Path.home() / ".local" / "bin" / "codex.cmd"]
        local_appdata = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        candidates.extend(sorted((local_appdata / "OpenAI" / "Codex" / "bin").glob("*/codex.exe")))
        executable = next((str(path) for path in candidates if path.is_file()), None)
    if executable is None:
        raise ProfileError(f"live runtime is unavailable: {host}")
    if os.name == "nt" and str(executable).lower().endswith((".cmd", ".bat")):
        return ["cmd", "/c", str(executable), "--version"]
    return [str(executable), "--version"]


def _live_runtime_versions() -> dict[str, str]:
    patterns = {
        "hermes": re.compile(r"Hermes Agent v?([^\s]+)"),
        "codex": re.compile(r"codex-cli\s+([^\s]+)"),
        "omp": re.compile(r"omp[/\s]+([^\s]+)"),
    }
    observed: dict[str, str] = {}
    for host in ("hermes", "codex", "omp"):
        try:
            completed = subprocess.run(
                _version_command(host),
                capture_output=True,
                text=True,
                check=False,
                timeout=30,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ProfileError(f"cannot inspect live runtime {host}: {exc}") from exc
        output = "\n".join((completed.stdout, completed.stderr))
        match = patterns[host].search(output)
        if completed.returncode != 0 or match is None:
            raise ProfileError(f"cannot parse live runtime version for {host}")
        observed[host] = match.group(1)
    return observed


def _verify_live_environment(repo: Path, matrix: dict[str, Any]) -> None:
    roots = recovery._default_roots()
    plan = recovery.restore(
        repo / "recovery.json",
        repo / "recovery" / "current",
        roots,
        apply=False,
        force_text=False,
        repo_root=repo,
    )
    if plan["changes"] or plan["conflicts"]:
        raise ProfileError(
            f"live recovery state mismatch: changes={plan['changes']} conflicts={plan['conflicts']}"
        )
    observed_versions = _live_runtime_versions()
    expected_versions = {
        host: str(matrix["hosts"][host]["cli_version"])
        for host in ("hermes", "codex", "omp")
    }
    if observed_versions != expected_versions:
        raise ProfileError(
            f"live runtime mismatch: expected={expected_versions} observed={observed_versions}"
        )
    omp_root = roots["omp"]
    native_agents = omp_root / "AGENTS.md"
    if native_agents.is_file() and native_agents.read_text(encoding="utf-8").strip():
        raise ProfileError("live OMP native AGENTS.md shadows the declared Codex inheritance")
    omp_config = recovery._read_config(omp_root / "config.yml", "yaml")
    disabled = omp_config.get("disabledProviders", [])
    if isinstance(disabled, list):
        codex_disabled = any(
            item == "codex"
            or (isinstance(item, dict) and "codex" in item.get("providers", []))
            for item in disabled
        )
        if codex_disabled:
            raise ProfileError("live OMP codex discovery provider is disabled")


def _unique_by_id(items: list[dict[str, Any]], label: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in items:
        item_id = str(item["id"])
        if item_id in result:
            raise ProfileError(f"duplicate {label} id: {item_id}")
        result[item_id] = item
    return result


def verify_profile(repo: Path, profile_path: Path, *, live: bool = True) -> dict[str, Any]:
    repo = repo.resolve()
    profile = _load(profile_path)
    _validate(repo / "contracts" / "model-profile.schema.json", profile, "model profile")

    surfaces_path = _repo_path(repo, profile["contracts"]["surfaces"], "surface contract")
    units_path = _repo_path(repo, profile["contracts"]["units"], "instruction-unit contract")
    manifest_path = _repo_path(repo, profile["contracts"]["recovery_manifest"], "recovery manifest")
    surfaces_doc = _load(surfaces_path)
    units_doc = _load(units_path)
    _validate(repo / "contracts" / "instruction-surfaces.schema.json", surfaces_doc, "instruction surfaces")
    _validate(repo / "contracts" / "instruction-units.schema.json", units_doc, "instruction units")

    manifest = recovery.verify_snapshot(repo / "recovery.json", manifest_path.parent)
    surfaces = _unique_by_id(surfaces_doc["surfaces"], "surface")
    units = _unique_by_id(units_doc["units"], "instruction unit")
    manifest_artifacts = {row["snapshot"]: row for row in manifest["artifacts"]}

    for surface in surfaces.values():
        if surface["backup"] != "captured":
            continue
        artifact = surface.get("artifact")
        if not artifact:
            raise ProfileError(f"captured surface has no artifact: {surface['id']}")
        artifact_path = _repo_path(repo, artifact, f"surface artifact {surface['id']}")
        if not artifact_path.is_file():
            raise ProfileError(f"missing surface artifact: {artifact}")
        try:
            snapshot_rel = artifact_path.relative_to(manifest_path.parent).as_posix()
        except ValueError as exc:
            raise ProfileError(f"captured surface is outside recovery snapshot: {artifact}") from exc
        record = manifest_artifacts.get(snapshot_rel)
        if record is None or record["sha256"] != _hash(artifact_path):
            raise ProfileError(f"surface artifact is not bound to recovery manifest: {artifact}")

    for route_id, route in profile["writing_routes"].items():
        if route["loading"] != "on-demand":
            raise ProfileError(f"writing route must remain on-demand: {route_id}")
        owner = _repo_path(repo, route["owner"], f"writing owner {route_id}")
        entrypoint = owner / "SKILL.md" if owner.is_dir() else owner
        if not entrypoint.is_file():
            raise ProfileError(f"missing writing owner: {route['owner']}")

    report_hosts: dict[str, Any] = {}
    for host, host_profile in profile["hosts"].items():
        selected_surfaces: list[str] = host_profile["effective_surfaces"]
        for surface_id in selected_surfaces:
            surface = surfaces.get(surface_id)
            if surface is None:
                raise ProfileError(f"unknown instruction surface for {host}: {surface_id}")
            if surface["status"] in {"retired", "disabled", "reference"}:
                raise ProfileError(f"{surface['status']} surface selected for {host}: {surface_id}")
            if host not in surface["hosts"] and "provider" not in surface["hosts"]:
                raise ProfileError(f"instruction surface is not valid for {host}: {surface_id}")

        selected_units: list[str] = host_profile["effective_units"]
        no_managed_standing_reason = host_profile.get("no_managed_standing_reason")
        if not selected_units and not no_managed_standing_reason:
            raise ProfileError(f"empty managed standing state requires an observed reason for {host}")
        if selected_units and no_managed_standing_reason:
            raise ProfileError(f"managed standing units conflict with no-managed-standing reason for {host}")
        total_bytes = 0
        source_hashes: set[str] = set()
        normalized_units: dict[str, str] = {}
        for unit_id in selected_units:
            unit = units.get(unit_id)
            if unit is None:
                raise ProfileError(f"unknown instruction unit for {host}: {unit_id}")
            if unit["status"] != "effective":
                raise ProfileError(f"non-effective instruction unit selected for {host}: {unit_id}")
            if host not in unit["hosts"]:
                raise ProfileError(f"instruction unit is not valid for {host}: {unit_id}")
            text = instruction_retirement.unit_text(repo, unit)
            normalized = " ".join(text.split()).casefold()
            if normalized in normalized_units:
                raise ProfileError(
                    f"duplicate effective instruction for {host}: {unit_id} and {normalized_units[normalized]}"
                )
            normalized_units[normalized] = unit_id
            total_bytes += len(text.encode("utf-8"))
            source_hashes.add(_hash(_repo_path(repo, unit["path"], f"instruction source {unit_id}")))

        declared_hashes = set(host_profile["artifact_sha256"])
        if source_hashes != declared_hashes:
            raise ProfileError(
                f"artifact hash mismatch for {host}: declared={sorted(declared_hashes)} actual={sorted(source_hashes)}"
            )
        budget = int(profile["context_policy"]["max_standing_bytes"][host])
        if total_bytes > budget:
            raise ProfileError(f"standing byte budget exceeded for {host}: {total_bytes}>{budget}")
        report_host = {
            "runtime": host_profile["runtime"],
            "model": host_profile.get("model", profile["target"]["model"]),
            "provider": host_profile.get("provider", profile["target"]["provider"]),
            "reasoning": host_profile["reasoning"],
            "bytes": total_bytes,
            "budget": budget,
            "units": selected_units,
            "surfaces": selected_surfaces,
            "artifact_sha256": sorted(source_hashes),
        }
        if no_managed_standing_reason:
            report_host["no_managed_standing_reason"] = no_managed_standing_reason
        report_hosts[host] = report_host

    evidence = profile["evidence"]
    if profile["status"] == "current-observed":
        if not evidence:
            raise ProfileError("current-observed profile requires evidence")
        for rel in evidence:
            path = _repo_path(repo, rel, "profile evidence")
            if not rel.startswith("evals/results/") or not path.is_file():
                raise ProfileError(f"missing profile evidence: {rel}")
        observations = _selector_observations(repo)
        _verify_selector_observations(profile, observations)
        matrix = _load(repo / "contracts" / "surface-matrix.json")
        runtime_prefix = {"hermes": "Hermes Agent", "codex": "codex-cli", "omp": "omp"}
        for host, declared in profile["hosts"].items():
            version = str(matrix["hosts"][host]["cli_version"])
            expected_runtime = f"{runtime_prefix[host]} {version}"
            if declared["runtime"] != expected_runtime:
                raise ProfileError(
                    f"runtime mismatch for {host}: declared={declared['runtime']} expected={expected_runtime}"
                )
        if live:
            _verify_live_environment(repo, matrix)

    return {
        "schema_version": 1,
        "profile": profile["id"],
        "status": profile["status"],
        "verification_mode": "live" if live else "artifact-only",
        "model": profile["target"]["model"],
        "provider": profile["target"]["provider"],
        "reasoning": profile["target"]["reasoning"],
        "hosts": report_hosts,
        "writing_routes": profile["writing_routes"],
        "evidence": evidence,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument(
        "--profile",
        type=Path,
        default=None,
        help="explicit profile; default resolves the one current-observed profile",
    )
    parser.add_argument(
        "--artifact-only",
        action="store_true",
        help="verify repository bindings without checking the installed live runtimes",
    )
    args = parser.parse_args(argv)
    repo = args.repo.resolve()
    try:
        profile_path = (args.profile if args.profile.is_absolute() else repo / args.profile) if args.profile else current_profile(repo)
        report = verify_profile(repo, profile_path, live=not args.artifact_only)
    except ProfileError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
