// SPDX-License-Identifier: AGPL-3.0-only
// Adapt only actual native Codex tool shapes; never dispatch or invent receipts.
import { requireState } from '../store.mjs';
const object=v=>v!==null&&typeof v==='object'&&!Array.isArray(v);
const keys=(v,allowed)=>object(v)&&Object.keys(v).every(k=>allowed.includes(k));
const id=v=>typeof v==='string'&&v.length>0&&v.length<=300&&v===v.trim();
export function codexDispatch(prepared) {
  requireState(prepared?.tool==='delegate_task'&&prepared.arguments?.tasks?.length===1,'invalid_job_dispatch','Expected one prepared worker.');
  const task=prepared.arguments.tasks[0];
  return {...prepared,tool:'spawn_agent',arguments:{message:task.goal+'\n'+task.context+
    '\nThis is a fresh Codex child. Do not forge MCP metadata or read/write the parent lesson. Return the real saved result hash.',fork_context:false},
    scope:'Prepared native Codex spawn_agent input only; not dispatched. Verify actual installed tool shape, route, limits and permissions before invocation. Native wait_agent result, not a Hermes background callback, establishes completion.'};
}
export function codexAdmission(receipt) {
  requireState(keys(receipt,['agent_id','nickname'])&&id(receipt.agent_id)&&
    (receipt.nickname===undefined||receipt.nickname===null||typeof receipt.nickname==='string'),
    'invalid_job_admission','Use the actual native Codex spawn_agent result, not a Hermes/joined/synthetic receipt.');
  return {delegationId:receipt.agent_id,subagentId:receipt.agent_id,hostRuntime:'t3-codex',hostAdmission:structuredClone(receipt)};
}
export function codexCompletion(job,receipt,error) {
  requireState(keys(receipt,['status','timed_out'])&&receipt.timed_out===false&&object(receipt.status)&&
    Object.keys(receipt.status).length===1&&Object.hasOwn(receipt.status,job.subagentId),
    'invalid_job_completion','Completion requires an actual terminal wait_agent result for this exact child.');
  const state=receipt.status[job.subagentId];
  const success=keys(state,['completed'])&&Object.hasOwn(state,'completed')&&(state.completed===null||typeof state.completed==='string');
  const failure=(keys(state,['errored'])&&typeof state.errored==='string')||['interrupted','shutdown','not_found'].includes(state);
  requireState(error?failure:success,'job_not_terminal','Timeout, running/unknown and mismatched outcomes do not complete work.');
  return structuredClone(receipt);
}
export function codexControl(job,control,message) {
  requireState(job.hostRuntime==='t3-codex'&&id(job.subagentId),'invalid_job_control','A real native Codex child handle is required.');
  if(control==='list')return {tool:'wait_agent',arguments:{targets:[job.subagentId],timeout_ms:10000}};
  if(control==='steer')return {tool:'send_input',arguments:{target:job.subagentId,message,interrupt:false}};
  return {tool:'close_agent',arguments:{target:job.subagentId}};
}
