#!/usr/bin/env python
"""Plan and transactionally reconcile persistent agent changes with Agent Sync."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import uuid
import time
import contextvars
import re
from functools import wraps
from pathlib import Path
from typing import Any, Mapping, Sequence

import jsonschema

try:
    import hermes_skill_review
    import capability_intake
    import fleet
    import host_deltas
    import recovery
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import hermes_skill_review  # type: ignore
    import capability_intake  # type: ignore
    import fleet  # type: ignore
    import host_deltas  # type: ignore
    import recovery  # type: ignore

SURFACES = ["recovery", "fleet", "instructions", "governance", "host-deltas", "skill-proposals"]
LIVE_MUTATION_ACTIONS = {"add", "adopt", "materialize", "repair", "update", "remove"}


def nonblocking_observation_kind(item: Any) -> str | None:
    """Classify validated plan output, never grant admission or approve a proposal.

    External pins are checked by plan and rechecked before writes/readback.
    Keep this shared with audit so visible no-action records are not conflicts.
    """
    if not isinstance(item, Mapping) or item.get("auto_apply_eligible") is not False:
        return None

    def digest(key: str) -> bool:
        value = item.get(key)
        return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)

    if (item.get("surface") == "skill-proposals" and item.get("host") == "hermes"
            and item.get("disposition") == "review-required"
            and isinstance(item.get("pending_id"), str) and item["pending_id"]
            and item.get("target") == item["pending_id"] and digest("sha256")):
        return "staged-skill-proposal"
    owner = item.get("external_owner")
    if (item.get("surface") == "fleet" and item.get("source_action") == "observe-external"
            and item.get("change_class") == "reviewed-external-owner"
            and item.get("disposition") == "no-action" and item.get("eligible_after_checks") is False
            and isinstance(owner, str) and owner and item.get("owner") == f"external:{owner}"
            and isinstance(item.get("destination"), str) and item["destination"]
            and isinstance(item.get("target"), str) and item["target"]
            and digest("content_sha256") and digest("marker_sha256")):
        return "reviewed-external-owner"
    return None


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def _finding_id(item: Mapping[str, Any]) -> str:
    stable = {key: value for key, value in item.items() if key != "finding_id"}
    return hashlib.sha256(_json_bytes(stable)).hexdigest()[:24]


def _with_id(item: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(item)
    result["finding_id"] = _finding_id(result)
    return result


def _snapshot(repo: Path) -> Path:
    config = fleet.load_fleet(repo)
    return fleet.validated_snapshot_output(repo, repo / str(config["snapshot_root"]))


def _destinations(
    repo: Path,
    machine: str,
    skill_roots: Sequence[str | Path] | None,
) -> list[tuple[str, Path]]:
    config = fleet.load_fleet(repo)
    machines = config["machines"]
    selected = machines.get(machine)
    if not isinstance(selected, Mapping):
        raise RuntimeError(f"unknown machine: {machine}")
    if skill_roots is None:
        raw = selected.get("skill_roots", [])
        roots = [fleet.resolve_template(str(value)) for value in raw]
    else:
        roots = [Path(value).expanduser().resolve() for value in skill_roots]
    unique = sorted({Path(root) for root in roots}, key=lambda value: os.path.normcase(str(value)))
    return [(f"{machine}:skill-root-{index}", root) for index, root in enumerate(unique, start=1)]


def _skill_state(repo: Path, snapshot: Path, destinations: list[tuple[str, Path]], name: str) -> dict[str, Any]:
    registry = fleet.registry(repo)
    entry = registry.get(name)
    canonical_path = repo / "skills" / name
    snapshot_path = snapshot / "skills" / name
    canonical = fleet.installed_hash(canonical_path)
    rendered = fleet.installed_hash(snapshot_path)
    live = [(label, path, fleet.installed_hash(path / name)) for label, path in destinations]
    managed = [
        (label, path, fleet.load_state(path).get("skills", {}).get(name, {}).get("sha256"))
        for label, path in destinations
    ]
    prior_values = {digest for _, _, digest in managed if isinstance(digest, str)}
    baseline = next(iter(prior_values)) if len(prior_values) == 1 else None
    changed_live = [
        (label, path, digest)
        for label, path, digest in live
        if baseline is None or digest != baseline
    ]

    state: dict[str, Any] = {
        "name": name,
        "registry_status": str((entry or {}).get("status", "unregistered")),
        "canonical_sha256": canonical,
        "rendered_sha256": rendered,
        "baseline_sha256": baseline,
        "managed": managed,
        "live": live,
        "changed_live": changed_live,
        "mode": "review-required",
        "origin": None,
    }
    if entry is None or entry.get("status") != "admitted":
        state["reason"] = "owner is not admitted"
    elif (canonical is None or rendered is None or baseline is None
          or any(digest is None for _, _, digest in live)
          or any(not isinstance(digest, str) for _, _, digest in managed)):
        state["reason"] = "owner is missing from canonical, rendered, managed, or live state"
    elif len(prior_values) != 1:
        state["reason"] = "managed destinations do not share one prior owner identity"
    elif not changed_live:
        if canonical == baseline:
            state.update(mode="unchanged", reason="canonical and live state match the managed baseline")
        else:
            state.update(mode="deploy-canonical", reason="only canonical state changed from the managed baseline")
    elif len(changed_live) == 1 and canonical == baseline:
        label, path, digest = changed_live[0]
        state.update(mode="adopt-live", origin=(label, path, digest), reason="one live origin changed and canonical still matches the managed baseline")
    elif all(digest == canonical for _, _, digest in live) and canonical != baseline:
        state.update(mode="deploy-canonical", reason="canonical change is already present in every live destination")
    else:
        state["reason"] = "concurrent, cross-origin, or ambiguous skill changes"
    return state


def _instruction_findings(repo: Path) -> list[dict[str, Any]]:
    path = repo / "contracts" / "instruction-surfaces.json"
    if not path.is_file():
        return [_with_id({"surface": "instructions", "target": "instruction-surfaces", "disposition": "review-required", "reason": "contract missing"})]
    data = json.loads(path.read_text(encoding="utf-8"))
    findings: list[dict[str, Any]] = []
    for surface in data.get("surfaces", []):
        if not isinstance(surface, Mapping):
            continue
        if surface.get("id") == "codex.surface-curator-plugin" and surface.get("status") != "disabled":
            findings.append(_with_id({"surface": "instructions", "target": str(surface.get("id")), "disposition": "review-required", "reason": "legacy authority is not disabled"}))
    return findings


def _governance_findings(repo: Path) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    registry = fleet.registry(repo)
    for required in ("cross-agent-surface-engineering", "fleet-sync"):
        if registry.get(required, {}).get("status") != "admitted":
            findings.append(_with_id({"surface": "governance", "target": required, "disposition": "review-required", "reason": "effective deterministic owner is not admitted"}))
    return findings


def _reconciliation_intent(*, adopt=(), include=(), recovery_artifacts=None,
                           capture_recovery=None, scoped=None, recovery_roots=None):
    """Resolve the same scope and capture contract for preview and completion."""
    if recovery_artifacts is not None and scoped is False:
        raise ValueError("full scope cannot broaden an exact artifact selection")
    if recovery_artifacts is not None and capture_recovery is False:
        raise ValueError("artifact capture conflicts with no-capture-recovery")
    selected = bool(adopt or include or recovery_artifacts is not None) if scoped is None else scoped
    capture = (bool(recovery_artifacts) if selected else
               recovery_roots is None or bool(recovery_roots)) if capture_recovery is None else capture_recovery
    if selected and capture and recovery_artifacts is None:
        raise ValueError("scoped recovery capture needs an explicit artifact contract; use a reviewed broad recovery operation")
    return {"scoped": selected, "capture_recovery": bool(capture)}


def plan(
    repo: str | Path,
    *,
    machine: str = "local-windows",
    recovery_roots: Mapping[str, str | Path] | None = None,
    skill_roots: Sequence[str | Path] | None = None,
    live: bool = False,
    review_options: Mapping[str, Any] | None = None,
    adopt: Sequence[str] = (),
    include: Sequence[str] = (),
    recovery_artifacts: Sequence[str] | None = None,
    capture_recovery: bool | None = None,
    scoped: bool | None = None,
) -> dict[str, Any]:
    """Aggregate bounded metadata-only findings across every governed surface."""

    repo = Path(repo).resolve()
    import sync_git
    names = _selected_owners(repo, adopt, strict=True)
    included = [sync_git.safe_path(repo, value) for value in include]
    for value in included:
        if not (repo / value).is_file():
            # An exact tracked deletion is a valid publication selection.
            if not (repo / ".git").exists() or not sync_git.git(repo, "ls-files", "--", value):
                raise RuntimeError("unknown included file: " + value)
    if recovery_artifacts is not None:
        recovery._select_artifacts(recovery._load_policy(repo / "recovery.json"), recovery_artifacts)
    intent = _reconciliation_intent(adopt=names, include=included, recovery_artifacts=recovery_artifacts,
                                    capture_recovery=capture_recovery, scoped=scoped, recovery_roots=recovery_roots)
    selected_scope = intent["scoped"]
    if not intent["capture_recovery"]:
        recovery_roots = {}
    findings: list[dict[str, Any]] = []
    try:
        if recovery_roots is None or recovery_roots:
            scan = capability_intake.scan(
                repo,
                machine=machine,
                recovery_roots=recovery_roots,
                skill_roots=skill_roots,
            )
            findings.extend(_with_id(item) for item in scan["findings"])
        else:
            findings.extend(_with_id(item) for item in capability_intake.fleet_findings(
                repo, machine=machine, skill_roots=skill_roots,
            ))
        findings.extend(_instruction_findings(repo))
        findings.extend(_governance_findings(repo))
    except (RuntimeError, ValueError, OSError) as exc:
        if not selected_scope:
            raise
        findings.append(_with_id({"surface": "governance", "target": "unselected-inventory",
            "disposition": "deferred", "reason": _safe_diagnostic(str(exc), repo)}))
    roots = recovery._default_roots() if recovery_roots is None else recovery_roots
    if roots.get("hermes"):
        findings.extend(_with_id(item) for item in hermes_skill_review.pending_findings(Path(roots["hermes"])))
    manifest = repo / "host-deltas.json"
    schema = repo / "contracts" / "host-deltas.schema.json"
    if manifest.is_file() and schema.is_file():
        try:
            host_deltas.load_manifest(manifest, repo)
        except RuntimeError:
            findings.append(_with_id({"surface": "host-deltas", "target": "host-deltas.json", "disposition": "review-required", "reason": "manifest is invalid or not public-safe"}))
    elif not manifest.is_file():
        findings.append(_with_id({"surface": "host-deltas", "target": "host-deltas.json", "disposition": "review-required", "reason": "manifest missing"}))

    unique: dict[str, dict[str, Any]] = {}
    for item in findings:
        unique[item["finding_id"]] = item
    ordered = sorted(unique.values(), key=lambda item: item["finding_id"])
    owners = names if selected_scope else {name for name, entry in fleet.registry(repo).items() if entry.get("status") == "admitted"}
    selected_owner_findings = []
    if owners:
        snapshot = _snapshot(repo)
        destinations = _destinations(repo, machine, skill_roots)
        for name in sorted(owners):
            state = _skill_state(repo, snapshot, destinations, name)
            if names or state["mode"] != "unchanged":
                selected_owner_findings.append(_with_id({"surface": "fleet", "target": name,
                    "owner": name, "source_action": state["mode"], "reason": state["reason"],
                    "disposition": "review-required" if state["mode"] == "review-required" else
                        ("no-action" if state["mode"] == "unchanged" else "eligible-after-checks"),
                    "canonical_sha256": state["canonical_sha256"], "baseline_sha256": state["baseline_sha256"]}))
    observations = []
    if selected_scope:
        references = set(recovery_artifacts or ())
        relevant = lambda row: (row.get("surface") == "fleet" and row.get("target") in names) or (
            row.get("surface") == "recovery" and f"{row.get('host')}:{row.get('target', row.get('id'))}" in references)
        observations = [row for row in ordered if not relevant(row)]
        ordered = [row for row in ordered if relevant(row) and row.get("surface") != "fleet"] + selected_owner_findings
        ordered += [_with_id({"surface": "governance", "target": value, "source_action": "publish-file",
                              "disposition": "eligible-after-checks"}) for value in included]
        ordered += [_with_id({"surface": "recovery", "target": value, "source_action": "capture-artifact",
                              "disposition": "eligible-after-checks"}) for value in sorted(references)]
    else:
        ordered += selected_owner_findings
    report = {
        "schema_version": 1,
        "mode": "live-readback" if live else "read-only-plan",
        "machine": machine,
        "surfaces": list(SURFACES),
        "mutation_performed": False,
        "intent": intent,
        "findings": ordered,
        "summary": {"total": len(ordered)},
    }
    if selected_scope:
        binding_dependencies = set()
        if (repo / "host-deltas.json").is_file():
            binding_dependencies = _binding_selection(host_deltas._load_manifest_unbound(repo / "host-deltas.json", repo),
                                                     names, recovery_artifacts, included)
        for identity in sorted(binding_dependencies):
            report["findings"].append(_with_id({"surface": "host-deltas", "target": identity,
                "source_action": "refresh-binding", "disposition": "eligible-after-checks"}))
        report["summary"]["total"] = len(report["findings"])
        report.update(selection={"owners": sorted(names), "files": sorted(included),
                                 "recovery_artifacts": sorted(recovery_artifacts or ())},
                      observations=observations,
                      binding_dependencies=sorted(binding_dependencies),
                      dependencies=_scope_dependencies(repo, machine, names, bool(recovery_artifacts), recovery_artifacts, binding_dependencies))
    if review_options:
        import change_review
        report["authoring_review"] = change_review.review(repo, **review_options)
    return report


def _selected_owners(repo, owners, *, strict=False):
    if not owners:
        return set()
    selected = fleet.owner_scope(owners, fleet.registry(repo) if strict else {value: {} for value in owners}) or set()
    return selected


def _assert_skill_public_safe(path: Path, name: str) -> None:
    record = fleet.directory_record(path, allow_root_link=True)
    for relative in record["files"]:
        data = (path / relative).read_bytes()
        recovery._assert_public_safe(data, label=f"skill:{name}:{relative}")


def _replace_tree(source: Path, target: Path) -> None:
    stage = target.with_name(f".{target.name}.reconcile-stage-{uuid.uuid4().hex}")
    fleet.remove_tree(stage)
    shutil.copytree(source, stage)
    old = target.with_name(f".{target.name}.reconcile-old-{uuid.uuid4().hex}")
    had_old = target.exists() or target.is_symlink()
    if had_old:
        os.replace(target, old)
    try:
        os.replace(stage, target)
    except Exception:
        if had_old and old.exists():
            os.replace(old, target)
        raise
    if old.exists():
        fleet.remove_tree(old)


def _copy_optional(source: Path, destination: Path) -> bool:
    if not (source.exists() or source.is_symlink()):
        return False
    initial = _mutation_identity(source)
    if fleet.is_linklike_path(source):
        if not source.is_symlink():
            raise RuntimeError(f"cannot transactionally back up a junction: {source}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.symlink_to(os.readlink(source), target_is_directory=source.is_dir())
    elif source.is_dir():
        shutil.copytree(source, destination)
    else:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    if _mutation_identity(source) != initial:
        raise RuntimeError("backup source changed while copying")
    return True


def _restore_optional(backup: Path, target: Path, existed: bool) -> None:
    fleet.remove_tree(target)
    if existed:
        if fleet.is_linklike_path(backup):
            target.parent.mkdir(parents=True, exist_ok=True)
            os.replace(backup, target)
        elif backup.is_dir():
            shutil.copytree(backup, target)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(backup, target)


def _backup_key(label: str) -> str:
    """Return a portable directory name for a logical destination label."""

    return hashlib.sha256(label.encode("utf-8")).hexdigest()[:16]


_check_measurements = contextvars.ContextVar("reconciliation_measurements", default=None)
_check_log_repo = contextvars.ContextVar("reconciliation_log_repo", default=None)


def _measure_completion(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        events = []
        token = _check_measurements.set(events)
        log_token = _check_log_repo.set(Path(args[0] if args else kwargs["repo"]).resolve())
        started = time.perf_counter()
        try:
            result = function(*args, **kwargs)
            result["measurements"] = {"total_seconds": time.perf_counter() - started,
                "checks": events, "check_seconds": sum(row["seconds"] for row in events),
                "billed_cost_usd": None, "cost_status": "not-observed"}
            return result
        finally:
            _check_measurements.reset(token)
            _check_log_repo.reset(log_token)
    return wrapped


def _transaction_lock(function):
    @wraps(function)
    def wrapped(repo, **kwargs):
        import sync_git
        repo = Path(repo).resolve()
        names = kwargs.get("adopt") or ()
        capture = kwargs.get("capture_recovery", False) or bool(kwargs.get("recovery_artifacts"))
        paths = [_snapshot(repo), repo / "host-deltas.json", *(repo / "skills" / name for name in names),
                 *(root for _, root in _destinations(repo, kwargs.get("machine", "local-windows"), kwargs.get("skill_roots")))] if names else []
        if kwargs.get("binding_identities"):
            paths.append(repo / "host-deltas.json")
        if capture:
            paths.extend([repo / "recovery/current", repo / "host-deltas.json"])
            roots = kwargs.get("recovery_roots") or recovery._default_roots()
            selected = kwargs.get("recovery_artifacts")
            hosts = {value.split(":", 1)[0] for value in selected} if selected else set(roots)
            paths.extend(Path(roots[host]) for host in hosts if host in roots)
        with sync_git.path_locks(paths):
            return function(repo, **kwargs)
    return wrapped


def _safe_diagnostic(output: str, repo: Path) -> str:
    output = output.replace(str(repo), "<repo>").replace(str(Path.home()), "<home>")
    output = re.sub(r"(?:[A-Za-z]:[\\/]|/)(?:[^\s:'\"<>]+[\\/])+[^\s:'\"<>]*", "<path>", output)
    output = re.sub(r"(?i)(?:sk-[\w-]+|(?:token|password|secret|api[_-]?key)\s*[:=]\s*[^\s]+)", "<redacted>", output)
    output = output[-2048:].strip()
    try:
        recovery._assert_public_safe(output.encode("utf-8"), label="check-diagnostic")
    except recovery.RecoveryError:
        return "diagnostic withheld by public-safety validation"
    return output


class CheckFailure(RuntimeError):
    def __init__(self, detail, completed_checks):
        super().__init__("reconciliation check failed: " + detail["command"])
        self.detail = detail
        self.completed_checks = list(completed_checks)


def _failure_detail(exc, phase, repo):
    return {"phase": phase, **(exc.detail if isinstance(exc, CheckFailure) else {
        "command": None, "exit_code": None, "diagnostic": _safe_diagnostic(str(exc), repo)})}


def _run_checks(repo: Path, commands: Sequence[Sequence[str] | str]) -> list[str]:
    labels: list[str] = []
    for command in commands:
        argv = [command] if isinstance(command, str) else list(command)
        started = time.perf_counter()
        try:
            completed = subprocess.run(argv, cwd=repo, capture_output=True, text=True, check=False)
        except OSError as exc:
            raise CheckFailure({"command": _safe_diagnostic(" ".join(Path(part).name if Path(part).is_absolute() else part for part in argv), repo),
                                "exit_code": None, "diagnostic": _safe_diagnostic(str(exc), repo)}, labels) from exc
        label = _safe_diagnostic(" ".join(
            Path(part).name if index == 0 or Path(part).is_absolute() else part
            for index, part in enumerate(argv)
        ), repo)
        measurements = _check_measurements.get()
        if measurements is not None:
            measurements.append({"command": label, "seconds": time.perf_counter() - started, "passed": completed.returncode == 0})
        if completed.returncode != 0:
            output = "\n".join(value for value in (completed.stdout, completed.stderr) if value)
            log_root = _check_log_repo.get() or repo
            log = log_root / ".staging/check-failures" / (uuid.uuid4().hex + ".json")
            fleet.atomic_json(log, {"argv": argv, "exit_code": completed.returncode, "output": output})
            raise CheckFailure({"command": label, "exit_code": completed.returncode,
                                "diagnostic": _safe_diagnostic(output, repo),
                                "local_log": log.relative_to(log_root).as_posix()}, labels)
        labels.append(label)
    return labels


def _tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    if root.is_dir():
        for path in sorted(item for item in root.rglob("*") if item.is_file()):
            digest.update(path.relative_to(root).as_posix().encode("utf-8"))
            digest.update(b"\0")
            digest.update(path.read_bytes())
    return digest.hexdigest()


def _request_id(machine: str, owners: Sequence[str], desired: Sequence[str]) -> str:
    value = {
        "machine": machine,
        "owners": list(owners),
        "desired": list(desired),
    }
    return hashlib.sha256(_json_bytes(value)).hexdigest()


def _request_schema(repo: Path) -> dict[str, Any]:
    path = repo / "contracts" / "change-request.schema.json"
    if not path.is_file():
        path = Path(__file__).resolve().parents[1] / "contracts" / "change-request.schema.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _request_artifacts(states: Sequence[Mapping[str, Any]]) -> list[dict[str, str]]:
    artifacts: list[dict[str, str]] = []
    for state in states:
        before = state.get("canonical_sha256")
        origin = state.get("origin")
        after = origin[2] if origin else before
        if not isinstance(before, str) or len(before) != 64:
            continue
        if not isinstance(after, str) or len(after) != 64:
            continue
        artifacts.append(
            {
                "owner": str(state["name"]),
                "source": "live" if origin else "canonical",
                "before_sha256": before,
                "after_sha256": after,
            }
        )
    return artifacts


def _write_request(repo: Path, request: Mapping[str, Any]) -> Path:
    value = dict(request)
    jsonschema.Draft202012Validator(_request_schema(repo)).validate(value)
    recovery._assert_public_safe(_json_bytes(value), label="change-request")
    path = repo / "reconciliation" / "requests" / f"{value['request_id']}.json"
    fleet.atomic_json(path, value)
    return path


def _decision_receipt(
    repo: Path,
    *,
    machine: str,
    names: Sequence[str],
    states: Sequence[Mapping[str, Any]],
    result: str,
    risk: str,
    failed_phase: str = "preflight",
) -> dict[str, Any]:
    owners = sorted(set(names)) or ["unresolved-change"]
    desired = [
        "|".join(
            str(value)
            for value in (
                state.get("name"),
                state.get("canonical_sha256"),
                state.get("baseline_sha256"),
                state.get("reason"),
            )
        )
        for state in states
    ] or [result]
    request_id = _request_id(machine, owners, [*desired, result])
    phase_order = ["preflight", "canonicalize", "render", "validate", "deploy", "verify"]
    if result == "rejected" and failed_phase in phase_order:
        failed_index = phase_order.index(failed_phase)
        phase_rows = [
            {
                "name": name,
                "status": "completed" if index < failed_index else ("failed" if index == failed_index else "skipped"),
            }
            for index, name in enumerate(phase_order)
        ]
    else:
        phase_rows = [
            {"name": "preflight", "status": "completed"},
            *({"name": name, "status": "skipped"} for name in phase_order[1:]),
        ]
    request = {
        "$schema": "../../contracts/change-request.schema.json",
        "schema_version": 1,
        "request_id": request_id,
        "machine": machine,
        "phase": result,
        "operation": "classify-change",
        "source": {"host": "shared-or-unknown", "surface": "fleet"},
        "risk": risk,
        "disposition": result,
        "owners": owners,
        "artifacts": _request_artifacts(states),
        "phases": [
            {"name": "classify", "status": "completed"},
            *phase_rows,
            {"name": "receipt", "status": "completed"},
        ],
        "checks": ["deterministic classification"],
        "result": result,
    }
    _write_request(repo, request)
    return {
        "schema_version": 1,
        "result": result,
        "mutation_performed": False,
        "request_id": request_id,
        "owners": owners,
    }


def _frozen_binding_candidate(function):
    @wraps(function)
    def wrapped(repo, **kwargs):
        import sync_git
        repo = Path(repo).resolve()
        names = _selected_owners(repo, kwargs.get("adopt") or ())
        if not names or kwargs.get("binding_repo") is not None or not (repo / ".git").exists():
            return function(repo, **kwargs)
        destinations = _destinations(repo, kwargs.get("machine", "local-windows"), kwargs.get("skill_roots"))
        selected, overrides = set(), {}
        for name in names:
            state = _skill_state(repo, _snapshot(repo), destinations, name)
            if state["mode"] == "review-required":
                return function(repo, **kwargs)
            desired = state["origin"][1] / name if state.get("origin") else repo / "skills" / name
            tracked = set(sync_git.git(repo, "ls-files", "-z", "--", f"skills/{name}/").split("\0")) - {""}
            files = {f"skills/{name}/{p}" for p in fleet.directory_record(desired)["files"]}
            selected.update(tracked | files)
            for value in tracked | files:
                source = desired / Path(value).relative_to(Path("skills") / name)
                overrides[value] = source.read_bytes() if source.is_file() else None
        identities = {value: hashlib.sha256(data).hexdigest() if data is not None else "deleted"
                      for value, data in overrides.items()}
        with sync_git.prepare_candidate(repo, identities, overrides=overrides) as (candidate, _):
            return function(repo, **kwargs, binding_repo=candidate)
    return wrapped


def _copy_binding_source(source, destination, manifest):
    """Copy only the declared artifact dependency closure into private staging."""
    destination.mkdir(parents=True)
    def copy_file(relative):
        path = recovery._safe_join(source, relative, must_exist=False)
        if path.is_file():
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
    copy_file("contracts/host-deltas.schema.json")
    sources = {row["source_identity"] for row in manifest["entries"]}
    if any(value.startswith("fleet:") for value in sources):
        copy_file("registry.json")
        for name, admitted in fleet.registry(source).items():
            if admitted.get("status") != "admitted":
                continue
            origin = source / "skills" / name
            record = fleet.directory_record(origin)
            target = destination / "skills" / name
            shutil.copytree(origin, target, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache", ".pytest-cache"))
            if fleet.directory_record(target) != record:
                raise RuntimeError("binding artifact changed while copying")
    if any(value.startswith("recovery-artifact:") for value in sources):
        copy_file("recovery/current/manifest.json")
        path = source / "recovery/current/manifest.json"
        records = json.loads(path.read_text(encoding="utf-8"))["artifacts"] if path.is_file() else []
        for row in records:
            if "recovery-artifact:" + f"{row['host']}:{row['id']}" in sources:
                copy_file("recovery/current/" + row["snapshot"])
    for identity in sources:
        if identity.startswith("repository:"):
            copy_file(identity.removeprefix("repository:"))


@_transaction_lock
@_frozen_binding_candidate
def sync(
    repo: str | Path,
    *,
    machine: str = "local-windows",
    adopt: Sequence[str] | None = None,
    recovery_roots: Mapping[str, str | Path] | None = None,
    skill_roots: Sequence[str | Path] | None = None,
    check_commands: Sequence[Sequence[str] | str] | None = None,
    capture_recovery: bool = False,
    scoped: bool = False,
    recovery_artifacts: Sequence[str] | None = None,
    binding_repo: Path | None = None,
    binding_identities: Sequence[str] = (),
) -> dict[str, Any]:
    """Reconcile selected owners and optionally capture allowlisted host state."""

    repo = Path(repo).resolve()
    names = sorted(_selected_owners(repo, adopt or ()))
    if recovery_artifacts is not None:
        recovery._select_artifacts(recovery._load_policy(repo / "recovery.json"), recovery_artifacts)
        capture_recovery = True
    if not names and not capture_recovery and not binding_identities:
        report = _decision_receipt(
            repo,
            machine=machine,
            names=[],
            states=[],
            result="review-required",
            risk="review",
        )
        report["reason"] = "no existing admitted owner or recovery capture was selected"
        return report
    host_delta_path = repo / "host-deltas.json"
    if capture_recovery:
        try:
            manifest = host_deltas._load_manifest_unbound(host_delta_path, repo)
            selected_bindings = {row["source_identity"] for row in manifest["entries"]
                if row["source_identity"].startswith("recovery-artifact:") and
                (recovery_artifacts is None or row["source_identity"].removeprefix("recovery-artifact:") in recovery_artifacts)}
            host_deltas._validate_bindings(manifest, repo, source_identities=selected_bindings)
        except RuntimeError:
            report = _decision_receipt(
                repo,
                machine=machine,
                names=[*names, "recovery-state", "host-deltas"],
                states=[],
                result="review-required",
                risk="review",
            )
            report["reason"] = "typed host-delta manifest must be valid before recovery capture"
            return report
    fleet_snapshot = _snapshot(repo) if names else repo / "render/fleet"
    destinations = _destinations(repo, machine, skill_roots) if names else []
    states = [_skill_state(repo, fleet_snapshot, destinations, name) for name in names]
    if any(state["mode"] == "review-required" for state in states):
        report = _decision_receipt(
            repo,
            machine=machine,
            names=names,
            states=states,
            result="review-required",
            risk="review",
        )
        report["reasons"] = [
            {"owner": state["name"], "reason": state["reason"]}
            for state in states
            if state["mode"] == "review-required"
        ]
        return report
    try:
        for state in states:
            if state["mode"] == "adopt-live":
                _assert_skill_public_safe(state["origin"][1] / state["name"], state["name"])
            else:
                _assert_skill_public_safe(repo / "skills" / state["name"], state["name"])
    except recovery.RecoveryError:
        report = _decision_receipt(
            repo,
            machine=machine,
            names=names,
            states=states,
            result="rejected",
            risk="high",
        )
        report["reason"] = "selected content failed public-safety validation"
        return report

    commands = list(check_commands) if check_commands is not None else [
        [sys.executable, str(repo / "tools" / "validate.py")],
        [sys.executable, str(repo / "tools" / "public_check.py")],
    ]

    with tempfile.TemporaryDirectory(prefix="agent-signal-reconcile-") as temporary:
        workspace = Path(temporary)
        backup = workspace / "backup"
        prepared_recovery: Path | None = None
        recovery_before: str | None = None
        recovery_after: str | None = None
        resolved_recovery_roots = dict(recovery_roots) if recovery_roots is not None else recovery._default_roots()
        if capture_recovery:
            prepared_recovery = workspace / "prepared-recovery"
            if recovery_artifacts is not None:
                shutil.copytree(repo / "recovery/current", prepared_recovery)
            recovery.snapshot(
                repo / "recovery.json",
                prepared_recovery,
                resolved_recovery_roots,
                repo_root=repo,
                artifacts=recovery_artifacts,
            )
            recovery_before = _tree_hash(repo / "recovery" / "current")
            recovery_after = _tree_hash(prepared_recovery)

        binding_sources = set(binding_identities)
        binding_result = None
        binding_input_identity = _mutation_identity(host_delta_path)
        if host_delta_path.is_file() and (names or capture_recovery or binding_sources):
            raw_manifest = host_deltas._load_manifest_unbound(host_delta_path, repo)
            binding_sources.update(_binding_selection(raw_manifest, names, recovery_artifacts))
            for row in raw_manifest["entries"]:
                source = row["source_identity"]
                if (names and source.startswith("fleet:")) or (capture_recovery and source.startswith("recovery-artifact:") and
                        (recovery_artifacts is None or source.removeprefix("recovery-artifact:") in recovery_artifacts)):
                    binding_sources.add(source)
            if binding_sources:
                # Freeze aggregate fleet integrity from the selected candidate.
                # Recovery is copied only to this private prospective source.
                prospective = workspace / "binding-source"
                source_repo = Path(binding_repo) if binding_repo is not None else repo
                _copy_binding_source(source_repo, prospective, raw_manifest)
                if binding_repo is None and scoped and names:
                    baseline_manifest = fleet.load_manifest(fleet_snapshot)
                    if baseline_manifest["registry_sha256"] != fleet.sha256_file(repo / "registry.json"):
                        raise RuntimeError("scoped binding requires a frozen registry baseline")
                    _replace_tree(fleet_snapshot / "skills", prospective / "skills")
                for state in states:
                    desired = state["origin"][1] / state["name"] if state.get("origin") else repo / "skills" / state["name"]
                    _replace_tree(desired, prospective / "skills" / state["name"])
                if prepared_recovery is not None:
                    # Freeze any valid legacy aggregate recovery hashes before
                    # changing its aggregate; unchanged artifacts keep identity.
                    baseline_manifest_path = repo / "recovery/current/manifest.json"
                    old_aggregate = "sha256:" + fleet.sha256_file(baseline_manifest_path)
                    old_records = {f"{row['host']}:{row['id']}": row for row in
                        json.loads(baseline_manifest_path.read_text(encoding="utf-8"))["artifacts"]}
                    for row in raw_manifest["entries"]:
                        source = row["source_identity"]
                        if source.startswith("recovery-artifact:") and row["version_or_hash"] == old_aggregate:
                            record = old_records.get(source.removeprefix("recovery-artifact:"))
                            if record is not None:
                                row["version_or_hash"] = "sha256:" + record["sha256"]
                    _replace_tree(prepared_recovery, prospective / "recovery/current")
                fleet.atomic_json(prospective / "host-deltas.json", raw_manifest)
                binding_result = host_deltas.prepare_bindings(prospective / "host-deltas.json", prospective,
                    source_identities=sorted(binding_sources))

        owners = names + (["recovery-state", "host-deltas"] if capture_recovery else (["host-deltas"] if binding_result else []))
        desired = [
            str(state["origin"][2] if state.get("origin") else state["canonical_sha256"])
            for state in states
        ] + ([str(recovery_after)] if capture_recovery else [])
        if binding_result is not None:
            desired.append(hashlib.sha256(_json_bytes(binding_result["manifest"])).hexdigest())
        request_id = _request_id(machine, owners, desired)
        request_path = repo / "reconciliation" / "requests" / f"{request_id}.json"
        no_skill_change = all(state["mode"] == "unchanged" for state in states)
        no_recovery_change = not capture_recovery or recovery_before == recovery_after
        no_binding_change = binding_result is None or binding_result["manifest"] == host_deltas._load_manifest_unbound(host_delta_path, repo)
        if request_path.is_file() and no_skill_change and no_recovery_change and no_binding_change:
            return {"schema_version": 1, "result": "unchanged", "mutation_performed": False, "request_id": request_id, "owners": owners}

        if capture_recovery and names:
            operation = "mixed-safe-reconciliation"
        elif capture_recovery:
            operation = "capture-recovery"
        elif not states and binding_result is not None:
            operation = "refresh-artifact-bindings"
        elif any(state["mode"] == "adopt-live" for state in states):
            operation = "adopt-existing-owner"
        else:
            operation = "deploy-canonical-owner"
        artifacts = [
            {
                "owner": state["name"],
                "source": "live" if state["mode"] == "adopt-live" else "canonical",
                "before_sha256": str(state["canonical_sha256"]),
                "after_sha256": str(state["origin"][2] if state.get("origin") else state["canonical_sha256"]),
            }
            for state in states
        ]
        if capture_recovery:
            artifacts.append(
                {
                    "owner": "recovery-state",
                    "source": "live",
                    "before_sha256": str(recovery_before),
                    "after_sha256": str(recovery_after),
                }
            )
        source_surface = "mixed" if capture_recovery and states else ("recovery" if capture_recovery else "fleet")
        if not states and binding_result is not None and not capture_recovery:
            source_surface = "host-deltas"
        source_labels = sorted(
            {
                str(state["origin"][0])
                for state in states
                if state.get("origin")
            }
        )
        source_host = "+".join(source_labels) if source_labels else ("live-hosts" if capture_recovery else "canonical")

        canonical_existed: dict[str, bool] = {}
        live_existed: dict[tuple[str, str], bool] = {}
        targets = [request_path, *(repo / "skills" / state["name"] for state in states)]
        if states:
            targets.append(fleet_snapshot)
        if capture_recovery:
            targets.extend([repo / "recovery" / "current", host_delta_path])
        elif binding_result is not None:
            targets.append(host_delta_path)
        prewrite = {target: _mutation_identity(target) for target in targets}
        snapshot_existed = _copy_optional(fleet_snapshot, backup / "snapshot") if states else False
        recovery_existed = _copy_optional(repo / "recovery" / "current", backup / "recovery") if capture_recovery else False
        host_delta_existed = _copy_optional(host_delta_path, backup / "host-deltas.json") if capture_recovery or binding_result is not None else False
        host_delta_before = fleet.sha256_file(host_delta_path) if host_delta_existed else None
        host_delta_after = host_delta_before
        request_existed = _copy_optional(request_path, backup / "request.json")
        for state in states:
            target = repo / "skills" / state["name"]
            canonical_existed[state["name"]] = _copy_optional(target, backup / "canonical" / state["name"])
        for label, destination in destinations if states else []:
            key = _backup_key(label)
            _copy_optional(destination / fleet.STATE_FILE, backup / "live" / key / fleet.STATE_FILE)
        committed = False
        checks: list[str] = []
        failed_phase = "preflight"
        failure: Exception | None = None
        written = []
        rollback_conflicts = []
        attempted = set()
        def before_write(target):
            if _mutation_identity(target) != prewrite[target]:
                raise RuntimeError("transaction target changed before mutation")
            attempted.add(target)
        installed_state = None
        def wrote(target, saved, existed, expected_sha=None):
            if expected_sha is not None and fleet.installed_hash(target) != expected_sha:
                rollback_conflicts.append(str(target))
                return
            # Repeated own writes share one original backup and latest identity.
            written[:] = [row for row in written if row[0] != target]
            written.append((target, saved, existed, _mutation_identity(target)))
        try:
            failed_phase = "canonicalize"
            for state in states:
                if state["mode"] == "adopt-live":
                    target = repo / "skills" / state["name"]
                    before_write(target)
                    if fleet.installed_hash(target) != state["canonical_sha256"]:
                        raise RuntimeError("canonical origin changed before canonicalization")
                    if fleet.installed_hash(state["origin"][1] / state["name"]) != state["origin"][2]:
                        raise RuntimeError("live origin changed before canonicalization")
                    _replace_tree(state["origin"][1] / state["name"], target)
                    wrote(target, backup / "canonical" / state["name"], canonical_existed[state["name"]])
            if prepared_recovery is not None:
                before_write(repo / "recovery" / "current")
                _replace_tree(prepared_recovery, repo / "recovery" / "current")
                wrote(repo / "recovery" / "current", backup / "recovery", recovery_existed)
            if binding_result is not None:
                before_write(host_delta_path)
                host_deltas._write_bound_manifest(host_delta_path, binding_result["manifest"], binding_input_identity)
                host_delta_after = fleet.sha256_file(host_delta_path)
                wrote(host_delta_path, backup / "host-deltas.json", host_delta_existed)

            failed_phase = "render"
            if states:
                before_write(fleet_snapshot)
                fleet.render_snapshot(repo, fleet_snapshot, names=names if scoped else None)
                wrote(fleet_snapshot, backup / "snapshot", snapshot_existed)
                planned = fleet.preflight_destinations(
                    fleet_snapshot, [path for _, path in destinations], names=names if scoped else None
                )
                for _, actions in planned:
                    if any(action["action"] not in {"unchanged", "reconcile"} and action["name"] not in names
                           for action in actions):
                        raise RuntimeError("render includes an unselected owner change")
                    if any(action["action"] in {"remove", "forget"} for action in actions):
                        raise RuntimeError("owner retirement requires separate review")
                for (label, destination), (_, actions) in zip(
                    destinations, planned, strict=True
                ):
                    key = _backup_key(label)
                    for action in actions:
                        if action["action"] not in LIVE_MUTATION_ACTIONS:
                            continue
                        name = action["name"]
                        live_existed[(label, name)] = _copy_optional(
                            destination / name,
                            backup / "live" / key / name,
                        )

            failed_phase = "validate"
            checks = _run_checks(repo, commands)

            failed_phase = "deploy"
            if states:
                for state in states:
                    expected = state["origin"][2] if state.get("origin") else state["canonical_sha256"]
                    if fleet.installed_hash(repo / "skills" / state["name"]) != expected:
                        raise RuntimeError("selected canonical owner changed during validation")
                fleet.preflight_destinations(fleet_snapshot, [path for _, path in destinations], names=names if scoped else None)
                for label, destination in destinations:
                    key = _backup_key(label)
                    saved_state = backup / "live" / key / "state-before-apply.json"
                    expected_state = fleet.state_identity(destination)
                    state_existed = _copy_optional(destination / fleet.STATE_FILE, saved_state)
                    planned_apply = fleet.plan_snapshot(fleet_snapshot, destination, names=names if scoped else None)
                    live_attempts = [destination / row["name"] for row in planned_apply if row["action"] in LIVE_MUTATION_ACTIONS]
                    live_attempts.append(destination / fleet.STATE_FILE)
                    for target in live_attempts:
                        prewrite[target] = _mutation_identity(target)
                        attempted.add(target)
                    actions = fleet.apply_snapshot(fleet_snapshot, destination, names=names if scoped else None,
                                                   expected_state=expected_state)
                    installed_manifest = fleet.load_manifest(fleet_snapshot)
                    for action in actions:
                        identity = (label, action["name"])
                        if identity in live_existed and action["action"] in LIVE_MUTATION_ACTIONS:
                            wanted = installed_manifest["skills"].get(action["name"], {}).get("sha256")
                            wrote(destination / action["name"], backup / "live" / key / action["name"], live_existed[identity], wanted)
                    if scoped:
                        installed_state = {name: {"sha256": installed_manifest["skills"][name]["sha256"],
                            "source_snapshot": str(fleet_snapshot.resolve()),
                            "manifest_sha256": fleet.sha256_file(fleet_snapshot / fleet.MANIFEST_FILE)} for name in names}
                    wrote(destination / fleet.STATE_FILE, saved_state, state_existed)

            failed_phase = "verify"
            if states:
                for _, destination in destinations:
                    if fleet.verify_snapshot(fleet_snapshot, destination, names=names if scoped else None):
                        raise RuntimeError("fleet postflight verification failed")
            if capture_recovery:
                recovery.verify_snapshot(repo / "recovery.json", repo / "recovery" / "current")
                postflight = recovery.restore(
                    repo / "recovery.json",
                    repo / "recovery" / "current",
                    resolved_recovery_roots,
                    apply=False,
                    repo_root=repo,
                    artifacts=recovery_artifacts,
                )
                if postflight["changes"] or postflight["conflicts"]:
                    raise RuntimeError("recovery postflight verification failed")
            if binding_result is not None:
                host_deltas._validate_bindings(host_deltas._load_manifest_unbound(host_delta_path, repo),
                    prospective, source_identities=binding_sources)

            failed_phase = "receipt"
            if capture_recovery or binding_result is not None:
                artifacts.append(
                    {
                        "owner": "host-deltas",
                        "source": "canonical",
                        "before_sha256": str(host_delta_before),
                        "after_sha256": str(host_delta_after),
                    }
                )
            request = {
                "$schema": "../../contracts/change-request.schema.json",
                "schema_version": 1,
                "request_id": request_id,
                "machine": machine,
                "phase": "completed",
                "operation": operation,
                "source": {"host": source_host, "surface": source_surface},
                "risk": "low",
                "disposition": "applied",
                "owners": owners,
                "artifacts": artifacts,
                "phases": [
                    {"name": "classify", "status": "completed"},
                    {"name": "preflight", "status": "completed"},
                    {"name": "canonicalize", "status": "completed" if any(state["mode"] == "adopt-live" for state in states) or capture_recovery or binding_result is not None else "skipped"},
                    {"name": "render", "status": "completed" if states else "skipped"},
                    {"name": "validate", "status": "completed"},
                    {"name": "deploy", "status": "completed" if states else "skipped"},
                    {"name": "verify", "status": "completed"},
                    {"name": "receipt", "status": "completed"},
                ],
                "checks": checks,
                "result": "applied",
            }
            before_write(request_path)
            _write_request(repo, request)
            wrote(request_path, backup / "request.json", request_existed)
            committed = True
        except Exception as exc:
            failure = exc
        finally:
            if not committed:
                recorded = {item[0] for item in written}
                for target in attempted - recorded:
                    if _mutation_identity(target) != prewrite[target]:
                        rollback_conflicts.append(str(target))
                for target, saved, existed, installed in reversed(written):
                    if scoped and target.name == fleet.STATE_FILE:
                        # Restore selected records only; independent state added
                        # before or after our application stays with its writer.
                        guard = fleet.state_identity(target.parent)
                        current_state = fleet.load_state(target.parent)
                        if any(current_state["skills"].get(name) != installed_state[name] for name in names):
                            rollback_conflicts.append(str(target))
                            continue
                        previous_state = json.loads(saved.read_text(encoding="utf-8")) if existed else {"skills": {}}
                        updated = dict(current_state)
                        updated["skills"] = dict(current_state["skills"])
                        for name in names:
                            if name in previous_state["skills"]:
                                updated["skills"][name] = previous_state["skills"][name]
                            else:
                                updated["skills"].pop(name, None)
                        if fleet.state_identity(target.parent) != guard:
                            rollback_conflicts.append(str(target))
                            continue
                        fleet.atomic_json(target, updated)
                        continue
                    if _mutation_identity(target) != installed:
                        rollback_conflicts.append(str(target))
                        continue
                    _restore_optional(saved, target, existed)
                if rollback_conflicts or (failure is not None and "rollback conflict" in str(failure)):
                    durable = repo / ".staging" / "reconcile-backups" / (request_id + "-" + uuid.uuid4().hex)
                    durable.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copytree(backup, durable)
                    fleet.atomic_json(durable / "rollback.json", {"request_id": request_id,
                                      "concurrent_content_preserved": True,
                                      "targets": [Path(p).name for p in rollback_conflicts]})
        if failure is not None:
            report = _decision_receipt(
                repo,
                machine=machine,
                names=owners,
                states=states,
                result="rejected",
                risk="high",
                failed_phase=failed_phase,
            )
            report["reason"] = "transactional reconciliation failed and own writes were rolled back"
            report["failure"] = _failure_detail(failure, failed_phase, repo)
            report["completed_checks"] = failure.completed_checks if isinstance(failure, CheckFailure) else checks
            if rollback_conflicts or (failure is not None and "rollback conflict" in str(failure)):
                report.update(result="incomplete", mutation_performed=True,
                              reason="concurrent content preserved; rollback is incomplete",
                              rollback_conflicts=[Path(p).name for p in rollback_conflicts],
                              backup=durable.relative_to(repo).as_posix())
                # The rejected requested change and incomplete rollback are
                # distinct; preserve their status with the retained backup.
                fleet.atomic_json(durable / "outcome.json", report)
            return report
    report = {"schema_version": 1, "result": "applied", "mutation_performed": True, "request_id": request_id, "owners": owners}
    if binding_result is not None:
        report["binding_refresh"] = {"committed": True, "selected": binding_result["selected"],
                                     "deferred": binding_result["deferred"]}
    return report


def _agent_identities(destinations) -> dict[str, dict[str, str]]:
    # Include unmanaged entries as well: managed verification alone misses
    # additions made by another agent while checks are running.
    return {label: {path.name: (_tree_hash(path) if path.is_dir() else fleet.sha256_file(path))
                    for path in sorted(root.iterdir()) if path.is_dir() or path.is_file()}
            for label, root in destinations}


def _recovery_owned_paths(repo: Path) -> set[str]:
    root = repo / "recovery/current"
    recovery.verify_snapshot(repo / "recovery.json", root)
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    owned = {"manifest.json", *(str(item["snapshot"]) for item in manifest["artifacts"])}
    actual = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}
    if actual != owned or any(p.is_symlink() for p in root.rglob("*")):
        raise RuntimeError("unexpected recovery files require review; capture cannot delete or publish them")
    return {"recovery/current/" + name for name in owned}



def _mutation_identity(path: Path):
    """Identity used to avoid restoring over another writer's content."""
    return fleet.path_identity(path)


