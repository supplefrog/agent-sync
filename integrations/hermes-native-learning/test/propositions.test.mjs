// SPDX-License-Identifier: AGPL-3.0-only
// Native v1 source-shaped synthetic catalogues only; no user propositions read.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { createHash } from 'node:crypto';
import { loadConfiguration } from '../src/config.mjs';
import { executeLearningCommand } from '../src/commands.mjs';
import { readNativePropositions } from '../src/propositions.mjs';
import { resolveTargetId } from '../src/vendor/runtime/target-pure.ts';
const hash=f=>createHash('sha256').update(fs.readFileSync(f)).digest('hex');
function fixture(t) {
  const base=fs.mkdtempSync(path.join(os.tmpdir(),'lh-proposition-control-'));t.after(()=>fs.rmSync(base,{recursive:true,force:true}));
  const graph=path.join(base,'graph');fs.mkdirSync(graph);
  const ledger=path.join(graph,'nodes.jsonl');
  const rows=[{id:'n_ratio',name:'Ratio identity',statement:'Synthetic proposition only.',createdAt:'2026-01-01',aliases:[],provenance:[{chatId:'source-fixture',messageId:'message-fixture'}]}];
  const saveRows=items=>fs.writeFileSync(ledger,items.map(x=>JSON.stringify(x)).join('\n')+'\n');saveRows(rows);
  fs.writeFileSync(path.join(graph,'format.json'),JSON.stringify({version:1}));
  const config={version:1,lessons:[{ownerSessionId:'synthetic-owner',chatId:'synthetic-tagged',kind:'practice',stateRoot:'private/state',exportRoot:'exports',graphRoot:'graph'}]};
  const configFile=path.join(base,'bindings.local.json');const saveConfig=()=>fs.writeFileSync(configFile,JSON.stringify(config));saveConfig();
  const binding=loadConfiguration(configFile).lessons[0],run=c=>executeLearningCommand(binding,{chatId:binding.chatId,...c});
  const initialized=run({op:'init',title:'Synthetic tagged practice',goal:'Exercise source boundary'});
  const problem=(view,target)=>run({op:'tool',expectedRevision:view.revision,authorship:'synthetic-fixture',name:'problem',toolCallId:'problem-1',input:{statement:'Synthetic problem.',mode:'recall',modelSolution:'HIDDEN-COMMITMENT',target}});
  return {base,graph,ledger,rows,saveRows,config,configFile,saveConfig,binding,run,initialized,problem};
}
test('fresh enrolled source normalizes known name to ID, retains commitment and never writes graph',t=>{
  const s=fixture(t),before=hash(s.ledger),context=s.run({op:'context'});
  assert.equal(context.context.propositions.nodes[0].id,'n_ratio');
  assert.equal(resolveTargetId(' ratio identity ',context.context.propositions.nodes),'n_ratio');
  const saved=s.problem(s.initialized.view,[' RATIO IDENTITY ']);
  assert.ok(!JSON.stringify(saved.view).includes('HIDDEN-COMMITMENT'));
  const call=s.run({op:'context'}).context.messages.find(m=>m.role==='assistant'&&m.content.some(b=>b.type==='toolCall'&&b.name==='problem')).content[0];
  assert.deepEqual(call.arguments.target,['n_ratio']);assert.equal(hash(s.ledger),before);
});
test('pose validates the current whole catalogue, rejects stale/missing targets and leaves state untouched',t=>{
  const s=fixture(t);s.run({op:'context'});s.saveRows([]);
  assert.throws(()=>s.problem(s.initialized.view,['n_ratio']),e=>e.code==='unknown_proposition');
  assert.equal(s.run({op:'view'}).view.revision,s.initialized.view.revision);
  s.saveRows(s.rows);
  assert.throws(()=>s.problem(s.initialized.view,['ratio']),e=>e.code==='unknown_proposition');
  assert.throws(()=>s.problem(s.initialized.view,['n_ratio',42]),e=>e.code==='invalid_problem');
  assert.equal(s.problem(s.initialized.view,['n_ratio']).ok,true);
});
test('native source parsing preserves first identity and refuses malformed/newer graph data',t=>{
  const s=fixture(t);s.saveRows([...s.rows,{...s.rows[0],name:'Changed display name'}]);
  assert.equal(readNativePropositions(s.graph).nodes[0].name,'Ratio identity');
  fs.appendFileSync(s.ledger,'not-json\n');assert.throws(()=>readNativePropositions(s.graph));
  s.saveRows(s.rows);fs.writeFileSync(path.join(s.graph,'format.json'),'{"version":2}');
  assert.throws(()=>readNativePropositions(s.graph),e=>e.code==='unsupported_graph_version');
});
test('graph enrollment is explicit and cannot overlap mutable state or arrive in problem arguments',t=>{
  const s=fixture(t);
  assert.throws(()=>s.run({op:'tool',expectedRevision:s.initialized.view.revision,authorship:'synthetic-fixture',toolCallId:'problem-1',name:'problem',input:{statement:'S',mode:'recall',modelSolution:'S',target:['n_ratio'],graphRoot:'untrusted'}}),e=>e.code==='invalid_problem');
  s.config.lessons.push({ownerSessionId:'other-owner',chatId:'other-lesson',kind:'teach',stateRoot:'graph/raw',exportRoot:'exports-other'});
  s.saveConfig();assert.throws(()=>loadConfiguration(s.configFile),e=>e.code==='invalid_config');s.config.lessons.pop();
  s.config.lessons[0].stateRoot='graph/state';s.saveConfig();assert.throws(()=>loadConfiguration(s.configFile));
  delete s.config.lessons[0].graphRoot;s.config.lessons[0].stateRoot='private/state';s.saveConfig();
  const noGraph=loadConfiguration(s.configFile).lessons[0];
  assert.throws(()=>executeLearningCommand(noGraph,{op:'tool',chatId:noGraph.chatId,expectedRevision:s.initialized.view.revision,authorship:'synthetic-fixture',toolCallId:'problem-1',name:'problem',input:{statement:'S',mode:'recall',modelSolution:'S',target:['n_ratio']}}),e=>e.code==='graph_unavailable');
});
