// SPDX-License-Identifier: AGPL-3.0-only
// Standard MCP Apps client for the existing controls, not a T3 frontend fork.
import { mountInline } from '../inline/inline-client.mjs';
import { readArtifact } from '../inline/artifacts.mjs';
import {createHostRichRenderer} from './rich-fragment.mjs';
import {mountFlashcards} from '../inline/flashcards-client.mjs';
import {createRichScope} from '../inline/rich-scope.mjs';
import {lessonVisualRows} from '../visuals-view.mjs';
import {lessonDraftKey,validateLessonView,MAX_LESSON_DRAFT_BYTES,practiceSubmissionIn,samePracticeSubmission} from '../inline/lesson-identity.mjs';
const root=document.querySelector('#lh-inline-lesson'),notice=document.querySelector('#lh-notice'),jobs=document.querySelector('#lh-jobs');
const options=document.querySelector('#lh-options'),materials=document.querySelector('#lh-materials');
const refreshButton=document.querySelector('#lh-refresh'),saveDraft=document.querySelector('#lh-save-draft');
const pending=new Map(),cache=new Map();let nextId=0,active=true,initialized=false,owner=null,view=null,controller=null,fresh=false,codex=false,refreshAttempt=0;
const {mount:mountRichFragment}=createHostRichRenderer(async(family,source)=>{
  if(!view)throw new Error('Open the saved lesson first.');
  const result=await call('learning_notation',{chatId:view.chatId,family,source});
  return result.structuredContent;
});
const jobRich=createRichScope(mountRichFragment);
let flashcards=null;
const flashcardSection=document.querySelector('#lh-flashcards');
let sentThinking=null;
const object=v=>v!==null&&typeof v==='object'&&!Array.isArray(v);
const byteSize=v=>new TextEncoder().encode(JSON.stringify(v)).length;
const keyOf=lessonDraftKey;
function unfinishedAnswer(payload) {
  const draft=payload?.privateContent?.lhInlineDraft??payload;
  if(!draft)return null;
  const {text,other,otherSelected,thinking,readingThinking,selected,dontKnow,confidenceIndex,drawing}=draft;
  const exercise=view?.activeProblem?.coding;
  const starter=view?.codingAttempts?.at(-1)?.code??exercise?.starterCode;
  const editedCode=exercise&&typeof draft.code==='string'&&draft.code!==starter?draft.code:undefined;
  if(!text&&!other&&!thinking&&!readingThinking&&!selected?.length&&!dontKnow&&!drawing?.length&&editedCode===undefined)return null;
  return JSON.stringify({text,other,otherSelected,thinking,readingThinking,selected,dontKnow,confidenceIndex,drawing,editedCode});
}
function updateDraftControl() {
  const entry=view&&cache.get(keyOf(view));
  const answer=unfinishedAnswer(entry?.payload);
  saveDraft.hidden=!fresh||!entry?.dirty||answer===(entry.savedAnswer??null);
  saveDraft.textContent=answer?'Save unfinished answer':'Discard unfinished answer';
}
function status(text,error=false){notice.textContent=text;notice.setAttribute('role',error?'alert':'status');}
function post(message){if(!active)throw new Error('This app was closed.');window.parent.postMessage(message,'*');}
function rpc(method,params) {
  if(pending.size>=8)return Promise.reject(new Error('A host request is already pending; wait for its outcome.'));
  return new Promise((resolve,reject)=>{
    const id='learning-'+(++nextId),timer=setTimeout(()=>{pending.delete(id);reject(new Error('Host outcome is unknown. Inspect the thread before repeating the action.'));},60000);
    pending.set(id,{resolve,reject,timer});post({jsonrpc:'2.0',id,method,params});
  });
}
async function call(name,args) {
  if(!initialized)throw new Error('The MCP App host has not initialized.');
  const result=await rpc('tools/call',{name,arguments:args});
  if(result?.isError)throw new Error('Learning tool refused the operation. Inspect the owning thread; no automatic retry.');
  return result;
}
function applyTheme(context) {
  if(context?.theme==='light'||context?.theme==='dark')document.documentElement.style.colorScheme=context.theme;
  for(const [key,value]of Object.entries(context?.styles?.variables??{}))
    if(/^--[a-zA-Z0-9_-]{1,100}$/.test(key)&&typeof value==='string'&&value.length<=500)document.documentElement.style.setProperty(key,value);
  // T3 supplies MCP Apps semantic variables, not Hermes's short token names.
  // Fixed aliases share the existing dock skin without changing either host.
  const aliases={'--foreground':['--color-text-primary','light-dark(#23272e,#e6e6e6)'],'--background':['--color-background-primary','light-dark(#fff,#141414)'],
    '--card':['--color-background-secondary','light-dark(#f5f6f7,#1c1c1c)'],'--muted-foreground':['--color-text-secondary','light-dark(#515960,#b8bfc7)'],
    '--border':['--color-border-primary','light-dark(#c7cdd3,#434343)'],'--accent':['--color-background-tertiary','light-dark(#e9edf1,#2a2a2a)'],
    '--destructive':['--color-text-danger','#ef4444'],'--ring':['--color-ring-primary','#8d8d8d']};
  for(const [name,[target,fallback]]of Object.entries(aliases))document.documentElement.style.setProperty(name,`var(${target}, ${fallback})`);
}
async function send(action,bound) {
  if(action.chatId!==bound.chatId)throw new Error('Input belongs to another lesson.');
  if(action.type==='resume') {
    const result=await call('learning_view',{chatId:bound.chatId});
    return {loaded:true,view:result.structuredContent.view};
  }
  if(!active||!fresh||view?.chatId!==bound.chatId||view?.revision!==bound.revision)throw new Error('Refresh current state before sending; this is a saved historical snapshot.');
  const allowed=bound.kind==='practice'?['practice-input','job-error']:['answer','approve','job-error'];
  if(!allowed.includes(action.type))throw new Error('Unsupported learner action.');
  const event={chatId:bound.chatId,kind:bound.kind==='practice'?'practice':'teach',expectedRevision:bound.revision,action};
  const text='lh.t3 '+JSON.stringify(event);
  if(new TextEncoder().encode(text).length>65536)throw new Error('Input exceeds64KiB; it was not sent or truncated.');
  if(action.type==='practice-input'&&action.input?.type==='thinking') {
    const key=keyOf(bound);
    sentThinking={key,text:action.input.text,code:action.input.code,drawing:action.input.drawing,
      draft:cache.get(key),ids:new Set(bound.thinkingEntries?.map(entry=>entry.id))};
  }
  // T3 confirms this message and routes it to the frame's owning conversation.
  // This is actual agent delivery, NOT a saved-answer acknowledgment.
  await rpc('ui/message',{role:'user',content:[{type:'text',text}]});
  return {delivered:true};
}
function validateResult(result) {
  const next=result?.structuredContent?.view,meta=result?._meta;
  if(!object(next)||!Number.isSafeInteger(next.revision)||typeof next.chatId!=='string'||
    typeof meta?.ownerThreadId!=='string'||!meta.ownerThreadId||meta.ownerThreadId.trim()!==meta.ownerThreadId||
    meta.ownerThreadId==='new'||byteSize(result)>256*1024)throw new Error('No valid bound lesson result received.');
  if(owner!==null&&(owner!==meta.ownerThreadId||view.chatId!==next.chatId||view.revision>next.revision))
    throw new Error('Refusing a different owner/lesson or stale replacement.');
  validateLessonView(next,{chatId:next.chatId,kind:next.kind==='practice'?'practice':'teach',minimumRevision:view?.revision??0});
  const key=keyOf(next);
  if(meta.draftKey!==key||!Number.isSafeInteger(meta.draft?.version))throw new Error('Saved draft identity differs.');
  return {next,meta,key};
}
function show({next,meta,key}) {
  view=next;fresh=true;
  if(sentThinking?.key===key&&next.thinkingEntries?.some(entry=>!sentThinking.ids.has(entry.id)&&practiceSubmissionIn(next,entry,sentThinking))) {
    const current=cache.get(key);
    // A new durable entry is the receipt. Delivery alone, or new typing,
    // must never consume a draft.
    if(current===sentThinking.draft&&samePracticeSubmission(current?.payload,sentThinking)) {
      if(current.version!==meta.draft.version)cache.delete(key);
      else cache.set(key,{...current,payload:null,dirty:samePracticeSubmission(meta.draft.payload,sentThinking)});
    }
    sentThinking=null;
  }
  const current=cache.get(key);
  if(!current?.dirty)cache.set(key,{version:meta.draft.version,payload:meta.draft.payload,savedAnswer:unfinishedAnswer(meta.draft.payload),dirty:false});
  controller?.destroy();
  const bound=structuredClone(next);
  const exploration=next.visuals?.some(visual=>visual.kind==='visual')?document.createElement('div'):null;
  controller=mountInline(root,next,{renderRich:mountRichFragment,send:action=>send(action,bound),workbench:true,exploration,appPresentation:true,
    runCoding:async(promptId,code)=>{
      if(!fresh||view.chatId!==bound.chatId||view.revision!==bound.revision)throw new Error('Refresh the current coding question first.');
      const result=await call('learning_coding_test',{chatId:bound.chatId,expectedRevision:bound.revision,promptId,code});
      return result.structuredContent;
    },readPracticeHistory:async(cursor)=>{
      if(!fresh||view.chatId!==bound.chatId||view.revision!==bound.revision)throw new Error('Refresh saved practice before reading responses.');
      return (await call('learning_practice_history',{chatId:bound.chatId,expectedRevision:bound.revision,...cursor})).structuredContent;
    },drafts:{
    read:requested=>cache.get(requested)?.payload??null,
    write(requested,payload){if(requested!==key||byteSize(payload)>MAX_LESSON_DRAFT_BYTES)throw new Error('Draft identity or size differs.');
      const old=cache.get(key)??{version:-1};cache.set(key,{...old,payload:structuredClone(payload),dirty:true});updateDraftControl();},
    remove:requested=>{const old=cache.get(requested);if(old)cache.set(requested,{...old,payload:null,dirty:true});updateDraftControl();},
  }});
  if(next.kind==='practice')options.append(saveDraft);
  else root.after(saveDraft);
  root.inert=false;options.hidden=false;updateDraftControl();
  if(flashcardSection) {
    flashcardSection.hidden=false;
    flashcardSection.inert=false;
    if(!flashcards)flashcards=mountFlashcards(flashcardSection,{renderRich:mountRichFragment,request:async request=>{
      if(!fresh)throw new Error('Open the current saved lesson to review flashcards.');
      const tool=['decks','next','reveal'].includes(request.action)?'learning_flashcards_view':'learning_flashcards';
      return (await call(tool,{chatId:bound.chatId,request})).structuredContent;
    }});
  }
  void renderJobs(next,bound,exploration);status('');
}
function node(tag,text){const e=document.createElement(tag);e.textContent=text;return e;}
function prose(tag,text){const e=node(tag,'');jobRich.render(e,text);return e;}
async function renderJobs(next,bound,exploration) {
  jobRich.clear();
  jobs.replaceChildren();
  materials.hidden=true;
  for(const material of next.materials??[])jobs.append(node('p',`Attached: ${material.label} (${material.kind})`));
  for(const job of [...(next.jobs?.jobs??[]),...lessonVisualRows(next)]) {
    if(!active||view!==next)return;
    const section=document.createElement('section');
    if(exploration&&job.directVisual&&job.artifact.kind==='visual')exploration.append(section);
    else {
      if(job.artifact?.kind!=='demo')section.append(node('h3',job.activity));
      jobs.append(section);
    }
    if(job.error)section.append(node('pre',job.error));
    const report=job.research??job.pdf;
    if(report?.brief)section.append(prose('div',report.brief));
    for(const source of job.research?.sources??[]) {
      const link=node('button',source.title);link.type='button';link.addEventListener('click',()=>void rpc('ui/open-link',{url:source.url}).catch(e=>status(e.message,true)));section.append(link);
    }
    if(job.pdf)section.append(node('p',`Reader-reported pages: ${job.pdf.pagesRead.join(', ')}; consulted: ${job.pdf.pagesConsulted.join(', ')}.`));
    if(job.artifact?.kind==='visual') {
      try {
        const source=await readArtifact({readText:async(_,file)=>({ok:true,...(await call('learning_asset',{chatId:next.chatId,file}))._meta})},{folder:'bound'},job.artifact);
        if(!active||view!==next)return;
        const image=document.createElement('img');image.alt=job.artifact.title;image.src='data:image/svg+xml;charset=utf-8,'+encodeURIComponent(source);image.style.maxWidth='100%';image.style.height='auto';section.append(image);
      } catch{section.append(node('p','Couldn’t load the figure.'));}
    }
    if(job.artifact?.kind==='demo') {
      if(codex) {
        const button=node('button',`Open ${job.artifact.title} in chat`);button.type='button';button.dataset.lhModelAction='demo';button.disabled=!fresh;
        button.addEventListener('click',()=>{
          if(!active||!fresh||view!==next)return;
          const event={chatId:bound.chatId,kind:bound.kind,expectedRevision:bound.revision,action:{type:'resume',chatId:bound.chatId}};
          void rpc('ui/message',{role:'user',content:[{type:'text',text:'lh.t3 '+JSON.stringify(event)}]}).catch(error=>status(error.message,true));
        });section.append(button);
        continue;
      }
      const button=node('button',`Open ${job.artifact.title}`);button.type='button';button.dataset.lhModelAction='demo';button.disabled=!active||!fresh||view!==next;
      button.addEventListener('click',()=>{
        if(!active||!fresh||view!==next){status('Refresh current state before asking the teacher to open this saved demo.',true);return;}
        void rpc('ui/message',{role:'user',content:[{type:'text',text:
          'Open the existing saved demo for '+JSON.stringify({chatId:bound.chatId,jobId:job.id,file:job.artifact.file})+' using learning_artifact_source and the supported T3 native visual publisher. Do not regenerate it, change learner state, install a preview browser or claim a test that did not run.'}]}).catch(e=>status(e.message,true));
      });section.append(button);
    }
  }
  materials.hidden=!jobs.childElementCount;
}
saveDraft.addEventListener('click',async()=>{
  if(!view||!fresh||saveDraft.hidden)return;
  const key=keyOf(view),saved=cache.get(key);
  if(!saved?.dirty)return;
  const captured=JSON.stringify(saved.payload),baseRevision=view.revision,chatId=view.chatId;
  const answer=unfinishedAnswer(saved.payload);
  saveDraft.disabled=true;
  try {
    const result=await call('learning_draft',{chatId,key,baseRevision,expectedVersion:saved.version,payload:JSON.parse(captured)});
    const version=result.structuredContent?.version;
    if(!Number.isSafeInteger(version))throw new Error('Draft save outcome is unknown.');
    const current=cache.get(key);
    if(current)cache.set(key,{...current,version,savedAnswer:answer,dirty:JSON.stringify(current.payload)!==captured});
    if(view?.chatId===chatId&&keyOf(view)===key) {
      updateDraftControl();
      const result=answer?'Unfinished answer saved.':'Unfinished answer discarded.';
      status(saveDraft.hidden?result:result+' Newer edits are still unsaved.');
    }
  }catch(error){status(error.message,true);}
  finally{saveDraft.disabled=false;}
});
async function refresh(checkOpeningRevision=false) {
  if(!view||!initialized)return;
  const attempt=++refreshAttempt;
  status(checkOpeningRevision?'Loading lesson…':'Refreshing lesson…');
  fresh=false;root.inert=true;refreshButton.disabled=true;saveDraft.hidden=true;
  if(flashcardSection)flashcardSection.inert=true;
  for(const button of jobs.querySelectorAll('[data-lh-model-action]'))button.disabled=true;
  try{
    const result=validateResult(await call('learning_view',{chatId:view.chatId}));
    if(!active||attempt!==refreshAttempt)return;
    if(checkOpeningRevision&&result.next.revision>view.revision) {
      options.hidden=true;
      status('Earlier lesson step');
      return;
    }
    show(result);
  }
  catch(error){
    if(active&&attempt===refreshAttempt) {
      options.hidden=false;
      status('Couldn’t load the lesson here.',true);
    }
  }
  finally{if(active&&attempt===refreshAttempt)refreshButton.disabled=false;}
}
refreshButton.addEventListener('click',()=>void refresh(!controller));
async function receive(event) {
  if(!active||event.source!==window.parent||!object(event.data)||event.data.jsonrpc!=='2.0')return;
  const message=event.data;if(byteSize(message)>256*1024)return;
  if(message.method==='ui/resource-teardown'&&message.id!==undefined) {
    controller?.destroy();flashcards?.destroy();jobRich.clear();post({jsonrpc:'2.0',id:message.id,result:{}});active=false;
    for(const row of pending.values()){clearTimeout(row.timer);row.reject(new Error('App closed; inspect outcome before repeating an action.'));}pending.clear();return;
  }
  if(message.method==='ui/notifications/tool-result'){
    if(view)return; // The opening result identifies this transcript entry.
    try{
      const {next,meta}=validateResult(message.params);
      owner=meta.ownerThreadId;view=next;
      if(initialized)void refresh(true);
    }catch{status('Couldn’t open the lesson here.',true);}return;
  }
  if(message.method==='ui/notifications/host-context-changed'){applyTheme(message.params);return;}
  const row=pending.get(message.id);if(!row)return;pending.delete(message.id);clearTimeout(row.timer);
  if(message.error)row.reject(new Error(typeof message.error.message==='string'?message.error.message:'Host refused the operation.'));
  else row.resolve(message.result);
}
window.addEventListener('message',receive);
const observer=new ResizeObserver(()=>{if(initialized&&active)post({jsonrpc:'2.0',method:'ui/notifications/size-changed',params:{height:Math.min(2000,Math.max(80,document.body.scrollHeight))}});});observer.observe(document.body);
rpc('ui/initialize',{protocolVersion:'2026-01-26',appInfo:{name:'learnharness-native',version:'0.1.0-dev'},appCapabilities:{}})
  .then(result=>{
    if(!active)return;
    if(!object(result)||typeof result.protocolVersion!=='string')throw new Error('The host returned an invalid MCP Apps initialization response.');
    // Host identity extensions can be omitted by a standards-only bridge.
    // Reply to the handshake before applying optional presentation metadata.
    initialized=true;
    post({jsonrpc:'2.0',method:'ui/notifications/initialized',params:{}});
    codex=result.hostInfo?.name!=='t3-code';
    applyTheme(result.hostContext);
    if(view)void refresh(true);})
  .catch(error=>{
    console.warn('LearnHarness MCP App initialization failed.');
    status('Couldn’t connect to the lesson.',true);
  });
