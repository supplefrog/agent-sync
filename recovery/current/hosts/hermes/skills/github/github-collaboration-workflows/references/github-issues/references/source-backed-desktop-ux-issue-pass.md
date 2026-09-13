# Source-backed Desktop UX issue pass

Use this reference when a user reports several possible Desktop UX/update/file-viewer issues from observation rather than a full repro. The useful pattern is to narrow each report into a maintainer-routable issue backed by source paths, and close or skip claims that the source pass cannot support.

## Workflow pattern

1. **Search duplicates broadly, then scan locally.** Use several query terms and then fetch/scan all issues locally when keyword search is noisy. Terms like `diff`, `viewer`, `editor`, `updater`, `progress`, `auto update`, and `open file` often produce false positives, so treat matches as related only if the same user-visible failure and expected fix are present.
2. **Inspect exact UI and IPC paths.** For Desktop UX reports, cite renderer component, preload IPC method, and main-process handler together. This usually gives maintainers a routeable surface without requiring a live screenshot.
3. **Split superficially similar update problems.** In Hermes Desktop there are at least two update flows:
   - Desktop app auto-update (`electron-updater`, sidebar update state, `download-progress`).
   - Hermes Agent/engine update from Settings (`runHermesUpdate`, `install-progress`, `hermes update`).
   File separate issues when the code paths and fixes differ.
4. **Close or avoid underspecified claims.** If the current source does not support a precise symptom (for example a claimed "first task freezes" state where current components update by live tool events), comment with the inspected paths and ask for screenshot/log/event sequence rather than keeping a misleading issue open.
5. **Preserve product framing.** Do not write process notes like "I searched issues" in bodies. Related issue links should explain product overlap; duplicate-search narration stays internal.

## Example evidence anchors from Hermes Desktop

- Worktree file viewer: `src/renderer/src/screens/Chat/WorktreePanel.tsx` renders `FileViewer`; `FileViewer.tsx` reads file content and calls `window.hermesAPI.openFileInEditor(filePath)`; `src/main/index.ts` handles `open-file-in-editor` via `shell.openPath(filePath)`. This supports issues about default-app behavior vs editor chooser/open-with, and absence of file-level diff view.
- Markdown diff rendering is separate: `src/renderer/src/components/AgentMarkdown.tsx` has `DiffView` for fenced `diff` code blocks, but that does not imply the Worktree viewer can show a selected file's working-tree diff.
- Worktree panel accidental reveal/toggle: `src/renderer/src/screens/Chat/Chat.tsx` renders `WorktreePanel` beside `.chat-messages` when `contextFolder && worktreeVisible`; `ContextFolderChip.tsx` owns the explicit `FolderTree` toggle; `main.css` places `.chat-body` as a side-by-side flex row, `.worktree-panel` at fixed width, and global scrollbars at 6px. This supports a narrow issue about accidental panel opening/toggling while trying to use the chat scrollbar, but phrase hover/edge behavior as observed unless a source path proves hover-open logic.
- Settings Hermes Agent update: `src/renderer/src/screens/Settings/Settings.tsx` awaits `window.hermesAPI.runHermesUpdate()` and renders only success/error; `src/main/index.ts` emits `install-progress`; `src/main/installer.ts::runHermesUpdate` emits `step: 1, totalSteps: 1` for the whole subprocess. This supports an issue about no live Settings progress/logs.
- Desktop app auto-update: `src/main/index.ts::setupUpdater` forwards only `Math.round(progress.percent)` from `electron-updater`; `src/renderer/src/screens/Layout/Layout.tsx` stores and renders only `downloadPercent`. This supports an issue about progress appearing stuck and lacking bytes/speed/ETA/phase.

## Maintainer-quality titles from this pass

- `Worktree file viewer needs open-with/editor choice and changed-file diff view`
- `Settings Hermes Agent update shows no live progress or logs while update runs`
- `Desktop app update progress can appear stuck until download completes`

These are class examples, not facts to repeat blindly. Re-inspect current source before filing future issues.
