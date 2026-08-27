#!/usr/bin/env python
"""Run one normal Hermes chat process with a process-local reasoning effort.

This adapter changes only ``cli.CLI_CONFIG`` in the child process. It does not
write config.yaml and then delegates to Hermes's public chat command unchanged.
"""

from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    values = list(sys.argv[1:] if argv is None else argv)
    try:
        separator = values.index("--")
    except ValueError:
        separator = -1
    if separator < 0:
        raise SystemExit("tier_chat: expected -- before Hermes chat arguments")
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(
        "--reasoning-effort",
        required=True,
        choices=("none", "minimal", "low", "medium", "high", "xhigh", "max"),
    )
    args = parser.parse_args(values[:separator])
    remaining = values[separator + 1 :]
    if not remaining:
        raise SystemExit("tier_chat: missing Hermes chat arguments")

    try:
        import hermes_bootstrap  # noqa: F401
    except ModuleNotFoundError:
        pass

    import cli

    agent_config = cli.CLI_CONFIG.setdefault("agent", {})
    agent_config["reasoning_effort"] = args.reasoning_effort

    from hermes_cli.main import main as hermes_main

    sys.argv = ["hermes", *remaining]
    result = hermes_main()
    return int(result) if isinstance(result, int) else 0


if __name__ == "__main__":
    raise SystemExit(main())
