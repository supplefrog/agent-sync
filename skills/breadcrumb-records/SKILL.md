---
name: breadcrumb-records
description: Use when recording or resuming substantial work. Preserve decision reasons, evidence, current status and safe handoff in a project-local breadcrumb.
version: 1.0.0
license: UNLICENSED
compatibility: Python 3.11+; local evidence files; one writer per record.
---

# Breadcrumb Records

Use for an explicit breadcrumb request, a substantial handoff, or a decision/change whose evidence and reasoning need to survive the session. On resume, consult the existing record before repeating the investigation. Skip trivial replies, isolated corrections and work already covered by an equivalent project record; extend that owner rather than create a duplicate.

## Capture and reuse

1. Keep one compact record per logical change in the project's existing work/docs area. Link it from the existing project index or handoff; do not create a global log. Keep private records outside the shared skill repository.
2. Record the requested outcome and original intent/approval locator when available. Separate observations, hypotheses and decisions. Preserve the chosen approach, material alternatives and rejection reasons in `change.text`; name what evidence would reopen the decision in `checks.limits`. Do not fabricate missing provenance or treat a previous model's conclusion as independent evidence.
3. Link exact diffs/artifacts, actual check output and limitations. Name one authoritative deployment/status receipt, its observation time or explicit unknown time, and session/reload implications. Clearly distinguish historical receipt state from current live state; supersede only the named outdated statement, not the entire source.
4. State the next safe action and rollback path or missing prerequisites. A record does not grant permission to deploy, publish, delete or undo work. If evidence is incomplete, stop the consequential action and identify only the missing lookup/check; do not restart a broad audit.
5. Validate the record and report material gaps. On reuse, inspect the linked evidence needed for the decision; recheck current state only where staleness changes that decision.

## Optional deterministic helper

If an equivalent record already exists, use it directly. Otherwise use [the CLI](scripts/breadcrumb.py) and [format/usage](references/usage.md). Resolve the script from this loaded skill directory, not the project working directory. Use the host's available Python 3.11+ interpreter (`python` or `python3`).

```text
python <skill-dir>/scripts/breadcrumb.py init <project>/change.json
python <skill-dir>/scripts/breadcrumb.py update <project>/change.json --from <temporary-input.json>
python <skill-dir>/scripts/breadcrumb.py check <project>/change.json
python <skill-dir>/scripts/breadcrumb.py render <project>/change.json
```

Complete a copy of the scaffold as INPUT; keep its ID and resolve evidence paths relative to RECORD. Later updates also use a copy, preserving prior revisions. One designated writer owns updates; other agents contribute evidence to it. The JSON is authoritative; Markdown is a generated view. For research or non-deployment work, explicitly state that deployment/rollback is not applicable and use `planned`/`in_progress` for unfinished work; do not label it deployed. This first schema has no generic completed-research status.

The helper checks shape and local file existence, not evidence truth, freshness, authorization or hashes. It does not fetch URLs: use an already-authorized local source extract plus its original URL in the prose, or an existing research record. It has no watcher, automatic capture, networking or agent hooks. Direct edits bypass history preservation. Do not store credentials, raw private transcripts or hidden prompts.

When changing the helper, run [its CLI regression suite](scripts/test_breadcrumb.py): `python -m unittest discover -s <skill-dir>/scripts -p test_breadcrumb.py`. Preserve draft completion, rejected-update nonmutation, scoped history, clean malformed-input errors and broken historical-link warnings. [Provenance and deployment boundary](references/provenance.md).
