// SPDX-License-Identifier: AGPL-3.0-only
// Real React/DOM lifecycle over synthetic exports, not Hermes renderer proof.
import test from 'node:test';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import path from 'node:path';
import {createRequire} from 'node:module';
import {createJobArtifacts} from '../src/inline/artifacts.mjs';
const require=createRequire(process.env.LH_TEST_TOOLCHAIN?path.join(path.resolve(process.env.LH_TEST_TOOLCHAIN),'package.json'):import.meta.url);
const {JSDOM}=require('jsdom'),React=require('react'),{createRoot}=require('react-dom/client');
test('artifacts keep opaque sandbox, verify source window and report errors only on human click',async t=>{
  const dom=new JSDOM('<main></main>',{url:'https://synthetic.invalid/'}),oldWindow=globalThis.window,oldDocument=globalThis.document,oldAct=globalThis.IS_REACT_ACT_ENVIRONMENT;
  globalThis.window=dom.window;globalThis.document=dom.window.document;globalThis.IS_REACT_ACT_ENVIRONMENT=true;
  const root=createRoot(document.querySelector('main'));t.after(async()=>{await React.act(()=>root.unmount());dom.window.close();globalThis.window=oldWindow;globalThis.document=oldDocument;globalThis.IS_REACT_ACT_ENVIRONMENT=oldAct;});
  const source='<html><body><button>Demo</button></body></html>',sha=createHash('sha256').update(source).digest('hex'),sent=[];
  const Component=createJobArtifacts(React),job={id:'job_synthetic',kind:'demo',activity:'Saved',execution:'result-ready',artifact:{kind:'demo',title:'Synthetic demo',sha256:sha,size:Buffer.byteLength(source),file:`asset-demo-${sha}.html`}};
  await React.act(async()=>{root.render(React.createElement(Component,{ctx:{files:{readText:async()=>({ok:true,text:source})}},binding:{folder:'synthetic-folder'},view:{chatId:'synthetic-lesson',jobs:{jobs:[job]}},port:{send:async action=>sent.push(action)}}));});
  // WebCrypto completes outside React's first effect flush.
  await React.act(async()=>{await new Promise(resolve=>setTimeout(resolve,25));});
  const frame=document.querySelector('iframe');assert.ok(frame);assert.equal(frame.getAttribute('sandbox'),'allow-scripts');assert.ok(!frame.getAttribute('sandbox').includes('same-origin'));
  assert.ok(frame.getAttribute('srcdoc').includes('Content-Security-Policy'));
  await React.act(()=>window.dispatchEvent(new window.MessageEvent('message',{source:window,data:{type:'demo-error',message:'forged'}})));
  assert.ok(!document.body.textContent.includes('forged'));assert.equal(sent.length,0);
  await React.act(()=>window.dispatchEvent(new window.MessageEvent('message',{source:frame.contentWindow,data:{type:'demo-error',message:'Synthetic frame error'}})));
  assert.ok(document.body.textContent.includes('Synthetic frame error'));assert.equal(sent.length,0);
  await React.act(async()=>document.querySelector('article button').click());assert.equal(sent.length,1);assert.equal(sent[0].type,'job-error');assert.equal(sent[0].artifactSha256,sha);
  const svg='<svg xmlns="http://www.w3.org/2000/svg"><script>UNTRUSTED_SVG()</script><text>Figure</text></svg>',svgHash=createHash('sha256').update(svg).digest('hex');
  await React.act(async()=>{root.render(React.createElement(Component,{ctx:{files:{readText:async()=>({ok:true,text:svg})}},binding:{folder:'synthetic-folder'},view:{chatId:'synthetic-lesson',jobs:{jobs:[{...job,kind:'visual',artifact:{kind:'visual',title:'SVG fixture',sha256:svgHash,size:Buffer.byteLength(svg),file:`asset-visual-${svgHash}.svg`}}]}},port:{send:async action=>sent.push(action)}}));});
  await React.act(async()=>{await new Promise(resolve=>setTimeout(resolve,25));});
  assert.ok(document.querySelector('img')?.src.startsWith('data:image/svg+xml;'));assert.equal(document.querySelector('svg,script,iframe'),null);assert.equal(sent.length,1);
});
