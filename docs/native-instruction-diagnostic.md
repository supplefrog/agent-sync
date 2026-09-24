# Native instruction diagnostic — implementation checkpoint

## Status

**Blocked before inference; not a behavioral or causal result.** The current implementation is an assembly-only preflight with no `run` command. It does not yet provide a faithful full-stack comparison, complete outbound-request tracing, or controlled causal trials.

The installed runtime was actually exercised. The latest initial checkpoint, [episode a040c7ecf42a4a9f915238f931663222](../evals/results/native-instruction-preflight/a040c7ecf42a4a9f915238f931663222.json), stopped during native imports before prompt assembly: Python's Windows platform discovery called `platform.win32_ver -> _syscmd_ver`, which attempted a subprocess under the probe's deny-subprocess boundary. This is a **harness/runtime compatibility limitation**, not a harmful instruction, a model failure, or evidence that Hermes cannot support a native diagnostic. The other arm was not launched on the already-invalid path.

An earlier [episode 229f2c0b242a48168dc742f88b542e1a](../evals/results/native-instruction-preflight/229f2c0b242a48168dc742f88b542e1a.json) stopped because the guard incorrectly classified the local `socket.gethostname` call as network activity. A regression test reproduced that error; the guard now permits the local lookup while still denying address resolution and connection attempts. That earlier receipt remains historical evidence, not a valid network-failure finding.

Neither episode entered a conversation or produced a behavioral output. Their workers were reaped and disposable runtime directories removed. The private evidence and attempt ledgers are retained under `.evals/native-diagnostic/<run-id>/`, which is ignored by Git. These are preflight processes, not trials charged against the authorized initial behavioral comparison. Interrupted, rejected and failed preflight attempts remain visible; do not silently relabel them successful or rerun into the same output location.

## What exists

- [Controller](../tools/evaluation_native_diagnostic.py): immutable run locations, candidate/surrounding-skill snapshots, runtime and harness bindings, attempt reservation, guarded-worker launch, parent process receipts, cleanup, and allowlisted public receipt construction.
- [Worker](../tools/evaluation_native_worker.py): assembly-only input contract; a declared credential-free route-construction substitute; native factory and prompt-component observation path; guards installed before native imports; no conversation loop, model tool dispatch or credential acquisition path.
- [Preflight tests](../tests/test_native_preflight.py): ownership, tamper checks, environment isolation, public/private separation, no-inference interface, actual guarded-child filesystem rejection, timeout/reap and staging-error cleanup, plus the hostname regression.
- [Diagnostic checker](../tools/evaluation_evidence.py) and [tests](../tests/test_native_diagnostic.py): the separate comparison checker now rejects byte-identical instruction arms. The existing admission `validate_report` is not changed by this work.
- [Case specification](../evals/autonomy-writing-diagnostic.json): the existing six paired cases. No case has run through this preflight.

The renderer observer preserves returned native text and records exact substring offsets, hashes and function origins when assembly reaches it. This is **component exposure**, not complete file-level provenance or causal influence. The current installed-runtime attempts did not reach it. A skill catalogue entry must not be reported as its body being loaded. Ephemeral instructions are retained separately because native request construction adds them after the initial system prompt.

## Reproduce within the existing scope

These commands prepare an isolated snapshot and run assembly only. Use actual installed native source/interpreter paths, not a wrapper that inherits a live session. `PRIVATE_ROOT` should be the repository's ignored `.evals/native-diagnostic` directory.

```text
python tools/evaluation_native_diagnostic.py prepare --repo REPO --suite evals/autonomy-writing-diagnostic.json --native-source NATIVE_SOURCE --python NATIVE_PYTHON --private-root PRIVATE_ROOT
python tools/evaluation_native_diagnostic.py probe --episode EPISODE_RETURNED_BY_PREPARE
```

A new output path is mandatory. A used or interrupted episode cannot be silently repeated. Prepared source/harness drift is rejected before launch; postflight drift is retained as a blocker. The CLI's successful exit means the preflight produced a receipt, **not that native assembly succeeded or inference is permitted**. Check `observations`, `blockers`, `cleanup_ok`, and validation explicitly.

