"""Preview or assign one stored Codex thread through the native project API."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import time
import uuid


class AssociationError(RuntimeError):
    pass


class RPC:
    def __init__(self, executable: Path):
        self.process = subprocess.Popen([str(executable), "app-server", "--listen", "stdio://"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, encoding="utf-8")
        self.responses = queue.Queue()
        self.sequence = 0
        self.reader = threading.Thread(target=self._read, daemon=True)
        self.reader.start()

    def _read(self):
        try:
            for line in self.process.stdout:
                self.responses.put(json.loads(line))
        except (ValueError, OSError):
            pass
        finally:
            self.responses.put(None)

    def notify(self, method, params=None):
        value = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            value["params"] = params
        self.process.stdin.write(json.dumps(value) + "\n")
        self.process.stdin.flush()

    def call(self, method, params):
        self.sequence += 1
        self.process.stdin.write(json.dumps({"jsonrpc": "2.0", "id": self.sequence,
            "method": method, "params": params}) + "\n")
        self.process.stdin.flush()
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            try:
                reply = self.responses.get(timeout=max(.01, deadline - time.monotonic()))
            except queue.Empty as exc:
                raise AssociationError(f"{method} timed out; read back before retrying a write") from exc
            if reply is None:
                raise AssociationError(f"{method} connection closed; read back before retrying a write")
            if reply.get("id") != self.sequence:
                continue  # Notifications/approvals are never answered automatically.
            if "error" in reply:
                raise AssociationError(f"{method} refused: {reply['error'].get('message', 'native error')}")
            return reply["result"]
        raise AssociationError(f"{method} timed out; inspect before retrying")

    def close(self):
        self.process.stdin.close()
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.terminate()
            self.process.wait(timeout=5)
        self.reader.join(timeout=1)
        self.process.stdout.close()


@contextmanager
def connected(executable):
    client = RPC(executable)
    try:
        client.call("initialize", {"clientInfo": {"name": "agent-sync-project", "version": "1"},
            "capabilities": {"experimentalApi": True}})
        client.notify("initialized")
        yield client
    finally:
        client.close()


def normalized(value):
    return os.path.normcase(os.path.abspath(value))


def projects(client):
    rows, seen, cursor = [], set(), None
    for _ in range(100):
        params = {"limit": 100}
        if cursor:
            params["cursor"] = cursor
        result = client.call("project/list", params)
        rows.extend(result["data"])
        cursor = result.get("nextCursor")
        if not cursor:
            return rows
        if cursor in seen:
            break
        seen.add(cursor)
    raise AssociationError("project inventory pagination incomplete; no write permitted")


def thread(client, thread_id):
    return client.call("thread/read", {"threadId": thread_id, "includeTurns": False})["thread"]


def associate(client, *, root, name, thread_id, apply=False, expect_project=None, key=None):
    if not root.is_dir():
        raise AssociationError("create/verify the chosen project directory first")
    before = thread(client, thread_id)  # Must be persisted; never resume or create a thread.
    current = before.get("projectId") or None
    matching = [p for p in projects(client) if any(normalized(r["path"]) == normalized(root) for r in p["roots"])]
    if len(matching) > 1:
        raise AssociationError("multiple native projects own this root; resolve the destination first")
    project = matching[0] if matching else None
    report = {"thread_id": thread_id, "root": str(root), "previous_project_id": current,
        "project_id": project["id"] if project else None, "action": "reuse" if project else "create",
        "status": "planned", "cwd_changed": False, "ui_refresh_verified": False}
    if not apply:
        return report
    if expect_project != (current or "none"):
        raise AssociationError("thread membership changed or expected prior ID is missing; preview again")
    if not project:
        try:
            uuid.UUID(key or "")
        except ValueError as exc:
            raise AssociationError("creation requires a retained UUID idempotency key") from exc
        project = client.call("project/create", {"idempotencyKey": key, "name": name,
            "roots": [{"path": str(root)}]})["project"]
    project = client.call("project/read", {"projectId": project["id"]})["project"]
    if not any(normalized(r["path"]) == normalized(root) for r in project["roots"]):
        raise AssociationError("native project root changed; no thread assignment performed")
    observed = thread(client, thread_id)
    if observed.get("projectId") != before.get("projectId") or observed.get("cwd") != before.get("cwd"):
        raise AssociationError("thread changed during preflight; any created project remains for inspection")
    if current != project["id"]:
        client.call("thread/metadata/update", {"threadId": thread_id, "projectId": project["id"]})
    after = thread(client, thread_id)
    if after.get("projectId") != project["id"] or after.get("cwd") != before.get("cwd"):
        raise AssociationError("assignment readback disagreed; inspect before retrying")
    report.update(status="persisted", project_id=project["id"])
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--codex-exe", type=Path, required=True, help="verified installed native executable")
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--thread-id", required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--expect-project", help="prior project ID from preview, or none")
    parser.add_argument("--idempotency-key", help="retain one UUID across uncertain project creation")
    args = parser.parse_args(argv)
    try:
        with connected(args.codex_exe.resolve(strict=True)) as client:
            result = associate(client, root=args.root.resolve(strict=True), name=args.name,
                thread_id=args.thread_id, apply=args.apply, expect_project=args.expect_project,
                key=args.idempotency_key)
        print(json.dumps(result, indent=2))
        return 0
    except (AssociationError, OSError, ValueError, KeyError, TypeError) as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
