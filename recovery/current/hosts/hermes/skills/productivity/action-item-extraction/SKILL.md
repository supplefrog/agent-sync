---
name: action-item-extraction
description: Use to extract cited actions from meetings or documents.
---
# Action-item extraction

Turn evidence into follow-through without upgrading guesses into commitments.

## Routing
- Documents, contracts, reports, and forms: `references/document-to-action-items/SKILL.md`
- Meeting notes and transcripts: `references/meeting-action-items/SKILL.md`

## Shared workflow
1. Inventory authoritative sources, versions, dates, parties, and extraction quality.
2. Preserve provenance using page/section, timestamp, speaker, or quote.
3. Separate facts, decisions, commitments, proposals, questions, risks, prohibitions, and inferred steps.
4. Normalize outcome, owner, due date, status, dependencies, evidence, and confidence. Use `unresolved` rather than inventing values.
5. Flag contradictions, ambiguous dates, low-confidence extraction, and superseded versions.
6. Present actions, decisions, risks, and unresolved questions.
7. Default to draft tickets/messages unless mutation is authorized.

Source-specific workflows remain complete nested guides under `references/`.