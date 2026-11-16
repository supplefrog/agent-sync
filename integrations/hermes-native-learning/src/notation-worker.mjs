// SPDX-License-Identifier: AGPL-3.0-only
// Runs the three pinned notation engines in a disposable worker. The output is
// rebuilt by LearnHarness's static SVG allowlist before it leaves this process.
import { parentPort, workerData } from 'node:worker_threads';
import { createRequire } from 'node:module';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { sanitizeSvg } from './vendor/notation/svg.ts';

const {family, source, runtimeFile} = workerData;
const require = createRequire(runtimeFile);
const {JSDOM, VirtualConsole} = require('jsdom');
const window = new JSDOM('', {virtualConsole:new VirtualConsole()}).window;
globalThis.window = window;
for (const key of ['document','SVGSVGElement','SVGElement','DOMParser','XMLSerializer','Node']) globalThis[key] = window[key];

async function drawMolecule() {
  const modulePath = path.join(path.dirname(require.resolve('smiles-drawer')), 'smiles-drawer.min.mjs');
  const {default: library} = await import(pathToFileURL(modulePath).href);
  const tree = await new Promise((resolve,reject)=>library.parse(source,resolve,reject));
  const drawer = new library.SvgDrawer({scale:1});
  const svg = drawer.draw(tree,null,'light');
  for (const node of svg.querySelectorAll('.element, .sub')) {
    node.setAttribute('font-size', (node.classList.contains('sub')?drawer.opts.fontSizeSmall:drawer.opts.fontSizeLarge)+'pt');
    node.setAttribute('font-family',drawer.opts.fontFamily);
  }
  // The drawer labels its already-namespaced SVG manually. XMLSerializer adds
  // the same declaration, so remove the duplicate before serializing.
  svg.removeAttribute('xmlns');
  return new XMLSerializer().serializeToString(svg);
}

function drawMusic() {
  const render = require('abcjs/src/api/abc_tunebook_svg.js');
  const target = document.createElement('div');
  const tunes = render(target,source,{staffwidth:700,add_classes:false,selectTypes:false,dragging:false});
  const svg=target.querySelector('svg');
  if (tunes.length!==1 || !svg?.querySelector('path')) throw new Error('No score');
  return new XMLSerializer().serializeToString(svg);
}

async function drawTeX() {
  const {tex2svg} = require('isomorphic-tikzjax');
  const svg = await tex2svg(source,{showConsole:false,disableSanitize:true,embedFontCss:false});
  // This DVI writer omits the closing outer element in its fragment output.
  return /^<svg\b/.test(svg)&&(svg.match(/<svg\b/g)??[]).length===1&&!/<\/svg\s*>/.test(svg)?svg+'</svg>':svg;
}

const labels={smiles:'Chemical structure',abc:'Musical score',tikz:'Technical diagram'};
try {
  const svg = family==='smiles'?await drawMolecule():family==='abc'?drawMusic():await drawTeX();
  const safe = sanitizeSvg(svg, labels[family]);
  // The App uses an image document and inherits no page CSS. Give the
  // standalone image deterministic neutral ink in both host appearances.
  safe.setAttribute('color','#20242a');
  const result = new XMLSerializer().serializeToString(safe);
  if (Buffer.byteLength(result) > 160 * 1024) throw new Error('Notation image too large');
  parentPort.postMessage({svg:result,label:labels[family]});
} catch {
  parentPort.postMessage({error:'The notation could not be rendered. Check the source below.'});
} finally {
  window.close();
}
