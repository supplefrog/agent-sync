// SPDX-License-Identifier: AGPL-3.0-only
// Practice domain port over the SAME adapter/store, not an agent/runtime loop.
import { TeachingAdapter } from './adapter.mjs';
import { requireState } from './store.mjs';
import { parseChatInput } from './vendor/runtime/input-parser.ts';
import { validDrawing, drawingText } from './drawing.mjs';
import { normalizeCoding, publicCoding, validateCodingText } from './coding.mjs';
import { newestWithin, practiceAttempts } from './practice-history.mjs';
import { resolveTargetId } from './vendor/runtime/target-pure.ts';
import { activeProblemOf, modelSolutionForConclude, newThinkingMessage, newNextMessage,
  newMessageId, CONCLUDE_ACK_TEXT } from './vendor/runtime/practice-pure.ts';
const text = value => typeof value === 'string' && value.trim().length > 0 && value.length <= 16000;
const keys = (value, names) => value && typeof value === 'object' && !Array.isArray(value) && Object.keys(value).every(key=>names.includes(key));
function appendTool(record, toolCallId, name, input, ack) {
  requireState(typeof toolCallId === 'string' && /^[A-Za-z0-9_-]{1,100}$/.test(toolCallId), 'invalid_call_id', 'Stable call id required.');
  requireState(!record.messages.some(m=>m.role==='assistant' && m.content.some(b=>b.type==='toolCall' && b.id===toolCallId)), 'replayed_call', 'Call already recorded.');
  record.messages.push({id:newMessageId(),role:'assistant',timestamp:Date.now(),content:[{type:'toolCall',id:toolCallId,name,arguments:structuredClone(input)}]},
    {id:newMessageId(),role:'toolResult',toolCallId,toolName:name,timestamp:Date.now(),content:[{type:'text',text:ack}],details:null,isError:false});
}
export class PracticeAdapter extends TeachingAdapter {
  constructor(root,{graphNodes}={}) {super(root);this.graphNodes=graphNodes;}
  createPractice(input) {
    super.create(input);
    this.store.change(input.chatId, record=>{record.kind='practice';record.adapter.practiceNextAllowed=true;return{record,result:{ok:true}};});
    return this.practiceView(input.chatId);
  }
  practiceTool({chatId,toolCallId,name,input}) {
    this.store.change(chatId, record=>{
      requireState(record.kind==='practice','wrong_session_kind','Practice session required.');
      const active=activeProblemOf(record.messages);
      if(name==='problem') {
        requireState(!active && record.adapter.practiceNextAllowed===true,'practice_next_required','One active problem; after conclusion wait for explicit next.');
        requireState(keys(input,['statement','mode','modelSolution','target','coding']) && text(input.statement) && text(input.modelSolution) && ['recall','discrimination','composition'].includes(input.mode),'invalid_problem','Valid statement, mode and committed modelSolution required.');
        requireState(input.target===undefined||(Array.isArray(input.target)&&input.target.every(t=>typeof t==='string')),
          'invalid_problem','Practice targets must be proposition IDs or names.');
        const normalized={...input};
        if(input.coding!==undefined) {
          normalized.coding=normalizeCoding(input.coding);
          requireState(normalized.coding.solution===input.modelSolution,'invalid_coding_spec','Use the same committed coding solution in both fields.');
        }
        if(!input.target?.length)delete normalized.target;
        else {
          requireState(typeof this.graphNodes==='function','graph_unavailable','Tagged practice requires an enrolled proposition source; omit target for topic practice.');
          const fresh=this.graphNodes();
          const canonical=input.target.map(t=>resolveTargetId(t,fresh));
          requireState(canonical.every(t=>t!==null),'unknown_proposition','Target is not a known proposition in the fresh source; do not substitute a plan node.');
          normalized.target=canonical;
        }
        appendTool(record,toolCallId,name,normalized,"Problem posed — the turn ends here; the learner's thinking traces and answer commits arrive as labeled messages.");
        record.adapter.practiceNextAllowed=false;
      } else if(name==='conclude') {
        requireState(active,'no_active_problem','No active practice problem.');
        requireState(keys(input,['outcome','verdict','rung','missClass','retest']) && ['solved','solvedWithHints','movedOn','surrendered'].includes(input.outcome) && text(input.verdict) && (input.rung===null || /^R[0-5]$/.test(input.rung)) && [null,'cue','discrimination','execution','careless','structural'].includes(input.missClass) && typeof input.retest==='boolean','invalid_conclusion','Use upstream conclude fields; never supply a replacement solution or author dismissed.');
        appendTool(record,toolCallId,name,input,CONCLUDE_ACK_TEXT);record.adapter.practiceNextAllowed=false;
      } else requireState(false,'unsupported_practice_tool','Use problem or conclude.');
      return{record,result:{ok:true}};
    });
    return this.practiceView(chatId);
  }
  practiceInput(envelope) {
    requireState(keys(envelope,['chatId','input']),'invalid_input','Use {chatId,input}.');
    const raw=envelope.input;
    requireState(raw?.drawing===undefined||raw.type==='thinking','invalid_drawing','Attach a drawing to an active practice response.');
    const codeOnly=raw?.type==='thinking'&&typeof raw.text==='string'&&!raw.text.trim()&&raw.code!==undefined;
    const input=codeOnly?{type:'thinking',problemCallId:raw.problemCallId,text:''}:parseChatInput(raw);
    this.store.change(envelope.chatId, record=>{
      requireState(record.kind==='practice','wrong_session_kind','Practice session required.');
      const active=activeProblemOf(record.messages);
      if(input.type==='thinking') {
        requireState(active&&active.toolCallId===input.problemCallId&&(codeOnly||text(input.text)),'stale_problem','Thinking must target the active problem.');
        const message = newThinkingMessage(input.problemCallId,input.text);
        if(active.input.coding) {
          const code=validateCodingText(raw.code);
          message.details.coding={language:active.input.coding.language,code,...(this.codingObservations?{observations:this.codingObservations}:{})};
          if(typeof message.content==='string')message.content+='\n\nExact learner code and recorded test observations: '+JSON.stringify(message.details.coding);
        } else requireState(raw.code===undefined,'invalid_coding_answer','Use ordinary thinking for this problem.');
        const drawing = envelope.input.drawing;
        requireState(drawing === undefined || validDrawing(drawing), 'invalid_drawing', 'The drawing is invalid or exceeds its size limit.');
        if (drawing) {
          message.details.drawing = structuredClone(drawing);
          if (typeof message.content === 'string') message.content += '\n\n' + drawingText(drawing, message.id);
        }
        record.messages.push(message);
      } else if(input.type==='next') {
        requireState(!active,'problem_active','Conclude the active problem first.');
        if(record.messages.at(-1)?.customType==='practice-next')return{record,result:{ok:true},changed:false};
        record.messages.push(newNextMessage());record.adapter.practiceNextAllowed=true;
      } else if(input.type==='text') {
        requireState(!active && record.adapter.practiceNextAllowed===false && text(input.text),
          'not_in_practice_pause','Between-problem questions require the concluded-problem pause. Explicit Next is a separate input.');
        record.messages.push({id:newMessageId(),role:'user',content:input.text,timestamp:Date.now()});
      } else requireState(false,'unsupported_practice_input','Use thinking, a pause question, or explicit next; no automatic answer inference.');
      return{record,result:{ok:true}};
    });
    return this.practiceView(envelope.chatId);
  }
  practiceView(chatId) {
    const record=this.store.read(chatId);requireState(record.kind==='practice','wrong_session_kind','Practice session required.');
    const active=activeProblemOf(record.messages);
    const conclude=record.messages.filter(m=>m.role==='assistant').flatMap(m=>m.content).filter(b=>b.type==='toolCall' && b.name==='conclude').at(-1);
    const concludeIndex=conclude ? record.messages.findIndex(m=>m.role==='assistant' && m.content.some(b=>b.type==='toolCall' && b.id===conclude.id)) : -1;
    const reviewed=conclude ? activeProblemOf(record.messages.slice(0,concludeIndex)) : null;
    const problemId=(active??reviewed)?.toolCallId;
    const problemIndex=record.messages.findIndex(m=>m.role==='assistant' && m.content.some(b=>b.type==='toolCall' && b.id===problemId));
    const feedback=problemIndex<0 ? [] : newestWithin(record.messages.slice(problemIndex+1,active?undefined:concludeIndex)
      .filter(m=>m.role==='assistant').flatMap(m=>m.content.filter(b=>b.type==='text').map(b=>({id:m.id,text:b.text}))),24*1024);
    const { rows, nextBefore }=practiceAttempts(record,problemId);
    const codingAttempts=rows.filter(row=>row.coding).map(row=>({id:row.id,...row.coding}));
    const discussion=active||concludeIndex<0?[]:newestWithin(record.messages.slice(concludeIndex+2).flatMap(m=>m.role==='user'?
      [{id:m.id,role:'user',text:m.content}]:m.role==='assistant'?m.content.filter(b=>b.type==='text').map(b=>({id:m.id,role:'assistant',text:b.text})):[]),24*1024);
    return{chatId,revision:record.adapter.revision,activeProblem:active ? {toolCallId:active.toolCallId,statement:active.input.statement,
      ...(active.input.coding?{coding:publicCoding(active.input.coding)}:{})} : null,
      feedback,discussion,thinking:rows.map(row=>row.text),
      thinkingEntries:active?rows.map(({id,text})=>({id,text})):[],
      drawings:rows.filter(row=>row.drawing).map(({id,drawing})=>({id,drawing})),
      ...(codingAttempts.length?{codingAttempts}:{}),
      ...(nextBefore?{earlierResponses:{problemId,before:nextBefore}}:{}),
      conclusion:conclude ? {...conclude.arguments,statement:reviewed?.input.statement,
        thinking:active?newestWithin(practiceAttempts(record,reviewed?.toolCallId).rows.map(row=>row.text),24*1024):rows.map(row=>row.text),
        ...(reviewed?.input.coding?{codingLanguage:reviewed.input.coding.language}:{}),
        modelSolution:modelSolutionForConclude(record.messages,conclude.id)} : null,
      nextAllowed:!active && record.adapter.practiceNextAllowed===true};
  }
}
