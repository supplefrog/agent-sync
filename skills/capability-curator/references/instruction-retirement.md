# Instruction retirement after model changes

Use this retirement gate when a new model or materially changed model becomes callable, or when a live surface is suspected of negative steering. It is the inverse of admission: current instructions must continue to earn their prompt weight.

## Unit classes

Classify each independently owned instruction unit before testing:

- **Generic steering** — style, planning habits, scope heuristics, generic review rituals, broad anti-slop guidance. Model-sensitive; eligible for release-triggered ablation.
- **Task procedure** — commands, APIs, file formats, local traps, scripts, templates, verification recipes. Retest when its owner/tool/environment changes, not merely because the model improved.
- **Safety/governance** — permission, privacy, destructive-action, provenance, promotion, and rollback boundaries. A model baseline may justify deduplicating wording, but never removing the guarantee. Deletion requires an equivalent enforced owner and explicit approval.
- **Environment fact** — move to config, project docs, or memory when that is the real owner; do not behavior-test stale facts.

## Cheap cascade

Do not run a whole-library curator pass.

1. **Static pass, no model calls.** Remove exact duplicates, dead references, superseded aliases, unreachable triggers, and verbatim host copies when one shared owner already supplies them. Preserve protected guarantees.
2. **Prioritize from evidence.** Queue only generic-steering units that are always-on, large, overlapping, rarely useful, repeatedly corrected, or tied to the changed model. Skip stable task procedures. Use telemetry only to prioritize; non-use does not prove uselessness.
3. **Bare-model gate.** On the new effective inference stack, run a small owner-specific suite with no candidate unit. If the bare model fails a hard requirement, retain the unit pending focused testing; do not test unrelated units.
4. **Full versus bare.** Compare the current complete owner against bare on the same cases. If full has no meaningful win, it is a retirement candidate.
5. **Leave-one-unit-out.** Compare full against full-minus-unit on owner cases plus a small cross-surface canary set. A unit is removable only when minus-unit has no critical loss and no meaningful aggregate regression.
6. **Minimize only when necessary.** If full beats bare but several units overlap, use binary splitting or delta debugging to find the smallest subset that preserves the gain. Do not evaluate every combination.
7. **Escalate judging only at the boundary.** Prefer deterministic artifact checks. For unresolved subjective cases use matched repeated trials with anonymous order-swapped judging. Separate case, repeated-generation, judge/order, and host-stack variance; the candidate model must not be its sole judge.
8. **Stop sequentially within a fixed budget.** Predeclare the practical margin, alpha/confidence rule, minimum evidence, maximum trials, and maximum agent runs. Use the bounded anytime-valid rule in `tools/eval.py`; never choose repetition after seeing the first verdict.
9. **Cache the result.** Key append-only receipts by host, exact model/provider snapshots and transport, reasoning, runtime, prompt/tool-schema/context assembly, evaluator identity, trial/seed design, decision margin, evaluation policy, unit hash, suite hash, and harness hash. Preserve raw paired observations. Reuse exact host/effective-stack matches; cross-host reuse requires an explicit equivalence hash covering the proven stack parity.

## Decision rule

Tie favors deletion for generic steering and the baseline for new admission.

Retire a generic unit only when:

- bare satisfies all hard checks or another surviving owner supplies the requirement;
- full-minus-unit has no critical loss against full;
- the unit has no unique deterministic procedure, environment knowledge, safety guarantee, or host-native capability mapping;
- a held-out or cross-surface canary does not regress; and
- rollback is available.

Use `inconclusive` rather than preserving instructions forever when evidence is noisy. Requeue only after a new signal: model/tool change, repeated failure, owner change, or better deterministic test.

## Promotion boundary

The release monitor may generate a plan and evidence. It must not mutate live surfaces. Apply reviewed retirements as one small batch, verify fresh host discovery and representative tasks, then keep a compact receipt. Do not run the host LLM curator across the whole instruction base as a substitute for this gate.

Catalog additions and release stories are research signals only. Reopen model-sensitive instruction evidence only when the canonical effective active-route fingerprint changes; the first observed fingerprint establishes a baseline without queuing work.