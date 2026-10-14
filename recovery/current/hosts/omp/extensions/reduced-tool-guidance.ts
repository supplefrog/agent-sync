// Native OMP extension: change request descriptions, never tool implementations or schemas.
const replacements: Record<string, [string, string][]> = {
  task: [
    ["Use most specific agent. Read-only research MUST use `scout` only when files unknown. Prefer one agent to investigate + edit. Omit `agent` only for default (`task`); NEVER specify it.", "Choose an agent suited to the task. Omit `agent` to use the default (`task`)."],
    ["Shared edits need one integration owner; siblings coordinate via `write agent://<id>`. Set interfaces in `context`. Every task MUST skip build/lint/tests/formatters mid-flight; run once afterward.", "Shared edits need one integration owner. Supply interfaces and verification duties in `context`; isolate concurrent writers."],
    ["MUST be used for exploratory codebase research, rapid code analysis, and broad pattern searches. ", ""],
    ["`context`: shared (`# Goal`, `# Contract` interfaces); NEVER repeat per task.", "`context`: shared requirements and interfaces."],
    ["`task`: self-contained (`# Target` files/non-goals, `# Change` steps/APIs, `# Acceptance` observable result).", "`task`: self-contained scope, outcome and acceptance criteria."],
  ],
  todo: [
    ["Before work, init for 3+ steps, requested task sets, or new instructions. MUST list EVERY user item separately (phased/numbered/bulleted/N); NEVER omit or remember leftovers.", "Use when explicit task tracking is requested or helps retain the work's state."],
    ["NEVER call todo alone: init with first work; done/start with next action.", ""],
  ],
  bash: [
    ["Persistent shell: one fact command/pipeline; dependencies use `&&`.\nScripts/heredocs/`$(…)`/complex pipelines → `eval`.", "Persistent shell. Use shell or eval according to the operation; sequence dependent commands."],
    ["No `head`/`tail`/redirection; output trunc by default, full result at `artifact://<id>`.", "Output truncates by default; the full result is available at `artifact://<id>`."],
  ],
};

export function reduceDescription(name: string, description: string): string {
  for (const [before, after] of replacements[name] ?? []) description = description.replaceAll(before, after);
  return description;
}

export function reducePayload(payload: any): any {
  if (!payload || !Array.isArray(payload.tools)) return payload;
  let changed = false;
  const tools = payload.tools.map((tool: any) => {
    const entry = tool?.function ?? tool;
    if (typeof entry?.name !== "string" || typeof entry.description !== "string") return tool;
    const description = reduceDescription(entry.name, entry.description);
    if (description === entry.description) return tool;
    changed = true;
    return tool.function ? { ...tool, function: { ...entry, description } } : { ...tool, description };
  });
  return changed ? { ...payload, tools } : payload;
}

export default function (pi: any) {
  pi.on("before_provider_request", (event: any) => reducePayload(event.payload));
}
