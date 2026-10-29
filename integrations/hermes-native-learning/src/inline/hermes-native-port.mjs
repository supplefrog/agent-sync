// SPDX-License-Identifier: AGPL-3.0-only
// Thin ports for the selected Hermes SDK; no backend/session creation or model.
import { mountInline } from './inline-client.mjs';
const bytes = value => new TextEncoder().encode(JSON.stringify(value)).length;
function requirePort(ok, message) { if (!ok) throw new Error(message); }
export function createHermesLessonPort(ownerSessionId, view, { composer, storage }) {
  requirePort(typeof ownerSessionId === 'string' && ownerSessionId.length > 0 && ownerSessionId.length <= 300 && ownerSessionId === ownerSessionId.trim() && ownerSessionId !== 'new', 'An exact owning Hermes session is required.');
  requirePort(typeof view.chatId === 'string' && view.chatId.length > 0 && view.chatId.length <= 100 && Number.isSafeInteger(view.revision) && view.revision >= 0, 'Invalid bound lesson view.');
  requirePort(typeof composer?.submit === 'function' && ['get','set','remove'].every(k => typeof storage?.[k] === 'function'), 'Supported Hermes composer/storage ports are unavailable.');
  const kind = view.kind === 'practice' ? 'practice' : 'teach';
  const key = kind === 'practice' ? `${view.chatId}:practice:${view.activeProblem?.toolCallId ?? 'between'}`
    : `${view.chatId}:${view.question?.toolCallId ?? 'idle'}`;
  const slot = 'draft:v1:' + JSON.stringify([ownerSessionId, view.chatId, key]);
  function checkKey(requested) { requirePort(requested === key, 'Draft key does not belong to this owner/question.'); }
  const drafts = {
    read(requested) {
      checkKey(requested); const saved = storage.get(slot, null);
      if (!saved || saved.owner !== ownerSessionId || saved.chatId !== view.chatId || saved.key !== key ||
          !Number.isSafeInteger(saved.baseRevision) || saved.baseRevision > view.revision || bytes(saved) > 16384) return null;
      // Only an explicitly submitted draft and a NEW matching authoritative
      // entry after its captured baseline can clear. Old equal text cannot.
      const submitted = saved.submission;
      if (kind === 'practice' && submitted && submitted.draftId === saved.draftId &&
          submitted.text === saved.payload?.text && Array.isArray(submitted.baselineIds) &&
          view.thinkingEntries?.some(entry => !submitted.baselineIds.includes(entry.id) && entry.text === submitted.text)) {
        storage.remove(slot); return null;
      }
      return saved.payload;
    },
    write(requested, payload) {
      checkKey(requested);
      const previous = storage.get(slot, null);
      requirePort(!previous || previous.baseRevision <= view.revision, 'A newer card owns this draft; keep this card open.');
      const sameDraft = previous?.key === key && (kind === 'practice'
        ? previous.payload?.text === payload?.text : JSON.stringify(previous.payload) === JSON.stringify(payload));
      const saved = { owner: ownerSessionId, chatId: view.chatId, key, baseRevision: view.revision, payload,
        draftId: sameDraft && previous.draftId ? previous.draftId : globalThis.crypto.randomUUID(), submission: sameDraft ? previous.submission : null };
      requirePort(bytes(saved) <= 16384, 'Native draft exceeds the 16 KiB task limit; keep the card open.');
      storage.set(slot, saved);
      requirePort(JSON.stringify(storage.get(slot, null)) === JSON.stringify(saved), 'Hermes did not retain this draft; keep the card open.');
    },
    remove(requested) { checkKey(requested); storage.remove(slot); },
  };
  return { drafts, async send(action) {
    requirePort(action?.chatId === view.chatId && (kind === 'practice' ? ['practice-input','resume','job-error'] : ['answer','approve','resume','job-error']).includes(action.type), 'Action does not belong to this bound lesson.');
    const envelope = { v: 1, ownerSessionId, chatId: view.chatId, kind, expectedRevision: view.revision, action };
    const prompt = 'lh.native ' + JSON.stringify(envelope);
    requirePort(new TextEncoder().encode(prompt).length <= 65536, 'Native input exceeds 64 KiB; nothing was truncated or sent.');
    let submission = null;
    if (kind === 'practice' && action.type === 'practice-input' && action.input?.type === 'thinking') {
      const saved = storage.get(slot, null);
      requirePort(!saved || saved.baseRevision <= view.revision, 'A newer card owns this draft; nothing was sent.');
      if (saved?.draftId && Number.isSafeInteger(saved.baseRevision) && saved.payload?.text === action.input.text && Array.isArray(view.thinkingEntries)) {
        submission = { before: JSON.stringify(saved), draftId: saved.draftId, text: action.input.text,
          baselineIds: view.thinkingEntries.map(entry => entry.id) };
      }
    }
    // Exact session address; NEVER null/active, core iframe send or another host.
    requirePort(composer.submit(ownerSessionId, prompt) === true, 'The owning Hermes composer is unavailable; draft retained.');
    if (submission) {
      // Never adopt a newer equal-text draft published during dispatch.
      // Metadata failure after delivery preserves the draft and is not a
      // claimed delivery failure. SDK storage has no cross-window atomic CAS.
      try {
        const current = storage.get(slot, null);
        if (current?.baseRevision <= view.revision && JSON.stringify(current) === submission.before) {
          const { before, ...identity } = submission;
          const marked = { ...current, submission: identity };
          if (bytes(marked) <= 16384) storage.set(slot, marked);
        }
      } catch { /* retain without auto-clear */ }
    }
    return { delivered: true, ownerSessionId }; // Delivery is NOT persisted-state proof.
  } };
}
export function mountHermesLearning(root, view, props, { host, ctx }) {
  const ports = createHermesLessonPort(props.sessionId, view, { composer: host.composer, storage: ctx.storage });
  return mountInline(root, view, ports);
}
