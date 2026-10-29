// SPDX-License-Identifier: AGPL-3.0-only
// One Connect action, bounded by activation/component/request lifetime.
// A cancelled picker may already have granted a folder in the host; this code
// cannot revoke that host grant, but must not persist/re-register afterwards.
export async function connectLessonExport(ctx,{owner,chatId,snapshot},{isCurrent,verifyBytes,install}) {
  const cancelled=()=>({connected:false,cancelled:true});
  if(!isCurrent())return cancelled();
  const match=/^(teach|practice)-r([0-9]+)-([a-f0-9]{64})\.json$/.exec(snapshot??'');
  if(typeof owner!=='string'||!owner||owner!==owner.trim()||owner==='new'||
    !/^[A-Za-z0-9_-]{1,80}$/.test(chatId??'')||!match)throw new Error('Invalid explicit lesson identity.');
  const selected=await ctx.files.requestFolder();
  if(!isCurrent())return cancelled();
  if(!selected.ok||!selected.folder)return{connected:false,cancelled:false};
  const file=await ctx.files.readText(selected.folder.id,snapshot);
  if(!isCurrent())return cancelled();
  if(!file.ok||typeof file.text!=='string'||new TextEncoder().encode(file.text).length>262144)
    throw new Error('Select this lesson\'s redacted exports.');
  await verifyBytes(snapshot,file.text);
  if(!isCurrent())return cancelled();
  const view=JSON.parse(file.text);
  if(view.chatId!==chatId||(view.kind==='practice'?'practice':'teach')!==match[1]||view.revision!==Number(match[2]))
    throw new Error('Snapshot lesson or revision differs.');
  if(!isCurrent())return cancelled();
  const previous=ctx.storage.get('bindings',[]);
  if(!Array.isArray(previous))throw new Error('Invalid stored folder bindings.');
  const rows=previous.filter(item=>!(item.ownerSessionId===owner&&item.chatId===chatId));
  rows.push({ownerSessionId:owner,chatId,kind:match[1],folder:selected.folder.id});
  if(!isCurrent())return cancelled();
  ctx.storage.set('bindings',rows);
  if(!isCurrent())return cancelled();
  if(JSON.stringify(ctx.storage.get('bindings',[]))!==JSON.stringify(rows))throw new Error('Folder binding was not retained.');
  if(!isCurrent())return cancelled();
  return{connected:install(rows)===true,cancelled:false};
}
