// SPDX-License-Identifier: AGPL-3.0-only
// Generates a self-contained fragment from a redacted adapter view.
import * as fs from 'node:fs';
import * as path from 'node:path';
import { fileURLToPath } from 'node:url';
import { stripTypeScriptTypes } from 'node:module';
import { TeachingAdapter } from '../adapter.mjs';

export const INLINE_HOME = fileURLToPath(new URL('./', import.meta.url));
export const QUALIFICATION_CHAT = 'synthetic-inline-slope';
export const QUALIFICATION_ROOT = path.join(INLINE_HOME, 'state');

export function qualifySeed(adapter, chatId = QUALIFICATION_CHAT) {
  if (fs.existsSync(adapter.store.file(chatId))) return adapter.view(chatId);
  adapter.create({ chatId, title: 'Synthetic inline slope lesson', goal: 'Exercise the inline teaching controls; this is a qualification fixture.' });
  adapter.tool({ chatId, toolCallId: 'assessment', name: 'probe_done', input: { assessment: { strands: [{ strand: 'Slope as a ratio', assessment: 'Synthetic fixture: start with a fixed run and changing rise.' }] } } });
  adapter.tool({ chatId, toolCallId: 'plan', name: 'plan_init', input: { mermaid: 'graph TD\n ratio[Slope as a ratio] --> secant[Average rate] --> limit[Instantaneous rate]' } });
  adapter.approvePlan({ chatId, planRevision: 1, text: 'Use this synthetic qualification plan.' });
  adapter.tool({ chatId, toolCallId: 'prediction', name: 'quiz', input: { type: 'predict', nodeId: 'ratio',
    question: 'A line rises 6 units over a run of 3. If its rise doubles and its run stays fixed, what is the new slope?',
    options: [{ label: '2', value: 'two' }, { label: '4', value: 'four' }, { label: '6', value: 'six' }],
    explanation: 'The rise becomes 12 while the run stays 3, so the new slope is 12 ÷ 3 = 4.', correctAnswer: 'four' } });
  return adapter.view(chatId);
}

export function inlineView(adapter, chatId) {
  const view = adapter.view(chatId);
  const messages = adapter.context(chatId);
  if (view.question) {
    const questionIndex = messages.findIndex(m => m.role === 'assistant' &&
      m.content.some(b => b.type === 'toolCall' && b.id === view.question.toolCallId));
    const precedingText = [];
    // Keep feedback/explanation from this teacher reaction beside either kind
    // of question. Stop at the preceding resolution so old teaching is not
    // accidentally carried into a later question without fresh feedback.
    for (let i = questionIndex; i >= 0; i--) {
      const message = messages[i];
      if (message.role === 'toolResult') break;
      if (message.role === 'assistant') {
        const text = message.content.filter(b => b.type === 'text').map(b => b.text).join('\n');
        if (text) precedingText.unshift(text);
      }
    }
    if (precedingText.length) view.teachingText = precedingText.join('\n\n');
  }
  return view;
}

// Native fragments keep their original no-network transport. Only the explicit
// standalone browser route opts into the same-origin local action endpoint.
export function renderInline(view, { localBrowser = false, nonce, csrfToken } = {}) {
  if (localBrowser && (![nonce, csrfToken].every(value => typeof value === 'string' && /^[A-Za-z0-9_-]{16,128}$/.test(value)))) {
    throw new Error('Local browser bootstrap requires valid ephemeral values.');
  }
  const template = fs.readFileSync(path.join(INLINE_HOME, 'inline-template.html'), 'utf8');
  const source = fs.readFileSync(path.join(INLINE_HOME, '../vendor/runtime/question-pure.ts'), 'utf8');
  const start = source.indexOf('export const CONFIDENCE_STOPS');
  const end = source.indexOf('// ─── options', start);
  if (start < 0 || end < 0) throw new Error('Pinned selection helper boundaries not found.');
  const selection = stripTypeScriptTypes(source.slice(start, end));
  const client = fs.readFileSync(path.join(INLINE_HOME, 'inline-client.mjs'), 'utf8').replace(/^import .*?;\r?\n/gm, '');
  const practiceClient = fs.readFileSync(path.join(INLINE_HOME, 'practice-client.mjs'), 'utf8');
  const safe = JSON.stringify(view).replace(/</g, '\\u003c').replace(/&/g, '\\u0026').replace(/\u2028/g, '\\u2028').replace(/\u2029/g, '\\u2029');
  const data = `<script id="lh-inline-data" type="application/json">${safe}</script>`;
  const browserSend = localBrowser ? `, { send: async action => {
    const response = await fetch('/action', { method: 'POST', mode: 'same-origin', credentials: 'omit',
      headers: { 'Content-Type': 'application/json', 'X-LH-CSRF': ${JSON.stringify(csrfToken)} }, body: JSON.stringify(action) });
    const result = await response.json();
    if (!response.ok || result.ok !== true) throw new Error(result.error || 'The local handler could not save this response.');
    return result;
  }, drafts: {
    read: key => { const raw = localStorage.getItem('lh-inline-draft:v1:' + key); return raw && raw.length <= 16384 ? JSON.parse(raw) : null; },
    write: (key, payload) => localStorage.setItem('lh-inline-draft:v1:' + key, JSON.stringify(payload)),
    remove: key => localStorage.removeItem('lh-inline-draft:v1:' + key)
  } }` : '';
  const scriptNonce = localBrowser ? ` nonce="${nonce}"` : '';
  const runtime = `<script type="module"${scriptNonce}>\n${selection}\n${client}\n${practiceClient}\nmountInline(document.getElementById('lh-inline-lesson'), JSON.parse(document.getElementById('lh-inline-data').textContent)${browserSend});\n</script>`;
  return template.replace('<!-- INLINE_PAYLOAD -->', data).replace('<!-- INLINE_RUNTIME -->', runtime);
}

export function buildInline(view, output = path.join(INLINE_HOME, 'inline-lesson.html')) {
  fs.mkdirSync(path.dirname(output), { recursive: true });
  fs.writeFileSync(output, renderInline(view));
  return output;
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const adapter = new TeachingAdapter(QUALIFICATION_ROOT);
  qualifySeed(adapter);
  const output = buildInline(inlineView(adapter, QUALIFICATION_CHAT));
  process.stdout.write(JSON.stringify({ output, chatId: QUALIFICATION_CHAT, scope: 'synthetic inline candidate; no live host interaction claimed' }) + '\n');
}
