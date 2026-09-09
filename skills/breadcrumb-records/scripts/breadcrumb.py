#!/usr/bin/env python3
"""A small, manually invoked JSON breadcrumb record CLI."""

from __future__ import annotations

import argparse
import copy
import json
import re
import sys
import tempfile
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
STATUSES = {"planned", "in_progress", "deployed", "rolled_back", "blocked"}
NETWORK_REFERENCE = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*://")
CORE_FIELDS = {
    "schema_version",
    "id",
    "title",
    "intent",
    "change",
    "checks",
    "deployment",
    "rollback",
    "supersedes",
    "revision",
}


class CliError(Exception):
    """An expected input, validation, or filesystem error."""


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _nonempty_text(value: Any, name: str, errors: list[str]) -> None:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{name} is missing or must be non-empty text")


def _string_list(value: Any, name: str, errors: list[str]) -> None:
    if not isinstance(value, list):
        errors.append(f"{name} must be a list of text")
        return
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            errors.append(f"{name}[{index}] must be non-empty text")


def _is_network_reference(reference: str) -> bool:
    """Reject URLs and UNC paths before any filesystem operation."""
    return NETWORK_REFERENCE.match(reference) is not None or reference.startswith(("\\\\", "//"))


def validate_record(value: Any, *, allow_history: bool = True, label: str = "record") -> list[str]:
    """Validate JSON shape without reading any referenced evidence."""
    errors: list[str] = []
    if not isinstance(value, dict):
        return [f"{label} must be a JSON object"]

    allowed = CORE_FIELDS | ({"history"} if allow_history else set())
    unknown = sorted(set(value) - allowed)
    if unknown:
        errors.append(f"{label} has unknown fields: {', '.join(unknown)}")

    if (
        "schema_version" not in value
        or not _is_int(value["schema_version"])
        or value["schema_version"] != SCHEMA_VERSION
    ):
        errors.append(f"{label}.schema_version must be integer {SCHEMA_VERSION}")

    _nonempty_text(value.get("id"), f"{label}.id", errors)
    _nonempty_text(value.get("title"), f"{label}.title", errors)

    intent = value.get("intent")
    if not isinstance(intent, dict):
        errors.append(f"{label}.intent must be an object")
    else:
        _nonempty_text(intent.get("text"), f"{label}.intent.text", errors)
        provenance = intent.get("provenance")
        if not isinstance(provenance, dict):
            errors.append(f"{label}.intent.provenance must be an object")
        else:
            refs = provenance.get("refs")
            _string_list(refs, f"{label}.intent.provenance.refs", errors)
            reason = provenance.get("missing_reason")
            if reason is not None and (not isinstance(reason, str) or not reason.strip()):
                errors.append(
                    f"{label}.intent.provenance.missing_reason must be non-empty text when present"
                )
            refs_are_empty = isinstance(refs, list) and not refs
            if refs_are_empty and not (isinstance(reason, str) and reason.strip()):
                errors.append(
                    f"{label}.intent.provenance needs refs or an explicit missing_reason"
                )
            if isinstance(refs, list) and refs and isinstance(reason, str) and reason.strip():
                errors.append(
                    f"{label}.intent.provenance must use refs or missing_reason, not both"
                )

    change = value.get("change")
    if not isinstance(change, dict):
        errors.append(f"{label}.change must be an object")
    else:
        _nonempty_text(change.get("text"), f"{label}.change.text", errors)
        _string_list(change.get("refs"), f"{label}.change.refs", errors)

    checks = value.get("checks")
    if not isinstance(checks, dict):
        errors.append(f"{label}.checks must be an object")
    else:
        _nonempty_text(checks.get("text"), f"{label}.checks.text", errors)
        _string_list(checks.get("refs"), f"{label}.checks.refs", errors)
        _string_list(checks.get("limits"), f"{label}.checks.limits", errors)

    deployment = value.get("deployment")
    if not isinstance(deployment, dict):
        errors.append(f"{label}.deployment must be an object")
    else:
        status = deployment.get("status")
        if not isinstance(status, str) or status not in STATUSES:
            errors.append(
                f"{label}.deployment.status must be one of: {', '.join(sorted(STATUSES))}"
            )
        _string_list(deployment.get("refs"), f"{label}.deployment.refs", errors)
        _string_list(
            deployment.get("session_limits"),
            f"{label}.deployment.session_limits",
            errors,
        )

    _nonempty_text(value.get("rollback"), f"{label}.rollback", errors)

    supersedes = value.get("supersedes")
    if not isinstance(supersedes, dict):
        errors.append(f"{label}.supersedes must be an object")
    else:
        _nonempty_text(supersedes.get("scope"), f"{label}.supersedes.scope", errors)
        _string_list(supersedes.get("refs"), f"{label}.supersedes.refs", errors)

    if "revision" not in value or not _is_int(value["revision"]) or value["revision"] < 1:
        errors.append(f"{label}.revision must be a positive integer")

    if allow_history and "history" in value:
        history = value["history"]
        if not isinstance(history, list):
            errors.append(f"{label}.history must be a list")
        else:
            for index, snapshot in enumerate(history):
                if _is_draft_snapshot(snapshot):
                    if isinstance(value.get("id"), str) and snapshot.get("id") != value["id"]:
                        errors.append(
                            f"{label}.history[{index}].id must match the current record id"
                        )
                    continue
                errors.extend(
                    validate_record(
                        snapshot,
                        allow_history=False,
                        label=f"{label}.history[{index}]",
                    )
                )
    elif not allow_history and "history" in value:
        errors.append(f"{label} historical snapshot must not contain history")

    return errors


