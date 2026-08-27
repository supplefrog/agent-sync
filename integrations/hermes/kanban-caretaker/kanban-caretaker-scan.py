#!/usr/bin/env python
"""Script-only cron adapter for the Kanban caretaker recovery scan."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _plugin_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "plugins" / "kanban-caretaker"


def main() -> int:
    module_path = _plugin_dir() / "caretaker.py"
    spec = importlib.util.spec_from_file_location("kanban_caretaker_core", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load caretaker core: {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    settings = module.load_settings()
    outcome = module.scan_all(settings)
    caretaker_recovery = module.recover_failed_caretakers(settings)
    handoff = module.apply_verified_recovery_actions(settings)
    errors = [
        *outcome["errors"],
        *caretaker_recovery["errors"],
        *handoff["errors"],
    ]
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
