#!/usr/bin/env python
"""Public-safe Agent Sync state snapshots and restores.

Only policy-allowlisted declarative values are copied. Secrets, auth state,
sessions, memory, logs, caches, and arbitrary home-directory content are never
implicitly traversed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
from collections.abc import Iterable, Sequence
from copy import deepcopy
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

import yaml
import jsonschema

try:
    import toml
except ImportError:  # pragma: no cover - exercised only on incomplete installs
    toml = None


class RecoveryError(RuntimeError):
    """Raised when snapshot or restore safety cannot be proven."""


HOSTS = ("hermes", "codex", "omp")
_HOST_SET = frozenset(HOSTS)


_SECRET_PATH_PART = re.compile(
    r"(?:^|_)(?:api_?keys?|tokens?|passwords?|passwds?|secrets?|credentials?|auths?|cookies?|"
    r"private_?keys?|session_?keys?|user_?ids?|chat_?ids?|device_?ids?|home_?channels?|"
    r"allowed_?users?|phones?|emails?|webhooks?)(?:$|_)",
    re.IGNORECASE,
)
_SAFE_SECRET_NAMED_PATHS = {
    "compression.proactive_prune_tokens",
    "security.redact_secrets",
    "features.memories",
    "memory.backend",
    "memory.flush_min_turns",
    "memory.memory_char_limit",
    "memory.memory_enabled",
    "memory.nudge_interval",
    "memory.provider",
    "memory.user_char_limit",
    "memory.user_profile_enabled",
    "memory.write_approval",
    "sessions.auto_prune",
    "sessions.min_interval_hours",
    "sessions.retention_days",
    "sessions.vacuum_after_prune",
    "sessions.write_json_snapshots",
}
_SAFE_NONNEGATIVE_INTEGER_PATHS = {
    "compression.proactive_prune_tokens",
}
_SENSITIVE_CONFIG_PARTS = {
    "memory",
    "memories",
    "session",
    "sessions",
    "oauth",
    "oauths",
    "pairing",
    "pairings",
}
_SECRET_VALUE_PATTERNS = (
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/-]{12,}"),
    re.compile(r"\b(?:sk-|ghp|github_pat|xox[baprs]|AKIA)[-_A-Za-z0-9]{12,}\b"),
    re.compile(r"(?i)https?://[^\s/@:]+:[^\s/@]+@"),
)
_BLOCKED_SOURCE_PARTS = re.compile(
    r"(?:^|[-_.])(?:\.env|auths?|credentials?|secrets?|sessions?|memor(?:y|ies)|"
    r"histor(?:y|ies)|logs?|caches?|cookies?|keyrings?|passwords?|passwds?|tokens?|"
    r"api[-_.]?keys?|private[-_.]?keys?|oauths?|pairings?|state\.db)(?:$|[-_.])",
    re.IGNORECASE,
)
_PORTABLE_PLACEHOLDERS = {
    "HOME": "{{agent-signal:HOME}}",
    "HERMES_HOME": "{{agent-signal:HERMES_HOME}}",
    "CODEX_HOME": "{{agent-signal:CODEX_HOME}}",
    "OMP_HOME": "{{agent-signal:OMP_HOME}}",
    "AGENT_SIGNAL_ROOT": "{{agent-signal:AGENT_SIGNAL_ROOT}}",
}


def _canonical_json(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def _canonical_newlines(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _load_policy(path: Path) -> dict[str, Any]:
    try:
        policy = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RecoveryError(f"cannot read recovery policy {path}: {exc}") from exc
    schema_path = path.parent / "contracts" / "recovery.schema.json"
    if schema_path.is_file():
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        errors = sorted(
            jsonschema.Draft202012Validator(schema).iter_errors(policy),
            key=lambda item: list(item.absolute_path),
        )
        if errors:
            error = errors[0]
            location = ".".join(str(part) for part in error.absolute_path) or "<root>"
            raise RecoveryError(f"recovery policy schema: {location}: {error.message}")
    _validate_policy(policy)
    return policy


def _blocked_source(source: PurePosixPath, kind: str) -> bool:
    # Explicitly allowlisted skill documentation/source can describe sessions,
    # auth or memory without being that private state. Data/credential files
    # keep the original denylist, as do all paths outside the skills tree.
    if (kind == "text" and source.parts[0] in {"skills", "plugins"}
            and len(source.parts) >= 3 and source.suffix.lower() in {".md", ".py", ".js", ".ts", ".sh"}
            and not any(p.startswith(".") for p in source.parts)):
        return False
    return any(_BLOCKED_SOURCE_PARTS.search(part) for part in source.parts)


def _validate_policy(policy: Mapping[str, Any]) -> None:
    if policy.get("schema_version") != 1:
        raise RecoveryError("recovery policy schema_version must be 1")
    if policy.get("public_safe") is not True:
        raise RecoveryError("recovery policy must declare public_safe: true")
    hosts = policy.get("hosts")
    if not isinstance(hosts, dict) or not hosts:
        raise RecoveryError("recovery policy must define hosts")
    seen: set[str] = set()
    seen_sources: set[str] = set()
    seen_snapshots: set[str] = set()
    for host, host_policy in hosts.items():
        if not isinstance(host, str) or not host:
            raise RecoveryError("host names must be non-empty strings")
        artifacts = host_policy.get("artifacts") if isinstance(host_policy, dict) else None
        if not isinstance(artifacts, list) or not artifacts:
            raise RecoveryError(f"host {host!r} must define artifacts")
        for artifact in artifacts:
            if not isinstance(artifact, dict):
                raise RecoveryError(f"host {host!r} has a non-object artifact")
            artifact_id = artifact.get("id")
            identity = f"{host}:{artifact_id}"
            if not isinstance(artifact_id, str) or not artifact_id or identity in seen:
                raise RecoveryError(f"duplicate or invalid artifact id: {identity}")
            seen.add(identity)
            source = _canonical_relative(artifact.get("source"), label=f"{identity} source")
            if "capture_mount" in artifact:
                mount = _canonical_relative(artifact["capture_mount"], label=f"{identity} capture mount")
                if (artifact.get("kind") != "text" or len(mount.parts) < 2
                        or mount.parts[0] not in {"skills", "plugins"}
                        or not source.is_relative_to(mount) or source == mount):
                    raise RecoveryError(f"{identity} has invalid capture mount")
            if _blocked_source(source, artifact.get("kind")):
                raise RecoveryError(f"blocked source artifact: {identity} ({source.as_posix()})")
            snapshot_path = _canonical_relative(
                artifact.get("snapshot"), label=f"{identity} snapshot"
            )
            source_identity = f"{host}:{source.as_posix()}"
            if source_identity in seen_sources:
                raise RecoveryError(f"duplicate artifact source: {source_identity}")
            seen_sources.add(source_identity)
            snapshot_identity = snapshot_path.as_posix()
            if snapshot_identity in seen_snapshots:
                raise RecoveryError(f"duplicate artifact snapshot: {snapshot_identity}")
            seen_snapshots.add(snapshot_identity)
            if artifact.get("kind") not in {"config", "text"}:
                raise RecoveryError(f"{identity} kind must be config or text")
            if artifact.get("strategy") not in {"merge", "replace-if-absent"}:
                raise RecoveryError(f"{identity} has unsupported strategy")
            replacements = artifact.get("replace_sha256", [])
            if (not isinstance(replacements, list)
                    or any(not isinstance(h, str) or not re.fullmatch(r"[a-f0-9]{64}", h) for h in replacements)
                    or (replacements and artifact["kind"] != "text")):
                raise RecoveryError(f"{identity} has invalid reviewed replacement hashes")
            if artifact["kind"] == "config":
                if artifact.get("format") not in {"json", "yaml", "toml"}:
                    raise RecoveryError(f"{identity} has unsupported config format")
                include = artifact.get("include")
                if not isinstance(include, list) or not include:
                    raise RecoveryError(f"{identity} must define an include list")
                for dotted in include:
                    if not isinstance(dotted, str) or not dotted or ".." in dotted.split("."):
                        raise RecoveryError(f"{identity} has invalid config path {dotted!r}")
                    if _secret_path(dotted):
                        raise RecoveryError(f"secret-bearing config path is forbidden: {dotted}")
            elif artifact.get("format") != "text":
                raise RecoveryError(f"{identity} text artifact must use text format")


def _canonical_relative(raw: Any, *, label: str) -> PurePosixPath:
    if not isinstance(raw, str) or not raw or "\\" in raw:
        raise RecoveryError(f"{label} must be a relative canonical path")
    path = PurePosixPath(raw)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise RecoveryError(f"{label} must be a relative canonical path")
    return path


def _secret_path(dotted: str) -> bool:
    if dotted in _SAFE_SECRET_NAMED_PATHS:
        return False
    leaf = dotted.rsplit(".", 1)[-1].lower()
    if leaf.endswith(("_env", "_env_var")):
        return False
    if any(part.casefold() in _SENSITIVE_CONFIG_PARTS for part in dotted.split(".")):
        return True
    return any(_SECRET_PATH_PART.search(part) for part in dotted.split("."))


def _is_reparse_point(path: Path) -> bool:
    try:
        info = path.lstat()
    except FileNotFoundError:
        return False
    if stat.S_ISLNK(info.st_mode):
        return True
    attrs = getattr(info, "st_file_attributes", 0)
    flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return bool(attrs & flag)


def _assert_no_reparse_ancestors(path: Path, *, label: str) -> Path:
    absolute = Path(os.path.abspath(os.fspath(path)))
    current = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        current = current / part
        if (current.exists() or current.is_symlink()) and _is_reparse_point(current):
            raise RecoveryError(f"{label} crosses a reparse point or symlink: {current}")
    return absolute


def _safe_join(root: Path, relative: str, *, must_exist: bool) -> Path:
    rel = _canonical_relative(relative, label="artifact path")
    root = _assert_no_reparse_ancestors(root, label="root path").resolve(strict=False)
    current = root
    for part in rel.parts:
        current = current / part
        if current.exists() or current.is_symlink():
            if _is_reparse_point(current):
                raise RecoveryError(f"artifact path crosses a reparse point or symlink: {current}")
    try:
        current.resolve(strict=False).relative_to(root)
    except ValueError as exc:
        raise RecoveryError(f"artifact path escapes root: {relative}") from exc
    if must_exist and not current.is_file():
        raise RecoveryError(f"required artifact is missing or not a file: {current}")
    return current


def _read_config(path: Path, fmt: str) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    try:
        if fmt == "json":
            value = json.loads(text)
        elif fmt == "yaml":
            value = yaml.safe_load(text)
        elif fmt == "toml":
            if toml is None:
                raise RecoveryError("the toml package is required for TOML recovery")
            value = toml.loads(text)
        else:  # pragma: no cover - guarded by policy validation
            raise RecoveryError(f"unsupported config format: {fmt}")
    except (ValueError, yaml.YAMLError) as exc:
        raise RecoveryError(f"cannot parse {fmt} config {path}: {exc}") from exc
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise RecoveryError(f"config root must be an object: {path}")
    return value


def _serialize_config(value: Mapping[str, Any], fmt: str) -> bytes:
    if fmt == "json":
        return _canonical_json(value)
    if fmt == "yaml":
        return yaml.safe_dump(
            dict(value), sort_keys=False, allow_unicode=True, default_flow_style=False
        ).encode("utf-8")
    if fmt == "toml":
        if toml is None:
            raise RecoveryError("the toml package is required for TOML recovery")
        return toml.dumps(dict(value)).encode("utf-8")
    raise RecoveryError(f"unsupported config format: {fmt}")


def _get_dotted(value: Mapping[str, Any], dotted: str) -> Any:
    current: Any = value
    for part in dotted.split("."):
        if not isinstance(current, Mapping) or part not in current:
            raise RecoveryError(f"allowlisted config path is missing: {dotted}")
        current = current[part]
    return deepcopy(current)


def _set_dotted(value: dict[str, Any], dotted: str, selected: Any) -> None:
    parts = dotted.split(".")
    current = value
    for part in parts[:-1]:
        child = current.get(part)
        if child is None:
            child = {}
            current[part] = child
        if not isinstance(child, dict):
            raise RecoveryError(f"config path collides with scalar: {dotted}")
        current = child
    current[parts[-1]] = selected


def _assert_no_secret_paths(value: Any, prefix: str) -> None:
    if prefix in _SAFE_NONNEGATIVE_INTEGER_PATHS:
        if type(value) is not int or value < 0:
            raise RecoveryError(
                f"safe token-budget config path must be a non-negative integer: {prefix}"
            )
        return
    if isinstance(value, Mapping):
        for key, child in value.items():
            dotted = f"{prefix}.{key}" if prefix else str(key)
            if _secret_path(dotted):
                raise RecoveryError(f"secret-bearing config path is forbidden: {dotted}")
            _assert_no_secret_paths(child, dotted)
    elif isinstance(value, list):
        for child in value:
            _assert_no_secret_paths(child, prefix)


def _logical_home(roots: Mapping[str, Path]) -> Path:
    if not roots:
        return Path.home()
    try:
        return Path(os.path.commonpath([str(Path(path).resolve(strict=False)) for path in roots.values()]))
    except ValueError:
        return Path.home()


def _normalize_hosts(hosts: Iterable[str] | None) -> tuple[str, ...]:
    """Validate and canonically order an optional host selection."""

    if hosts is None:
        return HOSTS
    if isinstance(hosts, str):
        values = [hosts]
    else:
        values = list(hosts)
    if not values:
        raise RecoveryError("--host requires at least one host")
    invalid = [value for value in values if not isinstance(value, str)]
    unknown = sorted({value for value in values if isinstance(value, str) and value not in _HOST_SET})
    if invalid:
        unknown.extend(str(value) for value in invalid)
    if unknown:
        raise RecoveryError(
            f"unknown host(s): {', '.join(str(value) for value in unknown)}; "
            f"choose from {', '.join(HOSTS)}"
        )
    selected = set(values)
    return tuple(host for host in HOSTS if host in selected)


def _selected_roots(
    roots: Mapping[str, str | Path], hosts: Iterable[str] | None
) -> tuple[tuple[str, ...], dict[str, Path]]:
    """Return only selected roots, validating their filesystem boundaries."""

    selected_hosts = _normalize_hosts(hosts)
    selected_roots: dict[str, Path] = {}
    for host in selected_hosts:
        if host not in roots:
            raise RecoveryError(f"missing host root: {host}")
        root = Path(roots[host])
        _assert_no_reparse_ancestors(root, label=f"{host} root")
        selected_roots[host] = root
    return selected_hosts, selected_roots


def _target_home(roots: Mapping[str, Path], hosts: Sequence[str]) -> Path:
    """Infer a target home without inspecting any unselected host root."""

    selected = {host: Path(roots[host]) for host in hosts}
    if len(selected) > 1:
        return _logical_home(selected)
    host, root = next(iter(selected.items()))
    root = Path(os.path.abspath(root))
    # The standard roots are ``<home>/.codex``, ``<home>/.hermes`` (or
    # ``<home>/AppData/Local/hermes``), and ``<home>/.omp/agent``.  Explicit
    # target roots in tests and clone workflows use the same one-directory
    # host-home shape, so the parent is the least surprising target scope.
    if host == "omp" and root.name.casefold() == "agent" and root.parent.name.casefold() == ".omp":
        return root.parent.parent
    if (
        host == "hermes"
        and root.name.casefold() == "hermes"
        and root.parent.name.casefold() == "local"
        and root.parent.parent.name.casefold() == "appdata"
    ):
        return root.parent.parent.parent
    return root.parent


def _target_local_skill_root(roots: Mapping[str, Path], hosts: Sequence[str]) -> Path:
    """Return the target's standard shared-skill scope, never the source scope."""

    target_home = _target_home(roots, hosts)
    candidate = target_home / ".agents" / "skills"
    # Derive exclusively from selected target roots. The receiving user's
    # normal home is valid; fleet.json's source-machine destination is not
    # consulted. Existing unmanaged collisions still fail fleet preflight.
    return _assert_no_reparse_ancestors(candidate, label="target-local skill root")


