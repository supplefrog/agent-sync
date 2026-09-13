---
name: frontend-ui-engineering
description: Builds production-quality, accessible, responsive user-facing UIs. Use when building or modifying production interfaces and pages, creating components, implementing layouts, meeting accessibility requirements, managing state, or when the output needs production-quality engineering and visual decisions. Do not use for an explicitly throwaway prototype; use the prototype workflow at the fidelity the user requested.
version: 3.0.0
author: Addy Osmani; Agent Sync adaptation
license: MIT
compatibility: Requires the project's frontend toolchain and browser rendering for production verification.
metadata:
  tags: [frontend, ui, accessibility, responsive-design, design-systems]
---

# Frontend UI Engineering

Build the interface for its actual task and audience. Keep visual judgment and production engineering together: a distinctive screenshot with a broken task path is unfinished; correct components with no hierarchy are unfinished too.

## Design authority and delegated taste

The current request and explicitly approved references lead. Preserve a coherent existing product system unless redesign is authorized; missing `DESIGN.md` does not erase the identity already present in the UI, assets, and code. Refinement fixes the named weakness, not the whole visual identity. An audit returns evidence and recommendations without editing.

When the user delegates design choices or has no time for comparisons, choose and build one reasoned direction. Use approved examples and explicit corrections when available; do not invent a preferred font, palette, era, or density from general engineering preferences. Keep uncertain choices reversible and briefly label the material assumption. Ask only when missing product truth, conflicting authority, or a consequential scope choice changes the work—not to select routine CSS values or run a compulsory taste quiz.

The design language is open-ended: combine useful influences from reviewed skills, other sources, and original design decisions. The sources are evidence, not an allowed-style menu; coherence describes the finished interface, not allegiance to one lineage. Tune the relevant dimensions to the frontend engineer's taste—such as density, type character and contrast, palette, geometry, composition, texture, imagery, and motion. These are adjustable dimensions, not a fixed preset or mandatory questionnaire. Choose which dimensions matter for this task; do not flatten personal taste into a universal “clean/minimal” policy.

Usability, accessibility, truthful content, and implementation constraints remain requirements, not aesthetic settings. Where taste evidence is missing, make a reasoned provisional choice without claiming it is the user's preference. Later feedback updates the affected dimensions at the stated scope; promote a preference to this shared skill only when the user states it applies generally. Silence is not preference evidence.

## Choose priorities by surface

| Visitor's job | Design priority | Common wrong turn |
|---|---|---|
| Complete a task: tools, dashboards, forms, settings | Stable hierarchy, useful density, familiar controls, fast feedback | Turning routine work into an art-directed landing page |
| Understand: docs, articles, guides | Readable measure, wayfinding, examples, predictable rhythm | Huge display type and sales sections interrupting reading |
| Decide and act: marketing, pricing, campaigns | Clear offer, real evidence, visible action, subject-specific identity | Generic hero and feature tiles, or spectacle that hides the offer |
| Explore the work: portfolios, galleries, showcases | The work leads; navigation supports exploration | Decorative interface competing with the artifacts |

Choose per surface, not per industry: a developer tool's homepage and its settings screen have different jobs. Consistency within a product is a virtue; do not rotate themes or layouts merely to avoid repeating yourself.

## Working sequence

1. **Inspect and frame.** Read the repository, running UI, design tokens, assets, stack, and relevant tests. Establish audience, task, real content, primary action, constraints, and required states. A local component change inherits its surrounding system and skips whole-page concept work.
2. **Set the direction.** For a new or redesigned surface, read `references/design-judgment.md`. State a short visual thesis with concrete structure, type roles, palette roles, density, asset treatment, and the first viewport's priority. When the brief is open, consider materially different structures internally and choose the best fit; do not require user comparison boards. Translate the subject into useful visual relationships, not a literal costume.
3. **Resolve structure before decoration.** Decide content order, grouping, responsive transformations, states, and scarce assets before polishing. Make one focal idea legible where expression helps; routine UI needs no compulsory signature effect. Create or expand project `DESIGN.md` only if requested or the in-scope work establishes a multi-page or reusable system.
4. **Implement with the project.** Reuse its framework, components, tokens, icons, and dependencies. Preserve routes, behavior, factual copy, and unrelated work. Check source, license, compatibility, accessibility, performance, and token fit before importing external components. Generation, paid services, account-bound assets, uploads, and deployment need their applicable authorization.
5. **Render, diagnose, refine.** Run the actual UI. Inspect target desktop/mobile sizes and interaction states in a batched pass; fix the material findings together and confirm affected states. Separate task failures, design-system drift, and hierarchy problems from aesthetic alternatives. Change the smallest region that addresses the cause.
6. **Verify delivery.** Exercise the complete task path, run relevant build/tests and accessibility checks, and report actual evidence and remaining gaps. Stop aesthetic churn once the brief and named defects are resolved; a known functional or accessibility failure is not waived by a polishing budget.

For full-page work involving references or assets, read `references/webpage-workflow.md`. Before choosing external sources, components, or extraction tools, read `references/resource-catalog.md`. During authorized skill-integration work, compare unique behaviors and extend this owner rather than installing overlapping frontend triggers; `references/provenance.md` records the reviewed sources, decisions, and evidence limits.

## Type, layout, color, and content

