---
name: creative-production-workflows
description: "Use for non-website visual and media artifacts: standalone diagrams, generative art, kinetic typography, ASCII media, GIFs, animation, ComfyUI, or TouchDesigner. Websites and product UI belong to frontend-ui-engineering."
version: 1.1.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [creative, diagrams, media, generative-art, animation]
---

# Creative Production Workflows

Route non-website visual, interactive-art, animation, and media deliverables to the narrowest production branch. Build and inspect the real artifact rather than describing one.

## Ownership boundary

- Production websites, landing pages, dashboards, forms, components, responsive layouts, accessibility, and reusable web design systems: use `frontend-ui-engineering`.
- Throwaway website/UI implementation spikes: use `spike`; use frontend guidance only at the requested fidelity.
- Website QA: use `dogfood`.
- Idea generation before a medium is chosen: use `creative-ideation`.
- This skill may still own a standalone browser-rendered artwork or visualization whose primary deliverable is the visual artifact rather than a website or product interface.

## Routing

- Clear inline/documentation diagram: use `mermaid-diagrams`.
- Designed standalone diagram, whiteboard, architecture visual, or infographic: `references/visual-diagrams/SKILL.md`.
- p5.js generative art, canvas, shaders, WebGL, or interactive visualization: `references/p5js/SKILL.md`.
- Kinetic typography or text geometry with Pretext: `references/pretext/SKILL.md`.
- ASCII banners, image conversion, or animated ASCII: `references/ascii-media/SKILL.md`.
- GIF discovery: `references/gif-search/SKILL.md`.
- Manim explanatory animation: `references/manim-video/SKILL.md`.
- ComfyUI image/video generation: `references/comfyui/SKILL.md`.
- TouchDesigner real-time visuals: `references/touchdesigner-mcp/SKILL.md`.
- A standalone one-off HTML poster, deck, or non-product visual prototype: `references/claude-design/SKILL.md`; do not use it for a production website or app UI.

Load one branch and follow its complete package. Combine branches only when their outputs genuinely compose.

## Shared contract

1. Identify the audience, message, medium, editing model, dimensions, and final format.
2. Preserve source facts and user assets; do not invent claims, metrics, or brand rules.
3. Use the existing project/toolchain when present and obtain approval before scarce or paid generation.
4. Produce the actual requested artifact at the final path.
5. Render or preview at the target size, inspect the result, run branch-specific checks, and iterate on visible defects.
6. Report the final artifact and observed verification; do not present an untested mock as complete.
