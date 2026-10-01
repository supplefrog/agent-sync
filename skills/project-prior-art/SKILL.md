---
name: project-prior-art
description: Use when starting a project or reconsidering its architecture. Compare existing implementations and relevant research before choosing, changing, or reviewing the approach.
version: 0.1.0
license: MIT
metadata:
  related_skills: [outcome-first-workflow-design]
---

# Project prior art

Start from what already works. For a new project, material redesign, or architecture review, inspect comparable implementations, reference architectures, and primary documentation before choosing a path. For an existing project, inspect the relevant implementation first. Treat old vendor assignments and model choices as prior decisions to reconcile with current user intent, not requirements to retain. When the user selects a replacement, evaluate implementation compatibility rather than reopening that preference through generic tier advice. For every new project, check GitHub for existing projects and whether relevant arXiv work could inform the design; a brief check is enough when no research fits. Neither source is a popularity contest or an instruction to copy.

Keep the search proportional to the decision. State the user's outcome and constraints, find credible examples, and compare what can be reused or adapted with what must be built. Inspect the source, license, maintenance evidence, and relevant behavior of a promising project before treating it as an implementation base. Treat papers as evidence for a mechanism, with limits, rather than proof that it will work here.

Recommend one path and the smallest useful next step. For an existing project, say what to retain, change, or defer. Briefly tell the user which approach the evidence favors before consequential implementation so they can steer. When the request authorizes building, continue in the same request. Ask when a material user-owned preference remains unresolved or a hard-to-reverse action still requires approval. Name the best alternative and the condition that would reopen the choice. Stop researching when another result is unlikely to change that choice. For a focused repair inside an established project, use the project's normal implementation path instead of reopening its architecture.

For a mid-build correction, post-build architecture review, or consequential vendor choice, use [the project decision checks](references/project-decisions.md). Keep that deeper review conditional on the actual decision.

When the choice genuinely depends on a deeper paper survey, use [the arXiv reading method](references/arxiv-reading.md). That reference contains source and citation checks; it does not impose a fixed paper count or worker fan-out on ordinary project work.
