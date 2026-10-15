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


def local_links(text: str) -> set[str]:
    return {target.strip() for target in LINK_RE.findall(text)
            if target.strip() and not target.strip().startswith(('#', 'mailto:'))
            and '://' not in target}


def loading_signals(text: str, before: str | None = None) -> dict:
    """Review signals, never a size-based validity or quality verdict."""
    _, body = frontmatter(text.replace('\r\n', '\n'))
    words = len(body.split())
    old_words = len(frontmatter((before or '').replace('\r\n', '\n'))[1].split())
    reasons = []
    if words >= 3000:
        reasons.append('entrypoint has at least 3000 body words')
    if len(body.splitlines()) > 500:
        reasons.append('entrypoint has more than 500 body lines')
    if before is not None and words - old_words >= 500 and words >= old_words * 1.25:
        reasons.append('entrypoint grew by at least 500 body words and 25 percent')
    return {'body_words': words, 'body_bytes': len(body.encode('utf-8')),
            'body_lines': len(body.splitlines()), 'before_body_words': old_words if before is not None else None,
            'review_reasons': reasons}


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


def validate_skill(path: Path, *, expected_name: str | None = None) -> list[str]:
    errors: list[str] = []
    text = path.read_text(encoding="utf-8")
    meta, body = frontmatter(text)
    name = meta.get("name", "")
    description = meta.get("description", "")

    if not name:
        errors.append("missing frontmatter name")
    elif not NAME_RE.fullmatch(name) or len(name) > 64:
        errors.append("name must be <=64 lowercase kebab-case characters")
    elif name != (expected_name or path.parent.name):
        label = "owner" if expected_name else "directory"
        errors.append(f"name '{name}' does not match {label} '{expected_name or path.parent.name}'")

    if not description:
        errors.append("missing frontmatter description")
    elif len(description) > 1024:
        errors.append("description exceeds 1024 characters")

    if not meta.get("license"):
        errors.append("missing license for public distribution")
    if not body.strip():
        errors.append("empty skill body")
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
        signals = loading_signals(path.read_text(encoding='utf-8'))
        if signals['review_reasons']:
            print('  REVIEW loading: ' + '; '.join(signals['review_reasons']))
    print(f"{len(files) - failures}/{len(files)} skills valid")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
