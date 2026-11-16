// SPDX-License-Identifier: AGPL-3.0-only
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { executeLearningCommand } from '../src/commands.mjs';
import { LessonKnowledge } from '../src/knowledge.mjs';
import { FileSessionStore } from '../src/store.mjs';

const charge = { id: 'charge', name: 'Conservation of charge',
  statement: 'The net electric charge of an isolated system remains constant.', aliases: [] };
const cayley = { id: 'cayley', name: 'Cayley theorem',
  statement: 'Cayley embeds a finite group into a permutation group.', aliases: [] };
const expected = ['n_z_charge', 'n_z_cayley'];
const authorship = 'synthetic-fixture';

function fixture(t) {
  const temporary = fs.realpathSync(os.tmpdir());
  const root = fs.mkdtempSync(path.join(temporary, 'lh-ranked-audit-'));
  t.after(() => {
    assert.equal(path.dirname(path.resolve(root)), temporary);
    fs.rmSync(root, { recursive: true, force: true });
  });
  const notes = path.join(root, 'notes.md');
  fs.writeFileSync(notes, 'PRIVATE_NOTES_RAW_ONLY');
  const binding = {
    ownerSessionId: 'graph-audit-fixture', chatId: 'audit-lesson', kind: 'teach',
    root: path.join(root, 'lesson'), output: path.join(root, 'exports'),
    knowledgeRoot: path.join(root, 'knowledge'),
    materials: [{ id: 'notes', label: 'Notes fixture', kind: 'notes', file: notes }],
  };
  const execute = command => executeLearningCommand(binding, { chatId: binding.chatId, ...command });
  const store = new FileSessionStore(binding.root);
  execute({ op: 'init', title: 'Graph audit fixture', goal: 'Exercise the real audit command' });
  store.change(binding.chatId, record => {
    record.messages.push(
      { id: 'a-teacher-passage', role: 'assistant', content: [{ type: 'text', text: 'PRIVATE_TEACHER_RAW_ONLY' }] },
      { id: 'learner', role: 'user', content: 'PRIVATE_LEARNER_ONLY' },
    );
    return { record };
  });
  const knowledge = new LessonKnowledge(binding.knowledgeRoot);
  const node = (id, name, statement) => ({
    id, name, statement, aliases: [], createdAt: '2026-01-01T00:00:00Z',
    provenance: [{ chatId: 'existing-source', messageId: 'PRIVATE_PRIOR_PASSAGE_ID' }],
  });
  knowledge.change(record => {
    record.nodes.push(...Array.from({ length: 20 }, (_, n) => node(
      'n_a' + String(n).padStart(2, '0'), 'Bread experiment ' + n, 'Sample ' + n + ' cools slowly.',
    )));
    record.nodes.push(...Array.from({ length: 6 }, (_, n) => node(
      'n_b' + n, 'Electric charge exercises', 'Electric charge example ' + n,
    )));
    record.nodes.push(node(expected[0], charge.name, charge.statement), node(expected[1], cayley.name, cayley.statement));
    return { record };
  });
  return { binding, execute, knowledge, revision: () => store.read(binding.chatId).adapter.revision };
}

function assertAudit(audit) {
  assert.ok(Array.isArray(audit.matches), 'the audit must rank candidates per finding');
  assert.equal(audit.chains, undefined);
  assert.deepEqual(audit.matches.map(m => [m.propositionId, m.candidateIds[0]]),
    [[charge.id, expected[0]], [cayley.id, expected[1]]]);
  assert.deepEqual(audit.candidates.find(n => n.id === expected[0]).statement, charge.statement);
  assert.equal(audit.matches[0].nextOffset, 5);
  assert.ok(!JSON.stringify(audit).match(/PRIVATE_|a-teacher-passage|existing-source/));
}

function prepareAudit(s, pathName, propositions, chains = []) {
  if (pathName === 'lesson') {
    const run = (action, extra) => s.execute({ op: 'knowledge', action, ...extra });
    const { batchId } = run('prepare', { expectedRevision: s.revision() });
    const findings = { propositions: propositions.map(p => ({ ...p, messageId: 'a-teacher-passage' })), chains };
    run('findings', { batchId, findings, authorship });
    return {
      audit: extra => run('audit', { batchId, ...extra }),
      merge: extra => run('merge', { batchId, authorship, ...extra }),
    };
  }
  s.execute({ op: 'material', action: 'attach', materialId: 'notes', expectedRevision: s.revision(), authorship });
  const run = (action, extra) => s.execute({ op: 'import', action, materialId: 'notes', importId: 'ranked', ...extra });
  const { part } = run('prepare');
  run('findings', { part, findings: { propositions, chains }, authorship });
  return {
    audit: extra => run('audit', extra),
    merge: extra => run('merge', { part, authorship, ...extra }),
  };
}

