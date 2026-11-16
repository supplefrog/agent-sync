// SPDX-License-Identifier: AGPL-3.0-only
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import {loadConfiguration} from '../src/config.mjs';
import {executeLearningCommand} from '../src/commands.mjs';
import {FileSessionStore} from '../src/store.mjs';
import {T3LearningBoundary} from '../src/t3/boundary.mjs';
import {handleLearningTool, TOOLS} from '../src/t3/server.mjs';
import {validateLessonView} from '../src/inline/lesson-identity.mjs';

const code = '  const twice = n => n + n;\n';
const thinking = 'Adding the input to itself avoids rounding.';
const solution = 'function twice(n) { return n * 2; } // committed example';
const coding = {language: 'javascript', starterCode: 'function twice(n) {}', solution,
  tests: [{name: 'Doubles 4', expression: 'twice(4)', expected: 8}]};
const expectedObservations = [{name: 'Doubles 4', status: 'pass'}];

function fixture(t, kind) {
  const dir = fs.realpathSync(os.tmpdir());
  const base = fs.mkdtempSync(path.join(dir, 'lh-coding-mcp-'));
  t.after(() => {
    assert.equal(path.dirname(fs.realpathSync(base)), dir);
    fs.rmSync(base, {recursive: true, force: true});
  });
  const configFile = path.join(base, 'bindings.json');
  const chatId = 'synthetic-lesson';
  const owner = 'synthetic-owner';
  fs.writeFileSync(configFile, JSON.stringify({version: 1, lessons: [{
    ownerSessionId: owner, chatId, kind, stateRoot: 'state', exportRoot: 'exports',
  }]}));
  const binding = loadConfiguration(configFile).lessons[0];
  const run = command => executeLearningCommand(binding, {chatId, ...command});
  const tool = (result, name, toolCallId, input) => run({op: 'tool', expectedRevision: result.view.revision,
    name, toolCallId, input, authorship: 'synthetic-fixture'});
  const call = (name, args, threadId = owner) => handleLearningTool(new T3LearningBoundary(configFile), {
    params: {name, arguments: {chatId, ...args}, _meta: {threadId}},
  });
  const input = (result, action) => call('learning_input', {kind, expectedRevision: result.view.revision, action: {chatId, ...action}});
  return {chatId, run, tool, call, input, recordFile: new FileSessionStore(binding.root).file(chatId)};
}

for (const kind of ['teach','practice']) test(`explicit MCP test and authoritative ${kind} submission preserve exact code and reveal the settled solution`, async t => {
  const s = fixture(t, kind);
  let r = s.run({op: 'init', goal: 'Practice a function', title: 'Synthetic coding lesson'});
  if (kind === 'teach') {
    r = s.tool(r, 'probe_done', 'assessment', {assessment: {strands: [{strand: 'JavaScript', assessment: 'Fixture'}]}});
    r = s.tool(r, 'plan_init', 'plan', {mermaid: 'graph TD\n functions[Functions]'});
    s.input(r, {type: 'approve', planRevision: r.view.plan.planRevision, text: 'Continue.'});
    r = s.tool(s.run({op: 'view'}), 'explain', 'coding-exercise', {type: 'predict', nodeId: 'functions',
      question: 'Implement a function that doubles its input.', correctAnswer: solution, coding});
  } else {
    r = s.tool(r, 'problem', 'coding-exercise', {statement: 'Implement a function that doubles its input.',
      mode: 'composition', modelSolution: solution, coding});
  }
  assert.equal(JSON.stringify(r.view).includes(solution), false);
  assert.equal(JSON.stringify(r.view).includes('twice(4)'), false);
  assert.deepEqual((r.view.question ?? r.view.activeProblem).coding,
    {language: 'javascript', starterCode: coding.starterCode, testNames: ['Doubles 4']});
  const publicView=s.call('learning_view',{}).structuredContent.view;
  assert.deepEqual((publicView.question??publicView.activeProblem).coding,
    {language:'javascript',starterCode:coding.starterCode,testNames:['Doubles 4']});
  assert.equal(JSON.stringify(publicView).includes(solution),false);
  const invalid=structuredClone(publicView);
  (invalid.question??invalid.activeProblem).coding.solution=solution;
  assert.throws(()=>validateLessonView(invalid,{chatId:s.chatId,kind}),/private coding fields/);
  assert.deepEqual(TOOLS.find(tool => tool.name === 'learning_coding_test')._meta.ui.visibility, ['app']);
  const baseline = fs.readFileSync(s.recordFile);
  const request = {promptId: 'coding-exercise', expectedRevision: r.view.revision, code};
  await assert.rejects(s.call('learning_coding_test', request, 'foreign-owner'));
  await assert.rejects(s.call('learning_coding_test', {...request, promptId: 'stale-question'}), {code: 'stale_coding_question'});
  const {structuredContent: receipt} = await s.call('learning_coding_test', request);
  assert.deepEqual(receipt.observations, expectedObservations);
  assert.deepEqual(fs.readFileSync(s.recordFile), baseline);
  const submit = (source, runId) => kind === 'teach'
    ? {type: 'answer', toolCallId: 'coding-exercise', request: {text: source, thinking, codingRunId: runId}}
    : {type: 'practice-input', input: {type: 'thinking', problemCallId: 'coding-exercise', text: thinking, code: source, codingRunId: runId}};
  assert.throws(() => s.input(r, submit(code.trim(), receipt.runId)), {code: 'stale_coding_run'});
  assert.deepEqual(fs.readFileSync(s.recordFile), baseline);
  s.input(r, submit(code, receipt.runId));
  assert.throws(() => s.input(r, submit(code, receipt.runId)));
  const current = s.run({op: 'view'});
  const entry = kind === 'teach' ? current.view.answers.at(-1).coding : current.view.codingAttempts.at(-1);
  assert.equal(entry.code, code);
  assert.deepEqual(entry.observations, expectedObservations);
  const saved = JSON.parse(fs.readFileSync(s.recordFile, 'utf8')).messages.find(message => message.details?.coding?.code === code);
  assert.ok(saved);
  assert.ok(JSON.stringify(saved).includes(thinking));
  const context = s.run({op: 'context'}).context;
  const teacherMessage = context.messages.at(-1);
  const teacherText = Array.isArray(teacherMessage.content)
    ? teacherMessage.content.map(block => block.text ?? '').join('\n') : teacherMessage.content;
  assert.ok(teacherText.includes(thinking));
  assert.ok(teacherText.includes(JSON.stringify(code)));
  assert.ok(teacherText.includes(JSON.stringify(expectedObservations)));
  if (kind === 'practice') {
    assert.equal(JSON.stringify(current.view).includes(solution), false);
    s.tool(current, 'conclude', 'conclude', {outcome: 'solved', verdict: 'The code doubles the input.',
      rung: 'R2', missClass: null, retest: false});
    assert.equal(s.run({op: 'view'}).view.conclusion.modelSolution, solution);
  } else {
    assert.equal(entry.solution, solution);
  }
});
