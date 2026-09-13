# WSL/Windows Hermes operations absorbed notes

## Windows Node PATH collision during `hermes update`

Symptom:

```text
→ Updating Node.js dependencies...
/mnt/c/Users/<user>/AppData/Local/fnm_multishells/<id>/npm: line 15: exec: node: not found
  ⚠ npm install failed in repo root
/mnt/c/Users/<user>/AppData/Local/fnm_multishells/<id>/npm: line 15: exec: node: not found
  ⚠ npm install failed in ui-tui
```

Interpretation: WSL inherited a Windows Node manager shim (`fnm`, Volta, WindowsApps, etc.) earlier in PATH than WSL-native npm. The shim is valid in Windows shells but may not find `node` from WSL.

Check:

```bash
hermes --version
type -a node npm
```

If Hermes says up to date, repair the post-update npm refresh rather than repeating the whole update.

Recovery:

```bash
export WSL_NODE="$(dirname "$(command -v node)")"
export CLEAN_PATH="$WSL_NODE:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:$HOME/.local/bin"

cd /usr/local/lib/hermes-agent
env PATH="$CLEAN_PATH" npm ci --no-fund --no-audit --progress=false \
  || env PATH="$CLEAN_PATH" npm install --no-fund --no-audit --progress=false

cd /usr/local/lib/hermes-agent/ui-tui
env PATH="$CLEAN_PATH" npm ci --no-fund --no-audit --progress=false \
  || env PATH="$CLEAN_PATH" npm install --no-fund --no-audit --progress=false
```

If `command -v node` resolves to `/mnt/c/...`, source the WSL Node manager or use the known WSL Node bin path such as `$HOME/.nvm/versions/node/<version>/bin`.

## PowerShell → WSL Hermes wrapper

PowerShell aliases cannot include arguments reliably. Use a function that calls `/usr/local/bin/hermes` through `wsl.exe env PATH=...` with a sanitized PATH.

Pattern:

```powershell
if (Test-Path Alias:hermes) { Remove-Item Alias:hermes -Force }
function hermes {
    param([Parameter(ValueFromRemainingArguments=$true)] [string[]]$HermesArgs)
    $wslPath = 'PATH=/root/.nvm/versions/node/v24.12.0/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin'
    if ($MyInvocation.ExpectingInput) {
        $input | wsl.exe env $wslPath /usr/local/bin/hermes $HermesArgs
    } else {
        wsl.exe env $wslPath /usr/local/bin/hermes $HermesArgs
    }
}
```

Verify from WSL with Windows PowerShell in no-profile mode, dot-source the profile, then run harmless commands such as `hermes --version`. If it launches interactive UI instead of printing the version, argument forwarding is suspect.
