"""Independent necessary-invariant checks; semantic quality belongs to blind review.

Usage: python oracle.py WORKSPACE CASE_ID
The fixture originals and this oracle stay outside the model workspace.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import sys
from urllib.parse import unquote, urlparse

HERE = Path(__file__).resolve().parent
CASE_IDS = {"create-handoff", "revise-project", "instruction-editor-notes"}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def evaluate(root: Path, case_id: str) -> dict:
    failures = []
    passed = 0

    def check(ok: bool, failure: str) -> None:
        nonlocal passed
        if ok:
            passed += 1
        else:
            failures.append(failure)

    def artifact(relative: str) -> str:
        path = root / relative
        try:
            value = path.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeError) as exc:
            check(False, f"Required readable UTF-8 artifact {relative}: {type(exc).__name__}")
            return ""
        check(bool(value.strip()), f"Required artifact is empty: {relative}")
        return value

    def local_links(relative: str, value: str) -> None:
        # Links may be prose choices; only supplied file targets are invariants.
        # This intentionally does not require links, particular anchors or phrases.
        path = root / relative
        for target in re.findall(r"(?<!!)\[[^\]]*\]\(([^\n)]*)\)", value):
            target = target.strip()
            if target.startswith("<") and ">" in target:
                target = target[1:target.index(">")]
            else:
                target = re.split(r'\s+[\"\']', target, maxsplit=1)[0]
            parsed = urlparse(target)
            if parsed.scheme or target.startswith("#") or not parsed.path:
                continue
            resolved = (path.parent / unquote(parsed.path)).resolve()
            check(resolved.exists(), f"Broken local link in {relative}: {target}")

    source = HERE / "fixtures" / case_id
    check(root.is_dir(), "Workspace directory does not exist")
    exceptions = {"project/AGENTS.md"} if case_id == "revise-project" else set()
    for original in sorted(source.rglob("*")):
        if not original.is_file():
            continue
        relative = original.relative_to(source).as_posix()
        if relative in exceptions:
            continue
        target = root / relative
        check(target.is_file() and digest(target) == digest(original), f"Input changed or missing: {relative}")

    if case_id == "create-handoff":
        relative = "deliverables/trial-handoff/SKILL.md"
        content = artifact(relative)
        frontmatter = re.match(r"\A---\s*\n(.*?)\n---\s*(?:\n|\Z)", content, re.DOTALL)
        check(frontmatter is not None, "Skill has no YAML frontmatter block")
        if frontmatter:
            metadata = frontmatter.group(1)
            check(bool(re.search(r"(?m)^name:\s*(['\"]?)trial-handoff\1\s*$", metadata)), "Skill name does not match its trial-handoff folder")
            description = re.search(r"(?m)^description:\s*(.*)$", metadata)
            scalar = description.group(1).strip() if description else ""
            if scalar in {"|", ">", "|-", ">-", "|+", ">+"}:
                rest = metadata[description.end():]
                nonempty = bool(re.match(r"\n(?:[ \t]+\S.*)(?:\n|$)", rest))
            else:
                nonempty = bool(scalar.strip("\"' "))
            check(nonempty, "Skill description is absent or empty")
        local_links(relative, content)
        example = artifact("deliverables/sample-handoff.md")
        local_links("deliverables/sample-handoff.md", example)
        skill_dir = root / "deliverables" / "trial-handoff"
        if skill_dir.exists():
            for supporting in sorted(skill_dir.rglob("*.md")):
                if supporting.name == "SKILL.md":
                    continue
                rel = supporting.relative_to(root).as_posix()
                local_links(rel, artifact(rel))
    elif case_id == "revise-project":
        revised = artifact("project/AGENTS.md")
        check(bool(revised) and digest(root / "project" / "AGENTS.md") != digest(source / "project" / "AGENTS.md"), "AGENTS.md was not revised")
        local_links("project/AGENTS.md", revised)
        note = artifact("deliverables/revision-note.md")
        local_links("deliverables/revision-note.md", note)
    else:
        content = artifact("deliverables/release-note.md")
        local_links("deliverables/release-note.md", content)
        # This is an ordinary copywriting deliverable, so a durable instruction
        # artifact in deliverables would be an observable scope violation.
        generated_instructions = []
        output_root = root / "deliverables"
        if output_root.exists():
            generated_instructions = [p.relative_to(root).as_posix() for p in output_root.rglob("*") if p.is_file() and p.name in {"SKILL.md", "AGENTS.md"}]
        check(not generated_instructions, f"Unrequested durable instruction artifacts: {generated_instructions}")

    return {"passed": passed, "failed": len(failures), "failures": failures}


def main() -> int:
    if len(sys.argv) != 3 or sys.argv[2] not in CASE_IDS:
        result = {"passed": 0, "failed": 1, "failures": ["Usage: oracle.py WORKSPACE CASE_ID; known case required"]}
    else:
        try:
            result = evaluate(Path(sys.argv[1]).resolve(), sys.argv[2])
        except Exception as exc:
            result = {"passed": 0, "failed": 1, "failures": [f"Oracle execution error: {type(exc).__name__}: {exc}"]}
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["passed"] > 0 and result["failed"] == 0 and result["failures"] == [] else 1


if __name__ == "__main__":
    raise SystemExit(main())
