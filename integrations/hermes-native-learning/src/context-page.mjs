// SPDX-License-Identifier: AGPL-3.0-only
// Lossless teacher-context retrieval after host compaction; never a summary/model.
import { createHash } from 'node:crypto';
import { LessonJobs } from './jobs.mjs';
import { TeachingAdapter } from './adapter.mjs';
import { PracticeAdapter } from './practice-state.mjs';
import { requireState } from './store.mjs';
export function teacherContextPage(binding,{offset,limit=30,expectedRevision}={}) {
  const adapter=binding.kind==='practice'?new PracticeAdapter(binding.root):new TeachingAdapter(binding.root);
  const record=adapter.store.read(binding.chatId),total=record.messages.length;
  requireState(Number.isSafeInteger(limit)&&limit>=1&&limit<=100,'invalid_context_page','Use1–100messages per context page.');
  const explicitOffset=offset!==undefined;
  requireState(!explicitOffset||Number.isSafeInteger(expectedRevision),'stale_host_revision','Explicit history navigation requires its captured revision.');
  requireState(expectedRevision===undefined||expectedRevision===record.adapter.revision,'stale_host_revision','Lesson changed; reopen current state before continuing history retrieval.');
  offset=offset??Math.max(0,total-limit);
  requireState(Number.isSafeInteger(offset)&&offset>=0&&offset<=total,'invalid_context_page','Context offset is outside this saved transcript.');
  const view=binding.kind==='practice'?adapter.practiceView(binding.chatId):adapter.view(binding.chatId);
  requireState(view.revision===record.adapter.revision,'concurrent_state_change','Lesson changed during context retrieval; no mixed revision returned.');
  const pendingId=view.question?.toolCallId??view.activeProblem?.toolCallId;
  const pendingToolCall=pendingId?record.messages.filter(message=>message.role==='assistant')
    .flatMap(message=>message.content).find(block=>block.type==='toolCall'&&block.id===pendingId):null;
  const messages=record.messages.slice(offset,offset+limit).map(message=>({
    id:message.id,role:message.role,content:message.role==='assistant'&&Array.isArray(message.content)
      ? message.content.filter(block=>block.type==='text'||block.type==='toolCall') : message.content,
    ...(message.role==='toolResult'?{toolCallId:message.toolCallId,toolName:message.toolName,isError:message.isError}:{}),
    ...(message.role==='custom'?{customType:message.customType}:{}),
  }));
  const context={chatId:binding.chatId,kind:binding.kind,title:record.title,goal:record.adapter.goal,revision:record.adapter.revision,
    phase:view.phase,assessment:view.assessment,plan:view.plan,pendingToolCall,
    continuationOwed:view.continuationOwed,continuation:view.continuation,
    activeProblemId:view.activeProblem?.toolCallId,nextAllowed:view.nextAllowed,
    page:{offset,limit,total,previousOffset:offset>0?Math.max(0,offset-limit):null,nextOffset:offset+messages.length<total?offset+messages.length:null},messages,
    ...(binding.jobRoot?{jobs:new LessonJobs(binding).context()}:{})};
  const bytes=JSON.stringify(context);
  requireState(Buffer.byteLength(bytes)<=262144,'host_context_too_large','Page exceeds256KiB; request fewer messages, never silently truncate.');
  return{ok:true,context,contextSha256:createHash('sha256').update(bytes).digest('hex'),
    scope:'Teacher-only exact saved content including active commitments. Not a learner projection, fabricated summary or model invocation.'};
}
