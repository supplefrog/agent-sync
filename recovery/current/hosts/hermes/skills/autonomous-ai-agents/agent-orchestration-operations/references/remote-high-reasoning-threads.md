# Remote high-reasoning task threads

Use when the user cannot change reasoning effort from their current client and explicitly asks to continue or respawn work in a higher-reasoning thread.

## Start a durable named thread

Write the full task packet to a file, then launch a named Hermes session:

```text
hermes chat --query-file <prompt-file> --reasoning high \
  --continue '<thread title>' --create-if-missing \
  --in <workspace> --pass-session-id -Q
```

Run it as a tracked background process with completion notification. Use a separate writable root or `--worktree` when another worker may edit the same repository.

## Resume the same thread

When the worker returns a session ID but stops before acceptance is complete, resume that exact session rather than creating another thread:

```text
hermes chat --query-file <completion-prompt> --reasoning high \
  --resume <session-id> --in <workspace> --pass-session-id -Q
```

The completion prompt must name the unfinished checks and say not to stop at status or a plan. A normal process exit is not task completion; compare the result with the original acceptance contract. Resume only when remaining work is mechanical and authorized. If a real user decision is required, stop before it and ask one short question.

## Prompt contract

Include the recovered source session/artifacts, bounded outcome, allowed writable root, prohibited live mutations, exact verification, cleanup, and failure behavior. Require simple, jargon-light user-facing output. Keep technical precision; define necessary terms briefly.

## Routing work

Do not call an adaptive router complete because selector unit tests pass. Completion requires:

- current eligible route evidence for the exact host/runtime/model/effort/tool stack;
- exact route receipts pinned to runs;
- native adapter coverage for every claimed surface;
- resume and cleanup checks;
- preservation of the incumbent when no route qualifies;
- independent review of nontrivial integration.

Separate a verified selector core from staged adapters and upstream host gaps in the report.