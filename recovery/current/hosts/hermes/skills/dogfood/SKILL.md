---
name: dogfood
description: "Use when testing or dogfooding a web app through real user workflows. Explore behavior, capture reproducible evidence, triage UX/accessibility/console failures, and optionally use an adversarial persona."
version: 2.0.0
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [qa, testing, browser, web, dogfood, ux, accessibility]
    related_skills: [frontend-ui-engineering]
---

# Dogfood Web Applications

Exercise a web app as a user, find real failures or friction, preserve evidence, and produce a bounded report. This owns black-box web QA and the optional adversarial-persona mode.

## Inputs and scope

Use the supplied URL and requested workflow. If scope is broad, prioritize the primary user journey, destructive/error recovery, empty/loading states, keyboard access, responsive behavior, and high-value integrations. State what was not tested.

Use the local browser session when the task depends on the user’s existing login. Stop at login walls rather than guessing credentials. Do not purchase, publish, delete remote data, submit consequential forms, create accounts, or create public tickets without authorization for that action.

## Workflow

1. **Frame the test.** Identify target user, core job, environment, important state, and stopping boundary. Inspect project guidance and known constraints before changing anything.
2. **Establish a baseline.** Load the page, record the URL/state, inspect the accessibility structure and visible layout, and note console/network failures when relevant.
3. **Exercise real tasks.** Follow complete user workflows rather than touring features. Test valid and invalid inputs, recovery, navigation, refresh/persistence, keyboard operation, narrow and wide viewports, and realistic long/empty data where in scope.
4. **Capture evidence.** For each candidate issue record exact steps, expected behavior, actual behavior, URL/state, console or network evidence, and a screenshot when the defect is visual. Reproduce before promoting it as a finding.
5. **Triage.** Deduplicate manifestations, separate product defects from environment/setup failures, classify impact and category using `references/issue-taxonomy.md`, and keep hypotheses labeled.
6. **Report.** Use `templates/dogfood-report-template.md` when a file report helps. Include tested scope, untested scope, blockers, and evidence paths. Counts must match the enumerated findings.
7. **Publish only when asked.** If the user requests tickets, create only actionable verified findings, then read back each created target before claiming success.

## Browser and evidence tools

Use the available browser surface rather than hardcoded legacy tool names:

- `browser_exec` for navigation, DOM/accessibility inspection, interaction, screenshots, and local logged-in sessions.
- Chrome DevTools tools when detailed console, network, Lighthouse, performance, or element inspection is needed.
- `vision_analyze` for close visual inspection of saved screenshots.

For many findings, write each batch to JSON or CSV in the workspace, then deduplicate/count programmatically before producing the report.

## Optional adversarial-persona mode

When the user asks for a hostile, skeptical, novice, low-patience, or accessibility-focused review—or when ordinary happy-path QA would miss adoption friction—load `references/adversarial-persona-mode.md` and run it as a mode inside this workflow. Persona reactions are evidence-generation prompts, not findings; the neutral triage pass decides what is real.

## Boundaries

- `frontend-ui-engineering` owns implementing fixes and production UI design.
- This skill owns web-QA execution, evidence, and adversarial-persona triage.
- Do not manufacture complaints, impose arbitrary click-count thresholds, or require every issue to have a screenshot when the failure is nonvisual.
- A clean first pass is not proof of quality, but neither is it permission to invent defects.
