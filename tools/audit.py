#!/usr/bin/env python
"""Mechanical convergence audit for the surface matrix and registry."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path, PurePosixPath
from typing import Any

import jsonschema

REQUIRED_MODALITY_IDS = {
    "instructions-style",
    "skills-procedures",
    "tools-mcp",
    "routing-delegation",
    "memory-context",
    "policy-security",
    "planning-automation",
    "lifecycle-update",
}

ALLOWED_REGISTRY_STATUSES = {"staged", "admitted", "blocked", "retired", "rejected"}
ALLOWED_MODALITY_STATUSES = {"unassessed", "staged", "confirmed", "partial", "stale"}
CURRENT_HOSTS = {"codex", "hermes", "omp"}


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"malformed JSON: {path}: {exc.msg}") from exc


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def cli_version(name: str) -> str:
    executable = shutil.which(name)
    if not executable:
        raise FileNotFoundError(name)
    command = [executable, "--version"]
    if os.name == "nt" and Path(executable).suffix.lower() in {".cmd", ".bat"}:
        command = ["cmd.exe", "/d", "/c", executable, "--version"]
    proc = subprocess.run(command, text=True, capture_output=True, check=False)
    output = (proc.stdout or proc.stderr or "").strip()
    if not output:
        raise RuntimeError(f"{name} --version produced no output")
    return output.splitlines()[0]


def validate_repo(repo: Path, live: bool = False) -> list[str]:
    errors: list[str] = []
    try:
        registry = load_json(repo / "registry.json")
    except Exception as exc:
        return [str(exc)]
    try:
        surface = load_json(repo / "contracts" / "surface-matrix.json")
    except Exception as exc:
        errors.append(str(exc))
        return errors
    try:
        findings = load_json(repo / "evidence" / "findings.json")
    except Exception as exc:
        errors.append(str(exc))
        return errors
    try:
        ownership = load_json(repo / "contracts" / "ownership.json")
    except Exception as exc:
        errors.append(str(exc))
        return errors
    try:
        ownership_schema = load_json(repo / "contracts" / "ownership.schema.json")
        validator = jsonschema.Draft202012Validator(ownership_schema)
        for error in sorted(validator.iter_errors(ownership), key=lambda item: list(item.path)):
            location = ".".join(str(part) for part in error.absolute_path) or "<root>"
            errors.append(f"ownership schema: {location}: {error.message}")
    except Exception as exc:
        errors.append(f"ownership schema: {exc}")

    if registry.get("schema_version") != 1:
        errors.append("wrong schema_version in registry.json")
    if surface.get("schema_version") != 1:
        errors.append("wrong schema_version in contracts/surface-matrix.json")
    if findings.get("schema_version") != 1:
        errors.append("wrong schema_version in evidence/findings.json")
    if ownership.get("schema_version") != 1:
        errors.append("wrong schema_version in contracts/ownership.json")

    hosts = surface.get("hosts") or {}
    supported_hosts = set(ownership.get("supported_hosts") or [])
    if supported_hosts != CURRENT_HOSTS:
        errors.append("supported host set must be exactly: codex, hermes, omp")
    if set(hosts) != supported_hosts:
        errors.append("surface host set differs from supported hosts")
    adapter_hosts = {
        path.stem
        for path in (repo / "adapters").glob("*.json")
        if path.name != "schema.json"
    }
    adapter_delta = sorted(adapter_hosts ^ supported_hosts)
    if adapter_delta:
        errors.append("adapter set differs from supported hosts: " + ", ".join(adapter_delta))
    for host in sorted(supported_hosts):
        if host not in hosts:
            errors.append(f"missing {host} host record")
        adapter_path = repo / "adapters" / f"{host}.json"
        try:
            adapter = load_json(adapter_path)
        except Exception as exc:
            errors.append(str(exc))
            continue
        if adapter.get("schema_version") != 1 or adapter.get("host") != host:
            errors.append(f"invalid adapter: {adapter_path.relative_to(repo)}")
            continue
        instructions = adapter.get("instructions") or {}
        skills = adapter.get("skills") or {}
        for rel in (instructions.get("source"), skills.get("source")):
            if not isinstance(rel, str) or not (repo / rel).exists():
                errors.append(f"missing adapter source for {host}: {rel}")
        if skills.get("selection") != "registry:admitted":
            errors.append(f"unsafe skill selection for {host}")
        for template in (instructions.get("target"), skills.get("install_root")):
            if not isinstance(template, str) or "{" not in template:
                errors.append(f"non-portable adapter target for {host}: {template}")

    modalities = surface.get("modalities", [])
    modality_ids = [item.get("id") for item in modalities]
    missing = sorted(REQUIRED_MODALITY_IDS - set(modality_ids))
    duplicates = sorted({mid for mid in modality_ids if modality_ids.count(mid) > 1})
    if missing:
        errors.append("missing modality ids: " + ", ".join(missing))
    if duplicates:
        errors.append("duplicate modality ids: " + ", ".join(duplicates))

    for item in modalities:
        status = item.get("status")
        if status not in ALLOWED_MODALITY_STATUSES:
            errors.append(f"invalid status for modality {item.get('id')}: {status}")
        for rel in item.get("portable_artifacts", []):
            if not (repo / rel).exists():
                errors.append(f"missing portable artifact path: {rel}")
        evidence = item.get("evidence") or {}
        suites = evidence.get("suites") or []
        summaries = evidence.get("summaries") or []
        for rel in [*suites, *summaries]:
            if not isinstance(rel, str) or not (repo / rel).is_file():
                errors.append(f"missing modality evidence for {item.get('id')}: {rel}")
        if status == "confirmed":
            suite_names = {
                load_json(repo / rel).get("name")
                for rel in suites
                if isinstance(rel, str) and (repo / rel).is_file()
            }
            result_docs = [
                load_json(repo / rel)
                for rel in summaries
                if isinstance(rel, str) and (repo / rel).is_file()
            ]
            covered = {(doc.get("host"), doc.get("suite")) for doc in result_docs}
            expected = {(host, suite) for host in hosts for suite in suite_names}
            if not suites or expected - covered:
                errors.append(f"incomplete confirmed evidence for {item.get('id')}")
            if any(not (doc.get("result") or {}).get("passed") for doc in result_docs):
                errors.append(f"failed result in confirmed evidence for {item.get('id')}")
            hashes = {
                (doc.get("artifacts") or {}).get("candidate_sha256")
                for doc in result_docs
            }
            if not result_docs or None in hashes or len(hashes) != 1:
                errors.append(f"candidate hash mismatch for confirmed modality {item.get('id')}")

    ledger_ref = surface.get("knowledge_ledger")
    if not isinstance(ledger_ref, str) or not (repo / "contracts" / ledger_ref).resolve().is_file():
        errors.append("missing ledger")
    ledger = findings.get("records")
    if not isinstance(ledger, list):
        errors.append("missing ledger")
        ledger = []
    elif not ledger:
        errors.append("missing ledger")
    for rec in ledger:
        for ev in rec.get("evidence", []):
            if ev.get("kind") == "evaluation":
                ref = ev.get("reference")
                if not ref:
                    errors.append(f"missing local evaluation reference in ledger: {rec.get('id')}")
                else:
                    p = repo / ref
                    if not ref.startswith("evals/results/") or not p.exists():
                        errors.append(f"missing local evaluation reference in ledger: {ref}")

    registry_names: list[str] = []
    if isinstance(registry.get("skills"), list):
        registry_names = [str(skill.get("name")) for skill in registry["skills"]]
        duplicate_skills = sorted({name for name in registry_names if registry_names.count(name) > 1})
        if duplicate_skills:
            errors.append("duplicate registry skills: " + ", ".join(duplicate_skills))
        actual_skills = {
            path.parent.name
            for path in (repo / "skills").glob("*/SKILL.md")
        }
        for name in sorted(actual_skills - set(registry_names)):
            errors.append(f"unregistered portable skill: {name}")
        for skill in registry["skills"]:
            name = skill.get("name")
            if skill.get("status") not in ALLOWED_REGISTRY_STATUSES:
                errors.append(f"invalid status for registry skill {name}: {skill.get('status')}")
            skill_path = repo / "skills" / str(name) / "SKILL.md"
            if not skill_path.is_file():
                errors.append(f"registry skill/path mismatch: {name}")
            if skill.get("status") == "admitted":
                suite_name = None
                skill_dir = repo / "skills" / str(name)
                skill_text = skill_path.read_text(encoding="utf-8") if skill_path.is_file() else ""
                for line in skill_text.splitlines():
                    if line.startswith("name:"):
                        suite_name = line.split(":", 1)[1].strip()
                        break
                candidates = [name]
                if suite_name:
                    candidates.append(suite_name)
                results_dir = repo / "evals" / "results"
                found = False
                if results_dir.is_dir():
                    for p in results_dir.iterdir():
                        if p.is_file() and p.name.endswith((".json", ".txt", ".md")):
                            lower = p.name.lower()
                            if any(token.lower() in lower for token in candidates):
                                found = True
                                break
                if not found:
                    errors.append(f"missing compact result for admitted skill: {name}")
    else:
        errors.append("missing registry skills")

    if "fleet-sync" in registry_names:
        tools_dir = str(Path(__file__).resolve().parent)
        if tools_dir not in sys.path:
            sys.path.insert(0, tools_dir)
        try:
            import recovery as recovery_tool

            recovery_tool.verify_snapshot(repo / "recovery.json", repo / "recovery" / "current")
        except Exception as exc:
            errors.append(f"recovery contract: {exc}")
        try:
            import instruction_profile as profile_tool

            profile_paths = sorted((repo / "profiles").glob("*.json"))
            if not profile_paths:
                errors.append("instruction profiles: no model-qualified profiles")
            current_profiles = 0
            for profile_path in profile_paths:
                report = profile_tool.verify_profile(repo, profile_path, live=False)
                if report.get("status") == "current-observed":
                    current_profiles += 1
            if current_profiles != 1:
                errors.append(
                    f"instruction profiles: expected exactly one current-observed profile, got {current_profiles}"
                )
        except Exception as exc:
            errors.append(f"instruction profiles: {exc}")

    integration_root = repo / "integrations"
    if integration_root.is_dir():
        for skill_path in sorted(integration_root.rglob("SKILL.md")):
            errors.append(
                "skill entrypoint outside canonical skills tree: "
                + skill_path.relative_to(repo).as_posix()
            )

    capability_records = ownership.get("capabilities")
    if not isinstance(capability_records, list):
        errors.append("missing ownership capabilities")
        capability_records = []
    capability_ids = [str(item.get("id")) for item in capability_records]
    duplicate_capabilities = sorted(
        {name for name in capability_ids if capability_ids.count(name) > 1}
    )
    if duplicate_capabilities:
        errors.append("duplicate ownership capabilities: " + ", ".join(duplicate_capabilities))
    if set(capability_ids) != set(registry_names):
        errors.append("ownership capabilities differ from registry skills")
    for item in capability_records:
        capability_id = str(item.get("id"))
        expected_owner = f"skills/{capability_id}"
        if item.get("owner") != expected_owner or not (repo / expected_owner / "SKILL.md").is_file():
            errors.append(f"invalid canonical owner for capability: {capability_id}")
        registry_status = next(
            (
                skill.get("status")
                for skill in registry.get("skills", [])
                if str(skill.get("name")) == capability_id
            ),
            None,
        )
        if item.get("status") != registry_status:
            errors.append(f"ownership status differs from registry: {capability_id}")
        selection_state = item.get("selection_state")
        selection_evidence = item.get("selection_evidence")
        if not isinstance(item.get("selection_reason"), str) or not item["selection_reason"].strip():
            errors.append(f"missing selection reason for capability: {capability_id}")
        if registry_status == "admitted":
            if selection_state != "selected" or not isinstance(selection_evidence, list) or not selection_evidence:
                errors.append(f"admitted capability lacks selected evidence: {capability_id}")
            else:
                for reference in selection_evidence:
                    if not isinstance(reference, str):
                        errors.append(f"invalid selection evidence for capability: {capability_id}")
                        continue
                    rel = PurePosixPath(reference)
                    if (
                        rel.is_absolute()
                        or ".." in rel.parts
                        or rel.parts[:2] != ("evals", "results")
                        or rel.suffix != ".json"
                    ):
                        errors.append(f"invalid selection evidence for capability: {capability_id}")
                        continue
                    evidence_path = (repo / Path(*rel.parts)).resolve()
                    results_root = (repo / "evals" / "results").resolve()
                    try:
                        evidence_path.relative_to(results_root)
                    except ValueError:
                        errors.append(f"invalid selection evidence for capability: {capability_id}")
                        continue
                    if not evidence_path.is_file():
                        errors.append(f"invalid selection evidence for capability: {capability_id}")
                        continue
                    try:
                        evidence_record = load_json(evidence_path)
                    except Exception:
                        errors.append(f"invalid selection evidence for capability: {capability_id}")
                        continue
                    bindings = {
                        evidence_record.get("suite"),
                        evidence_record.get("capability"),
                        evidence_record.get("owner_capability"),
                    }
                    if capability_id not in bindings:
                        errors.append(
                            f"selection evidence is not bound to capability: {capability_id}"
                        )
        elif selection_state != "unresolved" or selection_evidence != []:
            errors.append(f"non-admitted capability must remain unresolved: {capability_id}")

    retired_records = ownership.get("retired_artifacts")
    if not isinstance(retired_records, list):
        errors.append("missing retired artifact records")
        retired_records = []
    for item in retired_records:
        rel = item.get("path")
        replacement = item.get("replacement")
        reason = item.get("reason")
        if (
            not isinstance(rel, str)
            or not rel
            or not isinstance(replacement, str)
            or not replacement
            or not isinstance(reason, str)
            or not reason.strip()
        ):
            errors.append("invalid retired artifact record")
            continue
        if (repo / rel).exists():
            errors.append(f"retired artifact reappeared: {rel}")

    if live:
        for host, rec in hosts.items():
            configured = str(rec.get("cli_version", ""))
            try:
                actual = cli_version(host)
            except FileNotFoundError:
                errors.append(f"unavailable CLI: {host}")
                continue
            except Exception as exc:
                errors.append(f"unavailable CLI: {host}: {exc}")
                continue
            if configured and configured not in actual:
                errors.append(f"{host} version mismatch: expected {configured}, got {actual}")
    return errors


def snapshot_repo(repo: Path) -> dict[str, Any]:
    surface = load_json(repo / "contracts" / "surface-matrix.json")
    registry = load_json(repo / "registry.json")
    hashes = {
        "registry.json": sha256_file(repo / "registry.json"),
        "surfaces/core.md": sha256_file(repo / "surfaces" / "core.md"),
        "contracts/surface-matrix.json": sha256_file(repo / "contracts" / "surface-matrix.json"),
        "contracts/ownership.json": sha256_file(repo / "contracts" / "ownership.json"),
        "adapters/codex.json": sha256_file(repo / "adapters" / "codex.json"),
        "adapters/hermes.json": sha256_file(repo / "adapters" / "hermes.json"),
        "adapters/omp.json": sha256_file(repo / "adapters" / "omp.json"),
    }
    skill_hashes: dict[str, str] = {}
    for skill in registry.get("skills", []):
        name = skill.get("name")
        skill_path = repo / "skills" / str(name) / "SKILL.md"
        if skill_path.is_file():
            skill_hashes[str(name)] = sha256_file(skill_path)
    snapshot = {
        "timestamp_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "live_cli_versions": {
            host: cli_version(host) for host in (surface.get("hosts") or {})
        },
        "hashes": hashes,
        "skill_hashes": skill_hashes,
    }
    return snapshot


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", nargs="?", choices=("check", "snapshot"), default="check")
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)

    repo = args.repo.resolve()
    if args.action == "check":
        errors = validate_repo(repo, live=args.live)
        if errors:
            for err in errors:
                print(err, file=sys.stderr)
            return 1
        return 0

    snapshot = snapshot_repo(repo)
    out = args.out or repo / ".evals" / "surface-snapshot.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False), encoding="utf-8")
    print(out)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
