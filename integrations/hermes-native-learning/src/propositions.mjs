// SPDX-License-Identifier: AGPL-3.0-only
// Read-only native LearnHarness v1 catalogue projection. No graph writes,
// imported-source traversal, history reads, extraction, cache or new graph store.
import fs from 'node:fs';
import path from 'node:path';
import { createHash } from 'node:crypto';
import { requireState } from './store.mjs';
function readInside(root,relative) {
  const file=path.join(root,relative);
  if(!fs.existsSync(file))return null;
  const actual=fs.realpathSync(file),rel=path.relative(root,actual);
  requireState(rel!=='' && !path.isAbsolute(rel) && rel!=='..' && !rel.startsWith('..'+path.sep),
    'invalid_graph_source','Graph file escaped the explicitly enrolled graph directory.');
  requireState(fs.statSync(actual).size<=4194304,'graph_too_large','Graph source exceeds4MiB; do not truncate it.');
  return fs.readFileSync(actual,'utf8');
}
export function readNativePropositions(enrolledRoot) {
  const root=fs.realpathSync(enrolledRoot);
  requireState(fs.statSync(root).isDirectory(),'invalid_graph_source','Enrolled graph directory required.');
  const stampText=readInside(root,'format.json');
  if(stampText!==null){const stamp=JSON.parse(stampText);requireState(Number.isInteger(stamp?.version)&&stamp.version===1,
    'unsupported_graph_version','Only native graph format1 is supported.');}
  const ledger=readInside(root,'nodes.jsonl')??'',nodes=new Map();
  for(const line of ledger.split(/\r?\n/)) {
    if(!line.trim())continue;
    const row=JSON.parse(line);
    requireState(row&&['id','name','statement','createdAt'].every(k=>typeof row[k]==='string')&&row.id.length>0&&
      Array.isArray(row.aliases)&&row.aliases.every(x=>typeof x==='string')&&Array.isArray(row.provenance)&&
      row.provenance.every(p=>p&&typeof p.chatId==='string'&&typeof p.messageId==='string'),
      'invalid_graph_source','Invalid native proposition assertion; refusing an incomplete catalogue.');
    // Same first-identity rule as the existing read-only graph reader. Names
    // are canonical identity; aliases/provenance are not target-name matching.
    if(!nodes.has(row.id))nodes.set(row.id,{id:row.id,name:row.name,statement:row.statement});
  }
  return{nodes:[...nodes.values()],sourceSha256:createHash('sha256').update(stampText??'').update('\0').update(ledger).digest('hex'),
    scope:'read-only proposition identity/material, not learner mastery'};
}
