/** Optional native-select focus adapter. Use the project's established focus primitive first. */
export function bindSelectorFocus(select) {
  if (!(select instanceof HTMLSelectElement)) throw new TypeError('Expected a native select');
  const owner = select.ownerDocument;
  const abort = new AbortController();
  const options = {capture: true, signal: abort.signal};
  const view = owner.defaultView;
  let pointerTarget = null;
  let pendingClear;
  let mode = 'keyboard';
  const update = () => { select.dataset.focusRing = mode; };
  const pointer = event => {
    view.clearTimeout(pendingClear);
    pointerTarget = event.target === select && !select.disabled ? select : null;
    if (pointerTarget) { mode = 'pointer'; update(); }
    // Native focus follows the pointer event. Do not reuse an old event for a later restore.
    pendingClear = view.setTimeout(() => { pointerTarget = null; }, 0);
  };
  const keyboard = event => {
    if (['Shift', 'Control', 'Alt', 'Meta'].includes(event.key)) return;
    pointerTarget = null;
    mode = 'keyboard';
    update();
  };
  const focus = () => {
    // A programmatic move from a different object must remain visibly focused.
    mode = pointerTarget === select ? 'pointer' : 'keyboard';
    update();
    pointerTarget = null;
  };
  owner.addEventListener('pointerdown', pointer, options);
  owner.addEventListener('mousedown', pointer, options);
  owner.addEventListener('keydown', keyboard, options);
  select.addEventListener('focus', focus, {signal: abort.signal});
  select.addEventListener('blur', () => { pointerTarget = null; }, {signal: abort.signal});
  update();
  return () => { abort.abort(); view.clearTimeout(pendingClear); delete select.dataset.focusRing; };
}
