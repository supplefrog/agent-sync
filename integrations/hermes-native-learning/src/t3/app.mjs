// SPDX-License-Identifier: AGPL-3.0-only
// Standard MCP Apps client for the existing controls, not a T3 frontend fork.
import { mountInline } from '../inline/inline-client.mjs';
import { readArtifact } from '../inline/artifacts.mjs';
import {mountRichFragment} from './rich-fragment.mjs';
import {createRichScope} from '../inline/rich-scope.mjs';
import {lessonVisualRows} from '../visuals-view.mjs';
import {lessonDraftKey,validateLessonView} from '../inline/lesson-identity.mjs';
const root=document.querySelector('#lh-inline-lesson'),notice=document.querySelector('#lh-notice'),jobs=document.querySelector('#lh-jobs');
const jobRich=createRichScope(mountRichFragment);
const pending=new Map(),cache=new Map();let nextId=0,active=true,initialized=false,owner=null,view=null,controller=null,fresh=false,initialRefresh=false;
const object=v=>v!==null&&typeof v==='object'&&!Array.isArray(v);
const byteSize=v=>new TextEncoder().encode(JSON.stringify(v)).length;
const keyOf=lessonDraftKey;
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
  const aliases={'--foreground':['--color-text-primary','#e6e6e6'],'--background':['--color-background-primary','#141414'],
    '--card':['--color-background-secondary','#1c1c1c'],'--muted-foreground':['--color-text-secondary','#8d8d8d'],
    '--border':['--color-border-primary','#434343'],'--accent':['--color-background-tertiary','#2a2a2a'],
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
  // T3 confirms this message and routes it to the frame's owning conversation.
  // This is actual agent delivery, NOT a saved-answer acknowledgment.
  await rpc('ui/message',{role:'user',content:[{type:'text',text}]});
  return {delivered:true};
}
function show(result,isFresh=false) {
  const next=result?.structuredContent?.view,meta=result?._meta;
  if(!object(next)||!Number.isSafeInteger(next.revision)||typeof next.chatId!=='string'||
    typeof meta?.ownerThreadId!=='string'||!meta.ownerThreadId||meta.ownerThreadId.trim()!==meta.ownerThreadId||
    meta.ownerThreadId==='new'||byteSize(result)>256*1024)throw new Error('No valid bound lesson result received.');
  if(owner!==null&&(owner!==meta.ownerThreadId||view.chatId!==next.chatId||view.revision>next.revision))
    throw new Error('Refusing a different owner/lesson or stale replacement.');
  validateLessonView(next,{chatId:next.chatId,kind:next.kind==='practice'?'practice':'teach',minimumRevision:view?.revision??0});
  owner=meta.ownerThreadId;view=next;fresh=isFresh;const key=keyOf(next);
  if(meta.draftKey!==key||!Number.isSafeInteger(meta.draft?.version))throw new Error('Saved draft identity differs.');
  const current=cache.get(key);
  if(!current?.dirty)cache.set(key,{version:meta.draft.version,payload:meta.draft.payload,dirty:false});
  controller?.destroy();
  const bound=structuredClone(next);
  controller=mountInline(root,next,{renderRich:mountRichFragment,send:action=>send(action,bound),onResume:refresh,drafts:{
    read:requested=>cache.get(requested)?.payload??null,
    write(requested,payload){if(requested!==key||byteSize(payload)>16384)throw new Error('Draft identity/size differs.');
      const old=cache.get(key)??{version:-1};cache.set(key,{...old,payload:structuredClone(payload),dirty:true});status('Draft is local. Use Save draft to preserve it across reopen.');},
    remove:requested=>{const old=cache.get(requested);if(old)cache.set(requested,{...old,payload:null,dirty:true});},
  }});
  root.inert=!fresh;document.querySelector('#lh-save-draft').disabled=!fresh;
  void renderJobs(next,bound);status(fresh?'Current saved lesson loaded. The existing agent remains the teacher.':'Historical snapshot loaded; refreshing without a model turn.');
}
function node(tag,text){const e=document.createElement(tag);e.textContent=text;return e;}
function prose(tag,text){const e=node(tag,'');jobRich.render(e,text);return e;}
async function renderJobs(next,bound) {
  jobRich.clear();
  jobs.replaceChildren();
  for(const material of next.materials??[])jobs.append(node('p',`Attached: ${material.label} (${material.kind})`));
  for(const job of [...(next.jobs?.jobs??[]),...lessonVisualRows(next)]) {
    if(!active||view!==next)return;
    const section=document.createElement('section');section.append(node('h3',`${job.kind}: ${job.activity}`));jobs.append(section);
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
        const image=document.createElement('img');image.alt=job.artifact.title;image.src='data:image/svg+xml;charset=utf-8,'+encodeURIComponent(source);image.style.maxWidth='100%';section.append(image);
      } catch{section.append(node('p','Saved figure unavailable; inspect the owning session before trying again.'));}
    }
    if(job.artifact?.kind==='demo') {
      section.append(node('p','Demo saved. The MCP App CSP does not permit the nested demo frame; use the existing T3 native visual publisher.'));
      const button=node('button','Ask teacher to open saved demo');button.type='button';button.dataset.lhModelAction='demo';button.disabled=!active||!fresh||view!==next;
      button.addEventListener('click',()=>{
        if(!active||!fresh||view!==next){status('Refresh current state before asking the teacher to open this saved demo.',true);return;}
        void rpc('ui/message',{role:'user',content:[{type:'text',text:
          'Open the existing saved demo for '+JSON.stringify({chatId:bound.chatId,jobId:job.id,file:job.artifact.file})+' using learning_artifact_source and the supported T3 native visual publisher. Do not regenerate it, change learner state, install a preview browser or claim a test that did not run.'}]}).catch(e=>status(e.message,true));
      });section.append(button);
    }
  }
}
document.querySelector('#lh-save-draft').addEventListener('click',async()=>{
  if(!view||!fresh)return;const key=keyOf(view),saved=cache.get(key);if(!saved?.dirty){status('No changed draft to save.');return;}
  const captured=JSON.stringify(saved.payload),baseRevision=view.revision,chatId=view.chatId;
  try {
    const result=await call('learning_draft',{chatId,key,baseRevision,expectedVersion:saved.version,payload:JSON.parse(captured)});
    const version=result.structuredContent?.version;
    if(!Number.isSafeInteger(version))throw new Error('Draft save outcome is unknown.');
    const current=cache.get(key);
    if(current)cache.set(key,{...current,version,dirty:JSON.stringify(current.payload)!==captured});
    status(cache.get(key)?.dirty?'Earlier draft saved; newer typing is still local.':'Draft saved privately. No answer or model turn was submitted.');
  }catch(error){status(error.message,true);}
});
async function refresh() {
  if(!view)return;
  fresh=false;root.inert=true;document.querySelector('#lh-save-draft').disabled=true;
  for(const button of jobs.querySelectorAll('[data-lh-model-action]'))button.disabled=true;
  try{show(await call('learning_view',{chatId:view.chatId}),true);}
  catch(error){status('Current state unavailable. Resume the originating T3 conversation, then Refresh. '+error.message,true);}
}
document.querySelector('#lh-refresh').addEventListener('click',()=>void refresh());
async function receive(event) {
  if(!active||event.source!==window.parent||!object(event.data)||event.data.jsonrpc!=='2.0')return;
  const message=event.data;if(byteSize(message)>256*1024)return;
  if(message.method==='ui/resource-teardown'&&message.id!==undefined) {
    controller?.destroy();jobRich.clear();post({jsonrpc:'2.0',id:message.id,result:{}});active=false;
    for(const row of pending.values()){clearTimeout(row.timer);row.reject(new Error('App closed; inspect outcome before repeating an action.'));}pending.clear();return;
  }
  if(message.method==='ui/notifications/tool-result'){
    try{show(message.params);if(!initialRefresh){initialRefresh=true;void refresh();}}catch(e){status(e.message,true);}return;
  }
  if(message.method==='ui/notifications/host-context-changed'){applyTheme(message.params);return;}
  const row=pending.get(message.id);if(!row)return;pending.delete(message.id);clearTimeout(row.timer);
  if(message.error)row.reject(new Error(typeof message.error.message==='string'?message.error.message:'Host refused the operation.'));
  else row.resolve(message.result);
}
window.addEventListener('message',receive);
const observer=new ResizeObserver(()=>{if(initialized&&active)post({jsonrpc:'2.0',method:'ui/notifications/size-changed',params:{height:Math.min(2000,Math.max(80,document.body.scrollHeight))}});});observer.observe(document.body);
rpc('ui/initialize',{protocolVersion:'2026-01-26',appInfo:{name:'learnharness-native',version:'0.1.0-dev'},appCapabilities:{}})
  .then(result=>{if(result?.hostInfo?.name!=='t3-code')throw new Error('This adapter requires the supported T3 MCP App host.');
    applyTheme(result.hostContext);initialized=true;post({jsonrpc:'2.0',method:'ui/notifications/initialized',params:{}});})
  .catch(error=>status(error.message,true));
