# Project decision checks

Use these checks when an existing project's direction is in question or a vendor choice could materially affect it. Inspect the relevant source, boundaries, tests, deployment path, and prior decisions. Compare retaining or simplifying the current approach with credible alternatives only where the choice is live. For a post-build review, include operational, security, maintenance, and deployment gaps that could change the architecture recommendation. Cite inspected files and mark conclusions provisional where evidence is missing.

When a managed service matters to the choice, verify its current pricing, limits, lock-in, migration path, and likely cost at prototype, launch, and growth scale. If those facts cannot be checked, name the unknowns rather than inventing figures.

Recommend one path, its decisive tradeoff, the strongest alternative, and the condition that would reverse the recommendation. Keep the implementation path short. Do not turn a narrow correction into a broad architecture audit.

For a new or growing project, follow its ecosystem's maintained conventions before inventing a layout. Keep responsibilities and dependencies clear, choose the smallest coherent module boundaries, and record reproducible setup/check commands. Reuse the existing README/AGENTS/status record; create an ADR only when a consequential decision's context, alternatives and consequences need to survive. Scale writing and architecture work to maintenance needs. `breadcrumb-records` owns project promotion, organization, handoff and closeout; it does not require an architecture review for every task.
