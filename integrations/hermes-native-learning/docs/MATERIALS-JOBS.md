# Materials, imports and supporting work

The original normal-GUI worker paragraphs below describe Hermes. The T3 adapter now selects a separate native Codex port in `src/t3/job-port.mjs` through its trusted server-side binding, never a model-supplied host switch. See t3/AGENT-PROTOCOL.md and docs/T3-INTEGRATION.md. Both routes retain the shared private ledger/result/teacher-use contract.

On T3, dispatch prepares `spawn_agent` with a fresh context. Admission stores the actual `{agent_id,nickname?}` receipt and native host identity. Completion additionally requires the exact one-child terminal `wait_agent` result as `completionReceipt`; timeouts, nonterminal or mismatched results refuse. These are native Codex receipts, not fabricated Hermes dispatched/background handles. Native controls are prepared wait_agent/send_input/close_agent calls; the existing host agent executes them only under its actual supported tools, runtime/data/model limits and user authority. No child, provider loop, watcher or automatic model reentry is launched by these commands. The T3 source branch has not been exercised in a live host or assigned the predecessor's regression results.

These are native integration source contracts, not a record of worker execution or enrollment. The teacher is the existing Hermes agent. No model client, watcher, private backend or second learning application is supplied.

## Explicit local materials

The optional private binding accepts `materials:[{id,label,kind,file}]`, with `kind` equal to `notes` or `pdf` and a workspace-relative file. Files must exist, physically remain in the private workspace and stay outside every lesson, export, knowledge and job directory. IDs and relative paths are trusted enrollment configuration, never directive attributes or learner-selected commands. Access to a new source requires the user's data authority; this source preparation enrolled nothing.

`material list` returns enrolled labels and attached fingerprints. `material attach` needs `materialId`, current `expectedRevision` and actual `authorship`. It captures source SHA256, size and stable path-derived source ID in lesson state. Changed bytes require a fresh explicit attachment. `material read` returns bounded UTF-8 notes, not PDF bytes; use `offset`, `length` (at most64000characters) and the prior `sourceSha256` after the first page. No fetching URLs, OCR, broad file picker or private history scan occurs. A PDF header check establishes file type only, not successful reading.

The card lists attached names/kinds without raw text or file paths. Raw notes never enter exported snapshots automatically. Imported proposition statements are derived material and can appear in the private learner projection; enroll/export accordingly.

Reader limits apply to path metadata, the actual opened descriptor and the cumulative bytes read, before retention/decoding. At most one bounded sentinel byte beyond the cap can be read to detect growth. Identity/generation drift refuses the operation, closes the descriptor and never accepts a partial or silently truncated source/result.

## Notes into the existing knowledge store

With an explicitly enrolled private `knowledgeRoot`, use `import` with the bound `chatId`, `materialId` and a stable explicit `importId`:

1. `prepare` returns the next serialized chunk and fresh source-local graph digest. The pinned upstream `chunkNotes` algorithm is reused. Each **new explicit import** processes the whole file, including identical bytes; this is not global fingerprint deduplication. The same ID resumes its unchanged source. Only one unfinished import owns a source at a time.
2. Record actual `findings` with `part`, `{propositions,chains}` and `authorship`. Notes have source IDs, not invented teacher message anchors. Earlier findings are immutable.
3. `audit` exposes propositions and a bounded graph page, excluding raw source and proposed chains. Further graph lookup uses the existing revision-bound `knowledge graph` command. This projection is not an independent auditor context: when an independent auditor is required, use an actually fresh authorized host child/context, never merely change role names.
4. `merge` accepts `part`, the captured `graphRevision`, `{links}` identity judgments and actual `authorship`. It uses the existing upstream merger/ledger, rejects stale or unknown identities and replays once. Successful chunks remain after interruption or `abort`; the import checkpoint is written only when all chunks finish. An empty import is durably complete.

No extraction/auditing model is launched by these data commands. The owning agent can orchestrate the actual grounded stages through normal supported tools when authorized; this package does not claim independent model quality or automatic scheduling from a fixture. Imported propositions join the attached lesson's review and fresh practice target catalogue, not its mastery score.

`abort` is state-only: it resolves the saved owner/chat/import and enrolled material identity without reopening the source. Editing notes before or after an attachment refresh cannot trap an unfinished import. It retains committed chunks, refuses completed imports, is idempotent, and writes no false completion checkpoint. Preparing, extracting, auditing and merging still require the exact unchanged attached source generation; an aborted old run cannot merge findings into new bytes.

## Native supporting jobs

The optional private `jobRoot` must be physically disjoint from all state/export/graph roots. It is a bounded durable ledger and fixed worker-result directory, not a general tool server. It does not change lesson revision, pending questions, continuation claims or drafts when work progresses.

`job request` needs `kind` (`research`, `demo`, `visual`, `pdf`), stable `toolCallId`, current `expectedRevision` and the corresponding input. Research uses `{question,context?}`, demo `{title,brief}`, visual `{brief}`, PDF `{materialId,question}`. A saved request is explicitly **not dispatched**. Identical replay returns its existing job; a different request under the same call refuses.

