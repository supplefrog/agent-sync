"""Bind deployed skill bytes separately from the text included in a prompt."""

from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
TEXT_SUFFIXES = {".md", ".txt", ".json", ".yaml", ".yml"}
MAX_LINKED_BYTES = 100_000


def harness_hash(harness: Path) -> str:
    """Bind the evaluator and its local behavior-defining imports.

    Other standalone harnesses retain their file identity. Runtime and provider
    versions are recorded separately from this local implementation digest.
    """
    if harness.name != "eval.py":
        return hashlib.sha256(harness.read_bytes()).hexdigest()
    digest = hashlib.sha256()
    for name in ("artifact_hash.py", "eval.py", "evaluation_runtime.py", "evaluation_hermes_worker.py", "fleet.py"):
        path = harness.parent / name
        digest.update(name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


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


def freeze_candidate(candidate: Path) -> dict:
    """Capture source bytes once and derive both identity and prompt from them.

    SKILL.md package identity follows fleet.directory_record exactly. The
    projection hash identifies only the linked text included in the prompt;
    capturing scripts/assets does not claim that their behavior was exercised.
    """
    candidate = candidate.absolute()
    root = candidate.parent.resolve()
    captured: dict[Path, bytes] = {}
    package = candidate.name == "SKILL.md"
    package_order: list[Path] = []
    if package:
        try:
            from fleet import is_linklike_path, is_transient
        except ModuleNotFoundError:
            sys.path.insert(0, str(Path(__file__).resolve().parent))
            from fleet import is_linklike_path, is_transient
        if is_linklike_path(candidate.parent):
            raise RuntimeError(f"skill source is a link or junction: {candidate.parent}")
        for path in sorted(root.rglob("*")):
            if is_linklike_path(path):
                raise RuntimeError(f"skill source contains a symbolic link or junction: {path}")
            if is_transient(path, root) or not path.is_file():
                continue
            captured[path] = path.read_bytes()
            package_order.append(path)
        if root / "SKILL.md" not in captured:
            raise RuntimeError(f"skill has no SKILL.md: {root}")
    else:
        candidate = candidate.resolve()
        captured[candidate] = candidate.read_bytes()

    candidate = candidate.resolve()
    queue = [candidate]
    seen = {candidate}
    linked: list[Path] = []
    total = 0
    while queue:
        current = queue.pop(0)
        for raw in LINK_RE.findall(captured[current].decode("utf-8")):
            ref = raw.split("#", 1)[0].strip()
            if not ref or "://" in ref or ref.startswith(("#", "/")):
                continue
            path = (current.parent / ref).resolve()
            if not path.is_relative_to(root) or path in seen or path.suffix.lower() not in TEXT_SUFFIXES:
                continue
            if path not in captured:
                # Package projection is limited to the exact captured package.
                if package or not path.is_file():
                    continue
                captured[path] = path.read_bytes()
            total += len(captured[path])
            if total > MAX_LINKED_BYTES:
                raise ValueError("linked candidate references exceed size limit")
            seen.add(path)
            linked.append(path)
            queue.append(path)
    prompt_order = [candidate, *sorted(linked, key=lambda path: path.relative_to(root).as_posix())]
    sections = [
        f'<FILE path="{path.relative_to(root).as_posix()}">\n{captured[path].decode("utf-8")}\n</FILE>'
        for path in prompt_order
    ]
    prompt = "\n\n".join(sections)
    digest = hashlib.sha256()
    if not package:
        digest.update(b"agent-signal-standalone-v2\0")
    for path in package_order if package else prompt_order:
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(hashlib.sha256(captured[path]).digest())
    return {
        "prompt_text": prompt,
        "package_sha256": digest.hexdigest(),
        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "projection": "inline-linked-text-only",
        "identity_format": "fleet-package-v1" if package else "standalone-text-v2",
        "files": {path.relative_to(root).as_posix(): hashlib.sha256(data).hexdigest()
                  for path, data in captured.items()},
    }


def candidate_hash(candidate: Path) -> str:
    return freeze_candidate(candidate)["package_sha256"]


def candidate_prompt_text(candidate: Path) -> str:
    return freeze_candidate(candidate)["prompt_text"]
