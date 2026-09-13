# WSL to Windows-host `gh` fallback

Use this only when Hermes is running inside WSL and Linux `gh` is missing or unauthenticated while GitHub CLI may already be installed and authenticated on Windows.

## Detect both sides

```bash
command -v gh >/dev/null && gh auth status || true

powershell.exe -NoProfile -Command 'gh --version; gh auth status'
```

If normal Windows interop is unavailable but `/init` exists, retry the host check through it:

```bash
/init /mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe \
  -NoProfile -Command 'gh --version; gh auth status'
```

Do not ask for new credentials until both usable paths have been checked.

## Task-local helper

When Windows-host `gh` is the verified path:

```bash
gh_ps() {
  powershell.exe -NoProfile -Command '& gh @args' "$@"
}

gh_ps auth status
gh_ps api user --jq .login
```

If the environment specifically requires `/init`, substitute the verified `/init .../powershell.exe` prefix. Keep this helper task-local unless the user explicitly asks for a permanent shell function.

## Boundaries

- Verify the live Windows identity and exact repository permission before a write.
- Treat a scope or permission error from Windows `gh` as a GitHub authorization problem, not an interop problem.
- Do not copy tokens or credential files between Windows and WSL.
- Do not install a second `gh` or create a second login merely to avoid using an already working host CLI.
