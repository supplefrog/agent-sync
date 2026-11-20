"""Resolve saved T3 links and archive matching conversations via Codex app-server."""

import argparse
import json
import os
from pathlib import Path
from queue import Empty, Queue
import sqlite3
import subprocess
from threading import Thread
from uuid import UUID


def read_only(path):
    return sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)


def inventory(t3_db, codex_db, thread_ids):
    with read_only(t3_db) as database:
        database.execute("ATTACH DATABASE ? AS codex", (codex_db.resolve().as_uri() + "?mode=ro",))
        rows = database.execute(
            """
            SELECT t.thread_id, t.archived_at, t.deleted_at, t.default_provider,
                   p.provider_thread_id,
                   json_extract(p.payload_json, '$.nativeThreadRef.nativeId'),
                   json_extract(p.payload_json, '$.nativeThreadRef.strength'), c.archived
            FROM orchestration_v2_projection_threads t
            LEFT JOIN orchestration_v2_projection_provider_threads p
                ON p.thread_id = t.thread_id AND p.driver = 'codex'
            LEFT JOIN codex.threads c ON c.id = json_extract(p.payload_json, '$.nativeThreadRef.nativeId')
            WHERE t.thread_id IN (SELECT value FROM json_each(?))
            """,
            (json.dumps(thread_ids),),
        ).fetchall()
    result = {}
    for t3_id, archived, deleted, provider, provider_thread, native_id, strength, native_archived in rows:
        state = result.setdefault(t3_id, {"t3_archived": archived is not None, "codex": {}, "unresolved": False})
        if deleted or (native_id is None and (provider == "codex" or provider_thread is not None)):
            state["unresolved"] = True
        if native_id is None:
            continue
        if strength != "strong" or native_archived is None:
            state["unresolved"] = True
            continue
        state["codex"][native_id] = bool(native_archived)
    for thread_id in thread_ids:
        result.setdefault(thread_id, {"t3_archived": False, "codex": {}, "unresolved": True})
    return result


def shared_active_links(t3_db, native_ids):
    with read_only(t3_db) as database:
        return {
            row[0] for row in database.execute(
                """
                SELECT DISTINCT json_extract(p.payload_json, '$.nativeThreadRef.nativeId')
                FROM orchestration_v2_projection_provider_threads p
                JOIN orchestration_v2_projection_threads t ON t.thread_id = p.thread_id
                WHERE p.driver = 'codex' AND t.archived_at IS NULL AND t.deleted_at IS NULL
                    AND json_extract(p.payload_json, '$.nativeThreadRef.nativeId') IN
                        (SELECT value FROM json_each(?))
                """,
                (json.dumps(sorted(native_ids)),),
            )
        }


def archive(executable, ids):
    with subprocess.Popen(
        [executable, "app-server", "--listen", "stdio://"],
        text=True, encoding="utf-8", stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    ) as server:
        replies = Queue()

        def receive():
            try:
                for line in server.stdout:
                    replies.put(json.loads(line))
            finally:
                replies.put(None)

        Thread(target=receive, daemon=True).start()

        def send(message):
            server.stdin.write(json.dumps(message) + "\n")
            server.stdin.flush()

        def request(request_id, method, params):
            send({"id": request_id, "method": method, "params": params})
            while True:
                reply = replies.get(timeout=30)
                if reply is None:
                    raise RuntimeError("Codex app-server closed its output")
                if reply.get("id") == request_id:
                    if "error" in reply:
                        raise RuntimeError(reply["error"]["message"])
                    return reply["result"]

        errors = {}
        try:
            request(0, "initialize", {"clientInfo": {"name": "t3_archive_batch", "version": "1.0"}})
            send({"method": "initialized"})
            for index, native_id in enumerate(ids, start=1):
                try:
                    UUID(native_id)
                    request(index, "thread/archive", {"threadId": native_id})
                except (ValueError, RuntimeError) as error:
                    errors[native_id] = str(error)
        finally:
            server.stdin.close()
            try:
                server.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server.kill()
        return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ids_file", type=Path, help="JSON array of exact T3 thread IDs")
    parser.add_argument("--t3-db", type=Path, default=Path.home() / ".t3/userdata/statev2.sqlite")
    codex_home = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")
    parser.add_argument("--codex-db", type=Path, default=codex_home / "state_5.sqlite")
    parser.add_argument("--codex-executable", default="codex")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    ids = json.loads(args.ids_file.read_text(encoding="utf-8-sig"))
    if not isinstance(ids, list) or not all(isinstance(value, str) and value for value in ids):
        parser.error("ids_file must contain a JSON array of nonempty strings")
    before = inventory(args.t3_db, args.codex_db, ids)
    errors = {}
    if args.apply:
        if args.codex_db.resolve() != (codex_home / "state_5.sqlite").resolve():
            parser.error("the Codex database must match the active CODEX_HOME state_5.sqlite")
        pending = {native_id for row in before.values() if row["t3_archived"] and not row["unresolved"]
                   for native_id, archived in row["codex"].items() if not archived}
        shared = shared_active_links(args.t3_db, pending) if pending else set()
        for native_id in shared:
            errors[native_id] = "The Codex conversation is also linked to an unarchived T3 thread"
        pending -= shared
        if pending:
            try:
                errors.update(archive(args.codex_executable, sorted(pending)))
            except (Empty, OSError, RuntimeError) as error:
                errors["app-server"] = str(error) or "Timed out while waiting for Codex app-server"
    after = inventory(args.t3_db, args.codex_db, ids) if args.apply else before
    print(json.dumps({"threads": after, "errors": errors}, indent=2))
    partial = any(not row["t3_archived"] or row["unresolved"] or not all(row["codex"].values())
                  for row in after.values())
    return int(args.apply and (bool(errors) or partial))


if __name__ == "__main__":
    raise SystemExit(main())
