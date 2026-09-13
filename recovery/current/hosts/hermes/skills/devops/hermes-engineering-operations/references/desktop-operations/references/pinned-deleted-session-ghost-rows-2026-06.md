# Pinned/deleted session ghost rows in Desktop (2026-06)

When a deleted session remains visible in Desktop, split the problem into three stores:

1. **Backend truth** — `%LOCALAPPDATA%/hermes/state.db` `sessions` and `messages` rows.
2. **Live runtime** — `python[w].exe -m tui_gateway.slash_worker --session-key <id>` processes can outlive DB deletion and keep a tab/session reachable.
3. **Renderer state** — Electron localStorage/LevelDB under `%APPDATA%/Hermes/Local Storage/leveldb` stores UI keys such as `hermes.desktop.pinnedSessions`, `hermes.desktop.lastSessionId`, and composer drafts.

Useful checks:

```bash
# Verify backend truth
python - <<'PY'
import sqlite3, subprocess
from pathlib import Path
sid='<SESSION_ID>'
home=Path(subprocess.check_output(['hermes','config','path'], text=True).strip()).parent
conn=sqlite3.connect(home/'state.db')
print('sessions', conn.execute('select count(*) from sessions where id=?',(sid,)).fetchone()[0])
print('messages', conn.execute('select count(*) from messages where session_id=?',(sid,)).fetchone()[0])
PY

# Find stale workers
powershell.exe -NoProfile -Command 'Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match "tui_gateway.slash_worker|<SESSION_ID>" } | Select-Object ProcessId,ParentProcessId,Name,CommandLine | ConvertTo-Json -Depth 3'
```

Fix sequence:

1. If DB rows still exist, delete the session tree with the compression-delete workflow.
2. If DB rows are zero but a worker remains, kill only the stale worker parent/child PIDs.
3. If DB rows are zero and no worker remains but the row still appears, reload/restart Desktop; it is renderer-local pinned/sidebar cache.

Do not broadly clear `%APPDATA%/Hermes` or Electron LevelDB just to remove one stale pinned row; that risks unrelated UI state. Prefer narrow worker cleanup plus reload.

## Pins vanish after backend-sync update (observed 2026-08)

Newer Desktop builds mirror localStorage pins into `sessions.pinned` and pull backend pin state back into the renderer. A migration-order bug can erase pre-update pins at first boot:

1. Existing pins are present only in `hermes.desktop.pinnedSessions`.
2. The newly added SQLite `sessions.pinned` column defaults to false.
3. `watchSessionPins()` calls `pullRemotePins()` before the push/migration pass.
4. A loaded row with `pinned: false` therefore calls `unpinSession(...)`, clearing the local pin before it can be mirrored to SQLite.

Diagnosis: the Pinned section is empty, `state.db` has zero `pinned=1` rows, and sessions/messages remain intact. This is loss of pin assignments, not deletion of chats.

Restore a known conversation through the supported lineage-aware backend primitive rather than editing one row directly:

```bash
./venv/Scripts/python.exe -c "from hermes_state import SessionDB; db=SessionDB(); print(db.set_session_pinned('<known-session-id>', True))"
```

`set_session_pinned` updates the compression lineage as a unit. Verify `pinned=1` rows, `PRAGMA integrity_check`, and the real Desktop Pinned section.

### Recover an overwritten localStorage pin list

Do not assume an overwritten key is unrecoverable until inspecting every surviving LevelDB table/log record. Chromium may leave the previous value in an obsolete `.ldb` file even though normal localStorage reads return the new value.

Use `scripts/recover_chromium_localstorage_key.py` against `%APPDATA%/Hermes/Local Storage/leveldb`. It reads raw records without trusting the active manifest and prints every surviving value ordered by LevelDB sequence number.

A disposable dependency setup on Windows is:

```bash
python -m pip install --target "$TEMP/dfindexeddb-recovery" python-snappy zstd
python -m pip install --target "$TEMP/dfindexeddb-recovery" --no-deps dfindexeddb
PYTHONPATH="$TEMP/dfindexeddb-recovery" python scripts/recover_chromium_localstorage_key.py \
  "$APPDATA/Hermes/Local Storage/leveldb" hermes.desktop.pinnedSessions
```

Interpret recovered IDs against `state.db` before changing anything:

1. Confirm each session exists and count its messages.
2. Follow compression lineage/descendants; one stored root can represent a long conversation lineage.
3. Restore only valid roots with `SessionDB.set_session_pinned(...)`.
4. Do not resurrect empty placeholders or IDs absent from both `sessions` and `messages`.
5. If no older LevelDB value survives, the association is gone even though the chats may remain searchable; manual re-pinning is then the honest fallback.

LevelDB compaction can permanently remove still-older values, so a recovered array is the latest *surviving* snapshot, not proof that no earlier pin set ever existed. Remove the disposable parser environment after verification.