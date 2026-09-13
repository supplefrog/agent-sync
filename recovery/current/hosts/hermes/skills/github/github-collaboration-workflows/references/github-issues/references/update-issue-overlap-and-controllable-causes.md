# Update issue overlap and controllable-cause check

Use this reference when filing or editing multiple related product issues, especially update/progress/performance reports.

## Pattern

A user may describe several symptoms in one cluster (for example: "progress bar is wrong" + "updates feel slow"). Do not reflexively split every noun into a separate issue, and do not collapse distinct subsystems into one broad report.

## Required pass before finalizing

1. Identify the exact subsystem for each candidate issue:
   - Electron/Desktop app update path (`electron-updater`, release metadata, packaging artifacts, sidebar update UI).
   - Embedded/runtime engine update path (Settings -> Hermes Agent, installer/update subprocess, `install-progress`).
   - Generic installer/onboarding path (first install, reinstall, migration).
2. For each issue, state what code path owns it. If two reports share the same owner/code path and same expected fix, merge or cross-link rather than filing both.
3. For multiple related issues, add a short "Separate from ..." line in each body explaining the boundary.
4. Check whether the report only restates a UI symptom. If the user asked about slowness/performance, inspect controllable causes too:
   - release artifact size and metadata (`latest.yml`, `.blockmap`, `blockMapSize`, target type);
   - whether differential update is possible/used;
   - whether the app reruns full installers or dependency installs;
   - whether progress is determinate, indeterminate, or inferred from coarse log regexes;
   - whether logs/bytes/speed/ETA/phase data are dropped before the UI.
5. Correct existing issues in place when the user points out a scope or wording error. Avoid creating a new issue for a correction unless the current issue is unrecoverably misleading.

## Pitfalls

- Do not say "no progress UI" when a progress bar exists but is misleading/coarse.
- Do not report update slowness as only an observability/UI issue if source/release evidence can reveal controllable download or packaging costs.
- Do not leave sibling issues looking like duplicates. Titles should name the subsystem, e.g. "Hermes Agent runtime update..." vs "Electron Desktop app auto-update...".
