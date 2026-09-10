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
from pathlib import Path
from typing import Any, Mapping, Sequence

import jsonschema

try:
    import capability_intake
    import fleet
    import host_deltas
    import recovery
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import capability_intake  # type: ignore
    import fleet  # type: ignore
    import host_deltas  # type: ignore
    import recovery  # type: ignore

SURFACES = ["recovery", "fleet", "instructions", "governance", "host-deltas"]
LIVE_MUTATION_ACTIONS = {"add", "adopt", "materialize", "repair", "update", "remove"}


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


def plan(
    repo: str | Path,
    *,
    machine: str = "local-windows",
    recovery_roots: Mapping[str, str | Path] | None = None,
    skill_roots: Sequence[str | Path] | None = None,
    live: bool = False,
) -> dict[str, Any]:
    """Aggregate bounded metadata-only findings across every governed surface."""

    repo = Path(repo).resolve()
    findings: list[dict[str, Any]] = []
    if recovery_roots is None or recovery_roots:
        scan = capability_intake.scan(
            repo,
            machine=machine,
            recovery_roots=recovery_roots,
            skill_roots=skill_roots,
        )
        findings.extend(_with_id(item) for item in scan["findings"])
    else:
        snapshot = _snapshot(repo)
        registry = fleet.registry(repo)
        for destination_id, destination in _destinations(repo, machine, skill_roots):
            for action in fleet.plan_snapshot(snapshot, destination):
                if action["action"] == "unchanged":
                    continue
                findings.append(_with_id(capability_intake.classify_fleet_action(action, registry.get(action["name"]), destination_id=destination_id)))

    findings.extend(_instruction_findings(repo))
    findings.extend(_governance_findings(repo))
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
    return {
        "schema_version": 1,
        "mode": "live-readback" if live else "read-only-plan",
        "machine": machine,
        "surfaces": list(SURFACES),
        "mutation_performed": False,
        "findings": ordered,
        "summary": {"total": len(ordered)},
    }


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


def _run_checks(repo: Path, commands: Sequence[Sequence[str] | str]) -> list[str]:
    labels: list[str] = []
    for command in commands:
        argv = [command] if isinstance(command, str) else list(command)
        completed = subprocess.run(argv, cwd=repo, capture_output=True, text=True, check=False)
        label = " ".join(
            Path(part).name if index == 0 or Path(part).is_absolute() else part
            for index, part in enumerate(argv)
        )
        if completed.returncode != 0:
            raise RuntimeError(f"reconciliation check failed: {label}")
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


