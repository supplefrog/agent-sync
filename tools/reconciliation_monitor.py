#!/usr/bin/env python
"""Metadata-only delta monitor for cross-agent task reconciliation.

The monitor never interprets transcript or task bodies. It records bounded source
identities, cursors, and hashes, then wakes a Hermes reconciliation agent when
Hermes sessions, Hermes Kanban, Codex sessions, or OMP sessions change.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
from pathlib import Path
from typing import Any, Iterable

SCHEMA_VERSION = 1
EXTRACTOR_VERSION = "reconciliation-monitor-v1"


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def file_digest(path: Path, limit: int | None = None) -> str:
    value = hashlib.sha256()
    remaining = limit
    with path.open("rb") as handle:
        while remaining is None or remaining > 0:
            size = 1024 * 1024 if remaining is None else min(1024 * 1024, remaining)
            chunk = handle.read(size)
            if not chunk:
                break
            value.update(chunk)
            if remaining is not None:
                remaining -= len(chunk)
    return value.hexdigest()


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def load_state(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"unsupported monitor state: {path}")
    return value


def read_only_connection(path: Path) -> sqlite3.Connection:
    if not path.is_file():
        raise FileNotFoundError(path)
    connection = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def table_exists(connection: sqlite3.Connection, table: str) -> bool:
    return (
        connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)
        ).fetchone()
        is not None
    )


def columns(connection: sqlite3.Connection, table: str) -> set[str]:
    return {str(row[1]) for row in connection.execute(f"PRAGMA table_info({table})")}


def selected(row: sqlite3.Row, names: Iterable[str]) -> dict[str, Any]:
    available = set(row.keys())
    return {name: row[name] for name in names if name in available}


def sqlite_locator(path: Path, table: str, row: str, field: str | None = None) -> str:
    suffix = f"#table={table}&row={row}"
    if field:
        suffix += f"&field={field}"
    return f"sqlite:///{path.resolve().as_posix().lstrip('/')}" + suffix


def scan_hermes(
    path: Path,
    previous: dict[str, Any] | None,
    excluded_roots: set[str] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    changes: list[dict[str, Any]] = []
    connection = read_only_connection(path)
    try:
        session_columns = columns(connection, "sessions")
        safe_session_fields = [
            field
            for field in (
                "id",
                "source",
                "parent_session_id",
                "started_at",
                "ended_at",
                "end_reason",
                "message_count",
                "archived",
                "last_activity_at",
                "profile_name",
            )
            if field in session_columns
        ]
        rows = connection.execute(
            f"SELECT {', '.join(safe_session_fields)} FROM sessions "
            "WHERE source != 'cron'"
        ).fetchall()
        excluded = set(excluded_roots or ())
        parent_by_id = {
            str(row["id"]): (
                None if row["parent_session_id"] is None else str(row["parent_session_id"])
            )
            for row in rows
            if "parent_session_id" in row.keys()
        }
        changed = True
        while changed:
            descendants = {
                native_id
                for native_id, parent_id in parent_by_id.items()
                if parent_id in excluded
            }
            changed = not descendants.issubset(excluded)
            excluded.update(descendants)
        session_hashes = {
            str(row["id"]): digest(selected(row, safe_session_fields))
            for row in rows
            if str(row["id"]) not in excluded
        }
        max_message_id = 0
        activity_sessions: list[str] = []
        if table_exists(connection, "messages"):
            max_message_id = int(
                connection.execute("SELECT COALESCE(MAX(id), 0) FROM messages").fetchone()[0]
            )
            if previous is not None:
                previous_message_id = int(previous.get("max_message_id", 0))
                activity_sessions = sorted(
                    {
                        str(row[0])
                        for row in connection.execute(
                            """
                            SELECT DISTINCT messages.session_id
                            FROM messages
                            JOIN sessions ON sessions.id = messages.session_id
                            WHERE messages.id > ? AND sessions.source != 'cron'
                            """,
                            (previous_message_id,),
                        )
                    }
                    - excluded
                )
    finally:
        connection.close()

    current = {
        "max_message_id": max_message_id,
        "sessions": session_hashes,
    }
    if previous is None:
        return current, changes

    old_sessions = previous.get("sessions", {})
    for native_id in sorted(set(session_hashes) - set(old_sessions)):
        changes.append(
            {
                "provider": "hermes",
                "kind": "session-created",
                "native_id": native_id,
                "source_locator": sqlite_locator(path, "sessions", native_id),
            }
        )
    for native_id in sorted(set(session_hashes) & set(old_sessions)):
        if session_hashes[native_id] != old_sessions[native_id]:
            changes.append(
                {
                    "provider": "hermes",
                    "kind": "session-changed",
                    "native_id": native_id,
                    "source_locator": sqlite_locator(path, "sessions", native_id),
                }
            )
    existing_pairs = {(item["kind"], item["native_id"]) for item in changes}
    for native_id in activity_sessions:
        if ("session-changed", native_id) not in existing_pairs:
            changes.append(
                {
                    "provider": "hermes",
                    "kind": "session-activity",
                    "native_id": native_id,
                    "source_locator": sqlite_locator(
                        path,
                        "messages",
                        f"{int(previous.get('max_message_id', 0)) + 1}-{max_message_id}",
                    ),
                }
            )
    return current, changes


def scan_kanban(path: Path, previous: dict[str, Any] | None) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    changes: list[dict[str, Any]] = []
    connection = read_only_connection(path)
    try:
        task_columns = columns(connection, "tasks")
        safe_task_fields = [
            field
            for field in (
                "id",
                "assignee",
                "status",
                "priority",
                "created_by",
                "created_at",
                "started_at",
                "completed_at",
                "workspace_kind",
                "workspace_path",
                "branch_name",
                "tenant",
                "idempotency_key",
                "project_id",
                "session_id",
                "block_kind",
                "goal_mode",
            )
            if field in task_columns
        ]
        rows = connection.execute(
            f"SELECT {', '.join(safe_task_fields)} FROM tasks"
        ).fetchall()
        task_hashes = {
            str(row["id"]): digest(selected(row, safe_task_fields)) for row in rows
        }
        max_event_id = 0
        new_events: list[sqlite3.Row] = []
        if table_exists(connection, "task_events"):
            max_event_id = int(
                connection.execute("SELECT COALESCE(MAX(id), 0) FROM task_events").fetchone()[0]
            )
            if previous is not None:
                new_events = connection.execute(
                    "SELECT id, task_id, kind FROM task_events WHERE id > ? ORDER BY id",
                    (int(previous.get("max_event_id", 0)),),
                ).fetchall()
    finally:
        connection.close()

    current = {"max_event_id": max_event_id, "tasks": task_hashes}
    if previous is None:
        return current, changes

    old_tasks = previous.get("tasks", {})
    for native_id in sorted(set(task_hashes) - set(old_tasks)):
        changes.append(
            {
                "provider": "kanban",
                "kind": "task-created",
                "native_id": native_id,
                "source_locator": sqlite_locator(path, "tasks", native_id),
            }
        )
    for native_id in sorted(set(task_hashes) & set(old_tasks)):
        if task_hashes[native_id] != old_tasks[native_id]:
            changes.append(
                {
                    "provider": "kanban",
                    "kind": "task-changed",
                    "native_id": native_id,
                    "source_locator": sqlite_locator(path, "tasks", native_id),
                }
            )
    for row in new_events:
        changes.append(
            {
                "provider": "kanban",
                "kind": "task-event",
                "native_id": str(row["task_id"]),
                "event_kind": str(row["kind"]),
                "source_locator": sqlite_locator(path, "task_events", str(row["id"])),
            }
        )
    return current, changes


def scan_kanban_boards(
    default_db: Path,
    boards_root: Path,
    previous: dict[str, Any] | None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    databases = {"default": default_db}
    if boards_root.is_dir():
        databases.update(
            {
                path.parent.name: path
                for path in sorted(boards_root.glob("*/kanban.db"))
                if path.is_file()
            }
        )
    old_boards = {} if previous is None else previous.get("boards", {})
    current_boards: dict[str, Any] = {}
    changes: list[dict[str, Any]] = []
    for board, path in databases.items():
        old = None if previous is None else old_boards.get(board, {})
        snapshot, board_changes = scan_kanban(path, old)
        current_boards[board] = snapshot
        for change in board_changes:
            changes.append({**change, "board": board})
    if previous is not None:
        for board in sorted(set(old_boards) - set(current_boards)):
            changes.append(
                {
                    "provider": "kanban",
                    "kind": "board-missing",
                    "board": board,
                    "native_id": board,
                }
            )
    return {"boards": current_boards}, changes


def scan_omp_history(path: Path, previous: dict[str, Any] | None) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    connection = read_only_connection(path)
    try:
        max_id = int(connection.execute("SELECT COALESCE(MAX(id), 0) FROM history").fetchone()[0])
        rows: list[sqlite3.Row] = []
        if previous is not None:
            rows = connection.execute(
                "SELECT id, session_id FROM history WHERE id > ? ORDER BY id",
                (int(previous.get("max_id", 0)),),
            ).fetchall()
    finally:
        connection.close()
    changes = [
        {
            "provider": "omp",
            "kind": "history-activity",
            "native_id": str(row["session_id"] or f"history-{row['id']}"),
            "source_locator": sqlite_locator(path, "history", str(row["id"])),
        }
        for row in rows
    ]
    return {"max_id": max_id}, changes


def jsonl_files(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    return sorted(path for path in root.rglob("*.jsonl") if path.is_file())


def scan_jsonl_tree(
    provider: str, root: Path, previous: dict[str, Any] | None
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    previous_files = {} if previous is None else previous.get("files", {})
    current_files: dict[str, dict[str, Any]] = {}
    changes: list[dict[str, Any]] = []
    for path in jsonl_files(root):
        resolved = path.resolve()
        key = resolved.as_posix()
        stat = resolved.stat()
        old = previous_files.get(key)
        if (
            old is not None
            and int(old.get("size", -1)) == stat.st_size
            and int(old.get("mtime_ns", -1)) == stat.st_mtime_ns
        ):
            current_files[key] = old
            continue
        current_digest = file_digest(resolved)
        current_files[key] = {
            "size": stat.st_size,
            "mtime_ns": stat.st_mtime_ns,
            "digest": current_digest,
        }
        if previous is None:
            continue
        if old is None:
            kind = "source-created"
            start = 0
        else:
            old_size = int(old["size"])
            prefix_unchanged = (
                stat.st_size >= old_size
                and file_digest(resolved, old_size) == old.get("digest")
            )
            if stat.st_size > old_size and prefix_unchanged:
                kind = "source-appended"
                start = old_size
            elif stat.st_size == old_size and current_digest == old.get("digest"):
                continue
            else:
                kind = "source-rewritten"
                start = 0
        end = stat.st_size
        changes.append(
            {
                "provider": provider,
                "kind": kind,
                "native_id": resolved.stem,
                "source_locator": f"{resolved.as_uri()}#bytes={start}-{end}",
                "source_digest": current_digest,
            }
        )
    if previous is not None:
        for key in sorted(set(previous_files) - set(current_files)):
            changes.append(
                {
                    "provider": provider,
                    "kind": "source-missing",
                    "native_id": Path(key).stem,
                    "source_locator": Path(key).as_uri() + "#bytes=0-0",
                }
            )
    return {"files": current_files}, changes


def receipt_complete(event: dict[str, Any]) -> bool:
    report = Path(event["report_path"])
    receipt = Path(event["receipt_path"])
    if not report.is_file() or not receipt.is_file():
        return False
    try:
        value = json.loads(receipt.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return (
        isinstance(value, dict)
        and value.get("schema_version") == SCHEMA_VERSION
        and value.get("event_id") == event["event_id"]
        and value.get("status") == "completed"
        and value.get("report_path") == event["report_path"]
    )


def create_event(changes: list[dict[str, Any]], reports_dir: Path) -> dict[str, Any]:
    ordered = sorted(changes, key=canonical)
    event_id = digest({"extractor": EXTRACTOR_VERSION, "changes": ordered})[:20]
    return {
        "event_id": event_id,
        "changes": ordered,
        "attempt": 0,
        "report_path": str((reports_dir / f"{event_id}.md").resolve()),
        "receipt_path": str((reports_dir / f"{event_id}.completed.json").resolve()),
    }


def update_queue(
    previous: dict[str, Any] | None,
    snapshots: dict[str, Any],
    changes: list[dict[str, Any]],
    reports_dir: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    pending: list[dict[str, Any]] = []
    completed = [] if previous is None else list(previous.get("completed_event_ids", []))
    if previous is not None:
        for event in previous.get("pending", []):
            if receipt_complete(event):
                if event["event_id"] not in completed:
                    completed.append(event["event_id"])
            else:
                pending.append(dict(event))
    if changes:
        candidate = create_event(changes, reports_dir)
        if candidate["event_id"] not in completed and all(
            event["event_id"] != candidate["event_id"] for event in pending
        ):
            pending.append(candidate)
    for event in pending:
        event["attempt"] = int(event.get("attempt", 0)) + 1
    status = "baseline" if previous is None else ("pending" if pending else "idle")
    candidate_output = {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "pending": pending,
    }
    if previous is not None and not pending and not changes:
        output = previous.get("signal", candidate_output)
    else:
        output = candidate_output
    state = {
        "schema_version": SCHEMA_VERSION,
        "extractor_version": EXTRACTOR_VERSION,
        "snapshots": snapshots,
        "pending": pending,
        "completed_event_ids": completed[-1000:],
        "signal": output,
    }
    return state, output


def scan_and_update(
    *,
    state_path: Path,
    reports_dir: Path,
    hermes_db: Path,
    kanban_db: Path,
    kanban_boards_root: Path,
    codex_sessions: Path,
    codex_archived_sessions: Path,
    omp_history_db: Path,
    omp_sessions: Path,
    excluded_hermes_roots: set[str] | None = None,
) -> dict[str, Any]:
    previous = load_state(state_path)
    old_snapshots = {} if previous is None else previous.get("snapshots", {})
    snapshots: dict[str, Any] = {}
    changes: list[dict[str, Any]] = []
    scanners = (
        (
            "hermes",
            lambda old: scan_hermes(hermes_db, old, excluded_hermes_roots),
        ),
        (
            "kanban",
            lambda old: scan_kanban_boards(kanban_db, kanban_boards_root, old),
        ),
        ("codex", lambda old: scan_jsonl_tree("codex", codex_sessions, old)),
        (
            "codex_archived",
            lambda old: scan_jsonl_tree("codex", codex_archived_sessions, old),
        ),
        ("omp_history", lambda old: scan_omp_history(omp_history_db, old)),
        ("omp_sessions", lambda old: scan_jsonl_tree("omp", omp_sessions, old)),
    )
    for name, scanner in scanners:
        snapshot, found = scanner(old_snapshots.get(name))
        snapshots[name] = snapshot
        changes.extend(found)
    state, output = update_queue(previous, snapshots, changes, reports_dir)
    atomic_json(state_path, state)
    return output


def default_paths() -> dict[str, Path]:
    home = Path.home()
    hermes_home = home / "AppData" / "Local" / "hermes"
    return {
        "state_path": hermes_home / "reconciliation" / "monitor-state.json",
        "reports_dir": hermes_home / "reconciliation" / "reports",
        "hermes_db": hermes_home / "state.db",
        "kanban_db": hermes_home / "kanban.db",
        "kanban_boards_root": hermes_home / "kanban" / "boards",
        "codex_sessions": home / ".codex" / "sessions",
        "codex_archived_sessions": home / ".codex" / "archived_sessions",
        "omp_history_db": home / ".omp" / "agent" / "history.db",
        "omp_sessions": home / ".omp" / "agent" / "sessions",
        "excluded_hermes_roots_file": hermes_home
        / "reconciliation"
        / "excluded-hermes-roots.json",
    }


def load_excluded_roots(path: Path) -> set[str]:
    if not path.is_file():
        return set()
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"excluded Hermes roots must be a JSON string list: {path}")
    return set(value)


def main(argv: list[str] | None = None) -> int:
    defaults = default_paths()
    parser = argparse.ArgumentParser(description=__doc__)
    for name, default in defaults.items():
        parser.add_argument("--" + name.replace("_", "-"), type=Path, default=default)
    args = parser.parse_args(argv)
    try:
        output = scan_and_update(
            state_path=args.state_path,
            reports_dir=args.reports_dir,
            hermes_db=args.hermes_db,
            kanban_db=args.kanban_db,
            kanban_boards_root=args.kanban_boards_root,
            codex_sessions=args.codex_sessions,
            codex_archived_sessions=args.codex_archived_sessions,
            omp_history_db=args.omp_history_db,
            omp_sessions=args.omp_sessions,
            excluded_hermes_roots=load_excluded_roots(
                args.excluded_hermes_roots_file
            ),
        )
        print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    except Exception as exc:
        print(
            json.dumps(
                {
                    "schema_version": SCHEMA_VERSION,
                    "status": "source-error",
                    "error_class": type(exc).__name__,
                },
                sort_keys=True,
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
