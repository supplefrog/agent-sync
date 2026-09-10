# Shared instruction ownership

This file is a non-injected reference, not another prompt body. The effective host overlays are `recovery/current/hosts/hermes/SOUL.md` and `recovery/current/hosts/codex/AGENTS.md`; `contracts/instruction-surfaces.json` records where they actually load. Do not infer OMP inheritance from the Codex artifact's existence.

| Concern | Owner |
| --- | --- |
| Standing communication, judgment, artifact links, and orchestration consent | Host overlays; preserve necessary native differences |
| Chat-style calibration and consequential design updates | `skills/conversational-communication` |
| Instruction content, triggers, sentence-level intent, and evaluation | `skills/skill-creator` |
| Unresolved Hermes placement | `skills/hermes-self-engineering` |
| Cross-host placement, parity, deployment, and recovery | `skills/cross-agent-surface-engineering` |
| Unresolved workflow design | `skills/outcome-first-workflow-design` |
| Model-route research and qualification | `skills/openai-delegation-route-research` |
| Persisted DAG execution | `skills/dynamic-workflows` |

# Capability admission

Before installing, enabling, creating, replacing, retiring, or materially changing a shared agent capability or persistent behavior surface, use Agent Sync's `tools/reconcile.py` and the admitted `cross-agent-surface-engineering` owner. Existing admitted owners may be adopted or deployed only when deterministic checks prove a single-origin, reversible, non-conflicting change. Novel, staged, ambiguous, safety-sensitive, cross-host, or retirement changes require scoped authorization and recorded baseline/candidate evidence; they are not automatic promotions. Harness failure or missing evidence is inconclusive. Retaining the baseline is valid.

The staged `capability-curator` is not a promotion authority. Native local maintenance cannot admit, replace, or distribute portable capabilities. Project-local and ephemeral work is not promoted into shared ownership merely because an agent performed it.
