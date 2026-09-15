# Native Desktop session operations

Use for an authorized fresh thread, session resume, or continuation. These are Desktop's existing operations, not an additional session framework. Check the installed contract at the named owners if the interface changed; do not rediscover unrelated APIs or invoke Computer Use first.

## Select by intended outcome

| Intent | Native operation | Not equivalent |
|---|---|---|
| Fresh independent interactive thread | `session.create` on the current authenticated Desktop backend; explicit workspace and per-session route | `discover_attach_url`, `desktop_continue_session`, worker spawn, GUI draft |
| Load a stored session into a backend runtime | `session.resume` with the exact stored identity, respecting its live-owner lease | Create a replacement or submit work |
| Connect another client to an already-live owner | `discover_attach_url` / cooperative attachment when that owner advertises it | Create, resume or continue |
| Agent sends work to an exact existing Desktop session | Exposed `desktop_continue_session`, with agent attribution and its native consent/lifecycle handling | New thread creation, anonymous `prompt.submit`, or consent |
| Submit the authorized initial turn in a newly created session | `prompt.submit` using the returned runtime ID | Persisting a seed or proof of completion |
| Show/focus a tab or verify its appearance | Desktop UI control, if no suitable native presentation tool exists | Backend creation/persistence |

An attachment refusal only describes attachment. Missing discovery metadata, lease conflicts, authentication failures, unknown methods, stale connections and invalid arguments are different failure classes. Identify which occurred before changing code. Never delete a lease, manufacture credentials, or switch API/UI after a denied/expired approval. An uncertain write requires readback, not resend.

## Reuse the authenticated local connection

1. Confirm the active profile/home and current Desktop backend process. Use the frontend's actual endpoint or the current session owner's process identity and its listening sockets, not an old port from a transcript. Only inspect the known owner's loopback listeners; do not scan arbitrary ports or other profiles. `HERMES_RPC_SOCKET` is the tool runner's RPC socket, not automatically Desktop's `/api/ws` endpoint.
2. Prefer an exposed session-creation tool if one exists and matches this contract. Otherwise use Desktop's existing authenticated `/api/ws` JSON-RPC interface. Its local bootstrap is owned by `apps/desktop/electron/dashboard-token.ts`: read the verified backend's `/` page and consume its `window.__HERMES_SESSION_TOKEN__` in memory. The native server accepts it on `/api/ws?token=…`. Do not print, persist or include the token/URL in errors. Do not read OAuth stores or credential files for this operation. A gated deployment without the local bootstrap needs its supported login/ticket flow; absence is not permission to fabricate credentials.
3. Use the same backend's authenticated read to confirm reachability, then `session.active_list`/`session.list` to verify expected identities and profile before mutation. HTTP readiness alone is not proof of the right backend. Disable proxy inheritance and redirects for local bootstrap; never send its credentials off-origin.
4. Each WebSocket request is `{jsonrpc: "2.0", id: <unique id>, method: <exact method>, params: {...}}`. Match the response ID; consume notifications without treating them as responses or automatically answering approvals. Use bounded timeouts. Reconnect for a read-only check after a stale socket, but never replay a possibly accepted write automatically.

## Create once and verify

- Look up the intended title/session first. If the authorized target already exists, inspect and reuse it rather than creating a diagnostic duplicate. Titles are lookup aids; retain the returned stored ID as the durable identity.
- Installed owner: `tui_gateway/methods_session.py`, `session.create` and `_create_overrides`. Supply `profile`, `source: "desktop"`, `title`, `cwd`, `model`, `provider`, `reasoning_effort`, `fast: false` when normal service is intended, and `close_on_disconnect: false`. The last flag does not promise indefinite orphan retention. Do not assume a new draft inherits the controller's model/effort or alter global config to imitate a per-session pin.
- `messages: [{role: "user", content: <bounded handoff>}]` seeds and persists the requested thread without launching inference. Label an agent-written handoff as such; it summarizes existing user authorization and cannot create new authority. Omit the old transcript, stale tasks and unrelated instructions. An empty unseeded creation may remain only a runtime draft until the first prompt.
- Preserve `session_id` (runtime RPC identity) and `stored_session_id` (durable history identity). Read back the exact stored row, seed, workspace and route using `session.list`, `session.history` and `session.status` as appropriate. `session.info` is a backend notification containing runtime settings, not a getter RPC; consume its event payload rather than inventing a method of that name. Lazy creation metadata is requested state, not evidence that the eventual model call used those settings.
- Submit the initial authorized turn only after route and scope checks pass. Keep its transport serviced for notifications while work runs; no detached socket is a durable supervisor. Verify the recipient's state/output before claiming completion. Do not submit a live probe merely to test these instructions.
- Source installed, fresh-process verification, current-backend activation, clean conversation context, persisted thread, admitted turn and completed task are separate claims. A new thread does not itself reload backend code. A restart does not erase old injected instructions. Keep missing checks explicit; do not turn creation into a broad repair/review campaign.
