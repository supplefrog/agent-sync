---
name: hermes-prompt-style-tuning
description: Tune Hermes answer style, personality, concision, brainstorming behavior, and provider-native output controls with representative before/after probes. Use when output quality or tone is the target; do not use for general Hermes configuration or model-routing changes.
version: 2.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [hermes, prompt, style, verbosity, personality]
    related_skills: [hermes-self-engineering, humanizer, one-three-one-rule]
---

# Hermes Prompt and Style Tuning

Use `hermes-self-engineering` to choose the owning surface first. This skill handles the empirical style-tuning loop and bundled output-quality harness.

## Surface choices

- **Provider-native output control:** prefer for generation mechanics when supported.
- **Short `agent.system_prompt`/personality overlay:** tactical style defaults and experiments.
- **`SOUL.md`:** stable broad identity, judgment, and tone.
- **Task-specific skill:** output structure that belongs only to a workflow.

Do not use memory for assistant style procedures or patch Hermes source to change tone.

For current Codex request behavior, load `references/codex-text-verbosity.md`. `extra_body` is API request plumbing, not prompt text. Backend acceptance does not prove a behavioral effect; test both.

## Write lean overlays

A useful overlay:

- states the default and output order;
- preserves exceptions for audits, debugging, research, and broad tradeoffs;
- bans only the actual failure mode;
- avoids rigid word/bullet counts unless the current task explicitly requires them;
- does not duplicate skill triggers or tool rules.

Prefer a short causal rule such as:

```text
Default concise. Put the answer or recommendation first. Include the simplest mechanism or tradeoff needed for the decision. Use more structure only when the task requires it. Do not add generic follow-up offers.
```

Do not force plan mode for brainstorming. Exploration should produce concrete ideas, constraints, comparison axes, or a question only when it changes the next useful move.

## Minimal-instruction surfaces

When tuning prompts and agent-facing surfaces for this user:

- Treat concision as subtraction, not a growing list of negative instructions. Audit `SOUL.md`, `agent.system_prompt`, personality overlays, provider-native verbosity, and preference memory for overlapping owners; keep one owner for each behavior.
- Do not encode default autonomy or competence (for example, “determine the method” or “use engineering judgment”). State only requirements the agent cannot reliably infer.
- Divide instructions by task type: novel work gets irreducible intent, non-obvious constraints, and success criteria; repetitive work gets the established procedure, required format, and verification checks.
- When the user states a preference or decision, apply it without reflexively summarizing or refining it. Add a correction only when the decision is materially wrong or unsafe.
- Avoid universal rules requiring a causal model, mechanism, tradeoff, alternatives, or follow-up on every response. Such rules manufacture commentary even when the user already made the decision.
- Probe the exact corrected exchange in a fresh session. A style change is not successful if the agent merely follows a new template while still restating the user’s point.

See `references/minimal-instruction-surface-case.md` for the surface-audit and evaluation pattern that exposed this failure mode.

## Evaluation workflow

1. Restate the target behavior in plain language.
2. Capture the active config/overlay and a baseline.
3. Build representative prompts, including near-neighbor regressions.
4. Run fresh, isolated conditions with the same model/provider/reasoning unless those are the variable under test.
5. Grade output quality, not obedience to the candidate wording.
6. Compare latency/token/tool-call bloat when the overlay may change process.
7. Apply only meaningful, repeatable gains; otherwise keep the simpler baseline.
8. Probe-created sessions must use the native non-user marker when available (Hermes CLI: `--source tool`). After preserving raw output and integrating the result, delete/close the exact probe session and verify absence; process exit, stop, and archive are not deletion.
9. Read back config and run a fresh-session smoke test after applying.

Start from `scripts/output_quality_eval.py`, but update `PROMPTS`, variants, and graders for the actual target. A harness name or prior benchmark does not make its cases relevant forever.

## What to grade

Use dimensions relevant to the user:

- answers the actual question first;
- stays on the active objective;
- provides the decision-changing mechanism without padding;
- pushes back when needed;
- does not become shallow on audits, RCA, or nuanced tradeoffs;
- does not over-structure brainstorming;
- does not add generic closers;
- completes execution tasks instead of merely describing them.

Include regression cases for:

- one-line facts;
- a decision with a non-obvious tradeoff;
- a deep audit/debugging request;
- broad but bounded brainstorming;
- a task requiring actual tool execution;
- correction/steering where tangents must be dropped.

Treat one run as noisy. Repeat stochastic comparisons or use varied cases. Blind review is useful when subjective preference dominates; deterministic graders are better for exact format, task completion, and tool/result evidence.

## Provider knob probe

Test in layers:

1. Hermes config accepts and preserves the field.
2. The transport sends it on the active API path.
3. The backend accepts the request.
4. A controlled A/B shows the intended output effect.

Do not conflate reasoning effort, visible reasoning, display compactness, and answer verbosity.

## Reporting

Report baseline vs candidate, important regressions, run count, and the exact applied surface. If evidence is inconclusive, say so and leave the simpler configuration unchanged.

## Pitfalls

- Hard caps often improve short benchmark cases while making a capable model feel shallow elsewhere.
- Negative-instruction piles create the same prompt sludge they are trying to prevent.
- Prompt changes can increase tool/API turns even when final answers are shorter.
- Transient provider failures are not durable style evidence.
- Do not update a protected/bundled skill when a user-owned overlay or adjacent skill is the correct surface.
