// SPDX-License-Identifier: AGPL-3.0-only
// Local command authority is user admission + filesystem permissions, NOT env labels.
const object=v=>v!==null&&typeof v==='object'&&!Array.isArray(v);
const canonical=v=>typeof v==='string'&&v.length>0&&v.length<=300&&v===v.trim()&&v!=='new';
export function localCheck(ok,code,message) {
  if(!ok)throw Object.assign(new Error(message),{name:'FixedLocalError',code});
}
function fields(v,names) {localCheck(object(v)&&Object.keys(v).every(k=>names.includes(k)),'invalid_local_input','Unknown local input field.');}
export function fixedLocalBinding(enrollment,config,labels) {
  fields(enrollment,['version','configFile','chatId','nativeThreadId']);
  localCheck(enrollment.version===1&&canonical(enrollment.nativeThreadId)&&
    typeof enrollment.configFile==='string'&&typeof enrollment.chatId==='string'&&/^[A-Za-z0-9_-]{1,80}$/.test(enrollment.chatId),
    'invalid_local_enrollment','Explicit fixed local enrollment required.');
  localCheck(canonical(labels?.CODEX_THREAD_ID)&&canonical(labels?.CODEX_TOOL_CALL_ID),
    'local_correlation_missing','Use the admitted native Codex execution tool; correlation labels missing.');
  localCheck(labels.CODEX_THREAD_ID===enrollment.nativeThreadId,'local_correlation_mismatch','Native correlation changed; reconcile enrollment.');
  localCheck(object(config)&&Array.isArray(config.lessons),'invalid_local_enrollment','Validated configuration required.');
  const matches=config.lessons.filter(b=>b.ownerSessionId===enrollment.nativeThreadId&&b.chatId===enrollment.chatId);
  localCheck(matches.length===1,'local_not_enrolled','The fixed lesson is absent, invalid, duplicate or revoked.');
  return Object.freeze({...matches[0],runtimeHost:'t3-codex-local'});
}
export function runFixedLocal(binding,payload,execute) {
  fields(payload,['command','present']);
  localCheck(object(payload.command)&&typeof payload.command.op==='string','invalid_local_input','One existing learning command required.');
  localCheck(payload.present===undefined||typeof payload.present==='boolean','invalid_local_input','Presentation must be boolean.');
  const command=payload.command;
  localCheck(!['root','output','configFile','ownerSessionId','nativeThreadId','path'].some(k=>k in command),
    'invalid_local_input','No owner, configuration or path selectors.');
  localCheck(command.chatId===undefined||command.chatId===binding.chatId,'wrong_host_session','No foreign lesson selector.');
  localCheck(!['list','local-enroll','configure'].includes(command.op),'invalid_local_input','No target selection or enrollment operation.');
  return execute(binding,{...command,chatId:binding.chatId});
}
export function requirePublicView(view) {
  localCheck(object(view)&&Number.isSafeInteger(view.revision),'invalid_public_view','Current redacted projection required.');
  localCheck(!view.question||!['correctIndices','committedAnswer','explanation','correctAnswer'].some(k=>k in view.question),
    'commitment_exposed','Pending question contains teacher-only fields.');
  localCheck(!view.activeProblem||Object.keys(view.activeProblem).every(k=>['toolCallId','statement'].includes(k)),
    'commitment_exposed','Active practice problem contains teacher-only fields.');
  return view;
}
