# Cross-Host Evaluation Transport

Use when a capability bundle or expanded skill prompt must be compared on Windows across Codex, Hermes, or another CLI host.

## Transport invariants

- Baseline and candidate must receive semantically identical task envelopes through equivalent transport.
- Infrastructure delivery failures are harness failures, not capability losses. Repair the transport and rerun the affected cases.
- Preserve the exact model, provider, reasoning effort, tool policy, prompt assembly, artifact hashes, and judge configuration in the receipt.
- Recheck each host version immediately around matched arms. A runtime/source revision change between baseline and candidate invalidates that host comparison; archive it and rerun both arms on one revision.

## Credential and route preflight

Before starting a repeated trial, run one bounded no-tools smoke through each exact generator and judge CLI with the intended model, provider, reasoning effort, and isolation flags. An authenticated Desktop session, embedded runtime, or sibling CLI does not prove that a standalone evaluator transport can access the same OAuth state.

- Stop before batching if either arm cannot reach inference. Record `harness-blocked` or `harness-failure`; do not emit a behavioral win, tie, loss, or retirement verdict.
- Do not silently substitute direct Codex transport for Hermes, or vice versa. A substitute may produce explicitly provisional model evidence, but cannot satisfy the required-host gate without a separately proven effective-stack equivalence.
- Use each host's native authentication lifecycle. Never copy tokens or private credential stores into evaluation fixtures; temporary homes may receive only the minimum native auth artifact through an approved harness path.
- Include the smoke result and exact transport fingerprint in the durable receipt so a failed prerequisite cannot be mistaken for a candidate regression.

## Hermes prompt-overlay staging
`HERMES_EPHEMERAL_SYSTEM_PROMPT` replaces the configured `agent.system_prompt`/personality overlay; it does not append. For a candidate that should preserve the live overlay, resolve the non-secret live overlay first and set the environment value to `live overlay + candidate`. Record the combined hash. Treat an arm that silently removed the live overlay as mismatched and inconclusive.

## Windows long-prompt pattern

Windows `CreateProcess` can reject a Hermes `-q` argument after linked skill references expand the prompt, typically as `WinError 206`. Do not shorten the candidate silently or omit references.

1. Write the complete evaluation envelope to an isolated UTF-8 file under the case work directory.
2. Give Hermes a short `-q` instruction containing the file's **absolute path** and requiring it to read the file completely before completing the task.
3. Use the same file-indirection transport for baseline and candidate.
4. Verify from the output that the file was actually read before judging behavior.

A relative filename is insufficient: Hermes may resolve from the user home even when the CLI receives a working-directory option, especially under isolation flags. An absolute path was the verified fix.

## Admission interpretation

- A candidate that wins on one required host but loses on another is not a portable winner.
- Keep the host-native capability as an explicit delta when it adds real tools or artifact production; do not replace it merely to make instruction files identical.
- A non-trigger case may tie, but a new instruction still needs at least one meaningful gain and zero material losses on every required host.

## Evaluation child lifecycle

- Give evaluation children an explicit source tag and isolate workdirs/config so baseline and candidate cannot contaminate each other.
- Capture outputs, errors, routes, hashes, seeds, and judgments durably before cleanup.
- After each child process is confirmed ended and the report is readable, delete only agent-created evaluation sessions through supported lifecycle controls. Cover success, rejection, timeout, interruption, and judge failure; provide an explicit keep-evidence override for debugging.
- Never delete the user/parent session, active/shared/referenced sessions, or sessions whose unique evidence has not been integrated. Verify cleanup by source-filtered readback.
