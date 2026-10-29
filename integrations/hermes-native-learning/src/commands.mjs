// SPDX-License-Identifier: AGPL-3.0-only
// Existing agent is the teacher. This module is only the original state/tool lane.
import { TeachingAdapter } from './adapter.mjs';
import { PracticeAdapter } from './practice-state.mjs';
import { requireState } from './store.mjs';
import { randomUUID } from 'node:crypto';
import { learningWorkflow } from './workflow.mjs';
import { readNativePropositions } from './propositions.mjs';
import { LessonKnowledge } from './knowledge.mjs';
import { teacherContextPage } from './context-page.mjs';
import { materialCommand } from './materials.mjs';
import { MaterialImports } from './imports.mjs';
import { LessonJobs } from './jobs.mjs';
import { executeHostCommand, hostContext } from './inline/host/host-session.mjs';
import { RevisionBoundStore, readNativeView, executeNativeEnvelope, writeNativeSnapshot } from './inline/host/native-session.mjs';
const object = value => value && typeof value === 'object' && !Array.isArray(value);
function fields(command, keys) { requireState(object(command) && Object.keys(command).every(k => keys.includes(k)), 'invalid_command', 'Unknown command field.'); }
const adapterFor = b => b.kind === 'practice' ? new PracticeAdapter(b.root,
  {graphNodes:b.knowledgeRoot?()=>new LessonKnowledge(b.knowledgeRoot).graph().nodes:
    b.graphRoot?()=>readNativePropositions(b.graphRoot).nodes:undefined}) : new TeachingAdapter(b.root);
