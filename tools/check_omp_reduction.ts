// On-demand upgrade check for an actual private provider-request capture; no inference or prompt dump.
import { readFileSync } from "node:fs";
import { contextSearchAfter, contextSearchBefore, descriptionReductions, nativeContextPolicyLines }
  from "../recovery/current/hosts/omp/extensions/reduced-tool-guidance.ts";

export function checkRequest(payload: any): { passed: boolean; failures: string[] } {
  const failures: string[] = [];
  const entries = Array.isArray(payload?.tools) ? payload.tools.map((t: any) => t?.function ?? t) : [];
  const descriptions = new Map(entries.map((t: any) => [t?.name, t?.description]));
  for (const [name, reductions] of Object.entries(descriptionReductions)) {
    const description = descriptions.get(name);
    if (typeof description !== "string") { failures.push(`missing description: ${name}`); continue; }
    for (const [before, after] of reductions) {
      if (description.includes(before)) failures.push(`stock mandate remains: ${name}`);
      if (after && !description.includes(after)) failures.push(`changed description contract needs review: ${name}`);
    }
  }
  let system = typeof payload?.instructions === "string" ? payload.instructions : "";
  if (!system) {
    const messages = payload?.input ?? payload?.messages ?? [];
    for (const msg of Array.isArray(messages) ? messages : []) {
      if (!["system", "developer"].includes(msg?.role)) continue;
      system += typeof msg.content === "string" ? msg.content :
        (Array.isArray(msg.content) ? msg.content.map((c: any) => c?.text ?? "").join("\n") : "");
    }
    if (!system && typeof payload?.system === "string") system = payload.system;
    if (!system && Array.isArray(payload?.system)) system = payload.system.map((b: any) => b?.text ?? "").join("\n");
  }
  const policy = nativeContextPolicyLines(system);
  if (policy.includes(contextSearchBefore)) failures.push("stock context-search prohibition remains");
  if (!policy.includes(contextSearchAfter)) failures.push("native footer reduction missing or changed; review compatibility");
  return { passed: failures.length === 0, failures };
}

if (import.meta.main) {
  const path = process.argv[2];
  if (!path) { console.error("Usage: bun (or Node 24) tools/check_omp_reduction.ts <private-request-capture.json>"); process.exit(2); }
  const report = checkRequest(JSON.parse(readFileSync(path, "utf8")));
  console.log(JSON.stringify(report));
  process.exit(report.passed ? 0 : 1);
}
