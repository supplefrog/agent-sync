# Research workflow ownership

Use this boundary when several research/design workflows could all trigger before a persistent capability change.

## Owners

- **Capability admission** owns the outcome contract, baseline comparison, retain/adapt/replace/build decision, validation gate, and promotion.
- **Iterative blind research** owns open-ended candidate discovery, query mutation, source coverage, and shortlist evidence when first-pass search may miss the answer.
- **Advise project approach** owns comparison and adaptation when an enabled skill, native feature, reference architecture, comparable project, framework, or established approach may satisfy the project.
- **NeuroArxiv** owns the architecture recommendation only after that comparison finds no adequate existing approach and the remaining choice is a genuinely new project-architecture decision.
- **Workflow runners/delegation** own execution mechanics—fan-out, persistence, retries, and synthesis—not product or admission judgment.

## Conflict check

Before launching research:

1. Identify one final decision owner.
2. Give each helper one evidence-producing responsibility.
3. Verify no helper independently claims retain/adapt/replace/build or promotion authority.
4. Inspect live discovery roots and staged repositories separately; a staged draft is not an installed owner.
5. If a staged workflow substantially duplicates the decision owner, preserve only its missing distinction in the owner and remove the redundant draft rather than promoting both.
6. Run an independent trigger/ownership review before an expensive workflow when ambiguity could multiply work.

A clean composition has one decision owner, several bounded evidence providers, and one execution substrate. Overlapping verification steps are acceptable; overlapping authority is not.