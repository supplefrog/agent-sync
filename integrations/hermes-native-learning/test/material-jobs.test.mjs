// SPDX-License-Identifier: AGPL-3.0-only
// Synthetic contract tests, not live worker, provider, PDF quality or UI proof.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {loadConfiguration} from '../src/config.mjs';
import {executeLearningCommand} from '../src/commands.mjs';
import {LessonJobs,jobArtifactDescriptors,publishJobAssets} from '../src/jobs.mjs';
import {LessonKnowledge} from '../src/knowledge.mjs';
import {FileSessionStore} from '../src/store.mjs';
import {inspectMaterial} from '../src/materials.mjs';
import {readArtifact,demoDocument} from '../src/inline/artifacts.mjs';
function setup(t,notes='A ratio compares two quantities.') {
  const temporary=fs.realpathSync(os.tmpdir()),base=fs.mkdtempSync(path.join(temporary,'lh-material-jobs-'));
  t.after(()=>{assert.equal(path.dirname(base),temporary);fs.rmSync(base,{recursive:true,force:true});});
  fs.writeFileSync(path.join(base,'notes.md'),notes);fs.writeFileSync(path.join(base,'source.pdf'),'%PDF-1.7\nsynthetic bytes only');
  const file=path.join(base,'bindings.local.json'),config={version:1,lessons:[{ownerSessionId:'synthetic-owner',chatId:'synthetic-lesson',kind:'teach',stateRoot:'state',exportRoot:'exports',knowledgeRoot:'knowledge',jobRoot:'jobs',
    materials:[{id:'notes',label:'Enrolled notes',kind:'notes',file:'notes.md'},{id:'pdf',label:'Enrolled PDF',kind:'pdf',file:'source.pdf'}]}]};
  const save=()=>fs.writeFileSync(file,JSON.stringify(config));save();const binding=loadConfiguration(file).lessons[0];
  const run=command=>executeLearningCommand(binding,{chatId:binding.chatId,...command});
  run({op:'init',title:'Synthetic lesson',goal:'Contract checks'});
  const store=new FileSessionStore(binding.root),lesson=()=>store.read(binding.chatId),jobs=new LessonJobs(binding);
  const attach=id=>run({op:'material',action:'attach',materialId:id,expectedRevision:lesson().adapter.revision,authorship:'synthetic-fixture'});
  const request=(kind='research',input={question:'Synthetic question'},toolCallId='work')=>run({op:'job',action:'request',kind,input,toolCallId,expectedRevision:lesson().adapter.revision});
  const admit=id=>run({op:'job',action:'admit',jobId:id,receipt:{status:'dispatched',mode:'background',count:1,delegation_id:'synthetic-delegation',subagent_ids:['synthetic-child']}});
  const complete=(id,result,verification)=>run({op:'job',action:'complete',jobId:id,delegationId:'synthetic-delegation',result,verification,authorship:'synthetic-fixture'});
  return{base,file,config,save,binding,run,store,lesson,jobs,attach,request,admit,complete};
}
test('explicit material enrollment, source generations and bounded pages preserve private contents',t=>{
  const s=setup(t);assert.throws(()=>s.run({op:'material',action:'read',materialId:'notes'}));
  const attached=s.attach('notes');assert.match(attached.material.sourceId,/^src_[a-f0-9]{12}$/);
  const first=s.run({op:'material',action:'read',materialId:'notes',length:5});assert.equal(first.text,'A rat');
  assert.throws(()=>s.run({op:'material',action:'read',materialId:'notes',offset:5}));
  assert.ok(s.run({op:'material',action:'read',materialId:'notes',offset:5,sourceSha256:first.material.sha256}).text);
  const exported=s.run({op:'view'});assert.ok(!JSON.stringify(exported).includes('notes.md'));assert.ok(!JSON.stringify(exported).includes('A ratio compares'));
  fs.appendFileSync(path.join(s.base,'notes.md'),' New source.');assert.throws(()=>s.run({op:'material',action:'read',materialId:'notes'}),error=>error.code==='material_changed');
  s.attach('notes');assert.ok(s.run({op:'material',action:'read',materialId:'notes'}).text.endsWith('New source.'));
  s.config.lessons[0].jobRoot='exports/private';s.save();assert.throws(()=>loadConfiguration(s.file));
});
test('notes import uses serial extraction/audit/merge, replay-safe source provenance and explicit re-import',t=>{
  const s=setup(t);s.attach('notes');
  const command=(action,extra={})=>s.run({op:'import',action,materialId:'notes',importId:'explicit-one',...extra});
  const prepared=command('prepare');assert.equal(prepared.part,1);
  const knowledge=new LessonKnowledge(s.binding.knowledgeRoot),revision=knowledge.read().adapter.revision;
  command('prepare');assert.equal(knowledge.read().adapter.revision,revision);
  command('findings',{part:1,findings:{propositions:[{id:'p',name:'Ratio',statement:'A ratio compares quantities.',aliases:[]}],chains:[]},authorship:'synthetic-fixture'});
  const audit=command('audit');assert.equal(audit.text,undefined);assert.equal(audit.chains,undefined);
  const merged=command('merge',{part:1,verdicts:{links:[]},graphRevision:audit.graphRevision,authorship:'synthetic-fixture'});assert.equal(merged.complete,true);
  assert.equal(command('merge',{part:1,verdicts:{links:[]},graphRevision:audit.graphRevision,authorship:'synthetic-fixture'}).alreadyMerged,true);
  const graph=knowledge.lessonView(s.lesson());assert.equal(graph.nodes.length,1);assert.equal(graph.nodes[0].passages.length,0);
  assert.equal(knowledge.read().checkpoints[0].chatId,prepared.sourceId);
  assert.equal(s.run({op:'import',action:'prepare',materialId:'notes',importId:'explicit-two'}).part,1);
  const aborted=s.run({op:'import',action:'abort',materialId:'notes',importId:'explicit-two'});assert.equal(aborted.mergedParts,0);assert.equal(knowledge.graph().nodes.length,1);
});
test('empty notes import is durably completed instead of silently losing its record',t=>{
  const s=setup(t,'');s.attach('notes');assert.equal(s.run({op:'import',action:'prepare',materialId:'notes',importId:'empty'}).complete,true);
  assert.equal(Object.values(new LessonKnowledge(s.binding.knowledgeRoot).read().notesImports)[0].status,'done');
});
for(const refreshFirst of [false,true])test(`N2 changed notes can retire partial import ${refreshFirst?'after':'before'} refreshing attachment`,t=>{
  const s=setup(t,'Ratios compare.\nRates compare.\nUnits matter.');s.attach('notes');
  const command=(action,extra={})=>s.run({op:'import',action,materialId:'notes',importId:'old',...extra});
  const prepared=command('prepare',{budget:1});assert.ok(prepared.totalParts>1);
  command('findings',{part:1,findings:{propositions:[{id:'p',name:'Ratio',statement:'Ratios compare.',aliases:[]}],chains:[]},authorship:'synthetic-fixture'});
  const audit=command('audit');assert.equal(command('merge',{part:1,verdicts:{links:[]},graphRevision:audit.graphRevision,authorship:'synthetic-fixture'}).complete,false);
  const knowledge=new LessonKnowledge(s.binding.knowledgeRoot),beforeGraph=knowledge.graph(),file=path.join(s.base,'notes.md');
  fs.writeFileSync(file,'Changed notes.\nNew material.');
  if(refreshFirst)s.attach('notes');
  assert.throws(()=>command('audit'));
  const open=fs.openSync;t.mock.method(fs,'openSync',function(target,...rest){assert.notEqual(target,file,'abort must not open source bytes');return open(target,...rest);});
  assert.equal(command('abort').mergedParts,1);
  const retired=fs.readFileSync(knowledge.store.file('knowledge'));assert.equal(command('abort').aborted,true);
  assert.deepEqual(fs.readFileSync(knowledge.store.file('knowledge')),retired);
  assert.throws(()=>s.run({op:'import',action:'abort',materialId:'pdf',importId:'old'}));
  t.mock.restoreAll();
  assert.deepEqual(knowledge.graph(),beforeGraph);assert.equal(knowledge.read().checkpoints.length,0);
  const old=Object.values(knowledge.read().notesImports).find(run=>run.importId==='old');assert.equal(old.status,'aborted');assert.equal(old.next,1);
  if(!refreshFirst)s.attach('notes');
  const next=s.run({op:'import',action:'prepare',materialId:'notes',importId:'new',budget:1});assert.equal(next.part,1);assert.ok(next.text.startsWith('Changed'));
  assert.throws(()=>command('merge',{part:2,verdicts:{links:[]},graphRevision:knowledge.read().adapter.revision,authorship:'synthetic-fixture'}));
});
// Test-only controlled descriptor/read seams: no large fixture, runtime seam,
// alternate reader or live source. At most limit+1 bytes leave the fake reader.
function guardedRead(t,{file,limit,openedSize,virtualBytes},invoke,code) {
  const original={open:fs.openSync,stat:fs.fstatSync,read:fs.readSync,close:fs.closeSync};
  let active=null,last=null,read=0,closed=0;
  t.mock.method(fs,'openSync',function(target,...rest){const fd=original.open(target,...rest);if(target===file){active=fd;last=fd;}return fd;});
  t.mock.method(fs,'fstatSync',function(fd,...rest){const stat=original.stat(fd,...rest);
    if(fd===active&&openedSize!==undefined)return Object.assign(Object.create(Object.getPrototypeOf(stat)),stat,{size:BigInt(openedSize)});return stat;});
  t.mock.method(fs,'readSync',function(fd,buffer,offset,length,position){
    if(fd!==active)return original.read(fd,buffer,offset,length,position);
    if(virtualBytes===undefined){read+=length;return original.read(fd,buffer,offset,length,position);}
    assert.ok(length<=Math.min(65536,limit-read+1));const count=Math.min(length,virtualBytes-read);buffer.fill(65,offset,offset+count);read+=count;return count;
  });
  t.mock.method(fs,'closeSync',function(fd){if(fd===active){closed++;active=null;}return original.close(fd);});
  try{assert.throws(invoke,error=>error.code===code);assert.equal(closed,1);assert.equal(active,null);assert.throws(()=>original.stat(last),error=>error.code==='EBADF');
    if(virtualBytes===undefined)assert.equal(read,0);else assert.equal(read,limit+1);
  }finally{t.mock.restoreAll();}
}
test('N3 material rejects opened oversize/generation drift and cumulative growth before decoding',t=>{
  const s=setup(t),file=path.join(s.base,'notes.md'),read=()=>inspectMaterial(s.binding,'notes',{text:true});
  guardedRead(t,{file,limit:4194304,openedSize:4194305},read,'material_too_large');
  guardedRead(t,{file,limit:4194304,openedSize:fs.statSync(file).size+1},read,'material_changed');
  guardedRead(t,{file,limit:4194304,virtualBytes:4194305},read,'material_too_large');
  const normal=read();assert.equal(normal.size,Buffer.byteLength(normal.text));assert.equal(normal.text,'A ratio compares two quantities.');
});
test('N3 producer read rejects descriptor oversize/drift and growth without completing a job',t=>{
  const s=setup(t),{jobId}=s.request();s.run({op:'job',action:'dispatch',jobId});s.admit(jobId);
  const file=path.join(s.binding.jobRoot,jobId,'result.json'),payload=Buffer.from(JSON.stringify({jobId,kind:'research',result:{brief:'Small real bytes',sources:[]}}));fs.writeFileSync(file,payload);
  const before=fs.readFileSync(s.jobs.store.file(s.jobs.id)),complete=()=>s.run({op:'job',action:'complete',jobId,delegationId:'synthetic-delegation',resultFile:true,resultSha256:createHash('sha256').update(payload).digest('hex'),authorship:'synthetic-fixture'});
  guardedRead(t,{file,limit:2097152,openedSize:2097153},complete,'invalid_job_result_file');
  guardedRead(t,{file,limit:2097152,openedSize:payload.length+1},complete,'job_result_changed');
  guardedRead(t,{file,limit:2097152,virtualBytes:2097153},complete,'invalid_job_result_file');
  assert.deepEqual(fs.readFileSync(s.jobs.store.file(s.jobs.id)),before);assert.equal(s.jobs.context().length,0);
  complete();assert.equal(s.jobs.read().jobs[jobId].execution,'result-ready');
});
test('job request/admission/result/teacher acknowledgement is durable and never mutates a pending lesson',t=>{
  const s=setup(t),before=fs.readFileSync(s.store.file(s.binding.chatId)),{jobId}=s.request();
  assert.equal(s.jobs.read().jobs[jobId].execution,'prepared');
  const dispatch=s.run({op:'job',action:'dispatch',jobId});assert.equal(dispatch.tool,'delegate_task');assert.equal(dispatch.arguments.tasks.length,1);assert.equal(dispatch.arguments.tasks[0].output_schema,undefined);
  assert.ok(JSON.parse(dispatch.arguments.tasks[0].context).resultContract.sources);
  assert.equal(s.jobs.read().jobs[jobId].execution,'prepared');assert.equal(s.request().alreadyRecorded,true);
  assert.throws(()=>s.run({op:'job',action:'admit',jobId,receipt:{status:'running'}}));s.admit(jobId);
  assert.throws(()=>s.run({op:'job',action:'progress',jobId,delegationId:'wrong',activity:'Synthetic progress'}));
  const usage={eventId:'one',model:'synthetic-no-model',step:{inputTokens:3,outputTokens:2}};
  for(let i=0;i<2;i++)s.run({op:'job',action:'progress',jobId,delegationId:'synthetic-delegation',activity:'Synthetic progress',usage});
  assert.equal(s.jobs.read().jobs[jobId].usage.inputTokens,3);assert.equal(s.jobs.read().jobs[jobId].usage.outputTokens,2);
  assert.equal(s.jobs.read().jobs[jobId].usage.reasoningTokens,undefined);
  const result={brief:'Synthetic sourced finding',sources:[{title:'Primary source',url:'https://example.org/primary'}]};s.complete(jobId,result);
  assert.equal(s.complete(jobId,result).alreadyComplete,true);assert.equal(s.jobs.context().length,1);
  assert.deepEqual(fs.readFileSync(s.store.file(s.binding.chatId)),before);
  assert.throws(()=>s.run({op:'job',action:'ack',jobId,delegationId:'synthetic-delegation',afterMessageId:'invented'}));
  s.store.change(s.binding.chatId,record=>{record.messages.push({id:'actual-teacher',role:'assistant',content:[{type:'text',text:'Synthetic teacher actually used the finding.'}]});return{record,result:null};});
  s.run({op:'job',action:'ack',jobId,delegationId:'synthetic-delegation',afterMessageId:'actual-teacher'});
  assert.equal(new LessonJobs(s.binding).context().length,0);assert.equal(s.jobs.list().jobs[0].status,'done');
});
test('fixed producer result identity and immutable artifact exports keep payloads out of model context',async t=>{
  const s=setup(t),{jobId}=s.request('demo',{title:'Synthetic demo',brief:'One button'},'demo');s.run({op:'job',action:'dispatch',jobId});s.admit(jobId);
  const result={title:'Synthetic demo',html:'<html><body><button>Demo</button></body></html>',tested:true},verification={tested:true,receipts:['synthetic-test-receipt; NOT real render qualification']};
  const payload=Buffer.from(JSON.stringify({jobId,kind:'demo',result,verification})),file=path.join(s.binding.jobRoot,jobId,'result.json');fs.writeFileSync(file,payload);
  const hash=createHash('sha256').update(payload).digest('hex');
  const complete=sha=>s.run({op:'job',action:'complete',jobId,delegationId:'synthetic-delegation',resultFile:true,resultSha256:sha,authorship:'synthetic-fixture'});
  assert.throws(()=>complete('0'.repeat(64)));complete(hash);
  assert.ok(!JSON.stringify(s.jobs.context()).includes('<button>'));assert.ok(!JSON.stringify(jobArtifactDescriptors(s.jobs)).includes('<button>'));
  publishJobAssets(s.jobs,s.binding.output);const descriptor=jobArtifactDescriptors(s.jobs).jobs[0].artifact;
  const files={readText:async(folder,name)=>({ok:true,text:fs.readFileSync(path.join(folder,name),'utf8')})};
  assert.equal(await readArtifact(files,{folder:s.binding.output},descriptor),result.html);
  assert.throws(()=>s.complete(jobId,result,{...verification,receipts:['different']}));
  assert.ok(demoDocument(result.html).includes('connect-src &#39;none&#39;'));
  const envelope={v:1,ownerSessionId:s.binding.ownerSessionId,chatId:s.binding.chatId,kind:'teach',expectedRevision:s.lesson().adapter.revision,
    action:{type:'job-error',chatId:s.binding.chatId,jobId,artifactSha256:descriptor.sha256,error:'Synthetic user-clicked error'}};
  s.run({op:'learner',envelope});s.run({op:'learner',envelope});assert.equal(Object.keys(s.jobs.read().reports).length,1);
  assert.ok(s.jobs.context().some(row=>row.content==='Synthetic user-clicked error'));
  const reportId=Object.keys(s.jobs.read().reports)[0];
  assert.throws(()=>s.run({op:'job',action:'report-ack',reportId,afterMessageId:'not-saved'}));
  s.store.change(s.binding.chatId,record=>{record.messages.push({id:'error-response',role:'assistant',content:[{type:'text',text:'Synthetic actual saved response to the report.'}]});return{record,result:null};});
  s.run({op:'job',action:'report-ack',reportId,afterMessageId:'error-response'});
  assert.ok(!s.jobs.context().some(row=>row.id===reportId));
  fs.writeFileSync(path.join(s.binding.output,descriptor.file),'different');await assert.rejects(()=>readArtifact(files,{folder:s.binding.output},descriptor));
  assert.throws(()=>publishJobAssets(s.jobs,s.binding.output));
});
test('PDF job binds attached bytes and page claims rather than accepting arbitrary paths',t=>{
  const s=setup(t);s.attach('pdf');const{jobId}=s.request('pdf',{materialId:'pdf',question:'Synthetic question'},'pdf');s.admit(jobId);
  const result={path:path.join(s.base,'source.pdf'),question:'Synthetic question',brief:'Synthetic PDF fixture, not read by a model',pagesRead:[1],pagesConsulted:[1]};
  assert.throws(()=>s.complete(jobId,{...result,pagesConsulted:[]}));s.complete(jobId,result);
  assert.ok(!JSON.stringify(jobArtifactDescriptors(s.jobs)).includes('source.pdf'));
});
