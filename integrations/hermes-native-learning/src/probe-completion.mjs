// SPDX-License-Identifier: AGPL-3.0-only
// v0.4.1 reliability invariant, adapted to this port's native result format.
// A failed/partial historical call is evidence, not a completed assessment.
import { PROBE_DONE_ACK_TEXT } from './vendor/runtime/probe-ack.ts';
export function successfulProbeDone(messages) {
  const calls=new Map(),completed=[];
  for(const message of messages) {
    if(message.role==='assistant')for(const block of message.content??[])
      if(block.type==='toolCall'&&block.name==='probe_done')calls.set(block.id,block);
    if(message.role!=='toolResult'||message.toolName!=='probe_done'||message.isError===true||message.details?.ok===false)continue;
    const call=calls.get(message.toolCallId);if(!call)continue;
    const texts=(message.content??[]).filter(block=>block.type==='text').map(block=>block.text);
    let refused=false,affirmed=message.details?.ok===true;
    for(const text of texts) {
      if(text===PROBE_DONE_ACK_TEXT)affirmed=true;
      try {const result=JSON.parse(text);if(result?.ok===false)refused=true;if(result?.ok===true)affirmed=true;}catch{/* Plain acknowledgment is the native normal path. */}
    }
    if(affirmed&&!refused&&!completed.some(prior=>prior.id===call.id))completed.push(call);
  }
  return completed;
}
