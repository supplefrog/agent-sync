// SPDX-License-Identifier: AGPL-3.0-only
// Inline adaptation of LearnHarness v0.3.4 QuestionDock/ReadingThinkingField.
// See inline/NOTICE.md. This module performs no grading or state-file writes.
import { CONFIDENCE_STOPS, DEFAULT_CONFIDENCE_INDEX, emptyDockSelection, toggleOption, toggleOther } from '../vendor/runtime/question-pure.ts';
import { mountPractice } from './practice-client.mjs';

export const INLINE_PREFIX = 'lh.inline ';

export function nativeTransport(win) {
  return async action => {
    const prompt = INLINE_PREFIX + JSON.stringify(action);
    if (typeof win.hermes?.send === 'function') {
      if (prompt.length > 500) throw new Error('This answer is too long for Hermes’s inline send. Keep the draft and use the host file/tool lane; nothing has been truncated.');
      const ack = await win.hermes.send(prompt);
      if (!ack?.ok) throw new Error(`Delivery failed: ${ack?.error ?? 'undelivered'}. Your draft is retained.`);
      return { delivered: true };
    }
    if (typeof win.openai?.sendFollowUpMessage === 'function') {
      await win.openai.sendFollowUpMessage({ prompt, title: action.type === 'answer' ? 'Submit this lesson answer' : 'Resume the saved lesson' });
      return { requested: true };
    }
    throw new Error('Open this lesson in the host chat to submit. Your draft is retained.');
  };
}

