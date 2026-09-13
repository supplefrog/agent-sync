# Intact-System Agent Evaluation Reference

Use this reference for a repository-wide evaluation of a durable conversational OS or agent harness. It is a method and checklist, not a claim that any particular product supports the listed features.

## Evidence labels

- **Source-verified:** implementation, wiring, and ownership were traced in the intact repository.
- **Test-verified:** a real local test/build command passed.
- **Runtime-verified:** the real path exercised with its actual process boundary, sandbox, provider, and credentials.
- **Unproven:** the source or docs describe it, but prerequisites or runtime execution were unavailable.
- **Blocked:** a prerequisite or explicit source limitation prevented the check. Do not convert this into a permanent tool refusal.

Record commands and their actual result separately from conclusions. Preserve exact counts, exit codes, paths, and relevant error text.

## Intact conversational-OS trace

Trace one durable identity through this sequence:

```text
ingress/adapters/CLI
  -> agent + conversation + session + turn
  -> append-only event log
  -> executor/harness selection
  -> model/runtime protocol
  -> tool calls and sandbox processes
  -> stream/UI consumption
  -> wakeups, artifacts, scheduler, adapters
  -> fork/rewind/restart/self-modification
```

For every boundary, answer:

1. What durable record owns the state?
2. What process owns the live operation?
3. What event or cursor proves it happened?
4. What survives restart, executor replacement, sandbox rewind, fork, and deletion?
5. What is source-only versus tested versus runtime-proven?

## Durable identity and executor swap

Inspect agent, conversation, session, turn, event, model-binding, sandbox, secret, adapter, and scheduler records. Determine whether executor configuration is agent-scoped or conversation-scoped. A system can support history replay across executors without supporting concurrent per-conversation routing.

For each executor, verify:

- executable or SDK and sandbox image/command;
- model/provider binding and secret resolution;
- prompt/history projection from canonical events;
- native thread/session resume and persisted identifiers;
- tool request/result mapping and namespace preservation;
- server-request and approval behavior;
- streaming and durable stream/custom events;
- crash cleanup and warm-process reuse;
- fork/replay behavior;
- CLI/config preset and negative tests.

For an unlisted third-party runtime, the honest conclusion is “custom adapter required.” The minimum adapter should map the runtime into the system's canonical events rather than making the runtime's private history authoritative.

## Security and recovery probes

Inspect where secrets are stored, encrypted, resolved, and injected. Check whether the mutable agent can read raw key material, whether sandbox mounts expose host data, whether local-process mode is actually isolated, and whether external effects require explicit tool calls. Inspect automatic approval handlers rather than trusting an `on-request` label.

For rollback, distinguish:

- conversation/event rewind;
- sandbox filesystem snapshot/restore;
- process/memory checkpointing;
- git/source rollback;
- service restart/drain;
- agent clone/migration.

A filesystem snapshot is not a process checkpoint. A conversation fork is not a sandbox clone. An append-only log is not proof that every host lifecycle event is recorded.

## Transport and UI checks

Check both local and remote transports. A local `watch_events` implementation does not prove an HTTP or multi-client event stream. Inspect whether the browser UI consumes durable event cursors or only a relay/session stream. Verify that tool calls, errors, wakeups, approvals, and recovery markers are visible, not just final assistant text.

## Smallest honest pilot

Use this order:

1. One durable agent and one conversation.
2. One isolated sandbox and a low-risk file/test task.
3. Inspect canonical messages, tool requests/results, sandbox lifecycle, and turn completion events.
4. Fork or replay from a known event.
5. Swap the same identity to a deterministic custom executor and verify prior history remains usable.
6. Add snapshot/rewind, then adapters/scheduler wakeups.
7. Only after those seams pass, evaluate cloning, migration, or multi-executor routing.

If the host lacks a required compiler, sandbox daemon, runtime binary, or credential, record the blocked command and continue with source inspection and credential-free tests. Do not treat an environment prerequisite as a product capability or as a permanent prohibition.

## Common contradiction pattern

High-level pages often advertise “clone,” “migrate,” “computer use,” or “state management” while engineering status documents qualify these as roadmap or partial primitives. Resolve this by preferring executable code, focused tests, and the most specific status/known-limits section. Report both the advertised goal and the implemented boundary when they differ.
