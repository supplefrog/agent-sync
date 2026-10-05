// Event-sequence mechanism tests; actual browser rendering is checked separately.
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
const source = await readFile(new URL('../assets/selector-focus.js', import.meta.url), 'utf8');
class Select extends EventTarget {
  constructor() { super(); this.dataset = {}; this.disabled = false; }
}
globalThis.HTMLSelectElement = Select;
const owner = new EventTarget();
owner.defaultView = {setTimeout, clearTimeout};
const select = new Select(); select.ownerDocument = owner;
const {bindSelectorFocus} = await import('data:text/javascript;base64,' + Buffer.from(source).toString('base64'));
const dispose = bindSelectorFocus(select);
const send = (type, target = select, key) => {
  const event = new Event(type); Object.defineProperty(event, 'target', {value: target});
  if (key) Object.defineProperty(event, 'key', {value: key});
  owner.dispatchEvent(event);
};
send('pointerdown'); select.dispatchEvent(new Event('focus'));
assert.equal(select.dataset.focusRing, 'pointer', 'Immediate pointer focus');
send('keydown', select, 'ArrowDown');
assert.equal(select.dataset.focusRing, 'keyboard', 'Keyboard after pointer restores ring');
send('mousedown'); select.dispatchEvent(new Event('blur')); select.dispatchEvent(new Event('focus'));
assert.equal(select.dataset.focusRing, 'keyboard', 'Blur/refocus cannot reuse stale pointer');
send('pointerdown'); await new Promise(resolve => setTimeout(resolve, 5));
select.dispatchEvent(new Event('focus'));
assert.equal(select.dataset.focusRing, 'keyboard', 'Later programmatic focus has a ring');
send('pointerdown', new EventTarget()); select.dispatchEvent(new Event('focus'));
assert.equal(select.dataset.focusRing, 'keyboard', 'Programmatic move from another object');
select.disabled = true; send('pointerdown'); select.dispatchEvent(new Event('focus'));
assert.equal(select.dataset.focusRing, 'keyboard', 'Disabled control does not create pointer history');
select.disabled = false; dispose(); send('pointerdown');
assert.equal(select.dataset.focusRing, undefined, 'Cleanup removes listeners and owned marker');
console.log('7 selector event-sequence assertions passed; browser paint not certified.');
