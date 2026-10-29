// SPDX-License-Identifier: AGPL-3.0-only
// Host-neutral state adapter derived from LearnHarness v0.3.4 contracts.
import { randomUUID } from 'node:crypto';
import { isDeepStrictEqual } from 'node:util';
import { FileSessionStore, StateError, requireState } from './store.mjs';
import {
  normalizeOptions, parseOptionsIfString, quizInputProblems, explainInputProblems,
  seededRandom, shuffleOptions, resolveCorrect, buildAnswer, compactAnswerForModel,
  toClientQuestion, questionNeedsReveal,
} from './vendor/runtime/question-pure.ts';
import { parseChatInput } from './vendor/runtime/input-parser.ts';
import { danglingQuestionOf, hasProbeDone, needsContinuation } from './vendor/runtime/native-scans.ts';
import { toolQuestionKind, QUESTION_TOOLS } from './vendor/runtime/pending.ts';
import { createTree } from './vendor/runtime/plan-tree.ts';
import { derivePlanStatusesLh, derivedNodeStatus } from './vendor/runtime/plan-contract.ts';
import { parseMermaidPlan } from './vendor/runtime/mermaid-plan.ts';
import { PROBE_DONE_ACK_TEXT } from './vendor/runtime/probe-ack.ts';

const now = () => new Date().toISOString();
const id = () => `msg_${randomUUID()}`;
const clone = (value) => structuredClone(value);
function object(value, label) {
  requireState(value !== null && typeof value === 'object' && !Array.isArray(value), 'invalid_input', `${label} must be an object.`);
  return value;
}
function text(value, label, max = 16000) {
  requireState(typeof value === 'string' && value.trim().length > 0 && value.length <= max,
    'invalid_input', `${label} must be non-empty text of at most ${max} characters.`);
  return value;
}
function callId(value) {
  requireState(typeof value === 'string' && /^[A-Za-z0-9_-]{1,100}$/.test(value), 'invalid_call_id', 'A stable toolCallId is required.');
  return value;
}
function calls(record) {
  return record.messages.filter(m => m.role === 'assistant').flatMap(m => m.content.filter(b => b.type === 'toolCall'));
}
function pending(record, expected) {
  const p = danglingQuestionOf(record.messages);
  requireState(p && p.toolCallId === expected, 'stale_question', 'This input does not target the current dangling question.');
  return p;
}
function idle(record) { requireState(!danglingQuestionOf(record.messages), 'question_pending', 'Resolve the current question first.'); }
function phase(record) { return !hasProbeDone(record.messages) ? 'probe' : !record.tree ? 'plan' : 'teach'; }
// The revision is an audit of the learner's initial go-ahead, not a latch
// that plan_init rewrites must renew. Pre-approval rewrites still require
// approval of the latest presented map before teaching starts.
function initialPlanApproved(record) {
  const approved = record.adapter.approvedPlanRevision;
  return Boolean(record.tree && Number.isSafeInteger(approved) && approved >= 1 && approved <= record.adapter.planRevision);
}
function appendCall(record, toolCallId, name, input) {
  record.messages.push({ id: id(), role: 'assistant', timestamp: Date.now(),
    content: [{ type: 'toolCall', id: toolCallId, name, arguments: clone(input) }] });
  record.adapter.continuation = null;
}
function appendResult(record, toolCallId, toolName, details, modelValue = details) {
  const result = { id: id(), role: 'toolResult', toolCallId, toolName, timestamp: Date.now(),
    content: [{ type: 'text', text: typeof modelValue === 'string' ? modelValue : JSON.stringify(modelValue) }],
    details: clone(details), isError: false };
  record.messages.push(result);
  return result;
}

