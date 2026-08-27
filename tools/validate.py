#!/usr/bin/env python
"""Validate portable Agent Skills without executing candidate code."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")


def frontmatter(text: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end < 0:
        return {}, text
    values: dict[str, str] = {}
    for raw in text[4:end].splitlines():
        if not raw or raw[0].isspace() or ":" not in raw:
            continue
        key, value = raw.split(":", 1)
        values[key.strip()] = value.strip().strip('"\'')
    return values, text[end + 5 :]


def validate_skill(path: Path) -> list[str]:
    errors: list[str] = []
    text = path.read_text(encoding="utf-8")
    meta, body = frontmatter(text)
    name = meta.get("name", "")
    description = meta.get("description", "")

    if not name:
        errors.append("missing frontmatter name")
    elif not NAME_RE.fullmatch(name) or len(name) > 64:
        errors.append("name must be <=64 lowercase kebab-case characters")
    elif name != path.parent.name:
        errors.append(f"name '{name}' does not match directory '{path.parent.name}'")

    if not description:
        errors.append("missing frontmatter description")
    elif len(description) > 1024:
        errors.append("description exceeds 1024 characters")

    if not meta.get("license"):
        errors.append("missing license for public distribution")
    if not body.strip():
        errors.append("empty skill body")
    if len(text.splitlines()) > 500:
        errors.append("SKILL.md exceeds 500 lines; move detail into references")

    for target in LINK_RE.findall(body):
        target = target.split("#", 1)[0].strip()
        if not target or "://" in target or target.startswith(("#", "mailto:")):
            continue
        resolved = (path.parent / target).resolve()
        try:
            resolved.relative_to(path.parent.resolve())
        except ValueError:
            errors.append(f"reference escapes skill directory: {target}")
            continue
        if not resolved.exists():
            errors.append(f"missing referenced file: {target}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="*")
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    requested = [Path(item).resolve() for item in args.paths]
    if not requested:
        registry = json.loads((repo / "registry.json").read_text(encoding="utf-8"))
        requested = [repo / "skills" / item["name"] for item in registry["skills"]]
    files: list[Path] = []
    for root in requested:
        files.extend([root] if root.name == "SKILL.md" else sorted(root.rglob("SKILL.md")))
    if not files:
        print(f"no SKILL.md files under {root}", file=sys.stderr)
        return 2
    failures = 0
    for path in files:
        errors = validate_skill(path)
        if errors:
            failures += 1
            print(f"FAIL {path}")
            for error in errors:
                print(f"  - {error}")
        else:
            print(f"PASS {path}")
    print(f"{len(files) - failures}/{len(files)} skills valid")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
