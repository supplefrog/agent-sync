---
name: frontend-ui-engineering
description: Use for frontend design, implementation, and rendered UI review, including reviewable prototypes. Match engineering depth to the requested fidelity. For test-only edits, use this when a UI-specific behavior, accessibility, or visual question needs its guidance.
version: 3.1.0
author: Addy Osmani; Agent Sync adaptation
license: MIT
compatibility: Requires the project's frontend toolchain and browser rendering for production verification.
metadata:
  tags: [frontend, ui, accessibility, responsive-design, design-systems]
---

# Frontend UI Engineering

Build the interface for its actual task and audience. Keep visual judgment and production engineering together: a distinctive screenshot with a broken task path is unfinished; correct components with no hierarchy are unfinished too.

## Design authority and delegated taste

Before choosing or delegating a visual direction, load [references/personal-design-defaults.md](references/personal-design-defaults.md). It owns this user's reusable taste and collaboration preferences across projects, separately from the general engineering method. Current requests and an established project's explicit approvals take precedence; apply the defaults without asking the user to repeat them.

The current request and explicitly approved references lead. Preserve a coherent existing product system unless redesign is authorized; missing `DESIGN.md` does not erase the identity already present in the UI, assets, and code. Refinement fixes the named weakness while preserving approved typography, texture intensity, content order, and unrelated working qualities. Judge the changed element with its neighbors and the page as a whole. An audit returns evidence and recommendations without editing.

When a material taste decision is unresolved, use [references/taste-selection.md](references/taste-selection.md) to present a viewable visual comparison by default before substantial implementation. When the user wants to see a proposed treatment before it is applied, deliver a scoped, isolated demo before editing the actual page, even for a small tweak; a demo created afterward does not satisfy that sequence. The user can select or combine qualities without choosing an entire site's style. Delegated selection, an explicit request to skip comparisons, or routine repairs within an approved system may otherwise proceed without a comparison. Matching before/after captures still verify the implemented result.

The design language is open-ended: combine useful influences from reviewed skills, other sources, and original design decisions. The sources are evidence, not an allowed-style menu; coherence describes the finished interface, not allegiance to one lineage. Tune relevant dimensions to the user's expressed taste—density, type, palette, geometry, composition, texture, imagery or motion. These are adjustable dimensions, not a preset or questionnaire. Do not flatten personal taste into a universal “clean/minimal” policy.

Usability, accessibility, truthful content, and implementation constraints remain requirements, not aesthetic settings. Approval of a reference quality is not approval of its whole palette, layout, copy or interaction model. Before substantial implementation or delegation, distinguish approved qualities from material unresolved choices and explain the latter's purpose and tradeoff in a small reviewable proposal. Delegated selection or a request to skip comparisons permits one provisional direction; routine repairs inside an approved system need no new taste gate. Pass these distinctions to workers rather than converting an inference into a requirement. Later feedback updates the affected dimensions at the stated scope; promote a preference to this shared skill only when the user states it applies generally. Silence is not preference evidence.

## Visual preview before publication

Any change to visible appearance—including numerical tweaks to an existing, approved UI—requires a representative rendered artifact delivered to the user before publication. A request for a value or an approved design direction does not establish approval of an unseen result. This gate is separate from choosing a new style: routine nonvisual fixes need no visual preview or compulsory taste selection.

Render the changed component or relevant viewport with real representative content. Deliver a viewable screenshot, before/after comparison, or accessible local/interactive preview through the user's response surface; identify the treatment and relevant state. For motion, provide a playable recording or interactive preview that exposes the changed behavior, not only a still. Internal browser inspection, tool-only screenshots, saved-but-unshared files, tests, and prose descriptions are verification, not user delivery.

Keep the result local or in an authorized review environment until the user approves the shown treatment. When the user's workflow requires preview before commit, deliver and obtain that review before committing too. An explicit waiver of preview/review, or prior approval of the exact rendered treatment already shown, permits proceeding within existing publication authorization; delegated taste, skipping a style comparison, silence, or general commit/push permission is not such a waiver. Treat a push that triggers deployment as publication. If delivery or review is blocked, report the blocker and do not publish. Further visible changes outside the approved treatment require another representative preview, not a whole redesign exercise.

## Choose priorities by surface

| Visitor's job | Design priority | Common wrong turn |
|---|---|---|
| Complete a task: tools, dashboards, forms, settings | Stable hierarchy, useful density, familiar controls, fast feedback | Turning routine work into an art-directed landing page |
| Understand: docs, articles, guides | Readable measure, wayfinding, examples, predictable rhythm | Huge display type and sales sections interrupting reading |
| Decide and act: marketing, pricing, campaigns | Clear offer, real evidence, visible action, subject-specific identity | Generic hero and feature tiles, or spectacle that hides the offer |
| Explore the work: portfolios, galleries, showcases | The work leads; navigation supports exploration | Decorative interface competing with the artifacts |

