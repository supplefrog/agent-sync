---
name: frontend-ui-engineering
description: Use for frontend design, implementation, and rendered UI review, including image-led new visual identities, major redesigns and reviewable prototypes. Match engineering depth to the requested fidelity. For test-only edits, use this when a UI-specific behavior, accessibility, or visual question needs its guidance.
license: MIT
metadata:
  version: 5.1.15
  author: Addy Osmani; Agent Sync adaptation
  compatibility: Requires the project's frontend toolchain and browser rendering for production verification.
  tags: [frontend, ui, accessibility, responsive-design, design-systems]
---

# Frontend UI Engineering

Build the interface for its actual task and audience. Keep visual judgment and production engineering together: a distinctive screenshot with a broken task path is unfinished; correct components with no hierarchy are unfinished too.

## Purpose before parts

Before choosing words, controls, symbols or sections, decide what the visitor should understand, feel or accomplish and how the design makes that perceptible. Before coding a new direction, compare your proposed composition with a credible competing representation and with a version that omits its weakest part. Choose the experience whose visible relationships best convey the idea. Consider typography, color, imagery and behavior together; attractive parts in isolation do not establish a coherent whole. Keep this decision compact in the working context; no compulsory scorecard or long rationale.

Test contribution by the difference a part makes, not by assigning it a category such as personality, breathing room or engagement. If removing it preserves understanding, action, orientation and the distinctive experience, omit it. If removal loses something, identify the actual loss: a needed fact, a discoverable action, a relationship, or an expressive setup/payoff. Let space, color and imagery create a pause without automatically adding a slogan to fill it. Use the strongest visual relationship rather than repeating its explanation in small text.

Avoid repetition in meaning, not just identical wording. Compare neighboring copy by what it tells the visitor, and neighboring controls by the actual state or destination they produce. Several slogans can restate one benefit; differently named buttons can perform one action; different heroes can lead to the same stock demo. Consolidate these unless the visitor's changed context supplies a reason for recurrence. Keep useful metadata, instructions, honest limitations and distinctive voice; one memorable line may lead a composition. This asks for considered taste, not minimalism or a fixed text budget. Apply it while planning and delegating the first draft, before QA.

### Recurring defaults to reject

These are concrete failures of purpose, not a blacklist of styles or characters. Current explicit choices and an established product's intentional conventions take precedence.

- **Decorative `01 /`, `02 /` and slash labels:** do not invent a serial or technical-looking system for ordinary content. Use numbering when order, position or reference matters; ordinary lists need no index or zero padding. Preserve meaningful IDs, dates, fractions, paths and chosen notation.
- **An arrow on every card, selector or button:** establish its role from the actual action, destination and result. Local selection must not suggest leaving for another destination. Directional invitations and return actions must be coherent from their use position. Conventional progression arrows need not literally trace scrolling, but a repeated corner arrow cannot mean everything. Keep meaningful navigation, disclosure, transfer and expressive symbols; omit an unhelpful cue rather than replace it with another ornament.
- **Scattered captions and miniature slogans:** remove lines that repeat a headline, visible relation or already stated benefit. Place needed information next to what it informs. Small text itself is valid; redundant, ungrounded scattering is the failure.
- **Different labels for the same choice:** consolidate actions in the same decision context. A useful action repeated at a distant reading position can save travel; keep its meaning truthful. Do not create another sales section, footer CTA or capture box simply to fill the page.
- **One shell across distinct concepts:** do not use recolors of an outlined note window, numbered feature list and bottom form as different experiences. Let the product relationship determine representation and interaction. Shared primitives and state logic are useful; cards, outlines and shadows remain available when they fit.

Use model judgment for these decisions first, suitable tools/components for concrete implementation gaps, and focused instructions for recurring failures. Keep defect QA for behavior that needs observation; do not replace a coherent first draft with a growing mandatory patch/reviewer loop. When evaluating this guidance after a model change or recurring regression, recheck the affected behavior on fresh representative work with the exact model and active skill recorded, following `instruction-authoring`. Preserve successful capabilities and nearby valid cases; do not infer a weight-level cause or add a model-specific branch from one output. Keep evidence in the existing evaluation owner, without adding a compulsory evaluation to ordinary frontend work.

## Load detail for the task

Load the applicable reference before the decisions it governs; combine modes only when the work crosses those boundaries.

- Visual direction, a visible treatment change, reference-image planning, unresolved taste, or choosing UI parts/assets: read [design-mode](references/design-mode.md). Its conditional planner, first-draft, personal-default, comparison and component protocols preserve approved directions; routine repairs do not reopen concept exploration.
- A new product, substantial flow/redesign work, an iterative repair batch, cross-environment transfer, or whole-product readiness: read [product workflow](references/product-workflow.md). A bounded local repair carries only the commitments it can disturb.
- UI implementation, responsive/layout/type/color work, component state, accessibility, or a UI-specific test/review: read [implementation detail](references/implementation-mode.md) and its affected conditional references. Nonvisual repairs need no visual exploration.
- Delivery, a readiness claim, or committing a UI change: read [delivery checks](references/delivery-mode.md), with the commit/review contract below.

Detailed procedures remain at those owners. Do not load every mode just because the skill is available.

## Preserve the task contract

Keep one compact acceptance contract in the project's existing brief, test record or handoff. Carry the intended experience, useful content/actions, rendered relationships, chosen finishing treatments and complete interaction through planning, implementation and revision. For a new build these come from the brief and applicable personal defaults; for refinement inherit the accepted render and explicit approvals. Distinguish requirements and accepted choices from provisional treatments and unverified observations; a first draft's omissions are not protected approvals. Passing one dimension cannot compensate for failing another; do not replace the contract with the latest criticism or a single overall score. Pass the same commitments to workers and reviewers. For an expressive illustration, carry its intended perceptual payoff and selected behavior or reason for stillness. Review that decision against the intended experience even if no illustration-motion feature was declared; checking only implemented effects cannot catch a missing response. A small repair needs only the commitments it could disturb, not a new document or whole-page exercise.

## Checks and visual review before commit

Move checks and design review earlier in the work. Use scoped demos before implementation when requested or needed to resolve taste, then verify the implemented experience. Any change to visible appearance—including numerical tweaks to an approved UI—needs a representative rendered artifact delivered and reviewed before committing. A requested value or approved direction does not establish approval of an unseen result. Routine nonvisual fixes need the relevant checks, without compulsory visual previews or taste selection.

Render the changed component or relevant viewport with real representative content. Deliver a viewable screenshot, before/after comparison, or accessible local/interactive preview through the user's response surface; identify the treatment and relevant state. For motion, provide a playable recording or interactive preview that exposes the changed behavior, not only a still. Internal browser inspection, tool-only screenshots, saved-but-unshared files, tests, and prose descriptions are verification, not user delivery.

Commit when the agreed checks pass and needed user review is satisfied. Within existing repository and publication authorization, commit and push together as one completion step; do not add a separate approval pause before pushing an approved commit. Resolve missing publication authorization before committing when the intended workflow includes a push. Respect explicit draft-only, hold or no-push requests and repository protections. If checks, delivery or review are blocked, keep the work uncommitted and report the blocker. An explicit review waiver or prior approval of the exact rendered treatment satisfies review; delegated taste, skipping a style comparison, silence or general commit/push permission does not. Further visible changes outside the approved treatment need another representative preview before commit, not a whole redesign exercise.

