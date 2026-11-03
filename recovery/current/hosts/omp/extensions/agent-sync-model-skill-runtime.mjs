// OMP request-local adapter. Restricted packages never enter global skill discovery.
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const NAME = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;
const BODY = /<!-- agent-sync-model-skill:([a-z0-9-]+) -->[\s\S]*?(?:<!-- \/agent-sync-model-skill -->|$)/g;
const CATALOG = /<!-- agent-sync-model-skill-catalog -->[\s\S]*?(?:<!-- \/agent-sync-model-skill-catalog -->|$)/g;
const cache = new Map();

function readJson(file) {
  const stat = fs.statSync(file);
  if (stat.size > 2_000_000) throw new Error("Oversized model policy");
  const old = cache.get(file);
  if (old?.mtime === stat.mtimeMs && old?.size === stat.size) return old.data;
  const data = JSON.parse(fs.readFileSync(file, "utf8"));
  if (cache.size > 8) cache.clear();
  cache.set(file, { mtime: stat.mtimeMs, size: stat.size, data });
  return data;
}

function sourceRoot() {
  const shared = process.env.AGENT_SYNC_SHARED_SKILLS || path.join(os.homedir(), ".agents", "skills");
  const state = readJson(path.join(shared, ".agent-signal-fleet.json"));
  const snapshot = state.source_snapshot;
  if (typeof snapshot !== "string" || !path.isAbsolute(snapshot) || path.basename(snapshot) !== "fleet" || path.basename(path.dirname(snapshot)) !== "render") throw new Error("Invalid managed source origin");
  return path.dirname(path.dirname(snapshot));
}

export function createRuntime(source) {
  const root = () => source || sourceRoot();
  function file(name, relative) {
    if (typeof name !== "string" || !NAME.test(name) || typeof relative !== "string" || relative.includes("\\") || path.isAbsolute(relative) || relative.split("/").some(p => ["", ".", ".."].includes(p))) throw new Error("Invalid skill address");
    const base = path.join(root(), "skills", name), target = path.join(base, relative);
    let current = target;
    while (current !== root()) {
      if (fs.lstatSync(current).isSymbolicLink()) throw new Error("Linked skill path");
      const parent = path.dirname(current);
      if (parent === current) throw new Error("Escaping skill path");
      current = parent;
    }
    const rel = path.relative(fs.realpathSync(base), fs.realpathSync(target));
    if (rel.startsWith("..") || path.isAbsolute(rel) || fs.statSync(target).size > 128_000) throw new Error("Invalid skill file");
    return target;
  }
  function available(host, provider, model) {
    try {
      const policy = readJson(path.join(root(), "contracts", "skill-model-policy.json"));
      const catalog = readJson(path.join(root(), "contracts", "model-weights.json"));
      const models = catalog.open_weight_models?.[provider];
      if (policy.schema_version !== 1 || catalog.schema_version !== 1 || typeof provider !== "string" || typeof model !== "string" || !provider || !model || !Array.isArray(models) || !models.every(x => typeof x === "string") || !models.includes(model)) return [];
      return Object.entries(policy.skills).flatMap(([name, rule]) => {
        if (!NAME.test(name) || !rule || rule.requires !== "open-weights" || !Array.isArray(rule.hosts) || !rule.hosts.includes(host)) return [];
        const text = fs.readFileSync(file(name, "SKILL.md"), "utf8");
        const description = text.match(/^description: ([^\r\n]+)/m)?.[1]?.trim();
        return description ? [{ name, description }] : [];
      });
    } catch { return []; }
  }
  function view(provider, model, name, relative = "SKILL.md") {
    if (!available("omp", provider, model).some(row => row.name === name)) return { success: false, error: "Skill not available for the current model." };
    try {
      const text = fs.readFileSync(file(name, relative), "utf8");
      return { success: true, name, _agent_sync_model_skill: name, content: `<!-- agent-sync-model-skill:${name} -->\n${text}\n<!-- /agent-sync-model-skill -->` };
    } catch { return { success: false, error: "Skill file unavailable." }; }
  }
  return { available, view };
}

