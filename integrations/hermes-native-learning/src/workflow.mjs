// SPDX-License-Identifier: AGPL-3.0-only
// Read-only orchestration facts over the existing transcript, not an agent loop.
export function learningWorkflow(kind, view, messages) {
  const last=messages.at(-1);
  if(kind==='practice') {
    if(view.activeProblem) return last?.customType==='practice-thinking'
      ? {stage:'practice-reaction',allowed:['practice-reply','conclude'],afterThinkingId:last.id,
        instruction:'Read the thinking. A working trace is not a claimed answer. Give one requested hint or conclude from evidence; never replace the committed solution.'}
      : {stage:'await-thinking',allowed:[],instruction:'End the turn and wait for genuine thinking. Do not pose another problem.'};
    if(view.nextAllowed) return {stage:'pose-practice',allowed:['problem'],instruction:'Pose one problem from the available material, commit a worked solution, then end the turn.'};
    if(last?.role==='user') return {stage:'practice-discussion',allowed:['practice-discuss'],afterMessageId:last.id,
      instruction:'Answer the question about the concluded problem and end the turn. A clarification is not Next.'};
    return {stage:'practice-pause',allowed:[],instruction:'Wait for a question or explicit Next. Do not auto-advance.'};
  }
  if(view.question) return {stage:'await-answer',allowed:[],toolCallId:view.question.toolCallId,
    instruction:'One pending question. Wait for the learner; no answer, assessment or explanation may be invented.'};
  if(view.phase==='probe') return {stage:'diagnose',allowed:['probe','recall','ask','probe_done'],
    instruction:'Bracket the narrow prerequisite strands from real answers. Persist the evidence-grounded assessment before planning.'};
  if(!view.plan) return {stage:'plan',allowed:['plan_init'],instruction:'Build the validated dependency DAG from the diagnosis; stable node IDs, no dangling references.'};
  if(!view.plan.approved) return {stage:'await-plan-approval',allowed:[],instruction:'Return the proposed plan and wait for initial learner approval.'};
  if(view.continuationOwed) {
    const call=messages.filter(m=>m.role==='assistant').flatMap(m=>m.content).filter(b=>b.type==='toolCall'&&['quiz','explain'].includes(b.name)).at(-1);
    return {stage:call?.arguments.type==='predict'?'resolve-prediction':'react-to-check',
      allowed:view.continuation?[call?.arguments.type==='predict'?'teach':'reply']:['continue'],
      continuation:view.continuation??null,
      instruction:call?.arguments.type==='predict'?'Claim once, resolve the actual prediction explicitly, finish one teaching step, then pose one check.':'Claim once and react to the real check. A miss calls for repair before building further; visited is not mastered.'};
  }
  return {stage:'teaching-decision',allowed:['quiz','explain','plan_init'],
    instruction:'After a teaching step pose its check; after check feedback choose repair, next meaningful prediction, or wrap-up using evidence. Do not infer mastery or automate advancement from visited status. Legitimate plan rewrites do not repeat initial approval.'};
}
