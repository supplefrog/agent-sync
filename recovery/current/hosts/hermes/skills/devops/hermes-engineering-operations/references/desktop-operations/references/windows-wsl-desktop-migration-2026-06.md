# Windows + WSL Hermes Desktop migration notes (2026-06)

This reference captures a concrete migration/debugging pattern; keep the main SKILL.md class-level and use this only for details.

## Observed component layout

- Windows Desktop Hermes home: `{{agent-signal:HERMES_HOME}}`
- Windows Hermes source/venv: `{{agent-signal:HERMES_HOME}}\hermes-agent`
- Desktop executable: `{{agent-signal:HERMES_HOME}}\hermes-agent\apps\desktop\release\win-unpacked\Hermes.exe`
- Electron user data: `{{agent-signal:HOME}}\AppData\Roaming\Hermes`
- WSL distro: `openSUSE-Tumbleweed`
- WSL Hermes source home in this case: `/root/.hermes`

## Desktop behavior verified from source/processes

Desktop's Electron main process resolves `HERMES_HOME` and, on Windows, defaults to `%LOCALAPPDATA%\hermes`. It spawns a local dashboard backend approximately as:

```text
python -m hermes_cli.main dashboard --no-open --host 127.0.0.1 --port <picked-port>
```

The spawned environment pins:

```text
HERMES_HOME=<resolved home>
HERMES_DESKTOP=1
HERMES_DASHBOARD_SESSION_TOKEN=<random token>
```

Desktop also uses per-session workers like:

```text
python -m tui_gateway.slash_worker --session-key <id> --model <model>
```

The Electron user-data directory (`%APPDATA%\Hermes`) is browser/UI storage; the durable Hermes config/state is under `HERMES_HOME`.

Backend selection details observed in source:

- Windows Desktop default home: `%LOCALAPPDATA%\hermes`.
- `HERMES_HOME` overrides the home passed to the Python backend.
- `HERMES_DESKTOP_HERMES_ROOT` points at a source checkout.
- `HERMES_DESKTOP_HERMES` points at a Hermes command/shim.
- Desktop supports remote dashboard connection config; this is the safer route for a canonical WSL backend than making Windows Python write into `\\wsl$`.
- Hermes has a Windows-native CLI/backend in the Desktop-managed venv (`%LOCALAPPDATA%\hermes\hermes-agent\venv\Scripts\hermes`); do not assume Hermes CLI is Linux-only.

## Terminal and host semantics

Hermes core/backend is Python on both Windows and WSL. The backend host determines local tool semantics:

- WSL backend: local terminal is Linux bash; Windows automation requires interop calls such as `powershell.exe`/`cmd.exe` or paths under `/mnt/c`.
- Windows Desktop backend: local terminal is Git Bash/MSYS by default because the local environment searches for `bash.exe` (portable Git under `%LOCALAPPDATA%\hermes\git` first, then system Git). PowerShell is directly callable as `powershell.exe`/`pwsh`, but it is not the default shell.
- Windows Hermes venv isolates Python dependencies but is not an OS sandbox; terminal/file tools run with the Windows user's access unless a non-local backend is configured.

## Migration pattern that worked

1. Locate candidate homes (`/root/.hermes`, `/home/*/.hermes`, `%LOCALAPPDATA%\hermes`) and compare presence of `config.yaml`, `.env`, `auth.json`, `state.db`, `skills/`, and `profiles/`.
2. Back up the current Windows Desktop home and the WSL source critical state.
3. Copy WSL Hermes state into Windows Desktop home, excluding transient locks/caches:
   - exclude `cache/`, `audio_cache/`, `image_cache/`, `sandboxes/`
   - exclude `state.db-shm`, `state.db-wal`, `auth.lock`, `processes.json`
   - avoid overwriting live logs if Desktop is running
4. If `state.db` is locked by Desktop, copy source DB to a staged name like `state.db.from-wsl-migration`.
5. Launch a finalizer that waits for Desktop to close/unlock the DB, backs up the current Desktop DB, copies staged DB to `state.db`, and removes stale WAL/SHM files.
6. Verify with hashes for `config.yaml`, `.env`, `auth.json`, `SOUL.md`, profile list, skill counts, and final `state.db` size/hash.

## User interaction lesson

For this user's Hermes operations, avoid long repetitive command instructions. If authorization is clear, perform the migration/inspection directly and report concise facts: source path, target path, backup path, verification result, and remaining blocker.