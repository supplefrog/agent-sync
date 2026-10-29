// SPDX-License-Identifier: AGPL-3.0-only
// Existing-host file/tool adapter. No model dispatch, browser endpoint, or loop.
import * as fs from 'node:fs';
import * as path from 'node:path';
import { createHash, randomUUID } from 'node:crypto';
import { TeachingAdapter } from '../../adapter.mjs';
import { FileSessionStore, requireState } from '../../store.mjs';
import { inlineView } from '../build-inline.mjs';

function fields(command, allowed) {
  requireState(command && typeof command === 'object' && !Array.isArray(command), 'invalid_host_command', 'Expected a host command.');
  requireState(Object.keys(command).every(key => allowed.includes(key)), 'invalid_host_command', 'Unknown host-command field.');
}
function revision(value) {
  requireState(Number.isSafeInteger(value) && value >= 0, 'invalid_host_command', 'expectedRevision is required.');
}
function authorship(value) {
  requireState(['host-agent', 'synthetic-fixture'].includes(value), 'invalid_host_command', 'Declare host-agent or synthetic-fixture authorship.');
}

// The revision/lease guard runs INSIDE the existing file store's writer lock.
// It adds no alternate storage implementation or transaction/replay mechanism.
class HostBoundStore extends FileSessionStore {
  constructor(root, boundChatId, expectedRevision, continuationId) {
    super(root); this.boundChatId = boundChatId; this.expectedRevision = expectedRevision; this.continuationId = continuationId;
  }
  change(chatId, update, options) {
    return super.change(chatId, record => {
      requireState(chatId === this.boundChatId && record.id === chatId, 'wrong_host_session', 'Wrong host session.');
      requireState(record.adapter.revision === this.expectedRevision, 'stale_host_revision', 'Reload the current host context before writing.');
      if (this.continuationId !== undefined) requireState(record.adapter.continuation?.id === this.continuationId &&
        record.adapter.continuation?.after === record.messages.at(-1)?.id,
      'stale_continuation', 'This continuation no longer owns the current unanswered reaction.');
      return update(record);
    }, options);
  }
}

export function hostContext(adapter, chatId) {
  const view = adapter.view(chatId);
  const record = adapter.store.read(chatId);
  // Content-only host projection, not a fabricated provider/SDK wire message.
  // Commitments in authored tool arguments remain available to the teacher;
  // UI-only toolResult.details and provider credentials/metadata are excluded.
  const messages = adapter.context(chatId).map(message => message.role === 'user'
    ? { role: 'user', content: message.content }
    : message.role === 'assistant'
      ? { role: 'assistant', content: message.content }
      : { role: 'toolResult', toolCallId: message.toolCallId, toolName: message.toolName,
        content: message.content, isError: message.isError });
  const context = { chatId, title: record.title, goal: record.adapter.goal, revision: view.revision,
    phase: view.phase, assessment: view.assessment, plan: view.plan,
    pendingQuestion: view.question ? { toolCallId: view.question.toolCallId, nodeId: view.question.nodeId,
      type: view.question.questionType } : null,
    continuationOwed: view.continuationOwed, continuation: view.continuation, messages };
  const serialized = JSON.stringify(context);
  requireState(Buffer.byteLength(serialized) <= 262144, 'host_context_too_large', 'Context exceeds 256 KiB; do not silently truncate it.');
  return { ok: true, context, contextSha256: createHash('sha256').update(serialized).digest('hex'),
    scope: 'existing host reads this JSON as task context; no provider invocation or SDK metadata synthesized' };
}

export function executeHostCommand(root, chatId, command) {
  const plain = new TeachingAdapter(root);
  let result;
  if (command?.op === 'context') {
    fields(command, ['op']); return hostContext(plain, chatId);
  }
  if (command?.op === 'continue') {
    fields(command, ['op']);
    result = plain.input({ chatId, input: { type: 'continue' } });
  } else {
    revision(command?.expectedRevision); authorship(command?.authorship);
    const adapter = new TeachingAdapter(root);
    adapter.store = new HostBoundStore(root, chatId, command.expectedRevision,
      ['teach', 'reply'].includes(command.op) ? command.continuationId : undefined);
    if (command.op === 'teach') {
      fields(command, ['op', 'expectedRevision', 'continuationId', 'authorship', 'nodeId', 'predictionCallId', 'text']);
      requireState(typeof command.continuationId === 'string', 'stale_continuation', 'Claim the current reaction first.');
      result = { ok: true, view: adapter.teachStep({ chatId, nodeId: command.nodeId,
        predictionCallId: command.predictionCallId, text: command.text }) };
    } else if (command.op === 'question') {
      fields(command, ['op', 'expectedRevision', 'authorship', 'toolCallId', 'name', 'input']);
      requireState(['quiz', 'explain'].includes(command.name), 'unsupported_host_tool', 'Use a teaching quiz or explain question.');
      result = { ok: true, view: adapter.tool({ chatId, toolCallId: command.toolCallId, name: command.name, input: command.input }) };
    } else if (command.op === 'reply') {
      fields(command, ['op', 'expectedRevision', 'continuationId', 'authorship', 'afterToolCallId', 'text']);
      requireState(typeof command.continuationId === 'string', 'stale_continuation', 'Claim the current reaction first.');
      requireState(typeof command.text === 'string' && command.text.trim().length > 0 && command.text.length <= 16000,
        'invalid_host_command', 'Reply must be non-empty text of at most 16000 characters.');
      adapter.store.change(chatId, record => {
        const last = record.messages.at(-1);
        requireState(last?.role === 'toolResult' && last.toolCallId === command.afterToolCallId &&
          record.adapter.questions[command.afterToolCallId]?.questionType === 'check',
        'wrong_feedback_target', 'A reply here reacts to the current answered check; predictions use teach.');
        record.messages.push({ id: `msg_${randomUUID()}`, role: 'assistant',
          content: [{ type: 'text', text: command.text }], timestamp: Date.now() });
        record.adapter.continuation = null;
        return { record, result: { ok: true } };
      });
      result = { ok: true, view: adapter.view(chatId) };
    } else {
      requireState(false, 'unsupported_host_command', 'Unsupported host operation.');
    }
  }
  fs.appendFileSync(path.join(root, 'host-actions.jsonl'), JSON.stringify({ at: new Date().toISOString(),
    op: command.op, authorship: command.authorship, revision: result.view.revision,
    continuationId: result.continuation?.id, toolCallId: command.toolCallId,
    evidenceScope: 'local host command; authorship is caller-declared and requires host-turn correlation' }) + '\n');
  return { ...result, view: inlineView(plain, chatId) };
}
