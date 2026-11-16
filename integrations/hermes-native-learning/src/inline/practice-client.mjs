// SPDX-License-Identifier: AGPL-3.0-only
// Practice adaptation: same inline components/styles and native input contracts.
import {createRichScope} from './rich-scope.mjs';
import {lessonDraftKey,practiceSubmissionIn} from './lesson-identity.mjs';
import {lessonResponseArea} from './lesson-layout.mjs';
import {drawingPad,savedDrawing} from './drawing-client.mjs';
import {validDrawing} from '../drawing.mjs';
import {mountCodingEditor} from './coding-client.mjs';
import {codingRecord} from './answered-record.mjs';
export function mountPractice(root, initialView, options = {}) {
  const doc=root.ownerDocument, win=doc.defaultView;
  let view=initialView, text='', open=true, pending=false, editVersion=0, historyOpen=(initialView.feedback?.length??0)>0;
  let drawing=[], drawingHistory=[];
  const starter=current=>current.codingAttempts?.at(-1)?.code??current.activeProblem?.coding?.starterCode??'';
  let code=starter(view), codingReceipt;
  let earlierRows=[],earlierCursor=view.earlierResponses??null,historyPending=false;
  const rich=createRichScope(options.renderRich);
  const key=()=>lessonDraftKey(view);
  const node=(tag,value,attrs={})=>{const e=doc.createElement(tag);if(value!==null)e.textContent=value;for(const[k,v]of Object.entries(attrs))e.setAttribute(k,String(v));return e;};
  const button=(label,fn,attrs={})=>{const e=node('button',label,{type:'button',...attrs});e.addEventListener('click',fn);return e;};
  const prose=(tag,value,attrs={})=>{const element=node(tag,null,attrs);rich.render(element,value);return element;};
  const status=(message,error=false)=>{const e=root.querySelector('[data-status]');if(e){e.textContent=message;e.setAttribute('role',error?'alert':'status');}};
  function save(){try{options.drafts?.write(key(),{key:key(),text,open,...(drawing.length?{drawing}:{}),
    ...(view.activeProblem?.coding?{code}:{})});}catch{status('The draft could not be saved. Keep this view open.',true);}}
  function restore(){try{const cached=options.drafts?.read(key());if(cached?.key===key()&&typeof cached.text==='string'&&cached.text.length<=16000){
    text=cached.text;open=cached.open!==false;drawing=validDrawing(cached.drawing)?cached.drawing:[];
    if(view.activeProblem?.coding&&typeof cached.code==='string'&&cached.code.length<=8192)code=cached.code;
  }}catch{/* Corrupt storage cannot replace practice state. */}}
  restore();
  async function send(type,input){if(pending)return;pending=true;render();try{
    if(typeof options.send!=='function')throw new Error('Use the connected practice browser to save.');
    const oldKey=key(),versionAtSend=editVersion,baselineIds=(view.thinkingEntries??[]).map(entry=>entry.id);
    const submitted=type==='practice-input'&&input?.type==='thinking'&&input.problemCallId===view.activeProblem?.toolCallId;
    const draftBefore=submitted?JSON.stringify(options.drafts?.read(oldKey)):undefined;
    const result=await options.send({type,chatId:view.chatId,...(input?{input}: {})});
    if(result?.requested===true){status('Host action requested. Confirm delivery in chat; the saved lesson response will confirm persistence. If canceled, use Resume saved lesson.');return;}
    if(result?.delivered===true){
      status(options.appPresentation?'Sent. Waiting for the lesson to continue.':'Delivered to the owning agent. Waiting for the saved practice response.');
      return;
    }
    if(!result?.view||!(result.persisted||result.loaded))throw new Error('No saved practice response received.');
    const same=result.view.activeProblem?.toolCallId===view.activeProblem?.toolCallId;
    const thinkingSaved=submitted&&result.persisted===true&&same&&result.view.thinkingEntries?.some(entry=>
      !baselineIds.includes(entry.id)&&practiceSubmissionIn(result.view,entry,input));
    if(thinkingSaved&&editVersion===versionAtSend)try{
      // Delivery/reopen and an unrelated revision cannot consume a draft.
      // Nor can a newer draft typed while this request was in flight.
      if(JSON.stringify(options.drafts?.read(oldKey))===draftBefore)options.drafts?.remove(oldKey);
    }catch{/* Saved thinking remains authoritative; failed cleanup retains draft. */}
    if(result.view.feedback?.at(-1)?.id!==view.feedback?.at(-1)?.id)historyOpen=true;
    if(!same||result.view.revision!==view.revision){
      codingReceipt=undefined;earlierRows=[];earlierCursor=result.view.earlierResponses??null;
    }
    view=result.view;pending=false;
    if(!same){text='';code=starter(view);drawing=[];drawingHistory=[];open=true;restore();}
    else if(thinkingSaved&&editVersion===versionAtSend){text='';drawing=[];drawingHistory=[];open=true;}
    render();status(result.loaded?'Saved practice reopened.':input?.type==='next'?'Next problem requested.':
      thinkingSaved?'Thinking saved.':'Saved response received; draft retained until matching thinking is confirmed.');
  }catch(error){pending=false;render();status(error.message,true);}}
  function priorResponses(target) {
    for(const row of earlierRows) {
      if(row.text)target.append(node('p',`Your thinking: ${row.text}`));
      const drawing=savedDrawing(doc,row.drawing);if(drawing)target.append(drawing);
      if(row.coding)target.append(codingRecord(doc,row.coding));
    }
    if(earlierCursor&&options.readPracticeHistory){
      const control=button('Load earlier responses',async()=>{
        if(historyPending)return;
        const cursor=earlierCursor,revision=view.revision;
        historyPending=true;control.disabled=true;
        try{
          const page=await options.readPracticeHistory(cursor);
          if(revision!==view.revision)return;
          if(page?.problemId!==cursor.problemId||!Array.isArray(page.rows))throw new Error('Earlier responses could not be loaded.');
          earlierRows=[...page.rows,...earlierRows];
          earlierCursor=page.nextBefore?{problemId:cursor.problemId,before:page.nextBefore}:null;
          render();status('Earlier responses loaded.');
          root.querySelector('[data-earlier-responses]')?.focus();
        }catch(error){status(error.message,true);}
        finally{historyPending=false;control.disabled=false;}
      },{'data-earlier-responses':''});
      target.append(control);
    }
  }
  function render(){rich.clear();root.replaceChildren();options.onPresentation?.({open});const active=view.activeProblem;
    if(!active&&options.exploration){options.exploration.hidden=false;root.append(options.exploration);}
    if(view.conclusion&&!options.richProse){
      root.append(node('h3','Problem review'),prose('div',view.conclusion.statement));
      for(const thought of view.conclusion.thinking??[])if(thought)root.append(node('p',`Your thinking: ${thought}`));
      root.append(prose('div',view.conclusion.verdict),node('h3','Committed solution'));
      if(view.conclusion.codingLanguage) {
        const code=node('pre',view.conclusion.modelSolution);code.style.overflow='auto';root.append(code);
      } else root.append(prose('div',view.conclusion.modelSolution));
    }
    if(view.conclusion&&options.richProse)for(const thought of view.conclusion.thinking??[])root.append(node('p',`Your thinking: ${thought}`));
    if(!active)for(const record of view.drawings??[]){const saved=savedDrawing(doc,record.drawing);if(saved)root.append(saved);}
    if(!active)for(const attempt of view.codingAttempts??[])root.append(codingRecord(doc,attempt));
    if(!active)priorResponses(root);
    if(!options.richProse)for(const entry of view.discussion??[])root.append(entry.role==='user'?node('p',`Your question: ${entry.text}`):prose('div',entry.text));
    if(active){const dock=node('section',null,{class:'lh-dock'});root.append(dock);
      if(!open){
        dock.append(button('Practice problem · Reopen',()=>{open=true;save();render();},{class:'lh-reveal'}));
        if(options.workbench&&options.exploration)root.append(options.exploration);
      }
      else {const heading=node('div',null,{class:'lh-heading'});heading.append(node('span','Practice problem'),button('Close',()=>{open=false;save();render();},{class:'lh-close'}));dock.append(heading);
        const response=lessonResponseArea(dock,options);
        if(!options.richProse)response.append(prose('div',active.statement));
        const hasHistory=view.thinking.length>0||(!options.richProse&&(view.feedback?.length??0)>0);
        const history=options.workbench&&hasHistory?node('details',null,{class:'lh-practice-history'}):response;
        if(history!==response){
          history.open=historyOpen;
          history.addEventListener('toggle',()=>{historyOpen=history.open;});
          history.append(node('summary','Saved response and feedback'));
        }
        for(const thought of view.thinking)if(thought)history.append(node('p',`Your thinking: ${thought}`));
        for(const record of view.drawings??[]){const saved=savedDrawing(doc,record.drawing);if(saved)history.append(saved);}
        for(const attempt of view.codingAttempts??[])history.append(codingRecord(doc,attempt));
        priorResponses(history);
        if(!options.richProse)for(const entry of view.feedback??[])history.append(prose('div',entry.text,{'data-practice-feedback':entry.id}));
        const label=node('label',null,{class:'lh-field'});label.append(node('span','Think out loud',{class:'lh-field-label'}));
        const field=node('textarea',null,{rows:options.workbench?3:4,'data-practice-thinking':'',maxlength:16000});field.value=text;
        const canSubmit=()=>!pending&&(active.coding?code.trim()&&new TextEncoder().encode(code).length<=8192:text.trim());
        const updateSubmit=()=>{const submit=root.querySelector('[data-practice-send]');if(submit)submit.disabled=!canSubmit();};
        field.addEventListener('input',()=>{text=field.value;editVersion++;save();updateSubmit();});
        const submitWork=()=>{if(canSubmit())void send('practice-input',{type:'thinking',problemCallId:active.toolCallId,text,...(drawing.length?{drawing}:{}),
          ...(active.coding?{code,...(codingReceipt?{codingRunId:codingReceipt.runId}:{})}:{})});};
        field.addEventListener('keydown',event=>{if(!active.coding&&event.key==='Enter'&&(!event.shiftKey||event.metaKey||event.ctrlKey)){event.preventDefault();submitWork();}});
        if(active.coding)mountCodingEditor(response,{spec:active.coding,value:code,disabled:pending,observations:codingReceipt?.observations,
          onChange:value=>{code=value;editVersion++;save();updateSubmit();},onReceipt:receipt=>{codingReceipt=receipt;},
          onRun:options.runCoding?value=>options.runCoding(active.toolCallId,value):undefined});
        label.append(field);response.append(label);
        if(!active.coding)response.append(node('span','Enter sends · Shift+Enter newline',{class:'lh-secondary'}));
        if(options.allowDrawing!==false)response.append(drawingPad(doc,{value:drawing,disabled:pending,history:drawingHistory,
          onChange:strokes=>{drawing=strokes;editVersion++;save();}}));
        const submit=button(active.coding?'Submit code':'Submit thinking',submitWork,{class:'lh-submit','data-practice-send':''});submit.disabled=!canSubmit();response.append(submit);
        if(history!==response)response.append(history);}
    }else if(view.conclusion){
      const next=button('Next problem',()=>void send('practice-input',{type:'next'}),{class:'lh-submit'});next.disabled=pending||view.nextAllowed;root.append(next);
      if(view.nextAllowed)root.append(node('p','Next problem requested.'));
    }else root.append(node('p','No practice problem has been posed.'));
    root.append(node('p',pending?'Sending…':'',{'data-status':'','aria-live':'polite',role:'status'}));
    if(!options.appPresentation)root.append(button('Resume saved lesson',()=>options.onResume?void options.onResume():void send('resume'),{class:'lh-resume'}));
  }
  render();return{destroy(){rich.clear();},readDraft:()=>({text,open,pending})};
}
