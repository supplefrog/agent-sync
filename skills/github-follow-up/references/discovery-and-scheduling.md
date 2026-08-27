# Discovery and scheduling

Load this reference for a portfolio sweep or when installing the optional scheduled gate.

## Live discovery without the gate

Identify the viewer and recently active authored work:

```bash
gh auth status
viewer=$(gh api user --jq .login)

gh search issues \
  --author "$viewer" --state open \
  --sort updated --order desc --limit 200 \
  --json number,title,url,repository,updatedAt,state,commentsCount

gh search prs \
  --author "$viewer" --state open \
  --sort updated --order desc --limit 200 \
  --json number,title,url,repository,updatedAt,state,commentsCount,isDraft
```

Search results are an inventory, not evidence that action is needed. For each changed issue, use `gh issue view -R OWNER/REPO N --json ...`. For each own PR, use `gh pr view`, `gh pr checks`, and GraphQL review threads as described by `github-pr-workflow/references/review-feedback-remediation.md`.

Notifications are supplementary:

```bash
gh api notifications -f all=true -f participating=true -f per_page=100 --method GET
```

Do not use read/unread notification state as the only checkpoint. A user or another client can mark notifications read without resolving the thread.

## What the gate fingerprints

`scripts/github-follow-up-gate.py` uses only Python's standard library and `gh`. It tracks:

- open authored issues updated within the lookback window;
- all open authored PRs;
- authored PRs updated within the lookback window, including merged, closed-unmerged, reopened, and force-pushed outcomes;
- latest external issue/PR activity;
- formal PR reviews;
- review-thread resolution state;
- PR head SHA, mergeability, and check states.

It hashes bodies instead of injecting public comment text into the cron prompt. Terminal PR records stay compact: outcome, head/base, merge commit identity, and closing-issue references wake the agent; the agent must fetch live bodies, timelines, diffs, reviews, checks, merge commits, and current base before acting or retaining a lesson.

The gate writes:

- `cache/github-follow-up/state.json` — last successfully acknowledged snapshot;
- `cache/github-follow-up/pending.json` — snapshot awaiting successful handling.

Both paths are under the active Hermes home. If an agent run fails or only partially completes, do not run the acknowledgement command; the same delta wakes the next tick.

## Install the gate

Copy the skill's supporting script to the active Hermes home's `scripts/` directory as:

```text
github-follow-up-gate.py
```

Use `hermes config path` to find the active home. Do not assume `~/.hermes` on Windows or with profiles. The scheduled script must live under that home's `scripts/` directory because cron rejects arbitrary script paths.

Test without changing state:

```bash
python <HERMES_HOME>/scripts/github-follow-up-gate.py \
  --dry-run --state <TEMP_DIR>/github-follow-up-state.json --pretty
```

Expected final JSON contains either `"wakeAgent": false` or a `context.changed` list plus `context.ackCommand`.

## Create the job

A practical default is every four hours. Keep the prompt self-contained and attach this skill rather than copying its body into the prompt:

```bash
hermes cron create "every 4h" \
  "Process every item in the injected github-follow-up delta. Re-read live GitHub state, make only actions allowed by the github-follow-up skill, verify all writes and tests, then run context.ackCommand only if the whole batch completed. Return the skill's short Done/Workflow/Waiting report; return [SILENT] if nothing required action." \
  --name "GitHub follow-up" \
  --skill github-follow-up \
  --script github-follow-up-gate.py \
  --deliver local
```

Change `--deliver local` to a configured platform/home target if the report should be pushed to a chat. Delivery is handled by cron from the final response; the agent should not call messaging tools itself.

At creation, Hermes snapshots the current default provider/model for an unpinned job. If the global default later changes, the job fails closed and alerts instead of silently spending on the new route; explicitly review and repin the job when changing the global model.

Cron uses the toolsets enabled for the **cron** platform. This workflow needs terminal, file, and skills access. Add delegation only if independent repo work justifies it. Avoid carrying browser or unrelated toolsets by default.

## Scheduler prerequisite

The gateway daemon executes cron ticks. Check:

```bash
hermes cron status
hermes gateway status
```

On Windows, `hermes gateway install` creates an auto-start Scheduled Task. Installing or starting that service is a separate system-level decision; do not do it merely because the skill exists.

After setup:

```bash
hermes cron run "GitHub follow-up"
hermes cron runs "GitHub follow-up" --limit 10
hermes cron list
```

Read the first execution output and verify the gate state before relying on unattended runs.

## Scope and cost controls

- Default lookback is 45 days. The gate combines all open authored PRs with authored PRs updated in that window, so terminal outcomes persist long enough to be handled.
- The inventory limit applies independently to open issues, open PRs, and recently updated PRs. A source at the limit is named in `truncatedSources` and keeps waking the agent; paginate/narrow that live source or raise the gate limit rather than silently ignoring overflow.
- Unchanged ticks emit `wakeAgent:false`, so no model call occurs.
- The first run wakes once for every item in scope so existing label/body/state changes and silent review activity are not accidentally baselined. Later runs include only changed items.
- A self-authored GitHub update can produce one extra tick because acknowledgement captures the pre-action state. This is deliberate: avoiding a rare redundant read is not worth consuming a concurrent maintainer update.
