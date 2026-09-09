# Frontend Resource Catalog

This is a routing catalog, not an automatic install list. Recheck live terms, licenses, compatibility, and pricing when they matter.

| Resource | Best use | Boundary |
|---|---|---|
| [21st.dev](https://21st.dev/) | Searchable React and Tailwind components, screens, themes, and agent prompts | Copied source becomes project code. Inspect license, dependencies, accessibility, responsiveness, and token fit before importing. Do not make it a default dependency. |
| [Fancy Components](https://www.fancycomponents.dev/) | React microinteractions and expressive components inspired by award-winning sites | Usually adds source and Motion-related dependencies. Use targeted pieces, adapt styling, and provide reduced-motion behavior. |
| [Godly](https://godly.design/) | Curated website inspiration and composition references | Inspiration only. Extract principles and verify original sources; do not present gallery work as reusable code or clone it. |
| [Awwwards](https://www.awwwards.com/) | Broader visual and interaction references | Inspiration, not a quality or accessibility guarantee. Avoid borrowing spectacle that harms usability or performance. |
| Pinterest | Moodboards and visual discovery when the user supplies or authorizes account/browser use | Provenance and rights can be unclear. Use for directional references, not assets or implementation claims. |
| [Phosphor Icons](https://phosphoricons.com/) | A coherent icon family when the project has no established icon set | Prefer the project's current icon library. Check package and license before adding it; do not mix icon families casually. |
| [getDesign](https://getdesign.md/) | Reference-derived DESIGN.md files and design extraction | External network/service behavior and potentially copied site-derived analysis. Use only when requested or authorized; review output rather than treating it as truth. |
| [DESIGNmd](https://designmd.ai/) | Community DESIGN.md library and validation/export ecosystem | Community kits vary in quality and license. Review before use. Its MCP, API, and CLI are optional external capabilities, not prerequisites. |
| [Google DESIGN.md](https://github.com/google-labs-code/design.md) | Canonical portable design-system format and current linter/export behavior | The format is alpha and may change. Consult the live specification before strict validation or automation. |
| [TasteSkill](https://www.tasteskill.dev/) | Ideas about stronger visual briefs, typography, composition, and avoiding generic output | Do not install wholesale. Its large variants and prescriptive layouts, spacing, funnels, or GSAP-heavy recipes can override product needs. Borrow only task-relevant principles. |
| [Anthropic frontend-design](https://github.com/anthropics/skills/tree/main/skills/frontend-design) | Concise subject-grounded visual direction and deliberate aesthetic choices | Conceptual input only when this skill remains the frontend owner. Do not create a duplicate trigger. |
| [Vercel Web Interface Guidelines](https://github.com/vercel-labs/web-interface-guidelines) | Review checklist for interface quality | Review aid, not the design authority. Fetching live guidance is a network action. |
| [Emil Kowalski skills](https://github.com/emilkowalski/skills) | Motion purpose, interruption, and interaction-review guidance | Use the adapted `motion-design.md` reference for motion tasks. Do not install the overlapping suite or treat aesthetic prescriptions and hardware-acceleration claims as universal rules. |

## Selection rule

Start with the project's current system. Add a resource only when it supplies a missing capability or a clear reference for the desired outcome. Prefer one design lineage, one icon family, and the smallest dependency footprint that can express it.
