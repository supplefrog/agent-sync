---
name: hermes-behavior-engineering
description: Use when testing Hermes model routing or answer style.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [hermes, evaluation, routing, prompt, style]
---

# Hermes Behavior Engineering

Evaluate persistent changes to Hermes generation behavior with isolated representative probes and live verification. This umbrella owns two related branches: which model/provider route performs a task, and how the selected route should express its answer.

## Route by variable

- **Model, provider, reasoning effort, auxiliary slot, delegation slot, reliability, cost, or rate limits:** load `references/model-routing-evals/SKILL.md`.
- **Tone, concision, verbosity, personality, brainstorming posture, or provider-native text controls:** load `references/prompt-style-tuning/SKILL.md`.
- **Latency, time-to-first-tool, service-tier cost, reasoning-speed tradeoffs, tool-schema trimming, or profile splitting:** load `references/behavior-engineering/latency-cost-tuning.md`.
- If several variables change, evaluate one at a time before testing the combined configuration; paid or priority settings require explicit user approval.

## Shared workflow

1. Define the target behavior, slot, baseline, acceptance bar, and rollback.
2. Capture live config, auth availability, model/provider identity, and relevant instruction surfaces without exposing secrets.
3. Use fresh isolated sessions and representative positive plus regression cases.
4. Keep prompts, tools, fixtures, and reasoning fixed unless they are the variable under test.
5. Grade task success and externally verifiable outcomes before style, latency, token use, or cost.
6. Repeat enough to expose intermittent provider or behavioral variance.
7. Apply only a meaningful repeatable gain, read config back, and run a fresh-session smoke test.
8. Leave the simpler baseline unchanged when evidence is inconclusive.

## Boundary

Use `hermes-agent` or the local operations owner for ordinary configuration mechanics. Use this skill when behavior quality is the decision variable and evidence is needed before changing defaults.