def _path_replacements(roots: Mapping[str, Path], repo_root: Path | None = None) -> list[tuple[str, str]]:
    replacements: list[tuple[str, str]] = []
    placeholders = {
        "hermes": _PORTABLE_PLACEHOLDERS["HERMES_HOME"],
        "codex": _PORTABLE_PLACEHOLDERS["CODEX_HOME"],
        "omp": _PORTABLE_PLACEHOLDERS["OMP_HOME"],
    }
    for host, root in roots.items():
        placeholder = placeholders.get(host)
        if placeholder:
            replacements.append((str(Path(root).resolve(strict=False)), placeholder))
    if repo_root is not None:
        replacements.append(
            (str(repo_root.resolve(strict=False)), _PORTABLE_PLACEHOLDERS["AGENT_SIGNAL_ROOT"])
        )
    replacements.append(
        (str(_logical_home(roots).resolve(strict=False)), _PORTABLE_PLACEHOLDERS["HOME"])
    )
    replacements.sort(key=lambda item: len(item[0]), reverse=True)
    return replacements


def _replace_path_prefix(text: str, source: str, replacement: str) -> str:
    variants = {source, source.replace("\\", "/"), source.replace("/", "\\")}
    result = text
    for variant in sorted(variants, key=len, reverse=True):
        pattern = re.compile(re.escape(variant), re.IGNORECASE)
        result = pattern.sub(replacement, result)
    return result


