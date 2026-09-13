---
name: mermaid-diagrams
description: Use for clear Mermaid diagrams in chat, docs, or files.
version: 1.0.0
license: MIT
author: Local User
metadata:
  hermes:
    tags: [mermaid, diagrams, flowcharts, architecture, documentation]
    related_skills: [visual-diagrams]
---

# Mermaid diagrams

Use Mermaid when labeled nodes and edges explain the idea more clearly than prose. Optimize understanding, not visual production.

## When to Use

Use for requested flowcharts, sequence diagrams, state or entity relationships, architecture maps, and other text-first diagrams. Do not trigger merely because prose mentions several components; a diagram should materially improve understanding.

## Output ladder

1. For a conversational explanation or a request to “show the flow,” return one fenced `mermaid` block directly in chat. Do not create a file, preview, image, or custom theme unless requested.
2. For repository documentation, place the Mermaid block in the requested Markdown file or write a `.mmd` source file.
3. Render SVG, PNG, or PDF only when the user asks for a standalone artifact or the target surface cannot render Mermaid.
4. Route pixel-precise branded diagrams, editable whiteboards, hand-drawn visuals, or dense infographics to `visual-diagrams` instead.

## Choose the structure

- `flowchart`: processes, decisions, dependencies, and user journeys.
- `sequenceDiagram`: ordered interactions, APIs, and message exchange.
- `stateDiagram-v2`: lifecycles and state transitions.
- `erDiagram`: database entities and cardinality.
- `classDiagram`: type or object relationships.
- `architecture-beta` or a focused flowchart: system boundaries and deployment structure.

Use the simplest type that expresses the relationships accurately.

## Quality rules

1. Draft the message, entities, and relationships before writing syntax.
2. Keep one diagram focused on one question. Split a dense view rather than shrinking it.
3. Use short concrete labels and meaningful edge labels. Preserve identifiers exactly when they matter.
4. Choose direction for readability: branching flows often suit `TD`; short pipelines often suit `LR`. Change direction when the rendered aspect ratio is poor.
5. Use subgraphs only for real boundaries or phases. Reorder declarations to reduce edge crossings.
6. Avoid decorative classes, icons, colors, and theme directives unless they convey information or the user requests styling.
7. Do not invent entities, relationships, metrics, or chronology. State uncertainty outside the diagram.

## Persisted or rendered artifacts

When saving a diagram, retain the Mermaid source and add `accTitle` and `accDescr` where supported.

Validate persisted or rendered output with the official Mermaid CLI when available:

```text
mmdc -i diagram.mmd -o diagram.svg
```

If `mmdc` is absent, use the official package through `npx` only when downloading dependencies is permitted:

```text
npx --yes -p @mermaid-js/mermaid-cli mmdc -i diagram.mmd -o diagram.svg
```

Prefer SVG for diagrams. Use PNG when the delivery surface needs raster output. Do not send private diagram source to a remote rendering service unless the user authorizes it.

After rendering, inspect the real output for clipped labels, cramped density, edge crossings, low contrast, and a poor aspect ratio. Make at most two focused correction passes, revalidating after each. Report the source and rendered paths plus what was verified.

See `references/provenance.md` for source boundaries.