```text
python -m pytest tests/test_native_preflight.py tests/test_native_diagnostic.py tests/test_artifact_pilot.py tests/test_evaluation_evidence.py tests/test_instruction_profile.py tests/test_instruction_retirement.py -q
```

## Remaining gates

### Check evidence so far

After review fixes, the targeted and adjacent regression command above returned **81 passed, 97 subtests passed**; `git diff --check` passed. The original admission validator's AST matches `HEAD`; the diagnostic changes are separate. Parent readback independently confirmed that both recorded worker PIDs were absent and both disposable runtime directories were removed. These checks do not prove native assembly, outbound trace completeness or behavioral improvement.

Independent review `deleg_8a8779ab` returned “fix then accept as a stopped, no-inference diagnostic.” The parent reproduced both findings with failing tests and fixed them locally:

- Receipt validation requires nonempty observations with distinct allowed arms, typed lifecycle fields and consistent aggregate cleanup. Missing, duplicated, malformed or contradictory observations are rejected; a legitimate one-arm early stop remains valid.
- The network-forbidden probe strips proxy variables case-insensitively because proxy URLs can contain credentials. Synthetic credential-bearing proxy tests cover the real environment helper; the shared evaluator environment policy is unchanged. No live proxy values were inspected. Earlier episodes used the older filter and are not proof of a credential-free environment.

Both historical public receipts still validate under the stricter checker, and their artifact hashes were recomputed successfully. Their contents remain unchanged. No new native probe was launched for these controller-only fixes; the historical harness bindings identify the versions actually exercised, not the revised controller.

Review limitations remain: runtime binding covers tracked native Python files and the interpreter, not all imported dependencies/resources; `equal_except_declared` is test-only, not a production equivalence check; worker request/conversation/session fields are initialized assertions rather than instrumented counters. The observed early import failure supports the stopped episode's no-conversation conclusion, not a general successful-assembly guarantee. Timeout tests cover a sleeping child; successful assembly, interrupt/orphan recovery and complete request provenance remain unproved, and interruption can leave partial receipts.

Canonical SOUL and communication-skill hashes still match the historical prerequisite receipt. The live SOUL text matches canonical text, but its raw bytes use CRLF where canonical uses LF; the historical byte-equality claim must not be repeated. Future source bindings must preserve both byte hashes and state any justified text normalization explicitly.

### Before behavioral trials

1. Establish an explicitly bounded, observed way for required native startup helpers to run without allowing arbitrary subprocess effects. Do not classify a guard-induced startup failure as an instruction failure, remove the guard globally, or prewarm native initialization outside it to hide the boundary.
2. Attest the intended live-profile instruction projection, personal-context handling, enabled tools, native plugin/MCP initialization and frontend additions. The repository skill snapshot and explicit probe config are not proof of live Desktop equivalence. Safe mode and omitted plugins remain declared differences.
3. Capture complete final serialized requests without credentials. Native lifecycle payload helpers independently truncate long strings, sequences and deep objects; increasing one global limit is insufficient. Ephemeral context, middleware and Codex transport sanitization/SDK merging occur after initial assembly.
4. Establish actual tool-effect containment, equivalent route/settings, natural skill loading, exact candidate-only deltas, and complete ownership/cleanup before behavioral trials. A Python audit hook is not a sandbox for model-generated programs or untrusted native extensions.
5. Run the bounded native comparison only after those gates pass. Source mapping establishes exposure, not influence; failure-specific causal interventions and live repairs remain separately reviewed/budgeted steps.

No diagnostic receipt grants admission, retirement, cache eligibility, deployment or cross-host parity. Do not loosen existing governance schemas to admit it. Keep the older [prerequisite receipt](../evals/results/autonomy-writing-preflight.json) unchanged. Preserve conflicting evidence and distinguish a valid report of an operational failure from a successful experiment.

## Ownership and rollback

Changes are local implementation drafts, not deployed instructions. No live profile, canonical SOUL, shared communication skill, session history, or native Hermes source is changed. No commit or push is performed. The first milestone ends with this explicit no-go result; completing later gates may justify a narrowly reviewed adapter change, but not a new scheduler, evaluation framework or broad runtime rewrite.