function questionData(name, input, toolCallId) {
  object(input, 'Question input');
  text(input.question, 'question');
  const kind = toolQuestionKind(name);
  if (input.details !== undefined) text(input.details, 'details');
  const q = { id: toolCallId, kind, question: input.question, context: input.details,
    questionType: input.type, createdAt: now(), options: [], mode: 'text' };
  if (kind === 'explain') {
    text(input.correctAnswer, 'correctAnswer');
    requireState(!explainInputProblems(input).length, 'invalid_question', 'A committed answer is required.');
    q.committedAnswer = input.correctAnswer;
  } else {
    const list = parseOptionsIfString(input.options);
    if (kind === 'quiz' || input.options !== undefined) {
      requireState(Array.isArray(list) && list.length >= (kind === 'quiz' ? 2 : 1) && list.length <= 30,
        'invalid_question', 'Provide valid answer options.');
      for (const option of list) {
        object(option, 'option'); text(option.label, 'option.label', 2000);
        if (option.value !== undefined) text(option.value, 'option.value', 2000);
        requireState(kind !== 'quiz' || option.description === undefined, 'invalid_question', 'Quiz options contain bare claims; explanations belong after the answer.');
      }
      q.options = shuffleOptions(normalizeOptions(list), seededRandom(toolCallId));
      requireState(input.multiSelect === undefined || typeof input.multiSelect === 'boolean', 'invalid_question', 'multiSelect must be boolean.');
      q.mode = input.multiSelect ? 'multi-select' : 'single-select';
    }
    if (kind === 'quiz') {
      requireState(typeof input.correctAnswer === 'string' || (Array.isArray(input.correctAnswer) && input.correctAnswer.every(v => typeof v === 'string')),
        'invalid_question', 'correctAnswer must contain option keys.');
      text(input.explanation, 'explanation');
      const problems = quizInputProblems({ ...input, options: list });
      requireState(!problems.length, 'invalid_question', problems.join('\n'));
      const resolved = resolveCorrect(input.correctAnswer, q.options);
      requireState(!resolved.error, 'invalid_question', resolved.error);
      q.correctIndices = resolved.indices;
      q.explanation = input.explanation;
    }
  }
  return q;
}

function validateRequest(q, request) {
  object(request, 'answer request');
  requireState(Object.keys(request).every(k => ['values', 'dontKnow', 'other', 'text', 'thinking', 'readingThinking', 'confidence'].includes(k)),
    'invalid_answer', 'Unknown answer request field.');
  for (const key of ['text', 'other', 'thinking', 'readingThinking']) {
    if (request[key] !== undefined) requireState(typeof request[key] === 'string' && request[key].length <= 16000, 'invalid_answer', `Invalid ${key}.`);
  }
  requireState(request.dontKnow === undefined || typeof request.dontKnow === 'boolean', 'invalid_answer', 'dontKnow must be boolean.');
  const values = request.values ?? [];
  requireState(Array.isArray(values) && values.every(v => typeof v === 'string' && q.options.some(o => o.value === v)) && new Set(values).size === values.length,
    'invalid_answer', 'Selections must be unique current option values.');
  requireState(q.mode !== 'single-select' || values.length <= 1, 'invalid_answer', 'Select only one option.');
  requireState(!request.dontKnow || (!values.length && !request.text?.trim() && !request.other?.trim()), 'invalid_answer', 'dontKnow cannot carry an attempted answer.');
  requireState(request.confidence === undefined || (q.kind === 'quiz' && !request.dontKnow && Number.isFinite(request.confidence) && request.confidence >= 0 && request.confidence <= 100),
    'invalid_answer', 'Confidence is a probability from 0–100 on a real quiz answer.');
  requireState(q.kind === 'ask' || !request.other, 'invalid_answer', 'Other is an ask-only response.');
  requireState(q.mode === 'text' || !request.text, 'invalid_answer', 'Use option values for this question.');
  requireState(request.dontKnow || (q.mode === 'text' ? Boolean(request.text?.trim()) : Boolean(values.length || (q.kind === 'ask' && request.other?.trim()))),
    'invalid_answer', 'Choose an answer or explicitly say dontKnow.');
}

function answerFromRequest(record, toolCallId, request) {
  const p = pending(record, toolCallId);
  const q = record.adapter.questions[toolCallId];
  validateRequest(q, request);
  return buildAnswer(q, request, p.tool);
}

function answerFromEnvelope(record, input) {
  const p = pending(record, input.toolCallId);
  const answer = object(input.answer, 'answer');
  requireState(answer.kind === toolQuestionKind(p.tool) && Array.isArray(answer.answers) && answer.dismissed !== true,
    'invalid_answer', 'Answer kind must match the pending question. Closing a view is not a dismissal.');
  requireState(answer.answers.every(a => a && typeof a.value === 'string'), 'invalid_answer', 'Malformed answer selections.');
  const request = { values: answer.answers.map(a => a.value) };
  for (const key of ['dontKnow', 'text', 'other', 'thinking', 'readingThinking', 'confidence']) if (answer[key] !== undefined) request[key] = answer[key];
  const canonical = answerFromRequest(record, input.toolCallId, request);
  for (const key of ['questionText', 'tool', 'questionType', 'options', 'correct', 'correctIndices', 'committed', 'explanation', 'answers']) {
    if (answer[key] !== undefined) requireState(isDeepStrictEqual(answer[key], canonical[key]), 'altered_answer', `Answer field ${key} disagrees with the stored commitment.`);
  }
  return canonical;
}

