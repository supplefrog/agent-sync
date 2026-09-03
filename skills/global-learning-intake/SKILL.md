---
name: global-learning-intake
description: Use when a verified outcome, correction, comparison, or model change may improve persistent agent behavior. Stage one privacy-safe shadow candidate without mutating live surfaces.
version: 0.1.3
author: Local User
license: MIT
compatibility: Python 3.11+; one shared private state root accessible to the supported hosts.
metadata:
  hermes:
    tags: [learning, evidence, admission, self-improvement, shadow]
    related_skills: [capability-curator, skill-creator, github-follow-up, surface-convergence]
---

# Global Learning Intake

Use this as the single intake for potential improvements to the global agent. GitHub is one evidence adapter; user corrections, verified task failures, successful comparisons, model/runtime changes, and primary-source research can produce the same event.

The intake is **shadow-only**. It writes an append-only evidence receipt and a deduplicated candidate record. It never edits instructions, skills, memory, project files, config, plugins, routes, or live host state.

## Trigger boundary

Trigger only after a decision-changing signal is independently verified against its authoritative source. Good triggers include:

- a user correction that changes the successful behavior;
- a reproducible task failure with a confirmed better behavior;
- a matched comparison whose winner is supported by tests or explicit user preference;
- a GitHub review, CI result, or merged replacement verified against the actual code and current base;
- a changed model/runtime fingerprint that reopens instruction retirement;
- primary-source evidence that invalidates a persistent procedure.

Do not trigger on an ordinary successful task, agent self-report, speculation, one stylistic reaction, repository popularity, or raw transcript mining. Recurrence prioritizes a candidate; it does not prove promotion fitness.

Keep receipt fields distinct:

- `evidence` reports whether the source event or outcome is verified, not whether its proposed inference is approved. A verified result can still route to manual review when its lesson would weaken safety or governance.
- `recurrence` is `new` unless the same normalized candidate already has a receipt. Several examples supplied in one first-time signal do not make it `increment-only`.

## Scope and owner

Classify before staging:

| Scope/class | Shadow owner |
|---|---|
| global or cross-project generic judgment | `shared-instruction` |
| reusable procedure | `agent-skill` |
| deterministic/runtime mechanism | `host-adapter` |
| GitHub-only workflow behavior | `github-follow-up` |
| safety or governance | `manual-control-plane` |
| project convention | `project-local` |
| explicit user preference or environment fact | `user-memory` |

Classify portability before mechanism shape. `host-adapter` requires coupling to a specific host runtime, API, CLI, or implementation. A deterministic or testable procedure that applies across hosts or projects remains `agent-skill`.

Keep project conventions project-local. Stable explicit facts may go directly through the host's normal memory owner; use this intake when evidence is being proposed as a persistent behavior change or needs cross-host review.

An explicit user preference remains `user-memory` even when it concerns agent behavior or has recurred in one workflow. Route it to `shared-instruction` only with explicit global-policy intent or unrelated matched outcome evidence.

## Event contract

Create one temporary UTF-8 JSON object with:

```json
{
  "schema_version": 1,
  "source_type": "user-correction",
  "source_ref": "compact-public-safe-id",
  "observed_at": "2026-09-02T00:00:00Z",
  "scope": "global",
  "behavior_class": "generic-judgment",
  "verification": {
    "status": "verified",
    "evidence_refs": ["compact-reference-not-raw-content"]
  },
  "lesson": {
    "problem": "What verified behavior failed.",
    "better_behavior": "The narrow behavior supported by evidence.",
    "near_miss": "Adjacent behavior that must remain unchanged."
  }
}
```

Allowed source types are `user-correction`, `verified-task-failure`, `successful-comparison`, `github-outcome`, `model-runtime-change`, and `external-research`.

Never put credentials, private source text, raw transcripts, comment bodies, memory dumps, or proprietary code in the event. Use compact references and re-read the authoritative source when evaluation begins.

## Stage the event

Use one shared private store. The CLI resolves `AGENT_SIGNAL_LEARNING_STORE`, then `HERMES_HOME/cache/global-learning-intake/`, then the platform's default Hermes home. `--store` explicitly overrides that order. Do not create one ledger per host.

From this skill's directory run:

```text
python scripts/learning_intake.py ingest --event <TEMP_EVENT.json>
```

The script validates scope, evidence, timestamps, bounded fields, and credential-like content. It produces:

- `receipts/<event-id>.json`: append-only normalized evidence;
- `candidates/global/<candidate-id>.json`: global/cross-project shadow candidates;
- `candidates/local/<candidate-id>.json`: project-only routes;
- `candidates/memory/<candidate-id>.json`: user fact/preference routes.

Reingesting the same event is idempotent. Independent evidence for the same normalized lesson increments recurrence without authorizing promotion.

Delete the temporary event file after successful staging unless it is itself an approved durable artifact.

## Promotion boundary

After staging, stop. Report the candidate ID, owner, evidence count, and disposition.

A global candidate may advance only through `capability-curator` with:

1. the existing owner inspected first;
2. an explicit baseline and narrow candidate;
3. representative, near-miss, adversarial, and fresh held-out cases;
4. matched evaluation on every required host/effective stack;
5. no critical regression;
6. privacy, license, rollback, and fresh discovery checks.

Every `shadow-global` receipt must make the `capability-curator` gate and unrelated held-out proof explicit in its rationale. Recurrence alone never satisfies either requirement.

No evidence, duplicate ownership, a tie, a loss, a harness failure, or missing-host proof means **no live edit**. Subjective taste changes require repeated user preference evidence or explicit review. Safety/governance candidates always require manual approval and an equivalent protected owner.

Model/runtime changes should normally open an inverse-admission retirement plan. Never turn a stronger model into an excuse to accumulate more generic steering.

## GitHub adapter

`github-follow-up` remains responsible for discovering and reconstructing GitHub evidence. When it finds a genuinely reusable cross-project lesson, it stages a `github-outcome` event here instead of owning a second general promotion protocol. GitHub-only procedure corrections remain owned and directly tested by `github-follow-up`.

## Completion

Write the rationale as an audit explanation, using the fewest causal sentences that establish the evidence, boundary, and next gate. Name the exact destination surface (for example, the repository's project instructions or user memory) instead of substituting a generic owner label. Do not repeat receipt fields as rationale padding or add global-admission boilerplate to a local, memory, rejected, or manual-review route. A `shadow-global` route still must name the `capability-curator` gate and unrelated held-out proof.

Return one short line per staged or rejected event. Distinguish:

- `shadow-global` — queued for governed admission;
- `local-only` — must remain project scoped;
- `memory-only` — routed to explicit fact/preference review;
- rejected — unverified, unsafe, malformed, or unsupported.

Never call a staged candidate learned, admitted, installed, or active.
