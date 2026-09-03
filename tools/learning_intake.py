#!/usr/bin/env python
"""Repository adapter for the portable global-learning intake script."""

from __future__ import annotations

import runpy
from pathlib import Path

_IMPL = runpy.run_path(
    str(Path(__file__).resolve().parents[1] / "skills" / "global-learning-intake" / "scripts" / "learning_intake.py")
)

SOURCE_TYPES = _IMPL["SOURCE_TYPES"]
SCOPES = _IMPL["SCOPES"]
OWNER_BY_CLASS = _IMPL["OWNER_BY_CLASS"]
IntakeError = _IMPL["IntakeError"]
default_store = _IMPL["default_store"]
validate_event = _IMPL["validate_event"]
route = _IMPL["route"]
candidate_fingerprint = _IMPL["candidate_fingerprint"]
ingest = _IMPL["ingest"]
main = _IMPL["main"]


if __name__ == "__main__":
    raise SystemExit(main())
