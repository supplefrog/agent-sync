// SPDX-License-Identifier: AGPL-3.0-only
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {createRequire} from 'node:module';
import {executeLearningCommand} from '../src/commands.mjs';
import {loadConfiguration} from '../src/config.mjs';
import {T3LearningBoundary} from '../src/t3/boundary.mjs';
import {renderInline} from '../src/inline/build-inline.mjs';
function fixture(t){
  const base=fs.mkdtempSync(path.join(os.tmpdir(),'lh-native-visuals-'));
  t.after(()=>fs.rmSync(base,{recursive:true,force:true}));
  const file=path.join(base,'bindings.json');
  fs.writeFileSync(file,JSON.stringify({version:1,lessons:[{ownerSessionId:'owner',chatId:'trial',kind:'practice',stateRoot:'state',exportRoot:'exports'}]}));
  const binding=loadConfiguration(file).lessons[0],run=cmd=>executeLearningCommand(binding,{chatId:'trial',...cmd});
  run({op:'init',title:'Trial',goal:'Transport control'});
  run({op:'tool',expectedRevision:1,authorship:'host-agent',name:'problem',toolCallId:'problem1',input:{statement:'Explain the grouping.',mode:'recall',modelSolution:'PRIVATE_COMMITTED_SOLUTION'}});
  return{binding,run,boundary:new T3LearningBoundary(file)};
}
const visual=(revision,reveal='now')=>({op:'visual',expectedRevision:revision,authorship:'host-agent',id:'groups',title:'Grouping explorer',format:'html-fragment',source:'<div id="group-explorer">Explore groups</div><script>document.getElementById("group-explorer").dataset.ready="yes";</script>',reveal});
test('teacher visual persists and is accessible only through its bound published identity',t=>{
  const s=fixture(t),r=s.run(visual(2));assert.equal(r.view.revision,3);
  const v=s.boundary.view({threadId:'owner'},{chatId:'trial'}).structuredContent.view;
  assert.equal(v.visuals[0].title,'Grouping explorer');assert.ok(!JSON.stringify(v).includes('PRIVATE_COMMITTED_SOLUTION'));
  assert.equal(s.boundary.asset({threadId:'owner'},{chatId:'trial',file:v.visuals[0].file}).text,visual(2).source);
  assert.throws(()=>s.boundary.view({threadId:'foreign'},{chatId:'trial'}));
  assert.throws(()=>s.run(visual(2)),e=>e.code==='stale_native_revision');
  fs.writeFileSync(path.join(s.binding.output,v.visuals[0].file),'changed');
  assert.throws(()=>s.boundary.asset({threadId:'owner'},{chatId:'trial',file:v.visuals[0].file}));
});
test('deferred visual stays out of public views, native HTML and asset reads until conclusion',t=>{
  const s=fixture(t),r=s.run(visual(2,'after-question'));
  let view=s.boundary.view({threadId:'owner'},{chatId:'trial'});
  assert.deepEqual(view.structuredContent.view.visuals,[]);
  assert.ok(!fs.readFileSync(view.nativePresentation.path,'utf8').includes('group-explorer'));
  s.run({op:'tool',expectedRevision:r.view.revision,authorship:'host-agent',name:'conclude',toolCallId:'conclude1',input:{outcome:'movedOn',verdict:'Fixture conclusion',rung:null,missClass:null,retest:false}});
  view=s.boundary.view({threadId:'owner'},{chatId:'trial'});
  assert.equal(view.structuredContent.view.visuals.length,1);
  const revision=view.structuredContent.view.revision;
  assert.throws(()=>s.run({...visual(revision,'after-question'),id:'late'}),e=>e.code==='invalid_visual');
  assert.equal(s.boundary.view({threadId:'owner'},{chatId:'trial'}).structuredContent.view.revision,revision);
});
test('oversized raw or escaped visual payloads refuse before saving lesson state',t=>{
  const s=fixture(t);
  for(const source of ['<svg>'+ 'x'.repeat(250000)+'</svg>','<svg>'+ '\\'.repeat(130000)+'</svg>'])
    assert.throws(()=>s.run({...visual(2),format:'svg',source}),e=>e.code==='invalid_visual');
  assert.equal(s.boundary.view({threadId:'owner'},{chatId:'trial'}).structuredContent.view.revision,2);
});
test('native fragment mounts the real controls and emits exact revision-bound input without claiming persistence',async t=>{
  const s=fixture(t);s.run(visual(2));
  const r=s.boundary.view({threadId:'owner'},{chatId:'trial'}),html=fs.readFileSync(r.nativePresentation.path,'utf8');
  assert.ok(!html.includes('PRIVATE_COMMITTED_SOLUTION'));
  const require=createRequire(path.join(process.env.LH_TEST_TOOLCHAIN,'package.json')),{JSDOM}=require('jsdom');
  const dom=new JSDOM(html,{runScripts:'dangerously'});t.after(()=>dom.window.close());
  const prompts=[];dom.window.openai={sendFollowUpMessage:async value=>{prompts.push(value);}};
  // Module scripts are not executed by jsdom; evaluate the actual exported module body.
  const script=[...dom.window.document.scripts].find(e=>e.type==='module');
  dom.window.eval(script.textContent.replace(/^export /gm,''));
  const dock=dom.window.document.querySelector('.lh-dock');
  assert.equal(dock.querySelector('#group-explorer').dataset.ready,'yes');
  assert.ok(dock.querySelector('#lh-native-exploration'));
  const field=dom.window.document.querySelector('[data-practice-thinking]')??dom.window.document.querySelector('textarea');
  assert.ok(field);field.value='My exact reasoning';field.dispatchEvent(new dom.window.Event('input',{bubbles:true}));
  dom.window.document.querySelector('[data-practice-send]').click();await new Promise(resolve=>setTimeout(resolve,0));
  assert.equal(prompts.length,1);const envelope=JSON.parse(prompts[0].prompt.slice('lh.t3 '.length));
  dom.window.document.querySelector('[data-practice-send]').click();
  assert.equal(prompts.length,1,'Pending native request must not request a duplicate message');
  assert.equal(envelope.expectedRevision,3);assert.equal(envelope.action.input.text,'My exact reasoning');
  assert.equal(envelope.action.input.problemCallId,'problem1');assert.ok(!('ownerSessionId' in envelope));
  assert.match(dom.window.document.querySelector('[data-status]').textContent,/requested/i);
  assert.ok(!/saved\./i.test(dom.window.document.querySelector('[data-status]').textContent));
  assert.equal(s.boundary.view({threadId:'owner'},{chatId:'trial'}).structuredContent.view.revision,3);
  const saved=s.boundary.input({threadId:'owner'},envelope);assert.equal(saved.persisted,true);
  assert.throws(()=>s.boundary.input({threadId:'owner'},envelope),e=>e.code==='stale_native_revision');
  assert.deepEqual(s.boundary.view({threadId:'owner'},{chatId:'trial'}).structuredContent.view.thinking,['My exact reasoning']);
});
