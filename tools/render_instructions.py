"""Render shared standing rules into native overlays; check before reconciliation."""
from __future__ import annotations

import argparse
import json
from pathlib import Path, PurePosixPath
import re


class RenderError(RuntimeError):
    pass


HOSTS = ("codex", "hermes")
START, END = "<!-- agent-sync-standing -->", "<!-- /agent-sync-standing -->"


def shared_rules(repo: Path) -> dict[str, str]:
    text = (repo / "surfaces/core.md").read_text(encoding="utf-8")
    if text.count(START) != 1 or text.count(END) != 1:
        raise RenderError("core.md requires exactly one standing-rule section")
    if text.index(END) < text.index(START):
        raise RenderError("standing-rule delimiters are reversed")
    body = text.split(START, 1)[1].split(END, 1)[0].strip()
    rules = {}
    for part in re.split(r"(?m)^## ", body):
        if not part.strip():
            continue
        title, separator, content = part.partition("\n")
        key = title.strip().lower()
        if not separator or not re.fullmatch(r"[a-z][a-z-]*", key) or not content.strip():
            raise RenderError("invalid shared standing rule")
        if key in rules:
            raise RenderError(f"duplicate shared rule: {key}")
        rules[key] = " ".join(content.split())
    if not rules:
        raise RenderError("empty shared standing rules")
    return rules


def _source_path(repo: Path, value: str) -> Path:
    pure = PurePosixPath(value)
    if pure.is_absolute() or ".." in pure.parts or "\\" in value:
        raise RenderError(f"unsafe generated path: {value}")
    path = (repo / value).resolve()
    if not path.is_relative_to(repo.resolve()):
        raise RenderError(f"escaping generated path: {value}")
    return path


def projections(repo: Path) -> dict[str, tuple[Path, str]]:
    rules = shared_rules(repo)
    result = {}
    used = set()
    for host in HOSTS:
        adapter = json.loads((repo / f"adapters/{host}.json").read_text(encoding="utf-8"))
        instructions = adapter["instructions"]
        if instructions["strategy"] != "generated":
            raise RenderError(f"{host} instruction strategy must be generated")
        projection = instructions["projection"]
        parts = ["<!-- Generated from surfaces/core.md and the host adapter; do not edit here. -->"]
        labels = set()
        host_rules = set()
        for section in projection["sections"]:
            label = section["label"]
            if label in labels or "\n" in label:
                raise RenderError(f"duplicate or invalid {host} label: {label}")
            labels.add(label)
            if ("shared" in section) == ("text" in section):
                raise RenderError("section requires exactly one shared rule or native text")
            if "shared" in section:
                key = section["shared"]
                if key not in rules:
                    raise RenderError(f"unknown shared rule: {key}")
                if key in host_rules:
                    raise RenderError(f"duplicate shared rule for {host}: {key}")
                host_rules.add(key)
                used.add(key)
                text = rules[key]
            else:
                text = section["text"]
            text = " ".join(filter(None, [text.strip(), section.get("suffix", "").strip()]))
            if not text:
                raise RenderError(f"empty {host} section: {label}")
            if projection["format"] == "tagged-lines":
                parts.append(f"[{label}] {text}")
            elif projection["format"] == "headings":
                parts.append(f"# {label}\n\n{text}")
            else:
                raise RenderError(f"unsupported projection format for {host}")
        separator = "\n" if projection["format"] == "tagged-lines" else "\n\n"
        if host_rules != set(rules):
            raise RenderError(f"missing shared rules for {host}: {sorted(set(rules) - host_rules)}")
        result[host] = (_source_path(repo, instructions["source"]), separator.join(parts) + "\n")
    if used != set(rules):
        raise RenderError(f"unprojected shared rules: {sorted(set(rules) - used)}")
    return result


def verify(repo: Path) -> dict:
    expected = projections(repo)
    for host, (path, text) in expected.items():
        if not path.is_file() or path.read_bytes() != text.encode("utf-8"):
            raise RenderError(f"generated {host} overlay differs from its source; render instructions")
    return {"status": "pass", "hosts": list(expected), "owner": "surfaces/core.md"}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("check", "render"))
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args(argv)
    try:
        if args.mode == "render":
            for path, text in projections(args.repo).values():
                path.write_bytes(text.encode("utf-8"))
        print(json.dumps(verify(args.repo)))
        return 0
    except (RenderError, OSError, KeyError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
