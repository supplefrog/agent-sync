// SPDX-License-Identifier: AGPL-3.0-only
// Shared projection/draft identity, not caller authorization or a host transport.
export const lessonKind = view => view.kind === 'practice' ? 'practice' : 'teach';
export const lessonDraftKey = view => lessonKind(view) === 'practice'
  ? `${view.chatId}:practice:${view.activeProblem?.toolCallId ?? 'between'}`
  : `${view.chatId}:${view.question?.toolCallId ?? 'idle'}`;
export function currentProjectionName(chatId) {
  if (typeof chatId !== 'string' || !/^[A-Za-z0-9_-]{1,80}$/.test(chatId)) throw new Error('Invalid lesson identity.');
  return `current-${chatId}.json`;
}
export function validateLessonView(view, {chatId, kind, minimumRevision = 0}) {
  if (!view || view.chatId !== chatId || lessonKind(view) !== kind ||
      (view.kind !== undefined && !['teach','practice'].includes(view.kind)) ||
      !Number.isSafeInteger(view.revision) || view.revision < minimumRevision)
    throw new Error('Refusing a different lesson, mode or older saved revision.');
  if (view.question && ['committedAnswer','correctIndices','explanation'].some(k => k in view.question))
    throw new Error('An active question exposed its commitment.');
  if (view.activeProblem && Object.keys(view.activeProblem).some(k => !['toolCallId','statement'].includes(k)))
    throw new Error('An active problem exposed teacher-only fields.');
  return view;
}
export function parseCurrentProjection(text, binding, minimumRevision = 0) {
  if (typeof text !== 'string' || new TextEncoder().encode(text).length > 4096)
    throw new Error('Current lesson index is unavailable or oversized.');
  const index = JSON.parse(text);
  const match=/^(teach|practice)-r([0-9]+)-([a-f0-9]{64})\.json$/.exec(index?.snapshot??'');
  if (!index || index.v !== 1 || index.chatId !== binding.chatId || index.kind !== binding.kind ||
      Object.keys(index).some(k => !['v','chatId','kind','revision','snapshot'].includes(k)) ||
      !Number.isSafeInteger(index.revision) || index.revision < minimumRevision ||
      typeof index.snapshot !== 'string' || !match || match[1] !== binding.kind || match[2] !== String(index.revision))
    throw new Error('Current lesson index differs from this lesson or saved revision.');
  return index;
}
export async function loadCurrentProjection(files, binding, minimumRevision, verifyBytes) {
  const result = await files.readText(binding.folder, currentProjectionName(binding.chatId));
  if (!result.ok) throw new Error('Current saved lesson unavailable. Ask the owning teacher to export it; no action was sent.');
  const index = parseCurrentProjection(result.text, binding, minimumRevision);
  const snapshot = await files.readText(binding.folder, index.snapshot);
  if (!snapshot.ok || typeof snapshot.text !== 'string' || new TextEncoder().encode(snapshot.text).length > 262144)
    throw new Error('The current redacted lesson export is unavailable.');
  await verifyBytes(index.snapshot, snapshot.text);
  const view = validateLessonView(JSON.parse(snapshot.text), {...binding, minimumRevision:index.revision});
  if (view.revision !== index.revision) throw new Error('Current index and snapshot revisions differ.');
  return view;
}
