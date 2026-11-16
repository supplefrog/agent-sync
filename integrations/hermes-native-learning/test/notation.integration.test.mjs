// SPDX-License-Identifier: AGPL-3.0-only
import assert from 'node:assert/strict';
import test from 'node:test';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {renderNotation} from '../src/notation.mjs';

const runtimeFile=process.env.LH_NOTATION_TOOLCHAIN
  ?path.join(process.env.LH_NOTATION_TOOLCHAIN,'package.json')
  :fileURLToPath(new URL('../notation-runtime/package.json',import.meta.url));
const haveDeps=fs.existsSync(path.join(path.dirname(runtimeFile),'node_modules','jsdom','package.json'));
const sources={
  smiles:'CC(=O)Oc1ccccc1C(=O)O',
  abc:'X:1\nT:Scale\nM:4/4\nL:1/4\nK:C\nC D E F | G A B c |]',
  tikz:String.raw`\usepackage{tikz}`+'\n'+String.raw`\begin{document}`+'\n'+
    String.raw`\begin{tikzpicture}\draw (0,0) circle (1);\end{tikzpicture}`+'\n'+String.raw`\end{document}`,
};
test('three pinned renderers produce inert static SVG rather than source fallback',{skip:!haveDeps},async()=>{
  const results=await Promise.all(Object.entries(sources).map(([family,source])=>renderNotation({family,source},{runtimeFile})));
  assert.deepEqual(results.map(item=>item.label),['Chemical structure','Musical score','Technical diagram']);
  for(const {svg} of results) {
    assert.match(svg,/^<svg\b/);
    assert.match(svg,/<(?:path|circle|line|polygon)\b/);
    assert.doesNotMatch(svg,/<(?:script|foreignObject|iframe)\b|\bon\w+=|(?:href|src)="(?:https?:|file:)/i);
  }
});
test('blocks file directives, incomplete tunes and multiple chemical fragments',async()=>{
  for(const [family,source] of [['smiles','C.C'],['abc','X:1\nC D E'],['tikz',sources.tikz+'\\input{secrets}']])
    await assert.rejects(renderNotation({family,source},{runtimeFile}),error=>error.code==='invalid_notation');
  if(haveDeps)await assert.rejects(renderNotation({family:'smiles',source:'X!X!'},{runtimeFile}),/could not be rendered/);
});
