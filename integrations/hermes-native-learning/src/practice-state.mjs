// SPDX-License-Identifier: AGPL-3.0-only
// Practice domain port over the SAME adapter/store, not an agent/runtime loop.
import { TeachingAdapter } from './adapter.mjs';
import { requireState } from './store.mjs';
import { parseChatInput } from './vendor/runtime/input-parser.ts';
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
        requireState(keys(input,['statement','mode','modelSolution','target']) && text(input.statement) && text(input.modelSolution) && ['recall','discrimination','composition'].includes(input.mode),'invalid_problem','Valid statement, mode and committed modelSolution required.');
        requireState(input.target===undefined||(Array.isArray(input.target)&&input.target.every(t=>typeof t==='string')),
          'invalid_problem','Practice targets must be proposition IDs or names.');
        const normalized={...input};
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
    const input=parseChatInput(envelope.input);
    this.store.change(envelope.chatId, record=>{
      requireState(record.kind==='practice','wrong_session_kind','Practice session required.');
      const active=activeProblemOf(record.messages);
      if(input.type==='thinking') {
        requireState(active?.toolCallId===input.problemCallId && text(input.text),'stale_problem','Thinking must target the active problem.');
        record.messages.push(newThinkingMessage(input.problemCallId,input.text));
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
    const feedback=problemIndex<0 ? [] : record.messages.slice(problemIndex+1,active?undefined:concludeIndex)
      .filter(m=>m.role==='assistant').flatMap(m=>m.content.filter(b=>b.type==='text').map(b=>({id:m.id,text:b.text})));
    return{chatId,revision:record.adapter.revision,activeProblem:active ? {toolCallId:active.toolCallId,statement:active.input.statement} : null,
      feedback,
      discussion:active||concludeIndex<0?[]:record.messages.slice(concludeIndex+2).flatMap(m=>m.role==='user'?
        [{id:m.id,role:'user',text:m.content}]:m.role==='assistant'?m.content.filter(b=>b.type==='text').map(b=>({id:m.id,role:'assistant',text:b.text})):[]),
      thinking:record.messages.filter(m=>m.role==='custom' && m.customType==='practice-thinking' && m.details.problemCallId===(active??reviewed)?.toolCallId).map(m=>m.details.text),
      conclusion:conclude ? {...conclude.arguments,statement:reviewed?.input.statement,
        thinking:record.messages.filter(m=>m.role==='custom'&&m.customType==='practice-thinking'&&m.details.problemCallId===reviewed?.toolCallId).map(m=>m.details.text),
        modelSolution:modelSolutionForConclude(record.messages,conclude.id)} : null,
      nextAllowed:!active && record.adapter.practiceNextAllowed===true};
  }
}
