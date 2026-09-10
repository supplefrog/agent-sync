# Windows Node/npm PATH shadowing diagnostic pattern

Use when `node`, `npm`, `npx`, or another CLI resolves to an unexpected vendor/tool binary on Windows, especially from Hermes Desktop/Git Bash.

## Diagnostic sequence

1. Capture the live shell state:

```bash
printf 'PATH=%s\n' "$PATH"
command -v node npm npx codex fnm 2>/dev/null || true
node -v 2>/dev/null || true
npm -v 2>/dev/null || true
```

2. Ask Windows resolution directly from PowerShell/cmd, not only Git Bash:

```bash
python - <<'PY'
import subprocess
for cmd in [
    ['cmd.exe','/d','/s','/c','where npm && where node'],
    ['powershell.exe','-NoProfile','-Command','where.exe npm; where.exe node'],
]:
    r = subprocess.run(cmd, capture_output=True, text=True)
    print('---', cmd[0])
    print(r.stdout)
    if r.stderr: print(r.stderr)
PY
```

3. Inspect persistent PATH scopes separately:

```bash
python - <<'PY'
import subprocess
ps = r'''
'USER_PATH_BEGIN'
[Environment]::GetEnvironmentVariable('Path','User') -split ';' | ForEach-Object { $_ }
'USER_PATH_END'
'MACHINE_PATH_BEGIN'
[Environment]::GetEnvironmentVariable('Path','Machine') -split ';' | ForEach-Object { $_ }
'MACHINE_PATH_END'
'''
r = subprocess.run(['powershell.exe','-NoProfile','-Command',ps], capture_output=True, text=True)
print(r.stdout)
if r.stderr: print(r.stderr)
PY
```

Using Python subprocess avoids Git Bash mangling PowerShell `$_.` If invoking PowerShell inline from Bash, escape `$` carefully.

4. Read suspicious wrappers before touching them. Example: a vendored `npm.cmd` may intentionally call a private `node.exe` and private `npm-cli.js`.

5. If modifying PATH, prefer removing/reordering the stale PATH entry, not deleting vendor binaries. Save a backup first:

```powershell
$userPath = [Environment]::GetEnvironmentVariable('Path','User')
Set-Content -LiteralPath "$HOME\path-user-before-edit.txt" -Value $userPath -Encoding UTF8
```

6. For `fnm`, distinguish installed from activated:

```bash
fnm --version
fnm list
fnm current || true
fnm env --shell bash
```

If `fnm current` says `fnm env` was not applied, activate it in the current shell and verify:

```bash
eval "$(fnm env --shell bash)"
command -v node npm
node -v
npm -v
fnm current
```

PowerShell profile activation:

```powershell
fnm env --use-on-cd | Out-String | Invoke-Expression
```

Git Bash activation:

```bash
eval "$(fnm env --use-on-cd --shell bash)"
```

## Reporting rule

Be explicit about scope: a registry PATH edit affects new processes; the current Hermes/Desktop process may still resolve old binaries until restart.
