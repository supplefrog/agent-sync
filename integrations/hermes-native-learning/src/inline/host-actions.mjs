// SPDX-License-Identifier: AGPL-3.0-only
// Called explicitly by the existing host agent's file/terminal tool lane.
// No background watcher, plugin registration, model dispatch or HTTP server.
import { requireState, StateError } from '../store.mjs';
import { handleAnswerRequest } from '../bridge.mjs';
import { INLINE_PREFIX } from './inline-client.mjs';

export function dispatchInline(adapter, boundChatId, action) {
  requireState(action && typeof action === 'object' && !Array.isArray(action) && action.chatId === boundChatId,
    'wrong_host_session', 'The action must target this host-bound teaching session.');
  if (action.type === 'answer') {
    requireState(Object.keys(action).every(k => ['type', 'chatId', 'toolCallId', 'request'].includes(k)), 'invalid_bridge_input', 'Unknown answer action field.');
    const { type, ...request } = action;
    return handleAnswerRequest(adapter, boundChatId, request);
  }
  if (action.type === 'resume') {
    requireState(Object.keys(action).every(k => ['type', 'chatId'].includes(k)), 'invalid_bridge_input', 'Unknown resume field.');
    return { ok: true, loaded: true, view: adapter.view(boundChatId) };
  }
  if (action.type === 'approve') {
    requireState(Object.keys(action).every(k => ['type', 'chatId', 'planRevision', 'text'].includes(k)), 'invalid_bridge_input', 'Unknown approval field.');
    const { type, ...input } = action;
    return { ok: true, persisted: true, view: adapter.approvePlan(input) };
  }
  throw new StateError('unsupported_action', 'Unsupported inline teaching action.');
}

export function parseInlinePrompt(prompt) {
  requireState(typeof prompt === 'string' && prompt.startsWith(INLINE_PREFIX) && prompt.length <= 65536,
    'invalid_bridge_input', 'Expected lh.inline JSON.');
  try { return JSON.parse(prompt.slice(INLINE_PREFIX.length)); }
  catch { throw new StateError('invalid_bridge_input', 'Malformed inline action JSON.'); }
}
