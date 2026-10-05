# Selector feedback and indicator placement

Use when a selector must avoid incidental mouse-focus chrome or an authored indicator needs reliable placement. Prefer the project's established accessible primitive. In React Aria, `useFocusRing` supplies input-modality state; a native `:focus-visible` selector alone follows browser heuristics and can still match after mouse activation. Text-entry fields also follow the user's no-incidental-mouse-halo preference: retain focus and the caret for editing, while distinguishing the authored ring from necessary editing feedback. Preserve visible keyboard/programmatic focus. A system picker highlight is distinct from the closed control's authored outline.

For a small native-select implementation without a suitable focus primitive, the optional [selector-focus.js](../assets/selector-focus.js) adapter keeps the actual select and its native keyboard/picker semantics. It marks only the bound select with `data-focus-ring`. Import it into the isolated preview and call `bindSelectorFocus(select)`; retain its returned cleanup function in the component lifecycle. This is a narrow implementation aid, not a new UI framework or compulsory dependency. Inspect compatibility and retest integration in the target stack/browser.

Keep a visible fallback focus rule, then suppress only pointer feedback for this bound non-text control. For example:

```css
.category-select:focus { outline: 2px solid var(--focus-color); outline-offset: 3px; }
.category-select[data-focus-ring="pointer"]:focus { outline: none; }
@media (forced-colors: active) {
  .category-select:focus,
  .category-select[data-focus-ring="pointer"]:focus { outline: 2px solid Highlight; }
}
```

No global `outline: none` or removal of focus on click. This adapter is scoped to non-text selectors; do not bind it to text fields. For a textbox, use the established focus primitive or scoped modality handling and verify mouse editing, keyboard entry, programmatic restoration and mixed input independently; merely hiding `:focus` or trusting `:focus-visible` does not meet the preference safely. The adapter does not implement a dropdown, selected-state styling, contrast tokens or native-popup appearance. User high-contrast colors and visible keyboard focus remain independent requirements.

For an authored chevron, retain the native select, provide enough inline-end padding, and use one noninteractive `aria-hidden` SVG in a positioned wrapper. Anchor its box to the control's center and inspect its actual painted silhouette/insets at relevant widths; a centered viewBox alone does not prove an optically balanced path. In forced colors, either keep a visible system-colored icon or restore native appearance and hide the authored icon. Do not show two indicators. Moving the sidebar/container and morphing its glyph require separate checks.

Exercise pointer selection and cancellation, Tab into/out of the control, keyboard selection, mixed pointer-to-keyboard use, programmatic focus restoration, disabled state, long values, narrow layout and forced colors. Capture the closed control as well as the picker. Observe actual input events when an automation path's modality is uncertain; a scripted activation or `selectOption` does not prove a physical mouse interaction. Inspect pointer feedback and visible keyboard focus independently, then compare visible arrow insets/pivot. Record browser/emulation limits; do not claim native OS popup styling was tested from the closed trigger.

When using this adapter, run `node scripts/test_selector_focus.mjs` with the project's existing Node runtime. These seven event-sequence checks protect pointer, keyboard, restoration, disabled and cleanup behavior; they do not replace the browser and painted-indicator checks above. No new dependency is needed.

Primary references: [React Aria useFocusRing](https://react-spectrum.adobe.com/react-aria/useFocusRing.html), [MDN focus-visible](https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/Selectors/:focus-visible), [shadcn Native Select](https://ui.shadcn.com/docs/components/native-select). These establish available primitives and browser behavior, not acceptance of an arbitrary adapted product.
