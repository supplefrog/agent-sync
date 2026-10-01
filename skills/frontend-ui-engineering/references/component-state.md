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

Restructure pass-through props when they obscure ownership; depth alone is not a reason for a store. Represent relevant loading, empty, partial, error, success, disabled, permission, and pending states. Skeletons help when the content geometry is predictable; use other progress feedback when it is not. Optimistic updates require safe semantics, rollback, concurrency handling, and reconciliation with server truth; do not optimistically imply completion of a consequential action.

