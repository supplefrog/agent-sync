#!/usr/bin/env python
"""Review Hermes's existing skill queue locally; never copy proposals into Agent Sync."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path


_ID = re.compile(r"[0-9a-f]{8}")


def validate_id(value: str) -> str:
    if not _ID.fullmatch(value):
        raise ValueError("Expected one native eight-character pending ID, never 'all'.")
    return value


def _digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def pending_findings(home: Path) -> list[dict]:
    """Metadata only: even skill names and summaries may contain private material."""
    findings = []
    for path in sorted((Path(home) / "pending/skills").glob("*.json")):
        pid = path.stem if _ID.fullmatch(path.stem) else "invalid-record"
        findings.append({
            "surface": "skill-proposals", "host": "hermes", "target": pid,
            "pending_id": pid, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "route": "cross-agent-surface-engineering", "disposition": "review-required",
            "auto_apply_eligible": False,
            "reason": "Review locally with tools/hermes_skill_review.py; pending is not approved.",
        })
    return findings


def _tree(path: Path) -> dict:
    """Bind approval to the whole reviewed package, including deletion/support files."""
    if not path.exists():
        return {"path": str(path), "files": None}
    files = {}
    for file in sorted(path.rglob("*")):
        if file.is_symlink() or (hasattr(file, "is_junction") and file.is_junction()):
            raise ValueError("Linked package contents require owner-specific review.")
        if file.is_file():
            files[file.relative_to(path).as_posix()] = hashlib.sha256(file.read_bytes()).hexdigest()
    return {"path": str(path.resolve()), "files": files}


def inspect_pending(home: Path, pid: str, wa, smt) -> dict:
    validate_id(pid)
    record = wa.get_pending(wa.SKILLS, pid)
    if not record or record.get("id") != pid or record.get("subsystem") != wa.SKILLS:
        raise ValueError("Missing or malformed pending skill record.")
    payload = record["payload"]
    operations = payload.get("operations") or [payload]
    if not isinstance(operations, list) or not operations:
        raise ValueError("Invalid operations.")
    packages, diffs, native = {}, [], True
    registry = json.loads((Path(__file__).resolve().parents[1] / "registry.json").read_text(encoding="utf-8"))
    managed_names = {item["name"] for item in registry["skills"]}
    for op in operations:
        name = op.get("name") or payload.get("name")
        if not isinstance(name, str) or not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", name):
            raise ValueError("Invalid skill name.")
        found = smt._find_skill(name)
        native = native and name not in managed_names
        if found:
            path = Path(found["path"]).resolve()
            native = native and path.is_relative_to((home / "skills").resolve())
            packages[name] = _tree(path)
        else:
            # Creation destination has additional host/project config; promote new owners
            # through canonical source rather than guessing their placement here.
            native = False
            packages[name] = None
        diffs.append(wa.skill_pending_diff({"payload": {**op, "name": name}}))
    return {"pending_id": pid, "record": record, "diffs": diffs,
            "native_apply_allowed": native,
            "review_token": _digest({"record": record, "packages": packages})}


def run(action: str, home: Path, pid: str, expected: str | None, wa, smt) -> dict:
    review = inspect_pending(home, pid, wa, smt)
    if action == "show":
        return review
    if not expected or expected != review["review_token"]:
        raise ValueError("Proposal or skill changed (or no review token); show and review again.")
    if action == "approve":
        if not review["native_apply_allowed"]:
            raise ValueError("New/external owner: edit reviewed canonical source, deploy, then reject this proposal.")
        result = json.loads(smt.apply_skill_pending(review["record"]["payload"]))
        if not result.get("success") or result.get("staged"):
            raise ValueError(f"Native apply failed; proposal retained: {result}")
    if not wa.discard_pending(wa.SKILLS, pid) or wa.get_pending(wa.SKILLS, pid) is not None:
        raise RuntimeError("Native action finished but queue removal failed; inspect before retrying.")
    return {"result": "applied" if action == "approve" else "rejected", "pending_id": pid}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("list", "show", "approve", "reject"))
    parser.add_argument("pending_id", nargs="?")
    parser.add_argument("--home", type=Path, default=os.environ.get("HERMES_HOME"))
    parser.add_argument("--runtime", type=Path, help="Hermes source checkout; use its Python environment")
    parser.add_argument("--review-token", help="Token from the exact locally reviewed show result")
    args = parser.parse_args(argv)
    if not args.home:
        parser.error("Set HERMES_HOME or pass --home; another profile is never guessed.")
    home = args.home.resolve()
    if args.action == "list":
        report = pending_findings(home)
    else:
        validate_id(args.pending_id or "")
        runtime = args.runtime or home / "hermes-agent"
        if not (runtime / "tools/write_approval.py").is_file():
            parser.error("Pass --runtime pointing to the installed Hermes source checkout.")
        os.environ["HERMES_HOME"] = str(home)
        sys.path.insert(0, str(runtime.resolve()))
        from tools import write_approval as wa, skill_manager_tool as smt
        report = run(args.action, home, args.pending_id, args.review_token, wa, smt)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError, KeyError, TypeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
