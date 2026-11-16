// SPDX-License-Identifier: AGPL-3.0-only
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { createRequire } from 'node:module';
import test from 'node:test';
import { executeFlashcards } from '../src/flashcards.mjs';
import { mountFlashcards } from '../src/inline/flashcards-client.mjs';
import { FileSessionStore } from '../src/store.mjs';

const require = createRequire(process.env.LH_TEST_TOOLCHAIN
  ? path.join(path.resolve(process.env.LH_TEST_TOOLCHAIN), 'package.json') : import.meta.url);
const { JSDOM } = require('jsdom');
const turn = () => new Promise(resolve => setTimeout(resolve, 0));

test('the learner widget creates, reveals and rates a real saved card, then practices without grading', async t => {
  const temp = fs.realpathSync(os.tmpdir()), base = fs.mkdtempSync(path.join(temp, 'lh-flashcards-dom-'));
  const dom = new JSDOM('<!DOCTYPE html><main></main>');
  t.after(() => {
    dom.window.close();
    assert.equal(path.dirname(base), temp);
    fs.rmSync(base, { recursive: true, force: true });
  });
  const root = dom.window.document.querySelector('main');
  const binding = { root: base, chatId: 'lesson', ownerSessionId: 'learner' };
  const store = new FileSessionStore(base);
  store.change(binding.chatId, () => ({ record: {
    id: binding.chatId, version: 1, adapter: { version: 1, revision: 0 }, messages: [],
  } }), { create: true });
  const command = input => executeFlashcards(binding, { op: 'flashcards', chatId: binding.chatId, ...input },
    { origin: 'app', now: Date.UTC(2026, 10, 15, 12) });
  const reveals = [];
  let lostReceipt = true;
  const request = async input => {
    const result = command(input);
    if (input.action === 'reveal') reveals.push(result.back);
    if (input.action === 'rate' && lostReceipt) {
      lostReceipt = false;
      throw new Error('Delivery failed. Try again.');
    }
    return result;
  };
  const byText = matcher => [...root.querySelectorAll('button')].find(button => matcher.test(button.textContent));
  const submit = form => form.dispatchEvent(new dom.window.Event('submit', { bubbles: true, cancelable: true }));
  const open = () => { root.querySelector('details').open = true; };
  let widget = mountFlashcards(root, { request });
  open();
  await turn();
  assert.match(root.textContent, /Create a deck/);
  root.querySelector('input').value = 'Conservation';
  submit(root.querySelectorAll('form')[1]);
  await turn();
  assert.equal(root.querySelector('select option').textContent, 'Conservation');
  const [front, back] = root.querySelectorAll('textarea');
  front.value = 'What remains constant?';
  back.value = 'Net electric charge.';
  submit(root.querySelectorAll('form')[0]);
  await turn();
  assert.equal(byText(/Review due/).textContent, 'Review due (1)');
  byText(/Review due/).click();
  await turn();
  assert.match(root.querySelector('section').textContent, /What remains constant/);
  assert.doesNotMatch(root.querySelector('section').textContent, /Net electric charge/);
  assert.equal(reveals.length, 0);
  assert.equal(dom.window.document.activeElement.textContent, 'Show answer');
  byText(/Show answer/).click();
  await turn();
  assert.match(root.querySelector('section').textContent, /Net electric charge/);
  byText(/^Good$/).click();
  await turn();
  assert.match(root.querySelector('[role=alert]').textContent, /Delivery failed/);
  byText(/^Good$/).click();
  await turn();
  assert.equal(byText(/Review due/).disabled, true);
  assert.match(root.textContent, /Next review/);
  const afterGrade = command({ action: 'decks' });
  widget.destroy();
  widget = mountFlashcards(root, { request });
  open();
  await turn();
  assert.equal(byText(/Review due/).disabled, true);
  byText(/Extra practice/).click();
  await turn();
  byText(/Show answer/).click();
  await turn();
  assert.equal(byText(/^Good$/), undefined);
  assert.ok(byText(/Next card/));
  assert.deepEqual(command({ action: 'decks' }), afterGrade);
  widget.destroy();
  assert.equal(root.childElementCount, 0);
});
