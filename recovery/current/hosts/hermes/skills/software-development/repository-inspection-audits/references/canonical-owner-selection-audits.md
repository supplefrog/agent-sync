# Canonical owner and winner-selection audits

Use this when a repository is supposed to select the best implementation from experiments, worktrees, thread variants, or host-specific ports.

## Failure pattern

A green build does not prove the right candidate became canonical. Repositories commonly admit an inferior or duplicate implementation because validators check only that:

- a source directory exists;
- some result file exists;
- tests pass in isolation;
- an adapter is callable.

That misses provenance, comparison, ownership, and whether active evidence still depends on a rejected candidate.

## Audit contract

1. **Inventory every candidate and owner claim.** Search portable skill trees, integrations, adapters, tools, docs, current matrices, result summaries, and ignored/generated copies. Separate portable owners from thin host adapters and historical evidence.
2. **Name exactly one owner per capability.** Keep the owner in the portable source tree. Host integrations may consume it, but must not publish a competing skill entrypoint or own portable workflow state.
3. **Record selection state explicitly.** Admitted capabilities require a selected state, a concise decision reason, and local result evidence. Staged candidates remain unresolved; their presence is not admission.
4. **Bind evidence semantically.** Validate the ownership document against its schema. Evidence references must be canonical, non-escaping paths under the approved results root, resolve to files, and contain a capability/suite binding matching the owner they certify. Prefix plus existence is insufficient.
5. **Compare alternatives, not just the winner.** Preserve decision-changing evidence for rejected candidates: lifecycle failures, host lock-in, weaker portability, or inferior verification. Do not treat a red compatibility implementation as a repair obligation when a stronger portable winner already exists.
6. **Retire coherently.** Remove rejected current code, routes, schemas, docs, tests, installers, and smoke tools. Keep old evidence only when useful, mark it historical/superseded, and remove it from active matrices and admission summaries.
7. **Enforce absence.** Maintain retired-artifact records and fail the audit if those paths reappear. Also reject unregistered portable skills, duplicate ownership records, unsupported host adapters, and skill entrypoints under integration trees.
8. **Challenge the validator.** Add negative controls for schema-invalid ownership, duplicate owners, unregistered skills, path traversal, unrelated-but-existing evidence, stale active summaries, unsupported adapters, and retired-artifact reappearance.
9. **Verify the real distribution path.** After source changes, render/apply/verify the managed fleet or equivalent live destination. A clean repository alone does not prove consumers received the winner.

## Evidence hygiene

- Date-stamped results can remain as history, but current matrices must reference only current, capability-bound evidence.
- Embedded counts, hashes, and host claims are assertions; rerun and refresh them after deleting tests or adapters.
- A historical frozen fixture may preserve obsolete requirements for tamper testing, but label its boundary prominently so it cannot regain architectural authority.
- Independent review should attempt schema-invalid fields, `..` evidence paths, unrelated result substitution, and active references to deleted artifacts.

## Completion bar

Ship only when the current ownership contract, registry, schemas, active evidence matrix, source tree, adapters, and live distribution all agree—and the adversarial substitutions fail closed.