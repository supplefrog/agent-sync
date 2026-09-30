"""Approved default selectors from core.md and narrow native config adapters.

Preparation is read-only. The reconciler owns authorization, surrounding checks,
recovery capture and publication; no session or provider is migrated here.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import tempfile
from typing import Any, Iterable, Mapping

import recovery
import sync_git


class DefaultsError(RuntimeError):
    pass


HOSTS = ("codex", "hermes", "omp")
ADAPTERS = {
    "codex": ("config.toml", "toml", {"model": "model", "reasoning": "model_reasoning_effort"}),
    "hermes": ("config.yaml", "yaml", {"model": "model.default", "reasoning": "agent.reasoning_effort"}),
}


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise DefaultsError(f"duplicate preference field: {key}")
        result[key] = value
    return result


def load_preferences(repo: str | Path) -> dict[str, Any]:
    """Read the only desired-value owner; reject ambiguous or unsupported shapes."""
    path = Path(repo) / "surfaces/core.md"
    return _parse_preferences(path.read_text(encoding="utf-8"))


def _parse_preferences(text: str) -> dict[str, Any]:
    start, end = "<!-- agent-sync-preferences -->", "<!-- /agent-sync-preferences -->"
    if text.count(start) != 1 or text.count(end) != 1:
        raise DefaultsError("core.md must contain exactly one preference block")
    body = text.split(start, 1)[1].split(end, 1)[0]
    match = re.fullmatch(r"\s*```json\s*\n(.*?)\n```\s*", body, flags=re.DOTALL)
    if match is None:
        raise DefaultsError("core.md preference block must be one JSON fence")
    try:
        value = json.loads(match[1], object_pairs_hook=_unique_object)
    except (ValueError, TypeError) as exc:
        raise DefaultsError("core.md preference block is invalid JSON") from exc
    required = {"schema_version", "roles", "runtime_defaults", "maintained_hosts", "optional_hosts"}
    if (not isinstance(value, dict) or set(value) != required
            or type(value["schema_version"]) is not int or value["schema_version"] != 1):
        raise DefaultsError("unsupported preference contract")
    roles = value["roles"]
    if not isinstance(roles, dict) or set(roles) != {"reviewer", "worker", "linear", "hermes"}:
        raise DefaultsError("unsupported preference roles")
    for name, role in roles.items():
        if (not isinstance(role, dict) or set(role) != {"model", "reasoning"}
                or not isinstance(role["model"], str) or not re.fullmatch(r"[a-z0-9][a-z0-9._-]+", role["model"])
                or not isinstance(role["reasoning"], str)
                or role["reasoning"] not in {"none", "minimal", "low", "medium", "high", "xhigh", "max", "ultra"}):
            raise DefaultsError(f"unsupported role selector: {name}")
    defaults = value["runtime_defaults"]
    if (not isinstance(defaults, dict) or set(defaults) != {"codex", "hermes"}
            or any(not isinstance(role, str) or role not in roles for role in defaults.values())):
        raise DefaultsError("unsupported native default mapping")
    groups = []
    for field in ("maintained_hosts", "optional_hosts"):
        hosts = value[field]
        if (not isinstance(hosts, list) or not hosts or any(host not in HOSTS for host in hosts)
                or len(hosts) != len(set(hosts))):
            raise DefaultsError(f"invalid {field}")
        groups.append(set(hosts))
    if groups[0] & groups[1] or groups[0] | groups[1] != set(HOSTS):
        raise DefaultsError("maintained and optional hosts must partition supported hosts")
    return value


def selected_hosts(repo: str | Path, hosts: Iterable[str] | None = None) -> tuple[str, ...]:
    chosen = list(load_preferences(repo)["maintained_hosts"] if hosts is None else hosts)
    if not chosen or any(host not in HOSTS for host in chosen):
        raise DefaultsError("host selection must name supported hosts")
    return tuple(sorted(set(chosen)))


class PreparedDefaults:
    """Private transaction state. Raw config bytes must never enter a receipt."""
    def __init__(self, repo: Path, report: dict[str, Any], entries: list[dict[str, Any]]):
        self.repo = repo
        self.report = report
        self.entries = entries
        self.attempted: list[dict[str, Any]] = []
        self.applied = False
        self.private_backup: Path | None = None


def prepare_defaults(repo: str | Path, *, roots: Mapping[str, str | Path] | None = None,
                     hosts: Iterable[str] | None = None) -> PreparedDefaults:
    """Project only approved selectors; preserve all other parsed settings."""
    repo = Path(repo).resolve()
    core_bytes = (repo / "surfaces/core.md").read_bytes()
    preferences = _parse_preferences(core_bytes.decode("utf-8"))
    core_hash = _digest(core_bytes)
    selected = selected_hosts(repo, hosts if hosts is not None else preferences["maintained_hosts"])
    resolved_roots = recovery._default_roots() if roots is None else roots
    entries, changes, observations, deferred = [], [], {}, []
    for host in selected:
        if host not in preferences["runtime_defaults"]:
            deferred.append({"host": host, "reason": "no approved runtime-default mapping; existing setup retained"})
            continue
        if host not in resolved_roots:
            raise DefaultsError(f"selected config root is missing: {host}")
        source, fmt, keys = ADAPTERS[host]
        try:
            target = recovery._safe_join(Path(resolved_roots[host]), source, must_exist=True)
            identity = recovery._file_identity(target)
            original = target.read_bytes()
            current = recovery._read_config(target, fmt)
            provider = (current.get("model_provider", "openai") if host == "codex"
                        else recovery._get_dotted(current, "model.provider"))
            if provider != ("openai" if host == "codex" else "openai-codex"):
                raise DefaultsError(f"unsupported selected provider mapping: {host}")
            desired = preferences["roles"][preferences["runtime_defaults"][host]]
            merged = deepcopy(current)
            observed = {}
            for field, dotted in keys.items():
                before = recovery._get_dotted(current, dotted)
                if not isinstance(before, str) or not re.fullmatch(r"[a-z0-9][a-z0-9._-]+", before):
                    raise DefaultsError(f"selected native selector is unsupported: {host}:{dotted}")
                observed[field] = before
                if before != desired[field]:
                    changes.append({"host": host, "key": dotted, "before": before, "after": desired[field]})
                    recovery._set_dotted(merged, dotted, desired[field])
            data = original if merged == current else recovery._serialize_config(merged, fmt)
            if recovery._file_identity(target) != identity:
                raise DefaultsError(f"selected config changed during preparation: {host}")
        except recovery.RecoveryError as exc:
            raise DefaultsError(f"selected config cannot be prepared: {host}: {exc}") from exc
        observations[host] = {**observed, "provider": "openai-codex", "source_sha256": _digest(original)}
        entries.append({"host": host, "path": target, "format": fmt, "identity": identity,
                        "original": original, "desired": data, "desired_fields": dict(desired),
                        "parsed_desired": merged})
    report = {"schema_version": 1, "mode": "read-only-default-plan", "hosts": list(selected),
              "core_sha256": core_hash, "changes": changes, "observations": observations,
              "deferred": deferred, "mutation_performed": False,
              "limits": "Configured selectors only; native availability and active-session identity require separate evidence."}
    if _digest((repo / "surfaces/core.md").read_bytes()) != core_hash:
        raise DefaultsError("preference owner changed during preparation")
    return PreparedDefaults(repo, report, entries)


def plan_defaults(repo: str | Path, *, roots=None, hosts=None) -> dict[str, Any]:
    return prepare_defaults(repo, roots=roots, hosts=hosts).report


def _rollback_locked(prepared: PreparedDefaults) -> dict[str, Any]:
    conflicts, restored = [], []
    for entry in reversed(prepared.attempted):
        target = entry["path"]
        try:
            current_identity = recovery._file_identity(target)
            current = target.read_bytes()
            if current == entry["original"]:
                continue
            if (current != entry["desired"]
                    or (entry.get("written_identity") is not None
                        and current_identity != entry["written_identity"])):
                raise DefaultsError("concurrent config change")
            recovery._atomic_write_impl(target, entry["original"])
            restored.append(entry["host"])
        except (OSError, recovery.RecoveryError, DefaultsError):
            conflicts.append(entry)
    report: dict[str, Any] = {"restored_hosts": restored, "conflict_hosts": [entry["host"] for entry in conflicts]}
    if conflicts:
        backup = Path(tempfile.mkdtemp(prefix="agent-sync-defaults-conflict-"))
        for entry in conflicts:
            (backup / (entry["host"] + ".original")).write_bytes(entry["original"])
        report["private_backup"] = str(backup)
    prepared.attempted.clear()
    prepared.applied = False
    return report


def rollback_defaults(prepared: PreparedDefaults) -> dict[str, Any]:
    """Outer reconciliation may roll back own selector writes after later failure."""
    with sync_git.path_locks([entry["path"] for entry in prepared.entries]):
        return _rollback_locked(prepared)


def apply_defaults(prepared: PreparedDefaults) -> dict[str, Any]:
    """Apply a previously checked plan with CAS, parsed readback and own rollback."""
    if prepared.applied:
        raise DefaultsError("prepared defaults already applied; prepare a new readback")
    with sync_git.path_locks([entry["path"] for entry in prepared.entries]):
        if _digest((prepared.repo / "surfaces/core.md").read_bytes()) != prepared.report["core_sha256"]:
            raise DefaultsError("preference owner changed before selector apply")
        for entry in prepared.entries:
            if recovery._file_identity(entry["path"]) != entry["identity"]:
                raise DefaultsError(f"selected config changed before apply: {entry['host']}")
        changed = [entry for entry in prepared.entries if entry["desired"] != entry["original"]]
        if changed:
            prepared.private_backup = Path(tempfile.mkdtemp(prefix="agent-sync-defaults-baseline-"))
            for entry in changed:
                (prepared.private_backup / (entry["host"] + ".original")).write_bytes(entry["original"])
        try:
            for entry in prepared.entries:
                if _digest((prepared.repo / "surfaces/core.md").read_bytes()) != prepared.report["core_sha256"]:
                    raise DefaultsError("preference owner changed during selector apply")
                if entry["desired"] != entry["original"]:
                    if recovery._file_identity(entry["path"]) != entry["identity"]:
                        raise DefaultsError(f"selected config changed before write: {entry['host']}")
                    prepared.attempted.append(entry)
                    recovery._atomic_write(entry["path"], entry["desired"])
                    entry["written_identity"] = recovery._file_identity(entry["path"])
                if recovery._read_config(entry["path"], entry["format"]) != entry["parsed_desired"]:
                    raise DefaultsError(f"selected config parsed readback mismatch: {entry['host']}")
            # An unchanged selected host is also guarded through the readback boundary.
            for entry in prepared.entries:
                expected = entry.get("written_identity", entry["identity"])
                if recovery._file_identity(entry["path"]) != expected:
                    raise DefaultsError(f"selected config changed during readback: {entry['host']}")
            if _digest((prepared.repo / "surfaces/core.md").read_bytes()) != prepared.report["core_sha256"]:
                raise DefaultsError("preference owner changed during selector readback")
        except Exception as exc:
            rollback = _rollback_locked(prepared)
            raise DefaultsError(f"default selector apply failed; rollback={json.dumps(rollback)}; {exc}") from exc
        prepared.applied = True
        observed_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        observed = {entry["host"]: {**entry["desired_fields"], "provider": "openai-codex",
                    "source_sha256": _digest(entry["desired"]), "observed_at": observed_at,
                    "kind": "configured-defaults"} for entry in prepared.entries}
        return {"schema_version": 1, "result": "applied" if prepared.attempted else "unchanged",
                "hosts": prepared.report["hosts"], "changes": prepared.report["changes"],
                "core_sha256": prepared.report["core_sha256"], "observations": observed,
                "deferred": prepared.report["deferred"], "mutation_performed": bool(prepared.attempted),
                "limits": "New sessions/reload may be required; this is not active-session identity evidence."}
