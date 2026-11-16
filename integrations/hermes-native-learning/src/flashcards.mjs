// SPDX-License-Identifier: AGPL-3.0-only
// Private flashcard state beside the enrolled lesson, independent of its revision.
import fs from 'node:fs';
import path from 'node:path';
import { createHash, createHmac, randomBytes, randomUUID, timingSafeEqual } from 'node:crypto';
import { FileSessionStore, requireState } from './store.mjs';
import { LessonKnowledge } from './knowledge.mjs';
import { attachedMaterial } from './materials.mjs';
import { readNativePropositions } from './propositions.mjs';
import fsrs from './vendor/runtime/fsrs.cjs';

const actions = Object.freeze({
  decks: [],
  'create-deck': ['title'],
  add: ['deckId', 'front', 'back', 'source'],
  edit: ['cardId', 'expectedVersion', 'front', 'back'],
  cards: ['deckId', 'offset', 'expectedRevision'],
  source: ['kind', 'id'],
  next: ['deckId', 'mode', 'afterCardId'],
  reveal: ['token'],
  rate: ['token', 'rating'],
});
const appActions = new Set(['decks', 'create-deck', 'add', 'next', 'reveal', 'rate']);
const modelActions = new Set(['decks', 'create-deck', 'add', 'edit', 'cards', 'source']);
const maxDecks = 48;
const maxCards = 512;
const pageSize = 20;
const tokenLifetime = 30 * 60 * 1000;
const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);
const present = (value, length) => typeof value === 'string' && Boolean(value.trim()) && value.length <= length;
const hash = value => createHash('sha256').update(JSON.stringify(value)).digest('hex');

function verifyPath(target, directory) {
  try {
    const stat = fs.lstatSync(target);
    requireState((directory ? stat.isDirectory() : stat.isFile()) && !stat.isSymbolicLink() &&
      path.relative(target, fs.realpathSync(target)) === '', 'invalid_flashcard_root',
    'Flashcard storage must stay inside the enrolled lesson state directory.');
    return true;
  } catch (error) {
    if (error.code === 'ENOENT') return false;
    throw error;
  }
}

function openStore(binding) {
  const owner = binding.authorityId ?? binding.ownerSessionId;
  requireState(present(owner, 300), 'wrong_native_owner', 'A bound lesson owner is required.');
  const lesson = new FileSessionStore(binding.root);
  requireState(verifyPath(lesson.file(binding.chatId), false), 'not_found', 'Open the saved lesson before using flashcards.');
  const root = path.join(lesson.root, '.flashcards');
  verifyPath(root, true);
  const store = new FileSessionStore(root);
  const scope = hash([owner, binding.chatId]);
  return { store, scope, id: 'cards_' + scope };
}

function readRecord(port) {
  if (!verifyPath(port.store.file(port.id), false)) return null;
  return checkRecord(port.store.read(port.id), port.scope);
}

function checkRecord(record, scope) {
  requireState(record.family === 'lh-flashcards-v1' && record.scope === scope &&
    typeof record.tokenKey === 'string' && /^[0-9a-f]{64}$/.test(record.tokenKey) &&
    Array.isArray(record.decks) && Array.isArray(record.cards),
  'invalid_flashcard_store', 'Unrecognized flashcard store.');
  return record;
}

function change(port, update) {
  const create = !verifyPath(port.store.file(port.id), false);
  return port.store.change(port.id, current => {
    const record = current ? checkRecord(current, port.scope) : {
      id: port.id, version: 1, adapter: { version: 1, revision: -1 }, messages: [],
      scope: port.scope, family: 'lh-flashcards-v1',
      tokenKey: randomBytes(32).toString('hex'), decks: [], cards: [],
    };
    const { result, changed = true } = update(record);
    return { record, changed, result };
  }, { create, activity: false });
}

function findDeck(record, id) {
  const deck = record?.decks.find(value => value.id === id);
  requireState(deck, 'flashcard_deck_not_found', 'Choose a saved deck from this lesson.');
  return deck;
}

function findCard(record, id) {
  const card = record?.cards.find(value => value.id === id);
  requireState(card, 'flashcard_not_found', 'Choose a saved card from this lesson.');
  return card;
}

function authorCard(card) {
  return { id: card.id, deckId: card.deckId, version: card.version, front: card.front, back: card.back,
    due: card.schedule.due, ...(card.source ? { source: card.source } : {}) };
}

