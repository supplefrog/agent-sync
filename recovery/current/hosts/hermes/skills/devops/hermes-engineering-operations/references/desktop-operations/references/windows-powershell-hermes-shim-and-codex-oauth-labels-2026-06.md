# Windows PowerShell Hermes shim + Codex OAuth labels (2026-06)

## Situation

The user had Windows Desktop/native Hermes state under `%LOCALAPPDATA%\hermes`, but PowerShell `hermes ...` commands were routed through a profile function that launched WSL Hermes under `/root/.hermes`. This made OpenAI Codex OAuth debugging misleading: commands appeared to update one Hermes instance while Desktop/native Windows used another.

## Discovery pattern

- Check shell resolution with `Get-Command hermes | Format-List CommandType,Name,Source,Definition` from PowerShell, not just `where.exe hermes`/PATH.
- Inspect `{{agent-signal:HOME}}\Documents\PowerShell\profile.ps1`; a function can shadow the native `%LOCALAPPDATA%\hermes\hermes-agent\venv\Scripts\hermes.exe`.
- Verify the target instance with `hermes config path`:
  - native Windows should report `{{agent-signal:HERMES_HOME}}\config.yaml`.
  - WSL root typically reports `/root/.hermes/config.yaml` when launched through `wsl.exe`.

## Fix pattern

Keep names simple and explicit:

- `hermes` -> native Windows executable:
  `Join-Path $env:LOCALAPPDATA 'hermes\hermes-agent\venv\Scripts\hermes.exe'`
- `wsl-hermes` -> WSL wrapper preserving the existing WSL env/TUI/voice setup.

This avoids accidentally mutating WSL auth/config when investigating Windows Desktop behavior, while preserving the WSL workflow under an explicit command.

## OpenAI Codex OAuth label convention

For this user's OpenAI Codex OAuth accounts, labels should be platform-neutral account labels:

- `codex1`
- `codex2`

Do not use labels such as `codex-windows-secondary`; the accounts are not inherently tied to Windows/WSL. However, do **not** blindly rename Hermes technical source values used for refresh/sync. In particular, a singleton OAuth source may need to remain `device_code` even if the display label is `codex2`.

## Verification

After editing the profile, open a fresh PowerShell/profile context and run:

```powershell
Get-Command hermes | Format-List CommandType,Name,Source,Definition
hermes config path
hermes auth list openai-codex
```

Then inspect runtime selection from the relevant install if needed: `resolve_runtime_provider(requested='openai-codex')` should report the expected source and a credential pool for the native Windows instance.
