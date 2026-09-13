#!/usr/bin/env python
"""Recover every surviving historical value for one Chromium localStorage key.

Requires dfindexeddb plus a working python-snappy implementation. Reads all
LevelDB table/log records rather than only the manifest's current value.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from dfindexeddb.leveldb import record


def decode_value(value: bytes) -> str:
    """Decode Chromium localStorage's one-byte string encoding marker."""
    if value[:1] == b"\x01":
        return value[1:].decode("utf-8", "replace")
    if value[:1] == b"\x00":
        return value[1:].decode("utf-16le", "replace")
    return value.decode("utf-8", "replace")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("leveldb", type=Path)
    parser.add_argument("key", help="localStorage key, e.g. hermes.desktop.pinnedSessions")
    args = parser.parse_args()

    internal_key = b"_file://\x00\x01" + args.key.encode("utf-8")
    matches: list[dict[str, object]] = []
    for item in record.FolderReader(args.leveldb).GetRecords():
        parsed = item.record
        if getattr(parsed, "key", None) != internal_key:
            continue
        value = getattr(parsed, "value", b"") or b""
        matches.append(
            {
                "file": Path(item.path).name,
                "offset": getattr(parsed, "offset", None),
                "sequence": getattr(parsed, "sequence_number", None),
                "record_type": int(getattr(parsed, "record_type", 0)),
                "recovered": item.recovered,
                "value": decode_value(value),
            }
        )

    matches.sort(key=lambda row: (row["sequence"] is None, row["sequence"] or 0))
    print(json.dumps(matches, indent=2))


if __name__ == "__main__":
    main()
