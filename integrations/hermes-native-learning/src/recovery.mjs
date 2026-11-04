// SPDX-License-Identifier: AGPL-3.0-only
// One teacher recovery policy shared by local CLI and MCP context retrieval.
// Policy does not grant tool authority or dispatch an agent.
export const TEACHER_RECOVERY = Object.freeze({
  version:1,
  canonicalContext:'Read current context/context-page for this enrolled lesson before reacting; host conversation history may be behind another host.',
  currentQuestion:'Apply only the actual learner event for the matching question and expected revision. A stale event must not be reattached to a newer question.',
  uncertainOutcome:'Read current state and saved answer IDs before repeating any operation. Export failure after operationComplete is not a failed save.',
  recovery:'Reopen is read-only: retain pending question, answer, confidence and reasoning drafts. Do not regenerate a question or invent an answer on refresh.',
  feedback:'Save the reaction and next question through the existing revision/continuation guards, then visibly deliver the saved feedback and current card in the originating host.',
});