def _agent_scope_identities(destinations, names):
    if not names:
        return {}
    result = {}
    for label, root in destinations:
        state = fleet.load_state(root)
        result[label] = {
            name: {"content": fleet.installed_hash(root / name),
                   "managed": state.get("skills", {}).get(name)}
            for name in sorted(names)
        }
    return result


def _recovery_metadata_policy(value, manifest, artifacts):
    """Separate stable metadata from selected generated artifact hashes."""
    value = json.loads(json.dumps(value))
    records = {f"{row['host']}:{row['id']}": row for row in manifest["artifacts"]}
    aggregate = "sha256:" + hashlib.sha256(host_deltas._canonical_json(manifest)).hexdigest()
    for row in value["entries"]:
        source = row["source_identity"]
        if source.startswith("recovery-artifact:"):
            identity = source.removeprefix("recovery-artifact:")
            if identity in set(artifacts or ()):
                row.pop("version_or_hash", None)
            elif row["version_or_hash"] == aggregate and identity in records:
                row["version_or_hash"] = "sha256:" + records[identity]["sha256"]
    return value


def _capture_shared_preflight(repo, artifacts, included):
    """Shared metadata cannot implicitly publish another task's fields."""
    import sync_git
    def committed(name):
        return json.loads(sync_git.git(repo, "show", "HEAD:" + name))
    baseline_manifest = committed("recovery/current/manifest.json")
    current_manifest = json.loads((repo / "recovery/current/manifest.json").read_text(encoding="utf-8"))
    if "recovery/current/manifest.json" not in included:
        def outside(manifest):
            result = dict(manifest)
            result["artifacts"] = [row for row in manifest["artifacts"] if f"{row['host']}:{row['id']}" not in set(artifacts)]
            return result
        if outside(current_manifest) != outside(baseline_manifest):
            raise sync_git.SyncBlocked("unselected recovery manifest records differ; review the exact shared manifest file before publication")
    if "host-deltas.json" not in included:
        baseline = _recovery_metadata_policy(committed("host-deltas.json"), baseline_manifest, artifacts)
        current = _recovery_metadata_policy(json.loads((repo / "host-deltas.json").read_text(encoding="utf-8")), current_manifest, artifacts)
        if baseline != current:
            raise sync_git.SyncBlocked("unselected host-delta fields differ; review the exact shared metadata file before publication")


