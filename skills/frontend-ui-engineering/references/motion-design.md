# Motion Design and Review

Use when implementing, reviewing, or auditing UI motion. Preserve the project's motion tokens and accessible component primitives. No additional library is required for a simple transition.

## Decide before implementing

1. Name the purpose: feedback, state change, spatial continuity, or explanation. Remove decoration that distracts from reading or acting on data.
2. Consider repetition and input method. Frequently repeated navigation and command actions should be instant or nearly imperceptible; never delay input, focus, or availability until an animation finishes. Keyboard input alone is not a reason to remove useful state feedback.
3. Choose the smallest mechanism: CSS transitions for state changes, `@starting-style` for supported entry transitions, CSS keyframes for predetermined sequences, WAAPI for programmatic playback, or the existing motion library for gestures and coordinated springs. Check target-browser support and exit/unmount behavior; entry styling alone does not implement an exit lifecycle.
4. Define interruption, exit, reduced-motion behavior, and verification before tuning the curve.

## Tune without imposing a new style

- Reuse existing duration and easing tokens. As starting ranges, small feedback often needs roughly 100–200 ms and menus roughly 150–250 ms; larger surfaces may need longer. Judge actual distance, purpose, repetition, and device—not a universal duration ceiling.
- Prefer an immediate response with deceleration for entrances; smooth acceleration/deceleration can suit movement between established positions. Linear timing suits constant-rate progress. Custom curves and springs are options, not quality requirements.
- For trigger-anchored popovers, match transform origin to the trigger and actual placement; keep unanchored dialogs centered. A slight scale plus opacity may help continuity, but a pure fade or instant change is valid. Do not mandate scale on every button.
- Specify transition properties instead of `transition: all`. Prefer transform and opacity where they preserve the required layout and text clarity. Do not substitute a scaled, distorted accordion for necessary layout change merely to avoid animating height.
- Rapid toggles, toast changes, and gestures must retarget from the current visual state rather than jump to an initial keyframe. Transitions or velocity-preserving springs often fit; deliberately controlled WAAPI/keyframe playback can also work. Test cancellation and reversal, not just the first successful playback.
- Use stagger only when it clarifies grouping; never postpone interaction or apply a long cascade to routine results. Subsequent tooltips in a group can skip the initial delay, using the existing primitive's supported behavior.

## Accessibility and performance boundaries

- Honor `prefers-reduced-motion` by removing, reducing, or replacing nonessential motion. Instant state changes are valid; retain a short fade only when helpful and comfortable. Keep focus, announcements, and functionality equivalent.
- Gate decorative hover motion to hover-capable pointers without removing keyboard focus feedback. Test touch cancellation and pointer capture cleanup for drags; additional fingers must not jump the active gesture. Prefer the component library's gesture handling over a universal velocity threshold.
- Hardware acceleration depends on properties, browser, animation mechanism, and scene—not merely the presence of CSS or WAAPI. Profile under realistic main-thread load before rewriting Motion shorthand values or claiming a speedup. Layout and paint animations require measurement; blanket GPU guarantees are not evidence.
- Avoid inherited CSS-variable updates across large subtrees on every animation frame when a local style update suffices. Apply `will-change` selectively and remove temporary hints. Blur is not a default repair for a confusing state transition.

## Verify and report

Exercise normal playback, rapid reversal, repeated activation, exit/unmount, keyboard, touch where relevant, and reduced motion in a real browser. Inspect slowed playback for jumps and origin errors, then judge responsiveness at normal speed. Use a performance trace for performance findings; disclose when physical-device gesture testing is unavailable.

For a codebase audit, inventory actual motion with file/line evidence. Prioritize shared primitives and user-visible frequency, not raw occurrence counts. Each finding needs an observed defect or labeled risk, the smallest fix, and a concrete acceptance check. Record useful no-motion cases so the audit does not become a mandate to add animation everywhere. Review scope does not authorize implementation.

## Technical references

- [Motion performance](https://motion.dev/docs/performance): rendering cost, acceleration caveats, and layout exceptions.
- [MDN reduced motion](https://developer.mozilla.org/en-US/docs/Web/CSS/@media/prefers-reduced-motion): remove, reduce, or replace motion.
- [MDN starting styles](https://developer.mozilla.org/en-US/docs/Web/CSS/@starting-style): entry transition semantics and compatibility.

Source selection and rejected prescriptions are recorded in `provenance.md`.
