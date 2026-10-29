// SPDX-License-Identifier: AGPL-3.0-only
// Current-store file/tool seam. No model, server, plugin activation or seeding.
import fs from 'node:fs';
import path from 'node:path';
import { createHash, randomUUID } from 'node:crypto';
import { TeachingAdapter } from '../../adapter.mjs';
import { PracticeAdapter } from '../../practice-state.mjs';
import { FileSessionStore, requireState } from '../../store.mjs';
import { inlineView, buildInline } from '../build-inline.mjs';
import { dispatchInline } from '../host-actions.mjs';
import { LessonKnowledge } from '../../knowledge.mjs';
import { LessonJobs, jobArtifactDescriptors, publishJobAssets } from '../../jobs.mjs';

const digest = bytes => createHash('sha256').update(bytes).digest('hex');
const object = value => value && typeof value === 'object' && !Array.isArray(value);
function adapterFor(session) {
  requireState(['teach','practice'].includes(session?.kind), 'wrong_session_kind', 'Use a bound teaching/practice session.');
  return session.kind === 'practice' ? new PracticeAdapter(session.root) : new TeachingAdapter(session.root);
}
function viewOf(adapter, session) {
  if (session.kind !== 'practice') return inlineView(adapter, session.chatId);
  const view = { ...adapter.practiceView(session.chatId), kind: 'practice' };
  view.thinkingEntries = adapter.context(session.chatId).filter(message => message.role === 'custom' &&
    message.customType === 'practice-thinking' && message.details.problemCallId === view.activeProblem?.toolCallId)
    .map(message => ({ id: message.id, text: message.details.text }));
  return view;
}
export function readNativeView(session, { includeAnswerHistory = false } = {}) {
  const adapter = adapterFor(session), file = adapter.store.file(session.chatId);
  const before = digest(fs.readFileSync(file));
  const view = viewOf(adapter, session);
  const record=adapter.store.read(session.chatId);
  view.materials=record.adapter.materials??[];
  if(session.jobRoot)view.jobs=jobArtifactDescriptors(new LessonJobs(session));
  if(session.knowledgeRoot)view.knowledge=new LessonKnowledge(session.knowledgeRoot).lessonView(adapter.store.read(session.chatId));
  if (session.kind === 'teach' && !includeAnswerHistory) view.answers = [];
  requireState(digest(fs.readFileSync(file)) === before, 'concurrent_state_change', 'Read changed; reload rather than export mixed state.');
  return { view, sourceSha256: before };
}
export class RevisionBoundStore extends FileSessionStore {
  constructor(root, chatId, expectedRevision) { super(root); this.chatId = chatId; this.expectedRevision = expectedRevision; }
  change(chatId, update, options) {
    return super.change(chatId, record => {
      requireState(chatId === this.chatId && record.adapter.revision === this.expectedRevision,
        'stale_native_revision', 'Reload this lesson before saving an obsolete action.');
      return update(record);
    }, options);
  }
}
export function executeNativeLearnerAction(session, action, { expectedRevision } = {}) {
  requireState(object(action) && action.chatId === session.chatId, 'wrong_host_session', 'Action targets another lesson.');
  const adapter = adapterFor(session);
  if(action.type==='job-error') {
    requireState(Object.keys(action).every(key=>['type','chatId','jobId','artifactSha256','error'].includes(key)), 'invalid_bridge_input','Unknown artifact report field.');
    requireState(adapter.store.read(session.chatId).adapter.revision===expectedRevision,'stale_native_revision','Use the current lesson before reporting an artifact.');
    return {...new LessonJobs(session).report(action),view:readNativeView(session).view};
  }
  if (action.type !== 'resume' && expectedRevision !== undefined) {
    requireState(Number.isSafeInteger(expectedRevision) && expectedRevision >= 0, 'invalid_revision', 'Expected revision required.');
    adapter.store = new RevisionBoundStore(session.root, session.chatId, expectedRevision);
  }
  let result;
  if (session.kind === 'practice') {
    requireState(Object.keys(action).every(k => ['type','chatId','input'].includes(k)), 'invalid_bridge_input', 'Unknown practice field.');
    if (action.type === 'resume' && action.input === undefined) result = { ok: true, loaded: true };
    else {
      requireState(action.type === 'practice-input', 'unsupported_action', 'Use practice thinking/explicit next/resume.');
      adapter.practiceInput({ chatId: session.chatId, input: action.input });
      result = { ok: true, persisted: true };
    }
  } else result = dispatchInline(adapter, session.chatId, action);
  return { ...result, view: viewOf(adapter, session) };
}
// actualOwner is a TRUSTED caller parameter from the admitted native session,
// not the message's self-reported owner or process-global HERMES_SESSION_ID.
// This local function is not an authenticated network endpoint.
export function executeNativeEnvelope(binding, actualOwner, envelope) {
  requireState(object(envelope) && Object.keys(envelope).every(k =>
    ['v','ownerSessionId','kind','chatId','expectedRevision','action'].includes(k)), 'invalid_native_envelope', 'Unknown native envelope field.');
  requireState(typeof actualOwner === 'string' && actualOwner.length > 0 && actualOwner !== 'new' &&
    binding.ownerSessionId === actualOwner && envelope.ownerSessionId === actualOwner,
    'wrong_native_owner', 'Native caller must own this explicitly bound lesson.');
  requireState(envelope.v === 1 && envelope.kind === binding.kind && envelope.chatId === binding.chatId &&
    envelope.action?.chatId === binding.chatId, 'wrong_host_session', 'Native lesson binding differs.');
  requireState(Number.isSafeInteger(envelope.expectedRevision) && envelope.expectedRevision >= 0, 'invalid_revision', 'Native revision required.');
  return executeNativeLearnerAction(binding, envelope.action, { expectedRevision: envelope.expectedRevision });
}
export function writeNativeSnapshot(session, outputDirectory, { includeAnswerHistory = false } = {}) {
  const snapshot = readNativeView(session, { includeAnswerHistory });
  if(session.jobRoot)publishJobAssets(new LessonJobs(session),outputDirectory);
  const viewBytes = Buffer.from(JSON.stringify(snapshot.view), 'utf8');
  requireState(viewBytes.length<=262144,'view_too_large','Native view exceeds its256KiB reader limit; no unusable snapshot is published.');
  const projectionSha256 = digest(viewBytes);
  fs.mkdirSync(outputDirectory, { recursive: true });
  const stem = `${session.kind}-r${snapshot.view.revision}-${projectionSha256}`;
  const html = path.join(outputDirectory, stem + '.html');
  const json = path.join(outputDirectory, stem + '.json');
  // Generate without modifying an existing identity. The existing renderer is
  // still used; no old directive may silently change under the same basename.
  const temporaryHtml = path.join(outputDirectory, '.' + randomUUID() + '.html.pending');
  buildInline(snapshot.view, temporaryHtml);
  try {
    publishIdenticalOrNew(html, fs.readFileSync(temporaryHtml));
    publishIdenticalOrNew(json, viewBytes);
  } finally { fs.unlinkSync(temporaryHtml); }
  requireState(digest(fs.readFileSync(adapterFor(session).store.file(session.chatId))) === snapshot.sourceSha256,
    'concurrent_state_change', 'State changed during export; do not publish this snapshot.');
  return { output: html, viewFile: json, revision: snapshot.view.revision,
    pending: snapshot.view.question?.toolCallId ?? snapshot.view.activeProblem?.toolCallId ?? null,
    sourceSha256: snapshot.sourceSha256, projectionSha256, readOnly: true, priorAnswersIncluded: includeAnswerHistory };
}
function publishIdenticalOrNew(file, bytes) {
  try { fs.writeFileSync(file, bytes, { flag: 'wx' }); }
  catch (error) {
    if (error.code !== 'EEXIST') throw error;
    requireState(fs.readFileSync(file).equals(bytes), 'snapshot_identity_conflict', 'Existing snapshot bytes differ; never overwrite this identity.');
  }
}
