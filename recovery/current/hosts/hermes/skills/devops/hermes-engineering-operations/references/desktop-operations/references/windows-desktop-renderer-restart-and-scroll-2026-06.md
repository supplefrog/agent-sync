# Windows Desktop renderer restart + scroll-state investigation (2026-06)

Session-specific evidence useful for future Hermes Desktop troubleshooting.

## Process model observed on Windows

Hermes Desktop runs as an Electron process tree under `Hermes.exe` plus Python dashboard/slash-worker children.

Observed examples:

```text
Hermes.exe 19112  main Electron process
Hermes.exe 2376   --type=renderer --user-data-dir="{{agent-signal:HOME}}\AppData\Roaming\Hermes" ...
Hermes.exe 13440  --type=gpu-process ...
Hermes.exe 6772   --type=utility --utility-sub-type=network.mojom.NetworkService ...
python.exe 17752  ...\venv\Scripts\python.exe -m hermes_cli.main dashboard --no-open --host 127.0.0.1 --port 0
python.exe 12160  ... -m tui_gateway.slash_worker --session-key ...
```

Because Electron uses a single-instance lock, relaunching while the main process is alive focuses the existing instance instead of starting a fresh renderer/app. If a root error-boundary state appears to survive “restart,” verify the process tree is actually gone.

## Practical restart guidance

- In Task Manager → Details, end `Hermes.exe` entries. The parent/main process has no `--type=` in its command line; children include `--type=renderer`, `--type=gpu-process`, etc.
- For a full reset, kill all `Hermes.exe` entries rather than only the renderer, because the Python dashboard and slash-worker children may also be stale.
- PowerShell equivalent:

```powershell
Stop-Process -Name Hermes -Force
```

From Git Bash/MSYS terminal calls, avoid `tasklist /v` because `/v` may be path-converted; use `cmd.exe //c 'tasklist /v /fo csv'` or PowerShell/CIM:

```bash
powershell.exe -NoProfile -Command 'Get-CimInstance Win32_Process | Where-Object { $_.Name -match "Hermes|python|node" -or $_.CommandLine -match "hermes" } | Select-Object ProcessId,ParentProcessId,Name,CommandLine | Format-List'
```

## Source landmarks

`apps/desktop/electron/main.cjs`:

- `app.requestSingleInstanceLock()` and `second-instance` focus behavior explain why relaunch may not create a new renderer.
- `createWindow()` creates the main `BrowserWindow` and listens for `render-process-gone`; only crashed/OOM renderer exits auto-reload via `webContents.reload()`.
- `before-quit` kills the Hermes backend child process.
- `window-all-closed` calls `app.quit()` on non-macOS.

`apps/desktop/src/components/error-boundary.tsx`:

- Root fallback has `Retry`, `Reload window` (`window.location.reload()`), and `Open logs`.

`apps/desktop/src/components/assistant-ui/thread-list.tsx`:

- The chat scroller is owned by `useStickToBottom`.
- On mount/session switch it resets `renderBudget` and explicitly pins to bottom with `el.scrollTop = el.scrollHeight` / `scrollToBottom('instant')`.
- At the time of investigation there was no persisted per-session `scrollTop`, distance-from-bottom, anchor message id, or render budget. This supported filing a scroll-position persistence issue rather than treating it as user error.

## tapClientLookup crash linkage

For long chats/context compaction, `desktop.log` showed repeated root-boundary crashes from `UserMessage`:

```text
[renderer console] Error: tapClientLookup: Index 14 out of bounds (length: 8)
[renderer console] [error-boundary:root] Error: tapClientLookup: Index 14 out of bounds (length: 8)
    at UserMessage (<anonymous>)
```

This was added as evidence to an existing upstream issue rather than duplicated. The scroll-state issue was separate: root-boundary recovery forced a reload, and reload lost the user’s reading location.