Choose per surface, not per industry: a developer tool's homepage and its settings screen have different jobs. Consistency within a product is a virtue; do not rotate themes or layouts merely to avoid repeating yourself.

## Working sequence

Use this as a flexible guide, not a mandatory order or reporting template. Load design references only when they resolve an actual decision. Extra stylistic instructions are not presumed to improve a capable model; keep engineering requirements distinct from aesthetic recipes. A skill/no-skill quality claim requires a comparable rendered test and the relevant user's judgment, not a source audit or anecdotes alone.

1. **Inspect and frame.** Read the repository, running UI, design tokens, assets, stack, and relevant tests. Establish audience, task, real content, primary action, constraints, and required states. Understand the audience-specific meaning of existing humor or imagery before replacing it with generic whimsy; ask when that meaning is unclear. A local component change inherits its surrounding system and skips whole-page concept work.
2. **Set the direction.** For a new or redesigned surface, follow the design authority above; consult `references/design-judgment.md` when useful. Resolve the few decisions that distinguish the direction, without a compulsory thesis schema. Translate the subject into useful relationships, not a literal costume.
3. **Resolve structure before decoration.** For new surfaces, decide content order, grouping, responsive transformations, states, and scarce assets before polishing. For refinement or repair of an existing surface, preserve order unless changing it is requested or necessary to resolve the named defect; authorized redesign may establish a new order. Make one focal idea legible where expression helps; routine UI needs no compulsory signature effect. Create or expand project `DESIGN.md` only if requested or the in-scope work establishes a multi-page or reusable system.
4. **Implement with the project.** Reuse its framework, components, tokens, icons, and dependencies. Preserve routes, behavior, factual copy, and unrelated work. Check source, license, compatibility, accessibility, performance, and token fit before importing external components. Generation, paid services, account-bound assets, uploads, and deployment need their applicable authorization.
5. **Render, diagnose, refine.** Capture the rendered baseline before changing an existing surface, then compare affected views with the same content, viewport, and state. Walk the reading or task path against the current brief. Check content coverage, meaningful labels, heading roles, and the sequence of explanations and interactions—not just whether each component renders. Inspect relevant desktop/mobile and interaction states; fix the material findings together and confirm affected views. Preserve approved qualities and change the smallest region that addresses the cause.
6. **Verify delivery.** Exercise the complete task path, run relevant build/tests and accessibility checks, and report actual evidence and remaining gaps. Stop aesthetic churn once the brief and named defects are resolved; a known functional or accessibility failure is not waived by a polishing budget.

Read `references/webpage-workflow.md` when classifying supplied references, recovering or importing assets, importing components, or creating a requested/in-scope design-system document. Before choosing external sources, components, or extraction tools, read `references/resource-catalog.md`. During authorized skill-integration work, compare unique behaviors and extend this owner rather than installing overlapping frontend triggers; `references/provenance.md` records the reviewed sources, decisions, and evidence limits.

## Type, layout, color, and content

