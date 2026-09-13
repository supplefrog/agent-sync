# Orchestration ledger contract

Use a host-native task/goal store when it preserves these fields. Otherwise keep an equivalent local structured ledger. This is a data contract, not a mandated database.

## Minimum task record

```yaml
id: stable-task-id
title: concise observable outcome
goal_id: stable-goal-id | null
goal_relation: explicit | inferred | null
status: pending | active | blocked | completed | superseded | abandoned
priority: low | normal | high | urgent
sources:
  - host: hermes | codex | omp | external
    thread_id: string
    event_id: string | null
    timestamp: string | null
    locator: durable path, URL, or session link
requirements:
  - text: exact or safely normalized requirement
    source_index: 0
    confidence: explicit | inferred
depends_on: [task-id]
artifacts:
  - kind: file | commit | PR | issue | run | report | other
    locator: durable handle
    verified: true | false
verification:
  state: unverified | partial | verified | failed
  evidence: [locator]
next_action: one concrete action
user_decision: null | concise decision needed
worker_handles: []
updated_at: timestamp
```

## Goal record

A goal is a derived grouping, not a replacement for task evidence. Record:

- stable ID and concise outcome;
- explicit vs inferred status;
- member task IDs;
- supporting source pointers;
- contradictions or alternative interpretations;
- completion rule;
- current decision or next action.

Do not infer a grand project from thematic similarity alone. Require repeated intent, shared artifacts, dependency structure, or a user-confirmed link.

## Compression checkpoint

Before compression, retain:

1. active task and exact next action;
2. pending/blocked task IDs and dependencies;
3. unresolved user decisions;
4. source/event pointers for load-bearing requirements;
5. verified artifact handles;
6. running worker handles and cleanup obligations;
7. contradictions and superseded decisions;
8. the cursor/hash for each scanned source store.

Do not preserve full child transcripts unless they are the only available evidence. Prefer original source locators and final artifacts.

## Recovery after compression

1. Load the durable ledger, not the prose handoff alone.
2. Compare the handoff with current task records.
3. Re-open original source events for consequential or ambiguous requirements.
4. Verify running process/thread handles and live artifact state.
5. Mark stale claims instead of silently carrying them forward.
6. Resume exactly one active task; leave the rest queued.

## Cleanup receipt

For an agent-created temporary thread, record:

- thread/worker handle;
- useful artifact or distilled finding retained;
- tasks that referenced it;
- closure/delete operation and observed result;
- reason if intentionally retained.

A missing delete primitive is not permission to forget the worker. Close or release it when supported and retain the cleanup obligation until verified.
