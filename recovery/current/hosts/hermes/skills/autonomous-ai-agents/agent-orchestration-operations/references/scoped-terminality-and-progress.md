# Scoped Terminality and Anti-Progress-Theater

Use when a workflow has trials, comparisons, architecture decisions, reviews, promotions, or parent/child tasks.

## Invariant

Terminality belongs to the card's declared outcome and immutable acceptance contract. Never infer that a broader decision is complete because one evidence-producing child is terminal.

Examples of distinct outcomes:

- candidate trial completed;
- provider comparison completed;
- architecture selected;
- independent review passed;
- live promotion completed.

Each may be represented by a separate task or typed state, but they cannot collapse into one generic `done` rollup.

## Required state

Persist or derive:

- `outcome_scope` — what this task can legitimately claim;
- `evidence_scope` — what artifacts/checks were actually produced;
- `decision_scope` — which decision, if any, this task is authorized to close;
- unmet comparisons/checks and material caveats;
- review/promotion state separate from implementation completion.

A completion transition must fail or remain review-required when the claimed result exceeds these scopes.

## Reporting

Stakeholder briefs state the narrow terminal fact and the broader nonterminal state together: “candidate trial completed; comparative decision not run” rather than “memory work done.” Preserve missing comparisons, failed checks, and no-promotion outcomes.

## Held-out regression

Create a candidate trial that passes every trial-level check while the required comparison lane is absent. Assert:

1. the trial may become terminal;
2. the comparison/architecture/promotion task remains nonterminal;
3. no rollup or summary claims a winner or completed decision;
4. adding a polished result narrative cannot bypass the scope check.

## Failure modes

- treating activity or artifact production as outcome completion;
- rolling child `done` into parent `done` without parent acceptance;
- hiding missing comparisons inside comments while the headline says done;
- allowing the worker that produced evidence to widen the decision scope;
- using one generic result string for implementation, review, and promotion.