// SPDX-License-Identifier: AGPL-3.0-only
import fs from 'node:fs';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {renderInline} from '../inline/build-inline.mjs';
import {requireState} from '../store.mjs';
export function nativePresentation(binding,view,readAsset) {
  const visuals=(view.visuals??[]).map(descriptor=>({...descriptor,source:readAsset(descriptor.file).text}));
  const source=renderInline(view,{codex:true,visuals});
  requireState(Buffer.byteLength(source)<1048576,'native_presentation_too_large','Native lesson exceeds 1 MiB; use fewer or smaller visuals.');
  const sha256=createHash('sha256').update(source).digest('hex');
  fs.mkdirSync(binding.output,{recursive:true});
  requireState(fs.realpathSync(binding.output)===binding.output,'invalid_presentation_path','Export directory cannot be redirected.');
  const file=path.join(binding.output,`codex-r${view.revision}-${sha256}.html`);
  try{fs.writeFileSync(file,source,{flag:'wx'});}
  catch(error){if(error.code!=='EEXIST')throw error;
    requireState(fs.realpathSync(file)===file&&fs.lstatSync(file).isFile()&&fs.readFileSync(file,'utf8')===source,
      'presentation_changed','Existing native presentation differs.');}
  return{path:file,sha256,revision:view.revision,format:'codex-visualize-fragment',
    instruction:'In native Codex, include this absolute path in a visualize content reference in your final reply. On an actual lh.t3 user event call learning_input with its exact fields, read current context, save the required teacher reaction and return learning_view. A resume event only reopens the view. Requested delivery is not a saved answer.'};
}
