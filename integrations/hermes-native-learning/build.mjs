// SPDX-License-Identifier: AGPL-3.0-only
// Maintainer build only; reuses an explicitly selected existing toolchain.
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
const here = path.dirname(fileURLToPath(import.meta.url));
if (!process.argv[2]) throw new Error('Pass the existing Hermes source/toolchain directory; no dependency download is performed.');
const require = createRequire(path.join(path.resolve(process.argv[2]),'package.json'));
const esbuild = require('esbuild');
if (esbuild.version !== '0.28.2') throw new Error('This build receipt supports esbuild0.28.2 only.');
const template = fs.readFileSync(path.join(here,'src/inline/inline-template.html'),'utf8');
const css = template.match(/<style>([\s\S]*?)<\/style>/)?.[1];
if (!css) throw new Error('Existing inline style block missing.');
const result = await esbuild.build({entryPoints:[path.join(here,'src/desktop-entry.mjs')],outfile:path.join(here,'desktop/plugin.js'),
  bundle:true,platform:'browser',format:'esm',target:'es2022',sourcemap:false,minify:false,metafile:true,
  external:['@hermes/plugin-sdk','react','react/jsx-runtime'],define:{__LH_STYLE__:JSON.stringify(css.replaceAll('#lh-inline-lesson','.lh-native-lesson'))},
  banner:{js:'// SPDX-License-Identifier: AGPL-3.0-only; LearnHarness native integration. See NOTICE.md.'}});
const imports = Object.values(result.metafile.outputs).flatMap(output => output.imports);
if (imports.some(item => !item.external || !['@hermes/plugin-sdk','react','react/jsx-runtime'].includes(item.path))) throw new Error('Bundle retained an unsupported import.');
console.log(JSON.stringify({built:'desktop/plugin.js',esbuild:esbuild.version,imports:imports.map(i=>i.path),providerCalls:0}));
