#!/usr/bin/env python
"""Delete one complete Hermes compression lineage and verify it is gone."""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

from hermes_constants import get_hermes_home


def placeholders(items: list[str]) -> str:
    return ",".join("?" for _ in items)


def root_for(conn: sqlite3.Connection, sid: str) -> str:
    row = conn.execute(
        """with recursive a(id,parent_session_id,depth) as (
             select id,parent_session_id,0 from sessions where id=?
             union all
             select p.id,p.parent_session_id,a.depth+1
             from sessions p join a on a.parent_session_id=p.id
           ) select id from a order by depth desc limit 1""",
        (sid,),
    ).fetchone()
    if row is None:
        raise RuntimeError(f"Session vanished during lookup: {sid}")
    return row[0]


def descendants(conn: sqlite3.Connection, root: str) -> list[str]:
    return [
        row[0]
        for row in conn.execute(
            """with recursive d(id) as (
                 select id from sessions where id=?
                 union
                 select s.id from sessions s join d on s.parent_session_id=d.id
               ) select id from d""",
            (root,),
        )
    ]


def stop_windows_workers(ids: list[str]) -> list[int]:
    if os.name != "nt" or not ids:
        return []
    quoted = ",".join("'" + sid.replace("'", "''") + "'" for sid in ids)
    # Match only Python slash workers; otherwise the query matches its own PowerShell command line.
    script = (
        f"$ids=@({quoted}); "
        "$p=Get-CimInstance Win32_Process | Where-Object { "
        "$cmd=$_.CommandLine; $_.Name -eq 'python.exe' -and "
        "$cmd -match 'tui_gateway.slash_worker' -and "
        "(@($ids | Where-Object { $cmd -like ('*'+$_+'*') }).Count -gt 0) }; "
        "$pids=@($p.ProcessId); if($pids.Count -gt 0){Stop-Process -Id $pids -Force}; "
        "$pids | ForEach-Object { Write-Output $_ }"
    )
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-Command", script],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        print("warning: worker cleanup failed: " + result.stderr.strip(), file=sys.stderr)
        return []
    return [int(line) for line in result.stdout.splitlines() if line.strip().isdigit()]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("query", help="Exact session id or title")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--keep-workers", action="store_true")
    args = parser.parse_args()

    db = Path(get_hermes_home()) / "state.db"
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row

    if conn.execute("select 1 from sessions where id=?", (args.query,)).fetchone():
        seeds = [args.query]
    else:
        seeds = [
            row[0]
            for row in conn.execute(
                "select id from sessions where title=? or title glob ? order by started_at",
                (args.query, args.query + " #[0-9]*"),
            )
        ]
    if not seeds:
        print(f"No matching session id/title: {args.query}", file=sys.stderr)
        return 2

    roots = list(dict.fromkeys(root_for(conn, sid) for sid in seeds))
    if len(roots) != 1:
        print("Title matched unrelated compression roots; use an exact session id:", file=sys.stderr)
        for root in roots:
            print(root, file=sys.stderr)
        return 3

    ids = descendants(conn, roots[0])
    rows = [
        dict(row)
        for row in conn.execute(
            f"select id,title,parent_session_id,started_at,ended_at,message_count "
            f"from sessions where id in ({placeholders(ids)}) order by started_at",
            ids,
        )
    ]
    message_count = conn.execute(
        f"select count(*) from messages where session_id in ({placeholders(ids)})", ids
    ).fetchone()[0]

    if args.dry_run:
        print(json.dumps({"db": str(db), "sessions": rows, "messages": message_count}, indent=2))
        return 0

    with conn:
        conn.executemany("delete from compression_locks where session_id=?", ((sid,) for sid in ids))
        conn.executemany("delete from messages where session_id=?", ((sid,) for sid in ids))
        # Delete children before parents in case foreign-key enforcement changes later.
        conn.executemany("delete from sessions where id=?", ((sid,) for sid in reversed(ids)))

    remaining_sessions = conn.execute(
        f"select count(*) from sessions where id in ({placeholders(ids)})", ids
    ).fetchone()[0]
    remaining_messages = conn.execute(
        f"select count(*) from messages where session_id in ({placeholders(ids)})", ids
    ).fetchone()[0]
    if remaining_sessions or remaining_messages:
        raise RuntimeError(
            f"Verification failed: {remaining_sessions} sessions, {remaining_messages} messages remain"
        )

    killed = [] if args.keep_workers else stop_windows_workers(ids)
    print(
        json.dumps(
            {
                "deleted_session_ids": ids,
                "deleted_sessions": len(ids),
                "deleted_messages": message_count,
                "killed_worker_pids": killed,
                "verified": True,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
