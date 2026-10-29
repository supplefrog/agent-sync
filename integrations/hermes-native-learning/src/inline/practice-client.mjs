// SPDX-License-Identifier: AGPL-3.0-only
// Practice adaptation: same inline components/styles and native input contracts.
export function mountPractice(root, initialView, options = {}) {
  const doc=root.ownerDocument, win=doc.defaultView;
  let view=initialView, text='', open=true, pending=false;
  const key=()=>`${view.chatId}:practice:${view.activeProblem?.toolCallId??'between'}`;
  const node=(tag,value,attrs={})=>{const e=doc.createElement(tag);if(value!==null)e.textContent=value;for(const[k,v]of Object.entries(attrs))e.setAttribute(k,String(v));return e;};
  const button=(label,fn,attrs={})=>{const e=node('button',label,{type:'button',...attrs});e.addEventListener('click',fn);return e;};
  const status=(message,error=false)=>{const e=root.querySelector('[data-status]');if(e){e.textContent=message;e.setAttribute('role',error?'alert':'status');}};
  function save(){try{options.drafts?.write(key(),{key:key(),text,open});}catch{status('The draft could not be saved. Keep this view open.',true);}}
  function restore(){try{const cached=options.drafts?.read(key());if(cached?.key===key()&&typeof cached.text==='string'&&cached.text.length<=16000){text=cached.text;open=cached.open!==false;}}catch{/* Corrupt storage cannot replace practice state. */}}
  restore();
  async function send(type,input){if(pending)return;pending=true;render();try{
    if(typeof options.send!=='function')throw new Error('Use the connected practice browser to save.');
    const result=await options.send({type,chatId:view.chatId,...(input?{input}: {})});
    if(result?.delivered===true){status('Delivered to the owning agent. Waiting for the saved practice response.');return;}
    if(!result?.view||!(result.persisted||result.loaded))throw new Error('No saved practice response received.');
    const oldKey=key(),same=result.view.activeProblem?.toolCallId===view.activeProblem?.toolCallId;
    view=result.view;pending=false;
    if(input?.type==='thinking'||!same){try{options.drafts?.remove(oldKey);}catch{}text='';open=true;}
    if(!same)restore();render();status(result.loaded?'Saved practice reopened.':input?.type==='next'?'Next problem requested.':'Thinking saved.');
  }catch(error){pending=false;render();status(error.message,true);}}
  function render(){root.replaceChildren();options.onPresentation?.({open});const active=view.activeProblem;
    if(view.conclusion&&!options.richProse){root.append(node('h3','Problem review'),node('p',view.conclusion.statement));for(const thought of view.conclusion.thinking??[])root.append(node('p',`Your thinking: ${thought}`));root.append(node('p',view.conclusion.verdict),node('h3','Committed solution'),node('p',view.conclusion.modelSolution));}
    if(view.conclusion&&options.richProse)for(const thought of view.conclusion.thinking??[])root.append(node('p',`Your thinking: ${thought}`));
    if(!options.richProse)for(const entry of view.discussion??[])root.append(node('p',entry.role==='user'?`Your question: ${entry.text}`:entry.text));
    if(active){const dock=node('section',null,{class:'lh-dock'});root.append(dock);
      if(!open)dock.append(button('Practice problem · Reopen',()=>{open=true;save();render();},{class:'lh-reveal'}));
      else {const heading=node('div',null,{class:'lh-heading'});heading.append(node('span','Practice problem'),button('Close',()=>{open=false;save();render();},{class:'lh-close'}));dock.append(heading);if(!options.richProse)dock.append(node('h3',active.statement));
        for(const thought of view.thinking)dock.append(node('p',`Your thinking: ${thought}`));
        if(!options.richProse)for(const entry of view.feedback??[])dock.append(node('p',entry.text,{'data-practice-feedback':entry.id}));
        const label=node('label',null,{class:'lh-field'});label.append(node('span','Your thinking',{class:'lh-field-label'}));
        const field=node('textarea',null,{rows:4,'data-practice-thinking':'',maxlength:16000,placeholder:'Work here, think out loud.'});field.value=text;
        field.addEventListener('input',()=>{text=field.value;save();const submit=root.querySelector('[data-practice-send]');if(submit)submit.disabled=pending||!text.trim();});
        field.addEventListener('keydown',event=>{if(event.key==='Enter'&&(!event.shiftKey||event.metaKey||event.ctrlKey)){event.preventDefault();if(text.trim())void send('practice-input',{type:'thinking',problemCallId:active.toolCallId,text});}});
        label.append(field);dock.append(label,node('span','Enter sends · Shift+Enter newline',{class:'lh-secondary'}));
        const submit=button('Submit thinking',()=>void send('practice-input',{type:'thinking',problemCallId:active.toolCallId,text}),{class:'lh-submit','data-practice-send':''});submit.disabled=pending||!text.trim();dock.append(submit);}
    }else if(view.conclusion){
      const next=button('Next problem',()=>void send('practice-input',{type:'next'}),{class:'lh-submit'});next.disabled=pending||view.nextAllowed;root.append(next);
      if(view.nextAllowed)root.append(node('p','Next problem requested.'));
    }else root.append(node('p','No practice problem has been posed.'));
    root.append(node('p',pending?'Saving…':'',{'data-status':'','aria-live':'polite',role:'status'}),button('Resume saved lesson',()=>options.onResume?void options.onResume():void send('resume'),{class:'lh-resume'}));
  }
  render();return{destroy(){},readDraft:()=>({text,open,pending})};
}
