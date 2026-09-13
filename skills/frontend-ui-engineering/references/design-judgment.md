# Design Judgment

Use for a new visual direction, a substantial redesign, or a critique of composition and visual identity. A small repair inside an established interface uses its existing rules instead. This is a vocabulary for making choices, not a theme catalog or a mandatory sequence of user approvals.

## Tune taste without restricting the design language

Anthropic frontend-design, Impeccable, Hallmark, and the other reviewed sources supply ideas and evidence, not the boundaries of the result. Mix influences when they help express the engineer's taste; use other sources or original decisions when they fit better. Resolve conflicts in hierarchy, semantics, and component behavior rather than rejecting a combination merely because it has multiple lineages.

Choose the taste dimensions relevant to the work. Possible dimensions include information density and whitespace; type character, scale contrast, and weight; palette temperature, saturation, and color coverage; radii, border weight, and elevation; symmetry, alignment, and rhythm; texture and ornament; imagery and icon treatment; motion energy and pacing; and conventional versus experimental presentation. This list is illustrative, not a required parameter schema, numerical slider system, or set of permanent defaults. A request may introduce a different dimension entirely.

Ground each chosen value in the current brief, approved work, explicit feedback, or a labeled inference. “Less rounded” adjusts geometry; it does not prove a preference for sparse layouts or monochrome. Keep independent dimensions separate, then check their interactions in the render. Preserve working choices when new feedback only changes one axis. With no time for comparisons, make these decisions yourself, keep them reversible, and deliver one considered result rather than handing the tuning task back to the user.

The surface's job constrains usability, not taste to a genre: expressive color can coexist with dense task UI, and an editorial type treatment can coexist with familiar controls. Retain accessibility, legibility, task completion, and factual integrity while tuning the visual language. An established project's binding commitments still apply unless changing them is authorized.

## Make the direction concrete

Start from the surface's task and the design authority in `SKILL.md`. Inspect actual content and assets before choosing the page shape. A useful thesis explains what leads, what supports it, and why that relationship belongs to this product. “Clean, modern, premium” describes neither a composition nor a decision.

For an open brief, compare a few genuinely different structures internally rather than producing color variants of one template. Choose by task clarity, content fit, continuity with the product, feasible assets, accessibility, and implementation cost. Familiar patterns can win on those grounds; novelty is not a separate requirement. Only show alternatives when requested or when a consequential unresolved choice needs the user.

Translate subject cues selectively. A scientific product might benefit from clear notation and comparative data, not a decorative laboratory grid. An arts publication might use the work's own palette and scale, not automatically cream paper and italic serifs. Use cultural and material references to explain relationships, tone, or content—not to turn every app into a physical-object imitation.

Resolve these decisions before detailed styling:

- **Structure:** reading/task order, first viewport, focal region, navigation, and the page's ending.
- **Type:** role hierarchy, family/weight choice, prose measure, data treatment, and loading constraints.
- **Space:** density, alignment, related-item grouping, section rhythm, and responsive transformations.
- **Color and geometry:** semantic roles, surface/elevation relationships, control shapes, and brand expression.
- **Assets and motion:** which genuine artifact demonstrates the subject; whether movement clarifies something.

Keep this in the task's working context for bounded work. Do not automatically create token exports, preference logs, screenshots-as-design-systems, or a new `DESIGN.md` for every component.

## Compose from relationships

Choose a page shape before component decoration. These are alternatives to consider, not required templates:

| Content relationship | Possible structure | What must remain clear |
|---|---|---|
| Repeated comparable records or products | Table, list, catalog, or uniform gallery | Comparison fields, ordering, filtering, and item actions |
| One task with supporting context | Workspace with primary region and supporting panel | Current state, next action, and what changes on narrow screens |
| Explanation or argument | Document with headings, examples, and optional sidenotes | Reading order, measure, anchors, and conclusion |
| Work or physical object as evidence | Image-led composition with captions and contextual copy | The artifact, truthful description, and navigable next step |
| Mechanism or workflow to demonstrate | Annotated example, live demo, or sequential walkthrough | Cause/effect and the user's role; no invented proof |
| Choice between offerings | Comparison or decision-oriented layout | Real differences, conditions, pricing if supplied, and action |

Vary section density and scale when the content changes importance. Repetition supports recognition when items have the same role. Asymmetry, full-bleed media, overlap, or a grid break can create focus, but none is inherently better than a balanced grid. Keep visual and semantic order aligned across sizes.

