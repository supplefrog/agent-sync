// SPDX-License-Identifier: AGPL-3.0-only
// Practice adaptation: same inline components/styles and native input contracts.
import {createRichScope} from './rich-scope.mjs';
import {lessonDraftKey} from './lesson-identity.mjs';
export function mountPractice(root, initialView, options = {}) {
  const doc=root.ownerDocument, win=doc.defaultView;
  let view=initialView, text='', open=true, pending=false, editVersion=0;
  const rich=createRichScope(options.renderRich);
  const key=()=>lessonDraftKey(view);
  const node=(tag,value,attrs={})=>{const e=doc.createElement(tag);if(value!==null)e.textContent=value;for(const[k,v]of Object.entries(attrs))e.setAttribute(k,String(v));return e;};
  const button=(label,fn,attrs={})=>{const e=node('button',label,{type:'button',...attrs});e.addEventListener('click',fn);return e;};
  const prose=(tag,value,attrs={})=>{const element=node(tag,null,attrs);rich.render(element,value);return element;};
  const status=(message,error=false)=>{const e=root.querySelector('[data-status]');if(e){e.textContent=message;e.setAttribute('role',error?'alert':'status');}};
  function save(){try{options.drafts?.write(key(),{key:key(),text,open});}catch{status('The draft could not be saved. Keep this view open.',true);}}
  function restore(){try{const cached=options.drafts?.read(key());if(cached?.key===key()&&typeof cached.text==='string'&&cached.text.length<=16000){text=cached.text;open=cached.open!==false;}}catch{/* Corrupt storage cannot replace practice state. */}}
  restore();
  async function send(type,input){if(pending)return;pending=true;render();try{
    if(typeof options.send!=='function')throw new Error('Use the connected practice browser to save.');
    const oldKey=key(),versionAtSend=editVersion,baselineIds=(view.thinkingEntries??[]).map(entry=>entry.id);
    const submitted=type==='practice-input'&&input?.type==='thinking'&&input.problemCallId===view.activeProblem?.toolCallId;
    const draftBefore=submitted?JSON.stringify(options.drafts?.read(oldKey)):undefined;
    const result=await options.send({type,chatId:view.chatId,...(input?{input}: {})});
    if(result?.requested===true){status('Host action requested. Confirm delivery in chat; the saved lesson response will confirm persistence. If canceled, use Resume saved lesson.');return;}
    if(result?.delivered===true){status('Delivered to the owning agent. Waiting for the saved practice response.');return;}
    if(!result?.view||!(result.persisted||result.loaded))throw new Error('No saved practice response received.');
    const same=result.view.activeProblem?.toolCallId===view.activeProblem?.toolCallId;
    const thinkingSaved=submitted&&result.persisted===true&&same&&result.view.thinkingEntries?.some(entry=>
      typeof entry.id==='string'&&entry.id&&!baselineIds.includes(entry.id)&&entry.text===input.text);
    if(thinkingSaved&&editVersion===versionAtSend)try{
      // Delivery/reopen and an unrelated revision cannot consume a draft.
      // Nor can a newer draft typed while this request was in flight.
      if(JSON.stringify(options.drafts?.read(oldKey))===draftBefore)options.drafts?.remove(oldKey);
    }catch{/* Saved thinking remains authoritative; failed cleanup retains draft. */}
    view=result.view;pending=false;
    if(!same){text='';open=true;restore();}
    else if(thinkingSaved&&editVersion===versionAtSend){text='';open=true;}
    render();status(result.loaded?'Saved practice reopened.':input?.type==='next'?'Next problem requested.':
      thinkingSaved?'Thinking saved.':'Saved response received; draft retained until matching thinking is confirmed.');
  }catch(error){pending=false;render();status(error.message,true);}}
  function render(){rich.clear();root.replaceChildren();options.onPresentation?.({open});const active=view.activeProblem;
    if(!active&&options.exploration){options.exploration.hidden=false;root.append(options.exploration);}
    if(view.conclusion&&!options.richProse){root.append(node('h3','Problem review'),prose('div',view.conclusion.statement));for(const thought of view.conclusion.thinking??[])root.append(node('p',`Your thinking: ${thought}`));root.append(prose('div',view.conclusion.verdict),node('h3','Committed solution'),prose('div',view.conclusion.modelSolution));}
    if(view.conclusion&&options.richProse)for(const thought of view.conclusion.thinking??[])root.append(node('p',`Your thinking: ${thought}`));
    if(!options.richProse)for(const entry of view.discussion??[])root.append(entry.role==='user'?node('p',`Your question: ${entry.text}`):prose('div',entry.text));
    if(active){const dock=node('section',null,{class:'lh-dock'});root.append(dock);
      if(!open)dock.append(button('Practice problem · Reopen',()=>{open=true;save();render();},{class:'lh-reveal'}));
      else {const heading=node('div',null,{class:'lh-heading'});heading.append(node('span','Practice problem'),button('Close',()=>{open=false;save();render();},{class:'lh-close'}));dock.append(heading);
        if(options.exploration){options.exploration.hidden=false;dock.append(options.exploration);}
        if(!options.richProse)dock.append(prose('div',active.statement));
        for(const thought of view.thinking)dock.append(node('p',`Your thinking: ${thought}`));
        if(!options.richProse)for(const entry of view.feedback??[])dock.append(prose('div',entry.text,{'data-practice-feedback':entry.id}));
        const label=node('label',null,{class:'lh-field'});label.append(node('span','Your thinking',{class:'lh-field-label'}));
        const field=node('textarea',null,{rows:4,'data-practice-thinking':'',maxlength:16000,placeholder:'Work here, think out loud.'});field.value=text;
        field.addEventListener('input',()=>{text=field.value;editVersion++;save();const submit=root.querySelector('[data-practice-send]');if(submit)submit.disabled=pending||!text.trim();});
        field.addEventListener('keydown',event=>{if(event.key==='Enter'&&(!event.shiftKey||event.metaKey||event.ctrlKey)){event.preventDefault();if(text.trim())void send('practice-input',{type:'thinking',problemCallId:active.toolCallId,text});}});
        label.append(field);dock.append(label,node('span','Enter sends · Shift+Enter newline',{class:'lh-secondary'}));
        const submit=button('Submit thinking',()=>void send('practice-input',{type:'thinking',problemCallId:active.toolCallId,text}),{class:'lh-submit','data-practice-send':''});submit.disabled=pending||!text.trim();dock.append(submit);}
    }else if(view.conclusion){
      const next=button('Next problem',()=>void send('practice-input',{type:'next'}),{class:'lh-submit'});next.disabled=pending||view.nextAllowed;root.append(next);
      if(view.nextAllowed)root.append(node('p','Next problem requested.'));
    }else root.append(node('p','No practice problem has been posed.'));
    root.append(node('p',pending?'Saving…':'',{'data-status':'','aria-live':'polite',role:'status'}),button('Resume saved lesson',()=>options.onResume?void options.onResume():void send('resume'),{class:'lh-resume'}));
  }
  render();return{destroy(){rich.clear();},readDraft:()=>({text,open,pending})};
}
