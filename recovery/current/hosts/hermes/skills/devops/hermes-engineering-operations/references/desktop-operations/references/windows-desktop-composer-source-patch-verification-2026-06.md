# Windows Desktop composer source-patch verification pattern (2026-06)

Use when patching Hermes Desktop renderer/source inside the installed Windows tree and verification is blocked or polluted by live app locks, missing `node_modules`, or generated build artifacts.

## Symptom pattern

- User reports Desktop composer hotkey/input regression.
- Source patch touches `apps/desktop/src/app/chat/composer/index.tsx`.
- `npm --prefix apps/desktop run typecheck` / `test:ui` initially fail because dev binaries (`tsc`, `vitest`) are unavailable.
- Running `npm install` in the live install may fail or corrupt partial `node_modules` when Desktop/Electron/Python workers are alive (`EBUSY`, `EPERM`, missing package internals like `fs-extra/lib/index.js` or `@rolldown/pluginutils/dist/index.mjs`).
- Build may modify generated files (`apps/desktop/electron/main.cjs`, `package-lock.json`, build stamps) that are not part of the intended source patch.

## Durable workflow

1. Keep the actual source edit minimal in the live repo.
2. If live `node_modules` is missing/broken/locked, do not keep retrying in-place. Create a clean temp git worktree and apply only the source diff:

   ```bash
   tmp=$(mktemp -d -p /c/Users/E/AppData/Local/Temp hermes-verify-XXXXXX)
   git diff -- apps/desktop/src/app/chat/composer/index.tsx > /tmp/hermes_composer.patch
   git worktree add "$tmp" HEAD
   git -C "$tmp" apply /tmp/hermes_composer.patch
   ```

3. In the temp worktree, install and verify the full Desktop path:

   ```bash
   npm install --no-audit --no-fund
   npm --prefix apps/desktop run typecheck
   npm --prefix apps/desktop run test:ui -- src/app/chat/composer/enter-submit-dom-race.test.tsx src/app/chat/composer/composer-text-guard.test.tsx
   npm --prefix apps/desktop run build
   git diff --check
   ```

4. After verification, remove the temp worktree and prune:

   ```bash
   git worktree remove --force "$tmp" || rm -rf "$tmp"
   git worktree prune
   ```

5. If you also ran install/build in the live repo to make the installed Desktop pick up the patch, inspect `git status --short` and revert generated/package artifacts unless the user explicitly asked to keep them:

   ```bash
   git checkout -- package-lock.json apps/desktop/electron/main.cjs
   git status --short
   ```

   The intended residual change should normally be only the source file under `apps/desktop/src/...`.

## Composer hotkey bug class

For contenteditable composer issues, beware stale React/assistant-ui state. Recent composer fixes read the live DOM (`composerPlainText(editorRef.current)`) for keydown decisions such as Enter/Ctrl+Enter, because freshly typed text can exist in the DOM before React/AUI state has caught up.

Native `contenteditable` undo can be unreliable after manual DOM rewrites (`renderComposerContents`, replacing trigger text with chips, external inserts). A safer fix pattern is an explicit draft undo/redo stack keyed around `beforeinput`, paste/drop/insert/chip mutations, and `Ctrl+Z` / `Ctrl+Shift+Z` / `Ctrl+Y` handlers that restore via the same render path as normal draft loads.
