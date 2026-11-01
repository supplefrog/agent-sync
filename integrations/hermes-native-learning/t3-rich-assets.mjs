// SPDX-License-Identifier: AGPL-3.0-only
// Build-time reads from the selected existing toolchain; no downloads or exec.
import fs from 'node:fs';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {fileURLToPath} from 'node:url';
const hash=b=>createHash('sha256').update(b).digest('hex');
const noticeHome=fileURLToPath(new URL('./licenses/',import.meta.url));
function noticeSources(){const bytes=fs.readFileSync(path.join(noticeHome,'NOTICE-SOURCES.json')),data=JSON.parse(bytes);if(data.schema!==1||!data.entries)throw new Error('Notice source manifest invalid.');return{entries:data.entries,manifestSha256:hash(bytes)};}
function noticeFile(root,name){if(typeof name!=='string'||!/^[A-Za-z0-9_.-]+$/.test(name)||name==='.'||name==='..')throw new Error('Invalid notice source file.');const file=path.join(root,name);if(!fs.lstatSync(file).isFile())throw new Error('Notice source must be a regular file.');return fs.readFileSync(file);}
export function noticeSourceBindings(){const data=noticeSources(),files=new Map();for(const entry of Object.values(data.entries)){if(entry.kind==='repository-license'){const bytes=noticeFile(noticeHome,entry.file);if(hash(bytes)!==entry.sha256)throw new Error('Repository notice source changed.');files.set(entry.file,{path:'licenses/'+entry.file,sha256:entry.sha256});}}return{manifestSha256:data.manifestSha256,files:[...files.values()]};}
function selectedNotice(dir,meta){
  const identity=`${meta.name}@${meta.version}`,entry=noticeSources().entries[identity];
  if(!entry||meta.license!=='MIT')throw new Error(`License text missing for ${identity}.`);
  if(hash(fs.readFileSync(path.join(dir,'package.json')))!==entry.packageSha256)throw new Error(`Package identity changed for notice: ${identity}.`);
  let bytes;
  if(entry.kind==='package-readme')bytes=noticeFile(dir,entry.file);
  else if(entry.kind==='repository-license')bytes=noticeFile(noticeHome,entry.file);
  else throw new Error('Unknown notice source kind.');
  if(hash(bytes)!==entry.sha256)throw new Error(`Notice source changed for ${identity}.`);
  let text=bytes.toString('utf8');
  if(entry.kind==='package-readme'){const heading=/^## License[ \t]*\r?$/m.exec(text);if(!heading)throw new Error('Complete README license section missing.');text=text.slice(heading.index+heading[0].length).trim()+'\n';}
  const flat=text.replace(/\s+/g,' ');
  if(!['Copyright (c)','Permission is hereby granted, free of charge','The above copyright notice and this permission notice','WITHOUT WARRANTY OF ANY KIND','OTHER DEALINGS IN THE SOFTWARE.'].every(part=>flat.includes(part)))throw new Error('Incomplete MIT notice text.');
  return `Notice source: ${entry.source}\nSource SHA256: ${entry.sha256}\n\n${text}`;
}
export const RICH_PINS=Object.freeze({'react':'19.2.8','react-dom':'19.2.8','streamdown':'2.5.0','@streamdown/cjk':'1.0.3','@streamdown/math':'1.0.2','@streamdown/mermaid':'1.0.2','remark-breaks':'4.0.0','katex':'0.18.2','mermaid':'11.17.0'});
export function readRichAssets(toolchain) {
  const modules=path.join(path.resolve(toolchain),'node_modules'),packages=[];
  for(const [name,version]of Object.entries(RICH_PINS)) {
    const file=path.join(modules,...name.split('/'),'package.json'),bytes=fs.readFileSync(file),meta=JSON.parse(bytes);
    if(meta.name!==name||meta.version!==version)throw new Error(`Selected renderer dependency differs: ${name}.`);
    packages.push({name,version,license:meta.license,packageSha256:hash(bytes)});
  }
  const dist=path.join(modules,'katex','dist'),cssBytes=fs.readFileSync(path.join(dist,'katex.min.css')),fonts=new Map();
  const css=cssBytes.toString('utf8').replace(/src:([^;]+);/g,(_,sources)=>{
    const match=/url\((?:["'])?fonts\/(KaTeX_[A-Za-z0-9_-]+\.woff2)(?:["'])?\)\s*format\(["']woff2["']\)/.exec(sources);
    if(!match)throw new Error('Selected KaTeX font source differs.');
    const bytes=fs.readFileSync(path.join(dist,'fonts',match[1]));
    fonts.set(match[1],{file:match[1],bytes:bytes.length,sha256:hash(bytes)});
    return `src:url(data:font/woff2;base64,${bytes.toString('base64')}) format('woff2');`;
  });
  if(fonts.size!==20||/@import/i.test(css)||/url\((?!data:font\/woff2;base64,)/i.test(css)||Buffer.byteLength(css)>1048576)
    throw new Error('KaTeX CSS contains an unexpected asset or exceeds its bound.');
  return{css,fonts:[...fonts.values()],packages,sourceCssSha256:hash(cssBytes),noticeBindings:noticeSourceBindings()};
}

export function thirdPartyNotices(inputFiles,toolchain) {
  const root=fs.realpathSync(path.join(path.resolve(toolchain),'node_modules')),seen=new Map();
  for(const file of inputFiles) {
    let dir=path.dirname(path.resolve(file));
    while((()=>{const rel=path.relative(root,dir);return rel!==''&&!path.isAbsolute(rel)&&rel!=='..'&&!rel.startsWith('..'+path.sep);})()) {
      const manifest=path.join(dir,'package.json');
      if(fs.existsSync(manifest)) {
        const meta=JSON.parse(fs.readFileSync(manifest,'utf8'));
        if(meta.name&&meta.version) {
          const identity=`${meta.name}@${meta.version}`;
          if(!seen.has(identity)) {
            const licenses=fs.readdirSync(dir).filter(n=>/^(?:LICENSE|LICENCE|COPYING|NOTICE)(?:[.-].*)?$/i.test(n));
            const parts=licenses.length?licenses.map(name=>{const target=path.join(dir,name);if(!fs.lstatSync(target).isFile())throw new Error('License entry must be an ordinary file.');return fs.readFileSync(target,'utf8');}):[selectedNotice(dir,meta)];
            seen.set(identity,`${identity}\nDeclared license: ${typeof meta.license==='string'?meta.license:'See included text'}\n\n${parts.join('\n\n')}`);
          }
          break;
        }
      }
      const parent=path.dirname(dir);if(parent===dir)break;dir=parent;
    }
  }
  return [...seen.keys()].sort().map(key=>seen.get(key)).join('\n\n----------------------------------------\n\n')+'\n';
}
