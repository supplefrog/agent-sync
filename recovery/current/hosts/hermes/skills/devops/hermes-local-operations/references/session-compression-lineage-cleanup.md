# Hermes compression-lineage session cleanup

Use when Hermes creates visible numbered continuation sessions (`Title #2`, `Title #5`, etc.) after context compression and the user wants bulk cleanup instead of deleting each ID manually.

## What to check first

- Load the protected `hermes-agent` skill for the current official CLI surface.
- Check `hermes sessions --help`, `hermes sessions list --help`, and `hermes sessions delete --help` before assuming bulk CLI flags exist.
- Current CLI delete is single-session (`hermes sessions delete ID --yes`). Dashboard/session APIs may support bulk selection, but the shell CLI may not.
- On Windows Desktop installs, the canonical home may be `%LOCALAPPDATA%\hermes`, not `~/.hermes`; confirm with `hermes config path` or `hermes_constants.get_hermes_home()` before touching `state.db`.

## Compression lineage definition

A compression continuation is a child session where:

```sql
child.parent_session_id = parent.id
AND parent.end_reason = 'compression'
AND child.started_at >= parent.ended_at
```

This distinguishes compression continuations from branch/delegate children that also use `parent_session_id`.

Numbered titles are usually generated as `Base title #N`; do not match only by title. Combine numbered-title matching with the compression-lineage predicate above.

## Safe one-command pattern

Close Hermes/Desktop first if deleting from the SQLite store directly. Always create a timestamped backup before mutation.

```bash
python - <<'PY'
from shutil import copy2
from datetime import datetime
from hermes_state import SessionDB
from hermes_constants import get_hermes_home

DRY_RUN = True  # change to False after reviewing matches

home = get_hermes_home()
db_path = home / 'state.db'
backup = home / f'state.db.bak-before-compression-cleanup-{datetime.now():%Y%m%d-%H%M%S}'
copy2(db_path, backup)
print(f'Backup: {backup}')

db = SessionDB()
rows = db._conn.execute('''
    SELECT c.id, c.title, c.parent_session_id
    FROM sessions c
    JOIN sessions p ON p.id = c.parent_session_id
    WHERE p.end_reason = 'compression'
      AND c.started_at >= p.ended_at
      AND COALESCE(c.title, '') GLOB '* #[0-9]*'
    ORDER BY c.started_at DESC
''').fetchall()
ids = [r['id'] for r in rows]
for r in rows:
    print(r['id'], '—', r['title'])
print(f'\nMatched {len(ids)} compressed numbered sessions.')

if DRY_RUN:
    print('Dry run only. Set DRY_RUN = False to delete.')
else:
    deleted = db.delete_sessions(ids, sessions_dir=home / 'sessions')
    print(f'Deleted {deleted} sessions.')
PY
```

## Safer alternative: archive

If the user wants the session list clean but might need transcripts later, archive instead of delete:

```bash
python - <<'PY'
from hermes_state import SessionDB
DRY_RUN = True

db = SessionDB()
rows = db._conn.execute('''
    SELECT c.id, c.title
    FROM sessions c
    JOIN sessions p ON p.id = c.parent_session_id
    WHERE p.end_reason = 'compression'
      AND c.started_at >= p.ended_at
      AND COALESCE(c.title, '') GLOB '* #[0-9]*'
    ORDER BY c.started_at DESC
''').fetchall()
for r in rows:
    print(r['id'], '—', r['title'])
print(f'\nMatched {len(rows)} sessions.')

if DRY_RUN:
    print('Dry run only. Set DRY_RUN = False to archive.')
else:
    for r in rows:
        db.set_session_archived(r['id'], True)
    print('Archived.')
PY
```

## Pitfalls

- Do not delete by title suffix alone; numbered titles can also be legitimate manual titles.
- Do not assume `~/.hermes/state.db` on Windows Desktop. Use `get_hermes_home()`.
- `delete_session()` or `hermes sessions delete ID` deletes one row and may orphan compression children; use `delete_sessions([...])` for bulk direct DB cleanup.
- If direct Python/SQLite deletion is blocked by command-approval heuristics, create a `state.db` backup first, then loop over the reviewed ID list with the supported `hermes sessions delete <id> --yes` CLI command; verify the target IDs/titles are gone afterward.
- Achievement plugin scan caches (`plugins/hermes-achievements/scan_snapshot.json`, `scan_checkpoint.json`) can retain stale deleted-session titles. Move them aside after deleting sessions if searches/UI still surface old titles; they are derived caches and regenerate.
- Direct SQLite cleanup is an operational escape hatch. Prefer dashboard bulk delete if the user wants supported UI behavior and it is available.
