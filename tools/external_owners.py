"""Read-only, hash-bound coexistence for explicitly reviewed Paseo packages.

A product marker is not authentication or admission. Only a reviewed exact
machine/root/name record plus its pinned bytes can produce an observation.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping

import jsonschema
import yaml

import fleet

MARKER = ".paseo-managed-files.json"
CONTRACT = "contracts/external-owners.json"


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _json(raw: bytes):
    return json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object)


def lexical_root(value: str | Path) -> Path:
    """Preserve links for inspection rather than resolving them away."""
    expanded = Path(value).expanduser()
    if ".." in expanded.parts:
        raise RuntimeError("external-owner root contains traversal")
    return Path(os.path.abspath(expanded))


def reject_link_chain(path: Path) -> None:
    for part in [*reversed(path.parents), path]:
        if fleet.is_linklike_path(part):
            raise RuntimeError("external-owner path contains a link or reparse point")


def load_contract(repo: Path, config: Mapping[str, Any], registry: Mapping[str, Any]) -> list[dict[str, Any]]:
    path = repo / CONTRACT
    if not os.path.lexists(path):
        return []  # Old checkouts grant no exceptions; not an ignore list.
    try:
        reject_link_chain(path)
        data = _json(path.read_bytes())
        # Use the validator shipped with this code, not a caller-controlled schema.
        schema = _json((Path(__file__).resolve().parents[1] / "contracts/external-owners.schema.json").read_bytes())
        jsonschema.Draft202012Validator(schema).validate(data)
        if type(data["schema_version"]) is not int:
            raise ValueError("invalid schema version")
        records = data["packages"]
        seen = set()
        canonical = {name.casefold() for name in registry}
        if (repo / "skills").is_dir():
            canonical.update(child.name.casefold() for child in (repo / "skills").iterdir())
        for record in records:
            machine, root, name = record["machine"], record["skill_root"], record["name"]
            if (not fleet.SKILL_NAME_RE.fullmatch(name) or not fleet.SKILL_NAME_RE.fullmatch(machine)
                    or not fleet.SHA256_RE.fullmatch(record["marker_sha256"])):
                raise ValueError("invalid exact identifier or hash")
            if root not in config.get("machines", {}).get(machine, {}).get("skill_roots", []):
                raise ValueError("unconfigured machine/root")
            resolved = lexical_root(root.format_map(fleet.variables()))
            key = (machine, os.path.normcase(str(resolved)), name.casefold())
            if key in seen or name.casefold() in canonical:
                raise ValueError("duplicate or canonical ownership collision")
            seen.add(key)
        return records
    except (OSError, ValueError, KeyError, TypeError, jsonschema.ValidationError) as exc:
        raise RuntimeError("invalid external-owner contract; review required") from exc


def for_destination(records, machine: str, destination: Path, desired: set[str], managed: set[str]):
    selected = {}
    for record in records:
        root = lexical_root(record["skill_root"].format_map(fleet.variables()))
        if record["machine"] == machine and root == destination:
            selected[record["name"]] = record
    collisions = {name.casefold() for name in desired | managed} & {name.casefold() for name in selected}
    if collisions:
        raise RuntimeError("external-owner collides with fleet ownership: " + ", ".join(sorted(collisions)))
    return selected


def observe(package: Path, record: Mapping[str, Any]) -> dict[str, Any]:
    """Validate a present package without granting any mutation authority.

    The reviewed v1 Paseo shape is intentionally just SKILL.md and its marker.
    New support files, even product-marked ones, require a contract/code review.
    """
    result = {"claimed_external_owner": record["owner"], "disposition": "review-required",
              "change_class": "external-owner-drift", "reason": "external package identity failed validation"}
    try:
        reject_link_chain(package)
        if not package.is_dir():
            return result
        children = list(package.iterdir())
        if {child.name for child in children} != {MARKER, "SKILL.md"}:
            return result
        if any(fleet.is_linklike_path(child) or not child.is_file() for child in children):
            return result
        raw = (package / MARKER).read_bytes()
        marker_hash = hashlib.sha256(raw).hexdigest()
        if marker_hash != record["marker_sha256"]:
            return result
        marker = _json(raw)
        if (not isinstance(marker, dict) or set(marker) != {"version", "files"}
                or type(marker["version"]) is not int or marker["version"] != 1
                or not isinstance(marker["files"], dict) or set(marker["files"]) != {"SKILL.md"}):
            return result
        content = (package / "SKILL.md").read_bytes()
        expected = marker["files"]["SKILL.md"]
        if not isinstance(expected, str) or not fleet.SHA256_RE.fullmatch(expected):
            return result
        if hashlib.sha256(content).hexdigest() != expected:
            return result
        lines = content.decode("utf-8").splitlines()
        if not lines or lines[0] != "---":
            return result
        end = lines.index("---", 1)
        frontmatter = yaml.safe_load("\n".join(lines[1:end]))
        if not isinstance(frontmatter, dict) or frontmatter.get("name") != record["name"]:
            return result
        return {"owner": "external:" + record["owner"], "external_owner": record["owner"],
                "marker_sha256": marker_hash, "content_sha256": expected,
                "source_action": "observe-external", "change_class": "reviewed-external-owner",
                "disposition": "no-action", "route": "none"}
    except (OSError, ValueError, RuntimeError, yaml.YAMLError):
        return result
