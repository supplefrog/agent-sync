// SPDX-License-Identifier: AGPL-3.0-only
// One Connect action, bounded by activation/component/request lifetime.
// A cancelled picker may already have granted a folder in the host; this code
// cannot revoke that host grant, but must not persist/re-register afterwards.
import { loadCurrentProjection } from './inline/lesson-identity.mjs';
export async function connectLessonExport(ctx,{owner,chatId,snapshot,minimumRevision},{isCurrent,verifyBytes,install}) {
  const cancelled=()=>({connected:false,cancelled:true});
  if(!isCurrent())return cancelled();
  const match=/^(teach|practice)-r([0-9]+)-([a-f0-9]{64})\.json$/.exec(snapshot??'');
  if(typeof owner!=='string'||!owner||owner!==owner.trim()||owner==='new'||
    !/^[A-Za-z0-9_-]{1,80}$/.test(chatId??'')||!match)throw new Error('Invalid explicit lesson identity.');
  minimumRevision=minimumRevision??Number(match[2]);
  if(!Number.isSafeInteger(minimumRevision)||minimumRevision<Number(match[2]))throw new Error('Invalid current lesson revision floor.');
  const selected=await ctx.files.requestFolder();
  if(!isCurrent())return cancelled();
  if(!selected.ok||!selected.folder)return{connected:false,cancelled:false};
  // The old directive is a revision floor, not a demand to copy an obsolete
  // immutable snapshot into the newly selected current exports directory.
  const files={async readText(folder,file){
    if(!isCurrent())return{ok:false};
    const result=await ctx.files.readText(folder,file);
    return isCurrent()?result:{ok:false};
  }};
  let selectedView;
  try {selectedView=await loadCurrentProjection(files,{chatId,kind:match[1],folder:selected.folder.id},minimumRevision,verifyBytes);}
  catch(error){if(!isCurrent())return cancelled();throw error;}
  if(!isCurrent())return cancelled();
  const previous=ctx.storage.get('bindings',[]);
  if(!Array.isArray(previous))throw new Error('Invalid stored folder bindings.');
  const old=previous.find(item=>item.ownerSessionId===owner&&item.chatId===chatId);
  const backupKey='binding-rollback:v1:'+JSON.stringify([owner,chatId,old?.folder]);
  if(old&&ctx.storage.get(backupKey,null)===null){
    if(!isCurrent())return cancelled();
    // Opaque binding metadata only; never drafts, grants or raw state. A host
    // storage fault after this point must retain the backup for explicit recovery.
    ctx.storage.set(backupKey,{v:1,binding:{...old}});
    if(!isCurrent())return cancelled();
    if(JSON.stringify(ctx.storage.get(backupKey,null))!==JSON.stringify({v:1,binding:old}))throw new Error('Original connection backup was not retained.');
  }
  const rows=previous.filter(item=>!(item.ownerSessionId===owner&&item.chatId===chatId));
  const replacement={ownerSessionId:owner,chatId,kind:match[1],folder:selected.folder.id,minimumRevision:selectedView.revision};
  rows.push(replacement);
  if(!isCurrent())return cancelled();
  function restoreIfOurs() {
    if(!isCurrent())return;
    const actual=ctx.storage.get('bindings',[]);
    if(!Array.isArray(actual))return;
    const current=actual.find(item=>item.ownerSessionId===owner&&item.chatId===chatId);
    if(JSON.stringify(current)!==JSON.stringify(replacement))return;
    const restored=actual.filter(item=>!(item.ownerSessionId===owner&&item.chatId===chatId));
    if(old)restored.push(old);
    if(isCurrent())ctx.storage.set('bindings',restored);
  }
  try {
    ctx.storage.set('bindings',rows);
    if(!isCurrent())return cancelled();
    if(JSON.stringify(ctx.storage.get('bindings',[]))!==JSON.stringify(rows))throw new Error('Folder binding was not retained.');
    if(!isCurrent())return cancelled();
    const connected=install(rows)===true;
    if(!connected)restoreIfOurs();
    return{connected,cancelled:false};
  }catch(error){restoreIfOurs();throw error;}
}