export function scrub(value, allowed) {
  const hidden = Symbol(), unavailable = { success: false, error: "Skill unavailable for the current model." };
  function walk(item) {
    if (typeof item === "string") {
      if (item.includes('"_agent_sync_model_skill"')) {
        try { const parsed = walk(JSON.parse(item)); return JSON.stringify(parsed === hidden ? unavailable : parsed); } catch { /* plain text */ }
      }
      return item.replace(CATALOG, "").replace(BODY, (body, name) => allowed.has(name) ? body : "[Skill unavailable for the current model.]");
    }
    if (Array.isArray(item)) return item.map(walk).filter(v => v !== hidden);
    if (item && typeof item === "object") {
      if (Object.hasOwn(item, "_agent_sync_model_skill") && !allowed.has(item._agent_sync_model_skill)) return hidden;
      const result = Object.fromEntries(Object.entries(item).map(([k, v]) => [k, walk(v)]).filter(([, v]) => v !== hidden));
      if (Array.isArray(item.skills) && result.skills.length !== item.skills.length) {
        result.count = result.skills.length;
        result.categories = [...new Set(result.skills.map(row => row?.category).filter(Boolean))].sort();
      }
      return result;
    }
    return item;
  }
  const result = walk(value);
  return result === hidden ? unavailable : result;
}

export function settingsAllow(settings, name, match) {
  try {
    if (settings?.enabled !== true || process.argv.includes("--no-skills") || !Array.isArray(settings.disabledExtensions) || !Array.isArray(settings.includeSkills) || !Array.isArray(settings.ignoredSkills)) return false;
    if (settings.disabledExtensions.includes(`skill:${name}`)) return false;
    if (settings.ignoredSkills.some(pattern => match(pattern, name))) return false;
    return settings.includeSkills.length === 0 || settings.includeSkills.some(pattern => match(pattern, name));
  } catch { return false; }
}

function toolEnabled(payload) {
  const direct = [...(Array.isArray(payload?.tools) ? payload.tools : []), ...(Array.isArray(payload?.config?.tools) ? payload.config.tools : [])];
  return direct.some(tool => tool?.name === "model_skill_view" || tool?.function?.name === "model_skill_view" || Array.isArray(tool?.functionDeclarations) && tool.functionDeclarations.some(row => row?.name === "model_skill_view")) ||
    Array.isArray(payload?.toolConfig?.tools) && payload.toolConfig.tools.some(tool => tool?.toolSpec?.name === "model_skill_view");
}

export function rewrite(payload, model, runtime, settings, match) {
  const actual = typeof payload?.model === "string" ? payload.model : model?.id;
  const rows = toolEnabled(payload) ? runtime.available("omp", model?.provider, actual).filter(row => settingsAllow(settings, row.name, match)) : [];
  const result = scrub(payload, new Set(rows.map(row => row.name)));
  if (!rows.length || !result || typeof result !== "object") return result;
  const text = ["<!-- agent-sync-model-skill-catalog -->", "<model_skills>", ...rows.map(row => `${row.name}: ${row.description}`), "Read an applicable skill with model_skill_view; use file_path for its references.", "</model_skills>", "<!-- /agent-sync-model-skill-catalog -->"].join("\n");
  if (result.config && (Array.isArray(result.contents) || "systemInstruction" in result.config)) {
    const instruction = result.config.systemInstruction;
    if (typeof instruction === "string") result.config.systemInstruction += `\n\n${text}`;
    else if (instruction?.parts && Array.isArray(instruction.parts)) instruction.parts.push({ text });
    else if (instruction == null) result.config.systemInstruction = { parts: [{ text }] };
  }
  else if (typeof result.instructions === "string") result.instructions += `\n\n${text}`;
  else if (typeof result.system === "string") result.system += `\n\n${text}`;
  else if (Array.isArray(result.system)) result.system.push(result.toolConfig ? { text } : { type: "text", text });
  else if (Array.isArray(result.messages)) {
    const first = result.messages[0];
    if (["system", "developer"].includes(first?.role)) {
      if (typeof first.content === "string") first.content += `\n\n${text}`;
      else if (Array.isArray(first.content)) first.content.push({ type: "text", text });
    } else result.messages = [{ role: "system", content: text }, ...result.messages];
  }
  else if (Array.isArray(result.input)) result.instructions = text;
  return result;
}

export function install(pi, readSettings, match) {
  const runtime = createRuntime();
  pi.on("before_provider_request", (event, ctx) => rewrite(event.payload, ctx.model, runtime, readSettings(), match));
  pi.registerTool({
    name: "model_skill_view",
    loadMode: "essential",
    label: "Model-scoped skill",
    description: "Read a skill offered in model_skills for the current model. Use file_path for its references.",
    parameters: { type: "object", properties: { name: { type: "string" }, file_path: { type: "string" } }, required: ["name"], additionalProperties: false },
    async execute(_id, args, _signal, _update, ctx) {
      const result = settingsAllow(readSettings(), args.name, match) ? runtime.view(ctx.model?.provider, ctx.model?.id, args.name, args.file_path) : { success: false, error: "Skill unavailable under the active skill settings." };
      return { content: [{ type: "text", text: JSON.stringify(result) }], isError: !result.success };
    },
  });
}