export function mountInline(root, initialView, options = {}) {
  if (initialView.kind === 'practice') return mountPractice(root, initialView, options);
  const win = root.ownerDocument.defaultView;
  const doc = root.ownerDocument;
  const send = options.send ?? nativeTransport(win);
  let view = initialView;
  let state = { selection: emptyDockSelection(), text: '', other: '', thinking: '', readingThinking: '',
    confidenceIndex: DEFAULT_CONFIDENCE_INDEX, open: view.question?.open ?? true, pending: false };
  const draftKey = () => `${view.chatId}:${view.question?.toolCallId ?? 'idle'}`;
  function setStatus(message, error = false) {
    const status = root.querySelector('[data-status]');
    if (status) { status.textContent = message; status.setAttribute('role', error ? 'alert' : 'status'); }
  }
  function save() {
    const snapshot = { key: draftKey(), selected: [...state.selection.selected], otherSelected: state.selection.otherSelected,
      dontKnow: state.selection.dontKnow, text: state.text, other: state.other, thinking: state.thinking,
      readingThinking: state.readingThinking, confidenceIndex: state.confidenceIndex, open: state.open, pending: state.pending };
    if (!options.drafts && typeof win.openai?.setWidgetState !== 'function') return;
    const payload = { modelContent: null, privateContent: { lhInlineDraft: snapshot } };
    if (new TextEncoder().encode(JSON.stringify(payload)).length > 16 * 1024) {
      setStatus('This draft exceeds the host’s saved-state limit. Keep this view open.', true); return;
    }
    try {
      Promise.resolve(options.drafts ? options.drafts.write(snapshot.key, payload) : win.openai.setWidgetState(payload))
        .catch(() => setStatus('The host could not save this draft. Keep this view open.', true));
    } catch { setStatus('The host could not save this draft. Keep this view open.', true); }
  }
  function restore(widgetState) {
    const s = widgetState?.privateContent?.lhInlineDraft;
    if (!s || s.key !== draftKey() || !view.question) return;
    const count = view.question.options.length;
    if (!Array.isArray(s.selected) || !s.selected.every(i => Number.isInteger(i) && i >= 0 && i < count)) return;
    state = { ...state, selection: { selected: new Set(s.selected), otherSelected: s.otherSelected === true, dontKnow: s.dontKnow === true },
      text: typeof s.text === 'string' ? s.text : '', other: typeof s.other === 'string' ? s.other : '',
      thinking: typeof s.thinking === 'string' ? s.thinking : '', readingThinking: typeof s.readingThinking === 'string' ? s.readingThinking : '',
      confidenceIndex: Number.isInteger(s.confidenceIndex) && s.confidenceIndex >= 0 && s.confidenceIndex < CONFIDENCE_STOPS.length ? s.confidenceIndex : DEFAULT_CONFIDENCE_INDEX,
      open: typeof s.open === 'boolean' ? s.open : state.open, pending: false };
  }
  let draftLoadError = false;
  try { restore(options.drafts ? options.drafts.read(draftKey()) : win.openai?.widgetState); }
  catch { draftLoadError = true; }
  function node(tag, text, attributes = {}) {
    const element = doc.createElement(tag);
    if (text !== null) element.textContent = text;
    for (const [key, value] of Object.entries(attributes)) if (value !== undefined) element.setAttribute(key, String(value));
    return element;
  }
  function button(text, handler, attributes = {}) {
    const b = node('button', text, { type: 'button', ...attributes }); b.addEventListener('click', handler); return b;
  }
  function field(label, name, placeholder) {
    const wrap = node('label', null, { class: 'lh-field' });
    wrap.append(node('span', label, { class: 'lh-field-label' }));
    const input = node('textarea', null, { rows: view.phase === 'teach' ? 3 : 1, 'data-field': name, placeholder });
    input.value = state[name];
    input.addEventListener('input', () => { state[name] = input.value; save(); updateSubmit(); });
    input.addEventListener('keydown', event => {
      if (event.key === 'Enter' && (!event.shiftKey || event.metaKey || event.ctrlKey)) {
        event.preventDefault();
        if (name === 'readingThinking' && !state.open) { state.open = true; save(); render(); }
        else if (name !== 'readingThinking') void submit();
      }
    });
    wrap.append(input); return wrap;
  }
  function canSubmit() {
    const q = view.question;
    return q && !state.pending && (q.mode === 'text' ? state.text.trim().length > 0
      : state.selection.dontKnow || state.selection.selected.size > 0 || (state.selection.otherSelected && state.other.trim().length > 0));
  }
  function renderLessonPanels() {
    if(view.assessment) {
      const assessment=node('details',null,{'data-assessment':''});
      assessment.append(node('summary','Starting assessment'));
      if(view.assessment.summary)assessment.append(node('p',view.assessment.summary));
      for(const strand of view.assessment.strands)assessment.append(node('p',`${strand.strand}: ${strand.assessment}`));
      root.append(assessment);
    }
    if(view.knowledge?.nodes?.length) {
      const knowledge=node('details',null,{'data-knowledge':''});
      knowledge.append(node('summary','Propositions from this lesson'));
      knowledge.append(node('p',view.knowledge.scope));
      for(const proposition of view.knowledge.nodes) {
        const detail=node('details',null,{'data-proposition':proposition.id});
        detail.append(node('summary',proposition.name),node('p',proposition.statement));
        for(const passage of proposition.passages??[])detail.append(node('blockquote',passage));
        knowledge.append(detail);
      }
      root.append(knowledge);
    }
  }
  function updateSubmit() { const b = root.querySelector('[data-submit]'); if (b) b.disabled = !canSubmit(); }
  function answerRequest() {
    const q = view.question;
    const request = {};
    if (q.mode === 'text') request.text = state.text;
    else {
      request.dontKnow = state.selection.dontKnow;
      request.values = [...state.selection.selected].map(i => q.options[i].value);
      if (state.selection.otherSelected) request.other = state.other;
      if (state.thinking.trim()) request.thinking = state.thinking;
      if (q.kind === 'quiz' && !state.selection.dontKnow) request.confidence = CONFIDENCE_STOPS[state.confidenceIndex];
    }
    if (state.readingThinking.trim()) request.readingThinking = state.readingThinking;
    return request;
  }
  async function deliver(action) {
    try {
      const ack = await send(action);
      if (ack?.view && (ack.persisted === true || ack.loaded === true)) {
        applyView(ack.view); setStatus(ack.loaded ? 'Saved lesson reopened.' : action.type === 'approve' ? 'Plan approval saved.' : 'Answer saved.'); return;
      }
      setStatus(ack?.delivered ? 'Delivered to the host. Waiting for the saved lesson response.' : 'Host action requested. Waiting for the saved lesson response.');
    } catch (error) {
      state.pending = false; save(); updateSubmit(); setStatus(error.message, true);
    }
  }
  async function submit() {
    if (!canSubmit()) return;
    const action = { type: 'answer', chatId: view.chatId, toolCallId: view.question.toolCallId, request: answerRequest() };
    state.pending = true; save(); updateSubmit(); setStatus('Sending answer…');
    await deliver(action);
  }
  function renderPlan() {
    if (!view.plan) return;
    const details = node('details', null, { class: 'lh-plan' });
    details.append(node('summary', view.plan.approved ? 'Lesson plan' : 'Proposed lesson plan'));
    const list = node('ol', null);
    for (const item of view.plan.nodes) list.append(node('li', `${item.title} · ${item.status}`, { 'data-node-id': item.id }));
    details.append(list);
    if (!view.plan.approved) {
      details.open = true;
      details.append(button('Start this plan', () => { state.pending = true; save(); void deliver({ type: 'approve', chatId: view.chatId, planRevision: view.plan.planRevision, text: 'Start this plan.' }); }, { class: 'lh-submit', 'data-approve': '' }));
    }
    root.append(details);
  }
  function render() {
    root.replaceChildren();
    renderLessonPanels();
    options.onPresentation?.({open:state.open});
    const q = view.question;
    if (!q) {
      const last = view.answers.at(-1);
      if (last) {
        if(!options.richProse)root.append(node('h3', last.questionText));
        root.append(node('p', last.text ?? (last.dontKnow ? 'I don’t know' : last.answers.map(a => a.label).join(', '))));
        if (last.thinking) root.append(node('p', `Your thinking: ${last.thinking}`));
        if (last.readingThinking) root.append(node('p', `Thinking while reading: ${last.readingThinking}`));
        if (last.correct !== undefined) root.append(node('p', last.correct ? 'Correct' : 'Review this step'));
        if (last.committed&&!options.richProse) root.append(node('p', last.committed));
        if (last.explanation&&!options.richProse) root.append(node('p', last.explanation));
      }
      renderPlan();
    } else {
      if (view.teachingText&&!options.richProse) root.append(node('p', view.teachingText, { class: 'lh-teaching' }));
      if (q.needsReveal) root.append(field('Thinking while reading', 'readingThinking', 'Whatever comes to mind as you read.'));
      const dock = node('section', null, { class: 'lh-dock' });
      root.append(dock);
      if (!state.open) {
        dock.append(button(q.needsReveal ? 'Check your understanding · Open' : `${q.questionType === 'predict' ? 'Prediction' : 'Question'} · Reopen`, () => { state.open = true; save(); render(); }, { class: 'lh-reveal', 'data-reveal': '' }));
      } else {
        const heading = node('div', null, { class: 'lh-heading' });
        const label = q.questionType === 'predict' ? 'Prediction' : q.tool === 'probe' ? 'Probe' : q.tool === 'recall' ? 'Recall' : q.kind === 'ask' ? 'Question' : 'Check';
        heading.append(node('span', label, { class: 'lh-kind' }), button('Close', () => { state.open = false; save(); render(); }, { class: 'lh-close', 'data-close': '' }));
        dock.append(heading);
        if(!options.richProse)dock.append(node('h3', q.question));
        if (q.context&&!options.richProse) dock.append(node('p', q.context));
        if (q.mode !== 'text') {
          const group = node('div', null, { role: 'group', 'aria-label': q.mode === 'multi-select' ? 'Choose all that apply' : 'Choose an answer' });
          q.options.forEach((option, index) => {
            const row = button(`${index + 1}. ${option.label}`, () => { state.selection = toggleOption(q.mode, state.selection, index); save(); render(); },
              { class: 'lh-option', 'aria-pressed': state.selection.selected.has(index), 'data-option': option.value });
            if (option.description) row.append(node('span', option.description, { class: 'lh-secondary' }));
            group.append(row);
          });
          if (q.kind === 'ask') {
            group.append(button('Other…', () => { state.selection = toggleOther(q.mode, state.selection); save(); render(); }, { class: 'lh-option', 'aria-pressed': state.selection.otherSelected }));
            if (state.selection.otherSelected) group.append(field('Other', 'other', 'Your response.'));
          }
          group.append(button('I don’t know', () => { state.selection = { selected: new Set(), otherSelected: false, dontKnow: !state.selection.dontKnow }; save(); render(); },
            { class: 'lh-option', 'aria-pressed': state.selection.dontKnow, 'data-dont-know': '' }));
          dock.append(group);
          if (q.kind === 'quiz') {
            const confidence = node('label', null, { class: 'lh-confidence' });
            const slider = node('input', null, { type: 'range', min: 0, max: CONFIDENCE_STOPS.length - 1, step: 1,
              'aria-label': 'Confidence — the probability your selected answer is correct', 'data-confidence': '' });
            slider.value = state.confidenceIndex; slider.disabled = state.selection.dontKnow;
            const value = node('output', state.selection.dontKnow ? '—' : `${CONFIDENCE_STOPS[state.confidenceIndex]}%`);
            slider.addEventListener('input', () => { state.confidenceIndex = Number(slider.value); value.textContent = `${CONFIDENCE_STOPS[state.confidenceIndex]}%`; save(); });
            confidence.append(node('span', 'Confidence'), slider, value); dock.append(confidence);
          }
        }
        dock.append(q.mode === 'text' ? field('Your answer', 'text', 'Type your answer.') : field('Your thinking', 'thinking', 'Why this answer? Whatever comes to mind.'));
        const footer = node('div', null, { class: 'lh-footer' });
        footer.append(node('span', 'Enter submits · Shift+Enter newline', { class: 'lh-secondary' }), button('Submit answer', () => void submit(), { class: 'lh-submit', 'data-submit': '' }));
        dock.append(footer);
      }
      renderPlan();
    }
    root.append(node('p', state.pending ? 'Waiting for the saved lesson response.' : '', { 'data-status': '', 'aria-live': 'polite', role: 'status' }));
    root.append(button('Resume saved lesson', () => { if(options.onResume){void options.onResume();return;} state.pending = true; save(); void deliver({ type: 'resume', chatId: view.chatId }); }, { class: 'lh-resume', 'data-resume': '' }));
    updateSubmit();
  }
  function applyView(next) {
    if (next.chatId !== view.chatId) throw new Error('The saved response belongs to a different lesson.');
    const same = next.question?.toolCallId === view.question?.toolCallId;
    const previousKey = draftKey();
    view = next;
    if (!same) state = { selection: emptyDockSelection(), text: '', other: '', thinking: '', readingThinking: '', confidenceIndex: DEFAULT_CONFIDENCE_INDEX, open: next.question?.open ?? true, pending: false };
    else state.pending = false;
    if (!same && options.drafts) {
      try { options.drafts.remove(previousKey); } catch { /* Saved answer remains authoritative. */ }
      try { restore(options.drafts.read(draftKey())); } catch { /* A missing draft never replaces lesson state. */ }
    }
    render();
  }
  const onGlobals = event => { restore(event.detail?.globals?.widgetState); render(); };
  win.addEventListener('openai:set_globals', onGlobals);
  render();
  if (draftLoadError) setStatus('The saved draft could not be restored. The saved lesson is unchanged.', true);
  return { applyView, submit, readDraft: () => ({ ...state, selection: { ...state.selection, selected: new Set(state.selection.selected) } }),
    destroy: () => win.removeEventListener('openai:set_globals', onGlobals) };
}
