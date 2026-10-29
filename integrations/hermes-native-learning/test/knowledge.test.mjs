// SPDX-License-Identifier: AGPL-3.0-only
// Synthetic source correctness checks, not model/extractor quality evaluation.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { LessonKnowledge } from '../src/knowledge.mjs';
import { loadConfiguration } from '../src/config.mjs';
import { executeLearningCommand } from '../src/commands.mjs';
const owner='synthetic-owner';
function setup(t) {
  const temporary=fs.realpathSync(os.tmpdir()),base=fs.mkdtempSync(path.join(temporary,'lh-knowledge-'));
  t.after(()=>{assert.equal(path.dirname(base),temporary);fs.rmSync(base,{recursive:true,force:true});});
  const knowledge=new LessonKnowledge(path.join(base,'knowledge'));
  const lesson={id:'synthetic-teaching',kind:'teach',adapter:{revision:0},messages:[
    {id:'teacher-a',role:'assistant',content:[{type:'text',text:'A ratio compares two quantities.'}]},
    {id:'learner',role:'user',content:'PRIVATE_LEARNER_REASONING'},
    {id:'pending',role:'assistant',content:[{type:'toolCall',name:'quiz',arguments:{correctAnswer:'COMMITMENT_SECRET'}}]},
    {id:'result',role:'toolResult',content:[{type:'text',text:'PRIVATE_ANSWER'}]},
    {id:'teacher-b',role:'assistant',content:[{type:'text',text:'An average rate is a ratio of changes.'}]},
  ]};
  const findings={propositions:[
    {id:'p1',name:'Ratio',statement:'A ratio compares two quantities.',aliases:[],messageId:'teacher-a'},
    {id:'p2',name:'Average rate',statement:'An average rate is a ratio of changes.',aliases:[],messageId:'teacher-b'},
  ],chains:[{premises:['p1'],conclusion:'p2'}]};
  const prepare=(budget=8000)=>knowledge.prepare(lesson,{ownerSessionId:owner,expectedRevision:0,budget});
  const submit=(batchId,input=findings)=>knowledge.findings(lesson,{ownerSessionId:owner,batchId,findings:input,authorship:'synthetic-fixture'});
  const merge=(batchId,verdicts={links:[]},graphRevision=knowledge.audit(lesson,{ownerSessionId:owner,batchId}).graphRevision)=>
    knowledge.merge(lesson,{ownerSessionId:owner,batchId,graphRevision,verdicts,authorship:'synthetic-fixture'});
  return{base,knowledge,lesson,findings,prepare,submit,merge};
}
test('teacher-only coverage, audited merger, provenance, durable reopen and replay-safe commit compose',t=>{
  const s=setup(t),prepared=s.prepare();
  assert.equal(prepared.source.length,2);
  assert.ok(!JSON.stringify(prepared).match(/PRIVATE_|COMMITMENT_SECRET/));
  s.submit(prepared.batchId);
  const audit=s.knowledge.audit(s.lesson,{ownerSessionId:owner,batchId:prepared.batchId});
  assert.equal(audit.source,undefined);assert.equal(audit.chains,undefined);
  assert.equal(audit.propositions[0].messageId,undefined);
  const merged=s.merge(prepared.batchId);
  assert.equal(merged.stats.nodes,2);assert.equal(merged.stats.chains,1);
  const original=fs.readFileSync(s.knowledge.store.file('knowledge'));
  assert.equal(s.merge(prepared.batchId).alreadyMerged,true);
  assert.deepEqual(fs.readFileSync(s.knowledge.store.file('knowledge')),original);
  const reopened=new LessonKnowledge(s.knowledge.store.root);
  assert.equal(reopened.graph().nodes.length,2);assert.equal(reopened.graph().chains.length,1);
  assert.equal(reopened.status(s.lesson).uncoveredCount,0);
  const page=reopened.query({limit:1});assert.equal(page.nodes.length,1);assert.equal(page.nextOffset,1);
  const next=reopened.query({limit:1,offset:page.nextOffset,graphRevision:page.graphRevision});
  assert.notEqual(next.nodes[0].id,page.nodes[0].id);assert.equal(next.nextOffset,null);
  assert.throws(()=>reopened.query({offset:1,graphRevision:999}),error=>error.code==='stale_graph');
  assert.equal(reopened.query({query:'ratio'}).total,2);
  assert.equal(reopened.lessonView(s.lesson).nodes[0].passages.length,1);
  assert.ok(!JSON.stringify(reopened.read()).includes('PRIVATE_LEARNER_REASONING'));
  const altered=structuredClone(s.lesson);altered.messages[1].content='DIFFERENT_PRIVATE_REASONING';
  assert.equal(reopened.status(altered).uncoveredCount,0);
  altered.messages[0].content[0].text+=' More precision.';
  assert.equal(reopened.status(altered).uncoveredCount,1);
});
test('owner/source/audit revision and identity guards refuse stale or invented evidence',t=>{
  const s=setup(t),prepared=s.prepare();
  assert.throws(()=>s.knowledge.findings(s.lesson,{ownerSessionId:'wrong',batchId:prepared.batchId,findings:s.findings,authorship:'synthetic-fixture'}));
  const bad=structuredClone(s.findings);bad.propositions[0].messageId='learner';
  assert.throws(()=>s.submit(prepared.batchId,bad));
  s.submit(prepared.batchId);
  assert.throws(()=>s.merge(prepared.batchId,{links:[{id:'p1',linkTo:'invented'}]}));
  assert.throws(()=>s.merge(prepared.batchId,{links:[]},999));
  s.lesson.messages[0].content[0].text+=' Changed source.';
  assert.throws(()=>s.merge(prepared.batchId),error=>error.code==='stale_extraction');
});
test('overlapping unfinished extraction batches cannot duplicate already-covered source',t=>{
  const s=setup(t),first=s.prepare(1),overlap=s.prepare(8000);
  s.submit(first.batchId,{propositions:[s.findings.propositions[0]],chains:[]});
  s.submit(overlap.batchId);s.merge(first.batchId);
  assert.throws(()=>s.merge(overlap.batchId),error=>error.code==='stale_extraction');
  assert.equal(s.knowledge.graph().nodes.length,1);
  assert.equal(s.knowledge.status(s.lesson).uncoveredCount,1);
});
test('identity links merge reencounters, and practice consumes the saved fresh graph',t=>{
  const s=setup(t),batch=s.prepare();s.submit(batch.batchId);s.merge(batch.batchId);
  const first=s.knowledge.graph().nodes.find(node=>node.name==='Ratio');
  const later={id:'another-teaching',adapter:{revision:0},messages:[{id:'another-passage',role:'assistant',content:[{type:'text',text:'A ratio compares quantities.'}]}]};
  const p=s.knowledge.prepare(later,{ownerSessionId:owner,expectedRevision:0});
  s.knowledge.findings(later,{ownerSessionId:owner,batchId:p.batchId,authorship:'synthetic-fixture',findings:{propositions:[
    {id:'q1',name:'Comparison',statement:'A ratio compares quantities.',aliases:[],messageId:'another-passage'}],chains:[]}});
  const audit=s.knowledge.audit(later,{ownerSessionId:owner,batchId:p.batchId});
  s.knowledge.merge(later,{ownerSessionId:owner,batchId:p.batchId,graphRevision:audit.graphRevision,verdicts:{links:[{id:'q1',linkTo:first.id}]},authorship:'synthetic-fixture'});
  assert.equal(s.knowledge.graph().nodes.length,2);
  assert.ok(s.knowledge.graph().nodes.find(node=>node.id===first.id).provenance.some(point=>point.chatId===later.id));
  const binding={ownerSessionId:owner,chatId:'synthetic-practice',kind:'practice',root:path.join(s.base,'practice'),output:path.join(s.base,'exports'),knowledgeRoot:s.knowledge.store.root};
  const run=command=>executeLearningCommand(binding,{chatId:binding.chatId,...command});
  const created=run({op:'init',title:'Synthetic only',goal:'Verify graph targeting'});
  const problem=run({op:'tool',name:'problem',toolCallId:'problem1',expectedRevision:created.view.revision,authorship:'synthetic-fixture',
    input:{statement:'Compare two quantities.',mode:'recall',modelSolution:'The solution stays hidden.',target:['Ratio']}});
  assert.equal(problem.view.activeProblem.statement,'Compare two quantities.');
  assert.ok(!JSON.stringify(problem.view).includes('The solution stays hidden.'));
  assert.throws(()=>run({op:'knowledge',action:'prepare',expectedRevision:problem.view.revision}),error=>error.code==='wrong_session_kind');
});
test('knowledge enrollment is optional, private and physically separate from every export',t=>{
  const s=setup(t),file=path.join(s.base,'bindings.json');
  const config={version:1,lessons:[{ownerSessionId:owner,chatId:'a',kind:'teach',stateRoot:'state',exportRoot:'exports',knowledgeRoot:'private-knowledge'}]};
  const save=()=>fs.writeFileSync(file,JSON.stringify(config));save();
  assert.equal(loadConfiguration(file).lessons[0].knowledgeRoot,path.join(s.base,'private-knowledge'));
  for(const bad of ['exports/graph','state','../outside']){config.lessons[0].knowledgeRoot=bad;save();assert.throws(()=>loadConfiguration(file));}
});
