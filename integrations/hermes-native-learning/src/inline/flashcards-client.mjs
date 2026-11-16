// SPDX-License-Identifier: AGPL-3.0-only
import { createRichScope } from './rich-scope.mjs';

const grades = ['Again', 'Hard', 'Good', 'Easy'];

export function mountFlashcards(container, { request, renderRich }) {
  if (typeof request !== 'function') throw new TypeError('Flashcards require a bound learner request.');
  const doc = container.ownerDocument;
  const rich = createRichScope(renderRich);
  let alive = true, pending = false, listed = false, decks = [];
  let selected = '', mode = null, active = null, revealed = null;
  const element = (tag, text) => {
    const node = doc.createElement(tag);
    if (text !== undefined) node.textContent = text;
    return node;
  };
  const button = (text, handler, type = 'button') => {
    const node = element('button', text);
    node.type = type;
    if (handler) node.addEventListener('click', handler);
    return node;
  };
  function label(text, control) {
    const wrap = element('label');
    wrap.className = 'lh-flashcards-field';
    wrap.append(element('span', text), control);
    return wrap;
  }
  function assertion(value) {
    if (!value || value.ok !== true) throw new Error(value?.message ?? 'Flashcards are unavailable. Try again.');
    return value;
  }
  async function ask(action, args = {}) {
    return assertion(await request({ action, ...args }));
  }

  const details = element('details');
  details.className = 'lh-flashcards';
  const summary = element('summary', 'Flashcards');
  const body = element('div');
  body.className = 'lh-flashcards-body';
  const notice = element('p', '');
  notice.className = 'lh-flashcards-notice';
  notice.setAttribute('role', 'status');
  notice.setAttribute('aria-live', 'polite');
  const retry = button('Reload decks', () => void perform(loadDecks));
  retry.hidden = true;
  const deckSelect = element('select');
  const deckField = label('Deck', deckSelect);
  const actions = element('div');
  actions.className = 'lh-flashcards-actions';
  const dueButton = button('Review due', () => void perform(() => start('due')));
  const practiceButton = button('Extra practice', () => void perform(() => start('practice')));
  actions.append(dueButton, practiceButton);
  const play = element('section');
  play.className = 'lh-flashcards-review';
  play.setAttribute('aria-label', 'Flashcard review');
  play.hidden = true;
  const empty = element('p', 'Create a deck to start reviewing.');
  empty.hidden = true;
  const review = element('div');
  review.hidden = true;
  const nextDue = element('p', '');
  nextDue.className = 'lh-flashcards-notice';
  review.append(deckField, actions, nextDue, play);

  const deckForm = element('form');
  const deckName = element('input');
  deckName.maxLength = 120;
  deckName.required = true;
  deckName.type = 'text';
  const deckSubmit = button('Create deck', null, 'submit');
  deckForm.append(label('Deck name', deckName), deckSubmit);
  const addDeck = element('details');
  addDeck.append(element('summary', 'New deck'), deckForm);

  const cardForm = element('form');
  const front = element('textarea');
  front.rows = 2;
  front.required = true;
  front.maxLength = 1500;
  const back = element('textarea');
  back.rows = 3;
  back.required = true;
  back.maxLength = 4000;
  const cardSubmit = button('Save card', null, 'submit');
  cardForm.append(label('Question', front), label('Answer', back), cardSubmit);
  const addCard = element('details');
  addCard.append(element('summary', 'Add a card'), cardForm);
  addCard.hidden = true;

  body.append(notice, retry, empty, review, addCard, addDeck);
  details.append(summary, body);
  container.append(details);

  function setNotice(text, error = false) {
    notice.setAttribute('role', error ? 'alert' : 'status');
    notice.textContent = text;
  }

  function updateControls() {
    const deck = decks.find(item => item.id === selected);
    deckSelect.disabled = pending;
    dueButton.disabled = pending || !deck?.due;
    dueButton.textContent = deck?.due ? 'Review due (' + deck.due + ')' : 'Review due';
    practiceButton.disabled = pending || !deck?.total;
    nextDue.textContent = deck?.nextDue && !deck.due
      ? 'Next review ' + new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(deck.nextDue)
      : '';
    retry.disabled = pending;
    deckSubmit.disabled = pending;
    cardSubmit.disabled = pending || !deck;
    for (const control of play.querySelectorAll('button')) {
      control.disabled = pending;
    }
  }

  async function perform(operation) {
    if (!alive || pending) return;
    pending = true;
    details.setAttribute('aria-busy', 'true');
    updateControls();
    try {
      await operation();
    } catch (error) {
      if (alive) {
        setNotice(error?.message ?? 'Flashcards are unavailable. Try again.', true);
        retry.hidden = false;
      }
    } finally {
      pending = false;
      if (alive) {
        details.removeAttribute('aria-busy');
        updateControls();
        if (focusTarget && documentContains(focusTarget)) focusTarget.focus();
      }
      focusTarget = null;
    }
  }

  let focusTarget = null;
  const documentContains = node => doc.documentElement.contains(node);
  function updateDecks(next, prefer) {
    decks = next;
    selected = decks.some(deck => deck.id === prefer) ? prefer : (decks[0]?.id ?? '');
    deckSelect.replaceChildren(...decks.map(deck => {
      const option = element('option', deck.title);
      option.value = deck.id;
      return option;
    }));
    deckSelect.value = selected;
    review.hidden = addCard.hidden = !selected;
    empty.hidden = Boolean(selected);
    if (!selected) addDeck.open = true;
    listed = true;
    retry.hidden = true;
    updateControls();
  }

  async function loadDecks(prefer = selected) {
    const answer = await ask('decks');
    if (alive) updateDecks(answer.decks, prefer);
  }

  function showCard() {
    rich.clear();
    play.replaceChildren();
    play.hidden = !active;
    if (!active) return;
    const question = element('div');
    question.className = 'lh-flashcards-content';
    rich.render(question, active.front);
    play.append(question);
    if (revealed) {
      const answer = element('div');
      answer.className = 'lh-flashcards-answer lh-flashcards-content';
      rich.render(answer, revealed.back);
      play.append(answer);
    }
    const decisions = element('div');
    decisions.className = 'lh-flashcards-actions';
    let first;
    if (!revealed) {
      first = button('Show answer', () => void perform(reveal));
      decisions.append(first);
    }
    if (mode === 'practice') {
      const next = button('Next card', () => void perform(() => nextCard(active.id)));
      first ??= next;
      decisions.append(next);
    } else if (revealed) {
      const ratings = grades.map((label, index) => button(label, () => void perform(() => rate(index + 1))));
      first = ratings[0];
      decisions.setAttribute('role', 'group');
      decisions.setAttribute('aria-label', 'Rate your recall');
      decisions.append(...ratings);
    }
    play.append(decisions);
    focusTarget = first;
    updateControls();
  }

  async function nextCard(afterCardId, nextMode = mode) {
    const outcome = await ask('next', { deckId: selected, mode: nextMode, ...(afterCardId ? { afterCardId } : {}) });
    if (!alive) return;
    mode = nextMode;
    active = outcome.card;
    revealed = null;
    showCard();
    if (!active) {
      const deck = decks.find(item => item.id === selected);
      setNotice(deck?.total ? 'You’re caught up with this deck.' : 'Add a card to this deck to start.');
      focusTarget = practiceButton.disabled ? deckSelect : practiceButton;
    }
  }

  async function start(nextMode) {
    await nextCard(undefined, nextMode);
    if (alive && active) setNotice(nextMode === 'practice' ? 'Extra practice leaves due dates as they are.' : '');
  }

  async function reveal() {
    const outcome = await ask('reveal', { token: active.token });
    if (!alive) return;
    revealed = outcome;
    showCard();
  }

  async function rate(rating) {
    await ask('rate', { token: revealed.token, rating });
    if (!alive) return;
    active = revealed = null;
    showCard();
    setNotice('Review saved.');
    await loadDecks();
    if (alive) await nextCard();
  }

  details.addEventListener('toggle', () => {
    if (details.open && (!listed || !active)) void perform(loadDecks);
  });
  deckSelect.addEventListener('change', () => {
    selected = deckSelect.value;
    active = revealed = mode = null;
    showCard();
    setNotice('');
  });
  deckForm.addEventListener('submit', event => {
    event.preventDefault();
    void perform(async () => {
      const title = deckName.value;
      const { deck } = await ask('create-deck', { title });
      if (!alive) return;
      if (deckName.value === title) deckName.value = '';
      addDeck.open = false;
      active = revealed = mode = null;
      showCard();
      setNotice('Deck ready.');
      await loadDecks(deck.id);
      focusTarget = addCard.querySelector('summary');
    });
  });
  cardForm.addEventListener('submit', event => {
    event.preventDefault();
    void perform(async () => {
      const captured = { front: front.value, back: back.value };
      await ask('add', { deckId: selected, ...captured });
      if (!alive) return;
      if (front.value === captured.front) front.value = '';
      if (back.value === captured.back) back.value = '';
      setNotice('Card saved.');
      await loadDecks();
    });
  });

  return {
    destroy() {
      alive = false;
      rich.clear();
      details.remove();
    },
  };
}
