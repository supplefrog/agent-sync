# Windows Desktop model-route and fnm browser diagnosis (2026-07)

## New-session model/provider drift

A model label alone is not enough to verify routing. Compare all three layers:

1. `config.yaml`: `model.default` and `model.provider`.
2. Desktop renderer persistence: composer model, provider, and any provenance/source marker in localStorage.
3. Backend logs/session metadata: the actual `provider=...` and `model=...` used when the fresh session starts.

Observed failure class: config selected `openai-codex / gpt-5.6-sol`, but a fresh Desktop session used stale renderer state and launched as `nous / openai/gpt-5.6-sol`, producing a misleading Nous credits error. Existing sessions can route correctly while only the fresh-draft path is wrong.

Before coding, search open and closed issues/PRs for the symptom and mechanism. If an existing PR covers the stale source/provenance path, do not create another. Check out that PR in an isolated Windows worktree, run its targeted renderer tests, Desktop typecheck, and lint only the touched files, then publish the exact Windows reproduction as a PR comment. Treat unrelated CI failures as unrelated only after reading the failed job log.

## Browser CLI works in a shell but Desktop says it is missing

Separate CLI discovery from browser-engine availability:

1. Activate the user's Node manager and run `agent-browser doctor --offline --quick`.
2. Exercise the real path: open a harmless page, read its title, and close the session.
3. Inspect the stable global npm shim, not only `where agent-browser` output.
4. Compare that location with `tools/browser_tool.py::_browser_candidate_path_dirs()` and `_find_agent_browser()`.

For fnm on Windows, shell activation adds an ephemeral path under `%LOCALAPPDATA%\fnm_multishells\...`. Explorer-launched Electron processes do not inherit that shell-only path. The durable global shims live under:

```text
%FNM_DIR%\node-versions\<version>\installation
%APPDATA%\fnm\node-versions\<version>\installation
```

A source fix should discover those stable installation roots, prefer newer versions, merge them into both discovery and subprocess PATH construction, and retain `agent_browser_runnable()` validation. Add tests for explicit `FNM_DIR`, Windows `%APPDATA%` fallback, actual `_find_agent_browser()` resolution, and unreadable/missing roots. Do not hardcode a current `fnm_multishells` directory; it changes per shell.

## Windows worktree path pitfall

When Git Bash invokes Git for Windows, creating a worktree with `/c/Users/...` can be interpreted as the native path `C:/c/Users/...`. Pass a native Git path such as `C:/Users/<user>/...`, then verify with `git worktree list --porcelain` before installing dependencies. This avoids duplicating a large npm tree in the wrong location.
