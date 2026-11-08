// SPDX-License-Identifier: AGPL-3.0-only
// Offline resource build from the same existing control source/toolchain.
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { createHash } from 'node:crypto';
import {readRichAssets,thirdPartyNotices} from './t3-rich-assets.mjs';
const here=path.dirname(fileURLToPath(import.meta.url));
if(!process.argv[2])throw new Error('Pass the existing esbuild toolchain directory; no downloads.');
const require=createRequire(path.join(path.resolve(process.argv[2]),'package.json')),esbuild=require('esbuild');
const toolchain=path.resolve(process.argv[2]),moduleRoot=fs.realpathSync(path.join(toolchain,'node_modules'));
if(esbuild.version!=='0.28.2')throw new Error('Selected build uses esbuild0.28.2.');
const hash=bytes=>createHash('sha256').update(bytes).digest('hex'),inputsBefore=new Map();
const inside=(parent,file)=>{const rel=path.relative(parent,file);return rel!==''&&!path.isAbsolute(rel)&&rel!=='..'&&!rel.startsWith('..'+path.sep);};
function capture(directory){for(const item of fs.readdirSync(directory,{withFileTypes:true})){
  const file=path.join(directory,item.name);
  if(item.isDirectory())capture(file);
  else if(item.isFile())inputsBefore.set(path.resolve(file),hash(fs.readFileSync(file)));
  else throw new Error('Source input cannot be a link or special file.');
}}
capture(path.join(here,'src'));
const buildFile=fileURLToPath(import.meta.url),buildSha=hash(fs.readFileSync(buildFile));
const assetBuilder=path.join(here,'t3-rich-assets.mjs'),assetBuilderSha=hash(fs.readFileSync(assetBuilder));
const richAssets=readRichAssets(toolchain),richStyleFile=path.join(here,'src/t3/rich-style.css');
const richStyle=fs.readFileSync(richStyleFile,'utf8')+richAssets.css;
const styleFile=path.join(here,'src/inline/inline-template.html');
const style=fs.readFileSync(styleFile,'utf8').match(/<style>([\s\S]*?)<\/style>/)?.[1];
if(!style)throw new Error('Existing inline control stylesheet missing.');
const codexStyleFile=path.join(here,'src/inline/codex-lesson.css');
const codexStyle=fs.readFileSync(codexStyleFile,'utf8').replaceAll('#lh-inline-lesson','body[data-lh-host=codex] #lh-inline-lesson');
const result=await esbuild.build({entryPoints:[path.join(here,'src/t3/app.mjs')],bundle:true,write:false,
  platform:'browser',format:'iife',target:'es2022',minify:true,sourcemap:false,metafile:true,legalComments:'inline',nodePaths:[moduleRoot],
  plugins:[{name:'bind-renderer-sources',setup(build){build.onLoad({filter:/.*/},args=>{
    const file=path.resolve(args.path);
    if(!inside(path.join(here,'src'),file)&&!inside(moduleRoot,file))throw new Error('Unexpected build input root.');
    const before=hash(fs.readFileSync(file));
    if(inputsBefore.has(file)&&inputsBefore.get(file)!==before)throw new Error('Build source changed before loading.');
    inputsBefore.set(file,before);return undefined;
  });}}]});
if(Object.values(result.metafile.outputs).some(o=>o.imports.length))throw new Error('App resource must be self-contained.');
const boundInputs=Object.keys(result.metafile.inputs).map(input=>{
  const file=path.resolve(input),before=inputsBefore.get(file),after=hash(fs.readFileSync(file));
  if(!before||before!==after)throw new Error('A bundled source input changed during generation.');
  return {path:(inside(moduleRoot,file)?'dependencies/'+path.relative(moduleRoot,file):path.relative(here,file)).replaceAll(path.sep,'/'),sha256:after};
});
if(hash(fs.readFileSync(styleFile))!==inputsBefore.get(styleFile)||hash(fs.readFileSync(codexStyleFile))!==inputsBefore.get(codexStyleFile)||hash(fs.readFileSync(richStyleFile))!==inputsBefore.get(richStyleFile)||hash(fs.readFileSync(buildFile))!==buildSha||hash(fs.readFileSync(assetBuilder))!==assetBuilderSha)
  throw new Error('Builder/style changed during generation.');
if(JSON.stringify(readRichAssets(toolchain))!==JSON.stringify(richAssets))throw new Error('Selected renderer packages/fonts changed during generation.');
const js=result.outputFiles[0].text.replaceAll('</script','<\\/script');
const html='<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><style>'+style+
  codexStyle+richStyle+
  'body{margin:0;padding:12px;box-sizing:border-box;color:var(--foreground,#e6e6e6);background:var(--background,#141414);font-family:var(--font-sans,system-ui,sans-serif);font-size:16px;line-height:1.5}#lh-notice{color:var(--muted-foreground,#b8bfc7)}body>button{font:inherit;color:inherit;background:var(--card,#1c1c1c);border:1px solid var(--border,#434343);border-radius:8px;min-height:44px;padding:8px 12px;margin:0 8px 12px 0}#lh-jobs{overflow-wrap:anywhere}'+
  '</style></head><body><p id="lh-notice" role="status">Connecting to the owning conversation.</p><button type="button" id="lh-refresh">Refresh saved lesson</button><button type="button" id="lh-save-draft" disabled>Save draft privately</button><div id="lh-inline-lesson"></div><section id="lh-jobs" aria-label="Materials and supporting work"></section><script>'+js+'</script></body></html>';
if(Buffer.byteLength(html)>5*1024*1024)throw new Error('App exceeds T3 resource cap.');
const notices=thirdPartyNotices(Object.keys(result.metafile.inputs),toolchain);
const receipt={built:'t3/app.html',bytes:Buffer.byteLength(html),sha256:hash(Buffer.from(html)),esbuild:esbuild.version,
  builder:{path:'build-t3.mjs',sha256:buildSha},style:{path:'src/inline/inline-template.html',sha256:inputsBefore.get(styleFile)},
  codexStyle:{path:'src/inline/codex-lesson.css',sha256:inputsBefore.get(codexStyleFile)},
  rendererPackages:richAssets.packages,fontAssets:richAssets.fonts,katexCssSha256:richAssets.sourceCssSha256,assetBuilderSha256:assetBuilderSha,
  noticeSourceBindings:richAssets.noticeBindings,noticesSha256:hash(Buffer.from(notices)),inputs:boundInputs,hostActivation:false,providerCalls:0,scope:'Artifact generation only; no server syntax/runtime or live host test.'};
// Finish all validation/notice preparation before replacing any old artifact.
fs.mkdirSync(path.join(here,'t3'),{recursive:true});fs.writeFileSync(path.join(here,'t3/app.html'),html);
fs.writeFileSync(path.join(here,'t3/THIRD-PARTY-NOTICES.txt'),notices);
fs.writeFileSync(path.join(here,'t3/BUILD.json'),JSON.stringify(receipt,null,2)+'\n');
console.log(JSON.stringify(receipt));