function sourceContext(binding, kind, id) {
  requireState(present(id, 160), 'invalid_flashcard_command', 'Provide the ID of an enrolled source.');
  if (kind === 'graph') {
    const nodes = binding.knowledgeRoot ? new LessonKnowledge(binding.knowledgeRoot).graph().nodes :
      binding.graphRoot ? readNativePropositions(binding.graphRoot).nodes : [];
    const node = nodes.find(value => value.id === id);
    requireState(node, 'flashcard_source_unavailable', 'Choose a current proposition from the enrolled graph.');
    const proposition = { id: node.id, name: node.name, statement: node.statement };
    return { source: { kind, id, fingerprint: hash(proposition) }, proposition };
  }
  requireState(kind === 'material', 'invalid_flashcard_command', 'Choose graph or material.');
  const value = attachedMaterial(binding, id);
  const material = { id: value.id, label: value.label, kind: value.kind, sha256: value.sha256 };
  return { source: { kind, id, fingerprint: value.sha256 }, material };
}

function verifySource(binding, supplied) {
  if (supplied === undefined) return undefined;
  requireState(object(supplied) && Object.keys(supplied).every(key => ['kind', 'id', 'fingerprint'].includes(key)) &&
    typeof supplied.fingerprint === 'string' && /^[a-f0-9]{64}$/.test(supplied.fingerprint),
  'invalid_flashcard_command', 'Use a source reference returned by the flashcard source command.');
  const { source } = sourceContext(binding, supplied.kind, supplied.id);
  requireState(source.fingerprint === supplied.fingerprint, 'flashcard_source_changed',
    'This source changed. Read its latest version before authoring a card.');
  return source;
}

function sign(record, body) {
  return createHmac('sha256', Buffer.from(record.tokenKey, 'hex')).update(body).digest();
}

function pack(record, info) {
  const body = Buffer.from(JSON.stringify(info)).toString('base64url');
  return body + '.' + sign(record, body).toString('base64url');
}

function unpack(record, token, purpose, now) {
  const invalid = 'invalid_flashcard_token', guidance = 'Start a fresh review for this card.';
  requireState(record && typeof token === 'string' && token.length <= 512 && /^[A-Za-z0-9_-]+\.[A-Za-z0-9_-]{43}$/.test(token),
    invalid, guidance);
  const [body, mac] = token.split('.');
  requireState(timingSafeEqual(sign(record, body), Buffer.from(mac, 'base64url')) &&
    sign(record, body).toString('base64url') === mac, invalid, guidance);
  const payload = JSON.parse(Buffer.from(body, 'base64url').toString('utf8'));
  requireState(payload.purpose === purpose && payload.expires >= now &&
    (payload.mode === 'due' || payload.mode === 'practice'), invalid, guidance);
  return payload;
}

function verifyReview(record, payload) {
  const card = findCard(record, payload.id);
  requireState(card.version === payload.version && card.deckId === payload.deckId, 'stale_flashcard',
    'This card changed. Start a fresh review.');
  return card;
}

function summaries(record, now) {
  const summaries = new Map((record?.decks ?? []).map(({ id, title }) => [id, { id, title, total: 0, due: 0, nextDue: null }]));
  for (const card of record?.cards ?? []) {
    const deck = summaries.get(card.deckId);
    if (!deck) continue;
    deck.total++;
    if (fsrs.isDue(card.schedule, now)) deck.due++;
    else deck.nextDue = Math.min(deck.nextDue ?? Infinity, card.schedule.due);
  }
  return [...summaries.values()];
}

function pickNext(record, command, now) {
  const { deckId, mode, afterCardId } = command;
  findDeck(record, deckId);
  requireState((mode === 'due' && afterCardId === undefined) ||
    (mode === 'practice' && (afterCardId === undefined || present(afterCardId, 80))),
  'invalid_flashcard_command', 'Choose scheduled review or extra practice.');
  const cards = record.cards.filter(card => card.deckId === deckId);
  let card;
  if (mode === 'practice' && cards.length) {
    const previous = cards.findIndex(card => card.id === afterCardId);
    card = cards[(previous + 1) % cards.length];
  }
  if (mode === 'due') {
    const priority = [2, 0, 1, 0]; // Learning or relearning, then reviews, then new cards.
    card = cards.filter(candidate => fsrs.isDue(candidate.schedule, now)).sort((a, b) =>
      priority[a.schedule.state] - priority[b.schedule.state] || a.schedule.due - b.schedule.due)[0];
  }
  return { ok: true, card: card ? {
    id: card.id, front: card.front, token: pack(record, {
      purpose: 'reveal', id: card.id, deckId, mode, version: card.version,
      attempt: randomUUID(), expires: now + tokenLifetime,
    }),
  } : null };
}

