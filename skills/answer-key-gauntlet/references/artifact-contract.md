# Artifact contract

## `.wayfinder/map.md`

```markdown
# Wayfinder Map: <effort>

## Destination
<Observable user/system outcome and definition of done.>

## Scope
- In: ...
- Out: ...

## Evidence inspected
- <source/path/URL>: <decision-changing fact>

## Decisions
| ID | Decision | Rationale | Evidence/owner | Answer-key IDs |
|---|---|---|---|---|
| D-001 | ... | ... | ... | AK-001, AK-002 |

## Constraints
- ...

## Failure modes and recovery
| Failure | Required behavior | Recovery/rollback |
|---|---|---|
| ... | ... | ... |

## Dependencies and sequencing
- ...

## Design direction
<Enough causal structure to implement without inventing product behavior.>

## Blockers
- None.
```

A blocker is acceptable only when inspection, research, and a reversible default cannot resolve it. Never hide an unresolved product decision in Design direction.

## `.wayfinder/answer-key.md`

Within a frozen key version, only `Status` and `Evidence` may change. A user-authorized scope change or independently validated oracle error uses the [governed revision path](../SKILL.md#governed-revisions-after-freezing): preserve the predecessor and its evidence, record authority and check-level differences, validate and freeze a successor, and invalidate affected checks and dependent aggregates. Never edit a frozen rule in place to pass a failing build.

```markdown
# Answer Key: <effort>

Source map: [map.md](map.md)
Key version: <version identity>
Predecessor and change record: <none for initial key; preserved key and map decision links otherwise>
Frozen before implementation: <timestamp or commit/tree identity>

| ID | Required | Source | Requirement | Verification | Pass rule | Status | Evidence |
|---|---:|---|---|---|---|---|---|
| AK-001 | yes | D-001 | ... | `<command>` or exact manual procedure | observable binary rule | UNRUN | |
```

Allowed statuses: `UNRUN`, `PASS`, `FAIL`, `BLOCKED`, `N/A`. `N/A` requires an optional condition recorded before implementing against the current frozen version; it is not an escape hatch for a difficult check. Changed checks and dependent aggregates start `UNRUN`; historical evidence stays attached to the predecessor. Retired checks need explicit change records, not silent deletion or an invented `N/A`.

## Check quality rules

- One independent behavior per row where practical.
- Include preconditions, state, viewport/device, fixture, and identity/permissions when they affect the result.
- Commands must preserve the real exit code. Store raw output or a durable artifact path in Evidence.
- Manual or visual checks require a rubric and captured evidence, not “critic says good.”
- Include relevant negative, retry, persistence/reload, cleanup, accessibility, and integration behavior.
- A required aggregate passes only when every constituent required row passes.

## Traceability gate

Before freezing:

1. Every in-scope outcome and constraint has at least one answer-key ID.
2. Every answer-key row cites a decision, constraint, failure mode, or destination clause.
3. No two rows conflict.
4. Verification is executable with the planned environment and permissions.
5. The key does not prescribe an implementation unless the implementation itself is a requirement.
