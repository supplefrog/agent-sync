---
name: visual-diagrams
description: Use for designed standalone diagrams, whiteboards, and infographics.
---
# Visual diagrams

Use when the visual artifact itself is the deliverable. Choose the output branch from the requested editing model and visual purpose.

## Routing
- **Clear inline or documentation diagram:** use `mermaid-diagrams`; prefer one fenced Mermaid block for conversational explanations.
- **Technical architecture as designed standalone HTML/SVG:** read `references/architecture-diagram/SKILL.md`.
- **Editable hand-drawn diagram:** read `references/excalidraw/SKILL.md`.
- **Dense visual summary or infographic:** read `references/baoyu-infographic/SKILL.md`.

## Shared workflow
1. Identify audience, core message, entities, relationships, hierarchy, and output format.
2. Pick one branch; do not mix visual grammars without a reason.
3. Draft structure before styling. Use short labels and unambiguous edge direction.
4. Preserve source facts; avoid invented metrics, relationships, or claims.
5. Generate the real artifact and visually inspect it when tools permit.
6. Report the exact path and verification performed.

Each branch is preserved as a complete nested package under `references/<branch>/`, so internal templates, scripts, and relative links remain valid.