def _scope_dependencies(repo, machine, names, capture=False, recovery_artifacts=None, binding_identities=()):
    entries = fleet.registry(repo) if names else {}
    dependencies = {
        "admission": {name: entries.get(name) for name in sorted(names)},
        "destination": fleet.load_fleet(repo)["machines"].get(machine) if names else None,
        "snapshot_root": fleet.load_fleet(repo)["snapshot_root"] if names else None,
    }
    paths = ["tools/reconcile.py", "tools/fleet.py", "tools/sync_git.py",
             "tools/public_check.py"]
    paths.extend(["tools/render_instructions.py", "surfaces/core.md",
                  "adapters/codex.json", "adapters/hermes.json", "adapters/schema.json"])
    if names:
        paths.extend(["contracts/change-request.schema.json", "tools/recovery.py"])
    if binding_identities:
        paths.extend(["contracts/change-request.schema.json", "contracts/host-deltas.schema.json",
                      "tools/recovery.py", "tools/host_deltas.py"])
        metadata = host_deltas._load_manifest_unbound(repo / "host-deltas.json", repo)
        if capture:
            metadata = _recovery_metadata_policy(metadata,
                json.loads((repo / "recovery/current/manifest.json").read_text(encoding="utf-8")), recovery_artifacts)
        derived = set(binding_identities) | _binding_selection(metadata, names, recovery_artifacts)
        for row in metadata["entries"]:
            if row["source_identity"] in derived:
                row.pop("version_or_hash", None)
        dependencies["binding_metadata_policy"] = metadata
    if capture:
        dependencies["recovery_artifacts"] = sorted(recovery_artifacts or ())
        paths += ["recovery.json", "tools/recovery.py", "tools/host_deltas.py"]
        dependencies["recovery_metadata_policy"] = _recovery_metadata_policy(json.loads((repo / "host-deltas.json").read_text(encoding="utf-8")), json.loads((repo / "recovery/current/manifest.json").read_text(encoding="utf-8")), recovery_artifacts)
        derived = set(binding_identities) | _binding_selection(dependencies["recovery_metadata_policy"], names, recovery_artifacts)
        for row in dependencies["recovery_metadata_policy"]["entries"]:
            if row["source_identity"] in derived:
                row.pop("version_or_hash", None)
        if any(value in {"codex:settings", "hermes:settings"} for value in recovery_artifacts or ()):
            paths.extend(["tools/runtime_defaults.py", "surfaces/core.md", "tools/instruction_profile.py",
                          "contracts/model-profile.schema.json"])
    dependencies["execution"] = {name: fleet.sha256_file(repo / name)
                                 for name in paths if (repo / name).is_file()}
    return dependencies


