# Windows Desktop update: shallow count + generated `main.cjs` dirty state (2026-06)

Use when Hermes Desktop update status repeatedly shows huge counts like `+12k`, or when source installs become dirty after updating.

## Evidence pattern

Local Windows source install:

```text
Hermes Agent v0.17.0 · upstream 9b2af36d
Project: {{agent-signal:HERMES_HOME}}\hermes-agent
```

Git state before cleanup:

```text
## main...origin/main [ahead 1, behind 1]
 M apps/desktop/electron/main.cjs

git rev-parse --is-shallow-repository
true

git merge-base HEAD origin/main
# no output
```

`git rev-list HEAD..origin/main --count` may report a bogus large value when a shallow checkout has no visible merge-base. It is not real update distance.

The dirty file was generated/bundled Electron output, not a hand source edit:

```text
apps/desktop/electron/main.cjs | 17744 +++++++++++++++++++++++++++------------
12472 insertions(+), 5272 deletions(-)
```

The diff began with bundler boilerplate and inlined modules:

```diff
+"use strict";
+var __create = Object.create;
+var __defProp = Object.defineProperty;
+// electron/bootstrap-platform.cjs
+// electron/bootstrap-runner.cjs
+// electron/update-count.cjs
```

An updater-created stash can contain only the same generated file:

```text
stash@{0}: On main: hermes-update-autostash-YYYYMMDD-HHMMSS
M apps/desktop/electron/main.cjs
```

## Interpretation

There are two related but distinct issues:

1. **Fake update count**: shallow/no-merge-base git history makes exact commit counts unreliable. Correct behavior is presence-only: compare SHAs and show “update available”, not `+12000`.
2. **Dirty generated bundle**: update/build can overwrite tracked `apps/desktop/electron/main.cjs` with bundled output. That is build hygiene, not user source work.

Desktop-side count had an existing fix path (#51922). CLI update still had an unguarded `rev-list --count` path and was fixed upstream via PR #53512 / issue #53479.

## Safe triage steps

1. **Do not run `hermes update` while active Desktop/TUI workers are live.** First inspect process tree if available.
2. Check source state:
   ```bash
   cd "$LOCALAPPDATA/hermes/hermes-agent"
   git status --short --branch
   git rev-parse --is-shallow-repository
   git merge-base HEAD origin/main || true
   git diff --stat
   git stash list
   ```
3. If only `apps/desktop/electron/main.cjs` is dirty and the diff starts with bundled output, treat it as generated state.
4. If the user accepts cleanup, restore that generated file and drop any updater autostash that contains only that file:
   ```bash
   git restore -- apps/desktop/electron/main.cjs
   git stash show --stat stash@{0}
   git stash drop stash@{0}  # only if it contains no real user/source edits
   ```
5. For upstream work, split issues:
   - shallow/no-merge-base exact count should be avoided in CLI/Desktop update tracking;
   - generated `main.cjs` should not be left dirty after update/build;
   - updater should warn/defer/force when active Desktop agent workers exist.

## Windows process-holder and repair-installer traps

A Windows update can be blocked by orphaned read-only probe commands such as:

```text
hermes.exe prompt-size ...
hermes-agent.exe --version
```

Inspect command lines before killing anything. It is safe to terminate only those stale probe trees; do not kill live `serve`, `tui_gateway.slash_worker`, gateway, terminal, or user-task processes. Re-check after a short delay because healthy probes should exit rather than remain as venv holders.

A bare launch of an old staged `hermes-setup.exe` is the install/repair path, not the Desktop update handoff. Its cached `bootstrap-cache/install-main.ps1` may use `git pull --ff-only` and fail on the same shallow/no-merge-base checkout with `fatal: Not possible to fast-forward`. Do not reinstall to solve this. Prefer the Desktop client update handoff or a normal `hermes update` after closing Desktop; those updater paths can reset a clean divergent shallow checkout to the target branch. Remove only a stale cached `install-main.ps1` so a future repair downloads the current script, and remove `.git/shallow.lock` only after verifying no git process is still running.

## Verification notes

- Current TypeScript Desktop tests run with Vitest, for example: `vitest run --project electron electron/updater-process.test.ts electron/update-count.test.ts electron/bootstrap-runner.test.ts`.
- Older `.cjs` update-count tests use `node --test`; do not run JavaScript tests through `pytest`.
- If a wrong test runner fails, rerun the correct command before claiming verification.
- Confirm a clean working tree, no stale git/update lock, no orphaned read-only probe holders, `hermes update --check`, and `hermes config check` before handing control back to the in-app updater.