def _record_refs(
    value: dict[str, Any], label: str = "record", *, include_history: bool = True
) -> list[tuple[str, str]]:
    refs: list[tuple[str, str]] = []
    intent = value.get("intent", {})
    provenance = intent.get("provenance", {}) if isinstance(intent, dict) else {}
    provenance_refs = provenance.get("refs", []) if isinstance(provenance, dict) else []
    if isinstance(provenance_refs, list):
        for index, ref in enumerate(provenance_refs):
            refs.append((f"{label}.intent.provenance.refs[{index}]", ref))
    for field in ("change", "checks", "deployment", "supersedes"):
        section = value.get(field, {})
        values = section.get("refs", []) if isinstance(section, dict) else []
        if isinstance(values, list):
            for index, ref in enumerate(values):
                refs.append((f"{label}.{field}.refs[{index}]", ref))
    if include_history:
        history = value.get("history", [])
        if isinstance(history, list):
            for index, snapshot in enumerate(history):
                if isinstance(snapshot, dict):
                    refs.extend(
                        _record_refs(
                            snapshot,
                            f"{label}.history[{index}]",
                            include_history=True,
                        )
                    )
    return refs


def validate_references(
    value: dict[str, Any], record_path: Path, *, label: str = "record"
) -> list[str]:
    """Check current local references, never historical evidence or contents."""
    errors: list[str] = []
    base = record_path.parent.resolve()
    for field, reference in _record_refs(value, label, include_history=False):
        if _is_network_reference(reference):
            errors.append(
                f"{field}: unsupported network reference (local paths only): {reference}"
            )
            continue
        target = Path(reference)
        if not target.is_absolute():
            target = base / target
        try:
            exists = target.is_file()
        except OSError as exc:
            errors.append(f"{field}: cannot inspect local reference {reference}: {exc}")
            continue
        if not exists:
            errors.append(f"{field}: broken local reference: {reference}")
    return errors


def _historical_reference_warnings(value: dict[str, Any], record_path: Path) -> list[str]:
    warnings: list[str] = []
    history = value.get("history", [])
    if not isinstance(history, list):
        return warnings
    for index, snapshot in enumerate(history):
        if not isinstance(snapshot, dict):
            continue
        for warning in validate_references(
            snapshot,
            record_path,
            label=f"record.history[{index}]",
        ):
            warnings.append(f"historical evidence warning: {warning}")
    return warnings