def _candidate_commands(candidate, names, files=(), capture=False):
    commands = []
    if names and (candidate / "tools/validate.py").is_file():
        command = [sys.executable, str(candidate / "tools/validate.py")]
        command += [str(candidate / "skills" / name) for name in sorted(names)]
        commands.append(command)
    profile = any(value.startswith(("surfaces/", "profiles/", "adapters/", "recovery/current/hosts/")) or
                  value in {"contracts/instruction-surfaces.json", "contracts/instruction-profiles.json", "tools/instruction_profile.py"}
                  for value in files)
    structural = any(value.startswith(("tools/", "contracts/")) or value in {"registry.json", "fleet.json", "recovery.json"}
                     for value in files)
    if structural and (candidate / "tools/audit.py").is_file():
        # Structural audit already checks the artifact instruction profile.
        commands.append([sys.executable, str(candidate / "tools/audit.py"), "check", "--repo", str(candidate), "--structural"])
    elif profile and (candidate / "tools/instruction_profile.py").is_file():
        commands.append([sys.executable, str(candidate / "tools/instruction_profile.py"), "--repo", str(candidate), "--artifact-only"])
    if capture and (candidate / "tools/recovery.py").is_file():
        commands.append([sys.executable, str(candidate / "tools/recovery.py"), "verify",
                         "--policy", str(candidate / "recovery.json"), "--snapshot", str(candidate / "recovery/current")])
    if "host-deltas.json" in files and (candidate / "tools/host_deltas.py").is_file() and not structural:
        identities = _binding_selection(host_deltas._load_manifest_unbound(candidate / "host-deltas.json", candidate), names, None, files)
        if capture:
            records = json.loads((candidate / "recovery/current/manifest.json").read_text(encoding="utf-8"))["artifacts"]
            identities.update("recovery-artifact:" + f"{row['host']}:{row['id']}" for row in records
                              if "recovery/current/" + row["snapshot"] in files)
        validator = ("host_deltas._validate_bindings(host_deltas._load_manifest_unbound(Path('host-deltas.json'), Path.cwd()), "
                     "Path.cwd(), source_identities=" + repr(sorted(identities)) + ")") if identities else (
                         "host_deltas.load_manifest('host-deltas.json', Path.cwd())")
        commands.append([sys.executable, "-c",
            "import sys; from pathlib import Path; sys.path.insert(0, 'tools'); "
            "import host_deltas; " + validator])
    return commands


