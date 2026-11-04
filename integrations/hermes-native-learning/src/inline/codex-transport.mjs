// SPDX-License-Identifier: AGPL-3.0-only
// A native visualization request is never a persistence receipt.
export function codexTransport(win,view) {
  const bound={chatId:view.chatId,kind:view.kind==='practice'?'practice':'teach',expectedRevision:view.revision};
  return async action=>{
    if(action.chatId!==bound.chatId)throw new Error('Action belongs to another lesson.');
    if(typeof win.openai?.sendFollowUpMessage!=='function')throw new Error('Open this lesson in Codex to submit. Your draft is retained.');
    const prompt='lh.t3 '+JSON.stringify({...bound,action});
    if(new TextEncoder().encode(prompt).length>65536)throw new Error('Answer exceeds 64 KiB; nothing was sent or truncated.');
    await win.openai.sendFollowUpMessage({prompt,title:action.type==='resume'?'Reopen saved lesson':'Submit lesson response'});
    return {requested:true};
  };
}
export function codexOptions(win,view) {
  const send=codexTransport(win,view);
  return {send,exploration:win.document.getElementById('lh-native-exploration'),
    onResume:()=>send({type:'resume',chatId:view.chatId}).catch(()=>{})};
}
