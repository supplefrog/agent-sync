import { lookup } from "@oh-my-pi/pi-coding-agent/config/registry";
import { install } from "./agent-sync-model-skill-runtime.mjs";

export default function modelSkills(pi) {
  const ids = { enabled: "skills.enabled", ignoredSkills: "skills.ignoredSkills", includeSkills: "skills.includeSkills", disabledExtensions: "disabledExtensions" };
  function readSettings() {
    try {
      const settings = Object.fromEntries(Object.entries(ids).map(([key, id]) => [key, lookup(id).get(pi.pi.settings)]));
      // The native CLI can supply this per-launch filter separately from settings.
      const args = process.argv.slice(2);
      const i = args.indexOf("--skills"), inline = args.find(arg => arg.startsWith("--skills="));
      const patterns = i >= 0 ? args[i + 1] : inline?.slice("--skills=".length);
      if (patterns !== undefined) settings.includeSkills = patterns.split(",");
      return settings;
    } catch { return { enabled: false }; }
  }
  return install(pi, readSettings, (pattern, name) => new Bun.Glob(pattern).match(name));
}
