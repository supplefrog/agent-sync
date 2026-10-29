// SPDX-License-Identifier: AGPL-3.0-only
// Offline resource build from the same existing control source/toolchain.
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { createHash } from 'node:crypto';
const here=path.dirname(fileURLToPath(import.meta.url));
if(!process.argv[2])throw new Error('Pass the existing esbuild toolchain directory; no downloads.');
const require=createRequire(path.join(path.resolve(process.argv[2]),'package.json')),esbuild=require('esbuild');
if(esbuild.version!=='0.28.2')throw new Error('Selected build uses esbuild0.28.2.');
const hash=bytes=>createHash('sha256').update(bytes).digest('hex'),inputsBefore=new Map();
function capture(directory){for(const item of fs.readdirSync(directory,{withFileTypes:true})){
  const file=path.join(directory,item.name);
  if(item.isDirectory())capture(file);
  else if(item.isFile())inputsBefore.set(path.resolve(file),hash(fs.readFileSync(file)));
  else throw new Error('Source input cannot be a link or special file.');
}}
capture(path.join(here,'src'));
const buildFile=fileURLToPath(import.meta.url),buildSha=hash(fs.readFileSync(buildFile));
const styleFile=path.join(here,'src/inline/inline-template.html');
const style=fs.readFileSync(styleFile,'utf8').match(/<style>([\s\S]*?)<\/style>/)?.[1];
if(!style)throw new Error('Existing inline control stylesheet missing.');
const result=await esbuild.build({entryPoints:[path.join(here,'src/t3/app.mjs')],bundle:true,write:false,
  platform:'browser',format:'iife',target:'es2022',minify:false,sourcemap:false,metafile:true});
if(Object.values(result.metafile.outputs).some(o=>o.imports.length))throw new Error('App resource must be self-contained.');
const boundInputs=Object.keys(result.metafile.inputs).map(input=>{
  const file=path.resolve(input),before=inputsBefore.get(file),after=hash(fs.readFileSync(file));
  if(!before||before!==after)throw new Error('A bundled source input changed during generation.');
  return {path:path.relative(here,file).replaceAll(path.sep,'/'),sha256:after};
});
if(hash(fs.readFileSync(styleFile))!==inputsBefore.get(styleFile)||hash(fs.readFileSync(buildFile))!==buildSha)
  throw new Error('Builder/style changed during generation.');
const js=result.outputFiles[0].text.replaceAll('</script','<\\/script');
const html='<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><style>'+style+
  '</style></head><body><p id="lh-notice" role="status">Connecting to the owning T3 conversation.</p><button type="button" id="lh-refresh">Refresh saved lesson</button><button type="button" id="lh-save-draft" disabled>Save draft privately</button><div id="lh-inline-lesson"></div><section id="lh-jobs" aria-label="Materials and supporting work"></section><script>'+js+'</script></body></html>';
if(Buffer.byteLength(html)>5*1024*1024)throw new Error('App exceeds T3 resource cap.');
fs.mkdirSync(path.join(here,'t3'),{recursive:true});fs.writeFileSync(path.join(here,'t3/app.html'),html);
const receipt={built:'t3/app.html',bytes:Buffer.byteLength(html),sha256:hash(Buffer.from(html)),esbuild:esbuild.version,
  builder:{path:'build-t3.mjs',sha256:buildSha},style:{path:'src/inline/inline-template.html',sha256:inputsBefore.get(styleFile)},
  inputs:boundInputs,hostActivation:false,providerCalls:0,scope:'Artifact generation only; no server syntax/runtime or live host test.'};
fs.writeFileSync(path.join(here,'t3/BUILD.json'),JSON.stringify(receipt,null,2)+'\n');
console.log(JSON.stringify(receipt));