def _normalize(value: Any, replacements: list[tuple[str, str]]) -> Any:
    if isinstance(value, dict):
        return {key: _normalize(child, replacements) for key, child in value.items()}
    if isinstance(value, list):
        return [_normalize(child, replacements) for child in value]
    if isinstance(value, str):
        result = value
        for source, replacement in replacements:
            result = _replace_path_prefix(result, source, replacement)
        return result
    return value


def _expand(
    value: Any,
    roots: Mapping[str, Path],
    repo_root: Path | None = None,
    *,
    home: Path | None = None,
) -> Any:
    home = home or _logical_home(roots)
    # References to other hosts may occur in a selected skill's documentation.
    # Rebase those strings without touching or requiring the other homes.
    hermes_default = home / "AppData/Local/hermes" if os.name == "nt" else home / ".hermes"
    replacements = {
        _PORTABLE_PLACEHOLDERS["HOME"]: str(home),
        _PORTABLE_PLACEHOLDERS["HERMES_HOME"]: str(roots.get("hermes", hermes_default)),
        _PORTABLE_PLACEHOLDERS["CODEX_HOME"]: str(roots.get("codex", home / ".codex")),
        _PORTABLE_PLACEHOLDERS["OMP_HOME"]: str(roots.get("omp", home / ".omp/agent")),
        _PORTABLE_PLACEHOLDERS["AGENT_SIGNAL_ROOT"]: str(repo_root or ""),
    }
    if isinstance(value, dict):
        return {
            key: _expand(child, roots, repo_root, home=home)
            for key, child in value.items()
        }
    if isinstance(value, list):
        return [_expand(child, roots, repo_root, home=home) for child in value]
    if isinstance(value, str):
        result = value
        for placeholder, target in replacements.items():
            result = result.replace(placeholder, target)
        if os.name == "nt" and (":" in result[:4] or result.startswith("\\")):
            return result.replace("/", "\\")
        return result
    return value


def _assert_public_safe(data: bytes, *, label: str) -> None:
    text = data.decode("utf-8", errors="replace")
    for pattern in _SECRET_VALUE_PATTERNS:
        if pattern.search(text):
            raise RecoveryError(f"public-safety violation in {label}: secret-like value")
    # Absolute user-home paths must have been normalized before persistence.
    if re.search(r"(?i)\b[A-Z]:[/\\]Users[/\\][^/\\\s]+", text):
        raise RecoveryError(f"public-safety violation in {label}: absolute user path")
    if re.search(
        r"(?i)(?<![A-Za-z0-9_])/(?:home/[A-Za-z0-9._-]+|root)(?:/[A-Za-z0-9._~+-]*)?",
        text,
    ):
        raise RecoveryError(f"public-safety violation in {label}: absolute home path")