- Define type by role: display, heading, body, label, metadata, data. One family is often sufficient; a second needs a distinct job. Tune size, weight, line-height, measure, and spacing together. Keep semantic heading levels separate from visual styles. Test real copy, fallback fonts, used weights, zoom, and long or localized strings.
- Group related items closely and separate distinct groups more strongly. Use the project's spacing scale; equal tokens do not require equal spacing everywhere. Prefer proximity and alignment before extra cards, borders, shadows, or labels. Optical corrections are valid when the rendered result justifies them.
- Pick composition from content relationships: comparison may need a table; exploration may need a gallery; operations may need a workbench; reading may need a document. Repeated cards are appropriate for genuinely comparable items, not a universal section wrapper. Responsive behavior changes structure, not merely scale.
- Use semantic surface, text, border, action, selection, and status tokens. Choose light/dark behavior from the existing product, user setting, and usage context. Keep color meanings consistent across themes; check actual contrast. No color-space, accent-percentage, pure-black/white, gradient, or font blacklist overrides the brief.
- Keep factual copy intact unless changing it is in scope. Controls name their action and use the same terms through confirmation and error recovery. Never invent customers, testimonials, logos, prices, performance claims, or metrics as proof. Clearly labeled illustrative content is suitable for a demo, not production evidence; otherwise request the fact or choose a structure that does not need it.
- Review recurring defaults as symptoms, not bans: identical icon-card sections, excessive chrome, ornamental numbers or eyebrows, random emphasized headline words, automatic cream-serif or dark-neon palettes, and repeated fade-up reveals. Keep a treatment when it serves this brief; removing one default is not a reason to impose its fashionable opposite.

## Component architecture and state

Follow the repository's file structure; colocate component code, tests, types, and styles where its conventions do. Keep components focused, prefer composition to sprawling variant configuration, and separate data lifecycle from presentation when that improves reuse and testing. Split by responsibility, not an arbitrary line count. Do not add libraries or abstract components just to follow an example.

Use the narrowest state owner that fits:

- local state for component interaction;
- lifted state for nearby shared coordination;
- context for cross-tree, relatively stable values;
- URL state for shareable filters, pagination, and navigation;
- the existing server-state mechanism for remote caching and invalidation;
- a global client store only for genuinely app-wide client state.

Restructure pass-through props when they obscure ownership; depth alone is not a reason for a store. Represent relevant loading, empty, partial, error, success, disabled, permission, and pending states. Skeletons help when the content geometry is predictable; use other progress feedback when it is not. Optimistic updates require safe semantics, rollback, concurrency handling, and reconciliation with server truth; do not optimistically imply completion of a consequential action.

## Accessibility and resilient interaction

Use `references/accessibility-checklist.md` for implementation and review. Meet the project's accessibility target, at least WCAG 2.1 AA, and do not treat an automated scan as certification.

- Prefer native buttons, links, inputs, and established accessible primitives. Provide visible labels, accessible names for icon-only controls, meaningful headings/landmarks, image alternatives, and status announcements that do not overwhelm the user.
- Exercise keyboard activation, visible focus, logical navigation, Escape where applicable, and focus restoration. A modal must manage initial focus and contain interaction while open. Native `dialog.showModal()` or the existing accessible dialog primitive supplies modal behavior; an `open` attribute or `aria-modal` alone does not. Nonmodal popovers must not trap focus as if they were dialogs.
- Check text contrast (4.5:1 normal; 3:1 large text), relevant non-text contrast, and non-color state cues. Large text means at least 18pt regular or 14pt bold, not 18px regular. Preserve zoom and user settings. Prefer generous touch hit areas even when the visible icon is small.
- Design errors for recovery: associate field errors, preserve input, explain the failure, and expose the next action. Do not hide critical information in a toast or hover-only tooltip.
- Test 320px, 768px, 1024px, and 1440px as baseline widths, plus the user's actual viewport and relevant intermediate/container widths. Verify long content, zoom, missing assets, slow/failed data, and localization/RTL when supported. Maintain meaningful DOM and focus order after visual reflow.
- Fix overflow at its cause: shrinkable flex/grid children, appropriate wrapping, responsive tracks, and deliberate local scrolling for wide data. Do not globally clip overflow to disguise inaccessible content. Allow control labels to wrap when needed rather than clipping text or shrinking it below legibility. Check sticky headers and overlays for obscured focus, overlap, and clipping.

For motion implementation or review, read `references/motion-design.md`. Motion should explain change or support the chosen expression without delaying input. Preserve existing tokens, verify interruption and reduced motion, and measure expensive effects before claiming performance. Static interfaces are valid.

## Delivery checks

- [ ] The complete requested task works, with relevant content and failure states.
- [ ] Rendered hierarchy, composition, type, and density fit the brief and surrounding product.
- [ ] Responsive and content-stress paths retain readable content and usable controls.
- [ ] Keyboard, focus, labels, contrast, reduced motion, and applicable screen-reader checks pass.
- [ ] Relevant build/tests pass; console, font/image loading, layout shift, and interaction performance were checked at the claimed scope.
- [ ] External sources/assets meet license, dependency, privacy, and authorization boundaries.
- [ ] The final report distinguishes observed checks, inferred aesthetic judgments, and anything untested. No self-score or static source check substitutes for a rendered result or the user's taste approval.
