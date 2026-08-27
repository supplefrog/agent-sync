"""Deterministically load and hash a skill plus its linked text references."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
TEXT_SUFFIXES = {".md", ".txt", ".json", ".yaml", ".yml"}
MAX_LINKED_BYTES = 100_000


def linked_files(candidate: Path) -> list[Path]:
    root = candidate.parent.resolve()
    queue = [candidate.resolve()]
    found: set[Path] = {candidate.resolve()}
    linked: list[Path] = []
    total = 0
    while queue:
        current = queue.pop(0)
        text = current.read_text(encoding="utf-8")
        for raw in LINK_RE.findall(text):
            ref = raw.split("#", 1)[0].strip()
            if not ref or "://" in ref or ref.startswith(("#", "/")):
                continue
            path = (current.parent / ref).resolve()
            try:
                path.relative_to(root)
            except ValueError:
                continue
            if path in found or not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
                continue
            size = path.stat().st_size
            if total + size > MAX_LINKED_BYTES:
                raise ValueError("linked candidate references exceed size limit")
            total += size
            found.add(path)
            linked.append(path)
            queue.append(path)
    return sorted(linked, key=lambda path: path.relative_to(root).as_posix())


def candidate_files(candidate: Path) -> list[Path]:
    return [candidate.resolve(), *linked_files(candidate)]


def candidate_hash(candidate: Path) -> str:
    root = candidate.parent.resolve()
    digest = hashlib.sha256()
    for path in candidate_files(candidate):
        rel = path.relative_to(root).as_posix().encode("utf-8")
        digest.update(rel)
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def candidate_prompt_text(candidate: Path) -> str:
    root = candidate.parent.resolve()
    sections = []
    for path in candidate_files(candidate):
        rel = path.relative_to(root).as_posix()
        sections.append(f"<FILE path=\"{rel}\">\n{path.read_text(encoding='utf-8')}\n</FILE>")
    return "\n\n".join(sections)
