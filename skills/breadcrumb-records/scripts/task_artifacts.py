"""Explicit task-file ownership and recoverable closeout; no directory sweeps."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys
import uuid


class Blocked(RuntimeError):
    pass


CONTROL = ".task-artifacts"
PROTECTED = {".git", ".agents", ".codex", ".aws", CONTROL}


def plain(path: Path) -> None:
    if os.path.lexists(path):
        attrs = getattr(path.lstat(), "st_file_attributes", 0)
        if path.is_symlink() or attrs & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400):
            raise Blocked(f"link or reparse point: {path}")


def inside(root: Path, relative: str, *, internal: bool = False) -> Path:
    p = PurePosixPath(relative)
    if (not relative or p.is_absolute() or str(p) != relative or "\\" in relative
            or any(part in {".", ".."} or ":" in part or part.rstrip(" .") != part
                   or re.fullmatch(r"(?i)(con|prn|aux|nul|com[1-9]|lpt[1-9])(\..*)?", part)
                   for part in p.parts)):
        raise Blocked("expected a normalized relative file path")
    if any(part.casefold() in PROTECTED for part in p.parts) and not internal:
        raise Blocked("repository/application control paths are protected")
    current = root
    plain(current)
    for part in p.parts:
        current = current / part
        plain(current)
    if not current.resolve().is_relative_to(root.resolve()):
        raise Blocked("path escapes project root")
    return current


def validate_root(root: Path) -> None:
    for ancestor in (root, *root.parents):
        plain(ancestor)
        if ancestor.name.casefold() in PROTECTED:
            raise Blocked("project root overlaps a repository/application control path")
    if not root.is_dir():
        raise Blocked("explicit existing project root required")


def digest(path: Path) -> str:
    if not path.is_file():
        raise Blocked(f"not a regular file: {path}")
    plain(path)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def atomic(path: Path, value: dict) -> None:
    temporary = path.with_name(path.name + ".tmp-" + uuid.uuid4().hex)
    try:
        with temporary.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(value, stream, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


@contextmanager
def locked(root: Path):
    directory = inside(root, CONTROL, internal=True)
    directory.mkdir(exist_ok=True)
    lock = directory / "operation.lock"
    try:
        descriptor = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise Blocked("another operation owns this project lock; inspect before retrying") from exc
    try:
        with os.fdopen(descriptor, "w") as stream:
            stream.write(str(os.getpid()))
        yield
    finally:
        lock.unlink()


def load(root: Path, task: str) -> tuple[Path, dict]:
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", task):
        raise Blocked("task must be a short lowercase identifier")
    path = inside(root, f"{CONTROL}/{task}.json", internal=True)
    value = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {
        "schema_version": 1, "task": task, "root": str(root), "files": []}
    if (not isinstance(value, dict) or not isinstance(value.get("files"), list)
            or value.get("schema_version") != 1 or value.get("task") != task or value.get("root") != str(root)):
        raise Blocked("ownership record identity mismatch")
    seen = set()
    for row in value["files"]:
        if not isinstance(row, dict):
            raise Blocked("invalid ownership record")
        inside(root, row["path"])
        if (row["path"].casefold() in seen or row["kind"] not in {"scratch", "keep"}
                or row["state"] not in {"present", "archiving", "archived", "restored"}
                or not re.fullmatch(r"[0-9a-f]{64}", row["sha256"])):
            raise Blocked("invalid ownership record")
        seen.add(row["path"].casefold())
    return path, value


def register(root: Path, task: str, files: list[str], kind: str, reason: str) -> dict:
    if not reason.strip():
        raise Blocked("record the evidence/reason for task ownership and retention")
    with locked(root):
        path, value = load(root, task)
        claimed = {row["path"].casefold() for row in value["files"]}
        for other in (root / CONTROL).glob("*.json"):
            if other == path:
                continue
            plain(other)
            _, record = load(root, other.stem)
            claimed.update(row["path"].casefold() for row in record["files"])
        additions = []
        for relative in files:
            source = inside(root, relative)
            if relative.casefold() in claimed:
                raise Blocked(f"already claimed by an ownership record: {relative}")
            claimed.add(relative.casefold())
            additions.append({"path": relative, "kind": kind, "reason": reason,
                              "sha256": digest(source), "state": "present"})
        value["files"].extend(additions)
        atomic(path, value)
        return value


def backup_path(root: Path, task: str, row: dict) -> Path:
    return inside(root, f"{CONTROL}/recovery/{task}/{row['path']}", internal=True)


def preview(root: Path, task: str) -> dict:
    _, value = load(root, task)
    rows = []
    for row in value["files"]:
        source = inside(root, row["path"])
        backup = backup_path(root, task, row)
        source_ok = source.is_file() and digest(source) == row["sha256"]
        backup_ok = backup.is_file() and digest(backup) == row["sha256"]
        blocked = (row["kind"] == "scratch" and
                   ((source.exists() and not source_ok) or (backup.exists() and not backup_ok)
                    or (not source_ok and not backup_ok)
                    or (row["state"] == "archived" and source.exists())))
        rows.append({**row, "action": "blocked" if blocked else (
            "keep" if row["kind"] == "keep" or row["state"] == "restored" else "archive"),
                     "source_matches": source_ok, "recovery_matches": backup_ok,
                     "recovery": backup.relative_to(root).as_posix()})
    return {"task": task, "files": rows}


def copy_new(source: Path, target: Path, expected: str) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    data = source.read_bytes()
    if hashlib.sha256(data).hexdigest() != expected:
        raise Blocked("source changed before recovery copy")
    # Exclusive creation preserves an unexpected target, including a racing writer.
    with target.open("xb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    if digest(target) != expected:
        raise Blocked("recovery copy did not verify; original retained")


def archive(root: Path, task: str, *, references_checked: bool) -> dict:
    if not references_checked:
        raise Blocked("check references, completion and active users before archive")
    with locked(root):
        path, value = load(root, task)
        plan = preview(root, task)
        if any(row["action"] == "blocked" for row in plan["files"]):
            raise Blocked("a claimed file changed or lost recovery; no files archived")
        for row in value["files"]:
            if row["kind"] != "scratch" or row["state"] in {"archived", "restored"}:
                continue
            source = inside(root, row["path"])
            backup = backup_path(root, task, row)
            row["state"] = "archiving"
            atomic(path, value)  # Persist intent before moving any bytes.
            if not backup.exists():
                copy_new(source, backup, row["sha256"])
            if source.exists():
                before = source.stat()
                if digest(source) != row["sha256"] or digest(backup) != row["sha256"]:
                    raise Blocked("file changed during archive; original/recovery retained")
                now = source.stat()
                if (before.st_ino, before.st_size, before.st_mtime_ns) != (now.st_ino, now.st_size, now.st_mtime_ns):
                    raise Blocked("file changed during archive; original retained")
                source.unlink()
            row["state"] = "archived"
            atomic(path, value)
        return preview(root, task)


def restore(root: Path, task: str) -> dict:
    with locked(root):
        path, value = load(root, task)
        selected = [row for row in value["files"] if row["state"] in {"archiving", "archived"}]
        for row in selected:
            source, backup = inside(root, row["path"]), backup_path(root, task, row)
            if not backup.exists() or digest(backup) != row["sha256"]:
                raise Blocked("verified recovery is missing; no files restored")
            if source.exists() and digest(source) != row["sha256"]:
                raise Blocked("restore would replace a changed file; no files restored")
        for row in selected:
            source, backup = inside(root, row["path"]), backup_path(root, task, row)
            if not source.exists():
                copy_new(backup, source, row["sha256"])
            row["state"] = "restored"
            atomic(path, value)
        return preview(root, task)  # Recovery copies remain; no purge command.


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("register", "plan", "archive", "restore"))
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--task", required=True)
    parser.add_argument("--file", action="append", default=[])
    parser.add_argument("--kind", choices=("scratch", "keep"), default="scratch")
    parser.add_argument("--reason", default="")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--references-checked", action="store_true")
    args = parser.parse_args(argv)
    try:
        root = Path(os.path.abspath(args.root))
        validate_root(root)
        if args.action == "register":
            if not args.file:
                raise Blocked("name at least one task-owned file")
            result = register(root, args.task, args.file, args.kind, args.reason)
        elif args.action == "archive" and args.apply:
            result = archive(root, args.task, references_checked=args.references_checked)
        elif args.action == "restore" and args.apply:
            result = restore(root, args.task)
        else:
            result = preview(root, args.task)
        print(json.dumps(result, indent=2))
        return 0
    except (Blocked, OSError, ValueError, KeyError, TypeError) as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
