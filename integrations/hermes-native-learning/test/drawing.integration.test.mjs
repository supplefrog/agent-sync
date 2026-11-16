// SPDX-License-Identifier: AGPL-3.0-only
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import {executeLearningCommand} from '../src/commands.mjs';
import {T3LearningBoundary} from '../src/t3/boundary.mjs';
import {handleLearningTool} from '../src/t3/server.mjs';
import {loadConfiguration} from '../src/config.mjs';

for(const kind of ['teach','practice'])test('saved drawing stays bound to the learner response in '+kind,t=>{
  const tmp=fs.realpathSync(os.tmpdir()),dir=fs.mkdtempSync(path.join(tmp,'lh-drawn-'));
  t.after(()=>{assert.equal(path.dirname(fs.realpathSync(dir)),tmp);fs.rmSync(dir,{recursive:true,force:true});});
  const chatId='drawing-case',ownerSessionId='draw-owner',cfg=path.join(dir,'config.json');
  fs.writeFileSync(cfg,JSON.stringify({version:1,lessons:[{chatId,ownerSessionId,kind,stateRoot:'state',exportRoot:'exports'}]}));
  const boundary=new T3LearningBoundary(cfg),binding=loadConfiguration(cfg).lessons[0];
  const run=command=>executeLearningCommand(binding,{chatId,...command});
  const call=(name,args,threadId=ownerSessionId)=>handleLearningTool(boundary,{params:{name,arguments:{chatId,...args},_meta:{threadId}}});
  const created=run({op:'init',title:'Draw reasoning',goal:'Sketch the work'});
  const prompt=run({op:'tool',expectedRevision:created.view.revision,authorship:'synthetic-fixture',toolCallId:'draw',
    ...(kind==='practice'?{name:'problem',input:{statement:'Show the slope.',mode:'recall',modelSolution:'Use rise over run.'}}:
      {name:'probe',input:{question:'How did you draw the slope?',options:[{label:'Use rise over run',value:'slope'},
        {label:'Use only the run',value:'run'}],correctAnswer:'slope',explanation:'Compare both changes.'}})});
  const drawing=[[[200,500,2],[390,500,4],[390,240,8]]];
  const submit=(strokes,revision=prompt.view.revision)=>call('learning_input',{kind,expectedRevision:revision,action:
    kind==='practice'?{chatId,type:'practice-input',input:{type:'thinking',problemCallId:'draw',text:'Rise over run.',drawing:strokes}}:
      {chatId,type:'answer',toolCallId:'draw',request:{values:['slope'],thinking:'Rise over run.',drawing:strokes}}});
  assert.throws(()=>submit([[[9999,1,5]]]),error=>error.code==='invalid_drawing');
  assert.throws(()=>submit(drawing,prompt.view.revision-1),error=>error.code==='stale_native_revision');
  submit(drawing);
  const reopened=call('learning_view',{}).structuredContent.view;
  const saved=kind==='practice'?reopened.drawings.at(-1).drawing:reopened.answers.at(-1).drawing;
  assert.deepEqual(saved,drawing);
  const context=run({op:'context-page'}).context.messages;
  const response=context.find(message=>JSON.stringify(message.content).includes('Learner drawing attached'));
  assert.ok(response);
  const image=call('learning_drawing',{messageId:response.id}).content[0];
  assert.equal(image.mimeType,'image/png');
  const png=Buffer.from(image.data,'base64');
  assert.equal(png.subarray(0,8).toString('hex'),'89504e470d0a1a0a');
  assert.ok(png.length>300);
  assert.throws(()=>call('learning_drawing',{messageId:response.id},'another-owner'));
});

test('a combined coding and drawing draft fits, and older attempts stay retrievable after reopen',t=>{
  const tmp=fs.realpathSync(os.tmpdir()),dir=fs.mkdtempSync(path.join(tmp,'lh-history-'));
  t.after(()=>{assert.equal(path.dirname(fs.realpathSync(dir)),tmp);fs.rmSync(dir,{recursive:true,force:true});});
  const chatId='history-case',ownerSessionId='history-owner',cfg=path.join(dir,'config.json');
  fs.writeFileSync(cfg,JSON.stringify({version:1,lessons:[{chatId,ownerSessionId,kind:'practice',stateRoot:'state',exportRoot:'exports'}]}));
  const boundary=new T3LearningBoundary(cfg),binding=loadConfiguration(cfg).lessons[0];
  const run=command=>executeLearningCommand(binding,{chatId,...command});
  const call=(name,args={})=>handleLearningTool(boundary,{params:{name,arguments:{chatId,...args},_meta:{threadId:ownerSessionId}}});
  const initial=run({op:'init',title:'Long exercise',goal:'Save retries'});
  const committed='const value=42;';
  run({op:'tool',name:'problem',toolCallId:'code',authorship:'synthetic-fixture',expectedRevision:initial.view.revision,
    input:{statement:'Write some JavaScript.',mode:'composition',modelSolution:committed,coding:{language:'javascript',solution:committed}}});
  const original=call('learning_view').structuredContent.view;
  const strokes=[Array.from({length:320},(_,i)=>[100+i,300+i%100,7])];
  const code='const value=42; // '+'x'.repeat(7900);
  const payload={key:`${chatId}:practice:code`,text:'x'.repeat(5000),code,drawing:strokes,open:true};
  assert.ok(Buffer.byteLength(JSON.stringify(payload))>16*1024);
  call('learning_draft',{key:payload.key,expectedVersion:-1,baseRevision:original.revision,payload});
  assert.deepEqual(call('learning_view')._meta.draft.payload,payload);
  for(let index=0;index<11;index++){
    const view=run({op:'view'}).view;
    call('learning_input',{kind:'practice',expectedRevision:view.revision,
      action:{type:'practice-input',chatId,input:{type:'thinking',problemCallId:'code',text:'Attempt '+index,code,drawing:strokes}}});
  }
  const result=call('learning_view'),view=result.structuredContent.view;
  assert.ok(Buffer.byteLength(JSON.stringify(result))<=256*1024);
  assert.equal(view.thinking.at(-1),'Attempt 10');
  assert.ok(view.earlierResponses);
  const history=[...view.thinking];
  let cursor=view.earlierResponses;
  while(cursor) {
    const page=call('learning_practice_history',{...cursor,expectedRevision:view.revision}).structuredContent;
    assert.ok(page.rows.every(row=>row.coding.code===code&&JSON.stringify(row.drawing)===JSON.stringify(strokes)));
    history.unshift(...page.rows.map(row=>row.text));
    cursor=page.nextBefore?{problemId:page.problemId,before:page.nextBefore}:null;
  }
  assert.deepEqual(history,Array.from({length:11},(_,i)=>'Attempt '+i));
  assert.throws(()=>call('learning_practice_history',{...view.earlierResponses,expectedRevision:view.revision-1}),
    {code:'stale_native_revision'});
});
