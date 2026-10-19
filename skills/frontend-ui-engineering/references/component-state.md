# Component architecture and state

Use this when implementing or changing component boundaries, shared state, data lifecycle, or asynchronous interactions. A visual-only repair can retain the existing architecture.

Follow the repository's file structure; colocate component code, tests, types, and styles where its conventions do. Keep components focused, prefer composition to sprawling variant configuration, and separate data lifecycle from presentation when that improves reuse and testing. Split by responsibility, not an arbitrary line count. Do not add libraries or abstract components just to follow an example.

Use the narrowest state owner that fits:

- local state for component interaction;
- lifted state for nearby shared coordination;
- context for cross-tree, relatively stable values;
- URL state for shareable filters, pagination, and navigation;
- the existing server-state mechanism for remote caching and invalidation;
- a global client store only for genuinely app-wide client state.

Shareable URL state does not automatically require a history entry. Keep local reading/selection changes from filling Back unless retracing them serves the task; preserve direct links and real page navigation. Exercise restored and early-input states against validated data so a stale default cannot win.

Restructure pass-through props when they obscure ownership; depth alone is not a reason for a store. Represent relevant loading, empty, partial, error, success, disabled, permission, and pending states. Skeletons help when the content geometry is predictable; use other progress feedback when it is not. Optimistic updates require safe semantics, rollback, concurrency handling, and reconciliation with server truth; do not optimistically imply completion of a consequential action.


Fast completion and repeated actions must not flash through transient progress labels or shift the control's contents. Observe the active feedback window as well as the settled result; preserve honest progress for perceptible waits and readable error/retry feedback.
