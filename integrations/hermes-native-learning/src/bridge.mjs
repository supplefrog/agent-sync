// SPDX-License-Identifier: AGPL-3.0-only
// Data protocol only. This module installs no plugin and renders no interface.
import { StateError, requireState } from './store.mjs';

export const HERMES_PREFIX = 'lh.answer ';
export function encodeHermesAnswerIntent(request) {
  const prompt = HERMES_PREFIX + JSON.stringify(request);
  requireState(prompt.length <= 500, 'host_payload_too_long', 'Hermes intents are capped at 500 characters. Use the host file/tool lane for a longer response; never truncate it.');
  return prompt;
}

export function handleAnswerRequest(adapter, boundChatId, data) {
  requireState(data && typeof data === 'object' && !Array.isArray(data), 'invalid_bridge_input', 'An answer-request object is required.');
  requireState(Object.keys(data).every(k => ['chatId', 'toolCallId', 'request'].includes(k)), 'invalid_bridge_input', 'Unknown bridge field.');
  requireState(data.chatId === boundChatId, 'wrong_host_session', 'The response targets a different teaching session.');
  const result = adapter.answerRequest(data);
  // Only this ack proves that the adapter persisted the answer. The host's
  // window.hermes.send() ack means delivery to the composer, not persistence.
  return { ok: true, persisted: true, toolCallId: data.toolCallId, revision: result.view.revision, view: result.view };
}

export function handleHermesIntent(adapter, boundChatId, prompt) {
  requireState(typeof prompt === 'string' && prompt.length <= 500 && prompt.startsWith(HERMES_PREFIX),
    'invalid_bridge_input', 'Expected a compact lh.answer intent.');
  let data;
  try { data = JSON.parse(prompt.slice(HERMES_PREFIX.length)); }
  catch { throw new StateError('invalid_bridge_input', 'Malformed JSON answer intent.'); }
  return handleAnswerRequest(adapter, boundChatId, data);
}