def load_json(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError:
        raise CliError(f"record not found: {path}")
    except json.JSONDecodeError as exc:
        raise CliError(f"invalid JSON in {path}: line {exc.lineno} column {exc.colno}")
    except OSError as exc:
        raise CliError(f"cannot read {path}: {exc}")


def atomic_write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(value, indent=2, ensure_ascii=False) + "\n"
    temporary: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            handle.write(content)
            handle.flush()
            temporary = handle.name
        Path(temporary).replace(path)
        temporary = None
    except OSError as exc:
        raise CliError(f"cannot atomically write {path}: {exc}")
    finally:
        if temporary:
            try:
                Path(temporary).unlink()
            except OSError:
                pass


def _scaffold_for_id(record_id: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "id": record_id,
        "title": "",
        "intent": {
            "text": "",
            "provenance": {
                "refs": [],
                "missing_reason": "Intent provenance is not recorded yet.",
            },
        },
        "change": {"text": "", "refs": []},
        "checks": {"text": "", "refs": [], "limits": []},
        "deployment": {"status": "planned", "refs": [], "session_limits": []},
        "rollback": "",
        "supersedes": {"scope": "", "refs": []},
        "revision": 1,
        "history": [],
    }


def scaffold(record_path: Path) -> dict[str, Any]:
    return _scaffold_for_id(record_path.stem or "record")


def _is_exact_scaffold(value: Any, *, record_id: str | None = None) -> bool:
    if not isinstance(value, dict) or not isinstance(value.get("id"), str):
        return False
    expected_id = value["id"] if record_id is None else record_id
    return value == _scaffold_for_id(expected_id)


def _is_draft_snapshot(value: Any) -> bool:
    if not isinstance(value, dict) or value.get("draft") is not True:
        return False
    candidate = copy.deepcopy(value)
    candidate.pop("draft", None)
    return _is_exact_scaffold(candidate)


def command_init(record: Path) -> int:
    if record.exists():
        raise CliError(f"refusing to overwrite existing record: {record}")
    atomic_write(record, scaffold(record))
    print(f"created scaffold: {record}")
    return 0


def checked_record(record: Path) -> tuple[dict[str, Any] | None, list[str]]:
    value = load_json(record)
    shape_errors = validate_record(value)
    if shape_errors:
        return None, shape_errors
    assert isinstance(value, dict)
    return value, validate_references(value, record)


def command_check(record: Path) -> int:
    value, errors = checked_record(record)
    if errors:
        print("check failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    assert value is not None
    print("OK: structural validation passed; evidence contents were not inspected or proven.")
    for warning in _historical_reference_warnings(value, record):
        print(f"WARNING: {warning}")
    return 0


def command_update(record: Path, source: Path) -> int:
    current = load_json(record)
    replacement = load_json(source)

    current_is_scaffold = _is_exact_scaffold(current, record_id=record.stem or "record")
    current_errors = [] if current_is_scaffold else validate_record(current)
    replacement_errors = validate_record(replacement)
    if isinstance(replacement, dict) and not replacement_errors:
        # The replacement will become RECORD, so relative refs resolve there.
        replacement_errors.extend(validate_references(replacement, record))
    errors = [f"current record: {error}" for error in current_errors]
    errors.extend(f"replacement: {error}" for error in replacement_errors)
    if errors:
        raise CliError("update rejected before write:\n" + "\n".join(f"- {error}" for error in errors))
    assert isinstance(current, dict) and isinstance(replacement, dict)

    if current.get("id") != replacement.get("id"):
        raise CliError(
            "update rejected before write: immutable id mismatch "
            f"({current.get('id')!r} != {replacement.get('id')!r})"
        )

    old_revision = current["revision"]
    history = copy.deepcopy(current.get("history", []))
    previous = copy.deepcopy(current)
    previous.pop("history", None)
    previous["revision"] = old_revision
    if current_is_scaffold:
        previous["history"] = []
        previous["draft"] = True
    replacement = copy.deepcopy(replacement)
    replacement["schema_version"] = SCHEMA_VERSION
    replacement["revision"] = old_revision + 1
    history.append(previous)
    replacement["history"] = history
    historical_warnings = _historical_reference_warnings(replacement, record)
    atomic_write(record, replacement)
    print(f"updated {record} to revision {replacement['revision']}")
    for warning in historical_warnings:
        print(f"WARNING: {warning}", file=sys.stderr)
    return 0


def _markdown_refs(refs: list[str], record_path: Path | None = None) -> list[str]:
    if not refs:
        return ["- None recorded."]
    base = record_path.parent.resolve() if record_path is not None else Path.cwd().resolve()
    rendered: list[str] = []
    for ref in refs:
        target = Path(ref)
        if not target.is_absolute():
            target = base / target
        uri = target.resolve().as_uri()
        rendered.append(
            f"- [`{ref}`]({uri}) (structural reference only; evidence contents not inspected)"
        )
    return rendered


def _section_lines(title: str, text: str) -> list[str]:
    return [f"### {title}", text, ""]


def render_record(
    value: dict[str, Any],
    record_path: Path | None = None,
    historical_warnings: list[str] | None = None,
) -> str:
    intent = value["intent"]
    provenance = intent["provenance"]
    change = value["change"]
    checks = value["checks"]
    deployment = value["deployment"]
    supersedes = value["supersedes"]
    revision = value.get("revision", 1)

    lines = [
        f"# {value['title']}",
        "",
        f"- Record ID: `{value['id']}`",
        f"- Current revision: `{revision}`",
        "",
        "## Current state",
        "",
    ]
    lines.extend(_section_lines("Intent", intent["text"]))
    lines.append("**Intent provenance**")
    if provenance.get("missing_reason"):
        lines.append(f"- Unknown / not recorded: {provenance['missing_reason']}")
    else:
        lines.extend(_markdown_refs(provenance["refs"], record_path))
    lines.append("")

    lines.extend(_section_lines("Change", change["text"]))
    lines.append("**Change references**")
    lines.extend(_markdown_refs(change["refs"], record_path))
    lines.append("")

    lines.extend(_section_lines("Checks", checks["text"]))
    lines.append("**Check references**")
    lines.extend(_markdown_refs(checks["refs"], record_path))
    lines.append("**Check limits**")
    lines.extend(f"- {limit}" for limit in checks["limits"] or ["None recorded."])
    lines.append("")

    lines.extend(_section_lines("Deployment", f"Status: **{deployment['status']}**"))
    lines.append("**Deployment references**")
    lines.extend(_markdown_refs(deployment["refs"], record_path))
    lines.append("**Session limits**")
    lines.extend(
        f"- {limit}" for limit in deployment["session_limits"] or ["None recorded."]
    )
    lines.append("")

    lines.extend(_section_lines("Rollback", value["rollback"]))
    lines.append("### Supersedes (scoped)")
    lines.append(supersedes["scope"])
    lines.append("**Supersedes references**")
    lines.extend(_markdown_refs(supersedes["refs"], record_path))
    lines.append("")

    lines.extend(
        [
            "## Reference-validation boundary",
            "Only JSON structure, local-path existence, and supported reference type are checked. "
            "This validator does not inspect or prove the truth of evidence contents.",
            "",
            "## Historical revisions (not current)",
            "",
        ]
    )
    history = value.get("history", [])
    if not history:
        lines.append("No historical revisions recorded.")
    else:
        for snapshot in history:
            draft_label = " — DRAFT (not validated evidence)" if snapshot.get("draft") else ""
            lines.extend(
                [
                    f"### Revision {snapshot.get('revision', '?')} — historical and not current{draft_label}",
                    f"- Historical title: {snapshot.get('title', '')}",
                    f"- Historical deployment status: {snapshot.get('deployment', {}).get('status', '')}",
                    "- This snapshot is historical and not current.",
                    "",
                ]
            )
        if historical_warnings:
            lines.append("**Historical evidence warnings**")
            lines.extend(f"- WARNING: {warning}" for warning in historical_warnings)
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def command_render(record: Path) -> int:
    value, errors = checked_record(record)
    if errors:
        print("render rejected because the record is not structurally valid:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    assert value is not None
    warnings = _historical_reference_warnings(value, record)
    sys.stdout.write(render_record(value, record, warnings))
    return 0


def parser() -> argparse.ArgumentParser:
    command_parser = argparse.ArgumentParser(
        description="Validate and render one explicitly named breadcrumb JSON record."
    )
    commands = command_parser.add_subparsers(dest="command", required=True)

    for name in ("init", "check", "render"):
        sub = commands.add_parser(name)
        sub.add_argument("record", type=Path)

    update = commands.add_parser("update")
    update.add_argument("record", type=Path)
    update.add_argument("--from", dest="source", type=Path, required=True)
    return command_parser


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "init":
            return command_init(args.record)
        if args.command == "check":
            return command_check(args.record)
        if args.command == "update":
            return command_update(args.record, args.source)
        if args.command == "render":
            return command_render(args.record)
    except CliError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
