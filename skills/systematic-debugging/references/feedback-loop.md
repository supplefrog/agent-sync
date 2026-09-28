# Build a useful bug signal

Use this reference when a difficult or intermittent bug has no quick, trustworthy reproduction. A useful signal exercises the user's actual symptom and can distinguish the faulty path from a nearby working path. It need not be an automated test at first.

Choose the cheapest realistic loop: a failing test at the right seam, a CLI command with fixture input, a captured request or trace replay, a browser script, a differential run against a known-good version, or a timing measurement for a performance regression. For a manual-only path, record exact steps, state, time, and observed output so the next run is comparable. The old `diagnosing-bugs` skill included a Bash prompt template for manual steps; use a task-specific equivalent only when manual reproduction is truly needed.

Make the loop faster and more discriminating when it will save investigation time. Narrow inputs or state one factor at a time while the failure remains. For a flaky bug, increase the chance of observing it with repeated or stressed runs, then compare failure rates; one passing run does not establish a fix. If no reproduction is available, use logs, traces, a recorded artifact, or authorized temporary instrumentation to locate the boundary. State what remains unobserved rather than treating an untested explanation as root cause.

After a fix, rerun the original symptom path and a nearby valid case. Turn the loop into a regression test only when the test seam represents the real failure. Remove temporary instrumentation and keep the smallest useful reproducer with the issue or code when it will help future debugging.
