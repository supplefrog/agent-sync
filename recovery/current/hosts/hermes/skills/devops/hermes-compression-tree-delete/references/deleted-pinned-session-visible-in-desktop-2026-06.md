# Deleted pinned session still visible in Desktop (2026-06)

## Symptom

After deleting session `20260627_153529_28188e` from `state.db`, Desktop still showed it in the sidebar because it had been pinned.

## Evidence pattern

- `state.db` verification showed `sessions=0` and `messages=0` for the deleted id.
- Electron localStorage/LevelDB still contained UI state such as `hermes.desktop.lastSessionId`, `hermes.desktop.pinnedSessions`, and composer drafts.
- A stale worker was still alive:
  - `pythonw.exe -m tui_gateway.slash_worker --session-key 20260627_153529_28188e --model ...`
  - child `python.exe -m tui_gateway.slash_worker --session-key 20260627_153529_28188e --model ...`

## Fix pattern

1. Delete the session/messages directly from `state.db` as the main skill says.
2. Inspect live Desktop workers by command line:

   ```bash
   powershell.exe -NoProfile -Command 'Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match "tui_gateway.slash_worker|<SESSION_ID>" } | Select-Object ProcessId,ParentProcessId,Name,CommandLine | ConvertTo-Json -Depth 3'
   ```

3. If a worker for the deleted session remains, kill only that worker parent and child PIDs:

   ```bash
   powershell.exe -NoProfile -Command 'Stop-Process -Id <PARENT_PID>,<CHILD_PID> -Force -ErrorAction SilentlyContinue'
   ```

4. Re-verify DB rows are still zero. If the pinned row remains after the worker is gone, it is renderer/sidebar localStorage cache; a Desktop reload/restart should clear the stale row once the backend no longer returns the session.

## Pitfall

Do not conclude the DB deletion failed just because Desktop still shows a pinned session. Separate backend truth (`state.db` rows), live workers (`tui_gateway.slash_worker`), and renderer-local pinned/sidebar state (`%APPDATA%/Hermes/Local Storage/leveldb`).