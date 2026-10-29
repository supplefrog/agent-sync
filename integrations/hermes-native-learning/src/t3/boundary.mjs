// SPDX-License-Identifier: AGPL-3.0-only
// Supported MCP boundary only. No provider, shell, network or host-setting API.
import fs from 'node:fs';
import path from 'node:path';
import { createHash } from 'node:crypto';
import { loadConfiguration } from '../config.mjs';
import { executeLearningCommand } from '../commands.mjs';
import { readNativeView } from '../inline/host/native-session.mjs';
import { FileSessionStore, requireState } from '../store.mjs';

const object=v=>v!==null&&typeof v==='object'&&!Array.isArray(v);
const canonical=v=>typeof v==='string'&&v.length>0&&v.length<=300&&v===v.trim()&&v!=='new';
const digest=v=>createHash('sha256').update(v).digest('hex');
function fields(value,allowed) {
  requireState(object(value)&&Object.keys(value).every(k=>allowed.includes(k)), 'invalid_input','Unknown or malformed tool argument.');
}
const keyOf=view=>view.kind==='practice'?`${view.chatId}:practice:${view.activeProblem?.toolCallId??'between'}`:
  `${view.chatId}:${view.question?.toolCallId??'idle'}`;
function cleanView(binding) {
  const view=readNativeView(binding,{includeAnswerHistory:true}).view;
  requireState(!view.question||!['correctIndices','committedAnswer','explanation'].some(k=>k in view.question),
    'commitment_exposed','An active question exposed teacher-only fields.');
  requireState(!view.activeProblem||Object.keys(view.activeProblem).every(k=>['toolCallId','statement'].includes(k)),
    'commitment_exposed','An active practice problem exposed teacher-only fields.');
  return view;
}
function draftStore(binding,key) {
  const root=path.join(binding.root,'.t3-drafts');
  if(fs.existsSync(root))requireState(fs.realpathSync(root)===root&&fs.statSync(root).isDirectory(),
    'invalid_draft_root','Private draft root cannot be redirected.');
  return {store:new FileSessionStore(root),id:'draft_'+digest(JSON.stringify([binding.ownerSessionId,binding.chatId,key])).slice(0,48)};
}
function readDraft(binding,key) {
  const {store,id}=draftStore(binding,key);
  if(!fs.existsSync(store.file(id)))return {version:-1,payload:null};
  const r=store.read(id);
  requireState(r.owner===binding.ownerSessionId&&r.chatId===binding.chatId&&r.key===key,'wrong_draft','Draft identity differs.');
  return {version:r.adapter.revision,payload:r.payload??null,baseRevision:r.baseRevision};
}
function readAsset(binding,file) {
  requireState(typeof file==='string'&&/^asset-(demo|visual)-[a-f0-9]{64}\.(html|svg)$/.test(file),'invalid_asset','Use a saved artifact identity.');
  const descriptor=(cleanView(binding).jobs?.jobs??[]).map(j=>j.artifact).find(a=>a?.file===file);
  requireState(descriptor&&Number.isSafeInteger(descriptor.size)&&descriptor.size>0&&descriptor.size<=1048576,
    'unknown_asset','Artifact is not in the current owning lesson.');
  const target=path.join(binding.output,file);
  requireState(fs.realpathSync(target)===target&&fs.statSync(target).isFile(),'invalid_asset','Artifact path cannot be redirected.');
  const fd=fs.openSync(target,'r');
  try {
    const before=fs.fstatSync(fd);
    requireState(before.size===descriptor.size,'asset_changed','Artifact size changed.');
    const bytes=Buffer.alloc(descriptor.size+1);let count=0;
    while(count<bytes.length){const n=fs.readSync(fd,bytes,count,bytes.length-count,null);if(!n)break;count+=n;}
    const after=fs.fstatSync(fd);
    requireState(count===descriptor.size&&after.size===before.size&&after.mtimeMs===before.mtimeMs&&
      after.ino===before.ino&&digest(bytes.subarray(0,count))===descriptor.sha256,'asset_changed','Artifact bytes changed.');
    return {text:new TextDecoder('utf-8',{fatal:true}).decode(bytes.subarray(0,count)),size:count,kind:descriptor.kind};
  } finally {fs.closeSync(fd);}
}