`job dispatch` prepares one supported `delegate_task` request with a fresh child context and a fixed result file. It does not call that tool. The owning agent must first have normal authority for the child model, tools and disclosed data, then execute that exact supported request and retain its actual receipt. No `output_schema` is supplied because the host's bounded schema-correction retry would imply another model attempt. Normal child tools follow actual Hermes policy; a declared output folder is not an OS sandbox or a tool restriction.

For the selected Hermes source, a normal GUI top-level `delegate_task` has a later-result consumer and returns `status:"dispatched",mode:"background",count:1,delegation_id,subagent_ids:[id]`. Record that one-child receipt with `job admit`. This integration deliberately refuses joined/one-shot receipts instead of inventing an asynchronous admission. The existing Hermes runtime—not a package watcher—returns completion to the same parent between turns. Children may stop when that session exits, `/stop` or `/new` runs; the saved ledger is durable, the child is not promised to survive. Inspect actual status before any repair or redispatch; no automatic replacements are launched.

`job control` prepares existing `delegate_task` list/steer/stop requests using the admitted child handle. It does not claim the host actually stopped anything. `job progress` binds the actual `delegationId`, activity and optional uniquely identified observed usage. Unknown usage stays absent, never zero. Replayed observed-call IDs cannot double count or change accounting.

Children write `{jobId,kind,result,verification}` to their fixed `result.json`, return its SHA256 and actual evidence references, and do not run parent-owned state commands or forge owner environment aliases. The parent independently inspects the real evidence and uses `job complete` with `delegationId`, `resultFile:true`, `resultSha256` and actual `authorship`. No arbitrary result path is accepted. Completion checks regular-file identity/generation/hash, job/kind and the pinned result shape. Inline bounded result objects remain supported for normal tool returns. Errors are saved as failures, not fabricated success.

Demo success needs upstream `tested:true` plus actual test receipt references; visual success needs an inspection declaration and evidence references. These are recorded reports, not cryptographic proof or a host pixel attestation. PDF results must match the attached unchanged source/question and positive unique `pagesRead` contained in `pagesConsulted`; citation honesty remains the actual reader's responsibility. Research uses credential-free HTTP(S) citations; no link is fetched by the state adapter.

Results are saved and **queued**, not marked consumed. `context` and `context-page` return the pinned upstream result-steer intent with raw HTML/SVG excluded. After the actual owning teacher saves a new passage using the result, `job ack` binds `afterMessageId`; a learner input, old passage or queued marker cannot acknowledge it. Reopen preserves results and delivery state. Stale admission/result/reaction replays refuse.

## Native presentation

Export writes immutable content-addressed HTML/SVG files alongside the redacted card. The native contribution reads only its existing picker-granted folder and verifies each descriptor's kind, basename, size and SHA256. Research briefs/citations and PDF page sets use text/explicit links. No raw job prompts, producer paths or worker payloads enter the card JSON.

Demos reuse pinned `buildDemoSrcDoc` and its pure resize/error reducer. They run in `sandbox="allow-scripts"` with **no same-origin**, a restrictive CSP inserted before untrusted markup and source-window-checked postMessage. Inline interaction is permitted; parent answer, tool invocation, folder access and automatic follow-up bridges are absent. This is browser containment, not an OS network sandbox; self-navigation, renderer policy and real pixels still need consolidated host verification. SVG uses an image data URI, never active SVG in the application DOM. No native preview/execute-JavaScript capability is requested.

A demo error is bounded and shown locally. Only **Send error to teacher** submits a `job-error` envelope through the exact owning composer. The handler checks lesson revision and saved artifact identity, persists the report separately and queues it for the teacher. It does not submit an answer, overwrite a commitment or launch an automatic repair. After a genuine new saved teacher reaction, `job report-ack` consumes its `reportId`/`afterMessageId`; retries cannot consume another report.

Markdown, math and Mermaid lesson prose use the host renderer with prior literal-resource fallback and reveal guards. Rich choice presentations retain the exact shuffled indices used by the existing controls. Drafts, answer commitments and explicit practice Next remain authoritative in the existing adapter.

## Activation boundary

No material, knowledge/job root, child/provider call or new folder grant is activated by this file. The earlier two-input teaching grant cannot cover these new data/worker capabilities. Complete source review first; later consolidate native activation and real product acceptance with exact bundle, chosen files/roots, actual context/tool policy, child count/models/time/usage bounds and cleanup. No further runtime or maintenance fork is required by this source design. Hermes SDK/caller/loading and real host background completion remain qualification gates, not findings established by these offline controls.

Before any actual child call, read the selected runtime metadata for its provider/model, delegation.max_iterations, child timeout, tool exposure and parent background-consumer availability. In selected Hermes source, caller-supplied max_iterations is ignored in favor of delegation.max_iterations; a prompt or prepared JSON cannot enforce a smaller cap. Children inherit the parent model unless delegation.provider/model overrides it. If those actual limits/data differ from the approved scope, stop that invocation and obtain a supported bound or exact authority; do not change global settings silently. No child budget or model route was configured by this package.