def _run_candidate_checks(candidate, commands, tree):
    # Generic commands may import dependencies outside the candidate or use an
    # interpreter replaced at the same path. Without a complete runtime binding,
    # rerun checks, including receipt-only candidates; argv/source is insufficient.
    def source_identity():
        source = hashlib.sha256()
        for path in sorted(candidate.rglob("*")):
            relative = path.relative_to(candidate)
            if (path.is_file() and not set(relative.parts) & {".git", "render", ".staging", "__pycache__"}
                    and not re.fullmatch(r"\.agent-signal-path-[0-9a-f]{64}\.lock", path.name)):
                source.update(relative.as_posix().encode() + b"\0" + path.read_bytes())
        return source.hexdigest()
    source = source_identity()
    result = _run_checks(candidate, commands)
    if source_identity() != source:
        raise RuntimeError("pure candidate check changed its immutable source inputs")
    return result


def _binding_selection(manifest, names, artifacts, files=()):
    return {row["source_identity"] for row in manifest["entries"]
        if (names and row["source_identity"].startswith("fleet:")) or
        (artifacts and row["source_identity"].startswith("recovery-artifact:") and
         row["source_identity"].removeprefix("recovery-artifact:") in artifacts) or
        (row["source_identity"].startswith("repository:") and
         (row["source_identity"].removeprefix("repository:") in files or any(
             row["source_identity"].startswith(f"repository:skills/{name}/") for name in names)))}


def _prepare_candidate_bindings(candidate, names, artifacts, files=()):
    path = candidate / "host-deltas.json"
    if not path.is_file():
        return
    manifest = host_deltas._load_manifest_unbound(path, candidate)
    identities = _binding_selection(manifest, names, artifacts, files)
    if identities:
        host_deltas.refresh_bindings(path, candidate, source_identities=sorted(identities))


def _owner_binding_preflight(repo, names, included):
    import sync_git
    path = repo / "host-deltas.json"
    if not path.is_file():
        return set()
    current = host_deltas._load_manifest_unbound(path, repo)
    identities = _binding_selection(current, names, None, included)
    if not identities:
        return set()
    if "host-deltas.json" not in included:
        baseline = json.loads(sync_git.git(repo, "show", "HEAD:host-deltas.json"))
        def policy(manifest):
            manifest = json.loads(json.dumps(manifest))
            for row in manifest["entries"]:
                if row["source_identity"] in identities:
                    row.pop("version_or_hash", None)
            return manifest
        if policy(current) != policy(baseline):
            raise sync_git.SyncBlocked("unselected host-delta fields differ; include the reviewed shared metadata file")
    return identities


