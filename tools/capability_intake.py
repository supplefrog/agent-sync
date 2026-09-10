#!/usr/bin/env python
"""Classify Agent Sync recovery and fleet drift without mutating live state."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    import fleet
    import recovery
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import fleet  # type: ignore
    import recovery  # type: ignore

SAFE_EXISTING_OWNER_ACTIONS = {
    "add",
    "adopt",
    "materialize",
    "repair",
    "reconcile",
    "update",
}
RETIREMENT_ACTIONS = {"forget", "remove"}
INSTRUCTION_FILENAMES = {"agents.md", "soul.md"}


def _registry_status(registry_entry: Mapping[str, Any] | None) -> str:
    if registry_entry is None:
        return "unregistered"
    status = registry_entry.get("status")
    return str(status) if isinstance(status, str) and status else "unknown"


def classify_fleet_action(
    action_item: Mapping[str, Any],
    registry_entry: Mapping[str, Any] | None,
    *,
    destination_id: str,
    checked: bool = False,
    cross_host_change: bool = False,
    safety_sensitive: bool = False,
    ambiguous: bool = False,
) -> dict[str, Any]:
    """Classify one fleet plan action under the bounded autonomy policy.

    ``checked`` means deterministic prerequisite checks have already passed. It
    does not override staged ownership, conflicts, retirements, or risk flags.
    """

    name = str(action_item.get("name", ""))
    action = str(action_item.get("action", "unknown"))
    status = _registry_status(registry_entry)
    admitted = status == "admitted"
    risk_flagged = cross_host_change or safety_sensitive or ambiguous

    finding: dict[str, Any] = {
        "surface": "fleet",
        "target": name,
        "destination": destination_id,
        "source_action": action,
        "registry_status": status,
        "owner": f"skills/{name}" if registry_entry is not None and name else "unresolved",
        "route": "capability-curator",
        "change_class": "unmanaged-capability",
        "disposition": "stage-for-review",
        "eligible_after_checks": False,
        "auto_apply_eligible": False,
    }

    if action == "unchanged":
        finding.update(
            change_class="no-change",
            route="none",
            disposition="no-action",
        )
        return finding

    if action == "reconcile-state":
        finding.update(
            change_class="fleet-state-drift",
            owner="fleet-state",
            route="cross-agent-surface-engineering",
            disposition="review-required",
        )
        return finding

    if action == "conflict":
        finding.update(
            change_class=("managed-skill-conflict" if admitted else "unmanaged-collision"),
            route=("cross-agent-surface-engineering" if admitted else "capability-curator"),
            disposition="review-required" if admitted else "stage-for-review",
        )
        return finding

    if action in RETIREMENT_ACTIONS:
        finding.update(
            change_class="owner-retirement",
            route="cross-agent-surface-engineering",
            disposition="review-required",
        )
        return finding

    if admitted and action in SAFE_EXISTING_OWNER_ACTIONS:
        eligible = not risk_flagged
        finding.update(
            change_class="existing-owner-maintenance",
            route="cross-agent-surface-engineering",
            disposition=(
                "auto-apply-eligible"
                if eligible and checked
                else "checks-required"
                if eligible
                else "review-required"
            ),
            eligible_after_checks=eligible,
            auto_apply_eligible=eligible and checked,
        )
        return finding

    if registry_entry is not None:
        finding["change_class"] = "staged-capability-change"
    return finding


def _classify_recovery_item(
    item: Mapping[str, Any],
    artifact: Mapping[str, Any] | None,
    *,
    conflict: bool,
) -> dict[str, Any]:
    host = str(item.get("host", "unknown"))
    artifact_id = str(item.get("id", "unknown"))
    target = str(item.get("target", "unknown"))
    kind = str((artifact or {}).get("kind", "unknown"))
    source_name = Path(target).name.casefold()
    instruction = kind == "text" and (
        "instruction" in artifact_id.casefold() or source_name in INSTRUCTION_FILENAMES
    )

    if kind == "config":
        change_class = "host-config"
        route = "hermes-self-engineering" if host == "hermes" else "skill-creator"
    elif instruction:
        change_class = "host-instruction"
        route = "hermes-self-engineering" if host == "hermes" else "skill-creator"
    else:
        change_class = "host-adapter"
        route = "cross-agent-surface-engineering"

    return {
        "surface": "recovery",
        "target": target,
        "host": host,
        "source_action": "conflict" if conflict else str(item.get("action", "change")),
        "change_class": change_class,
        "owner": f"recovery:{host}:{artifact_id}",
        "route": route,
        "disposition": "review-required",
        "eligible_after_checks": False,
        "auto_apply_eligible": False,
    }


def _artifact_index(policy: Mapping[str, Any]) -> dict[tuple[str, str], Mapping[str, Any]]:
    indexed: dict[tuple[str, str], Mapping[str, Any]] = {}
    hosts = policy.get("hosts", {})
    if not isinstance(hosts, Mapping):
        return indexed
    for host, host_policy in hosts.items():
        if not isinstance(host_policy, Mapping):
            continue
        artifacts = host_policy.get("artifacts", [])
        if not isinstance(artifacts, list):
            continue
        for artifact in artifacts:
            if isinstance(artifact, Mapping):
                indexed[(str(host), str(artifact.get("id", "")))] = artifact
    return indexed


def _destination_specs(
    config: Mapping[str, Any],
    machine: str,
    skill_roots: Sequence[str | Path] | None,
) -> list[tuple[str, Path]]:
    machines = config.get("machines", {})
    machine_config = machines.get(machine) if isinstance(machines, Mapping) else None
    if not isinstance(machine_config, Mapping):
        raise RuntimeError(f"unknown machine: {machine}")

    if skill_roots is None:
        raw_roots = machine_config.get("skill_roots", [])
        if not isinstance(raw_roots, list) or not raw_roots:
            raise RuntimeError(f"machine has no skill roots: {machine}")
        roots = [fleet.resolve_template(str(value)) for value in raw_roots]
    else:
        if not skill_roots:
            raise RuntimeError("skill_roots cannot be empty")
        roots = [Path(value).expanduser().resolve() for value in skill_roots]

    unique = sorted({Path(root) for root in roots}, key=lambda value: os.path.normcase(str(value)))
    return [(f"{machine}:skill-root-{index}", root) for index, root in enumerate(unique, start=1)]


def _unmanaged_skill_names(
    destination: Path,
    *,
    desired: set[str],
    managed: set[str],
) -> list[str]:
    if not destination.is_dir() or fleet.is_linklike_path(destination):
        return []
    names: list[str] = []
    for child in destination.iterdir():
        if child.name.startswith(".") or fleet.is_linklike_path(child) or not child.is_dir():
            continue
        if child.name in desired or child.name in managed:
            continue
        if (child / "SKILL.md").is_file():
            names.append(child.name)
    return sorted(names)


def scan(
    repo: str | Path,
    *,
    machine: str = "local-windows",
    recovery_roots: Mapping[str, str | Path] | None = None,
    skill_roots: Sequence[str | Path] | None = None,
) -> dict[str, Any]:
    """Return a deterministic metadata-only drift report.

    The scanner deliberately has no apply path. It delegates to the existing
    recovery and fleet dry-run planners and never emits file bodies or config
    values.
    """

    repo = Path(repo).resolve()
    policy_path = repo / "recovery.json"
    snapshot_dir = repo / "recovery" / "current"
    roots = dict(recovery_roots) if recovery_roots is not None else recovery._default_roots()

    recovery_plan = recovery.restore(
        policy_path,
        snapshot_dir,
        roots,
        apply=False,
        repo_root=repo,
    )
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    artifacts = _artifact_index(policy)
    findings: list[dict[str, Any]] = []
    for item in recovery_plan.get("changes", []):
        key = (str(item.get("host", "")), str(item.get("id", "")))
        findings.append(_classify_recovery_item(item, artifacts.get(key), conflict=False))
    for item in recovery_plan.get("conflicts", []):
        key = (str(item.get("host", "")), str(item.get("id", "")))
        findings.append(_classify_recovery_item(item, artifacts.get(key), conflict=True))

    config = fleet.load_fleet(repo)
    snapshot = fleet.validated_snapshot_output(repo, repo / str(config["snapshot_root"]))
    manifest = fleet.load_manifest(snapshot)
    registry = fleet.registry(repo)
    desired = set(manifest["skills"])

    for destination_id, destination in _destination_specs(config, machine, skill_roots):
        state = fleet.load_state(destination)
        managed = set(state["skills"])
        for action_item in fleet.plan_snapshot(snapshot, destination):
            if action_item.get("action") == "unchanged":
                continue
            name = str(action_item.get("name", ""))
            findings.append(
                classify_fleet_action(
                    action_item,
                    registry.get(name),
                    destination_id=destination_id,
                    checked=False,
                )
            )
        for name in _unmanaged_skill_names(destination, desired=desired, managed=managed):
            findings.append(
                classify_fleet_action(
                    {"name": name, "action": "unmanaged"},
                    registry.get(name),
                    destination_id=destination_id,
                    checked=False,
                    ambiguous=True,
                )
            )

    findings.sort(
        key=lambda item: (
            str(item.get("surface", "")),
            str(item.get("target", "")),
            str(item.get("host", "")),
            str(item.get("destination", "")),
            str(item.get("source_action", "")),
        )
    )
    by_class = Counter(str(item["change_class"]) for item in findings)
    by_disposition = Counter(str(item["disposition"]) for item in findings)
    return {
        "schema_version": 1,
        "mode": "read-only-drift-scan",
        "machine": machine,
        "mutation_performed": False,
        "findings": findings,
        "summary": {
            "total": len(findings),
            "auto_apply_eligible": sum(bool(item["auto_apply_eligible"]) for item in findings),
            "by_change_class": dict(sorted(by_class.items())),
            "by_disposition": dict(sorted(by_disposition.items())),
        },
    }


def _parse_recovery_roots(values: Sequence[str]) -> dict[str, Path] | None:
    if not values:
        return None
    roots = recovery._default_roots()
    for value in values:
        if "=" not in value:
            raise RuntimeError(f"--root must be HOST=PATH: {value}")
        host, raw_path = value.split("=", 1)
        if not host or not raw_path:
            raise RuntimeError(f"--root must be HOST=PATH: {value}")
        roots[host] = Path(raw_path)
    return roots


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("scan",))
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--machine", default="local-windows")
    parser.add_argument("--root", action="append", default=[], metavar="HOST=PATH")
    parser.add_argument("--skill-root", action="append", default=[], type=Path)
    args = parser.parse_args(argv)

    report = scan(
        args.repo,
        machine=args.machine,
        recovery_roots=_parse_recovery_roots(args.root),
        skill_roots=args.skill_root or None,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
