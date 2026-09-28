---
name: project-prior-art
description: Use when starting or materially redesigning a project. Find existing implementations and relevant research before inventing a new approach; use GitHub and arXiv when they can change the design.
version: 0.1.0
license: MIT
metadata:
  related_skills: [outcome-first-workflow-design]
---

# Project prior art

Start from what already works. For a new project or a material redesign, inspect comparable implementations, reference architectures, and primary documentation before choosing a structure. GitHub is a source of existing projects, including nearby approaches that solve only part of the problem. For agent or research-heavy work, check relevant arXiv work for mechanisms and failure modes that could change the design. Neither source is a popularity contest or an instruction to copy.

Keep the search proportional to the decision. State the user's outcome and constraints, find credible examples, and compare what can be reused or adapted with what must be built. Inspect the source, license, maintenance evidence, and relevant behavior of a promising project before treating it as an implementation base. Treat papers as evidence for a mechanism, with limits, rather than proof that it will work here.

Choose a practical starting point and the smallest useful slice. Briefly tell the user which approach the evidence favors before consequential implementation so they can steer. When the request authorizes building, continue in the same request unless the choice depends on an unresolved user preference or is hard to reverse. Name the best alternative and the condition that would reopen the choice. Stop researching when another result is unlikely to change that choice. For a focused repair inside an established project, use the project's normal implementation path instead of reopening its architecture.

When the choice genuinely depends on a deeper paper survey, use [the arXiv reading method](references/arxiv-reading.md). That reference contains source and citation checks; it does not impose a fixed paper count or worker fan-out on ordinary project work.
