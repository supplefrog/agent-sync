# Desktop session-bleed issue pattern

Use this reference when filing or auditing Hermes Desktop issues where the selected session, transcript, composer, and composer-adjacent status rows disagree.

## Durable lesson

For Desktop multi-session UI bugs, do not describe the issue as a vague “random message” or “stale UI” symptom. Frame it as a session-scoping invariant failure:

- selected sidebar row / stored session id
- active runtime session id
- shared foreground transcript store
- composer state and queue key
- composer-adjacent status rows / background process rows
- streamed updates from background sessions

The maintainer-useful report states which visible surfaces disagree and which source paths own the scoping boundary.

## Useful active-source paths

- `apps/desktop/src/app/session/hooks/use-session-state-cache.ts` — per-runtime session cache; shared foreground `$messages` synchronization; active-session guard; RAF-flushed pending view state.
- `apps/desktop/src/app/chat/composer/index.tsx` — composer session keys; queue session key vs runtime status session id; renders `ComposerStatusStack`.
- `apps/desktop/src/app/chat/composer/status-stack/index.tsx` — composer-adjacent status rows; reads `$statusItemsBySession` by session id; refreshes background processes for the current session.
- `apps/desktop/src/store/composer-status.ts` — merges todos, subagents, and background process rows per session.

## Issue-writing checklist

1. State the invariant: every visible chat surface should be scoped to the same selected session.
2. Describe evidence from screenshots or reproduction as surface mismatch, not agent/process confusion.
3. Separate transcript bleed from composer/status-stack bleed when possible.
4. Cite active `apps/desktop` source paths, not older standalone Desktop paths.
5. Avoid repo-routing notes, apology, duplicate-search narration, or “I verified” process comments.
6. If a report is underspecified, close/withdraw with clear refile criteria rather than preserving stale source evidence.

## Example concise summary

“After switching sessions, Desktop can keep showing the prior session’s transcript/status rows above the composer while the sidebar highlights a different session. This makes the active target ambiguous and can cause the user to respond in the wrong conversation.”
