# Desktop status/screenshot issue scope pitfalls

Use this when filing Hermes Desktop UX bugs from screenshots or brief user reports, especially composer/status-stack/loading indicators.

## Preserve the user's exact complaint dimension

A screenshot can show several visible inefficiencies. Do not generalize the report beyond the user's stated pain:

- If the user says the task-list space is wasted and later clarifies the rows are fine, scope the issue to the empty right-side / horizontal layout, not row height or vertical space.
- If the screenshot shows a stale status label while the model continues, scope the issue to status lifecycle/staleness, not generic slowness or model stall.
- Avoid suggesting row hiding, aggressive collapse, or reduced progress visibility when the complaint is unused width or misleading state.

Good issue body wording:

> The task rows themselves are not the problem. The issue is horizontal layout: the status surface reserves the full composer/chat width even though the visible labels and controls occupy a much narrower column.

## Source-backed Desktop status patterns

For composer status/task/list bugs, inspect these areas first:

- `apps/desktop/src/app/chat/composer/status-stack/index.tsx` — status stack container; may use `absolute inset-x-0` full-width overlay and measured height CSS vars.
- `apps/desktop/src/app/chat/composer/status-stack/status-row.tsx` — row title/content caps such as `max-w-[18rem]` that can create empty horizontal space inside a full-width card.
- `apps/desktop/src/components/chat/status-section.tsx` and `components/chat/status-row.tsx` — shared row/section chrome.
- `apps/desktop/src/components/assistant-ui/thread.tsx` — response loading / stream stall status rows and visible labels such as `Summarizing thread`.
- `apps/desktop/src/store/compaction.ts` — per-session compaction flag exposed as `$compactionActive`.
- `apps/desktop/src/app/session/hooks/use-message-stream.ts` — gateway event handling that sets/clears status flags (`status.update`, `message.start`, `message.complete`, `error`).

## Stale status lifecycle pattern

When a UI status says an old phase is still active while the model is visibly doing later work, inspect whether the renderer only clears that phase on turn boundaries. Example: compaction can be set on `status.update.kind === 'compacting'` and cleared on `message.start`, `message.complete`, or `error`; if no fresh `message.start` occurs after in-turn compaction finishes, the label can remain stale until turn completion.

Issue language should separate:

- observed behavior: the visible status row text/timer from the screenshot,
- expected behavior: phase label clears or changes once the backend phase changes,
- source hypothesis: state flag lifecycle may not receive an in-turn clear event.
