# Repository rules

Use [Agent Signal skill-creator](skills/skill-creator/SKILL.md) for durable/shared instruction content. Identify this owner by source path; Codex's bundled `.system/skill-creator` owns Codex-only scaffolding and UI metadata.

Use [cross-agent-surface-engineering](skills/cross-agent-surface-engineering/SKILL.md) for cross-host placement or parity, and [hermes-self-engineering](skills/hermes-self-engineering/SKILL.md) for unresolved Hermes placement. Preserve native capabilities and explicit unsupported mappings; existing procedures remain reviewable within the user's authorization.

Keep `skills/` compatible with the Agent Skills standard. Put host-specific behavior in adapters, not portable skill instructions.

Match evidence to the claim: reproduce and verify a mechanism correction, check source/discovery for structural changes, and compare current-model behavior for quality claims. Carry existing authorization forward, preserve rollback, and state missing or inconclusive evidence.

Treat `contracts/surface-matrix.json` as the cross-host behavior contract and `evidence/findings.json` as the public-safe findings and contradiction ledger. Never erase contradictory evidence merely to present a unified result.

Keep the repository small: extend or replace an existing capability when its scope substantially overlaps; do not add aliases or speculative skills.

Choose supported worker routes from task requirements and available evidence. Fixed model tiers or reasoning labels are not fitness tests. Keep persisted runs pinned unless changing their route is part of the authorized task.

Never commit generated run transcripts, credentials, private paths, or third-party content without a compatible license.
