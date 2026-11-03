import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { createRuntime, rewrite as rewriteCore, settingsAllow, scrub } from "../integrations/model-skills/agent-sync-model-skill-runtime.mjs";

const root = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const open = { provider: "openrouter", id: "openai/gpt-oss-120b" };
const closed = { provider: "openrouter", id: "anthropic/claude-sonnet-4" };
const tools = [{ type: "function", function: { name: "model_skill_view" } }];
const settings = { enabled: true, ignoredSkills: [], includeSkills: [], disabledExtensions: [] };
const match = (pattern, name) => pattern === name || pattern === "*" || pattern === "lea*" && name.startsWith("lea");
const rewrite = (payload, model, runtime, selected = settings) => rewriteCore(payload, model, runtime, selected, match);

test("same runtime switches closed/open/closed and withholds marked history", () => {
  const runtime = createRuntime(root);
  const loaded = runtime.view(open.provider, open.id, "leanrea");
  assert.equal(loaded.success, true);
  const saved = { tools, messages: [{ role: "tool", content: loaded.content }, { role: "user", content: "ordinary content" }] };
  const before = JSON.stringify(saved);
  for (const model of [closed, open, closed]) {
    const result = rewrite(saved, model, runtime);
    assert.equal(JSON.stringify(result).includes("leanrea:"), model === open);
    assert.equal(JSON.stringify(result).includes("# leanrea: fast path"), model === open);
    assert.match(JSON.stringify(result), /ordinary content/);
  }
  assert.equal(JSON.stringify(saved), before);
});

test("managed view metadata is withheld without rewriting user text", () => {
  const runtime = createRuntime(root), view = runtime.view(open.provider, open.id, "leanrea");
  const request = { tools, messages: [{ role: "tool", content: JSON.stringify(view) }, { role: "user", content: "I mentioned leanrea." }] };
  const result = rewrite(request, closed, runtime);
  assert.equal(result.messages[0].content.includes('"name":"leanrea"'), false);
  assert.equal(result.messages[1].content, "I mentioned leanrea.");
  const ordinary = JSON.stringify({ model_scope: "open-weights", name: "ordinary user data" });
  assert.equal(scrub(ordinary, new Set()), ordinary);
});

test("native Google and Bedrock payloads receive valid catalog blocks", () => {
  const runtime = createRuntime(root);
  const google = { provider: "google", id: "gemma-4-31b-it" };
  const bedrock = { provider: "amazon-bedrock", id: "openai.gpt-oss-120b-1:0" };
  assert.equal(runtime.available("omp", google.provider, google.id).length, 1);
  assert.equal(runtime.available("omp", bedrock.provider, bedrock.id).length, 1);
  const g = rewrite({ model: google.id, contents: [], config: { tools: [{ functionDeclarations: [{ name: "model_skill_view" }] }], systemInstruction: { parts: [{ text: "original" }] } } }, google, runtime);
  assert.equal(g.config.systemInstruction.parts[0].text, "original");
  assert.match(g.config.systemInstruction.parts[1].text, /leanrea:/);
  const b = rewrite({ messages: [], system: [{ text: "original" }], toolConfig: { tools: [{ toolSpec: { name: "model_skill_view" } }] } }, bedrock, runtime);
  assert.deepEqual(Object.keys(b.system[1]), ["text"]);
  assert.match(b.system[1].text, /leanrea:/);
});

test("native master, include, ignored and disabled controls apply on every call", () => {
  const runtime = createRuntime(root), payload = { tools, messages: [] };
  for (const disabled of [{ ...settings, enabled: false }, { ...settings, ignoredSkills: ["lea*"] }, { ...settings, includeSkills: ["ordinary"] }, { ...settings, disabledExtensions: ["skill:leanrea"] }, undefined]) {
    assert.equal(settingsAllow(disabled, "leanrea", match), false);
    assert.equal(JSON.stringify(rewriteCore(payload, open, runtime, disabled, match)).includes("leanrea:"), false);
  }
  assert.equal(settingsAllow({ ...settings, includeSkills: ["lea*"] }, "leanrea", match), true);
});

test("exact provider/model metadata, unknown models and Codex fail closed", () => {
  const runtime = createRuntime(root);
  for (const model of [closed, { provider: "unknown", id: open.id }, { provider: open.provider, id: open.id + "-lookalike" }, {}]) {
    assert.deepEqual(runtime.available("omp", model.provider, model.id), []);
    assert.equal(runtime.view(model.provider, model.id, "leanrea").success, false);
  }
  assert.deepEqual(runtime.available("codex", open.provider, open.id), []);
});

test("references are readable only inside the selected package", () => {
  const runtime = createRuntime(root);
  assert.equal(runtime.view(open.provider, open.id, "leanrea", "references/windows.md").success, true);
  for (const relative of ["../SKILL.md", "/etc/passwd", "C:\\secret", "references//windows.md"]) assert.equal(runtime.view(open.provider, open.id, "leanrea", relative).success, false);
});

test("malformed and missing policy, stale host model and separate contexts", () => {
  const temp = fs.mkdtempSync(path.join(os.tmpdir(), "model-skill-test-"));
  try {
    const runtime = createRuntime(temp);
    assert.deepEqual(runtime.available("omp", open.provider, open.id), []);
    fs.mkdirSync(path.join(temp, "contracts"));
    fs.writeFileSync(path.join(temp, "contracts/skill-model-policy.json"), "{broken");
    assert.deepEqual(runtime.available("omp", open.provider, open.id), []);
  } finally { fs.rmSync(temp, { recursive: true }); }
  const runtime = createRuntime(root);
  assert.equal(JSON.stringify(rewrite({ model: closed.id, messages: [] }, open, runtime)).includes("leanrea:"), false);
  assert.equal(runtime.available("omp", open.provider, open.id).length, 1);
  assert.equal(runtime.available("omp", closed.provider, closed.id).length, 0);
  assert.equal(runtime.available("omp", open.provider, open.id).length, 1);
});
