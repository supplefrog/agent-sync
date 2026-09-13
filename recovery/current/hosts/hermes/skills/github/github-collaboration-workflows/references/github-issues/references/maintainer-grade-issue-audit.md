# Maintainer-grade issue filing and audit workflow

Use this when filing or repairing GitHub issues based on a user's observed bug report, especially UI/runtime bugs where the first description is anecdotal.

## Failure mode this prevents

A fast issue-creation workflow can accidentally optimize for pleasing the requester rather than helping maintainers. Symptoms:

- Turning a short observation into a verbose generic issue without evidence.
- Adding process notes like “I searched existing issues” in the issue body.
- Treating a workflow correction as a memory/preference instead of improving the issue-filing procedure.
- Filing a narrow issue even when a broader existing issue should receive the new evidence as a comment.

## Required sequence

1. **Load this skill and repo context**
   - Confirm the exact repository.
   - Read repo-specific issue templates or contributing guidance when present.

2. **Duplicate and scope check**
   - Search open and closed issues.
   - Include broad umbrella symptoms, not just exact wording.
   - Decide among:
     - New focused issue.
     - Comment with evidence on an existing broader issue.
     - Close/avoid filing because the claim is unsupported or duplicate.

3. **Evidence extraction before writing**
   - UI bug: use browser/app screenshot, console logs, network logs, or DOM/runtime state when possible.
   - Runtime bug: use logs, status endpoints, process/config state, DB rows, or exact command output.
   - Code-path bug: inspect source and cite files/functions/line ranges or current commit.
   - If direct verification is not possible, keep the report narrow and label the source as reported/observed behavior, not proven root cause.

4. **Issue body structure**
   - Summary: one dense paragraph.
   - Environment/version/commit when known.
   - Steps to reproduce.
   - Expected vs actual.
   - Evidence: logs, screenshots, source snippets, status output.
   - Suspected area/hypothesis, explicitly separated from evidence.
   - Impact/workaround.
   - Related issues only when they help maintainers understand scope.

5. **Product-facing wording**
   - Do not write as if talking to the user.
   - Do not include self-referential agent process notes.
   - Do not apologize in the issue body.
   - Prefer concise, maintainer-useful details over broad “this is annoying” framing.

6. **After posting**
   - Verify issue state with `gh issue view`.
   - Verify labels actually applied; label creation/edit may fail due to permissions.
   - If a later audit shows the report is underspecified, either update it with evidence or close/comment honestly.
   - Before closing a duplicate you created, compare it against the kept issue and move any unique reproduction steps, logs, source-path evidence, screenshots, or implementation notes onto the kept issue. Verify the comment exists before closing the duplicate.
   - Remove or avoid cleanup/apology/routing-churn comments that add no product evidence for maintainers.

## Source-inspection patterns that worked

For a React/Electron UI issue, useful evidence often comes from tracing state paths:

- Find the component rendering the visible banner/panel.
- Find the hook or IPC listener updating its state.
- Identify dependencies of `useEffect` or subscription cleanup.
- Compare against the separate component that shows contradictory state.
- Cite exact files and the relevant state/update snippets.

For queue/timing issues, trace:

- Where user input is accepted.
- Whether it is added to transcript immediately or stored in a queue/ref.
- What condition drains the queue.
- Whether the UI exposes the queued data in a readable/copyable way.

For auto-scroll issues, inspect whether scroll is tied only to message-array changes or also to rendered height changes via `ResizeObserver`, mutation observer, requestAnimationFrame bottom-pin loop, or explicit streaming state.