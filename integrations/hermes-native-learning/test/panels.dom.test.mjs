// SPDX-License-Identifier: AGPL-3.0-only
// Actual DOM lifecycle regression; not a loaded Hermes/rendering acceptance test.
import test from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import { createRequire } from 'node:module';
import { mountInline } from '../src/inline/inline-client.mjs';
const require=createRequire(process.env.LH_TEST_TOOLCHAIN?path.join(path.resolve(process.env.LH_TEST_TOOLCHAIN),'package.json'):import.meta.url);
const {JSDOM}=require('jsdom');
function view(question=null) {
  return{chatId:'synthetic-panels',revision:1,phase:'teach',answers:[],question,
    assessment:{summary:'Synthetic starting point',strands:[{strand:'Ratio',assessment:'Synthetic edge'}]},
    knowledge:{scope:'Teacher propositions, not mastery',nodes:[{id:'n_one',name:'Ratio',statement:'A ratio compares quantities.',passages:['Synthetic source passage']}]}};
}
test('N1 panels exist once with no question and while the question is closed',t=>{
  const dom=new JSDOM('<main></main>');t.after(()=>dom.window.close());const root=dom.window.document.querySelector('main');
  const controller=mountInline(root,view(),{send:async()=>({delivered:true})});
  assert.equal(root.querySelectorAll('[data-assessment]').length,1);assert.equal(root.querySelectorAll('[data-knowledge]').length,1);
  controller.applyView(view({toolCallId:'pending',question:'Synthetic pending question',mode:'text',kind:'explain',options:[],open:false,needsReveal:false}));
  assert.equal(root.querySelectorAll('[data-assessment]').length,1);assert.equal(root.querySelectorAll('[data-knowledge]').length,1);
  controller.destroy();
});
test('N1 repeated typing never appends or duplicates lesson panels',t=>{
  const dom=new JSDOM('<main></main>');t.after(()=>dom.window.close());const root=dom.window.document.querySelector('main');
  const controller=mountInline(root,view({toolCallId:'pending',question:'Synthetic pending question',mode:'text',kind:'explain',options:[],open:true,needsReveal:false}),
    {send:async()=>({delivered:true})});
  const input=root.querySelector('[data-field="text"]');assert.ok(input);
  for(const text of ['a','ab','abc','','again']){
    input.value=text;input.dispatchEvent(new dom.window.Event('input',{bubbles:true}));
    assert.equal(root.querySelectorAll('[data-assessment]').length,1);assert.equal(root.querySelectorAll('[data-knowledge]').length,1);
  }
  controller.destroy();
});