for (const pathName of ['lesson', 'notes']) {
  test(pathName + ' audit ranks the full graph per finding and preserves ownership, revisions and identity on merge', t => {
    const s = fixture(t);
    assert.equal(s.knowledge.query({ limit: 20 }).nodes.some(n => expected.includes(n.id)), false);
    const chains = [{ premises: [charge.id], conclusion: cayley.id }];
    const { audit, merge } = prepareAudit(s, pathName, [charge, cayley], chains);

    const first = audit();
    assertAudit(first);
    assert.throws(() => audit({ chatId: 'foreign-lesson' }), { code: 'wrong_host_session' });
    const requests = [{ id: charge.id, offset: first.matches[0].nextOffset }];
    const page = audit({ graphRevision: first.graphRevision, requests });
    assert.deepEqual(page.matches[0].candidateIds, ['n_b4', 'n_b5']);
    assert.equal(page.matches[0].nextOffset, null);
    assert.deepEqual(audit({ graphRevision: first.graphRevision, requests }), page);
    const hinted = audit({ graphRevision: first.graphRevision, requests: [{ id: charge.id, hints: ['bread experiment'] }] });
    assert.equal(hinted.matches[0].totalCandidates, 27);
    assert.ok(hinted.matches[0].candidateIds.includes(expected[0]));
    assert.throws(() => audit({ requests }), { code: 'stale_graph' });
    const snapshot = () => fs.readFileSync(s.knowledge.store.file('knowledge'));
    const beforeInvalid = snapshot();
    for (const invalid of [null, [], [{}], [{ id: 'foreign' }], [{ id: charge.id, offset: -1 }],
      [{ id: charge.id, hints: [''] }], [{ id: charge.id }, { id: charge.id }]]) {
      assert.throws(() => audit({ graphRevision: first.graphRevision, requests: invalid }), { code: 'invalid_audit_request' });
    }
    assert.deepEqual(snapshot(), beforeInvalid);
    s.knowledge.change(record => {
      record.nodes.push({ id: 'n_y_context', name: 'Geometry', statement: 'A circle has a center.',
        aliases: [], createdAt: '2026-01-01T00:00:00Z', provenance: [] });
      return { record };
    });
    const verdicts = { links: [charge, cayley].map((p, index) => ({ id: p.id, linkTo: expected[index] })) };
    const beforeStale = snapshot();
    assert.throws(() => audit({ graphRevision: first.graphRevision, requests }), { code: 'stale_graph' });
    assert.throws(() => merge({ graphRevision: first.graphRevision, verdicts }), { code: 'stale_graph' });
    assert.deepEqual(snapshot(), beforeStale);
    const current = audit();
    const result = merge({ graphRevision: current.graphRevision, verdicts });
    assert.equal(result.stats.nodes, 0);
    const graph = new LessonKnowledge(s.binding.knowledgeRoot).graph();
    assert.equal(graph.nodes.length, 29);
    for (const id of expected) assert.equal(graph.nodes.find(n => n.id === id).provenance.length, 2);
  });

  test(pathName + ' audit returns long ranked aliases in bounded pages without skipping a match', t => {
    const s = fixture(t);
    const finding = { id: 'large', name: 'Goldsignal', statement: 'Goldsignal', aliases: [] };
    const statement = '静'.repeat(15870) + ' "\\" ';
    const alias = 'Goldsignal ' + '測'.repeat(15870) + ' "\\" ';
    const nodeIds = Array.from({ length: 5 }, (_, index) => 'n_large' + index);
    s.knowledge.change(record => {
      for (const id of nodeIds) record.nodes.push({
        id, name: 'Detailed article', statement, aliases: [alias],
        createdAt: '2026-01-01T00:00:00Z', provenance: [],
      });
      return { record };
    });
    const { audit } = prepareAudit(s, pathName, [finding]);
    let page = audit();
    const first = page;
    assert.deepEqual(audit(), first, 'initial page is deterministic on the same revision');
    const seen = [];
    for (const count of [2, 2, 1]) {
      assert.ok(Buffer.byteLength(JSON.stringify(page)) <= 256 * 1024);
      const match = page.matches[0];
      assert.equal(match.totalCandidates, 5);
      assert.equal(match.offset, seen.length);
      assert.deepEqual(match.candidateIds, nodeIds.slice(seen.length, seen.length + count));
      assert.equal(page.candidates[0].statement, statement);
      assert.deepEqual(page.candidates[0].matchedAliases, [alias]);
      seen.push(...match.candidateIds);
      const nextOffset = seen.length < nodeIds.length ? seen.length : null;
      assert.equal(match.hasMore, nextOffset !== null);
      assert.equal(match.nextOffset, nextOffset);
      if (nextOffset !== null) page = audit({ graphRevision: first.graphRevision, requests: [{ id: finding.id, offset: nextOffset }] });
    }
    assert.deepEqual(seen, nodeIds);
  });

  test(pathName + ' audit ranks on finding aliases omitted from the returned evidence', t => {
    const s = fixture(t);
    const aliases = [...Array.from({ length: 5 }, (_, n) => '静'.repeat(15860) + n), 'Rarealiasneedle'];
    const finding = { id: 'alias-heavy', name: 'Filed claim', statement: 'Learner-visible statement', aliases };
    const nodeId = 'n_alias_lookup';
    s.knowledge.change(record => {
      record.nodes.push({
        id: nodeId, name: 'Evidence archive', statement: '測'.repeat(15860) + ' Rarealiasneedle', aliases: [],
        createdAt: '2026-01-01T00:00:00Z', provenance: [],
      });
      return { record };
    });
    const { audit } = prepareAudit(s, pathName, [finding]);
    const first = audit();
    assert.ok(Buffer.byteLength(JSON.stringify(first)) <= 256 * 1024);
    assert.equal(first.propositions[0].name, finding.name);
    assert.equal(first.propositions[0].statement, finding.statement);
    assert.ok(!first.propositions[0].aliases.includes(aliases.at(-1)));
    assert.equal(first.propositions[0].omittedAliasCount, aliases.length - first.propositions[0].aliases.length);
    assert.equal(first.matches[0].candidateIds[0], nodeId);
    assert.equal(first.candidates[0].preview, undefined);
  });

  test(pathName + ' audit keeps an oversized ranked identity and supports exact lookup at its revision', t => {
    const s = fixture(t);
    const finding = { id: 'large-evidence', name: 'Goldsignal', statement: 'Goldsignal', aliases: [] };
    const nodeId = 'n_exact_oversized';
    const name = 'Exact name ' + '\u0001'.repeat(15860);
    const statement = 'Exact statement ' + '\u0001'.repeat(15860);
    const alias = 'Goldsignal ' + '\u0001'.repeat(15860);
    s.knowledge.change(record => {
      const line = { id: nodeId, name, statement, aliases: [], createdAt: '2026-01-01T00:00:00Z', provenance: [] };
      record.nodes.push(line, { ...line, name: 'Later wording', statement: alias });
      return { record };
    });
    const { audit } = prepareAudit(s, pathName, [finding]);
    const first = audit();
    assert.ok(Buffer.byteLength(JSON.stringify(first)) <= 256 * 1024);
    assert.deepEqual(first.matches[0].candidateIds, [nodeId]);
    assert.equal(first.matches[0].nextOffset, null);
    assert.equal(first.candidates[0].preview, true);
    assert.equal(first.candidates[0].id, nodeId);
    assert.equal(first.candidates[0].statement, undefined);
    assert.ok(first.candidates[0].statementPreview.startsWith('Exact statement'));
    const lookup = options => s.execute({ op: 'knowledge', action: 'graph', nodeId,
      graphRevision: first.graphRevision, ...options }).graph;
    assert.equal(lookup().name, name);
    assert.equal(lookup().statement, statement);
    assert.equal(lookup({ aliasIndex: first.candidates[0].matchedAliasIndex }).alias, alias);
    assert.throws(() => lookup({ graphRevision: first.graphRevision + 1 }), { code: 'stale_graph' });
    assert.throws(() => lookup({ nodeId: nodeId.slice(0, -2) }), { code: 'graph_node_not_found' });
  });
}
