---
name: hermes-self-engineering
description: Use when the owning Hermes behavior surface is unclear. Select the supported placement; skill-creator owns instruction content and cross-agent-surface-engineering owns cross-host parity.
version: 2.1.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [hermes, self-engineering, prompt, config, skills, routing]
    related_skills: [hermes-agent, skill-creator, cross-agent-surface-engineering]
---

# Hermes surface placement

Use for an unresolved placement decision, not a known-owner wording edit. Identify the unwanted behavior and a nearby valid case; distinguish missing instructions from a bad trigger, conflict, stale procedure, unsupported mechanism, or failure to follow an existing rule.

Load `hermes-agent` for supported operations. Inspect the active home/profile, relevant config and source, and current official docs before relying on a knob or hook. Recover history only when it can explain the failure or the existing design.

## Select the direct control

- **Provider request setting:** generation mechanics such as verbosity, reasoning, service tier, JSON mode, or token limits. Display verbosity, reasoning visibility, reasoning effort, and answer length are different controls; backend acceptance does not prove the desired behavior.
- **Task-specific auxiliary/delegation config:** routing for a defined side task. A catalog entry is not proof of account availability or usable rate limits.
- **Skill:** a reusable task procedure, local trap, script, template, or conditional reference. Once selected, use `skill-creator` for content and proportional evaluation.
- **SOUL.md:** instance-wide communication and judgment defaults. Keep useful short rules inline; do not move them solely to reduce this file's word count.
- **agent.system_prompt / API override:** deployment-specific or experimental text when no named personality is selected; not a second baseline communication owner.
- **/personality / agent.personalities:** temporary or named persona overlays.
- **Memory/user profile:** stable facts and preferences, not task results or short-lived rankings.
- **Source/plugin:** only when supported higher-level surfaces cannot implement the behavior. Within authorization, preserve the source revision, diff, rollback, and fresh-runtime check. Publishing issues or PRs remains a separate action.

A one-off execution mistake or an already-correct rule may need no durable change. Do not edit another profile without explicit authorization.

## Verify placement

Check the chosen surface's actual load path, precedence, and effect. For a config change, read back the value and check backend acceptance before judging output. For a prompt/trigger change, `skill-creator` owns baseline/candidate and nearby-case checks. Compare useful outcomes and induced work, not template compliance alone.

Cross-host behavior or deployment inconsistency uses `cross-agent-surface-engineering`. Orchestration design and model routing stay with their existing owners; they are not reasons to expand this placement guide into a second control plane.
