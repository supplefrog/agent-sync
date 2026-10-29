// SPDX-License-Identifier: AGPL-3.0-only
// Post-hoc knowledge contracts over the existing atomic store, not an agent loop.
import { createHash } from 'node:crypto';
import fs from 'node:fs';
import { isDeepStrictEqual } from 'node:util';
import { FileSessionStore, requireState } from './store.mjs';
import { coverageOf, batchRuns, messageViewLines } from './vendor/runtime/coverage.ts';
import { mergeFindings, getGraph, deriveView } from './vendor/runtime/graph.ts';

const object = value => value && typeof value === 'object' && !Array.isArray(value);
const text = value => typeof value === 'string' && value.trim().length > 0 && value.length <= 16000;
const ownFields = (value, names) => object(value) && Object.keys(value).every(key => names.includes(key));
const hash = value => createHash('sha256').update(JSON.stringify(value)).digest('hex');
function empty() {
  return {id:'knowledge',version:1,adapter:{version:1,revision:0},messages:[],family:'lh-knowledge-v1',
    nodes:[],chains:[],coverage:[],checkpoints:[],batches:{}};
}
export function knowledgePorts(record) {
  return {
    readNodes:()=>record.nodes,readChains:()=>record.chains,
    appendNode:node=>record.nodes.push(node),appendChain:chain=>record.chains.push(chain),
    appendCoverage:entry=>record.coverage.push(entry),appendCheckpoint:entry=>record.checkpoints.push(entry),
    rewriteLedgers:next=>{for(const name of ['nodes','chains','coverage','checkpoints'])if(next[name])record[name]=next[name];},
  };
}
const ports=knowledgePorts;
function checkRecord(record) {
  requireState(record.family==='lh-knowledge-v1'&&['nodes','chains','coverage','checkpoints'].every(key=>Array.isArray(record[key]))&&object(record.batches),
    'unsupported_knowledge','Refusing an unknown knowledge record.');
  return record;
}
export class LessonKnowledge {
  constructor(root) {this.store=new FileSessionStore(root);}
  read() {return fs.existsSync(this.store.file('knowledge'))?checkRecord(this.store.read('knowledge')):empty();}
  change(update) {
    return this.store.change('knowledge',current=>update(current?checkRecord(current):empty()),
      {create:!fs.existsSync(this.store.file('knowledge'))});
  }
  graph() {return structuredClone(getGraph(ports(this.read())));}
  query({query='',offset=0,limit=50,graphRevision}={}) {
    const record=this.read();
    requireState(typeof query==='string'&&query.length<=200&&Number.isSafeInteger(offset)&&offset>=0&&
      Number.isSafeInteger(limit)&&limit>=1&&limit<=100,'invalid_graph_query','Use a plain query, nonnegative offset and1–100items.');
    requireState(offset===0||Number.isSafeInteger(graphRevision),'stale_graph','A later page requires its captured graph revision.');
    requireState(graphRevision===undefined||graphRevision===record.adapter.revision,'stale_graph','Graph changed; restart lookup from a fresh first page.');
    const needle=query.toLocaleLowerCase(),all=getGraph(ports(record)).nodes.filter(node=>
      !needle||[node.id,node.name,node.statement,...node.aliases].some(text=>text.toLocaleLowerCase().includes(needle))).sort((a,b)=>a.id.localeCompare(b.id));
    const nodes=all.slice(offset,offset+limit),nextOffset=offset+nodes.length<all.length?offset+nodes.length:null;
    const result={graphRevision:record.adapter.revision,nodes,total:all.length,offset,nextOffset,query};
    requireState(Buffer.byteLength(JSON.stringify(result))<=262144,'graph_page_too_large','Graph page exceeds256KiB; request fewer items.');
    return result;
  }
  lessonView(lesson) {
    const state=this.read(),graph=getGraph(ports(state));
    const sources=new Set([lesson.id,...(lesson.adapter.materials??[]).map(material=>material.sourceId)]);
    const chains=graph.chains.filter(chain=>chain.provenance.some(point=>sources.has(point.chatId)));
    const ids=new Set(graph.nodes.filter(node=>node.provenance.some(point=>sources.has(point.chatId))).map(node=>node.id));
    for(const chain of chains)for(const id of [...chain.premises,chain.conclusion])ids.add(id);
    const nodes=graph.nodes.filter(node=>ids.has(node.id)).map(node=>({...node,
      passages:node.provenance.filter(point=>point.chatId===lesson.id).flatMap(point=>{
        const message=lesson.messages.find(message=>message.id===point.messageId);
        return message?.role==='assistant'&&Array.isArray(message.content)
          ? message.content.filter(block=>block.type==='text'&&typeof block.text==='string').map(block=>block.text):[];
      })}));
    const visual=deriveView({nodes,chains});
    return{revision:state.adapter.revision,nodes,diagram:{nodes:visual.nodes.map(node=>({id:node.id,title:node.name})),edges:visual.edges},
      scope:'Propositions from this lesson and its explicitly attached materials; not assessed learner mastery.'};
  }
  status(lesson) {
    const state=this.read(),coverage=coverageOf(lesson.messages,state.coverage,lesson.id);
    return {graphRevision:state.adapter.revision,coveredCount:coverage.coveredCount,uncoveredCount:coverage.uncoveredCount,
      coveredTokens:coverage.coveredTokens,uncoveredTokens:coverage.uncoveredTokens,
      scope:'Teacher propositions and source coverage; never learner mastery.'};
  }
  prepare(lesson,{ownerSessionId,expectedRevision,budget=8000}) {
    requireState((lesson.kind??'teach')==='teach','wrong_session_kind','Practice never writes the knowledge graph.');
    requireState(lesson.adapter.revision===expectedRevision,'stale_native_revision','Reload the lesson before selecting extraction material.');
    requireState(Number.isSafeInteger(budget)&&budget>0&&budget<=32000,'invalid_budget','Use an extraction budget of1–32000 estimated tokens.');
    return this.change(record=>{
      const coverage=coverageOf(lesson.messages,record.coverage,lesson.id);
      const slots=batchRuns(coverage.slots,coverage.uncovered,budget)[0];
      if(!slots)return{record,changed:false,result:{ok:true,complete:true,graphRevision:record.adapter.revision}};
      const items=slots.map(slot=>({id:slot.message.id,fp:slot.fp,tokens:slot.tokens}));
      const batchId=hash([ownerSessionId,lesson.id,items.map(item=>item.fp)]);
      const batch=record.batches[batchId];
      requireState(!batch||batch.ownerSessionId===ownerSessionId&&batch.chatId===lesson.id,
        'wrong_native_owner','Extraction belongs to a different owner.');
      if(!batch)record.batches[batchId]={ownerSessionId,chatId:lesson.id,items,status:'prepared'};
      const source=slots.flatMap(slot=>messageViewLines(slot.message,slot.message.id));
      requireState(Buffer.byteLength(JSON.stringify(source))<=262144,'extraction_too_large','One teacher passage exceeds256KiB; no silent split or truncation.');
      return{record,changed:!batch,result:{ok:true,batchId,source,
        instruction:'Extract true teacher propositions and reasoning chains, with source message IDs. Learner answers and tool commitments are excluded. Submit findings; do not invent audit judgments.'}};
    });
  }
  batch(record,id,owner,lesson) {
    const batch=record.batches[id];
    requireState(batch&&batch.ownerSessionId===owner&&batch.chatId===lesson.id,'wrong_native_owner','No prepared batch for this owning lesson.');
    const current=coverageOf(lesson.messages,[],lesson.id).slots;
    requireState(batch.items.every(item=>current.some(slot=>slot.message.id===item.id&&slot.fp===item.fp)),
      'stale_extraction','Teacher source changed; prepare a fresh extraction batch.');
    return batch;
  }
  findings(lesson,{ownerSessionId,batchId,findings,authorship}) {
    requireState(['host-agent','synthetic-fixture'].includes(authorship),'invalid_authorship','Declare the actual findings author.');
    requireState(ownFields(findings,['propositions','chains'])&&Array.isArray(findings.propositions)&&Array.isArray(findings.chains)&&
      Buffer.byteLength(JSON.stringify(findings))<=262144,'invalid_findings','Use bounded upstream proposition/chain findings.');
    return this.change(record=>{
      const batch=this.batch(record,batchId,ownerSessionId,lesson),ids=new Set();
      for(const proposition of findings.propositions) {
        requireState(ownFields(proposition,['id','name','statement','aliases','messageId'])&&text(proposition.id)&&!ids.has(proposition.id)&&
          text(proposition.name)&&text(proposition.statement)&&Array.isArray(proposition.aliases)&&proposition.aliases.every(text)&&
          batch.items.some(item=>item.id===proposition.messageId),'invalid_findings','Each proposition needs a unique local ID and a teacher passage in this exact batch.');
        ids.add(proposition.id);
      }
      const known=new Set([...ids,...record.nodes.map(node=>node.id)]);
      for(const chain of findings.chains)requireState(ownFields(chain,['premises','conclusion'])&&Array.isArray(chain.premises)&&chain.premises.length>0&&
        chain.premises.every(id=>known.has(id))&&known.has(chain.conclusion),'invalid_findings','Chain endpoints must resolve in this batch or the enrolled graph.');
      if(batch.findings){requireState(isDeepStrictEqual(batch.findings,findings),'replayed_findings','Prepared findings are immutable; use a new source batch for changes.');
        return{record,changed:false,result:{ok:true,alreadyRecorded:true,batchId}};}
      batch.findings=structuredClone(findings);batch.authorship=authorship;batch.status='extracted';
      return{record,result:{ok:true,batchId}};
    });
  }
  audit(lesson,{ownerSessionId,batchId}) {
    const record=this.read(),batch=this.batch(record,batchId,ownerSessionId,lesson);
    requireState(batch.findings,'findings_required','Submit extractor findings before identity audit.');
    // Auditor receives propositions and existing identities only: no teacher
    // source, chain proposals, learner answers or commitments in this projection.
    const result={ok:true,batchId,graphRevision:record.adapter.revision,
      propositions:batch.findings.propositions.map(({id,name,statement,aliases})=>({id,name,statement,aliases})),
      existing:this.query({limit:20}),
      instruction:'Return identity links only. Equivalent propositions link to existing IDs; absent links create. Do not alter findings or mint edges. This projection does not isolate a model that already saw the source.'};
    requireState(Buffer.byteLength(JSON.stringify(result))<=262144,'audit_context_too_large','Audit context exceeds256KiB; prepare a smaller source batch.');
    return result;
  }
  merge(lesson,{ownerSessionId,batchId,graphRevision,verdicts,authorship}) {
    requireState(['host-agent','synthetic-fixture'].includes(authorship)&&ownFields(verdicts,['links'])&&Array.isArray(verdicts.links)&&
      Buffer.byteLength(JSON.stringify(verdicts))<=262144,'invalid_verdicts','Declare audit authorship and use bounded identity links only.');
    return this.change(record=>{
      const batch=this.batch(record,batchId,ownerSessionId,lesson);
      requireState(batch.findings,'findings_required','No extractor findings to merge.');
      if(batch.status==='merged') {
        requireState(isDeepStrictEqual(batch.verdicts,verdicts),'replayed_audit','A merged batch cannot accept different identity judgments.');
        return{record,changed:false,result:{ok:true,alreadyMerged:true,batchId,stats:batch.stats}};
      }
      requireState(Number.isSafeInteger(graphRevision)&&record.adapter.revision===graphRevision,'stale_graph','The graph changed after audit; request its fresh identity context.');
      requireState(!batch.items.some(item=>record.coverage.some(entry=>entry.chatId===lesson.id&&entry.fp===item.fp)),
        'stale_extraction','Another batch already covered this source; prepare remaining material.');
      const local=new Set(batch.findings.propositions.map(p=>p.id)),existing=new Set(record.nodes.map(node=>node.id)),seen=new Set();
      for(const link of verdicts.links){requireState(ownFields(link,['id','linkTo'])&&local.has(link.id)&&existing.has(link.linkTo)&&!seen.has(link.id),
        'invalid_verdicts','Every audit link must uniquely join a batch proposition to an existing graph identity.');seen.add(link.id);}
      const foldedAt=new Date().toISOString();
      const stats=mergeFindings(lesson.id,batch.findings,verdicts,{graphStore:ports(record)},
        {foldedAt,coverage:batch.items.map(item=>({chatId:lesson.id,fp:item.fp,tokens:item.tokens,foldedAt}))});
      batch.verdicts=structuredClone(verdicts);batch.auditAuthorship=authorship;batch.stats=stats;batch.status='merged';
      return{record,result:{ok:true,batchId,stats}};
    });
  }
}
