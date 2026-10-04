# Design Judgment

Use for a new visual direction, a substantial redesign, or a critique of composition and visual identity. A small repair inside an established interface uses its existing rules instead. This is a vocabulary for making choices, not a theme catalog or a mandatory sequence of user approvals.

## Tune taste without restricting the design language

Anthropic frontend-design, Impeccable, Hallmark, and other reviewed sources supply ideas, not boundaries or proof of better model output. Mix influences when they fit the user's expressed taste. Use other sources or original decisions when they fit better. Resolve conflicts in hierarchy, semantics and behavior rather than rejecting multiple lineages.

Choose the taste dimensions relevant to the work. Possible dimensions include information density and whitespace; type character, scale contrast, and weight; palette temperature, saturation, and color coverage; radii, border weight, and elevation; symmetry, alignment, and rhythm; texture and ornament; imagery and icon treatment; motion energy and pacing; and conventional versus experimental presentation. This list is illustrative, not a required parameter schema, numerical slider system, or set of permanent defaults. A request may introduce a different dimension entirely.

Ground each chosen value in the current brief, approved work, explicit feedback, or a labeled inference. “Less rounded” adjusts geometry; it does not prove a preference for sparse layouts or monochrome. Keep independent dimensions separate, then check their interactions in the render. Preserve working choices when new feedback only changes one axis. When selection is explicitly delegated or existing design authority resolves the choice, make reversible decisions and deliver one considered result. Time pressure alone does not authorize consequential unresolved choices; keep those pending for review rather than implementing them as approved.

The surface's job constrains usability, not taste to a genre: expressive color can coexist with dense task UI, and an editorial type treatment can coexist with familiar controls. Retain accessibility, legibility, task completion, and factual integrity while tuning the visual language. An established project's binding commitments still apply unless changing them is authorized.

## Make the direction concrete

Start from the surface's task and the design authority in `SKILL.md`. Inspect actual content and assets before choosing the page shape. A useful thesis explains what leads, what supports it, and why that relationship belongs to this product. “Clean, modern, premium” describes neither a composition nor a decision.

When multiple concepts are requested, each should offer a different answer to how the product's idea becomes an experience. Look beyond the first viewport: composition, type hierarchy, color and material relationships, representation of the product, and interaction can distinguish alternatives. Differences need to be perceptible, not satisfy a quota of changed properties. Compare the set at the actual viewing sizes before factoring visible sections into shared components; an identical lower-page demo can outweigh different heroes. Shared behavior may have distinct presentations. This exploration does not require unrelated styles inside an approved product or novelty in routine controls. When taste remains uncertain, use `taste-selection.md`; if selection was delegated, choose provisionally within that authorization.

Translate subject cues selectively. A scientific product might benefit from clear notation and comparative data, not a decorative laboratory grid. An arts publication might use the work's own palette and scale, not automatically cream paper and italic serifs. Use cultural and material references to explain relationships, tone, or content—not to turn every app into a physical-object imitation.

Develop the choices together: what leads and how the page unfolds; what the type sounds like; how space groups and gives emphasis; how color, shape and light distinguish objects; and what imagery or movement makes the idea tangible. A typeface, hero illustration or effect chosen in isolation can leave the rest of the page generic. A practical task screen can instead express its identity through useful density, precise feedback and well-related surfaces. Keep feasibility, factual integrity and accessibility in the decision rather than deferring them to polish.

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

Apply `SKILL.md`'s comparison and omission test before committing the page shape. Choose structural devices from the meaning they carry, including action, destination and result for symbols. Do not manufacture a justification after adding habitual chrome. Borders and surfaces can establish grouping or state; proximity, alignment, filled color, overlap and light are also available. Navigation, framing and overlays should support actual use.

For example, two adjacent capture invitations remain one choice even if their wording differs; a capture action beside the note being read can serve a different access context. A panel named “Connections” needs a visible or actionable relation, not generic encouragement to connect things. A visual pause can use space and color without another version of the hero promise. A recurring brand phrase can be an intentional refrain, but calling every caption a refrain does not give it a role. Judge the actual contribution in this composition. Keep demo copy truthful when the visitor changes the content; a fixed example title or explanation must not misdescribe their new result.

For expressive surfaces, concentrate emphasis: a compelling artifact, a distinctive type composition, a useful demonstration, or a meaningful interaction. Supporting regions can be quiet without making the whole page visually timid. A task screen can instead be memorable through accuracy, responsiveness, and consistent details.

For interactive explanations, make the depicted object the place to act when that is the natural affordance: open the shown page, select the shown item, manipulate the shown relationship. Carry its state through the response so the visitor sees what changed and why. Separate selectors or a workspace remain useful for comparison, precision or sustained work; they should not be the only route to an object that visibly invites direct action. Provide keyboard equivalents, visible focus and readable information for people who do not interact. Do not imply working functionality that the demo does not provide.

Connected diagrams need shared geometry. Anchor connectors to the rendered objects or derive both from the same coordinate model; keep them attached through responsive reflow, font loading, movement and selection. Choose connector behavior that communicates the relationship. Independently positioned lines that only approach a node undermine a visual explanation even when they look decorative in source.

