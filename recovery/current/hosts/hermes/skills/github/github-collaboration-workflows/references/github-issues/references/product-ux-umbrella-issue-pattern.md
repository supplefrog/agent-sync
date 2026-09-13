# Product UX umbrella issue pattern

Use when the user describes broad product friction spanning several visible symptoms (for example: confusing delete behavior, hidden history, resume ambiguity, and search gaps around one underlying workflow).

## Pattern

1. Do not immediately file the narrowest symptom as a standalone issue.
2. Search existing issues across the main symptom terms and adjacent capability terms.
   - Example query families: `compression session numbering`, `delete lineage`, `pre-compression history`, `raw compressed view`, `Ctrl+F find in chat`, `session lineage`.
3. Inspect source only enough to distinguish shipped UI/API surfaces from missing ones.
   - Example: dashboard may expose `bulk-delete`, while Desktop may only expose `deleteSession(id)`.
4. Classify existing issues into:
   - direct bug fix for one symptom,
   - related feature request,
   - broader product principle gap,
   - duplicate/overlap.
5. Draft an umbrella request when the real problem is an implementation detail leaking into UX.
   - State the product principle first.
   - Link existing narrow issues as related work rather than duplicating them.
   - Include concrete expected behaviors and non-goals.
6. Prefer commenting on an existing broad issue if one already owns the product principle; otherwise create a new umbrella issue and cross-link the narrow issues.

## Example product principle wording

> Storage/runtime implementation details should not be exposed as primary user-facing objects. The default UI should present logical user concepts; advanced lineage/debug controls can be opt-in.

## Example session/compression UX framing

For Hermes compression chains, the user-facing concept is one long chat. The DB/runtime may store `root → #2 → #3 → #4 → #5`, but the default Desktop UX should treat that as one logical conversation:

- sidebar shows one chat, usually the latest tip;
- delete/archive applies to the whole logical lineage;
- resume opens the latest tip unless the user explicitly chooses view-only or branch-from-old-segment;
- old compressed segments are accessible as transcript/history, not normal sidebar chats;
- search/find operates across the logical conversation or clearly reports matches in compressed history.

This avoids filing only “bulk delete compressed sessions” when the actual issue is that users are being asked to manage compression shards at all.
