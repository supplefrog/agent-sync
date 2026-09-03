#!/usr/bin/env python
"""Stage verified global-agent learning signals without mutating live behavior."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


SOURCE_TYPES = {
    "user-correction",
    "verified-task-failure",
    "successful-comparison",
    "github-outcome",
    "model-runtime-change",
    "external-research",
}
SCOPES = {"global", "cross-project", "project", "user"}
OWNER_BY_CLASS = {
    "generic-judgment": "shared-instruction",
    "reusable-procedure": "agent-skill",
    "runtime-mechanic": "host-adapter",
    "github-workflow": "github-follow-up",
    "safety-governance": "manual-control-plane",
    "project-convention": "project-local",
    "user-preference": "user-memory",
    "environment-fact": "user-memory",
}
EVENT_FIELDS = {
    "schema_version",
    "source_type",
    "source_ref",
    "observed_at",
    "scope",
    "behavior_class",
    "verification",
    "lesson",
}
VERIFICATION_FIELDS = {"status", "evidence_refs"}
LESSON_FIELDS = {"problem", "better_behavior", "near_miss"}
SECRET_PATTERNS = [
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\bgh[opusr]_[A-Za-z0-9]{20,}\b"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"(?i)\b(?:api[_-]?key|access[_-]?token|password)\s*[:=]\s*[^\s,;]{8,}"),
    re.compile(r"(?i)\bauthorization\s*:\s*bearer\s+[^\s]{8,}"),
]


class IntakeError(ValueError):
    """The proposed event is unsafe or outside the intake contract."""


def default_store(
    environ: Mapping[str, str] | None = None,
    *,
    platform_name: str | None = None,
    home: Path | None = None,
) -> Path:
    """Resolve one shared ledger location across Hermes, Codex, and OMP."""

    values = os.environ if environ is None else environ
    explicit = values.get("AGENT_SIGNAL_LEARNING_STORE", "").strip()
    if explicit:
        return Path(explicit).expanduser()
    hermes_home = values.get("HERMES_HOME", "").strip()
    if hermes_home:
        return Path(hermes_home).expanduser() / "cache" / "global-learning-intake"
    platform = os.name if platform_name is None else platform_name
    home_path = Path.home() if home is None else home
    if platform == "nt":
        local_appdata = values.get("LOCALAPPDATA", "").strip()
        if local_appdata:
            return Path(local_appdata).expanduser() / "hermes" / "cache" / "global-learning-intake"
    return home_path / ".hermes" / "cache" / "global-learning-intake"


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def normalized_text(value: str) -> str:
    return " ".join(value.casefold().split())


def normalized_timestamp(value: str) -> str:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise IntakeError("observed_at must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise IntakeError("observed_at must include a timezone")
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def required_string(container: dict[str, Any], name: str, *, maximum: int = 1000) -> str:
    value = container.get(name)
    if not isinstance(value, str) or not value.strip():
        raise IntakeError(f"{name} must be a non-empty string")
    value = value.strip()
    if len(value) > maximum:
        raise IntakeError(f"{name} exceeds {maximum} characters")
    if "\x00" in value:
        raise IntakeError(f"{name} contains a NUL byte")
    return value


def reject_unknown(container: dict[str, Any], allowed: set[str], label: str) -> None:
    unknown = sorted(set(container) - allowed)
    if unknown:
        raise IntakeError(f"unsupported field in {label}: {', '.join(unknown)}")


def validate_event(raw: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise IntakeError("event must be a JSON object")
    reject_unknown(raw, EVENT_FIELDS, "event")
    if raw.get("schema_version") != 1:
        raise IntakeError("unsupported event schema_version")

    source_type = raw.get("source_type")
    if source_type not in SOURCE_TYPES:
        raise IntakeError(f"unsupported source_type: {source_type}")
    scope = raw.get("scope")
    if scope not in SCOPES:
        raise IntakeError(f"unsupported scope: {scope}")
    behavior_class = raw.get("behavior_class")
    if behavior_class not in OWNER_BY_CLASS:
        raise IntakeError(f"unsupported behavior_class: {behavior_class}")

    if scope == "project" and behavior_class != "project-convention":
        raise IntakeError("project scope must use project-convention")
    if behavior_class == "project-convention" and scope != "project":
        raise IntakeError("project-convention must remain project scoped")
    if scope == "user" and behavior_class not in {"user-preference", "environment-fact"}:
        raise IntakeError("user scope is limited to preferences and environment facts")
    if behavior_class in {"user-preference", "environment-fact"} and scope != "user":
        raise IntakeError("user facts and preferences must use user scope")

    source_ref = required_string(raw, "source_ref", maximum=500)
    if "\n" in source_ref or "\r" in source_ref:
        raise IntakeError("source_ref must be a compact identifier")
    observed_at = normalized_timestamp(required_string(raw, "observed_at", maximum=64))

    verification = raw.get("verification")
    if not isinstance(verification, dict):
        raise IntakeError("verification must be an object")
    reject_unknown(verification, VERIFICATION_FIELDS, "verification")
    refs = verification.get("evidence_refs")
    if verification.get("status") != "verified" or not isinstance(refs, list) or not refs:
        raise IntakeError("verified evidence is required")
    if len(refs) > 20:
        raise IntakeError("evidence_refs exceeds 20 entries")
    clean_refs: list[str] = []
    for ref in refs:
        if not isinstance(ref, str) or not ref.strip() or len(ref.strip()) > 500:
            raise IntakeError("each evidence reference must be a compact string")
        if "\n" in ref or "\r" in ref:
            raise IntakeError("evidence references cannot contain raw text")
        clean_refs.append(ref.strip())

    lesson = raw.get("lesson")
    if not isinstance(lesson, dict):
        raise IntakeError("lesson must be an object")
    reject_unknown(lesson, LESSON_FIELDS, "lesson")
    clean_lesson = {
        key: required_string(lesson, key, maximum=1000)
        for key in ("problem", "better_behavior", "near_miss")
    }

    clean = {
        "schema_version": 1,
        "source_type": source_type,
        "source_ref": source_ref,
        "observed_at": observed_at,
        "scope": scope,
        "behavior_class": behavior_class,
        "verification": {"status": "verified", "evidence_refs": sorted(set(clean_refs))},
        "lesson": clean_lesson,
    }
    serialized = canonical_json(clean)
    if any(pattern.search(serialized) for pattern in SECRET_PATTERNS):
        raise IntakeError("event contains sensitive credential-like material")
    return clean


def route(event: dict[str, Any]) -> tuple[str, str, str]:
    scope = event["scope"]
    if scope == "project":
        return "project-local", "local-only", "local"
    if scope == "user":
        return "user-memory", "memory-only", "memory"
    return OWNER_BY_CLASS[event["behavior_class"]], "shadow-global", "global"


def candidate_fingerprint(event: dict[str, Any], owner: str) -> str:
    lesson = {
        key: normalized_text(event["lesson"][key])
        for key in ("problem", "better_behavior", "near_miss")
    }
    return digest(
        {
            "schema_version": 1,
            "scope": event["scope"],
            "behavior_class": event["behavior_class"],
            "owner": owner,
            "lesson": lesson,
        }
    )


def atomic_json_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with temp.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp, path)


def append_receipt(path: Path, payload: dict[str, Any]) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError:
        return False
    return True


def ingest(raw_event: dict[str, Any], store: Path) -> dict[str, Any]:
    event = validate_event(raw_event)
    owner, disposition, bucket = route(event)
    event_id = digest(event)
    fingerprint = candidate_fingerprint(event, owner)
    candidate_id = fingerprint[:20]
    receipt_path = store / "receipts" / f"{event_id}.json"
    candidate_path = store / "candidates" / bucket / f"{candidate_id}.json"

    evidence_item = {
        "event_id": event_id,
        "source_type": event["source_type"],
        "source_ref": event["source_ref"],
        "observed_at": event["observed_at"],
        "evidence_refs": event["verification"]["evidence_refs"],
    }
    if candidate_path.is_file():
        candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
    else:
        candidate = {
            "schema_version": 1,
            "candidate_id": candidate_id,
            "fingerprint": fingerprint,
            "status": "shadow",
            "scope": event["scope"],
            "behavior_class": event["behavior_class"],
            "owner": owner,
            "lesson": event["lesson"],
            "promotion_allowed": False,
            "promotion_blocked": True,
            "promotion_gate": "capability-curator" if bucket == "global" else "explicit-owner-review",
            "created_at": event["observed_at"],
            "updated_at": event["observed_at"],
            "recurrence_count": 0,
            "evidence": [],
        }

    known_ids = {item["event_id"] for item in candidate.get("evidence", [])}
    idempotent = event_id in known_ids or receipt_path.exists()
    if event_id not in known_ids:
        candidate["evidence"].append(evidence_item)
        candidate["evidence"].sort(key=lambda item: item["event_id"])
        candidate["recurrence_count"] = len(candidate["evidence"])
        candidate["created_at"] = min(candidate["created_at"], event["observed_at"])
        candidate["updated_at"] = max(candidate["updated_at"], event["observed_at"])
        atomic_json_write(candidate_path, candidate)

    receipt = {
        "schema_version": 1,
        "event_id": event_id,
        "candidate_id": candidate_id,
        "candidate_fingerprint": fingerprint,
        "disposition": disposition,
        "owner": owner,
        "event": event,
    }
    created_receipt = append_receipt(receipt_path, receipt)
    idempotent = idempotent or not created_receipt
    return {
        "schema_version": 1,
        "event_id": event_id,
        "candidate_id": candidate_id,
        "disposition": disposition,
        "owner": owner,
        "promotion_blocked": True,
        "idempotent": idempotent,
        "candidate_path": str(candidate_path.resolve()),
        "receipt_path": str(receipt_path.resolve()),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    ingest_parser = subparsers.add_parser("ingest", help="Validate and stage one learning event")
    ingest_parser.add_argument("--event", type=Path, required=True)
    ingest_parser.add_argument(
        "--store",
        type=Path,
        help="Shared ledger root; overrides AGENT_SIGNAL_LEARNING_STORE and the active Hermes home",
    )
    args = parser.parse_args(argv)
    try:
        raw = json.loads(args.event.read_text(encoding="utf-8"))
        store = args.store if args.store is not None else default_store()
        result = ingest(raw, store.resolve())
    except (OSError, json.JSONDecodeError, IntakeError) as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

