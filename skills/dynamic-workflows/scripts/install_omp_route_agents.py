#!/usr/bin/env python
"""Generate exact-route OMP task agents from the reviewed GPT catalogue."""

from __future__ import annotations

import argparse
import json
import os
import re
import tempfile
from pathlib import Path

ROUTE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
EFFORTS = {"minimal", "low", "medium", "high", "xhigh", "max"}


def default_catalog() -> Path:
    return (
        Path(__file__).resolve().parents[2]
        / "openai-delegation-route-research"
        / "references"
        / "current-gpt-catalog.json"
    )


def agent_text(route: dict[str, object]) -> str:
    route_id = route.get("id")
    model = route.get("model")
    effort = route.get("reasoning_effort")
    if not isinstance(route_id, str) or not ROUTE_ID_RE.fullmatch(route_id):
        raise ValueError(f"invalid route id: {route_id!r}")
    if not isinstance(model, str) or not model.startswith("gpt-"):
        raise ValueError(f"invalid model for route {route_id!r}")
    if effort not in EFFORTS:
        raise ValueError(f"invalid reasoning effort for route {route_id!r}")
    label = route_id.replace("-", " ").title()
    return f'''---
name: route-{route_id}
description: Internal exact-route DAG worker for {label}.
model: "openai-codex/{model}"
thinkingLevel: {effort}
tools: [read, grep, glob, bash, edit, write, lsp, web_search, ast_grep, yield]
spawns: []
---
Execute only the assigned routed DAG node. Do not reroute or delegate. Return concise evidence and identify blockers instead of guessing.
'''


def expected_agents(catalog_path: Path) -> dict[str, str]:
    value = json.loads(catalog_path.read_text(encoding="utf-8"))
    if value.get("schema_version") != 2 or value.get("status") != "active":
        raise ValueError("catalogue must be active schema version 2")
    if value.get("provider") != "openai-codex":
        raise ValueError("catalogue provider must be openai-codex")
    routes = value.get("delegation_candidates")
    if not isinstance(routes, list) or not routes:
        raise ValueError("catalogue has no delegation candidates")
    result: dict[str, str] = {}
    for route in routes:
        if not isinstance(route, dict):
            raise ValueError("catalogue route must be an object")
        name = f"route-{route.get('id')}.md"
        if name in result:
            raise ValueError(f"duplicate route agent: {name}")
        result[name] = agent_text(route)
    return result


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def synchronize(catalog: Path, agents_root: Path, check: bool) -> list[str]:
    expected = expected_agents(catalog)
    existing = {path.name: path for path in agents_root.glob("route-*.md")} if agents_root.is_dir() else {}
    mismatches = sorted(
        name
        for name, content in expected.items()
        if name not in existing or existing[name].read_text(encoding="utf-8") != content
    )
    stale = sorted(set(existing) - set(expected))
    if check:
        if mismatches or stale:
            raise ValueError(f"OMP route agents differ: changed={mismatches}, stale={stale}")
        return sorted(expected)
    agents_root.mkdir(parents=True, exist_ok=True)
    for name, content in expected.items():
        atomic_write(agents_root / name, content)
    for name in stale:
        existing[name].unlink()
    return sorted(expected)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=default_catalog())
    parser.add_argument("--agents-root", type=Path, default=Path.home() / ".omp" / "agent" / "agents")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    try:
        names = synchronize(args.catalog, args.agents_root, args.check)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    print(json.dumps({"status": "ok", "agents": names}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
