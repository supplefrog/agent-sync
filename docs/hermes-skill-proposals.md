# Hermes skill proposals

Hermes stages; Agent Sync reviews and promotes. The existing `skills.write_approval: true` setting gates both background and foreground `skill_manage` writes. Memory settings are independent. No daemon, second queue, or automatic inference is added: review runs when the agent performs reconciliation.

`tools/reconcile.py plan` lists opaque proposal IDs and content hashes from the selected Hermes home's existing `pending/skills` store. A normal sync leaves proposals staged and may finish unrelated checked work. Proposal bodies, summaries, and skill names are not copied into public reconciliation evidence.

## Review and resolve

Use the active Hermes Python environment and `HERMES_HOME`. If its checkout is elsewhere, pass `--runtime PATH`; use `--home PATH` only for the explicitly selected profile.

```text
python tools/hermes_skill_review.py list
python tools/hermes_skill_review.py show ID
python tools/hermes_skill_review.py approve ID --review-token TOKEN
python tools/hermes_skill_review.py reject ID --review-token TOKEN
```

`show` is private working context, not a publishable report. It returns the full pending payload, each operation's native diff, and a token binding the candidate to the currently reviewed packages. Read the owning skill and evidence; use `skill-creator` for proportional checks. Reject duplication, unsupported generalization, and needless restrictions; shortening or replacing existing guidance is equally valid. A generated proposal is not evidence of improvement.

- **Existing native owner:** after review/checks, `approve` delegates to Hermes's native approval function and preserves its mutation ledger/rollback behavior. Verify the resulting file and fresh load. It refuses a changed proposal/package since `show`.
- **Shared/external or new owner:** make the reviewed change in the canonical source and use its normal deployment path. The helper refuses direct approval for these; after verified promotion, discard the redundant proposal with `reject`.
- **Revise:** do not approve an obsolete payload. Apply the reviewed revision through the owning source and discard the original once verified.
- **Reject:** discard only the selected ID. There is no bulk approval.

This is operator governance, not a sandbox against an agent with unrestricted shell access. Native `/skills approve` remains a user override. The token detects changes between inspection and apply; native filesystem writes are not globally atomic against concurrent external editors. Do not edit the same package concurrently during promotion. Native records lack a stage-time base hash: review against current content, not an assumed historical diff.

## Verification and rollback

Run `python -m pytest tests/test_hermes_skill_review.py tests/test_reconcile.py`. Set `HERMES_TEST_RUNTIME` to an installed Hermes checkout to include real stage/show/approve/reject tests in disposable profile directories. These tests spend no inference and create no chat sessions.

To roll back this integration, restore the previous `skills.write_approval` value and revert the bridge/reconciliation changes. Existing pending records remain available to native `/skills pending`; do not delete them during rollback. Turning approval off re-enables direct skill writes.
