# Research-before-install pattern for GitHub tools

Use when the user asks to install a GitHub project only if there is no better option, or asks for "best"/"creme de la creme" before installing.

## Evidence to collect

For the target repo and serious alternatives, capture comparable facts:

- GitHub metadata via API: description, stars, forks, open issues, pushed_at, archived, license.
- README claims and install path.
- Package metadata when relevant (`npm view`, PyPI, Docker image, releases).
- Maintenance signals: recent commits, issue/PR activity, changelog, release automation, governance/docs.
- Install friction: runtime stack, package manager, browser/PDF deps, Docker availability, AI provider/CLI dependency.
- Fit to the requested workflow: all-in-one breadth vs a narrower best-in-class slice.
- Red flags: archived repo, unusual hype/star velocity, open-core/plugin removal, unclear security posture, auto-apply/spam behavior, or stale docs.

## Decision framing

Rank by workflow fit, not stars alone:

- If no alternative clearly beats the target for the requested all-in-one workflow, install the target and name the narrower best-in-class alternatives separately.
- If a narrower tool is better only for one slice (resume tailoring, tracking, auto-apply), say that explicitly instead of treating it as a replacement.
- Distinguish local/open-source installable tools from hosted SaaS; include privacy and pricing tradeoffs when SaaS is considered.

## Low-risk install sequence

1. Check whether the target directory already exists before running an installer that creates a fixed folder.
2. If it exists and is the intended repo, update/fetch/status rather than overwriting.
3. Install project dependencies using the repo's documented local command.
4. Run the repo's doctor/check/update command when present.
5. Install optional project-scoped dependencies if explicitly part of the documented workflow (for example Playwright browser binaries for PDF generation).
6. Do not install broad system packages or language runtimes as a side effect unless the user explicitly approved that class of package-management change.
7. Verify with real command output: dependency audit/status, doctor result, package version, and git status.

## Reporting

Keep the final concise:

- State the verdict first.
- List the top alternatives and why they are or are not better.
- Give the exact install path and verification outputs.
- Call out remaining onboarding/configuration steps without pretending they are complete.