def _assert_artifact_public_safe(data: bytes, relative: str, repo: Path) -> None:
    """Honor only exact, content-bound documentation reviews, never wildcards.

    The same reviewed findings are checked by public_check before publication.
    Validate proposed bytes directly so newly captured files can be reviewed
    before they exist on disk. This does not exempt manifest/config metadata.
    """
    review_file = repo / "evidence/public-safety-allowlist.json"
    if not review_file.is_file():
        return _assert_public_safe(data, label=relative)
    review = json.loads(review_file.read_text(encoding="utf-8"))
    if review.get("schema_version") != 1 or not isinstance(review.get("findings"), list):
        raise RecoveryError("invalid public-safety review inventory")
    lines = data.decode("utf-8").splitlines()
    reviewed: set[int] = set()
    for item in review["findings"]:
        if item.get("path") != "recovery/current/" + relative:
            continue
        line = item.get("line")
        if (not isinstance(line, int) or not 1 <= line <= len(lines)
                or _sha256(lines[line - 1].encode("utf-8")) != item.get("line_sha256")
                or not item.get("disposition")):
            raise RecoveryError(f"stale public-safety review: {relative}")
        reviewed.add(line)
    checked = "\n".join(value for number, value in enumerate(lines, 1) if number not in reviewed)
    _assert_public_safe(checked.encode("utf-8"), label=relative)


