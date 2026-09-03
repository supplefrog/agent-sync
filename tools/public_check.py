#!/usr/bin/env python
"""Reject private paths, likely credentials, and generated evidence before publication."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

EXCLUDED_DIRS = {
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
    args = parser.parse_args(argv)
    findings = scan(args.repo.resolve())
    for path, line, rule in findings:
        print(f"{path}:{line}: {rule}", file=sys.stderr)
    if findings:
        print(f"FAIL {len(findings)} public-safety finding(s)", file=sys.stderr)
        return 1
    print("PASS public-safety scan")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
