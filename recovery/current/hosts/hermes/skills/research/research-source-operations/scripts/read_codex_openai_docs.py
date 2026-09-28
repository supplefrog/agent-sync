#!/usr/bin/env python
"""Read the installed Codex OpenAI Docs procedure without copying or executing it."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path

MAX_BYTES = 256_000

def _read(path: Path) -> bytes:
    if not path.is_file() or path.is_symlink():
        raise ValueError('requested source is not a regular installed file')
    with path.open('rb') as handle:
        raw = handle.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError('installed source exceeds the bounded read limit')
    return raw

def _marker(root: Path) -> str | None:
    path = root.parent / '.codex-system-skills.marker'
    return _read(path).decode('utf-8').strip() if path.is_file() else None

def read_source(codex_home: str | Path | None = None, file_path: str = 'SKILL.md') -> dict:
    home = Path(codex_home or os.environ.get('CODEX_HOME') or Path.home()/'.codex').expanduser()
    root = home/'skills'/'.system'/'openai-docs'
    relative = Path(file_path)
    if relative.is_absolute() or '..' in relative.parts or not relative.parts:
        raise ValueError('select a package-relative source file')
    if relative.as_posix() != 'SKILL.md' and relative.parts[0] not in ('references', 'scripts'):
        raise ValueError('select SKILL.md or a needed reference/helper')
    selected = root/relative
    if not selected.resolve().is_relative_to(root.resolve()):
        raise ValueError('selected source escapes the installed package')
    before = _marker(root)
    entrypoint = _read(root/'SKILL.md')
    text = entrypoint.decode('utf-8')
    if not re.search(r'^name:\s*["\']?openai-docs["\']?\s*$', text, re.MULTILINE):
        raise ValueError('installed entrypoint is not the expected OpenAI Docs package')
    license_bytes = _read(root/'LICENSE.txt')
    selected_bytes = entrypoint if relative.as_posix() == 'SKILL.md' else _read(selected)
    after = _marker(root)
    if before != after or _read(root/'SKILL.md') != entrypoint or _read(selected) != selected_bytes:
        raise ValueError('installed source changed during reading; retry against the new package')
    return {'source': 'installed-codex-openai-docs', 'path': str(selected.absolute()),
            'file': relative.as_posix(), 'content': selected_bytes.decode('utf-8'),
            'entrypoint_sha256': hashlib.sha256(entrypoint).hexdigest(),
            'file_sha256': hashlib.sha256(selected_bytes).hexdigest(),
            'license_sha256': hashlib.sha256(license_bytes).hexdigest(),
            'codex_bundle_marker': after, 'source_copied': False, 'source_executed': False,
            'update_scope': 'Fresh reads follow installed Codex package changes; no independent upstream fetch.'}

def main() -> int:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--codex-home', type=Path)
    parser.add_argument('--file', default='SKILL.md')
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()
    try:
        result = read_source(args.codex_home, args.file)
    except (ValueError, OSError, UnicodeError) as exc:
        print(json.dumps({'source_available': False, 'error': str(exc),
                          'fallback': 'Use current official pages, disclose missing local procedures; do not invent or auto-install a copy.'}))
        return 1
    print(json.dumps(result, ensure_ascii=False) if args.json else result['content'])
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