def _scoped_complete_sync(repo, *, machine, adopt, recovery_roots, skill_roots,
                          capture_recovery, include, message, recovery_artifacts=None):
    """Complete one explicit change set; leave independent work pending."""
    import sync_git
    repo = Path(repo).resolve()
    names = _selected_owners(repo, adopt or ())
    capture = bool(capture_recovery) or bool(recovery_artifacts)
    artifacts = list(recovery_artifacts) if recovery_artifacts is not None else None
    if artifacts is not None:
        recovery._select_artifacts(recovery._load_policy(repo / "recovery.json"), artifacts)
    try:
        with sync_git.lock(repo):
            pending = sync_git.read_pending(repo)
            needed_owners = set(pending.get("owners", ())) if pending and pending.get("scoped") else names
            destinations = _destinations(repo, machine, skill_roots) if needed_owners else []
            needs_recovery = capture or bool(pending and pending.get("capture_recovery"))
            roots = {host: str(Path(path).resolve()) for host, path in
                     (recovery_roots if recovery_roots is not None else recovery._default_roots()).items()} if needs_recovery else {}
            if pending:
                if not pending.get("scoped"):
                    raise sync_git.SyncBlocked("a broad sync is pending; resume its original scope")
                if adopt and set(adopt) != set(pending["owners"]):
                    raise sync_git.SyncBlocked("pending sync belongs to a different owner selection")
                if include and not set(include).issubset(pending["files"]):
                    raise sync_git.SyncBlocked("pending sync belongs to a different publication selection")
                if pending["machine"] != machine or pending["destinations"] != [str(p) for _, p in destinations]:
                    raise sync_git.SyncBlocked("pending sync belongs to different agent destinations")
                if pending.get("recovery_roots") != roots:
                    raise sync_git.SyncBlocked("pending sync belongs to different settings directories")
                names = set(pending["owners"])
                capture = pending["capture_recovery"]
                if artifacts is not None and set(artifacts) != set(pending.get("recovery_artifacts") or ()):
                    raise sync_git.SyncBlocked("pending sync belongs to a different recovery artifact selection")
                artifacts = pending.get("recovery_artifacts")
            elif capture and artifacts is None:
                # Recovery capture is a cohesive allowlisted snapshot operation.
                # Explicit portable/file selection must not silently capture it.
                return {"result": "review-required", "reason": "scoped recovery capture needs an explicit artifact contract; use a reviewed broad recovery operation", "owners": sorted(names)}
            bind_owners = set(pending.get("binding_identities", ())) if pending else _owner_binding_preflight(repo, names, set(include))
            if pending:
                dependencies = pending["dependencies"]
            else:
                dependencies = _scope_dependencies(repo, machine, names, capture, artifacts, bind_owners)
            def check_dependencies(candidate=None):
                if _scope_dependencies(repo, machine, names, capture, artifacts, bind_owners) != dependencies:
                    raise sync_git.SyncBlocked("a selected admission, destination, or execution dependency changed")
                if candidate is not None:
                    candidate_dependencies = _scope_dependencies(candidate, machine, names, capture, artifacts, bind_owners)
                    if candidate_dependencies != dependencies:
                        raise sync_git.SyncBlocked("selected work depends on unpublished admission, destination, or execution changes; include the reviewed dependency")

            checked_agents = pending.get("agent_identities") if pending else None
            expected_owners = pending.get("owner_identities", {}) if pending else {}
            def readback():
                check_dependencies()
                if capture:
                    probe = recovery.restore(repo / "recovery.json", repo / "recovery/current", roots, apply=False, repo_root=repo, artifacts=artifacts)
                    if probe["changes"] or probe["conflicts"]:
                        raise sync_git.SyncBlocked("selected native recovery changed after capture")
                if checked_agents is not None and _agent_scope_identities(destinations, names) != checked_agents:
                    raise sync_git.SyncBlocked("selected agent content or managed identity changed during sync")
                if names:
                    snapshot = _snapshot(repo)
                    for name, expected in expected_owners.items():
                        if fleet.installed_hash(repo / "skills" / name) != expected:
                            raise sync_git.SyncBlocked("selected canonical owner changed after verification")
                    for _, destination in destinations:
                        if fleet.verify_snapshot(snapshot, destination, names=names):
                            raise sync_git.SyncBlocked("selected agent owners do not match the checked snapshot")

            verification_failures = []
            def verify():
                readback()
                current = sync_git.read_pending(repo) or pending
                with sync_git.prepare_candidate(repo, current["files"], base=current["base"]) as (candidate, tree):
                    if current.get("tree") != tree:
                        raise sync_git.SyncBlocked("publication candidate changed")
                    check_dependencies(candidate)
                    sync_git.assert_publishable(candidate, current["files"])
                    if (candidate / "registry.json").is_file():
                        fleet.render_snapshot(candidate, _snapshot(candidate))
                    try:
                        _run_candidate_checks(candidate, _candidate_commands(candidate, names, current["files"], capture), tree)
                    except CheckFailure as exc:
                        verification_failures.append(exc)
                        raise
                readback()

            def finish(report, state):
                if verification_failures:
                    failure = verification_failures[-1]
                    report["failure"] = _failure_detail(failure, "verify", repo)
                    report["completed_checks"] = failure.completed_checks
                report["verified_owners"] = sorted(names)
                report["installed_verified"] = bool(state.get("installed_verified"))
                report["verified_recovery_artifacts"] = sorted(state.get("recovery_artifacts") or ())
                report["capture_verified"] = bool(state.get("capture_recovery"))
                report["pending_files"] = sorted(sync_git.changed(repo) - set(state["files"]))
                report["verification_scope"] = state["limits"]
                return report

            if pending:
                return finish(sync_git.publish(repo, pending, verify=verify, readback=readback), pending)
            target = sync_git.destination(repo)
            if capture:
                _capture_shared_preflight(repo, artifacts, set(include))
            snapshot = _snapshot(repo) if names else None
            states = {name: _skill_state(repo, snapshot, destinations, name) for name in names}
            if any(state["mode"] == "review-required" for state in states.values()):
                return {"result": "review-required", "reason": "selected owner missing, unadmitted, or conflicting", "owners": sorted(names)}
            selected = {sync_git.safe_path(repo, name) for name in include}
            if bind_owners:
                selected.add("host-deltas.json")
            overrides = {}
            for name, state in states.items():
                owner = repo / "skills" / name
                desired = state["origin"][1] / name if state.get("origin") else owner
                _assert_skill_public_safe(desired, name)
                desired_files = fleet.directory_record(desired)["files"]
                tracked = set(sync_git.git(repo, "ls-files", "-z", "--", f"skills/{name}/").split("\0")) - {""}
                selected.update(tracked)
                selected.update(f"skills/{name}/{path}" for path in desired_files)
                for path in selected & (tracked | {f"skills/{name}/{p}" for p in desired_files}):
                    relative = Path(path).relative_to(Path("skills") / name)
                    desired_file = desired / relative
                    if state.get("origin") or not desired_file.is_file():
                        overrides[path] = desired_file.read_bytes() if desired_file.is_file() else None
                expected_owners[name] = str(state["origin"][2] if state.get("origin") else state["canonical_sha256"])
            if capture:
                selected.add("host-deltas.json")
                selected.add("recovery/current/manifest.json")
                policy = recovery._load_policy(repo / "recovery.json")
                selected.update("recovery/current/" + item["snapshot"] for host, item in recovery._policy_artifacts(policy) if f"{host}:{item['id']}" in set(artifacts))
            if not selected and not names:
                return {"result": "review-required", "reason": "no explicit owner or publication file selected"}
            sync_git.preflight(repo, target, files=selected, scoped=True)
            before_files = sync_git.identities(repo, selected)
            before_agents = _agent_scope_identities(destinations, names)
            files = dict(before_files)
            for path, data in overrides.items():
                files[path] = hashlib.sha256(data).hexdigest() if data is not None else "deleted"
            base_commit = sync_git.git(repo, "rev-parse", "HEAD")
            with sync_git.prepare_candidate(repo, files, base=base_commit, overrides=overrides) as (candidate, candidate_tree):
                check_dependencies(candidate)
                _prepare_candidate_bindings(candidate, names, artifacts, files)
                sync_git.assert_publishable(candidate, files)
                if (candidate / "registry.json").is_file():
                    fleet.render_snapshot(candidate, _snapshot(candidate))
                commands = _candidate_commands(candidate, names, files, capture)
                _run_candidate_checks(candidate, commands, candidate_tree)
                if (sync_git.identities(repo, selected) != before_files
                        or _agent_scope_identities(destinations, names) != before_agents):
                    raise sync_git.SyncBlocked("selected files or agent owners changed during prerequisite checks")
                check_dependencies()
                if names or capture or bind_owners:
                    result = sync(repo, machine=machine, adopt=sorted(names), recovery_roots=recovery_roots,
                                  skill_roots=skill_roots, capture_recovery=capture, recovery_artifacts=artifacts,
                                  check_commands=[], scoped=True, binding_repo=candidate, binding_identities=sorted(bind_owners))
                    if result["result"] not in {"applied", "unchanged"}:
                        return result
                    if result.get("request_id"):
                        selected.add(f"reconciliation/requests/{result['request_id']}.json")
            checked_agents = _agent_scope_identities(destinations, names)
            readback()
            final_files = sync_git.identities(repo, selected)
            with sync_git.prepare_candidate(repo, final_files, base=base_commit) as (candidate, tree):
                check_dependencies(candidate)
                sync_git.assert_publishable(candidate, final_files)
                if (candidate / "registry.json").is_file():
                    fleet.render_snapshot(candidate, _snapshot(candidate))
                _run_candidate_checks(candidate, _candidate_commands(candidate, names, final_files, capture), tree)
            if sync_git.identities(repo, selected) != final_files:
                raise sync_git.SyncBlocked("selected files changed after deployment checks")
            pending = {"schema_version": 1, "scoped": True, "machine": machine,
                       "owners": sorted(names), "destinations": [str(p) for _, p in destinations],
                       "capture_recovery": capture, "recovery_roots": roots, "recovery_artifacts": artifacts,
                       "agent_identities": checked_agents, "owner_identities": expected_owners,
                       "binding_identities": sorted(bind_owners),
                       "agents_verified": False, "installed_verified": bool(names), "dependencies": dependencies,
                       "target": target, "base": base_commit, "message": message,
                       "files": final_files, "tree": tree,
                       "checks": "selected candidate artifact checks" + (", selected installed owner readback" if names else "") +
                                 (", selected native capture readback" if capture else "") + (", selected binding identities" if bind_owners else ""),
                       "limits": "No whole-fleet, current-runtime, or model-behavior parity claim."}
            sync_git.save_pending(repo, pending)
            result = sync_git.publish(repo, pending, verify=verify, readback=readback)
            return finish(result, pending)
    except (OSError, RuntimeError, ValueError, KeyError, subprocess.SubprocessError) as exc:
        return {"result": "incomplete", "failed_step": "scoped-preflight-or-reconcile", "reason": _safe_diagnostic(str(exc), repo),
                "failure": _failure_detail(exc, "scoped-preflight-or-reconcile", repo),
                "completed_checks": exc.completed_checks if isinstance(exc, CheckFailure) else []}


