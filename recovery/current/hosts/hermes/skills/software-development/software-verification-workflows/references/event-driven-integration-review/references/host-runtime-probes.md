# Host-runtime probe recipes

These probes complement focused unit tests when reviewing a lifecycle plugin.

## 1. In-process child isolation

Load the plugin callback with its persistence readers stubbed to return one context. Clear the relevant environment markers. Invoke once normally and once inside the host’s real delegated-child context manager.

Expected result: the normal call returns the one context; the delegated-child call returns `None`. If the child call still returns context, the plugin is checking an env marker while the host uses a ContextVar or other task-local state.

## 2. Idempotency race

Use a temporary real database and the host’s actual create API. Arrange a barrier immediately after all callers perform the idempotency lookup and immediately before the write transaction. Start several concurrent callers with the same key and distinct titles.

Expected result: one durable row and one stable returned ID. Multiple rows with the same key prove that a pre-check plus a non-unique index is not idempotency; require a unique constraint or an atomic conflict-safe insert-or-return operation.

## 3. Handoff provenance

Insert a valid-looking structured resolution/comment marker using an untrusted author or unrelated record, while keeping the event ID current. Run the integration’s handoff selector.

Expected result: the marker is ignored unless it is tied to a verified producer/caretaker record and current event. Selecting it proves an operator/parent prompt-injection or lifecycle-authority gap.

## 4. Deployment path distinction

Run a recovery script both from its source checkout and from the documented installed layout. If the source script deliberately resolves sibling installed directories, only the documented installed-layout result is production evidence; record source-only failure separately.

Always pair these probes with exact host-source references for hook firing process, commit ordering, child identity, mutation guards, and exception behavior.
