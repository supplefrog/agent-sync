# Research-First Intake Gates

Use when diagnosing or changing task creation, specification, or promotion in a control plane that implements the evidence modes below. These are that mechanism's integrity checks, not prerequisites for ordinary task execution.

## Failure class

Worker-time research instructions cannot repair a task that was already shaped and promoted from an unsupported premise. A detailed actionable card is not evidence that the action is justified. Correcting that card is containment; the RCA must trace:

1. user intent and the implied decision;
2. card/task creation premise;
3. specification or decomposition prompt;
4. structured-output parsing and validation;
5. persisted promotion/state transition;
6. worker-visible context and skill load timing;
7. completion and reporting semantics.

Fix creation → specification/decomposition → promotion → dispatch at the narrowest owning boundary, including sibling paths. A skill loaded after dispatch cannot govern earlier task shaping.

## Pre-promotion contract

Before a task becomes runnable, persist exactly one evidence mode with a concrete reason:

- `research_required` — material or novel direction where supported existing solutions or external evidence may change the action;
- `reuse_established` — a named trustworthy procedure, baseline, research receipt, or supported native owner already applies;
- `not_applicable` — bounded mechanical work where research cannot change the correct action; convenience is not a reason.

For `research_required`:

1. inspect supported/native solutions, primary documentation and external evidence, and relevant prior local artifacts;
2. compare retain, simplify, adapt, replace, remove, and no-change where credible;
3. reuse public evaluations rather than repeating them locally;
4. run local experiments only for unresolved decision-changing integration gaps;
5. keep implementation and promotion gated on that evidence.

The evidence decision belongs in durable task state or the worker-visible body, not only in chat, an operator comment, or a skill loaded after dispatch.

## Fail-closed boundaries

- Treat model output as untrusted input. Accept only one complete JSON object with surrounding whitespace, or one complete JSON object inside one complete JSON fence.
- Reject arbitrary prefix/suffix prose, trailing garbage inside or outside fences, multiple objects, non-object JSON, malformed fences, and missing/invalid gate metadata. Never recover by slicing from the first `{` to the last `}` or by promoting malformed text as a raw body.
- Missing, malformed, or invalid evidence metadata leaves the task in triage with no children created.
- Valid title-only model output may preserve the original task plus the evidence contract; it must not promote with `body=null`.
- Evidence-only output with neither a usable title nor specification remains triage.
- A formatted body never bypasses the evidence decision.
- For research-required fan-out, require at least one parent-free evidence task. Every execution and verification child must depend directly or transitively on evidence.
- Apply the same checks to specification and decomposition/fallback paths; otherwise the sibling path recreates the bug.

## Behavioral verification

Test through the production task-command and persistence seam:

- malformed JSON, prefix/suffix prose, trailing garbage, multiple/non-object values, malformed fences, missing evidence, and invalid modes do not mutate triage state;
- one whitespace-wrapped object and one complete fenced object remain valid;
- each valid mode persists its mode and reason;
- title-only research-required output persists the worker contract;
- evidence-only output is rejected;
- invalid phases/parent indices, disconnected execution, and parented evidence tasks are rejected atomically;
- transitive evidence → execution → verification graphs preserve readiness order;
- repetitive/mechanical work remains usable without forced broad research;
- a terminal candidate trial cannot satisfy a broader comparison, architecture, or promotion criterion without immutable criterion-to-evidence scope binding;
- an independent reviewer attempts bypasses after the focused suite is green.

When an independent reviewer finds an ad-hoc bypass, reproduce it through the real seam, add the regression before the fix, and request a fresh independent review. Green self-authored tests are evidence, not authority. Close the RCA only when the owning mechanism and sibling paths are fixed, valid paths remain usable, independent adversarial review passes, coherent files are included in the handoff, and broader lifecycle verification still gates live promotion.

For candidate-trial versus comparison/architecture/promotion scope, also load `scoped-terminality-and-progress.md`.
