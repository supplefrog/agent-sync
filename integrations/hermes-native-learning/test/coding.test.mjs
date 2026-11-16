// SPDX-License-Identifier: AGPL-3.0-only
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import {FileSessionStore} from '../src/store.mjs';
import {normalizeCoding, publicCoding, recordCodingRun, readCodingRun, runCodingTests} from '../src/coding.mjs';

const spec = {
  language: 'javascript',
  starterCode: 'function twice(n) {\n  // Write your answer here.\n}\n',
  solution: 'function twice(n) { return n * 2; }',
  tests: [{name: 'Doubles a positive number', expression: 'twice(4)', expected: 8},
    {name: 'Doubles a negative number', expression: 'twice(-2)', expected: -4}],
};

function fixture(t) {
  const dir = fs.realpathSync(os.tmpdir());
  const root = fs.mkdtempSync(path.join(dir, 'lh-coding-'));
  t.after(() => {
    assert.equal(path.dirname(fs.realpathSync(root)), dir);
    fs.rmSync(root, {recursive: true, force: true});
  });
  const binding = {root, chatId: 'disposable-coding', kind: 'teach', ownerSessionId: 'fixture-owner'};
  const store = new FileSessionStore(root);
  store.change(binding.chatId, () => ({
    record: {id: binding.chatId, version: 1, adapter: {version: 1, revision: -1}, messages: []},
    result: undefined,
  }), {create: true});
  return {binding, store};
}

test('pending coding projection excludes the solution, test expressions and expected values', () => {
  assert.deepEqual(publicCoding(spec), {language: 'javascript', starterCode: spec.starterCode,
    testNames: ['Doubles a positive number', 'Doubles a negative number']});
  assert.equal(publicCoding(undefined), undefined);
  assert.deepEqual(normalizeCoding({language: 'javascript', solution: '42'}).tests, []);
  for (const invalid of [null, {language: 'python'}, {...spec, shell: 'cmd.exe'},
    {...spec, tests: [{name: 'shell', expected: 1, command: 'cat'}]},
    {...spec, tests: [{name: 'non JSON', expression: 'Infinity', expected: Infinity}]},
    {...spec, tests: Array(1)}])
    assert.throws(() => publicCoding(invalid), {name: 'StateError'});
});

test('QuickJS executes real expressions and distinguishes wrong answers, invalid code and test failure', async () => {
  const results = await runCodingTests(spec, 'const twice = n => n > 0 ? n * 2 : n;');
  assert.deepEqual(results, [{name: 'Doubles a positive number', status: 'pass'},
    {name: 'Doubles a negative number', status: 'fail', actual: '-2'}]);
  const broken = await runCodingTests({...spec, tests: [spec.tests[0]]}, 'function twice(');
  assert.equal(broken[0].status, 'error');
  const suspended = await runCodingTests({
    ...spec, tests: [{name: 'Does not accept Promise as object', expression: 'twice(4)', expected: {}}],
  }, 'async function twice(n) { return n * 2; }');
  assert.equal(suspended[0].status, 'error');
});

test('teacher and learner code lack host process capability, and looping code is interrupted', async () => {
  const isolated = await runCodingTests({...spec, tests: [
    {name: 'No host capabilities', expression: 'check()', expected: Array(6).fill('undefined')},
  ]}, `const check = () => [typeof process, typeof require, typeof fetch, typeof std, typeof os,
    globalThis.constructor.constructor('return typeof process')()];`);
  assert.equal(isolated[0].status, 'pass');
  const looping = await runCodingTests({...spec, tests: [spec.tests[0]]}, 'while (true) {}');
  assert.equal(looping[0].status, 'timeout');
});

test('receipt survives reopen, stays separate from lesson state, and rejects changed code, prompt, owner or revision', async t => {
  const {binding, store} = fixture(t);
  const input = {revision: 0, promptId: 'current-prompt', spec, code: 'function twice(n) { return n * 2; }\n'};
  const baseline = fs.readFileSync(store.file(binding.chatId));
  const saved = await recordCodingRun(binding, input);
  const lookup = {revision: input.revision, promptId: input.promptId, code: input.code, runId: saved.runId};
  assert.deepEqual(readCodingRun({...binding}, lookup), saved.observations);
  assert.deepEqual(saved.observations.map(value => value.status), ['pass','pass']);
  assert.deepEqual(fs.readFileSync(store.file(binding.chatId)), baseline);
  assert.throws(() => readCodingRun(binding, {...lookup, code: input.code.trimEnd()}), {code: 'stale_coding_run'});
  assert.throws(() => readCodingRun(binding, {...lookup, promptId: 'another-prompt'}), {code: 'stale_coding_run'});
  assert.throws(() => readCodingRun({...binding, ownerSessionId: 'other'}, lookup), {code: 'stale_coding_run'});
  store.change(binding.chatId, record => ({record, result: undefined}));
  await assert.rejects(recordCodingRun(binding, input), {code: 'stale_native_revision'});
  assert.throws(() => readCodingRun(binding, lookup), {code: 'stale_native_revision'});
});
