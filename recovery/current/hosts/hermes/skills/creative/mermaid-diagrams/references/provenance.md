# Provenance and boundaries

Reviewed 2026-08-25.

| Source | Contribution retained | Boundary |
|---|---|---|
| [Mermaid](https://github.com/mermaid-js/mermaid) and [Mermaid CLI](https://github.com/mermaid-js/mermaid-cli) | Canonical syntax/rendering ecosystem and official `mmdc` path | Rendering may require Node and a compatible Chromium/Puppeteer setup. |
| [Agents365-ai/mermaid-skill](https://github.com/Agents365-ai/mermaid-skill) | Validate before export; inspect rendered readability; distinguish setup failures from syntax failures | Its proactive 3+-component trigger, mandatory artifact production, remote Kroki fallback, and five-round review loop were intentionally not retained. |
| [softaworks/agent-toolkit mermaid-diagrams](https://github.com/softaworks/agent-toolkit/tree/main/skills/mermaid-diagrams) | Broad diagram-type selection and focused-diagram guidance | It does not provide a validation or rendered inspection loop; its “always diagram” guidance was not retained. |

The owning policy is inline-first: explanation requests receive Mermaid Markdown, while files and rendered media require an actual artifact need.
