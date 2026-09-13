---
name: creative-ideation
title: Creative Ideation
description: "Use when brainstorming, exploring options, unsticking an idea, making it less generic, or choosing among possibilities. Apply one fitting creative method without methodology theater."
version: 2.2.0
author: SHL0MS
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [Creative, Ideation, Brainstorming, Methods, Inspiration]
    category: creative
    requires_toolsets: []
---

# Creative Ideation

Help the user reach stronger, less obvious ideas while keeping the conversation natural. Use a named method as an internal tool, not as a ceremony the user must manage.

## Trigger and boundary

Use for brainstorming, invention, alternatives, variations, creative blocks, “this feels generic,” selecting among ideas, research-question generation, or early product/project direction.

Do not use merely because ordinary implementation involves design choices. Once the user has selected a direction and asks to build it, hand off to the relevant production skill.

## Workflow

1. Identify the current need: generate, expand, unblock, subvert, refine, synthesize, or select.
2. Pick the narrowest useful method from the routing below. Load that method’s reference file before applying it. Use one method unless two genuinely supply different stages, such as generation then selection.
3. Generate past the obvious defaults internally. Return concrete options tied to the user’s real constraints, each with a mechanism and honest tradeoff. Include at least one grounded option with a feasible first step.
4. Keep the method mostly invisible. Name or explain it only when that improves the user’s thinking or they ask how the ideas were produced.
5. Follow the user’s reactions. Refine or combine what survives instead of restarting with another generic list. When they choose, stop ideating and help execute.

Ask one clarifying question only when the missing distinction would materially change the method or domain. Otherwise infer from context and begin.

## Routing

- Blank page or no useful constraint: `references/full-prompt-library.md`.
- Existing idea needs variations: `references/methods/scamper.md`.
- Existing work is stuck: `references/methods/oblique-strategies.md`.
- Output is safe, generic, or predictable: `references/methods/lateral-provocations.md`; use `pataphysics.md` only when implausibility is welcome.
- Many notes or observations need structure: `references/methods/affinity-diagrams.md`.
- Several options need a decision: `references/methods/premortem-and-inversion.md`; use `compression-progress.md` for research/project upside.
- Engineering contradiction: `references/methods/triz-principles.md`.
- Software or product structure: `references/methods/pattern-languages.md`, `first-principles.md`, or `jobs-to-be-done.md` according to the actual question.
- Research question: `references/methods/compression-progress.md`; known formal problem: `polya.md`.
- Narrative: `references/methods/story-skeletons.md`; formal writing constraint: `oulipo.md`; exhausted source material: `chance-and-remix.md`.
- System, organization, or policy intervention: `references/methods/leverage-points.md`.
- Life/career direction or unfamiliar territory: `references/methods/derive-and-mapping.md`.

If these cues conflict, prefer the user’s explicit desired effect over domain defaults. For the full catalog or close calls, load `references/method-catalog.md` or `references/heuristics.md`.

## Quality bar

Strong output is specific enough to imagine or test, non-obvious for a reason, and candid about failure modes. Avoid idea-shaped labels such as “an AI app for X” without a concrete mechanism. Do not force a fixed number, rigid template, inventor attribution, or narrated rejection ritual unless useful to the task.

## References

- `references/method-catalog.md` — compact method index.
- `references/heuristics.md` — close-call routing and edge cases.
- `references/anti-slop.md` — use when the domain strongly attracts generic answers.
- `references/exercises.md` — use when the user wants an exercise rather than generated ideas.
- `references/full-prompt-library.md` — blank-page constraints.
- `references/methods/` — individual methods; load only the chosen one.
