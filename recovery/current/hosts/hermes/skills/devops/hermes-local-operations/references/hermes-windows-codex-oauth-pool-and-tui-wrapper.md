# Windows Hermes Codex OAuth pool + default TUI wrapper

Use this when the user wants the current Codex session added to native Windows Hermes, has multiple `openai-codex` OAuth accounts and wants fallback behavior verified, or wants plain PowerShell `hermes` to launch the Ink TUI.

## Add the current Codex session to Hermes if missing

Treat “this session’s OAuth token” as the current Codex OAuth **credential pair**:
the access token and refresh token. Never print either value.

1. Read `~/.codex/auth.json` and the live Hermes `auth.json` selected by
   `hermes config path`/`HERMES_HOME`. Never print token values.
2. Compare stable account identity claims and the exact access token with every
   `credential_pool.openai-codex[*].access_token`; never display identity
   values. If multiple rows represent the same existing account, keep the
   canonical `device_code` singleton over stale manual aliases and remove only
   those aliases through `removed_ids`. Do not collapse genuinely distinct
   accounts. If meeting a requested account count would require deleting a
   distinct account, stop and ask which account to remove.
3. If an exact access-token match exists, ensure the matching manual session row
   holds the current refresh token. Do not change a `device_code` singleton or a
   distinct-account row.
4. If it is absent, append one independent pool entry:
   - `auth_type: oauth`
   - `source: manual:codex-session`
   - the current access token and refresh token
   - a clear session/date label and the next fallback priority
5. Write through Hermes' locked credential-pool API, not an unlocked JSON edit.
6. Verify from a fresh process with `hermes auth list openai-codex`, then compare
   account identities and exact in-memory token values without displaying them.
   When the requested target is “previous login plus this session,” require two
   rows representing two distinct accounts.

Codex refresh tokens rotate. Hermes serializes its own refreshes through the
auth-store lock and persists the refreshed pair back to the pool. If a manually
seeded session entry receives `refresh_token_reused`, `invalid_grant`, or a
terminal 401, do not retry the same refresh token: under the lock, re-read the
current Codex credential pair, replace only that `manual:codex-session` row, and
retry once. Never overwrite a singleton or distinct-account row. Hermes preserves
quota-limited entries: 429 responses become `EXHAUSTED` and recover through their
cooldown/reset logic. A terminal auth failure that cannot recover from the current
Codex credential pair becomes `DEAD` and needs a fresh Codex login.

Do not overwrite `providers.openai-codex.tokens`, rename a singleton source, start
a device-code login, simulate quota failures, or alter existing pool entries when
the request is only to add the current session if missing.

## Verify two-account Codex fallback without touching real auth

1. Copy the real Windows Hermes auth/config into a temporary `HERMES_HOME`.
2. Load the `openai-codex` credential pool in a fresh Python process.
3. Simulate limit hits with `mark_exhausted_and_rotate(status_code=429, ...)`.
4. Re-load the pool after each hit and assert the entry count stays `2`.
5. Run `HERMES_HOME=<tmp> HERMES_TUI=1 hermes auth list openai-codex` to verify the CLI surface from a fresh runtime.
6. Verify the real `hermes auth list openai-codex` afterwards to prove the simulation did not mutate real auth.

Observed good shape:

```text
initial: count=2
  codex1 device_code
  codex2 manual:codex2

after hit 1:
  codex1 exhausted 429
  codex2 selected

after hit 2:
  count still 2
  codex1 exhausted 429
  codex2 exhausted 429
  select=None
```

If a third entry appears, look for stale manual `device_code`/duplicate `codex2` pool rows plus the auto-seeded singleton `device_code` row. Clean by keeping only the singleton source (`device_code`, label `codex1`) and one independent manual source (`manual:codex2`, label `codex2`). Do not rename the singleton source itself; `device_code` is technical source identity, not the account label.

## Native Windows PowerShell `hermes` should launch Ink TUI

For this user's Windows-native workflow, plain `hermes` in PowerShell should target native Windows Hermes and set TUI/color env vars before invoking the real exe. Use a function, not an alias, so arguments forward correctly and temporary env changes are restored.

Profile path commonly used here:

```text
{{agent-signal:HOME}}\Documents\WindowsPowerShell\Microsoft.PowerShell_profile.ps1
```

Function shape:

```powershell
function hermes {
  $hermesExe = "$env:LOCALAPPDATA\hermes\hermes-agent\venv\Scripts\hermes.exe"
  $oldHermesTui = $env:HERMES_TUI
  $oldTerm = $env:TERM
  $oldColorTerm = $env:COLORTERM
  $oldForceColor = $env:FORCE_COLOR
  $oldCliColor = $env:CLICOLOR
  try {
    $env:HERMES_TUI = "1"
    if (-not $env:TERM) { $env:TERM = "xterm-256color" }
    $env:COLORTERM = "truecolor"
    $env:FORCE_COLOR = "3"
    $env:CLICOLOR = "1"
    & $hermesExe @args
  } finally {
    if ($null -eq $oldHermesTui) { Remove-Item Env:HERMES_TUI -ErrorAction SilentlyContinue } else { $env:HERMES_TUI = $oldHermesTui }
    if ($null -eq $oldTerm) { Remove-Item Env:TERM -ErrorAction SilentlyContinue } else { $env:TERM = $oldTerm }
    if ($null -eq $oldColorTerm) { Remove-Item Env:COLORTERM -ErrorAction SilentlyContinue } else { $env:COLORTERM = $oldColorTerm }
    if ($null -eq $oldForceColor) { Remove-Item Env:FORCE_COLOR -ErrorAction SilentlyContinue } else { $env:FORCE_COLOR = $oldForceColor }
    if ($null -eq $oldCliColor) { Remove-Item Env:CLICOLOR -ErrorAction SilentlyContinue } else { $env:CLICOLOR = $oldCliColor }
  }
}
```

Verification from no-profile PowerShell after dot-sourcing the profile:

```powershell
. "$HOME\Documents\WindowsPowerShell\Microsoft.PowerShell_profile.ps1"
(Get-Command hermes).CommandType   # Function
hermes --version                   # still runs native Windows Hermes
```

Then open a new PowerShell window and run plain `hermes`; it should enter Ink TUI.
