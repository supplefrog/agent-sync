# Evidence basis

The architecture uses mechanisms supported by canonical sources rather than marketplace convention.

| Decision | Primary evidence |
|---|---|
| Use portable `SKILL.md` directories | [Agent Skills specification](https://agentskills.io/specification) defines the cross-product format; [OpenAI Codex](https://developers.openai.com/codex/skills) and [Hermes](https://hermes-agent.nousresearch.com/docs/user-guide/features/skills) both support it. |
| Evaluate baseline versus skill on representative tasks | [Agent Skills evaluation guidance](https://agentskills.io/skill-creation/evaluating-skills) and Anthropic's official [`skill-creator`](https://github.com/anthropics/skills/tree/main/skills/skill-creator) use task suites, baseline comparison, assertions, and iterative improvement. |
| Optimize triggering separately from task quality | [Agent Skills description optimization](https://agentskills.io/skill-creation/optimizing-descriptions) treats trigger behavior as its own evaluation problem. |
| Share one skill tree | Hermes documents `skills.external_dirs`, explicitly citing `~/.agents/skills/` shared by multiple AI tools; Codex documents `$HOME/.agents/skills` as a user scope. |
| Keep host-specific enforcement thin | Hooks and prompt files are host mechanisms, while Agent Skills are portable. No canonical universal hook contract exists across the supported agents. |
| Separate admission from lifecycle cleanup | Hermes Curator uses telemetry, staleness, consolidation, archival, and pruning. Those signals do not test whether a new capability beats the live baseline. |

## What was deliberately rejected

- Installing the highest-ranked marketplace result.
- Treating stars, downloads, reviews, or an upstream benchmark as local proof.
- Making the existing Codex-only pre-tool hook the source of truth.
- Copying the same skills into separate Codex and Hermes stores.
- Requiring a heavyweight benchmark platform before every low-risk change.

The local harness keeps the useful parts of official skill-creator workflows—fresh baseline/candidate runs, held-out cases, blinded ordering, deterministic assertions, and durable evidence—without binding the repository to one model API.