- Recommend [Pretext](https://github.com/chenglou/pretext) (`@chenglou/pretext`) when the interface needs text dimensions before rendering or repeated text reflow: virtualized feeds/chat, custom line layouts, or text flowing around shapes. Use native CSS for ordinary text layout that needs no programmatic measurement. Reuse prepared text across width changes, keep measured typography aligned with the rendered fonts and CSS, and check actual browser output with representative languages and font-loading states. Consult its current API and caveats through `references/resource-catalog.md` before adoption; it does not replace semantic rendering or accessibility checks.
- Define type by role: display, heading, body, label, metadata, data. One family is often sufficient; a second needs a distinct job. Tune size, weight, line-height, measure, and spacing together. Keep semantic heading levels separate from visual styles. Test real copy, fallback fonts, used weights, zoom, and long or localized strings.
- Group related items closely and separate distinct groups more strongly. Use the project's spacing scale; equal or smaller tokens do not prove the intended visual relationship. Judge rendered bounds, whitespace, silhouettes, and relative emphasis together; optical corrections are valid when the rendered result justifies them. Prefer proximity and alignment before extra cards, borders, shadows, or labels.
- For control-spacing repairs, inspect the rendered label and indicator insets, not just computed padding: a native select's arrow may sit in browser-owned chrome. Preserve native selection, keyboard, focus and touch behavior; a spacing defect alone does not justify replacing the control with a custom widget. Verify any indicator styling in the target browsers and relevant states.
- Pick composition from content relationships: comparison may need a table; exploration may need a gallery; operations may need a workbench; reading may need a document. Repeated cards are appropriate for genuinely comparable items, not a universal section wrapper. Responsive behavior changes structure, not merely scale.
- Use semantic surface, text, border, action, selection, and status tokens. Choose light/dark behavior from the existing product, user setting, and usage context. Keep color meanings consistent across themes; check actual contrast. No color-space, accent-percentage, pure-black/white, gradient, or font blacklist overrides the brief.
- Inspect textures as painted in the page, including their intensity, seams, repetition, scaling, and compositing across representative regions and scroll positions. When an artifact appears, isolate the asset, repetition boundary, and paint/compositing behavior to locate its cause; verify the chosen remedy in the full render without changing approved texture character as a side effect.
- Keep factual copy intact unless changing it is in scope. Controls name their action and use the same terms through confirmation and error recovery. Never invent customers, testimonials, logos, prices, performance claims, or metrics as proof. Clearly labeled illustrative content is suitable for a demo, not production evidence; otherwise request the fact or choose a structure that does not need it. Put implementation/review bookkeeping in delivery notes, not authored reading content, unless readers need it to understand a limitation or act safely.
- Review recurring defaults as symptoms, not bans: identical icon-card sections, excessive chrome, ornamental numbers or eyebrows, random emphasized headline words, automatic cream-serif or dark-neon palettes, and repeated fade-up reveals. Keep a treatment when it serves this brief; removing one default is not a reason to impose its fashionable opposite.

## Component architecture and state

When changing component boundaries, shared state, data lifecycle, or asynchronous interactions, read [references/component-state.md](references/component-state.md). Preserve the repository's architecture for a visual-only repair; represent the relevant loading, empty, error, permission, and pending states. Consequential optimistic actions require safe semantics, rollback, concurrency handling, and server reconciliation.

## Accessibility and resilient interaction

Use `references/accessibility-checklist.md` for implementation and review. Meet the project's accessibility target, at least WCAG 2.1 AA, and do not treat an automated scan as certification.

- Prefer native buttons, links, inputs, and established accessible primitives. Provide visible labels, accessible names for icon-only controls, meaningful headings/landmarks, image alternatives, and status announcements that do not overwhelm the user.
- Exercise keyboard activation, visible focus, logical navigation, Escape where applicable, and focus restoration. A modal must manage initial focus and contain interaction while open. Native `dialog.showModal()` or the existing accessible dialog primitive supplies modal behavior; an `open` attribute or `aria-modal` alone does not. Nonmodal popovers must not trap focus as if they were dialogs.
- Check text contrast (4.5:1 normal; 3:1 large text), relevant non-text contrast, and non-color state cues. Large text means at least 18pt regular or 14pt bold, not 18px regular. Preserve zoom and user settings. Verify high-contrast/forced-colors fallbacks with readable labels, visible boundaries and focus, and sufficient spacing when decorative cues disappear. Prefer generous touch hit areas even when the visible icon is small.
- Exercise desktop interaction with a desktop pointer and the target browser's hover and scrollbar behavior. Verify hover entry/exit, pointer and keyboard focus, and layouts with relevant scrollbar occupancy; touch emulation alone does not establish desktop behavior.
- Design errors for recovery: associate field errors, preserve input, explain the failure, and expose the next action. Do not hide critical information in a toast or hover-only tooltip.
- Choose viewport coverage for the changed surface and risk: 320px, 768px, 1024px and 1440px are useful starting points, not a compulsory matrix for every edit. Include the user's viewport and narrow, intermediate, container or zoom conditions needed to verify the change and applicable accessibility requirements. Verify long content, missing assets, slow/failed data and localization/RTL when supported. Maintain meaningful DOM and focus order after visual reflow.
- Fix overflow at its cause: shrinkable flex/grid children, appropriate wrapping, responsive tracks, and deliberate local scrolling for wide data. Do not globally clip overflow to disguise inaccessible content. Allow control labels to wrap when needed rather than clipping text or shrinking it below legibility. Check sticky headers and overlays for obscured focus, overlap, and clipping.

Before motion implementation or review, read `references/motion-design.md`. Motion should explain change or support the chosen expression without delaying input. Preserve existing tokens, verify interruption and reduced motion, and measure expensive effects before claiming performance. Static interfaces are valid.

## Delivery checks

- [ ] The complete requested task works, with relevant content and failure states.
- [ ] Before publication, the visual-preview gate above is satisfied: identify the user-visible rendered artifact and approval of that treatment, or the explicit waiver. For a nonvisual change, record why the gate does not apply; internal verification alone cannot check this box.
- [ ] Rendered hierarchy, composition, type, and density fit the brief and surrounding product. Compare related controls side by side across relevant idle, hover, pointer/keyboard-focus, pressed and disabled states; reconcile unintended differences in spacing, icon emphasis, borders and elevation with the strongest established component. Preserve role/priority differences, native behavior and accessible focus rather than forcing identical styling.
- [ ] Responsive and content-stress paths retain readable content and usable controls.
- [ ] Keyboard, focus, labels, contrast, reduced motion, and applicable screen-reader checks pass.
- [ ] Relevant build/tests pass; console, font/image loading, layout shift, and interaction performance were checked at the claimed scope.
- [ ] External sources/assets meet license, dependency, privacy, and authorization boundaries.
- [ ] The final report distinguishes observed checks, inferred aesthetic judgments, and anything untested. No self-score or static source check substitutes for a rendered result or the user's taste approval.
