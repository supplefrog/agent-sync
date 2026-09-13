# Windows Desktop composer shortcut regressions — Ctrl+Z undo and Ctrl+Enter steer

## Symptom class

- `Ctrl+Z` does not undo text reliably in the Desktop composer.
- `Ctrl+Enter` is documented/shown as steer while a turn is running, but only works sometimes, especially immediately after typing.

## Source landmarks

In the integrated Desktop app:

- `apps/desktop/src/app/chat/composer/index.tsx`
  - `ChatBar`
  - `handleEditorKeyDown`
  - `handleEditorInput` / `flushEditorToDraft`
  - `steerDraft`
  - hidden `<ComposerPrimitive.Input ... submitMode="ctrlEnter">`
- `apps/desktop/src/app/chat/composer/rich-editor.ts`
  - contenteditable serialization/helpers: `composerPlainText`, `renderComposerContents`, `insertPlainTextAtCaret`, chip deletion helpers.
- Existing nearby regression tests:
  - `src/app/chat/composer/enter-submit-dom-race.test.tsx`
  - `src/app/chat/composer/composer-text-guard.test.tsx`

## Likely mechanism

The visible composer is a custom `contentEditable` surface. Hermes also keeps Assistant UI composer state and a local `draftRef`. Native browser undo can be invalidated when the app manually rewrites DOM with `renderComposerContents`, inserts chips, handles paste through custom code, or deletes contenteditable=false directive chips. Do not assume browser undo is enough after custom DOM mutation.

For `Ctrl+Enter`, avoid deciding from render-lagged React/AUI state. The plain Enter path already has a bug-class note: read the live contenteditable DOM via `composerPlainText(editor)` because the just-typed text may not have reached composer state yet. Steer should follow the same live-DOM pattern, then sync `draftRef`/AUI before calling `steerDraft`.

## Fix pattern

- For shortcut regressions in `handleEditorKeyDown`, handle `Ctrl/Cmd+Z`, `Ctrl/Cmd+Shift+Z`, and Windows `Ctrl+Y` explicitly if custom DOM operations have broken native undo.
- Maintain a bounded local undo/redo stack keyed to draft text, not DOM nodes.
- Push snapshots before mutation paths:
  - `onBeforeInput` for normal typing.
  - custom paste handler before `insertPlainTextAtCaret`.
  - directive/chip replacement before DOM rewrite.
  - inline ref insertion and external insert paths.
  - custom Backspace/Delete selection/chip handlers.
- Reset undo/redo stacks when loading a different session/draft with `loadIntoComposer`, so undo does not jump across conversations.
- For `Ctrl/Cmd+Enter` steer, compute steerability from live editor text, not `canSteer` if `canSteer` is derived from `draft`/render state.

## Verification commands

From repo root after Desktop npm dependencies are installed:

```bash
npm --prefix apps/desktop run typecheck
npm --prefix apps/desktop run test:ui -- src/app/chat/composer/enter-submit-dom-race.test.tsx src/app/chat/composer/composer-text-guard.test.tsx
```

If `tsc`/`vitest` are unavailable, the concrete setup fix is to install workspace dependencies (`npm install` from the repo root) before claiming verification. Do not repeatedly rerun the same missing-binary command; inspect setup once, then either install with approval or report the blocker.
