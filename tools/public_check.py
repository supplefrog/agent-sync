#!/usr/bin/env python
"""Reject private paths, likely credentials, and generated evidence before publication."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

EXCLUDED_DIRS = {
    ".venv",
    ".git",
    ".evals",
    ".hermes",
    ".pytest-cache",
    ".pytest_cache",
    ".staging",
    ".worktrees",
    "__pycache__",
    "render",
}
EXCLUDED_PREFIXES = {("evals", "reports", "raw")}
TEXT_SUFFIXES = {"", ".md", ".json", ".py", ".toml", ".yaml", ".yml", ".txt"}
RULES = {
    "windows-user-path": re.compile(
        r"(?i)[a-z]:(?:[\\/]|\\\\)(?:users|documents and settings)(?:[\\/]|\\\\)"
    ),
    "posix-user-path": re.compile(
        r"(?<![A-Za-z0-9_])/(?:home/[A-Za-z0-9._-]+|root)(?:/[A-Za-z0-9._~+-]*)?"
    ),
    "credential-assignment": re.compile(
        r"(?i)(?:api[_-]?key|access[_-]?token|password|client[_-]?secret)\s*[:=]\s*['\"][^{}<>\s'\"]{8,}"
    ),
    "token-prefix": re.compile(
        r"(?<![A-Za-z0-9_-])(?:gh[pousr]_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9_-]{20,})"
    ),
}

DEFAULT_ALLOWLIST = Path("evidence/public-safety-allowlist.json")


def _line_sha256(repo: Path, path: Path, line: int) -> str:
    lines = (repo / path).read_text(encoding="utf-8").splitlines()
    if line < 1 or line > len(lines):
        raise ValueError(f"reviewed public-safety line is absent: {path}:{line}")
    return hashlib.sha256(lines[line - 1].encode()).hexdigest()


def reviewed_findings(repo: Path, path: Path | None = None) -> set[tuple[Path, int, str]]:
    """Load exact, content-bound false positives; stale or malformed reviews fail closed."""
    source = path or repo / DEFAULT_ALLOWLIST
    if not source.is_file():
        return set()
    value = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("schema_version") != 1 or not isinstance(value.get("findings"), list):
        raise ValueError(f"invalid public-safety allowlist: {source}")
    reviewed: set[tuple[Path, int, str]] = set()
    for item in value["findings"]:
        if not isinstance(item, dict) or set(item) != {"path", "line", "rule", "line_sha256", "disposition"}:
            raise ValueError(f"invalid public-safety allowlist row: {source}")
        relative = Path(item["path"])
        if relative.is_absolute() or ".." in relative.parts or item["rule"] not in RULES:
            raise ValueError(f"unsafe public-safety allowlist row: {source}")
        if _line_sha256(repo, relative, item["line"]) != item["line_sha256"]:
            raise ValueError(f"stale public-safety allowlist row: {relative}:{item['line']}")
        key = (relative, item["line"], item["rule"])
        if key in reviewed:
            raise ValueError(f"duplicate public-safety allowlist row: {relative}:{item['line']}")
        reviewed.add(key)
    return reviewed


def scan(repo: Path) -> list[tuple[Path, int, str]]:
    findings: list[tuple[Path, int, str]] = []
    for path in sorted(repo.rglob("*")):
        relative = path.relative_to(repo)
        if (
            not path.is_file()
            or any(part in EXCLUDED_DIRS for part in relative.parts)
            or any(relative.parts[: len(prefix)] == prefix for prefix in EXCLUDED_PREFIXES)
        ):
            continue
        if path.name != ".gitignore" and path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue
        for number, line in enumerate(lines, 1):
            for name, pattern in RULES.items():
                if pattern.search(line):
                    findings.append((relative, number, name))
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--allowlist", type=Path)
    args = parser.parse_args(argv)
    repo = args.repo.resolve()
    findings = scan(repo)
    try:
        reviewed = reviewed_findings(repo, args.allowlist.resolve() if args.allowlist else None)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"FAIL {exc}", file=sys.stderr)
        return 1
    stale = reviewed - set(findings)
    if stale:
        for path, line, rule in sorted(stale, key=lambda row: (str(row[0]), row[1], row[2])):
            print(f"{path}:{line}: stale-reviewed-{rule}", file=sys.stderr)
        print(f"FAIL {len(stale)} stale public-safety review(s)", file=sys.stderr)
        return 1
    findings = [finding for finding in findings if finding not in reviewed]
    for path, line, rule in findings:
        print(f"{path}:{line}: {rule}", file=sys.stderr)
    if findings:
        print(f"FAIL {len(findings)} public-safety finding(s)", file=sys.stderr)
        return 1
    print(f"PASS public-safety scan ({len(reviewed)} exact reviewed false positive(s))")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
