// SPDX-License-Identifier: AGPL-3.0-only
// Coding commitments and receipts use the existing lesson ownership and revision.
import {createHash, randomUUID} from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import {Worker} from 'node:worker_threads';
import {FileSessionStore, StateError, requireState} from './store.mjs';

export const MAX_CODE_BYTES = 8 * 1024;
const MAX_TESTS = 8;
const WORKER_DEADLINE_MS = 4500;
const active = new Set();
const plain = value => value !== null && typeof value === 'object' && !Array.isArray(value)
  && (Object.getPrototypeOf(value) === Object.prototype || Object.getPrototypeOf(value) === null);
const fields = (value, allowed) => plain(value) && Object.keys(value).every(key => allowed.includes(key));
const digest = value => createHash('sha256').update(JSON.stringify(value)).digest('hex');
const boundedText = (value, max) => typeof value === 'string' && Buffer.byteLength(value) <= max;
const validId = value => typeof value === 'string' && /^[A-Za-z0-9_-]{1,100}$/.test(value);
const issue = message => new StateError('coding_runner_failed', message);

function validExpected(value, depth = 0) {
  if (depth > 12) return false;
  if (value === null || typeof value === 'boolean') return true;
  if (typeof value === 'number') return Number.isFinite(value);
  if (typeof value === 'string') return boundedText(value, 1024);
  if (Array.isArray(value)) return value.length <= 80 && Array.from(value).every(item => validExpected(item, depth + 1));
  return plain(value) && Object.keys(value).length <= 80
    && Object.entries(value).every(([key, item]) => boundedText(key, 160) && validExpected(item, depth + 1));
}

export function normalizeCoding(spec) {
  if (spec === undefined) return undefined;
  requireState(fields(spec, ['language','starterCode','tests','solution']) && spec.language === 'javascript'
    && (spec.starterCode === undefined || boundedText(spec.starterCode, MAX_CODE_BYTES)) && boundedText(spec.solution, MAX_CODE_BYTES)
    && spec.solution.trim().length > 0, 'invalid_coding_spec',
  'Coding questions require JavaScript, a committed solution, and bounded starter code.');
  const tests = spec.tests === undefined ? [] : spec.tests;
  requireState(Array.isArray(tests) && tests.length <= MAX_TESTS && Array.from(tests).every(test =>
    fields(test, ['name','expression','expected']) && boundedText(test.name, 100) && test.name.trim().length > 0
    && boundedText(test.expression, 2048) && test.expression.trim().length > 0 && Object.hasOwn(test, 'expected')
    && validExpected(test.expected) && Buffer.byteLength(JSON.stringify(test.expected)) <= 2048),
  'invalid_coding_tests', 'Use at most eight named JavaScript test expressions with bounded JSON expected values.');
  requireState(new Set(tests.map(test => test.name.trim())).size === tests.length,
    'invalid_coding_tests', 'Coding test names must be distinct.');
  return {
    language: 'javascript', starterCode: spec.starterCode ?? '', solution: spec.solution,
    tests: tests.map(({name, expression, expected}) => ({name: name.trim(), expression, expected: JSON.parse(JSON.stringify(expected))})),
  };
}

export function publicCoding(spec) {
  const coding = normalizeCoding(spec);
  if (!coding) return undefined;
  return {language: coding.language, starterCode: coding.starterCode, testNames: coding.tests.map(test => test.name)};
}

export function validateCodingText(code) {
  requireState(boundedText(code, MAX_CODE_BYTES) && code.trim().length > 0,
    'invalid_coding_answer', 'Use nonblank JavaScript code of at most 8 KiB.');
  return code;
}