function guarded(b, command) {
  requireState(Number.isSafeInteger(command.expectedRevision) && command.expectedRevision >= 0 &&
    ['host-agent','synthetic-fixture'].includes(command.authorship), 'invalid_command', 'Expected revision and declared authorship required.');
  const adapter = adapterFor(b); adapter.store = new RevisionBoundStore(b.root, b.chatId, command.expectedRevision); return adapter;
}
export function executeLearningCommand(binding, command) {
  requireState(object(command), 'invalid_command', 'One JSON command required.');
  requireState(command.chatId === binding.chatId, 'wrong_host_session', 'Command targets another configured lesson.');
  if(command.op==='material') {
    const allowed={list:[],attach:['materialId','expectedRevision','authorship'],read:['materialId','offset','length','sourceSha256']};
    requireState(Object.hasOwn(allowed,command.action),'unsupported_command','Use list, attach or read for an enrolled material.');
    fields(command,['op','chatId','action',...allowed[command.action]]);return materialCommand(binding,command);
  }
  if(command.op==='import') {
    const allowed={prepare:['budget'],findings:['part','findings','authorship'],audit:[],merge:['part','verdicts','graphRevision','authorship'],abort:[]};
    requireState(Object.hasOwn(allowed,command.action),'unsupported_command','Use the explicit notes import stages.');
    fields(command,['op','chatId','action','importId','materialId',...allowed[command.action]]);return new MaterialImports(binding).execute(command);
  }
  if(command.op==='job') {
    const allowed={list:['offset','limit'],request:['kind','toolCallId','expectedRevision','input'],dispatch:[],control:['control','message'],
      admit:['receipt'],progress:['delegationId','activity','usage'],complete:['delegationId','result','verification','resultFile','resultSha256','error','authorship','completionReceipt'],ack:['delegationId','afterMessageId'],'report-ack':['reportId','afterMessageId']};
    requireState(Object.hasOwn(allowed,command.action),'unsupported_command','Use the supported job record/control stages.');
    fields(command,['op','chatId','action','jobId',...allowed[command.action]]);return new LessonJobs(binding).execute(command);
  }
  if(command.op==='context-page') {
    fields(command,['op','chatId','offset','limit','expectedRevision']);
    return teacherContextPage(binding,command);
  }
  if(command.op==='knowledge') {
    requireState(binding.knowledgeRoot,'knowledge_unavailable','Knowledge requires an explicitly configured private directory; no default graph access.');
    const knowledge=new LessonKnowledge(binding.knowledgeRoot),lesson=adapterFor(binding).store.read(binding.chatId);
    if(command.action==='status'||command.action==='graph') {
      fields(command,['op','chatId','action',...(command.action==='graph'?['query','offset','limit','graphRevision']:[])]);
      const {query,offset,limit,graphRevision}=command;
      return{ok:true,...(command.action==='status'?knowledge.status(lesson):{graph:knowledge.query({query,offset,limit,graphRevision})}),scope:'Teacher proposition evidence, not learner mastery; no model invoked.'};
    }
    requireState(binding.kind==='teach','wrong_session_kind','Practice cannot extract or write graph evidence.');
    const allowed={prepare:['expectedRevision','budget'],findings:['batchId','findings','authorship'],audit:['batchId'],merge:['batchId','graphRevision','verdicts','authorship']};
    requireState(Object.hasOwn(allowed,command.action),'unsupported_command','Use prepare, findings, audit, merge, graph or status.');
    fields(command,['op','chatId','action',...allowed[command.action]]);
    const {op,chatId,action,...args}=command;
    return knowledge[action](lesson,{...args,ownerSessionId:binding.ownerSessionId});
  }
  let result;
  if (command.op === 'init') {
    fields(command, ['op','chatId','title','goal']);
    const adapter = adapterFor(binding);
    const input = {chatId:binding.chatId,title:command.title,goal:command.goal};
    result = {ok:true,view:binding.kind === 'practice' ? adapter.createPractice(input) : adapter.create(input)};
  } else if(command.op==='rename') {
    fields(command,['op','chatId','expectedRevision','authorship','title']);
    requireState(typeof command.title==='string'&&command.title.trim()&&command.title.length<=300,'invalid_title','Use a title of1–300characters.');
    const adapter=guarded(binding,command);
    adapter.store.change(binding.chatId,record=>{
      const title=command.title.trim(),changed=record.title!==title;record.title=title;
      return{record,result:{ok:true},changed};
    },{activity:false});
    result={ok:true,view:binding.kind==='practice'?adapter.practiceView(binding.chatId):adapter.view(binding.chatId)};
  } else if (command.op === 'view' || command.op === 'export') {
    fields(command, ['op','chatId']); result = {ok:true,view:readNativeView(binding,{includeAnswerHistory:true}).view};
  } else if (command.op === 'context') {
    fields(command,['op','chatId']);
    if (binding.kind === 'teach') {
      const response=hostContext(adapterFor(binding),binding.chatId);
      const jobs=binding.jobRoot?new LessonJobs(binding).context():[];
      requireState(Buffer.byteLength(JSON.stringify({...response,jobs}))<=262144,'host_context_too_large','Teacher context plus queued work exceeds256KiB; retrieve bounded context/job pages.');
      return {...response,jobs,workflow:learningWorkflow('teach',readNativeView(binding).view,response.context.messages)};
    }
    const context = {chatId:binding.chatId,kind:'practice',view:readNativeView(binding).view,messages:adapterFor(binding).context(binding.chatId),
      propositions:binding.knowledgeRoot?{nodes:new LessonKnowledge(binding.knowledgeRoot).graph().nodes}:
        binding.graphRoot?readNativePropositions(binding.graphRoot):null,jobs:binding.jobRoot?new LessonJobs(binding).context():[]};
    requireState(Buffer.byteLength(JSON.stringify(context)) <= 262144,'context_too_large','Teacher context exceeds256KiB; no silent truncation.');
    return {ok:true,context,workflow:learningWorkflow('practice',context.view,context.messages),scope:'teacher-only commitment context; no model invoked'};
  } else if (command.op === 'learner') {
    fields(command,['op','chatId','envelope']);
    result = executeNativeEnvelope(binding,binding.ownerSessionId,command.envelope);
  } else if (command.op === 'practice-discuss') {
    fields(command,['op','chatId','expectedRevision','authorship','afterMessageId','text']);
    requireState(binding.kind==='practice','wrong_session_kind','Practice discussion requires a practice session.');
    requireState(typeof command.text==='string' && command.text.trim() && command.text.length<=16000,'invalid_command','Bounded discussion text required.');
    const adapter=guarded(binding,command);
    adapter.store.change(binding.chatId,record=>{
      const current=adapter.practiceView(binding.chatId),last=record.messages.at(-1);
      requireState(!current.activeProblem && current.conclusion && !current.nextAllowed && last?.role==='user' && last.id===command.afterMessageId,
        'stale_practice_reaction','Discussion must answer the current pause question; it cannot advance the problem.');
      record.messages.push({id:`msg_${randomUUID()}`,role:'assistant',timestamp:Date.now(),content:[{type:'text',text:command.text}]});
      return{record,result:{ok:true}};
    });
    result={ok:true,view:adapter.practiceView(binding.chatId),turnInstruction:'End this turn; a clarification is not permission to pose another problem.'};
  } else if (command.op === 'practice-reply') {
    fields(command,['op','chatId','expectedRevision','authorship','problemCallId','afterThinkingId','text']);
    requireState(binding.kind === 'practice','wrong_session_kind','Practice feedback requires a practice session.');
    requireState(typeof command.text === 'string' && command.text.trim() && command.text.length <= 16000,
      'invalid_command','Practice feedback must be non-empty text of at most16000 characters.');
    const adapter=guarded(binding,command);
    adapter.store.change(binding.chatId,record=>{
      const active=adapter.practiceView(binding.chatId).activeProblem,last=record.messages.at(-1);
      requireState(active?.toolCallId === command.problemCallId && last?.role === 'custom' &&
        last.customType === 'practice-thinking' && last.details.problemCallId === command.problemCallId &&
        last.id === command.afterThinkingId,'stale_practice_reaction','Feedback must answer the current unreplied thinking entry.');
      record.messages.push({id:`msg_${randomUUID()}`,role:'assistant',timestamp:Date.now(),content:[{type:'text',text:command.text}]});
      return{record,result:{ok:true}};
    });
    result={ok:true,view:adapter.practiceView(binding.chatId),turnInstruction:'End this turn; wait for real learner thinking.'};
  } else if (command.op === 'tool') {
    fields(command,['op','chatId','expectedRevision','authorship','toolCallId','name','input']);
    const adapter = guarded(binding,command);
    const allowed = binding.kind === 'practice' ? ['problem','conclude'] : ['ask','probe','recall','probe_done','plan_init','quiz','explain'];
    requireState(allowed.includes(command.name),'unsupported_tool','Tool is outside this learning mode.');
    const args={chatId:binding.chatId,toolCallId:command.toolCallId,name:command.name,input:command.input};
    result={ok:true,view:binding.kind === 'practice'?adapter.practiceTool(args):adapter.tool(args),
      turnInstruction:binding.kind === 'practice'?'End this turn; wait for the learner thinking or explicit next.':undefined};
  } else {
    requireState(binding.kind === 'teach' && ['continue','teach','reply','question'].includes(command.op),'unsupported_command','Unsupported learning command.');
    const {chatId,...existing}=command;
    result=executeHostCommand(binding.root,binding.chatId,existing);
  }
  let snapshot;
  try {snapshot=writeNativeSnapshot(binding,binding.output,{includeAnswerHistory:true});}
  catch(error) {
    // Presentation happens AFTER the authoritative operation. Never report a
    // committed mutation as unsaved merely because its export is unavailable.
    const response={...result,operationComplete:true,persisted:!['view','export'].includes(command.op),
      authoritativeRevision:result.view?.revision??null,snapshot:null,directive:null,
      presentation:{available:false,code:error.code??'snapshot_failed'},
      instruction:'The operation completed; the native export is unavailable. Read current state/context-page. Do not repeat a saved mutation.',
      scope:'Authoritative state operation and presentation outcome are separate; no model invoked.'};
    if(Buffer.byteLength(JSON.stringify(response))>262144)delete response.view;
    return response;
  }
  return {...result,snapshot,directive:`::lh-lesson{lesson="${binding.chatId}" snapshot="${snapshot.viewFile.split(/[\\/]/).at(-1)}"}`,
    scope:'state/tool operation only; delivery and genuine model teaching need host correlation'};
}
