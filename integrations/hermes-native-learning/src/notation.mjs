// SPDX-License-Identifier: AGPL-3.0-only
import { createHash } from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { Worker } from 'node:worker_threads';
import { requireState } from './store.mjs';

const bounds = {smiles:2048,abc:16384,tikz:16384};
const runtime = fileURLToPath(new URL('../notation-runtime/package.json',import.meta.url));
const cache = new Map(), pending = new Map();
const lanes = [{tail:Promise.resolve(),count:0},{tail:Promise.resolve(),count:0}];

function input(family, source) {
  requireState(Object.hasOwn(bounds,family)&&typeof source==='string'&&source.trim()&&Buffer.byteLength(source)<=bounds[family]&&
    !source.includes('\0'),'invalid_notation','Use one bounded SMILES, ABC or TikZ block.');
  source = source.trim();
  if(family==='smiles')requireState(!/[\s.>]/.test(source),'invalid_notation','Use one SMILES molecule.');
  if(family==='abc')requireState(['X','M','L','K'].every(header=>new RegExp('^'+header+':[\\t ]*\\S','m').test(source))&&
    (source.match(/^X:/gm)??[]).length===1,'invalid_notation','Use one ABC tune with X:, M:, L: and K: headers.');
  if(family==='tikz')requireState(/\\begin\{document\}/.test(source)&&/\\end\{document\}/.test(source)&&
    !/\\(?:document(?:class|style)|write|openout|openin|read|input|include(?:graphics)?|usefont|catcode|csname|special)\b/i.test(source),
    'invalid_notation','Use a self-contained TikZ document with bundled packages.');
  return source;
}

function run(workerData) {
  return new Promise((resolve,reject)=>{
    const worker = new Worker(new URL('./notation-worker.mjs',import.meta.url),{
      workerData, env:{}, execArgv:[], stdout:true, stderr:true,
      resourceLimits:{maxOldGenerationSizeMb:192,maxYoungGenerationSizeMb:32,stackSizeMb:6},
    });
    // The worker never publishes dependency/TeX output or writes to the MCP transport.
    worker.stdout.resume();worker.stderr.resume();
    let settled=false;
    const finish=(error,result)=>{
      if(settled)return;
      settled=true;
      clearTimeout(timer);
      void worker.terminate();
      if(error)reject(new Error(error));
      else resolve(result);
    };
    const timer=setTimeout(()=>finish('Rendering took too long. Try a smaller notation block.'),12000);
    worker.once('message', result=>finish(result?.error,result));
    worker.once('error',()=>finish('The local notation renderer could not start.'));
    worker.once('exit',()=>finish('The local notation renderer stopped.'));
  });
}

export async function renderNotation({family,source}, {runtimeFile=runtime}={}) {
  source=input(family,source);
  const key=createHash('sha256').update(JSON.stringify([runtimeFile,family,source])).digest('hex');
  if(cache.has(key))return cache.get(key);
  if(pending.has(key))return pending.get(key);
  requireState(pending.size<8,'notation_busy','Other notation blocks are still rendering.');
  const lane=lanes[0].count<=lanes[1].count?lanes[0]:lanes[1];
  lane.count++;
  const request=lane.tail.then(()=>run({family,source,runtimeFile})).then(result=>{
    if(cache.size>=16)cache.delete(cache.keys().next().value);
    cache.set(key,result);
    return result;
  }).finally(()=>{lane.count--;pending.delete(key);});
  lane.tail=request.catch(()=>{});
  pending.set(key,request);
  return request;
}
