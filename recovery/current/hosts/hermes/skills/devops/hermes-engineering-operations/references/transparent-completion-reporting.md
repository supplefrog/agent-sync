# Transparent Completion Reporting

## Validation fixture (not an instruction owner)

The active Hermes owner is the standing communication/defaults section in `SOUL.md`; Codex/OMP use their surviving global `AGENTS.md` adapter, with a measured OMP `RULES.md` hard-rule adapter. This reference preserves the behavior contract and regression cases for style tuning, not another prompt layer. CLI probes must account for Hermes' later platform hint that asks for non-Markdown output; Desktop is the final seam for clickable-link behavior.

For this user, transparency comes from inspectable artifacts, not long narration:

1. Start with one plain-language conclusion line.
2. If artifacts changed, add a short `Changed:` list.
3. Each item says what changed and links the relevant file with Markdown. For local files shown in Hermes Desktop, prefer `[name](file:///absolute/path)`; when many files changed, link one diff or index instead.
4. Omit `Changed:` when no artifact changed.
5. Add explanation only when it changes understanding, a decision, or the next action.
6. If a concept genuinely needs teaching and a teach skill is available, use it. Do not turn routine completion reports into lessons.
7. Do not restate the user's point; the links are the transparency layer.

## Owning-surface rule

Replace overlapping style instructions rather than stacking another overlay. Provider verbosity controls answer length but does not define output order. Rigid word caps and blanket bans on headings or lists conflict with inspectable completion reports.

Keep broad communication behavior in one host-owned surface, then use the smallest native adapter for other agents. A user preference may also be recorded as a fact, but memory is not the procedure owner.

## Tested contract

```text
Start with one plain-language conclusion line. If artifacts changed, add a `Changed:` list; each item says what changed and uses a Markdown file link (`[name](file:///absolute/path)`), or links one diff/index when many. Add detail only when it changes understanding, a decision, or the next action. If a concept needs teaching, use the teach skill when available. Do not restate the user's point.
```

## Regression probes

Use fresh, equivalent sessions and clean up temporary probes afterward:

- **Completed work with two files:** must produce one conclusion plus linked changes.
- **Simple concept:** should usually stop after the plain-language answer; no empty `Changed:` section.
- **Deep debugging or audit:** may expand after the conclusion without becoming shallow.
- **Many changed files:** link a diff/index rather than dumping a long path list.
- **User correction or decision:** apply it without restating or refining it.
- **Concept needing instruction:** invoke the teach skill only when available and useful.

Grade usefulness and inspectability, not exact phrasing. A candidate fails if it is concise but omits evidence links, or transparent but recreates a long report around them.
