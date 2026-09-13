# Windows-host tooling from WSL

Use when Hermes is running in WSL but the useful authenticated CLI/tool surface lives on the Windows host: GitHub CLI, PowerShell profile functions, Windows package managers, browser-profile-bound auth, or vendor CLIs installed only on Windows.

## Pattern

1. First check the WSL-native tool when appropriate; if it is missing or unauthenticated, do not stop there.
2. If `/proc/sys/kernel/osrelease` indicates WSL, check the Windows-host surface from inside WSL.
3. On this setup, direct execution of `/mnt/c/.../powershell.exe` can return `Exec format error`; prefer invoking Windows PowerShell via `/init`.
4. Keep the command scoped and explicit. Do not create compatibility aliases or launchers unless the user asks.
5. Verify the Windows-side command actually used the expected auth/profile before performing writes.

## Helpers

General PowerShell helper:

```bash
win_ps() {
  /init /mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe \
    -NoProfile -Command "$@"
}

win_ps '$PSVersionTable.PSVersion.ToString()'
```

GitHub CLI helper using Windows-host auth:

```bash
gh_ps() {
  /init /mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe \
    -NoProfile -Command '& gh @args' "$@"
}

gh_ps auth status
gh_ps issue view OWNER/REPO#123 --json number,title,state,labels
```

## Pitfalls

- Do not treat `gh: command not found` in WSL as proof that GitHub auth is unavailable.
- Do not ask for new credentials before checking the user's existing Windows-host authenticated surface.
- Do not substitute an adjacent GUI launcher when the task asked for an actual CLI; use the official Windows CLI command if it exists.
- Distinguish permission failure from auth discovery failure. Windows `gh auth status` can be valid while the authenticated account still lacks repository write permission.