export class T3LearningBoundary {
  constructor(configFile) { this.config=loadConfiguration(configFile); }
  owner(meta) {
    // Codex writes this OUTSIDE model-visible arguments, including on T3 app calls.
    // Never accept an argument, environment alias, initialize.clientInfo or a UI ID as fallback.
    requireState(object(meta)&&canonical(meta.threadId),'caller_unqualified','Host-written MCP _meta.threadId is required.');
    return meta.threadId;
  }
  binding(meta,chatId) {
    const owner=this.owner(meta),matches=this.config.lessons.filter(b=>b.ownerSessionId===owner&&b.chatId===chatId);
    requireState(matches.length===1,'wrong_native_owner','This native Codex thread has no unique enrolled lesson.');
    return Object.freeze({...matches[0],runtimeHost:'t3-codex'});
  }
  catalogue(meta,args) {
    fields(args,[]);const owner=this.owner(meta);
    return this.config.lessons.filter(b=>b.ownerSessionId===owner).map(b=>({chatId:b.chatId,kind:b.kind}));
  }
  view(meta,args) {
    fields(args,['chatId']);const b=this.binding(meta,args.chatId),view=cleanView(b),key=keyOf(view);
    const result={structuredContent:{view},_meta:{ownerThreadId:b.ownerSessionId,draft:readDraft(b,key),draftKey:key}};
    requireState(Buffer.byteLength(JSON.stringify(result))<=240*1024,'view_too_large','This card exceeds the host bridge limit; no truncation.');
    return result;
  }
  command(meta,args) {
    fields(args,['command']);requireState(object(args.command),'invalid_command','Use an explicit learning command.');
    const command=args.command,b=this.binding(meta,command.chatId);
    requireState(!['learner','list'].includes(command.op),'invalid_command','Use the bound input/catalogue tool.');
    return executeLearningCommand(b,command);
  }
  input(meta,args) {
    fields(args,['chatId','kind','expectedRevision','action']);const b=this.binding(meta,args.chatId);
    requireState(args.kind===b.kind,'wrong_session_kind','Input kind differs from enrollment.');
    requireState(Buffer.byteLength(JSON.stringify(args))<=65536,'input_too_large','Input exceeds64KiB; nothing was truncated.');
    // The host supplies ownership; user/model content never does.
    return executeLearningCommand(b,{op:'learner',chatId:b.chatId,envelope:{v:1,ownerSessionId:b.ownerSessionId,
      chatId:b.chatId,kind:b.kind,expectedRevision:args.expectedRevision,action:args.action}});
  }
  draft(meta,args) {
    fields(args,['chatId','key','expectedVersion','baseRevision','payload']);const b=this.binding(meta,args.chatId),view=cleanView(b);
    requireState(args.key===keyOf(view)&&args.baseRevision===view.revision&&Number.isSafeInteger(args.expectedVersion),
      'stale_draft','Reload the current question before saving its draft.');
    requireState(args.payload===null||object(args.payload),'invalid_draft','Draft must be an object or explicit tombstone.');
    requireState(Buffer.byteLength(JSON.stringify(args.payload))<=16384,'draft_too_large','Draft exceeds16KiB.');
    const current=readDraft(b,args.key);
    requireState(current.version===args.expectedVersion,'stale_draft','Another card owns a newer draft; do not overwrite it.');
    requireState(current.baseRevision===undefined||current.baseRevision<=args.baseRevision,'stale_draft','An older lesson revision cannot replace a newer draft.');
    const {store,id}=draftStore(b,args.key);
    const saved=store.change(id,r=>{
      requireState((r?.adapter.revision??-1)===args.expectedVersion,'stale_draft','Draft changed during save.');
      const record=r??{id,version:1,messages:[],adapter:{version:1,revision:-1},owner:b.ownerSessionId,chatId:b.chatId,key:args.key};
      record.payload=args.payload;record.baseRevision=args.baseRevision;
      return {record,result:{saved:true,version:(r?.adapter.revision??-1)+1}};
    },{create:current.version===-1,activity:false});
    return saved;
  }
  asset(meta,args) {fields(args,['chatId','file']);return readAsset(this.binding(meta,args.chatId),args.file);}
}