Expressive purpose can include curiosity, surprise and authorial voice, not only task efficiency. Preserve a meaningful discovery's setup and payoff rather than replacing it with generic witty copy. Compose for the web's variable dimensions and changing states rather than forcing a fixed canvas onto it; this does not prohibit print influences, split panes or playful effects.

## Tune typography and space

Define the fewest type roles that keep the hierarchy legible. One well-tuned family can serve an entire interface; pairing faces is useful only when their roles are distinct. Preserve approved fonts and existing loading infrastructure. Evaluate alternative fonts by actual glyphs, language coverage, license, available weights, and delivery cost—not by whether they appear on an anti-AI blacklist.

For Latin prose, roughly 45–75 characters per line is a starting range, not a rule for tables, short labels, or every writing system. Tune line-height to face, size, measure, and language. Longer lines generally need more leading; large display type often needs less. Keep dense UI scales predictable; fluid display sizing is an option when the available space calls for it. Use tabular numerals for aligned comparisons when supported.

Test headlines with the real words and realistic expansion. Do not repair an awkward wrap by clipping, illegible tracking, or fixed line breaks that fail at other widths. Inspect optical alignment, fallback metrics, missing weights, font loading, and zoom. A source token or mathematically regular scale is not proof that the rendered type looks balanced.

Spacing expresses relationships: tight within a group, stronger separation between groups, enough room around the focal region. Reuse the project scale and use `gap` where it describes sibling layout. Optical offsets can be exceptions; do not invent a second system for them. Keep page gutters, component padding, and section spacing distinct where their jobs differ.

## Choose palette, surfaces, and assets

Assign roles before colors: base surface, raised surface, primary and secondary text, borders, actions, selection, and statuses. A subdued palette is useful for state-rich tools and long reading. Large color fields or a broader palette can support a campaign or a body of work. Neither is a universal default; the brief and current system win.

When creating a palette, hue-related neutrals can improve coherence, but neutral gray, white, and black remain valid. OKLCH can help author perceptual ramps when supported by the project; it does not replace contrast checks or require converting an existing palette. Inspect light/dark variants independently, preserving semantic meanings and legible focus. Do not prescribe fixed accent coverage or automatic font-weight changes for dark mode.

Make color and material relationships do expressive work as well as identify tokens. Filled surfaces, outlines, overlap, gradients, texture and shadow can suggest weight, translucency, depth or light when they agree with the objects and composition. Choose the combination in context; outlining and shadowing every object is not a substitute for those relationships. Keep legible boundaries and states. Repeated roles inside the same treatment should behave alike; distinct concepts need not inherit that treatment. Native controls and scrollbars remain valid.

Choose the finishing treatment during composition, rather than leaving expressive motion and assets for optional decoration after QA. Compare a product-fitting opportunity with the still/unillustrated treatment: a drawn annotation or underline, a passage highlight, an object responding to manipulation, or an authored image/material can make the idea more tangible. Choose what contributes to this experience; useful delight and character count, without requiring an effect or asset quota. Smooth control feedback alone does not establish that the product's expressive opportunity was considered. Consult `motion-design.md` and its liked options when choosing motion.

Choose assets for the idea they make visible. An authentic screenshot, authored illustration, photograph, diagram or specimen can lead the composition rather than sit beside explanatory copy. With generation authorized, use the native image route when an authored asset materially improves the concept: a meaningful object, scene, cutout or functional surface. Decide its role, scale, crop, surrounding color and interactive layers together, then review the integrated result; unrelated placeholders and generic crops add little. Keep controls and essential text in semantic HTML. Verify source/rights, loading, alternatives and responsive treatment; generated images are not proof of real product behavior or customer results. Follow `personal-design-defaults.md` for authorization and truthful version reporting. If an essential asset is unavailable, adapt the concept or report the dependency.

## Critique the rendered result

Evaluate the design before letting a lint rule decide whether a style is good. In the actual target viewport, ask:

- Is the primary task or message evident at a glance, including when detail is visually de-emphasized?
- Do size, contrast, and position reflect importance rather than give every block equal weight?
- Does this composition use the product's actual content well, or could the brand be swapped without changing anything meaningful?
- Does the visual explanation carry its share of the message, with useful copy and controls rather than repeated captions and slogans?
- Are repeated structures helping recognition? Are breaks in rhythm earned by changes in content?
- For a requested concept set, do full pages convey meaningfully different experiences, including their demonstrations, rather than different skins of one page?
- Do direct interaction and visible state changes support the depicted relationships, with attached geometry and coherent intermediate motion?
- Does the chosen expression survive real content, mobile, zoom, states, and available assets?
- Which single material weakness most limits the experience? Is its cause structure, type, content, behavior, or decoration?

Separate an observed defect from an alternative aesthetic preference. A clean accessibility scan cannot prove hierarchy, and a screenshot cannot prove keyboard behavior or personal taste. Fix named failures in batches, compare the affected views, and stop when the brief and quality checks hold. Self-assigned scores, mandatory novelty, and automatic full-page rewrites are not validation.

Source comparison, version pins, rejected prescriptions, and evaluation limits are in `provenance.md`. These are independently written decision rules informed by the reviewed sources, not their bundled scripts, themes, code, or copied playbooks.
