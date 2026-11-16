// SPDX-License-Identifier: AGPL-3.0-only
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import path from 'node:path';
import test from 'node:test';
import {mountCodingEditor} from '../src/inline/coding-client.mjs';

const require = createRequire(process.env.LH_TEST_TOOLCHAIN
  ? path.join(path.resolve(process.env.LH_TEST_TOOLCHAIN), 'package.json') : import.meta.url);
const {JSDOM} = require('jsdom');

test('coding editor keeps markup inert, runs only on click and rejects results after a mid-run edit', async t => {
  const dom = new JSDOM('<main></main>');
  t.after(() => dom.window.close());
  const root = dom.window.document.querySelector('main');
  const starterCode = 'const text = "<img src=x onerror=alert(1)>";\n';
  const events = [];
  let finish;
  mountCodingEditor(root, {
    spec: {language: 'javascript', starterCode, testNames: ['Example']},
    onChange: value => events.push(['changed', value]),
    onReceipt: value => events.push(['receipt', value]),
    onRun: value => {
      events.push(['run', value]);
      return new Promise(resolve => { finish = resolve; });
    },
  });
  const editor = root.querySelector('textarea');
  const run = root.querySelector('[data-code-run]');
  assert.equal(editor.value, starterCode);
  assert.equal(root.querySelector('img'), null);
  assert.ok(root.querySelector('.lh-code-colors span'));
  assert.deepEqual(events, []);
  run.click();
  assert.deepEqual(events.find(event => event[0] === 'run'), ['run', starterCode]);
  const changedCode = starterCode + 'const changed = 1;\n';
  editor.value = changedCode;
  editor.dispatchEvent(new dom.window.Event('input', {bubbles: true}));
  const receipt = {runId: 'sample-receipt', observations: [{name: 'Example', status: 'pass'}]};
  finish(receipt);
  await Promise.resolve();
  assert.equal(root.querySelector('[data-code-observations]').childElementCount, 0);
  assert.deepEqual(events.find(event => event[0] === 'changed'), ['changed', changedCode]);
  assert.equal(events.some(event => event[1] === receipt), false);
  run.click();
  finish(receipt);
  await Promise.resolve();
  assert.match(root.querySelector('[data-code-observations]').textContent, /Example — Passed/);
  assert.ok(events.some(event => event[1] === receipt));
});
