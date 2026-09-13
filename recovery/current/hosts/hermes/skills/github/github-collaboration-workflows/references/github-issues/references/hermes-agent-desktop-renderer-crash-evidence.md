# Hermes Agent Desktop renderer crash evidence pattern

Use this reference when filing/updating issues for Hermes Agent Desktop renderer crashes, especially screenshot-backed root error-boundary failures.

## Repo routing

There are multiple Desktop-related repos in the ecosystem. Before filing, verify which source tree/runtime produced the error:

- Older/community Desktop UI reports may belong in `fathah/hermes-desktop`.
- Current Hermes Agent Desktop app source lives under `NousResearch/hermes-agent`, especially `apps/desktop/`.
- Runtime logs can reveal the actual path, e.g. `.../hermes-agent/apps/desktop/release/win-unpacked/...` means file or update the issue in `NousResearch/hermes-agent`, not the adjacent Desktop repo.

## Evidence to gather

For a screenshot showing the root error page, extract and preserve:

- Exact user-visible title and error string.
- Buttons/affordances shown, especially whether recovery is `Retry`, `Reload window`, `Open logs`, etc.
- OS and Desktop package/app version when available.
- `desktop.log` lines around the crash, not just the screenshot.
- Whether the backend continued while the renderer was in the root error boundary.
- Whether closing/reopening the app recovered the UI or restored the same broken window state.

## Known `tapClientLookup` crash pattern

A recurring Hermes Agent Desktop failure is:

```text
tapClientLookup: Index N out of bounds (length: M)
[renderer console] [error-boundary:root]
    at UserMessage
```

This is associated with `@assistant-ui/store` / assistant-ui message indexing and can be triggered by session shrink/replacement, long chats, compaction, gateway reconnect replay, or virtualized message rendering. It can surface as the root UI error screen: `Something broke in the interface`.

Relevant source areas in `NousResearch/hermes-agent`:

- `apps/desktop/src/main.tsx` wraps the app in the root `ErrorBoundary`.
- `apps/desktop/src/components/error-boundary.tsx` renders the root recovery UI.
- `apps/desktop/src/components/assistant-ui/thread-virtualizer.tsx` renders virtualized `ThreadPrimitive.MessageByIndex` rows.
- `apps/desktop/src/components/assistant-ui/message-render-boundary.tsx` is a local mitigation intended to swallow transient `tapClientLookup` / `tapClientResource` out-of-bounds races.

If logs still show `[error-boundary:root]`, say so explicitly: either the running packaged build lacks the mitigation or a path is escaping the local message boundary.

## Issue handling

Search before filing. As of this reference, related existing Hermes Agent issues included:

- `NousResearch/hermes-agent#41693` — root error-boundary crash from `tapClientLookup`.
- `NousResearch/hermes-agent#44562` — similar crash framed around unexpected tool data.

Prefer adding new screenshot/log/source evidence to the broad existing issue when it describes the same root error-boundary failure. Create a new issue only when the symptom is clearly different (for example, a recovery button that does not work independently of `tapClientLookup`).

## Good wording

Keep the claim narrow and evidence-separated:

- Observed: screenshot/log shows `tapClientLookup: Index 14 out of bounds (length: 8)` and root error boundary.
- Evidence: quote `desktop.log` lines and source paths.
- Suspected trigger: long chat/session replacement/context compaction if logs show preflight compression or session switching nearby.
- Open question: whether packaged build lacks mitigation or another render path sits outside the mitigation boundary.
