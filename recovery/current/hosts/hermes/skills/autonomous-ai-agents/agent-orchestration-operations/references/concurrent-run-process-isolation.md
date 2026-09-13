# Concurrent run process isolation

Use when an evaluation, benchmark, or agent workflow can spawn or clean up subprocesses while other agent work is active.

## Contract

A run may stop only processes it can prove it owns. Process cleanup must not terminate sibling agent threads, user processes, or unrelated work that happens to use the same executable.

## Procedure

1. At spawn, record an opaque run ID, PID, process-start token/time, parent identity, descendants, scratch root, and any child session IDs.
2. Before concurrent dispatch, inspect the evaluator's cleanup logic. If it kills by executable name, broad command fragment, source tag, or working directory alone, serialize the runs or use an in-process child that is outside that cleanup path.
3. Terminate only identities registered to the run and recheck PID plus process-start token immediately before signaling. Prefer graceful termination before force.
4. Treat a missing scheduler/process handle as insufficient proof of cleanup. Check the live process table and, when deletion is blocked, inspect open files or working directories for the exact scratch root.
5. Remove scratch data only after no owned process still references it. Preserve a concise interruption receipt when partial output affects later decisions; otherwise remove unusable partial artifacts.
6. Verify that owned processes, child sessions, scratch roots, and temporary cleanup scripts are gone. Keep user-created or adopted sessions.

## Failure boundary

If ownership cannot be proved, do not kill the process. Surface or serialize the conflict instead.
