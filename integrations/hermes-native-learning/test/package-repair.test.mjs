// SPDX-License-Identifier: AGPL-3.0-only
// Synthetic filesystem and controlled SDK-promise contracts, not native loading.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { createHash } from 'node:crypto';
import { loadConfiguration } from '../src/config.mjs';
import { connectLessonExport } from '../src/connect-export.mjs';
import { verifyProjectionBytes } from '../src/inline/hermes-contribution.mjs';
function files(t) {
  const base=fs.mkdtempSync(path.join(os.tmpdir(),'lh-physical-control-'));
  t.after(()=>{const rel=path.relative(os.tmpdir(),base);assert.ok(rel&&!path.isAbsolute(rel)&&rel!=='..'&&!rel.startsWith('..'+path.sep));fs.rmSync(base,{recursive:true,force:true});});
  const file=path.join(base,'bindings.local.json');
  const row=(id,stateRoot,exportRoot)=>({ownerSessionId:'owner-'+id,chatId:id,kind:'teach',stateRoot,exportRoot});
  const read=lessons=>{fs.writeFileSync(file,JSON.stringify({version:1,lessons}));return loadConfiguration(file);};
  return{base,row,read};
}
test('physical aliases including missing suffix cannot expose raw state as exports',t=>{
  const s=files(t),raw=path.join(s.base,'private/state'),alias=path.join(s.base,'export-alias');
  fs.mkdirSync(raw,{recursive:true});fs.symlinkSync(raw,alias,'junction');
  assert.throws(()=>s.read([s.row('a','private/state','export-alias')]),e=>e.code==='invalid_config');
  assert.throws(()=>s.read([s.row('a','private/state/future','export-alias/future')]),e=>e.code==='invalid_config');
});
test('every export root is checked against every lesson state in both containment directions',t=>{
  const s=files(t);
  assert.throws(()=>s.read([s.row('a','private/a','exports/a'),s.row('b','exports/a/raw','exports/b')]),e=>e.code==='invalid_config');
  assert.throws(()=>s.read([s.row('a','private/a','private/b/exports'),s.row('b','private/b','exports/b')]),e=>e.code==='invalid_config');
});
test('valid disjoint physical destinations and shared raw store remain supported',t=>{
  const s=files(t),realExport=path.join(s.base,'actual-exports');fs.mkdirSync(realExport);
  fs.symlinkSync(realExport,path.join(s.base,'export-alias'),'junction');
  const config=s.read([s.row('a','private/shared','export-alias/a'),s.row('b','private/shared','exports/b')]);
  assert.equal(config.lessons[0].output,path.join(fs.realpathSync(realExport),'a'));
  assert.equal(config.lessons[0].root,config.lessons[1].root);
});
function deferred(){let resolve;const promise=new Promise(r=>{resolve=r;});return{promise,resolve};}
function connectFixture(stage) {
  const gate=deferred(),reached=deferred(),view={chatId:'synthetic-connect',revision:1};
  const text=JSON.stringify(view),snapshot='teach-r1-'+createHash('sha256').update(text).digest('hex')+'.json';
  let current=true,rows=[],writes=0,registrations=0,reads=0;
  const wait=async(name,result)=>{if(stage===name){reached.resolve();await gate.promise;}return result;};
  const ctx={files:{requestFolder:()=>wait('picker',{ok:true,folder:{id:'opaque-folder'}}),
    readText:()=>{reads++;return wait('read',{ok:true,text});}},storage:{get:()=>structuredClone(rows),set:(key,value)=>{writes++;rows=structuredClone(value);}}};
  const options={isCurrent:()=>current,verifyBytes:async(...args)=>{await verifyProjectionBytes(...args);await wait('digest',null);},
    install:()=>{registrations++;return true;}};
  return{ctx,options,identity:{owner:'synthetic-owner',chatId:view.chatId,snapshot},gate,reached,
    cancel:()=>{current=false;},counts:()=>({writes,registrations,reads})};
}
for(const stage of ['picker','read','digest'])test('cancelled/unmounted Connect cannot persist or register after '+stage,async()=>{
  const s=connectFixture(stage),pending=connectLessonExport(s.ctx,s.identity,s.options);
  await s.reached.promise;s.cancel();s.gate.resolve();const result=await pending;
  assert.equal(result.cancelled,true);assert.equal(s.counts().writes,0);assert.equal(s.counts().registrations,0);
  if(stage==='picker')assert.equal(s.counts().reads,0);
});
test('current Connect validates real digest then persists and registers exactly once',async()=>{
  const s=connectFixture(null),result=await connectLessonExport(s.ctx,s.identity,s.options);
  assert.equal(result.connected,true);assert.deepEqual(s.counts(),{writes:1,registrations:1,reads:1});
});
test('disposal during a synchronous storage commit prevents subsequent registration',async()=>{
  const s=connectFixture(null),set=s.ctx.storage.set;s.ctx.storage.set=(...args)=>{set(...args);s.cancel();};
  const result=await connectLessonExport(s.ctx,s.identity,s.options);
  assert.equal(result.cancelled,true);assert.equal(s.counts().writes,1);assert.equal(s.counts().registrations,0);
});
