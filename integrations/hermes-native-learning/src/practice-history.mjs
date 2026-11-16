// SPDX-License-Identifier: AGPL-3.0-only
import { validDrawing } from './drawing.mjs';
import { FileSessionStore, requireState } from './store.mjs';

const bytes=value=>Buffer.byteLength(JSON.stringify(value));
export function newestWithin(entries, capacity, cost=bytes) {
  let remaining=capacity, start=entries.length;
  while(start>0) {
    const n=cost(entries[start-1])+1;
    if(n>remaining&&start<entries.length)break;
    remaining-=n;start--;
  }
  return entries.slice(start);
}

export function practiceAttempts(record,problemId,before) {
  const entries=record.messages.filter(message=>message.role==='custom'&&message.customType==='practice-thinking'&&
    message.details.problemCallId===problemId).map(message=>({
      id:message.id,text:message.details.text,
      ...(validDrawing(message.details.drawing)?{drawing:message.details.drawing}:{}),
      ...(message.details.coding?{coding:message.details.coding}:{}),
    }));
  const end=before===undefined?entries.length:entries.findIndex(row=>row.id===before);
  requireState(end>=0,'invalid_history_cursor','The response anchor is outside this exercise.');
  const rows=newestWithin(entries.slice(0,end),80*1024,row=>bytes(row)+bytes(row.text));
  return {problemId,rows,nextBefore:rows.length<end?rows[0].id:null};
}

export function readPracticeHistory(binding,{problemId,before,expectedRevision}) {
  requireState(binding.kind==='practice'&&typeof problemId==='string'&&typeof before==='string',
    'invalid_practice_history','Use an older-response cursor from the saved practice view.');
  const record=new FileSessionStore(binding.root).read(binding.chatId);
  requireState(record.adapter.revision===expectedRevision,'stale_native_revision','Refresh the practice problem before reading earlier responses.');
  return practiceAttempts(record,problemId,before);
}
