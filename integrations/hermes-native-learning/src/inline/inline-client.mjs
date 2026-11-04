// SPDX-License-Identifier: AGPL-3.0-only
// Inline adaptation of LearnHarness v0.3.4 QuestionDock/ReadingThinkingField.
// See inline/NOTICE.md. This module performs no grading or state-file writes.
import { CONFIDENCE_STOPS, DEFAULT_CONFIDENCE_INDEX, emptyDockSelection, toggleOption, toggleOther } from '../vendor/runtime/question-pure.ts';
import { mountPractice } from './practice-client.mjs';
import { CONFIDENCE_COLORS, confidenceRailStyle, nearestConfidenceIndex } from './confidence-style.mjs';
import { answeredRecord } from './answered-record.mjs';
import { createRichScope } from './rich-scope.mjs';
import { planDiagram } from './lesson-prose.mjs';
import { lessonDraftKey } from './lesson-identity.mjs';

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
  const rich=createRichScope(options.renderRich);
  let destroyed=false;
  let view = initialView;
  let state = { selection: emptyDockSelection(), text: '', other: '', thinking: '', readingThinking: '',
    confidenceIndex: DEFAULT_CONFIDENCE_INDEX, open: view.question?.open ?? true, pending: false };
  const draftKey = () => lessonDraftKey(view);
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
  function prose(tag,text,attributes={}){const element=node(tag,null,attributes);rich.render(element,text);return element;}
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
        detail.append(node('summary',proposition.name),prose('div',proposition.statement));
        for(const passage of proposition.passages??[])detail.append(prose('blockquote',passage));
        knowledge.append(detail);
      }
      root.append(knowledge);
    }
  }
  function present() {
    const q=view.question;
    options.onPresentation?.({open:state.open,...(options.externalChoices?{
      questionId:q?.toolCallId??null,selected:[...state.selection.selected],pending:state.pending}: {})});
  }
  function updateSubmit() { const b = root.querySelector('[data-submit]'); if (b) b.disabled = !canSubmit();if(options.externalChoices)present(); }
  function selectOption(index,questionId) {
    const q=view.question;
    if(destroyed||!q||q.toolCallId!==questionId||q.mode==='text'||!state.open||state.pending||
      !Number.isInteger(index)||index<0||index>=q.options.length)return false;
    state.selection=toggleOption(q.mode,state.selection,index);save();render();return true;
  }
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
    const diagram=planDiagram(view.plan);if(diagram&&options.renderRich&&!options.richProse)details.append(prose('div',diagram));
    if (!view.plan.approved) {
      details.open = true;
      details.append(button('Start this plan', () => { state.pending = true; save(); void deliver({ type: 'approve', chatId: view.chatId, planRevision: view.plan.planRevision, text: 'Start this plan.' }); }, { class: 'lh-submit', 'data-approve': '' }));
    }
    root.append(details);
  }
  function render() {
    rich.clear();
    root.replaceChildren();
    renderLessonPanels();
    const q = view.question;
    present();
    if(q&&view.answers.length){const previous=node('details',null,{'data-previous-answer':''});previous.append(node('summary','Previous answer'),answeredRecord(doc,view.answers.at(-1),{externalRichExplanation:options.richProse,renderProse:rich.render}));root.append(previous);}
    if (!q) {
      if(options.exploration){options.exploration.hidden=false;root.append(options.exploration);}
      const last = view.answers.at(-1);
      if(last)root.append(answeredRecord(doc,last,{richProse:options.richProse,externalRichExplanation:options.richProse,renderProse:rich.render}));
      renderPlan();
    } else {
      if (view.teachingText&&!options.richProse) root.append(prose('div', view.teachingText, { class: 'lh-teaching' }));
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
        if(options.exploration){options.exploration.hidden=false;dock.append(options.exploration);}
        if(!options.richProse)dock.append(prose('div', q.question, {class:'lh-question-text'}));
        if (q.context&&!options.richProse) dock.append(prose('div', q.context));
        if (q.mode !== 'text') {
          const group = node('div', null, { role: 'group', 'aria-label': q.mode === 'multi-select' ? 'Choose all that apply' : 'Choose an answer' });
          if(!options.externalChoices)q.options.forEach((option, index) => {
            const row = button(null, () => { selectOption(index,q.toolCallId); },
              { class: 'lh-option', 'aria-pressed': state.selection.selected.has(index), 'data-option': option.value });
            row.append(prose('span',`${index+1}. ${option.label}`,{class:'lh-choice-text'}));
            // Match the original dock: quiz descriptions can telegraph the answer.
            if (q.kind !== 'quiz' && option.description) row.append(prose('span', option.description, { class: 'lh-secondary' }));
            group.append(row);
          });
          if (q.kind === 'ask') {
            group.append(button('Other…', () => { state.selection = toggleOther(q.mode, state.selection); save(); render(); }, { class: 'lh-option', 'aria-pressed': state.selection.otherSelected }));
            if (state.selection.otherSelected) group.append(field('Other', 'other', 'Your response.'));
          }
          if (q.kind === 'quiz') group.append(button("I don't know", () => { state.selection = { selected: new Set(), otherSelected: false, dontKnow: !state.selection.dontKnow }; save(); render(); },
            { class: 'lh-option', 'aria-pressed': state.selection.dontKnow, 'data-dont-know': '' }));
          dock.append(group);
          if (q.kind === 'quiz') {
            const confidence = node('label', null, { class: 'lh-confidence' });
            const slider = node('input', null, { type: 'range', min: 0, max: 100, step: 1,
              'aria-label': 'Confidence — the probability your selected answer is correct', 'data-confidence': '' });
            slider.value = CONFIDENCE_STOPS[state.confidenceIndex]; slider.disabled = state.selection.dontKnow;
            slider.setAttribute('aria-valuetext', `${CONFIDENCE_STOPS[state.confidenceIndex]} percent`);
            const track=node('span',null,{class:'lh-confidence-track'}),rail=node('span',null,{class:'lh-confidence-rail','aria-hidden':'true'});
            const paint=()=>{Object.assign(rail.style,confidenceRailStyle(CONFIDENCE_STOPS[state.confidenceIndex]));slider.style.setProperty('--lh-confidence-color',CONFIDENCE_COLORS[state.confidenceIndex]);};
            paint();track.append(rail,slider);
            const value = node('output', state.selection.dontKnow ? '—' : `${CONFIDENCE_STOPS[state.confidenceIndex]}%`);
            const change=index=>{state.confidenceIndex=index;slider.value=CONFIDENCE_STOPS[index];value.textContent=`${CONFIDENCE_STOPS[index]}%`;slider.setAttribute('aria-valuetext',`${CONFIDENCE_STOPS[index]} percent`);paint();save();};
            slider.addEventListener('input', () => {const raw=Number(slider.value);if(!Number.isFinite(raw)||raw<0||raw>100||slider.disabled)return;change(nearestConfidenceIndex(raw));});
            slider.addEventListener('keydown',event=>{if(slider.disabled||event.altKey||event.ctrlKey||event.metaKey||!['ArrowLeft','ArrowRight'].includes(event.key))return;event.preventDefault();change(Math.max(0,Math.min(CONFIDENCE_STOPS.length-1,state.confidenceIndex+(event.key==='ArrowRight'?1:-1))));});
            confidence.append(node('span', 'Confidence'), track, value); dock.append(confidence);
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
    view = next;
    if (!same) state = { selection: emptyDockSelection(), text: '', other: '', thinking: '', readingThinking: '', confidenceIndex: DEFAULT_CONFIDENCE_INDEX, open: next.question?.open ?? true, pending: false };
    else state.pending = false;
    if (!same && options.drafts) {
      // Another host may have advanced the question. Preserve the old keyed
      // draft; a revision change is not proof that this unsent text was saved.
      try { restore(options.drafts.read(draftKey())); } catch { /* A missing draft never replaces lesson state. */ }
    }
    render();
  }
  const onGlobals = event => { restore(event.detail?.globals?.widgetState); render(); };
  win.addEventListener('openai:set_globals', onGlobals);
  render();
  if (draftLoadError) setStatus('The saved draft could not be restored. The saved lesson is unchanged.', true);
  return { applyView, submit, selectOption, readDraft: () => ({ ...state, selection: { ...state.selection, selected: new Set(state.selection.selected) } }),
    destroy: () => {destroyed=true;rich.clear();win.removeEventListener('openai:set_globals', onGlobals);} };
}
