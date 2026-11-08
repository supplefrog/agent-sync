# Native lesson visuals

Rich content is saved in shared lesson state. Each host chooses its display surface; an MCP connection alone does not supply an HTML renderer.

## Save a teacher visual

After reading the current revision, call `learning_command` with:

```json
{"op":"visual","chatId":"the-enrolled-lesson","expectedRevision":4,"authorship":"host-agent","id":"grouping-explorer","title":"Grouping explorer","format":"html-fragment","source":"<div id=\"grouping-explorer\">...</div>","reveal":"now"}
```

`format` is `html-fragment` or `svg`. HTML supports inline styles, scripts, charts and controls. Use a unique root ID and scope selectors/styles to it. Self-contained content is most portable because each host has its own resource policy. Fragments omit doctype/html/head/body wrappers. Existing worker-produced complete HTML demos keep their existing artifact route.

The teacher can use its host's Visualize authoring guidance and save that exact source. Attachment launches no worker or model. Each lesson retains up to eight immutable visual IDs, each at most 200 KiB and bounded to fit the T3 asset bridge after JSON encoding. Save changed content under a new ID. Content digests bind exported bytes to the lesson. Only descriptors in the owning public view are readable through `learning_artifact_source` or the existing app-only asset tool.

Use a visual when it helps the learner see the relationship they are reasoning about. Match the lesson's quantities, labels and assumptions. Place a worked answer with feedback or review after the learner has attempted the question. Omit the visual when it would distract or turn a prediction or retrieval check into reading off the answer. To correct an existing visual, set optional `replaces` to its ID and give the correction a new ID. This removes the superseded visual from current learner views, preserves its record, and respects the original reveal gate.

`reveal:"now"` means the teacher checked that content is safe at the current question. Never embed hidden answers in HTML, JavaScript, inline data or widget state. `reveal:"after-question"` binds to the current pending question/problem: teaching waits for its saved result; practice waits for its conclusion. Attachment refuses when no question/problem is active. Deferred source and descriptors remain absent from learner views and native HTML. Browser state cannot unlock them.

## Native Codex desktop

`learning_view` associates the saved lesson with an MCP App resource. Codex desktop can use the same app card in the conversation and its side panel. The card uses the host bridge to refresh the current lesson and displays saved SVGs with the response controls. Interactive HTML uses the separate native chat renderer. For that path, `learning_view` supplies a content-addressed `nativePresentation.path` for a `visualize` content reference. Both use the same saved lesson and revision-bound input. A descriptor alone does not prove that the UI mounted.

The native layout puts the visual beside the question and response controls when the lesson container is wide enough. It stacks the visual above the question at narrow widths. The same controls and explorer remain mounted across resizing. The shared controls retain their original presentation on T3/Hermes.

The controls send the existing `lh.t3 {chatId,kind,expectedRevision,action}` through user-confirmed `sendFollowUpMessage`. On a genuine event, pass its exact fields to `learning_input`, inspect persistence, read teacher context, save the required reaction, and return a fresh `learning_view`. Resume only reopens the view. Caller ownership still comes from host-written MCP metadata.

Snapshots keep their original revision. Late answers refuse instead of targeting newer questions. Requested delivery is not persistence. Pending controls suppress repeated submission; after canceled confirmation, **Resume saved lesson** requests a fresh view. After uncertain saves, inspect current state before retrying. Widget state is optional interface restoration, not the lesson database; this change adds no durable practice-draft guarantee.

Presentation failure is separate from saved state. Combined native content has a 1 MiB limit; reduce visual size rather than replay a successful mutation.

## Other hosts

T3 keeps its MCP App controls. The card lists direct visuals with existing artifacts: SVG renders in the card; HTML uses its native visual publisher because the App blocks nested demo frames. Read verified source with `learning_artifact_source`; wrap a fragment as a full document when that renderer requires one. Hermes uses its existing sandboxed artifact components and export grant. No CSP weakening or new frame origin is required.

Other explicitly enrolled MCP clients can read the same permitted sources, but need their own renderer and confirmed-input adapter. Clients without an HTML surface cannot become interactive just by receiving a path. Remote renderers also need supported access to files on their execution host.

## Build and activation

Rebuild `t3/app.html` and `desktop/plugin.js` using the selected dependency pins. Preserve private bindings and lessons. Point the MCP declaration at the reviewed successor release; a newly loaded MCP process is required. Do not restart an active conversation or claim its previously loaded server uses new code.

`test/native-visuals.test.mjs` drives real commands, state, asset reads, exported HTML and shared DOM controls: identity/ownership, reveal timing, exact response delivery, pending-request suppression, stale-input refusal, and raw/escaped delivery limits. Existing backend checks cover teaching/practice persistence. A genuine native practice response has also been observed saving and reopening through MCP; this does not qualify every host or question variant.
