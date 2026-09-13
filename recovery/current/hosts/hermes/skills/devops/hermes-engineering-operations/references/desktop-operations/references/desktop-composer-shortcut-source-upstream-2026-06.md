# Desktop composer shortcut source/upstream pattern (2026-06)

Use this when Hermes Desktop composer keyboard behavior is inconsistent and the first instinct is to patch the installed app.

## Classification

Composer shortcut failures can be source bugs, not config issues. For example, `Ctrl/Cmd+Enter` steering was already wired in `apps/desktop/src/app/chat/composer/index.tsx`; the intermittent failure came from the shortcut branch gating on render-derived composer state while the `contentEditable` DOM already had fresher text.

The source pattern was already known in the same file: plain Enter reads `composerPlainText(editorRef.current)` before submit/queue decisions because assistant-ui/React draft state can lag a real DOM keydown. `Ctrl/Cmd+Enter` needed the same live-DOM read before calling `steerDraft()`.

## Split duplicate symptoms

Do not bundle nearby shortcut complaints automatically:

- `Ctrl/Cmd+Z` composer undo was already covered upstream by issue `#49745` and PR `#49746`.
- `Ctrl/Cmd+Enter` missing freshly typed steer text was separate and missing, so it warranted its own issue/PR.

Search both issues and PRs with symptom and implementation terms before filing: `composer ctrl z undo`, `Ctrl+Enter steer composer`, `composer state lag Ctrl+Enter`, etc.

## Local install cleanup

If you already patched the installed Hermes source while debugging:

1. Save the useful diff if needed.
2. Revert the installed app/main branch to clean before filing/upstreaming.
3. Create a focused branch for the missing source fix.
4. Verify on that branch, push, create a PR, then switch back to the user's normal branch.
5. If a later verification guard complains, rerun checks on the PR branch that contains the edits and then restore the prior branch.

## Verification slice used

For the `Ctrl/Cmd+Enter` stale-state fix, targeted verification was:

```bash
npm --prefix apps/desktop run typecheck
npm --prefix apps/desktop run test:ui -- src/app/chat/composer/enter-submit-dom-race.test.tsx src/app/chat/composer/composer-text-guard.test.tsx
git diff --check
```

A full Desktop build is useful before telling the user the installed renderer build still succeeds:

```bash
npm --prefix apps/desktop run build
```