Let structural devices carry information. Numbering should indicate an actual sequence or reference system. An eyebrow can clarify category or context; remove it when it merely repeats the heading. Borders and surfaces should establish grouping or state; try proximity and alignment before nesting containers. Use a modal when interruption or contained focus is justified, not because a new form needs somewhere to go.

For expressive surfaces, concentrate emphasis: a compelling artifact, a distinctive type composition, a useful demonstration, or a meaningful interaction. Supporting regions can be quiet without making the whole page visually timid. A task screen can instead be memorable through accuracy, responsiveness, and consistent details.

## Tune typography and space

Define the fewest type roles that keep the hierarchy legible. One well-tuned family can serve an entire interface; pairing faces is useful only when their roles are distinct. Preserve approved fonts and existing loading infrastructure. Evaluate alternative fonts by actual glyphs, language coverage, license, available weights, and delivery cost—not by whether they appear on an anti-AI blacklist.

For Latin prose, roughly 45–75 characters per line is a starting range, not a rule for tables, short labels, or every writing system. Tune line-height to face, size, measure, and language. Longer lines generally need more leading; large display type often needs less. Keep dense UI scales predictable; fluid display sizing is an option when the available space calls for it. Use tabular numerals for aligned comparisons when supported.

Test headlines with the real words and realistic expansion. Do not repair an awkward wrap by clipping, illegible tracking, or fixed line breaks that fail at other widths. Inspect optical alignment, fallback metrics, missing weights, font loading, and zoom. A source token or mathematically regular scale is not proof that the rendered type looks balanced.

Spacing expresses relationships: tight within a group, stronger separation between groups, enough room around the focal region. Reuse the project scale and use `gap` where it describes sibling layout. Optical offsets can be exceptions; do not invent a second system for them. Keep page gutters, component padding, and section spacing distinct where their jobs differ.

## Choose palette, surfaces, and assets

Assign roles before colors: base surface, raised surface, primary and secondary text, borders, actions, selection, and statuses. A subdued palette is useful for state-rich tools and long reading. Large color fields or a broader palette can support a campaign or a body of work. Neither is a universal default; the brief and current system win.

When creating a palette, hue-related neutrals can improve coherence, but neutral gray, white, and black remain valid. OKLCH can help author perceptual ramps when supported by the project; it does not replace contrast checks or require converting an existing palette. Inspect light/dark variants independently, preserving semantic meanings and legible focus. Do not prescribe fixed accent coverage or automatic font-weight changes for dark mode.

Use scale, spacing, and surface contrast before adding elevation effects. Choose borders, radii, and shadows as a coherent component language; repeated roles should behave alike. Native controls and scrollbars are valid, not unfinished solely because the browser supplies them.

An authentic screenshot, photograph, diagram, or specimen should reveal something relevant. Verify its source, rights, loading, aspect ratio, crop, alternatives, and mobile treatment. Device/browser framing can explain context but should not become inaccurate decorative chrome. Do not invent proof badges, charts, or testimonials to fill a layout. If a necessary asset is unavailable, adapt the composition or state the dependency; do not silently replace it with unrelated gradients or expensive generation.

## Critique the rendered result

Evaluate the design before letting a lint rule decide whether a style is good. In the actual target viewport, ask:

- Is the primary task or message evident at a glance, including when detail is visually de-emphasized?
- Do size, contrast, and position reflect importance rather than give every block equal weight?
- Does this composition use the product's actual content well, or could the brand be swapped without changing anything meaningful?
- Are repeated structures helping recognition? Are breaks in rhythm earned by changes in content?
- Does the chosen expression survive real content, mobile, zoom, states, and available assets?
- Which single material weakness most limits the experience? Is its cause structure, type, content, behavior, or decoration?

Separate an observed defect from an alternative aesthetic preference. A clean accessibility scan cannot prove hierarchy, and a screenshot cannot prove keyboard behavior or personal taste. Fix named failures in batches, compare the affected views, and stop when the brief and quality checks hold. Self-assigned scores, mandatory novelty, and automatic full-page rewrites are not validation.

Source comparison, version pins, rejected prescriptions, and evaluation limits are in `provenance.md`. These are independently written decision rules informed by the reviewed sources, not their bundled scripts, themes, code, or copied playbooks.