def sync(
    repo: str | Path,
    *,
    machine: str = "local-windows",
    adopt: Sequence[str] | None = None,
    recovery_roots: Mapping[str, str | Path] | None = None,
    skill_roots: Sequence[str | Path] | None = None,
    check_commands: Sequence[Sequence[str] | str] | None = None,
    capture_recovery: bool = False,
) -> dict[str, Any]:
    """Reconcile selected owners and optionally capture allowlisted host state."""

    repo = Path(repo).resolve()
    names = sorted(set(adopt or []))
    if not names and not capture_recovery:
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
            host_deltas.load_manifest(host_delta_path, repo)
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
    fleet_snapshot = _snapshot(repo)
    destinations = _destinations(repo, machine, skill_roots)
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
            recovery.snapshot(
                repo / "recovery.json",
                prepared_recovery,
                resolved_recovery_roots,
                repo_root=repo,
            )
            recovery_before = _tree_hash(repo / "recovery" / "current")
            recovery_after = _tree_hash(prepared_recovery)

        owners = names + (["recovery-state", "host-deltas"] if capture_recovery else [])
        desired = [
            str(state["origin"][2] if state.get("origin") else state["canonical_sha256"])
            for state in states
        ] + ([str(recovery_after)] if capture_recovery else [])
        request_id = _request_id(machine, owners, desired)
        request_path = repo / "reconciliation" / "requests" / f"{request_id}.json"
        no_skill_change = all(state["mode"] == "unchanged" for state in states)
        no_recovery_change = not capture_recovery or recovery_before == recovery_after
        if request_path.is_file() and no_skill_change and no_recovery_change:
            return {"schema_version": 1, "result": "unchanged", "mutation_performed": False, "request_id": request_id, "owners": owners}

        if capture_recovery and names:
            operation = "mixed-safe-reconciliation"
        elif capture_recovery:
            operation = "capture-recovery"
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
        snapshot_existed = _copy_optional(fleet_snapshot, backup / "snapshot")
        recovery_existed = _copy_optional(repo / "recovery" / "current", backup / "recovery")
        host_delta_existed = _copy_optional(host_delta_path, backup / "host-deltas.json")
        host_delta_before = fleet.sha256_file(host_delta_path) if host_delta_existed else None
        host_delta_after = host_delta_before
        request_existed = _copy_optional(request_path, backup / "request.json")
        for state in states:
            target = repo / "skills" / state["name"]
            canonical_existed[state["name"]] = _copy_optional(target, backup / "canonical" / state["name"])
        for label, destination in destinations:
            key = _backup_key(label)
            _copy_optional(destination / fleet.STATE_FILE, backup / "live" / key / fleet.STATE_FILE)
        committed = False
        checks: list[str] = []
        failed_phase = "preflight"
        failure: Exception | None = None
        try:
            failed_phase = "canonicalize"
            for state in states:
                if state["mode"] == "adopt-live":
                    _replace_tree(state["origin"][1] / state["name"], repo / "skills" / state["name"])
            if prepared_recovery is not None:
                _replace_tree(prepared_recovery, repo / "recovery" / "current")
                host_deltas.refresh_bindings(
                    host_delta_path,
                    repo,
                    source_prefixes=("recovery-artifact:",),
                )
                host_delta_after = fleet.sha256_file(host_delta_path)

            failed_phase = "render"
            if states:
                fleet.render_snapshot(repo, fleet_snapshot)
                planned = fleet.preflight_destinations(
                    fleet_snapshot, [path for _, path in destinations]
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
                fleet.apply_destinations(fleet_snapshot, [path for _, path in destinations])

            failed_phase = "verify"
            if states:
                for _, destination in destinations:
                    if fleet.verify_snapshot(fleet_snapshot, destination):
                        raise RuntimeError("fleet postflight verification failed")
            if capture_recovery:
                recovery.verify_snapshot(repo / "recovery.json", repo / "recovery" / "current")
                postflight = recovery.restore(
                    repo / "recovery.json",
                    repo / "recovery" / "current",
                    resolved_recovery_roots,
                    apply=False,
                    repo_root=repo,
                )
                if postflight["changes"] or postflight["conflicts"]:
                    raise RuntimeError("recovery postflight verification failed")
                host_deltas.load_manifest(host_delta_path, repo)

            failed_phase = "receipt"
            if capture_recovery:
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
                    {"name": "canonicalize", "status": "completed" if any(state["mode"] == "adopt-live" for state in states) or capture_recovery else "skipped"},
                    {"name": "render", "status": "completed" if states else "skipped"},
                    {"name": "validate", "status": "completed"},
                    {"name": "deploy", "status": "completed" if states else "skipped"},
                    {"name": "verify", "status": "completed"},
                    {"name": "receipt", "status": "completed"},
                ],
                "checks": checks,
                "result": "applied",
            }
            _write_request(repo, request)
            committed = True
        except Exception as exc:
            failure = exc
        finally:
            if not committed:
                for state in states:
                    _restore_optional(backup / "canonical" / state["name"], repo / "skills" / state["name"], canonical_existed[state["name"]])
                _restore_optional(backup / "snapshot", fleet_snapshot, snapshot_existed)
                _restore_optional(backup / "recovery", repo / "recovery" / "current", recovery_existed)
                _restore_optional(backup / "host-deltas.json", host_delta_path, host_delta_existed)
                destination_by_label = dict(destinations)
                for (label, name), existed in live_existed.items():
                    destination = destination_by_label[label]
                    key = _backup_key(label)
                    _restore_optional(
                        backup / "live" / key / name,
                        destination / name,
                        existed,
                    )
                for label, destination in destinations:
                    key = _backup_key(label)
                    state_backup = backup / "live" / key / fleet.STATE_FILE
                    _restore_optional(state_backup, destination / fleet.STATE_FILE, state_backup.exists())
                _restore_optional(backup / "request.json", request_path, request_existed)
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
            report["reason"] = "transactional reconciliation failed and was rolled back"
            return report
    return {"schema_version": 1, "result": "applied", "mutation_performed": True, "request_id": request_id, "owners": owners}


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
) -> dict[str, Any]:
    """One operator operation: reconcile checked owners, commit, push, read back.

    `include` names exact additional files already reviewed by the caller. It
    widens Git publication scope, never admission, ownership, or deployment.
    The low-level `sync` function remains the rollback-tested local mechanism.
    """
    import sync_git

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

            def readback():
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
                _run_checks(repo, [*commands, [sys.executable, str(repo / "tools/audit.py"), "check"]])
                readback()

            if pending:
                if pending.get("recovery_roots") != resolved_roots:
                    raise sync_git.SyncBlocked("pending sync belongs to different settings directories")
                if pending["machine"] != machine or pending["destinations"] != [str(p) for _, p in destinations]:
                    raise sync_git.SyncBlocked("pending sync belongs to different agent destinations")
                capture = pending["capture_recovery"]
                return sync_git.publish(repo, pending, verify=verify, readback=readback)

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
            findings = plan(repo, machine=machine, recovery_roots=recovery_roots, skill_roots=skill_roots)["findings"]
            blocked = []
            for item in findings:
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
            if names or capture:
                result = sync(repo, machine=machine, adopt=sorted(names), recovery_roots=recovery_roots,
                              skill_roots=skill_roots, capture_recovery=capture)
                if result["result"] not in {"applied", "unchanged"}:
                    return result
                if result.get("request_id"):
                    selected.add(f"reconciliation/requests/{result['request_id']}.json")
            checked_agents = _agent_identities(destinations)
            for label, prior in agents_before.items():
                current = checked_agents[label]
                if any(prior.get(name) != current.get(name) for name in (prior.keys() | current.keys())
                       if name not in names and name != fleet.STATE_FILE):
                    raise sync_git.SyncBlocked("unselected agent content changed during reconciliation")
            selected.update(name for name in sync_git.changed(repo) if any(name.startswith(f"skills/{owner}/") for owner in names))
            if capture:
                selected.update(sync_git.changed(repo) & (_recovery_owned_paths(repo) | {"host-deltas.json"}))
            evidence_paths = [f"evals/results/{name}-local-windows.json" for name in
                              ("fleet-discovery", "unified-reconciliation")]
            if machine == "local-windows" and all((repo / name).is_file() for name in evidence_paths):
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
            return sync_git.publish(repo, pending, verify=verify, readback=readback)
    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
        return {"result": "incomplete", "failed_step": "preflight-or-reconcile", "reason": str(exc)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("plan", "sync"))
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--machine", default="local-windows")
    parser.add_argument("--adopt", action="append", default=[])
    parser.add_argument("--capture-recovery", action="store_true", default=None,
                        help="capture reviewed allowlisted settings (included by default in sync)")
    parser.add_argument("--no-capture-recovery", dest="capture_recovery", action="store_false",
                        help="scope this operation to skills/repository files; do not capture native settings")
    parser.add_argument("--include", action="append", default=[], metavar="FILE",
                        help="exact additional repository file already reviewed for commit; does not authorize deployment")
    parser.add_argument("--message", default="chore: reconcile checked agent changes")
    parser.add_argument("--root", action="append", default=[], metavar="HOST=PATH")
    parser.add_argument("--skill-root", action="append", default=[], type=Path)
    args = parser.parse_args(argv)
    roots = recovery._parse_roots(args.root)
    if args.action == "plan":
        report = plan(args.repo, machine=args.machine, recovery_roots=roots, skill_roots=args.skill_root or None, live=True)
    else:
        report = complete_sync(args.repo, machine=args.machine, adopt=args.adopt, recovery_roots=roots,
                               skill_roots=args.skill_root or None, capture_recovery=args.capture_recovery,
                               include=args.include, message=args.message)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if args.action == "plan" or report.get("result") == "synced" else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, KeyError, ValueError, RuntimeError, json.JSONDecodeError, jsonschema.ValidationError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
