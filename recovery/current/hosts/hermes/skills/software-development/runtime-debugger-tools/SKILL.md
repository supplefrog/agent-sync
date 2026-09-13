---
name: runtime-debugger-tools
description: Drive language runtime debuggers from Hermes for breakpoint, stack, scope, expression, attach, profiling, and test-debug workflows. Covers Python pdb/debugpy and Node.js inspect/CDP. Use when logs are insufficient or live runtime state must be inspected.
---
# Runtime debugger tools

Start with `systematic-debugging` to establish a reproducible failure and hypothesis. Use this skill when runtime state is needed to test that hypothesis.

## Routing
- Python pdb/debugpy/DAP: read `references/python-debugpy.md`.
- Node.js `node inspect`, V8 inspector, and CDP: read `references/node-inspect-debugger.md`.

## Shared workflow
1. Reproduce under a single-process test when possible.
2. Bind debugger listeners to loopback; never expose an unauthenticated debugger publicly.
3. Prefer break-on-start when execution could race past the target.
4. Confirm PID, source mapping, breakpoint location, and paused frame before interpreting values.
5. Capture the minimal state needed, then rerun the normal test suite without debugger instrumentation.
6. Stop debugger and target processes cleanly.