@_measure_completion
def complete_sync(
    repo: str | Path,
    *,
    machine: str = "local-windows",
    adopt: Sequence[str] | None = None,
    recovery_roots: Mapping[str, str | Path] | None = None,
    skill_roots: Sequence[str | Path] | None = None,
    capture_recovery: bool | None = None,
    include: Sequence[str] = (),
    message: str = "chore: reconcile checked agent changes",
    scoped: bool | None = None,
    recovery_artifacts: Sequence[str] | None = None,
) -> dict[str, Any]:
    """One operator operation: reconcile checked owners, commit, push, read back.

    `include` names exact additional files already reviewed by the caller. It
    widens Git publication scope, never admission, ownership, or deployment.
    The low-level `sync` function remains the rollback-tested local mechanism.
    """
    import sync_git

    try:
        intent = _reconciliation_intent(adopt=adopt, include=include, recovery_artifacts=recovery_artifacts,
                                       capture_recovery=capture_recovery, scoped=scoped, recovery_roots=recovery_roots)
    except ValueError as exc:
        return {"result": "review-required", "reason": str(exc)}
    selected_scope = intent["scoped"]
    try:
        existing_pending = sync_git.read_pending(Path(repo).resolve())
    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
        return {"result": "incomplete", "failed_step": "preflight-or-reconcile", "reason": _safe_diagnostic(str(exc), Path(repo)),
                "failure": _failure_detail(exc, "preflight-or-reconcile", Path(repo)),
                "completed_checks": exc.completed_checks if isinstance(exc, CheckFailure) else []}
    if existing_pending and existing_pending.get("scoped"):
        selected_scope = True
    if selected_scope:
        return _scoped_complete_sync(repo, machine=machine, adopt=adopt,
                                     recovery_roots=recovery_roots, skill_roots=skill_roots,
                                     capture_recovery=capture_recovery, include=include, message=message, recovery_artifacts=recovery_artifacts)
    repo = Path(repo).resolve()
    try:
        with sync_git.lock(repo):
            pending = sync_git.read_pending(repo)
            destinations = _destinations(repo, machine, skill_roots)
            capture = (recovery_roots is None or bool(recovery_roots)) if capture_recovery is None else capture_recovery
            resolved_roots = {host: str(Path(path).resolve()) for host, path in
                              (recovery_roots if recovery_roots is not None else recovery._default_roots()).items()}
            checked_agents = pending.get("agent_identities") if pending else None
            commands = [
                [sys.executable, str(repo / "tools/validate.py")],
                [sys.executable, str(repo / "tools/public_check.py")],
                [sys.executable, str(repo / "tools/instruction_profile.py")],
            ]

            def check_external_owners():
                current = capability_intake.fleet_findings(repo, machine=machine, skill_roots=skill_roots)
                if any(item.get("source_action") == "unmanaged" for item in current):
                    raise RuntimeError("unmanaged or external-owner content requires review")

            def readback():
                check_external_owners()
                if checked_agents is not None and _agent_identities(destinations) != checked_agents:
                    raise RuntimeError("agent content changed during sync; re-review required")
                snapshot = _snapshot(repo)
                manifest = fleet.load_manifest(snapshot)
                expected = {name: fleet.directory_record(repo / "skills" / name)
                            for name, entry in fleet.registry(repo).items() if entry.get("status") == "admitted"}
                if manifest["skills"] != expected:
                    raise RuntimeError("rendered skills differ from their current source")
                for _, destination in destinations:
                    if fleet.verify_snapshot(snapshot, destination):
                        raise RuntimeError("agent skills do not match the checked source")
                if capture:
                    recovery.verify_snapshot(repo / "recovery.json", repo / "recovery/current")
                    report = recovery.restore(repo / "recovery.json", repo / "recovery/current",
                                              resolved_roots,
                                              apply=False, repo_root=repo)
                    if report["changes"] or report["conflicts"]:
                        raise RuntimeError("agent settings differ from their saved recovery files")

            def verify():
                readback()
                verified_commands = commands if capture else [*commands[:-1], [*commands[-1], "--artifact-only"]]
                audit_command = [sys.executable, str(repo / "tools/audit.py"), "check"]
                if not capture:
                    audit_command.append("--structural")
                _run_checks(repo, [*verified_commands, audit_command])
                readback()

            evidence_paths = [f"evals/results/{name}-local-windows.json" for name in
                              ("fleet-discovery", "unified-reconciliation")]
            def publish_broad(state):
                report = sync_git.publish(repo, state, verify=verify, readback=readback)
                if not capture:
                    report["deferred_evidence"] = [name for name in evidence_paths if (repo / name).is_file()]
                return report

            if pending:
                if pending.get("recovery_roots") != resolved_roots:
                    raise sync_git.SyncBlocked("pending sync belongs to different settings directories")
                if pending["machine"] != machine or pending["destinations"] != [str(p) for _, p in destinations]:
                    raise sync_git.SyncBlocked("pending sync belongs to different agent destinations")
                capture = pending["capture_recovery"]
                return publish_broad(pending)

            target = sync_git.destination(repo)
            sync_git.preflight(repo, target)
            snapshot = _snapshot(repo)
            entries = fleet.registry(repo)
            names = set(adopt or ())
            states = {}
            for name, entry in entries.items():
                if entry.get("status") == "admitted" or name in names:
                    state = _skill_state(repo, snapshot, destinations, name)
                    states[name] = state
                    if state["mode"] != "unchanged":
                        names.add(name)
            if names - set(states) or any(states[name]["mode"] == "review-required" for name in names):
                return {"result": "review-required", "reason": "owner missing, unadmitted, or conflicting",
                        "owners": sorted(names)}
            findings = plan(repo, machine=machine, recovery_roots=recovery_roots, skill_roots=skill_roots,
                            capture_recovery=capture, scoped=False)["findings"]
            blocked = []
            for item in findings:
                if nonblocking_observation_kind(item) is not None:
                    continue  # Visible and untouched; never admission or proposal approval.
                if item["surface"] == "fleet" and item["target"] in names and item.get("source_action") not in {"remove", "forget"}:
                    continue  # _skill_state has already proved one unambiguous admitted owner.
                if item["surface"] == "recovery" and capture and item.get("source_action") != "conflict":
                    continue  # Native settings stay native; only allowlisted recovery data is captured.
                blocked.append(item)
            if blocked:
                return {"result": "review-required", "findings": blocked}
            recovery_owned = _recovery_owned_paths(repo) if capture else set()
            agents_before = _agent_identities(destinations)
            before = sync_git.changed(repo)
            selected = {sync_git.safe_path(repo, name) for name in include}
            selected.update(name for name in before if any(name.startswith(f"skills/{owner}/") for owner in names))
            if capture:
                selected.update(before & (recovery_owned | {"host-deltas.json"}))
            if before - selected:
                return {"result": "review-required", "reason": "additional repository files need review before publication",
                        "files": sorted(before - selected)}
            approved = sync_git.identities(repo, selected)
            sync_git.assert_publishable(repo, selected)
            _run_checks(repo, [*commands[:-1], [*commands[-1], "--artifact-only"],
                               [sys.executable, str(repo / "tools/audit.py"), "check", "--structural"]])
            if (_agent_identities(destinations) != agents_before
                    or sync_git.identities(repo, selected) != approved or sync_git.changed(repo) != before):
                raise sync_git.SyncBlocked("files changed during prerequisite checks")
            check_external_owners()  # Revalidate pins before writes, including plan-to-baseline races.
            if names or capture:
                result = sync(repo, machine=machine, adopt=sorted(names), recovery_roots=recovery_roots,
                              skill_roots=skill_roots, capture_recovery=capture)
                if result["result"] not in {"applied", "unchanged"}:
                    return result
                if result.get("request_id"):
                    selected.add(f"reconciliation/requests/{result['request_id']}.json")
                if result.get("binding_refresh"):
                    selected.add("host-deltas.json")
            checked_agents = _agent_identities(destinations)
            for label, prior in agents_before.items():
                current = checked_agents[label]
                if any(prior.get(name) != current.get(name) for name in (prior.keys() | current.keys())
                       if name not in names and name != fleet.STATE_FILE):
                    raise sync_git.SyncBlocked("unselected agent content changed during reconciliation")
            selected.update(name for name in sync_git.changed(repo) if any(name.startswith(f"skills/{owner}/") for owner in names))
            if capture:
                selected.update(sync_git.changed(repo) & (_recovery_owned_paths(repo) | {"host-deltas.json"}))
            if capture and machine == "local-windows" and all((repo / name).is_file() for name in evidence_paths):
                import audit
                selected.update(audit.refresh_current_evidence(repo))
            if sync_git.changed(repo) - selected:
                raise sync_git.SyncBlocked("unreviewed changes appeared during reconciliation")
            pending = {"schema_version": 1, "machine": machine,
                       "destinations": [str(p) for _, p in destinations], "capture_recovery": capture,
                       "recovery_roots": resolved_roots, "agent_identities": checked_agents,
                       "target": target, "base": sync_git.git(repo, "rev-parse", "HEAD"),
                       "message": message, "files": sync_git.identities(repo, selected)}
            sync_git.save_pending(repo, pending)
            return publish_broad(pending)
    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
        return {"result": "incomplete", "failed_step": "preflight-or-reconcile", "reason": _safe_diagnostic(str(exc), repo),
                "failure": _failure_detail(exc, "preflight-or-reconcile", repo),
                "completed_checks": exc.completed_checks if isinstance(exc, CheckFailure) else []}