export async function runCodingTests(spec, code) {
  const coding = normalizeCoding(spec);
  requireState(coding?.tests.length, 'coding_tests_unavailable', 'This question has no runnable tests.');
  validateCodingText(code);
  const worker = new Worker(new URL('./coding-worker.mjs', import.meta.url), {
    workerData: {tests: coding.tests, code},
    argv: [],
    execArgv: [],
    env: {},
    resourceLimits: {maxOldGenerationSizeMb: 48, maxYoungGenerationSizeMb: 8, stackSizeMb: 2},
  });
  let deadline;
  try {
    return await new Promise((resolve, reject) => {
      deadline = setTimeout(() => reject(issue('The JavaScript test runner reached its time limit.')), WORKER_DEADLINE_MS);
      worker.once('message', result => {
        if (!Array.isArray(result) || result.length !== coding.tests.length) {
          reject(issue('The JavaScript test runner could not return an observation.'));
        } else {
          resolve(result);
        }
      });
      worker.once('error', () => reject(issue('The JavaScript test runner could not execute.')));
      worker.once('exit', () => reject(issue('The JavaScript test runner exited before returning observations.')));
    });
  } finally {
    clearTimeout(deadline);
    await worker.terminate();
  }
}

function receiptLocation(binding) {
  // Cross-host owner aliases may share the explicitly enrolled lesson ID and
  // state root. Receipt validation is additionally bound to the authenticated
  // caller's resolved authority namespace.
  const owner = binding?.authorityId ?? binding?.ownerSessionId;
  requireState(binding && validId(binding.chatId) && typeof binding.root === 'string' && path.isAbsolute(binding.root)
    && typeof owner === 'string' && owner.length > 0,
  'invalid_coding_binding', 'Use the existing private lesson enrollment.');
  const root = path.join(binding.root, '.coding-runs');
  try {
    const entry = fs.lstatSync(root);
    requireState(entry.isDirectory() && !entry.isSymbolicLink(), 'invalid_coding_binding', 'The private run directory is invalid.');
  } catch (error) {
    if (error.code !== 'ENOENT') throw error;
  }
  const store = new FileSessionStore(root);
  return {store, id: digest([owner, binding.chatId, binding.kind])};
}

function validateRunTarget(binding, revision, promptId) {
  requireState(Number.isSafeInteger(revision) && revision >= 0 && validId(promptId),
    'invalid_coding_run', 'Coding tests require the current question or problem.');
  const current = new FileSessionStore(binding.root).read(binding.chatId);
  requireState(current.adapter.revision === revision, 'stale_native_revision', 'Refresh the lesson before using a test result.');
}

export async function recordCodingRun(binding, {revision, promptId, spec, code}) {
  const {store, id} = receiptLocation(binding);
  validateRunTarget(binding, revision, promptId);
  const key = path.join(store.root, id);
  requireState(active.size < 2 && !active.has(key), 'coding_busy', 'Wait for the current JavaScript tests to finish.');
  active.add(key);
  try {
    const observations = await runCodingTests(spec, code);
    validateRunTarget(binding, revision, promptId);
    const receipt = {runId: randomUUID(), promptId, revision, codeHash: digest(code), observations};
    store.change(id, prior => ({record: {...(prior ?? {id, version: 1, adapter: {version: 1, revision: -1}, messages: []}), receipt},
      result: undefined}), {create: !fs.existsSync(store.file(id))});
    return {runId: receipt.runId, observations};
  } finally {
    active.delete(key);
  }
}

export function readCodingRun(binding, {revision, promptId, code, runId}) {
  if (runId === undefined) return undefined;
  const {store, id} = receiptLocation(binding);
  validateRunTarget(binding, revision, promptId);
  validateCodingText(code);
  requireState(typeof runId === 'string' && /^[a-f0-9-]{36}$/.test(runId) && fs.existsSync(store.file(id)),
    'stale_coding_run', 'Run tests again for this exact code.');
  const {receipt} = store.read(id);
  requireState(receipt?.runId === runId && receipt.promptId === promptId && receipt.revision === revision && receipt.codeHash === digest(code),
    'stale_coding_run', 'Run tests again for this exact code.');
  return receipt.observations;
}