export class TeachingAdapter {
  constructor(root) { this.store = new FileSessionStore(root); }
  create({ chatId, title, goal }) {
    text(title, 'title', 300); text(goal, 'goal', 2000);
    this.store.change(chatId, () => ({ record: { id: chatId, title, createdAt: now(), updatedAt: now(), version: 1,
      messages: [{ id: id(), role: 'user', content: goal, timestamp: Date.now() }],
      adapter: { version: 1, revision: 0, goal, questions: {}, questionOpen: {}, planRevision: 0,
        approvedPlanRevision: null, teachingSteps: [], continuation: null } }, result: { ok: true } }), { create: true });
    return this.view(chatId);
  }
  tool({ chatId, toolCallId, name, input }) {
    callId(toolCallId); object(input, 'tool input');
    this.store.change(chatId, record => {
      idle(record);
      requireState(!calls(record).some(c => c.id === toolCallId), 'replayed_call', 'toolCallId has already been used.');
      if (QUESTION_TOOLS.includes(name)) {
        if (name === 'probe' || name === 'recall') {
          requireState(phase(record) === 'probe' && input.nodeId === undefined && input.type === undefined,
            'wrong_phase', 'Probe questions precede probe_done and carry no plan position.');
        } else if (name === 'quiz' || name === 'explain') {
          requireState(phase(record) === 'teach' && initialPlanApproved(record),
            'plan_unapproved', 'The learner must give the initial go-ahead before teaching.');
          requireState(record.tree.nodes.some(n => n.id === input.nodeId) && ['predict', 'check'].includes(input.type),
            'invalid_position', 'Teaching questions require a current plan node and predict/check role.');
          if (input.type === 'check') {
            const prediction = calls(record).filter(c => ['quiz', 'explain'].includes(c.name) && c.arguments.type === 'predict' && c.arguments.nodeId === input.nodeId).at(-1);
            requireState(prediction && record.adapter.teachingSteps.some(s => s.predictionCallId === prediction.id),
              'teaching_missing', 'A check follows the teaching step for the latest prediction.');
          }
        }
        const q = questionData(name, input, toolCallId);
        appendCall(record, toolCallId, name, input);
        record.adapter.questions[toolCallId] = q;
        record.adapter.questionOpen[toolCallId] = !questionNeedsReveal(name, input, phase(record));
      } else if (name === 'probe_done') {
        requireState(phase(record) === 'probe', 'wrong_phase', 'The probe has already concluded.');
        const assessment = object(input.assessment, 'assessment');
        requireState(Array.isArray(assessment.strands) && assessment.strands.length >= 1,
          'invalid_assessment', 'Provide at least one assessed dependency strand.');
        for (const strand of assessment.strands) { object(strand, 'strand'); text(strand.strand, 'strand'); text(strand.assessment, 'assessment'); }
        if (assessment.summary !== undefined) text(assessment.summary, 'summary');
        appendCall(record, toolCallId, name, input);
        appendResult(record, toolCallId, name, { ok: true }, PROBE_DONE_ACK_TEXT);
      } else if (name === 'plan_init') {
        requireState(hasProbeDone(record.messages), 'wrong_phase', 'Conclude the probe before planning.');
        text(input.mermaid, 'mermaid');
        const parsed = parseMermaidPlan(input.mermaid);
        requireState(parsed.ok && parsed.plan, 'invalid_plan', parsed.problems.join('\n'));
        let next;
        try { next = createTree(parsed.plan.nodes, parsed.plan.edges); }
        catch (error) { throw new StateError('invalid_plan', error.message); }
        appendCall(record, toolCallId, name, input);
        record.tree = next;
        record.adapter.planRevision++;
        appendResult(record, toolCallId, name, { ok: true, tree: next }, { ok: true, nodeIds: next.nodes.map(n => n.id) });
      } else throw new StateError('unsupported_tool', `Tool ${name} is outside the first slice.`);
      return { record, result: { ok: true } };
    });
    return this.view(chatId);
  }
  approvePlan({ chatId, planRevision, text: learnerText }) {
    text(learnerText, 'learner approval');
    this.store.change(chatId, record => {
      idle(record);
      requireState(record.tree && record.adapter.planRevision === planRevision, 'stale_plan', 'Approval targets an older plan.');
      requireState(!initialPlanApproved(record), 'replayed_approval', 'The learner has already given the initial go-ahead.');
      record.messages.push({ id: id(), role: 'user', content: learnerText, timestamp: Date.now() });
      record.adapter.approvedPlanRevision = planRevision;
      record.adapter.continuation = null;
      return { record, result: { ok: true } };
    });
    return this.view(chatId);
  }
  prepareAnswer({ chatId, toolCallId, request }) {
    const record = this.store.read(chatId);
    return { chatId, input: { type: 'answer', toolCallId, answer: answerFromRequest(record, toolCallId, request) } };
  }
  answerRequest(request) { return this.input(this.prepareAnswer(request)); }
  input(envelope) {
    object(envelope, 'chat envelope');
    requireState(Object.keys(envelope).every(k => ['chatId', 'input'].includes(k)), 'invalid_input', 'Use {chatId,input}; never send a client transcript.');
    const input = parseChatInput(envelope.input);
    const result = this.store.change(envelope.chatId, record => {
      if (input.type === 'answer') {
        const answer = answerFromEnvelope(record, input);
        const p = pending(record, input.toolCallId);
        appendResult(record, input.toolCallId, p.tool, answer, compactAnswerForModel(answer));
        record.adapter.continuation = null;
      } else if (input.type === 'text') {
        idle(record); text(input.text, 'text');
        record.messages.push({ id: id(), role: 'user', content: input.text, timestamp: Date.now() });
        record.adapter.continuation = null;
      } else if (input.type === 'continue') {
        idle(record);
        requireState(needsContinuation(record.messages), 'no_continuation', 'No unanswered teacher reaction is owed.');
        const tail = record.messages.at(-1).id;
        if (record.adapter.continuation?.after === tail) return { record, result: { ok: true, continuation: record.adapter.continuation, alreadyClaimed: true }, changed: false };
        record.adapter.continuation = { id: `continue_${randomUUID()}`, after: tail, status: 'claimed' };
        return { record, result: { ok: true, continuation: record.adapter.continuation, alreadyClaimed: false } };
      } else throw new StateError('unsupported_input', 'Practice thinking/next are preserved contracts, deferred until the teaching slice works.');
      return { record, result: { ok: true } };
    });
    return { ...result, view: this.view(envelope.chatId) };
  }
  setQuestionOpen({ chatId, toolCallId, open }) {
    requireState(typeof open === 'boolean', 'invalid_input', 'open must be boolean.');
    this.store.change(chatId, record => {
      pending(record, toolCallId);
      const changed = record.adapter.questionOpen[toolCallId] !== open;
      record.adapter.questionOpen[toolCallId] = open;
      return { record, result: { ok: true }, changed };
    });
    return this.view(chatId);
  }
  teachStep({ chatId, nodeId, predictionCallId, text: teachingText }) {
    text(teachingText, 'teaching step');
    this.store.change(chatId, record => {
      idle(record);
      requireState(initialPlanApproved(record), 'plan_unapproved', 'Give the initial go-ahead before teaching.');
      const prediction = calls(record).find(c => c.id === predictionCallId && ['quiz', 'explain'].includes(c.name));
      requireState(prediction?.arguments.type === 'predict' && prediction.arguments.nodeId === nodeId && record.tree.nodes.some(n => n.id === nodeId),
        'prediction_missing', 'Teaching must resolve an answered prediction on this plan node.');
      requireState(record.messages.some(m => m.role === 'toolResult' && m.toolCallId === predictionCallId), 'prediction_unanswered', 'The learner must commit a prediction first.');
      requireState(!record.adapter.teachingSteps.some(s => s.predictionCallId === predictionCallId), 'replayed_teaching', 'This prediction already has its teaching step.');
      const messageId = id();
      record.messages.push({ id: messageId, role: 'assistant', content: [{ type: 'text', text: teachingText }], timestamp: Date.now() });
      record.adapter.teachingSteps.push({ nodeId, predictionCallId, messageId });
      record.adapter.continuation = null;
      return { record, result: { ok: true } };
    });
    return this.view(chatId);
  }
  view(chatId) {
    const r = this.store.read(chatId);
    const p = danglingQuestionOf(r.messages);
    const statuses = r.tree ? derivePlanStatusesLh(r.tree, r.messages) : null;
    const assessment = calls(r).find(c => c.name === 'probe_done')?.arguments.assessment ?? null;
    return { chatId, revision: r.adapter.revision, phase: phase(r), assessment,
      plan: r.tree ? { ...clone(r.tree), planRevision: r.adapter.planRevision,
        approved: initialPlanApproved(r),
        nodes: r.tree.nodes.map(n => ({ ...n, status: derivedNodeStatus(statuses, n.id) })) } : null,
      question: p ? { toolCallId: p.toolCallId, tool: p.tool, ...toClientQuestion(r.adapter.questions[p.toolCallId]),
        questionType: r.adapter.questions[p.toolCallId].questionType, nodeId: p.input.nodeId,
        needsReveal: questionNeedsReveal(p.tool, p.input, phase(r)), open: r.adapter.questionOpen[p.toolCallId] } : null,
      continuationOwed: needsContinuation(r.messages), continuation: r.adapter.continuation,
      answers: r.messages.filter(m => m.role === 'toolResult' && QUESTION_TOOLS.includes(m.toolName)).map(m => ({ toolCallId: m.toolCallId, ...clone(m.details) })) };
  }
  context(chatId) { return clone(this.store.read(chatId).messages); }
}