export function executeFlashcards(binding, command, { origin = 'model', now = Date.now() } = {}) {
  requireState(object(command) && command.op === 'flashcards' && command.chatId === binding.chatId &&
    Number.isSafeInteger(now) && now >= 0 && now <= 8640000000000000 - tokenLifetime &&
    (origin === 'app' ? appActions.has(command.action) : origin === 'model' && modelActions.has(command.action)) &&
    Object.keys(command).every(key => ['op', 'chatId', 'action', ...actions[command.action]].includes(key)) &&
    (origin !== 'app' || command.source === undefined), 'invalid_flashcard_command',
  'Use an authorized flashcard action for the current lesson.');
  const port = openStore(binding);
  if (command.action === 'decks') return { ok: true, decks: summaries(readRecord(port), now) };
  if (command.action === 'source') return { ok: true, ...sourceContext(binding, command.kind, command.id) };
  if (command.action === 'next') return pickNext(readRecord(port), command, now);
  if (command.action === 'reveal') {
    const record = readRecord(port);
    const payload = unpack(record, command.token, 'reveal', now);
    const card = verifyReview(record, payload);
    return { ok: true, id: card.id, back: card.back, ...(payload.mode === 'due' ?
      { token: pack(record, { ...payload, purpose: 'rate' }) } : {}) };
  }
  if (command.action === 'cards') {
    const record = readRecord(port);
    findDeck(record, command.deckId);
    const offset = command.offset ?? 0;
    const revision = record.adapter.revision;
    requireState(Number.isSafeInteger(offset) && offset >= 0 && offset <= maxCards &&
      (offset === 0 || command.expectedRevision === revision) &&
      (command.expectedRevision === undefined || command.expectedRevision === revision),
    'stale_flashcard', 'Reload the first page after the deck changes.');
    const cards = record.cards.filter(card => card.deckId === command.deckId);
    return { ok: true, revision, cards: cards.slice(offset, offset + pageSize).map(authorCard),
      nextOffset: offset + pageSize < cards.length ? offset + pageSize : null };
  }
  if (command.action === 'create-deck') {
    requireState(present(command.title, 120), 'invalid_flashcard_command', 'Enter a deck name of up to 120 characters.');
    return change(port, record => {
      const title = command.title.trim(), saved = record.decks.find(deck => deck.title === title);
      if (saved) return { changed: false, result: { ok: true, deck: saved } };
      requireState(record.decks.length < maxDecks, 'flashcard_limit', 'This lesson has reached its deck limit.');
      const deck = { id: randomUUID(), title };
      record.decks.push(deck);
      return { result: { ok: true, deck } };
    });
  }
  if (command.action === 'add' || command.action === 'edit') {
    requireState(present(command.front, 1500) && present(command.back, 4000), 'invalid_flashcard_command',
      'Enter a question (up to 1,500 characters) and answer (up to 4,000).');
    return change(port, record => {
      let card;
      if (command.action === 'edit') {
        card = findCard(record, command.cardId);
        requireState(card.version === command.expectedVersion, 'stale_flashcard', 'Read the current card before editing.');
        if (card.front === command.front && card.back === command.back)
          return { changed: false, result: { ok: true, card: authorCard(card) } };
        card.front = command.front;
        card.back = command.back;
        card.version++;
      } else {
        findDeck(record, command.deckId);
        const source = verifySource(binding, command.source);
        const saved = record.cards.find(value => value.deckId === command.deckId && value.front === command.front &&
          value.back === command.back && value.source?.fingerprint === source?.fingerprint &&
          value.source?.kind === source?.kind && value.source?.id === source?.id);
        if (saved) return { changed: false, result: { ok: true, card: authorCard(saved) } };
        requireState(record.cards.length < maxCards, 'flashcard_limit', 'This lesson has reached its card limit.');
        card = { id: randomUUID(), deckId: command.deckId, version: 0, front: command.front, back: command.back,
          schedule: fsrs.createSchedule(now), ...(source ? { source } : {}) };
        record.cards.push(card);
      }
      return { result: { ok: true, card: authorCard(card) } };
    });
  }

  // Grade a single revealed, scheduled review. The write holds the store's
  // exclusive lock while validating the signed card version and updating it.
  requireState(Number.isInteger(command.rating) && command.rating >= 1 && command.rating <= 4,
    'invalid_flashcard_command', 'Choose Again, Hard, Good, or Easy.');
  const initial = readRecord(port);
  unpack(initial, command.token, 'rate', now);
  return change(port, record => {
    const payload = unpack(record, command.token, 'rate', now);
    const card = findCard(record, payload.id);
    const receipt = hash(command.token);
    if (card.lastReview?.receipt === receipt && card.lastReview.rating === command.rating) {
      return { changed: false, result: { ok: true, due: card.schedule.due, reps: card.schedule.reps, replayed: true } };
    }
    verifyReview(record, payload);
    requireState(payload.mode === 'due' && fsrs.isDue(card.schedule, now) &&
      (card.schedule.last_review === null || card.schedule.last_review <= now),
    'stale_flashcard', 'This card is no longer due for review.');
    card.schedule = fsrs.rate(card.schedule, command.rating, now);
    card.version++;
    card.lastReview = { receipt, rating: command.rating };
    return { result: { ok: true, due: card.schedule.due, reps: card.schedule.reps } };
  });
}