@_measure_completion
def complete_defaults_sync(repo, *, hosts=None, **options):
    """Reconcile approved native selectors, their observations, and publication."""
    import sync_git
    import runtime_defaults
    import instruction_profile

    repo = Path(repo).resolve()
    if options.get("capture_recovery") is False or options.get("scoped") is False:
        return {"result": "review-required", "reason": "default reconciliation requires selected native capture; it conflicts with no-capture or full scope"}
    prepared = None
    written = []
    baseline_commit = None
    completion_failure = None
    try:
        with sync_git.lock(repo):
            # A failed push resumes its exact candidate, without creating a new observation.
            pending = sync_git.read_pending(repo)
            if pending:
                preferences = runtime_defaults.load_preferences(repo)
                chosen = runtime_defaults.selected_hosts(repo, hosts)
                expected_artifacts = {host + ":settings" for host in chosen if host in preferences["runtime_defaults"]}
                expected_artifacts.update(options.get("recovery_artifacts") or ())
                if not pending.get("scoped") or set(pending.get("recovery_artifacts") or ()) != expected_artifacts:
                    raise sync_git.SyncBlocked("pending sync belongs to a different default target selection")
                options.update(capture_recovery=True, scoped=True, recovery_artifacts=sorted(expected_artifacts))
                return complete_sync(repo, **options)
            prepared = runtime_defaults.prepare_defaults(repo, roots=options.get("recovery_roots"), hosts=hosts)
            if not prepared.entries:
                return {"result": "review-required", "reason": "selected hosts have no approved default mapping", "defaults": prepared.report}
            roots = options.get("recovery_roots")
            roots = recovery._default_roots() if roots is None else roots
            settings = {entry["host"] + ":settings" for entry in prepared.entries}
            artifacts = sorted(settings | set(options.get("recovery_artifacts") or ()))
            included = set(options.get("include", ()))
            policy = recovery._load_policy(repo / "recovery.json")
            recovery._select_artifacts(policy, artifacts)
            profile_path = instruction_profile.current_profile(repo)
            profile_name = profile_path.relative_to(repo).as_posix()
            if profile_name not in included:
                def outside_profile(value):
                    value = json.loads(json.dumps(value))
                    value.pop("claim", None)
                    if "codex:settings" in settings:
                        value.pop("target", None)
                    for host in {item.split(":", 1)[0] for item in settings}:
                        for field in ("model", "provider", "reasoning", "observation"):
                            value["hosts"][host].pop(field, None)
                    return value
                baseline_profile = json.loads(sync_git.git(repo, "show", "HEAD:" + profile_name))
                if outside_profile(baseline_profile) != outside_profile(json.loads(profile_path.read_text(encoding="utf-8"))):
                    raise sync_git.SyncBlocked("unselected observed profile fields differ; include the reviewed profile")
            paths = [repo / "recovery/current", repo / "host-deltas.json", profile_path,
                     *(entry["path"] for entry in prepared.entries),
                     *(Path(roots[host]) for host in {item.split(":", 1)[0] for item in artifacts})]
            with sync_git.path_locks(paths), tempfile.TemporaryDirectory(prefix="agent-sync-defaults-stage-") as temporary:
                policy_rows = {f"{host}:{item['id']}": item for host, item in recovery._policy_artifacts(policy)}
                # Ordinary editors do not honor our locks. Freeze every implicit
                # output before reading its baseline or preparing candidate checks.
                derived = {"recovery/current/manifest.json", "host-deltas.json", profile_name}
                derived.update("recovery/current/" + policy_rows[item]["snapshot"] for item in artifacts)
                expected = {name: fleet.path_identity(repo / name) for name in derived}
                _capture_shared_preflight(repo, artifacts, included)
                if profile_name not in included and outside_profile(baseline_profile) != outside_profile(json.loads(profile_path.read_text(encoding="utf-8"))):
                    raise sync_git.SyncBlocked("unselected observed profile fields differ; include the reviewed profile")
                stage = Path(temporary) / "snapshot"
                shutil.copytree(repo / "recovery/current", stage)
                # Capture current allowlisted data first; only approved selector keys are projected.
                manifest = recovery.snapshot(repo / "recovery.json", stage, roots, repo_root=repo, artifacts=artifacts)
                records = {f"{row['host']}:{row['id']}": row for row in manifest["artifacts"]}
                for entry in prepared.entries:
                    identity = entry["host"] + ":settings"
                    item = policy_rows[identity]
                    keys = runtime_defaults.ADAPTERS[entry["host"]][2]
                    if item["kind"] != "config" or not set(keys.values()).issubset(item["include"]):
                        raise RuntimeError("default selector is outside the selected recovery allowlist")
                    target = stage / item["snapshot"]
                    value = json.loads(target.read_text(encoding="utf-8"))
                    for field, dotted in keys.items():
                        recovery._set_dotted(value, dotted, entry["desired_fields"][field])
                    fleet.atomic_json(target, value)
                    records[identity]["sha256"] = fleet.sha256_file(target)
                    records[identity]["bytes"] = target.stat().st_size
                fleet.atomic_json(stage / "manifest.json", manifest)
                recovery.verify_snapshot(repo / "recovery.json", stage)
                targets = {"recovery/current/manifest.json": (stage / "manifest.json").read_bytes()}
                targets.update({"recovery/current/" + policy_rows[item]["snapshot"]:
                                (stage / policy_rows[item]["snapshot"]).read_bytes() for item in artifacts})
                # Freeze the caller's reviewed source selection before touching native configs.
                selected = {sync_git.safe_path(repo, name) for name in included}
                for name in _selected_owners(repo, options.get("adopt") or ()):
                    selected.update(sync_git.git(repo, "ls-files", "-z", "--", f"skills/{name}/").split("\0"))
                    selected.discard("")
                    selected.update(f"skills/{name}/{path}" for path in fleet.directory_record(repo / "skills" / name)["files"])
                initial = sync_git.identities(repo, selected)
                baseline_commit = sync_git.git(repo, "rev-parse", "HEAD")
                sync_git.preflight(repo, sync_git.destination(repo), files=selected, scoped=True)
                with sync_git.prepare_candidate(repo, initial, base=baseline_commit) as (candidate, tree):
                    if _scope_dependencies(candidate, options.get("machine", "local-windows"), set(options.get("adopt") or ()), True, artifacts) != _scope_dependencies(repo, options.get("machine", "local-windows"), set(options.get("adopt") or ()), True, artifacts):
                        raise sync_git.SyncBlocked("default reconciliation depends on unpublished execution changes; include the reviewed dependency")
                    _prepare_candidate_bindings(candidate, set(options.get("adopt") or ()), artifacts, initial)
                    _run_candidate_checks(candidate, _candidate_commands(candidate, set(options.get("adopt") or ()), initial, True), tree)
                if sync_git.identities(repo, selected) != initial:
                    raise sync_git.SyncBlocked("selected files changed during default prerequisite checks")
                if any(fleet.path_identity(repo / name) != identity for name, identity in expected.items()):
                    raise sync_git.SyncBlocked("selected derived metadata changed during default prerequisite checks")
                receipt = runtime_defaults.apply_defaults(prepared)
                # Bind observations to the actual allowlisted readback, using the
                # capture serializer that subsequent scoped sync will repeat.
                recovery.snapshot(repo / "recovery.json", stage, roots,
                                  repo_root=repo, artifacts=artifacts)
                targets["recovery/current/manifest.json"] = (stage / "manifest.json").read_bytes()
                targets.update({"recovery/current/" + policy_rows[item]["snapshot"]:
                                (stage / policy_rows[item]["snapshot"]).read_bytes() for item in artifacts})
                observation = instruction_profile.refresh_observed_profile(repo, receipt, write=False, snapshot=stage)
                targets[observation["path"]] = _json_bytes(observation["value"])
                if recovery._file_identity(profile_path) != observation["expected_identity"]:
                    raise sync_git.SyncBlocked("observed profile changed during preparation")
                # Bind projected artifacts against the same isolated selected source, never dirty neighbors.
                prospective = {**initial, **{name: hashlib.sha256(data).hexdigest() for name, data in targets.items()}}
                with sync_git.prepare_candidate(repo, prospective, base=baseline_commit, overrides=targets) as (candidate, _):
                    candidate_bindings = host_deltas.prepare_bindings(candidate / "host-deltas.json", candidate,
                        source_identities=sorted("recovery-artifact:" + item for item in artifacts))
                    targets["host-deltas.json"] = host_deltas._canonical_json(candidate_bindings["manifest"])
                for name, data in targets.items():
                    recovery._assert_public_safe(data, label=name)
                    target = repo / name
                    if fleet.path_identity(target) != expected[name]:
                        raise sync_git.SyncBlocked("selected derived metadata changed before default installation")
                    original = target.read_bytes() if target.is_file() else None
                    journal = [target, original, data, None]
                    written.append(journal)
                    recovery._atomic_write(target, data)
                    journal[3] = fleet.path_identity(target)
                options.update(capture_recovery=True, scoped=True, recovery_artifacts=artifacts,
                               include=sorted(included | set(targets)))
                report = complete_sync(repo, **options)
                report["defaults"] = receipt
                if getattr(prepared, "private_backup", None) is not None:
                    report["private_defaults_backup"] = str(prepared.private_backup)
                if report.get("result") != "synced" and not sync_git.read_pending(repo) and sync_git.git(repo, "rev-parse", "HEAD") == baseline_commit:
                    completion_failure = report
                    raise RuntimeError("selected default completion failed: " + report.get("reason", report.get("result", "unknown")))
                return report
    except (OSError, RuntimeError, ValueError, KeyError, subprocess.SubprocessError) as exc:
        conflicts = []
        backups = {}
        with sync_git.path_locks([row[0] for row in written]):
            for target, original, desired, expected in reversed(written):
                try:
                    current = target.read_bytes() if target.is_file() else None
                    if expected is None and current == original:
                        continue
                    if current != desired or (expected is not None and fleet.path_identity(target) != expected):
                        raise RuntimeError("concurrent derived metadata change")
                    if original is not None:
                        recovery._atomic_write(target, original)
                    elif target.is_file():
                        target.unlink()
                except (OSError, RuntimeError):
                    conflicts.append(target.relative_to(repo).as_posix())
                    if original is not None:
                        backup = Path(tempfile.mkdtemp(prefix="agent-sync-defaults-metadata-conflict-"))
                        (backup / "original").write_bytes(original)
                        backups[target.relative_to(repo).as_posix()] = str(backup)
        rollback = runtime_defaults.rollback_defaults(prepared) if prepared and prepared.applied else None
        return {"result": "incomplete", "failed_step": "default-reconciliation", "failure": (completion_failure or {}).get("failure", _failure_detail(exc, "default-reconciliation", repo)),
                "reason": _safe_diagnostic(str(exc), repo), "metadata_conflicts": conflicts,
                "private_metadata_backups": backups, "defaults_rollback": rollback}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("review", "plan", "sync"))
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--machine", default="local-windows")
    parser.add_argument("--adopt", action="append", default=[])
    capture_options = parser.add_mutually_exclusive_group()
    capture_options.add_argument("--capture-recovery", action="store_true", default=None,
                        help="capture reviewed allowlisted settings (included by default in sync)")
    capture_options.add_argument("--no-capture-recovery", dest="capture_recovery", action="store_false",
                        help="scope this operation to skills/repository files; do not capture native settings")
    parser.add_argument("--capture-artifact", action="append", default=None, metavar="HOST:ID", help="capture only an exact existing recovery artifact")
    parser.add_argument("--include", action="append", default=[], metavar="FILE",
                        help="exact additional repository file already reviewed for commit; does not authorize deployment")
    parser.add_argument("--message", default="chore: reconcile checked agent changes")
    parser.add_argument("--full", action="store_true", help="explicitly retain broad reconciliation when owner/file selectors are present")
    parser.add_argument("--root", action="append", default=[], metavar="HOST=PATH")
    parser.add_argument("--skill-root", action="append", default=[], type=Path)
    parser.add_argument("--reconcile-defaults", action="store_true", help="apply supported approved defaults after scoped checks and capture their observations")
    parser.add_argument("--maintenance-host", action="append", choices=("codex", "hermes", "omp"), help="select native default targets; default comes from core.md")
    parser.add_argument("--target", help="repository-relative authoring target; required for review")
    parser.add_argument("--candidate", type=Path, help="staged candidate source; never executed")
    parser.add_argument("--baseline", type=Path, help="saved baseline source")
    parser.add_argument("--host", action="append", default=[], help="narrow suggested model cells")
    parser.add_argument("--model", action="append", default=[], help="add an exact session-selected model")
    parser.add_argument("--evidence", action="append", default=[], type=Path)
    parser.add_argument("--suite", action="append", default=[], type=Path)
    parser.add_argument("--reference-skill", action="append", default=[], type=Path)
    args = parser.parse_args(argv)
    authoring = bool(args.target or args.candidate or args.baseline or args.host or args.model or
                     args.evidence or args.suite or args.reference_skill)
    if authoring and (args.action == "sync" or not args.target):
        parser.error("authoring options require --target and apply only to review or plan")
    if args.action == "review" and not args.target:
        parser.error("review requires --target")
    if (args.reconcile_defaults or args.maintenance_host) and args.action == "review":
        parser.error("default reconciliation applies only to plan or sync")
    options = dict(target=args.target, candidate=args.candidate, baseline=args.baseline,
                   hosts=args.host, models=args.model, reports=args.evidence, suites=args.suite,
                   reference_skills=args.reference_skill) if args.target else None
    roots = recovery._parse_roots(args.root)
    settings_hosts = [value.split(":", 1)[0] for value in (args.capture_artifact or ())
                      if value in {"codex:settings", "hermes:settings"}]
    default_hosts = args.maintenance_host or (settings_hosts if settings_hosts else None)
    use_defaults = args.reconcile_defaults or bool(args.maintenance_host) or bool(settings_hosts)
    if args.action != "review":
        try:
            _reconciliation_intent(adopt=args.adopt, include=args.include, recovery_artifacts=args.capture_artifact,
                                   capture_recovery=args.capture_recovery, scoped=False if args.full else None,
                                   recovery_roots=roots)
            if use_defaults and (args.capture_recovery is False or args.full):
                raise ValueError("default reconciliation requires scoped recovery capture")
        except ValueError as exc:
            parser.error(str(exc))
    if args.action == "review":
        import change_review
        report = change_review.review(args.repo, **options)
    elif args.action == "plan":
        artifacts, capture, selected_scope = args.capture_artifact, args.capture_recovery, False if args.full else None
        defaults_report = None
        if use_defaults:
            import runtime_defaults
            preferences = runtime_defaults.load_preferences(args.repo)
            chosen = runtime_defaults.selected_hosts(args.repo, default_hosts)
            artifacts = sorted(set(artifacts or ()) | {
                host + ":settings" for host in chosen if host in preferences["runtime_defaults"]})
            capture, selected_scope = bool(artifacts), True
            defaults_report = runtime_defaults.plan_defaults(args.repo, roots=roots, hosts=default_hosts)
        report = plan(args.repo, machine=args.machine, recovery_roots=roots,
                      skill_roots=args.skill_root or None, live=True, review_options=options,
                      adopt=args.adopt, include=args.include, recovery_artifacts=artifacts or None,
                      capture_recovery=capture, scoped=selected_scope)
        if defaults_report is not None:
            report["defaults"] = defaults_report
    else:
        operation = complete_defaults_sync if use_defaults else complete_sync
        extra = {"hosts": default_hosts} if use_defaults else {}
        report = operation(args.repo, machine=args.machine, adopt=args.adopt, recovery_roots=roots,
                               skill_roots=args.skill_root or None, capture_recovery=args.capture_recovery,
                               include=args.include, message=args.message, scoped=False if args.full else None, recovery_artifacts=args.capture_artifact, **extra)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if args.action in {"review", "plan"} or report.get("result") == "synced" else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, KeyError, ValueError, RuntimeError, json.JSONDecodeError, jsonschema.ValidationError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