def _atomic_write_impl(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temp = Path(temp_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
    finally:
        if temp.exists():
            temp.unlink()


def _atomic_write(path: Path, data: bytes) -> None:
    """Atomic write seam kept patchable for fault-injection tests."""

    _atomic_write_impl(path, data)


def _policy_artifacts(policy: Mapping[str, Any]):
    for host in sorted(policy["hosts"]):
        for artifact in policy["hosts"][host]["artifacts"]:
            yield host, artifact


def snapshot(
    policy_path: str | Path,
    output_dir: str | Path,
    roots: Mapping[str, str | Path],
    *,
    repo_root: str | Path | None = None,
) -> dict[str, Any]:
    """Build a deterministic public-safe snapshot and return its manifest."""

    policy_path = Path(policy_path)
    output_dir = Path(output_dir)
    policy = _load_policy(policy_path)
    resolved_roots = {host: Path(root) for host, root in roots.items()}
    missing = sorted(set(policy["hosts"]) - set(resolved_roots))
    if missing:
        raise RecoveryError(f"missing host roots: {', '.join(missing)}")
    repo = Path(repo_root) if repo_root is not None else policy_path.parent
    replacements = _path_replacements(resolved_roots, repo)
    prepared: dict[str, bytes] = {}
    records: list[dict[str, Any]] = []

    for host, artifact in _policy_artifacts(policy):
        identity = f"{host}:{artifact['id']}"
        source_rel = artifact["source"]
        if _blocked_source(PurePosixPath(source_rel), artifact["kind"]):
            raise RecoveryError(f"blocked source artifact: {identity} ({source_rel})")
        if artifact.get("capture_mount"):
            mount = resolved_roots[host] / artifact["capture_mount"]
            relative = PurePosixPath(source_rel).relative_to(artifact["capture_mount"]).as_posix()
            source = _safe_join(mount.resolve(strict=True), relative, must_exist=True)
        else:
            source = _safe_join(resolved_roots[host], source_rel, must_exist=True)
        if artifact["kind"] == "config":
            config = _read_config(source, artifact["format"])
            fragment: dict[str, Any] = {}
            for dotted in artifact["include"]:
                selected = _get_dotted(config, dotted)
                _assert_no_secret_paths(selected, dotted)
                _set_dotted(fragment, dotted, selected)
            normalized = _normalize(fragment, replacements)
            data = _canonical_json(normalized)
        else:
            try:
                text = source.read_bytes().decode("utf-8")
            except UnicodeDecodeError as exc:
                raise RecoveryError(f"text artifact is not UTF-8: {identity}") from exc
            if artifact.get("portable_paths"):
                text = _normalize(text, replacements)
            data = _canonical_newlines(text).encode("utf-8")
        snapshot_rel = str(_canonical_relative(artifact["snapshot"], label=f"{identity} snapshot"))
        if artifact["kind"] == "text":
            _assert_artifact_public_safe(data, snapshot_rel, repo)
        else:
            _assert_public_safe(data, label=identity)
        prepared[snapshot_rel] = data
        records.append(
            {
                "host": host,
                "id": artifact["id"],
                "kind": artifact["kind"],
                "source": source_rel,
                "snapshot": snapshot_rel,
                "format": artifact["format"],
                "strategy": artifact["strategy"],
                "include": artifact.get("include", []),
                "portable_paths": bool(artifact.get("portable_paths", False)),
                "sha256": _sha256(data),
                "bytes": len(data),
                **({"replace_sha256": artifact["replace_sha256"]} if artifact.get("replace_sha256") else {}),
                **({"capture_mount": artifact["capture_mount"]} if artifact.get("capture_mount") else {}),
            }
        )

    policy_copy = deepcopy(policy)
    policy_copy.pop("$schema", None)
    manifest = {
        "$schema": "contracts/recovery-snapshot.schema.json",
        "schema_version": 1,
        "machine": policy["machine"],
        "public_safe": True,
        "policy_sha256": _sha256(_canonical_json(policy_copy)),
        "artifacts": records,
    }
    manifest_data = _canonical_json(manifest)
    _assert_public_safe(manifest_data, label="manifest")

    # No output bytes are written until every artifact has passed validation.
    old_paths: set[str] = set()
    old_manifest_path = output_dir / "manifest.json"
    if old_manifest_path.is_file():
        try:
            old = json.loads(old_manifest_path.read_text(encoding="utf-8"))
            old_paths = {item["snapshot"] for item in old.get("artifacts", []) if isinstance(item, dict)}
        except (OSError, json.JSONDecodeError, KeyError):
            old_paths = set()
    for relative, data in prepared.items():
        destination = _safe_join(output_dir, relative, must_exist=False)
        _atomic_write(destination, data)
    _atomic_write(_safe_join(output_dir, "manifest.json", must_exist=False), manifest_data)
    for stale in sorted(old_paths - set(prepared)):
        stale_path = _safe_join(output_dir, stale, must_exist=False)
        if stale_path.is_file() and not _is_reparse_point(stale_path):
            stale_path.unlink()
    return manifest


def verify_snapshot(policy_path: str | Path, output_dir: str | Path) -> dict[str, Any]:
    policy = _load_policy(Path(policy_path))
    output_dir = Path(output_dir)
    manifest_path = _safe_join(output_dir, "manifest.json", must_exist=True)
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RecoveryError(f"invalid snapshot manifest: {exc}") from exc
    if manifest.get("schema_version") != 1 or manifest.get("public_safe") is not True:
        raise RecoveryError("snapshot manifest has unsupported schema or safety class")
    schema_path = Path(policy_path).parent / "contracts" / "recovery-snapshot.schema.json"
    if schema_path.is_file():
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        errors = sorted(
            jsonschema.Draft202012Validator(schema).iter_errors(manifest),
            key=lambda item: list(item.absolute_path),
        )
        if errors:
            error = errors[0]
            location = ".".join(str(part) for part in error.absolute_path) or "<root>"
            raise RecoveryError(f"recovery snapshot schema: {location}: {error.message}")
    policy_copy = deepcopy(policy)
    policy_copy.pop("$schema", None)
    expected_policy_hash = _sha256(_canonical_json(policy_copy))
    if manifest.get("policy_sha256") != expected_policy_hash:
        raise RecoveryError("snapshot policy hash mismatch")
    expected = {
        (host, artifact["id"]): artifact
        for host, artifact in _policy_artifacts(policy)
    }
    records = manifest.get("artifacts")
    if not isinstance(records, list) or len(records) != len(expected):
        raise RecoveryError("snapshot artifact inventory mismatch")
    seen: set[tuple[str, str]] = set()
    for record in records:
        if not isinstance(record, dict):
            raise RecoveryError("snapshot artifact record must be an object")
        identity = (record.get("host"), record.get("id"))
        if identity not in expected or identity in seen:
            raise RecoveryError(f"snapshot artifact identity mismatch: {identity}")
        seen.add(identity)
        artifact = expected[identity]
        for field in ("kind", "source", "snapshot", "format", "strategy"):
            if record.get(field) != artifact.get(field):
                raise RecoveryError(f"snapshot metadata mismatch for {identity}: {field}")
        if record.get("include", []) != artifact.get("include", []):
            raise RecoveryError(f"snapshot include mismatch for {identity}")
        if record.get("portable_paths", False) != bool(artifact.get("portable_paths", False)):
            raise RecoveryError(f"snapshot portable-path metadata mismatch for {identity}")
        if record.get("replace_sha256", []) != artifact.get("replace_sha256", []):
            raise RecoveryError(f"snapshot replacement-hash metadata mismatch for {identity}")
        if record.get("capture_mount") != artifact.get("capture_mount"):
            raise RecoveryError(f"snapshot capture-mount metadata mismatch for {identity}")
        path = _safe_join(output_dir, record["snapshot"], must_exist=True)
        data = path.read_bytes()
        if _sha256(data) != record.get("sha256"):
            raise RecoveryError(f"snapshot hash mismatch: {record['snapshot']}")
        if len(data) != record.get("bytes"):
            raise RecoveryError(f"snapshot byte count mismatch: {record['snapshot']}")
        if record["kind"] == "text":
            _assert_artifact_public_safe(data, record["snapshot"], Path(policy_path).parent)
        else:
            _assert_public_safe(data, label=record["snapshot"])
    _assert_public_safe(manifest_path.read_bytes(), label="manifest")
    return manifest


def _deep_merge(base: dict[str, Any], overlay: Mapping[str, Any]) -> dict[str, Any]:
    result = deepcopy(base)
    for key, value in overlay.items():
        if isinstance(value, Mapping) and isinstance(result.get(key), Mapping):
            result[key] = _deep_merge(dict(result[key]), value)
        else:
            result[key] = deepcopy(value)
    return result


def _normalize_windows_path_spans(text: str) -> str:
    pattern = re.compile(
        r"(?i)[A-Z]:(?:[\\/]+[A-Za-z0-9_ .@(){}\[\]$~+-]+)+"
    )
    return pattern.sub(lambda match: re.sub(r"[\\/]+", "/", match.group(0)), text)


def _semantic_equal(left: Any, right: Any) -> bool:
    """Compare values while ignoring separators only inside Windows path spans."""

    if isinstance(left, Mapping) and isinstance(right, Mapping):
        return set(left) == set(right) and all(
            _semantic_equal(left[key], right[key]) for key in left
        )
    if isinstance(left, list) and isinstance(right, list):
        return len(left) == len(right) and all(
            _semantic_equal(a, b) for a, b in zip(left, right)
        )
    if isinstance(left, str) and isinstance(right, str):
        left = _canonical_newlines(left)
        right = _canonical_newlines(right)
        if left == right:
            return True
        return _normalize_windows_path_spans(left) == _normalize_windows_path_spans(right)
    return left == right


def restore(
    policy_path: str | Path,
    snapshot_dir: str | Path,
    roots: Mapping[str, str | Path],
    *,
    apply: bool = False,
    force_text: bool = False,
    repo_root: str | Path | None = None,
    hosts: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Plan or apply a restore. Dry-run is the default."""

    policy_path = Path(policy_path)
    snapshot_dir = Path(snapshot_dir)
    policy = _load_policy(policy_path)
    selected_hosts = _normalize_hosts(policy["hosts"] if hosts is None else hosts)
    # Verify every policy artifact and every manifest record before narrowing
    # the effect scope.  A selected restore must not hide a damaged artifact
    # belonging to another host.
    manifest = verify_snapshot(policy_path, snapshot_dir)
    _, resolved_roots = _selected_roots(roots, selected_hosts)
    repo = Path(repo_root) if repo_root is not None else policy_path.parent
    records = {(item["host"], item["id"]): item for item in manifest["artifacts"]}
    writes: dict[Path, bytes] = {}
    changes: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []
    selected_set = set(selected_hosts)
    target_home = _target_home(resolved_roots, selected_hosts)

    # Complete preflight before the first mutation.
    for host, artifact in _policy_artifacts(policy):
        if host not in selected_set:
            continue
        record = records[(host, artifact["id"])]
        source_data = _safe_join(snapshot_dir, record["snapshot"], must_exist=True).read_bytes()
        read_only_mount = False
        mount = resolved_roots[host] / artifact.get("capture_mount", "")
        if artifact.get("capture_mount") and _is_reparse_point(mount):
            # Capture may follow this explicitly declared native owner. Restore
            # may read it for parity, but never overwrite through the link.
            relative = PurePosixPath(artifact["source"]).relative_to(artifact["capture_mount"]).as_posix()
            target = _safe_join(mount.resolve(strict=True), relative, must_exist=False)
            read_only_mount = True
        else:
            target = _safe_join(resolved_roots[host], artifact["source"], must_exist=False)
        if artifact["kind"] == "config":
            fragment = json.loads(source_data.decode("utf-8"))
            fragment = _expand(fragment, resolved_roots, repo, home=target_home)
            current = _read_config(target, artifact["format"]) if target.exists() else {}
            current_fragment: dict[str, Any] = {}
            selected_matches = target.is_file()
            for dotted in artifact["include"]:
                try:
                    selected = _get_dotted(current, dotted)
                except RecoveryError:
                    selected_matches = False
                    break
                _set_dotted(current_fragment, dotted, selected)
            if selected_matches and _semantic_equal(current_fragment, fragment):
                desired = target.read_bytes()
            else:
                merged = _deep_merge(current, fragment)
                desired = _serialize_config(merged, artifact["format"])
        else:
            if artifact.get("portable_paths"):
                desired = _expand(
                    source_data.decode("utf-8"), resolved_roots, repo, home=target_home
                ).encode("utf-8")
            else:
                desired = source_data
            existing = target.read_bytes() if target.is_file() else None
            text_matches = existing == desired
            if existing is not None and not text_matches:
                try:
                    text_matches = _semantic_equal(existing.decode("utf-8"), desired.decode("utf-8"))
                except UnicodeDecodeError:
                    text_matches = False
            if text_matches and existing is not None:
                desired = existing
            elif (existing is not None and not force_text
                  and _sha256(existing.replace(b"\r\n", b"\n").replace(b"\r", b"\n"))
                  not in artifact.get("replace_sha256", [])):
                conflicts.append(
                    {
                        "host": host,
                        "id": artifact["id"],
                        "target": artifact["source"],
                        "reason": "text conflict; existing file differs",
                    }
                )
                continue
        current_data = target.read_bytes() if target.is_file() else None
        if current_data != desired:
            if read_only_mount:
                conflicts.append({"host": host, "id": artifact["id"], "target": artifact["source"],
                                  "reason": "linked native source is read-only; edit its owner instead"})
                continue
            writes[target] = desired
            changes.append(
                {
                    "host": host,
                    "id": artifact["id"],
                    "target": artifact["source"],
                    "action": "update" if current_data is not None else "create",
                }
            )

    plan = {
        "apply": apply,
        "hosts": list(selected_hosts),
        "changes": changes,
        "conflicts": conflicts,
    }
    if apply and conflicts:
        names = ", ".join(f"{item['host']}:{item['id']}" for item in conflicts)
        raise RecoveryError(f"text conflict prevents restore: {names}")
    if apply:
        originals = {
            target: target.read_bytes() if target.is_file() else None
            for target in writes
        }
        applied: list[Path] = []
        try:
            for target, data in writes.items():
                _atomic_write(target, data)
                applied.append(target)
        except Exception:
            for target in reversed(applied):
                original = originals[target]
                if original is None:
                    if target.is_file() and not _is_reparse_point(target):
                        target.unlink()
                else:
                    _atomic_write_impl(target, original)
            raise
    return plan


def _default_roots() -> dict[str, Path]:
    home = Path.home()
    if os.name == "nt":
        hermes_default = Path(
            os.environ.get("LOCALAPPDATA", home / "AppData" / "Local")
        ) / "hermes"
    else:
        hermes_default = home / ".hermes"
    return {
        "hermes": Path(os.environ.get("HERMES_HOME", hermes_default)),
        "codex": Path(os.environ.get("CODEX_HOME", home / ".codex")),
        "omp": Path(os.environ.get("OMP_HOME", home / ".omp" / "agent")),
    }


def _parse_roots(values: list[str]) -> dict[str, Path]:
    roots = _default_roots()
    for value in values:
        if "=" not in value:
            raise RecoveryError(f"--root must be HOST=PATH: {value}")
        host, raw_path = value.split("=", 1)
        if host not in _HOST_SET or not raw_path:
            raise RecoveryError(f"--root must be HOST=PATH: {value}")
        roots[host] = Path(raw_path)
    return roots


def _skill_name(path: Path) -> str | None:
    try:
        text = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError):
        return None
    if not text.startswith("---"):
        return None
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None
    try:
        frontmatter = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError:
        return None
    name = frontmatter.get("name") if isinstance(frontmatter, Mapping) else None
    return name if isinstance(name, str) and name else None


def _local_skill_files(root: Path) -> list[Path]:
    if not root.is_dir() or _is_reparse_point(root):
        return []
    found: list[Path] = []
    for current, directories, files in os.walk(root, followlinks=False):
        current_path = Path(current)
        directories[:] = [
            name
            for name in directories
            if not name.startswith(".") and not _is_reparse_point(current_path / name)
        ]
        if "SKILL.md" in files:
            found.append(current_path / "SKILL.md")
    return sorted(found)


def find_admitted_local_skill_collisions(
    repo: Path,
    roots: Mapping[str, str | Path],
    *,
    hosts: Iterable[str] | None = None,
) -> dict[str, list[str]]:
    selected_hosts, selected_roots = _selected_roots(roots, hosts)
    try:
        registry = json.loads((repo / "registry.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RecoveryError(f"cannot read registry.json: {exc}") from exc
    admitted = {
        item.get("name")
        for item in registry.get("skills", [])
        if isinstance(item, Mapping) and item.get("status") == "admitted"
    }
    allowed_adapters: set[tuple[str, str]] = set()
    try:
        recovery_policy = json.loads((repo / "recovery.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        recovery_policy = {}
    for host, host_config in (recovery_policy.get("hosts") or {}).items():
        if not isinstance(host_config, Mapping):
            continue
        for artifact in host_config.get("artifacts", []):
            if not isinstance(artifact, Mapping) or artifact.get("kind") != "text":
                continue
            source = PurePosixPath(str(artifact.get("source", "")))
            if len(source.parts) >= 3 and source.parts[0] == "skills" and source.name == "SKILL.md":
                allowed_adapters.add((str(host), PurePosixPath(*source.parts[1:-1]).as_posix()))
    collisions: dict[str, list[str]] = {}
    for host in selected_hosts:
        root = selected_roots[host] / "skills"
        for skill_file in _local_skill_files(root):
            name = _skill_name(skill_file)
            if name not in admitted:
                continue
            relative = skill_file.parent.relative_to(root).as_posix()
            if (host, relative) in allowed_adapters:
                continue
            collisions.setdefault(name, []).append(f"{host}:{relative}")
    return {name: sorted(paths) for name, paths in sorted(collisions.items())}


def find_retired_local_skills(
    repo: Path,
    roots: Mapping[str, str | Path],
    *,
    hosts: Iterable[str] | None = None,
) -> dict[str, list[str]]:
    selected_hosts, selected_roots = _selected_roots(roots, hosts)
    try:
        ownership = json.loads(
            (repo / "contracts" / "ownership.json").read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as exc:
        raise RecoveryError(f"cannot read contracts/ownership.json: {exc}") from exc
    retired_names = {
        PurePosixPath(str(item.get("path", ""))).name
        for item in ownership.get("retired_artifacts", [])
        if isinstance(item, Mapping)
        and str(item.get("path", "")).startswith("integrations/")
    }
    found: dict[str, list[str]] = {}
    for host in selected_hosts:
        root = selected_roots[host] / "skills"
        for skill_file in _local_skill_files(root):
            name = _skill_name(skill_file)
            if name not in retired_names:
                continue
            relative = skill_file.parent.relative_to(root).as_posix()
            found.setdefault(name, []).append(f"{host}:{relative}")
    return {name: sorted(paths) for name, paths in sorted(found.items())}


def _selected_fleet_module(repo: Path):
    tools_dir = str(repo / "tools")
    if tools_dir not in sys.path:
        sys.path.insert(0, tools_dir)
    try:
        import fleet
    except (ImportError, OSError) as exc:
        raise RecoveryError(f"cannot load fleet tool for selected bootstrap: {exc}") from exc
    return fleet


def _fleet_plan_report(
    planned: Sequence[tuple[Path, list[dict[str, str]]]]
) -> list[dict[str, Any]]:
    return [
        {"destination": str(destination), "actions": actions}
        for destination, actions in planned
    ]


def _selected_bootstrap(
    repo: Path,
    policy_path: Path,
    snapshot_dir: Path,
    roots: Mapping[str, str | Path],
    *,
    hosts: Iterable[str],
    machine: str,
    apply: bool,
    force_text: bool,
) -> dict[str, Any]:
    """Run bootstrap against only selected host roots and a target-local fleet."""

    selected_hosts, selected_roots = _selected_roots(roots, hosts)
    # Validate the complete snapshot before inspecting any target-local host
    # state.  Scope narrowing belongs to the effect/readback phase, not to
    # snapshot integrity verification.
    preflight = restore(
        policy_path,
        snapshot_dir,
        roots,
        apply=False,
        force_text=force_text,
        repo_root=repo,
        hosts=selected_hosts,
    )
    if preflight["conflicts"]:
        names = ", ".join(f"{item['host']}:{item['id']}" for item in preflight["conflicts"])
        raise RecoveryError(f"restore preflight has conflicts: {names}")

    skill_root = _target_local_skill_root(selected_roots, selected_hosts)
    retired = find_retired_local_skills(repo, selected_roots, hosts=selected_hosts)
    if retired:
        details = ", ".join(
            f"{name} ({'; '.join(paths)})" for name, paths in retired.items()
        )
        raise RecoveryError(f"retired skills remain in host-local discovery roots: {details}")
    collisions = find_admitted_local_skill_collisions(
        repo, selected_roots, hosts=selected_hosts
    )
    if collisions:
        details = ", ".join(
            f"{name} ({'; '.join(paths)})" for name, paths in collisions.items()
        )
        raise RecoveryError(
            "admitted skills already exist in host-local discovery roots; "
            f"retire or migrate the duplicate copies before fleet apply: {details}"
        )

    fleet = _selected_fleet_module(repo)
    try:
        fleet_config = fleet.load_fleet(repo)
        machine_config = fleet_config["machines"].get(machine)
        if not isinstance(machine_config, Mapping):
            raise RecoveryError(f"unknown fleet machine: {machine}")
        declared_hosts = set(machine_config.get("hosts", []))
        undeclared = sorted(set(selected_hosts) - declared_hosts)
        if undeclared:
            raise RecoveryError(
                f"selected host(s) are not declared for fleet machine {machine}: "
                f"{', '.join(undeclared)}"
            )
    except RecoveryError:
        raise
    except (KeyError, OSError, ValueError, RuntimeError) as exc:
        raise RecoveryError(f"cannot validate selected fleet machine: {exc}") from exc

    tools_dir = str(repo / "tools")
    if tools_dir not in sys.path:
        sys.path.insert(0, tools_dir)
    try:
        import host_deltas
    except (ImportError, OSError) as exc:
        raise RecoveryError(f"cannot load host-delta tool for selected bootstrap: {exc}") from exc

    # Fleet insists that rendered output stays in the repository.  Keep that
    # output in a disposable in-repository directory; the destination remains
    # the target-local scope derived above, never fleet's live shared root.
    with tempfile.TemporaryDirectory(prefix="recovery-selected-fleet-", dir=repo) as temp:
        fleet_snapshot = Path(temp) / "snapshot"
        try:
            rendered = fleet.render_snapshot(repo, fleet_snapshot)
            planned = fleet.preflight_destinations(fleet_snapshot, [skill_root])
        except (OSError, KeyError, ValueError, RuntimeError) as exc:
            raise RecoveryError(f"selected fleet preflight failed: {exc}") from exc
        fleet_conflicts = [
            f"{destination}:{item['name']}"
            for destination, actions in planned
            for item in actions
            if item["action"] == "conflict"
        ]
        if fleet_conflicts:
            raise RecoveryError(
                "selected fleet preflight has conflicts: " + ", ".join(fleet_conflicts)
            )

        result: dict[str, Any] = {
            "apply": apply,
            "hosts": list(selected_hosts),
            "fleet_skill_root": str(skill_root),
            "recovery_preflight": preflight,
            "fleet_render": rendered,
            "fleet_diff": _fleet_plan_report(planned),
        }
        delta_manifest = host_deltas.load_manifest(repo / "host-deltas.json", repo)
        changed_references = {
            f"{item['host']}:{item['id']}" for item in preflight["changes"]
        }
        restored_ids = {
            str(item["id"])
            for item in delta_manifest["entries"]
            if str(item["host"]) in selected_hosts
            and item["restore"]["kind"] == "recovery-artifact"
            and str(item["restore"]["reference"]) in changed_references
        }

        result["state_report"] = host_deltas.verify(
            repo / "host-deltas.json", repo, roots=selected_roots,
            skill_roots=[skill_root], fleet_snapshot=fleet_snapshot, hosts=selected_hosts,
        )
        required_native = {
            item["id"] for item in delta_manifest["entries"]
            if item["host"] in selected_hosts and item["required"]
            and item["restore"]["kind"] in {"prerequisite", "manual-prerequisite"}
        }
        missing_native = [
            item["id"] for item in result["state_report"]["entries"]
            if item["id"] in required_native and item["status"] != "verified"
        ]
        if apply and missing_native:
            raise RecoveryError("selected host prerequisite(s) missing before restore: " + ", ".join(missing_native))
        if not apply:
            result["profile"] = {
                "status": "skipped-selected-hosts",
                "hosts": list(selected_hosts),
                "reason": "global instruction profile verification is outside the selected scope",
            }
            return result

        try:
            fleet_applied = fleet.apply_snapshot(fleet_snapshot, skill_root)
        except (OSError, KeyError, ValueError, RuntimeError) as exc:
            raise RecoveryError(f"selected fleet apply failed: {exc}") from exc
        result["fleet_apply"] = [
            {"destination": str(skill_root), "actions": fleet_applied}
        ]
        result["recovery_apply"] = restore(
            policy_path,
            snapshot_dir,
            selected_roots,
            apply=True,
            force_text=force_text,
            repo_root=repo,
            hosts=selected_hosts,
        )
        try:
            fleet_findings = fleet.verify_snapshot(fleet_snapshot, skill_root)
        except (OSError, KeyError, ValueError, RuntimeError) as exc:
            raise RecoveryError(f"selected fleet postflight failed: {exc}") from exc
        result["fleet_verify"] = fleet_findings
        if fleet_findings:
            raise RecoveryError("selected fleet postflight is not clean")

        postflight = restore(
            policy_path,
            snapshot_dir,
            selected_roots,
            apply=False,
            force_text=False,
            repo_root=repo,
            hosts=selected_hosts,
        )
        if postflight["changes"] or postflight["conflicts"]:
            raise RecoveryError("recovery postflight is not clean")
        result["profile"] = {
            "status": "skipped-selected-hosts",
            "hosts": list(selected_hosts),
            "reason": "global instruction profile verification is outside the selected scope",
        }
        result["postflight"] = postflight
        result["state_report"] = host_deltas.verify(
            repo / "host-deltas.json",
            repo,
            roots=selected_roots,
            skill_roots=[skill_root],
            fleet_snapshot=fleet_snapshot,
            restored_ids=restored_ids,
            hosts=selected_hosts,
        )
        if not result["state_report"]["passed"]:
            raise RecoveryError("host-delta postflight is not clean")
        return result


def bootstrap(
    repo: str | Path,
    policy_path: str | Path,
    snapshot_dir: str | Path,
    roots: Mapping[str, str | Path],
    *,
    machine: str = "local-windows",
    apply: bool = False,
    force_text: bool = False,
    hosts: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Preflight and optionally restore declarative state plus admitted skills."""

    repo = Path(repo).resolve()
    policy_path = Path(policy_path)
    snapshot_dir = Path(snapshot_dir)
    if hosts is not None:
        return _selected_bootstrap(
            repo,
            policy_path,
            snapshot_dir,
            roots,
            hosts=hosts,
            machine=machine,
            apply=apply,
            force_text=force_text,
        )
    retired = find_retired_local_skills(repo, roots)
    if retired:
        details = ", ".join(
            f"{name} ({'; '.join(paths)})" for name, paths in retired.items()
        )
        raise RecoveryError(f"retired skills remain in host-local discovery roots: {details}")
    collisions = find_admitted_local_skill_collisions(repo, roots)
    if collisions:
        details = ", ".join(
            f"{name} ({'; '.join(paths)})" for name, paths in collisions.items()
        )
        raise RecoveryError(
            "admitted skills already exist in host-local discovery roots; "
            f"retire or migrate the duplicate copies before fleet apply: {details}"
        )
    preflight = restore(
        policy_path,
        snapshot_dir,
        roots,
        apply=False,
        force_text=force_text,
        repo_root=repo,
    )
    if preflight["conflicts"]:
        names = ", ".join(f"{item['host']}:{item['id']}" for item in preflight["conflicts"])
        raise RecoveryError(f"restore preflight has conflicts: {names}")

    def run_fleet(action: str) -> str:
        command = [
            sys.executable,
            str(repo / "tools" / "fleet.py"),
            action,
            "--repo",
            str(repo),
            "--machine",
            machine,
        ]
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
        output = "\n".join(part.strip() for part in (completed.stdout, completed.stderr) if part.strip())
        if completed.returncode != 0:
            raise RecoveryError(f"fleet {action} failed ({completed.returncode}): {output}")
        return output

    fleet_render = run_fleet("render")
    fleet_diff = run_fleet("diff")
    result: dict[str, Any] = {
        "apply": apply,
        "recovery_preflight": preflight,
        "fleet_render": fleet_render,
        "fleet_diff": fleet_diff,
    }
    tools_dir = str(repo / "tools")
    if tools_dir not in sys.path:
        sys.path.insert(0, tools_dir)
    import host_deltas

    if not apply:
        result["state_report"] = host_deltas.verify(
            repo / "host-deltas.json", repo, roots=roots
        )
        return result

    result["fleet_apply"] = run_fleet("apply")
    result["recovery_apply"] = restore(
        policy_path,
        snapshot_dir,
        roots,
        apply=True,
        force_text=force_text,
        repo_root=repo,
    )
    result["fleet_verify"] = run_fleet("verify")
    postflight = restore(
        policy_path,
        snapshot_dir,
        roots,
        apply=False,
        force_text=False,
        repo_root=repo,
    )
    if postflight["changes"] or postflight["conflicts"]:
        raise RecoveryError("recovery postflight is not clean")
    import instruction_profile as profile_tool

    result["profile"] = profile_tool.verify_profile(
        repo, profile_tool.current_profile(repo)
    )
    result["postflight"] = postflight
    changed_references = {
        f"{item['host']}:{item['id']}" for item in preflight["changes"]
    }
    delta_manifest = host_deltas.load_manifest(repo / "host-deltas.json", repo)
    restored_ids = {
        str(item["id"])
        for item in delta_manifest["entries"]
        if item["restore"]["kind"] == "recovery-artifact"
        and str(item["restore"]["reference"]) in changed_references
    }
    result["state_report"] = host_deltas.verify(
        repo / "host-deltas.json",
        repo,
        roots=roots,
        restored_ids=restored_ids,
    )
    if not result["state_report"]["passed"]:
        raise RecoveryError("host-delta postflight is not clean")
    return result


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("snapshot", "verify", "diff", "restore", "bootstrap"))
    parser.add_argument("--policy", default="recovery.json")
    parser.add_argument("--snapshot", default="recovery/current")
    parser.add_argument("--root", action="append", default=[], metavar="HOST=PATH")
    parser.add_argument(
        "--host",
        action="append",
        choices=HOSTS,
        default=None,
        metavar="HOST",
        help="scope restore, diff, or bootstrap to one or more hosts",
    )
    parser.add_argument("--apply", action="store_true", help="apply restore; default is dry-run")
    parser.add_argument("--force-text", action="store_true", help="replace conflicting instruction files")
    parser.add_argument("--machine", default="local-windows", help="fleet machine id")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    policy = Path(args.policy)
    snapshot_dir = Path(args.snapshot)
    try:
        if args.host and args.command not in {"diff", "restore", "bootstrap"}:
            raise RecoveryError("--host is supported only for diff, restore, and bootstrap")
        roots = _parse_roots(args.root)
        if args.command == "snapshot":
            result = snapshot(policy, snapshot_dir, roots, repo_root=policy.resolve().parent)
        elif args.command == "verify":
            result = verify_snapshot(policy, snapshot_dir)
        elif args.command == "bootstrap":
            result = bootstrap(
                policy.resolve().parent,
                policy,
                snapshot_dir,
                roots,
                machine=args.machine,
                apply=args.apply,
                force_text=args.force_text,
                hosts=args.host,
            )
        else:
            result = restore(
                policy,
                snapshot_dir,
                roots,
                apply=args.command == "restore" and args.apply,
                force_text=args.force_text,
                repo_root=policy.resolve().parent,
                hosts=args.host,
            )
            if args.command == "diff":
                result["apply"] = False
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except RecoveryError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
