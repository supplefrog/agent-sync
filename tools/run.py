#!/usr/bin/env python
"""Run an Agent Sync tool with the checkout's dependency-ready Python."""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def runtime(repo: Path) -> str:
    declared = [repo / ".venv/Scripts/python.exe", repo / ".venv/bin/python"]
    if not any(path.is_file() for path in declared) and (repo / ".git").is_file():
        shared = subprocess.run(["git", "-C", str(repo), "rev-parse", "--path-format=absolute", "--git-common-dir"],
                                capture_output=True, text=True, check=False)
        if shared.returncode == 0:
            primary = Path(shared.stdout.strip()).parent
            declared += [primary / ".venv/Scripts/python.exe", primary / ".venv/bin/python"]
    interpreter = next((str(path) for path in declared if path.is_file()), sys.executable)
    probe = subprocess.run(
        [interpreter, "-B", "-c", "import jsonschema,yaml,toml"],
        capture_output=True, text=True, check=False,
    )
    if probe.returncode:
        raise RuntimeError(
            "Agent Sync runtime is missing declared dependencies. Set up the checkout's "
            ".venv using requirements.txt before retrying; no dependencies were installed."
        )
    return interpreter


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tool", help="existing tool basename, for example reconcile")
    parser.add_argument("arguments", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    repo = Path(__file__).resolve().parents[1]
    name = args.tool.removesuffix(".py")
    if not name or any(character not in "abcdefghijklmnopqrstuvwxyz_0123456789" for character in name):
        parser.error("tool must be an existing basename in tools/")
    target = repo / "tools" / (name + ".py")
    if not target.is_file() or target.resolve().parent != (repo / "tools").resolve() or name == "run":
        parser.error("unknown tool")
    try:
        return subprocess.run(
            [runtime(repo), "-B", str(target), *args.arguments], cwd=repo, check=False,
        ).returncode
    except (OSError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
