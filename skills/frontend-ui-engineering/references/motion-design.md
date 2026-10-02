# Motion Design and Review

Use when implementing, reviewing, or auditing UI motion. Preserve the project's motion tokens and accessible component primitives. No additional library is required for a simple transition.

## Decide before implementing

1. Translate the request into each affected target, trigger, direction, and state before choosing effects. Preserve requested motion character and coverage; animating one target or substituting a different effect does not fulfill a multi-target request. Name the purpose: feedback, state change, spatial continuity, expression, or explanation. Remove decoration that distracts from reading or acting on data.
2. Consider repetition and input method. Frequently repeated navigation and command actions should be instant or nearly imperceptible; never delay input, focus, or availability until an animation finishes. Keyboard input alone is not a reason to remove useful state feedback.
3. Choose the smallest mechanism: CSS transitions for state changes, `@starting-style` for supported entry transitions, CSS keyframes for predetermined sequences, WAAPI for programmatic playback, or the existing motion library for gestures and coordinated springs. Check target-browser support and exit/unmount behavior; entry styling alone does not implement an exit lifecycle.
4. Define interruption, entry, exit, reduced-motion behavior, and verification before tuning the curve. Treat entrance and exit as independent lifecycles with their own timing and state visibility; verify each requested direction rather than assuming a reversed entrance implements the requested exit.

## Tune without imposing a new style

- Reuse existing duration and easing tokens. As starting ranges, small feedback often needs roughly 100–200 ms and menus roughly 150–250 ms; larger surfaces may need longer. Judge actual distance, purpose, repetition, and device—not a universal duration ceiling.
- Prefer an immediate response with deceleration for entrances; smooth acceleration/deceleration can suit movement between established positions. Linear timing suits constant-rate progress. Custom curves and springs are options, not quality requirements.
- For trigger-anchored popovers, match transform origin to the trigger and actual placement; keep unanchored dialogs centered. A slight scale plus opacity may help continuity, but a pure fade or instant change is valid. Do not mandate scale on every button.
- Specify transition properties instead of `transition: all`. Prefer transform and opacity where they preserve the required layout and text clarity. Do not substitute a scaled, distorted accordion for necessary layout change merely to avoid animating height.
- Rapid toggles, toast changes, and gestures must retarget from the current visual state rather than jump to an initial keyframe. Transitions or velocity-preserving springs often fit; deliberately controlled WAAPI/keyframe playback can also work. Test cancellation and reversal, not just the first successful playback.
- Use stagger only when it clarifies grouping; never postpone interaction or apply a long cascade to routine results. Subsequent tooltips in a group can skip the initial delay, using the existing primitive's supported behavior.

## Accessibility and performance boundaries

- Honor `prefers-reduced-motion` by removing, reducing, or replacing nonessential motion. Instant state changes are valid; retain a short fade only when helpful and comfortable. Keep focus, announcements, and functionality equivalent. Include animated pseudo-elements such as `::backdrop` when relevant. When reduced-motion preference changes or printing begins, verify that in-flight CSS/WAAPI motion stops or reaches a usable static state; a zero-duration rule or empty animation list alone does not establish this.
- Gate decorative hover motion to hover-capable pointers without removing keyboard focus feedback. Test touch cancellation and pointer capture cleanup for drags; additional fingers must not jump the active gesture. Prefer the component library's gesture handling over a universal velocity threshold.
- Hardware acceleration depends on properties, browser, animation mechanism, and scene—not merely the presence of CSS or WAAPI. Profile under realistic main-thread load before rewriting Motion shorthand values or claiming a speedup. Layout and paint animations require measurement; blanket GPU guarantees are not evidence.
- Avoid inherited CSS-variable updates across large subtrees on every animation frame when a local style update suffices. Apply `will-change` selectively and remove temporary hints. Blur is not a default repair for a confusing state transition.
- If a trace implicates broad inherited color animation, investigate offscreen style work as well as visible paint. Containment is a candidate, not a drop-in fix: verify margin collapse, section/anchor geometry, resize/font changes, scrolling, focus, find-in-page and print. Keep only measured changes that preserve the required appearance and behavior; a diagnostic removal of approved motion is not a shipping fix.

## Verify and report

Exercise every requested target and state in normal playback, both directions where applicable, rapid reversal, repeated activation, exit/unmount, keyboard, touch where relevant, and reduced motion in a real browser with representative content. Verify visible intermediate behavior and content lifetime, not just final styles or source presence. Inspect slowed playback for jumps and origin errors, then judge responsiveness at normal speed. Deliver a playable recording or interactive preview under the skill's checks and visual review before commit. User approval of the look is not performance evidence.

When layout motion overlaps navigation, verify the destination after both settle: a collapsing disclosure can move an already-measured anchor. Coordinate or settle that layout before measuring the destination, while preserving ordinary disclosure motion. Test intentionally instant neighboring disclosures and closed-content printing when changing shared selectors. Measure intermediate geometry, visibility and actual content lifetime; browser-owned pseudo-element motion may not appear in `getAnimations()`, so an empty animation list is not proof of no motion. Keep intermediate samples separate from settled-state comparisons.

For performance findings, profile the active transition window, not an idle-padded average or just the longer decorative tail. Compare repeated baselines and the candidate under the same content, viewport and environment; pair traces with an untraced timestamp-only rAF control so the sampler does not force layout reads. Callback cadence, compositor draws and presentation feedback are distinct signals, not proof of physically displayed FPS. Report the measured signal and window, browser/device scope and headless or physical-device limits.

For a codebase audit, inventory actual motion with file/line evidence. Prioritize shared primitives and user-visible frequency, not raw occurrence counts. Each finding needs an observed defect or labeled risk, the smallest fix, and a concrete acceptance check. Record useful no-motion cases so the audit does not become a mandate to add animation everywhere. Review scope does not authorize implementation.

## Technical references

- [Motion performance](https://motion.dev/docs/performance): rendering cost, acceleration caveats, and layout exceptions.
- [MDN reduced motion](https://developer.mozilla.org/en-US/docs/Web/CSS/@media/prefers-reduced-motion): remove, reduce, or replace motion.
- [MDN starting styles](https://developer.mozilla.org/en-US/docs/Web/CSS/@starting-style): entry transition semantics and compatibility.

Source selection and rejected prescriptions are recorded in `provenance.md`.
