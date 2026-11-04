// SPDX-License-Identifier: AGPL-3.0-only
// Teacher-authored lesson artifacts, independent of worker/provider execution.
import fs from 'node:fs';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {FileSessionStore,requireState} from './store.mjs';
import {activeProblemOf} from './vendor/runtime/practice-pure.ts';
const hash=source=>createHash('sha256').update(source).digest('hex');
export function attachVisual(binding,command) {
  requireState(Number.isSafeInteger(command.expectedRevision)&&command.authorship==='host-agent'&&
    /^[A-Za-z0-9_-]{1,80}$/.test(command.id??'')&&typeof command.title==='string'&&command.title.trim()&&command.title.length<=300&&
    ['html-fragment','svg'].includes(command.format)&&typeof command.source==='string'&&command.source.trim()&&
    Buffer.byteLength(command.source)<=204800&&['now','after-question'].includes(command.reveal)&&
    Buffer.byteLength(JSON.stringify({text:command.source,size:Buffer.byteLength(command.source),kind:command.format==='svg'?'visual':'demo'}))<=230*1024,
    'invalid_visual','Use a bounded teacher-authored HTML fragment or SVG with explicit reveal timing.');
  requireState(command.format==='svg'?/^\s*<svg[\s>]/i.test(command.source):!/<\/?(?:html|head|body)\b|<!doctype/i.test(command.source),
    'invalid_visual','Use an SVG root or an HTML fragment, not a complete document.');
  const store=new FileSessionStore(binding.root);
  return store.change(binding.chatId,record=>{
    requireState(record.adapter.revision===command.expectedRevision,'stale_native_revision','Reload before attaching a visual.');
    // Teaching questions are resolved by their actual tool result, not UI state.
    const pending=record.messages.filter(m=>m.role==='assistant').flatMap(m=>m.content??[]).filter(b=>b.type==='toolCall'&&
      ['ask','probe','recall','quiz','explain'].includes(b.name)&&!record.messages.some(m=>m.role==='toolResult'&&m.toolCallId===b.id)).at(-1)?.id;
    const anchor=binding.kind==='practice'?activeProblemOf(record.messages)?.toolCallId:pending;
    requireState(command.reveal==='now'||anchor,'invalid_visual','Deferred reveal requires a question or practice problem.');
    const row={id:command.id,title:command.title.trim(),format:command.format,source:command.source,sha256:hash(command.source),
      reveal:command.reveal,...(command.reveal==='after-question'?{questionId:anchor}: {})};
    const visuals=record.adapter.visuals??[],old=visuals.find(v=>v.id===row.id);
    requireState(!old||JSON.stringify(old)===JSON.stringify(row),'visual_identity_conflict','A saved visual ID is immutable; use a new ID for changed content.');
    requireState(old||visuals.length<8,'visual_limit','This lesson already has eight saved visuals.');
    if(!old)record.adapter.visuals=[...visuals,row];
    return {record,changed:!old,result:{ok:true,visualId:row.id}};
  });
}
function visible(row,record) {
  if(row.reveal==='now')return true;
  if(record.kind!=='practice')return record.messages.some(m=>m.role==='toolResult'&&m.toolCallId===row.questionId);
  const anchor=record.messages.findIndex(m=>m.role==='assistant'&&(m.content??[]).some(b=>b.id===row.questionId));
  return anchor>=0&&record.messages.slice(anchor+1).some(m=>m.role==='assistant'&&(m.content??[]).some(b=>b.type==='toolCall'&&b.name==='conclude'));
}
export function visualDescriptors(record) {
  return (record.adapter.visuals??[]).filter(row=>visible(row,record)).map(row=>{
    const kind=row.format==='svg'?'visual':'demo';
    return {id:row.id,title:row.title,format:row.format,kind,sha256:row.sha256,size:Buffer.byteLength(row.source),
      file:`asset-${kind}-${row.sha256}.${kind==='visual'?'svg':'html'}`};
  });
}
export function publishVisualAssets(binding,record) {
  const descriptors=visualDescriptors(record);
  if(!descriptors.length)return;
  fs.mkdirSync(binding.output,{recursive:true});
  requireState(fs.realpathSync(binding.output)===binding.output,'invalid_visual_path','Export directory cannot be redirected.');
  for(const descriptor of descriptors) {
    const source=record.adapter.visuals.find(row=>row.id===descriptor.id).source;
    requireState(hash(source)===descriptor.sha256,'visual_changed','Saved visual digest differs.');
    const file=path.join(binding.output,descriptor.file);
    try{fs.writeFileSync(file,source,{flag:'wx'});}
    catch(error){if(error.code!=='EEXIST')throw error;
      requireState(fs.realpathSync(file)===file&&fs.lstatSync(file).isFile()&&hash(fs.readFileSync(file))===descriptor.sha256,
        'visual_changed','Existing export differs; never overwrite it.');}
  }
}
