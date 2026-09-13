# Candidate-board promotion and exact-hash admission

Use this after cross-provider discovery has produced a candidate list but before any item becomes durable task authority.

## Promote discovery into a task graph

A discovery item with only confidence, contradictions, dependencies, and disposition is not yet a task record. For every accepted item add:

- stable task ID and goal relation (`explicit` or `inferred`);
- status and priority;
- original source handles;
- dependencies and verified artifacts;
- verification state and evidence;
- one concrete next action;
- the smallest user decision, or `null`.

Validate before review:

- every task has at least one source;
- every completed task has verified evidence;
- historical roots superseded by a current explicit goal are merged, not reactivated;
- stale open flags, worker-only roots, and externally blocked work are not marked active;
- exactly one task is the current action.

Review ambiguous historical candidates one decision at a time. A blank/no-response decision keeps the candidate unresolved; it is not acceptance of the recommended default.

## Exact-hash metadata-ledger gate

Independent review applies only to the exact code, test, and contract hashes named in the request. Any post-review edit invalidates the affected receipt.

Regression coverage must include equivalent bypasses, not only the originally reported path:

- normalize offset-aware observation times to one canonical UTC representation before lexical SQL bounds/version comparison;
- require complete offset-aware provider timestamps; syntax-only datetime parsing is insufficient;
- validate every public write API, not only importer-generated values, and assert rejection occurs before any durable write;
- parse locators as typed URIs rather than relying on regex presence: require local canonical authority, reject hosted/UNC-like forms, query/control characters, and reversed byte ranges across every accepted scheme;
- restrict digests to lowercase SHA-256, IDs/versions to bounded tokens, and lifecycle assertions/relations to enumerated values;
- reserve migration sentinels so public ingestion/write paths cannot replay them as real provider/importer versions;
- replay migration from an interrupted state where a legacy row has already been copied to the destination;
- verify payload absence after transaction/WAL close and reopen.

When review finds a material bypass: add a regression that fails for the intended reason, probe sibling representations of the same defect class, implement the smallest root-cause fix, run focused and public-safety checks, recompute hashes, and request a new exact-hash review. Preserve earlier FAIL receipts rather than rewriting history. A green local suite is not admission by itself; exact-hash adversarial review remains a separate gate.
