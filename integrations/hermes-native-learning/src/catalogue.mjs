// SPDX-License-Identifier: AGPL-3.0-only
// Explicitly enrolled lessons only; no profile/history scan or owner fallback.
import fs from 'node:fs';
import { FileSessionStore, requireState } from './store.mjs';
export function lessonCatalogue(config,env) {
  const aliases=[env.HERMES_SESSION_ID,env.HERMES_UI_SESSION_ID].filter(value=>
    typeof value==='string'&&value.length>0&&value===value.trim()&&value!=='new');
  const owners=new Set(config.lessons.filter(binding=>aliases.includes(binding.ownerSessionId)).map(binding=>binding.ownerSessionId));
  requireState(owners.size===1,'caller_unqualified','One explicitly configured owner is required; no active-session fallback.');
  const owner=[...owners][0],lessons=[];
  for(const binding of config.lessons.filter(binding=>binding.ownerSessionId===owner)) {
    const store=new FileSessionStore(binding.root);
    if(!fs.existsSync(store.file(binding.chatId))){lessons.push({chatId:binding.chatId,kind:binding.kind,exists:false});continue;}
    const record=store.read(binding.chatId);
    requireState((record.kind??'teach')===binding.kind,'wrong_session_kind','Configured mode differs from the saved lesson.');
    lessons.push({chatId:binding.chatId,kind:binding.kind,exists:true,title:record.title,
      createdAt:record.createdAt,updatedAt:record.updatedAt,revision:record.adapter.revision});
  }
  lessons.sort((a,b)=>(b.updatedAt??'').localeCompare(a.updatedAt??'')||a.chatId.localeCompare(b.chatId));
  return{ok:true,ownerSessionId:owner,lessons,
    instruction:'Choose an enrolled lesson and use view/export to reopen it. Use init only for an explicitly configured missing lesson. No new conversation or grant is created.'};
}
