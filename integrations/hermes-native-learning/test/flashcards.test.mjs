// SPDX-License-Identifier: AGPL-3.0-only
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import { executeFlashcards } from '../src/flashcards.mjs';
import { FileSessionStore } from '../src/store.mjs';
import { materialCommand } from '../src/materials.mjs';

const start = Date.UTC(2026, 10, 15, 12);
function fixture(t) {
  const absoluteTemp = fs.realpathSync(os.tmpdir());
  const base = fs.mkdtempSync(path.join(absoluteTemp, 'lh-flashcards-'));
  t.after(() => {
    assert.equal(path.dirname(base), absoluteTemp);
    fs.rmSync(base, { recursive: true, force: true });
  });
  const binding = {
    root: path.join(base, 'state'), output: path.join(base, 'exports'),
    chatId: 'lesson', ownerSessionId: 'unique-owner',
    graphRoot: path.join(base, 'graph'), materials: [
      { id: 'notes', label: 'Course notes', kind: 'notes', file: path.join(base, 'notes.txt') },
    ],
  };
  fs.mkdirSync(binding.graphRoot);
  fs.writeFileSync(path.join(binding.graphRoot, 'nodes.jsonl'), JSON.stringify({
    id: 'electric-charge', name: 'Conservation of charge',
    statement: 'Net electric charge is constant in an isolated system.',
    createdAt: '2026-11-14', aliases: [], provenance: [],
  }) + '\n');
  fs.writeFileSync(binding.materials[0].file, 'A circuit needs a closed path.');
  const lesson = new FileSessionStore(binding.root);
  lesson.change(binding.chatId, () => ({ record: {
    id: binding.chatId, version: 1, adapter: { version: 1, revision: 0 }, messages: [],
  } }), { create: true });
  const call = (action, args = {}, now = start, origin = 'app', scope = binding) =>
    executeFlashcards(scope, { op: 'flashcards', chatId: binding.chatId, action, ...args }, { origin, now });
  const deck = title => call('create-deck', { title }).deck.id;
  const add = (deckId, front, back) => call('add', { deckId, front, back }).card.id;
  return { binding, lesson, call, deck, add };
}

test('FSRS review survives reopen and cannot be graded twice or before reveal', t => {
  const { call, deck, add, lesson } = fixture(t);
  const initialLesson = lesson.read('lesson');
  const deckId = deck('Electric circuits');
  const cardId = add(deckId, 'What is needed?', 'A closed path.');
  const next = call('next', { deckId, mode: 'due' });
  assert.equal(next.card.id, cardId);
  assert.equal(next.card.front, 'What is needed?');
  assert.equal(next.card.back, undefined);
  assert.throws(() => call('rate', { token: next.card.token, rating: 3 }), { code: 'invalid_flashcard_token' });
  assert.throws(() => call('reveal', { token: next.card.token + 'x' }), { code: 'invalid_flashcard_token' });

  const shown = call('reveal', { token: next.card.token });
  assert.equal(shown.back, 'A closed path.');
  const request = { token: shown.token, rating: 3 };
  const result = call('rate', request);
  assert.equal(result.due, start + 10 * 60 * 1000);
  assert.equal(result.reps, 1);

  const replay = call('rate', request, start + 1000);
  assert.equal(replay.reps, 1);
  assert.equal(replay.due, result.due);
  assert.equal(replay.replayed, true);
  assert.throws(() => call('rate', { ...request, rating: 1 }), { code: 'stale_flashcard' });
  assert.equal(call('next', { deckId, mode: 'due' }, result.due - 1).card, null);

  const due = call('next', { deckId, mode: 'due' }, result.due);
  assert.equal(due.card.id, cardId);
  assert.deepEqual(lesson.read('lesson'), initialLesson);
});

test('extra practice rotates cards without changing their due dates or exposure at next', t => {
  const { call, deck, add } = fixture(t);
  const deckId = deck('Recall');
  add(deckId, 'A', 'Answer A');
  add(deckId, 'B', 'Answer B');
  const original = call('decks');
  const first = call('next', { deckId, mode: 'practice' }).card;
  const shown = call('reveal', { token: first.token });
  assert.match(shown.back, /^Answer [AB]$/);
  assert.equal(shown.token, undefined);
  const second = call('next', { deckId, mode: 'practice', afterCardId: first.id }).card;
  assert.notEqual(second.id, first.id);
  assert.equal(second.back, undefined);
  assert.deepEqual(call('decks'), original);
});

test('sources are authorized and fingerprinted, and grade access is owner-bound and learner-only', t => {
  const { call, deck, binding, lesson } = fixture(t);
  const deckId = deck('Sources');
  const graph = call('source', { kind: 'graph', id: 'electric-charge' }, start, 'model');
  assert.match(graph.proposition.statement, /isolated system/);
  assert.throws(() => call('add', { deckId, front: 'What is conserved?', back: 'Charge.', source: graph.source }),
    { code: 'invalid_flashcard_command' });
  const authored = call('add', { deckId, front: 'What is conserved?', back: 'Charge.', source: graph.source }, start, 'model');
  assert.equal(authored.card.source.id, 'electric-charge');
  assert.throws(() => call('source', { kind: 'graph', id: 'invented' }, start, 'model'), { code: 'flashcard_source_unavailable' });

  assert.throws(() => call('source', { kind: 'material', id: 'notes' }, start, 'model'), { code: 'material_not_attached' });
  materialCommand(binding, { action: 'attach', materialId: 'notes', expectedRevision: lesson.read('lesson').adapter.revision, authorship: 'synthetic-fixture' });
  const notes = call('source', { kind: 'material', id: 'notes' }, start, 'model');
  assert.equal(notes.material.label, 'Course notes');
  call('add', { deckId, front: 'Why must a path be closed?', back: 'To permit current.', source: notes.source }, start, 'model');
  fs.appendFileSync(binding.materials[0].file, '\nChanged.');
  assert.throws(() => call('add', { deckId, front: 'Question', back: 'Answer', source: notes.source }, start, 'model'),
    { code: 'material_changed' });

  const other = { ...binding, ownerSessionId: 'different-owner' };
  assert.deepEqual(call('decks', {}, start, 'app', other).decks, []);
  const { token } = call('next', { deckId, mode: 'due' }).card;
  assert.throws(() => call('reveal', { token }, start, 'app', other), { code: 'invalid_flashcard_token' });
  assert.throws(() => call('reveal', { token }, start, 'model'), { code: 'invalid_flashcard_command' });
});

test('editing a card preserves due dates and invalidates an outstanding token', t => {
  const { call, deck, add } = fixture(t);
  const deckId = deck('Review');
  const cardId = add(deckId, 'Original', 'Answer');
  const { token } = call('next', { deckId, mode: 'due' }).card;
  const { card } = call('edit', { cardId, expectedVersion: 0, front: 'Revised', back: 'New answer' }, start, 'model');
  assert.equal(card.due, start);
  assert.throws(() => call('reveal', { token }), { code: 'stale_flashcard' });
  assert.equal(call('next', { deckId, mode: 'due' }).card.front, 'Revised');
});

