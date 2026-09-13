# Claude Desktop with a third-party gateway

Use this when Claude Desktop/Claude Code is connected through an Anthropic-compatible gateway rather than a Claude account.

## Stable configuration boundary

- Prefer Claude Desktop's Setup UI and the gateway application's supported agent/model-mapping UI. Treat direct edits to generated profile IDs, Electron state, or proxy internals as diagnostic only, not promotion-ready configuration.
- A static `inferenceModels` list is the supported control for the desktop picker. The first entry is the default. Gateway entries must be exact gateway model IDs that satisfy Claude Desktop's Anthropic-model validation; raw `gpt-*` IDs can be rejected even when model discovery previously displayed them.
- When a gateway intentionally exposes Anthropic-shaped routes backed by another provider, use those routes in `inferenceModels` and use `labelOverride` only for display. Create the route through the gateway's supported alias/mapping feature, not by mutating generated state.
- `autoModeEnabled` makes Auto mode available; it does not prove that Auto is selected. Verify the permission selector visibly shows Auto/Automatically approve.

## Picker versus delegation

Visible picker restriction and backend/subagent routing are separate claims. Claude Code subagents normally select `inherit`, `haiku`, `sonnet`, or `opus`; a gateway may map those tiers elsewhere. Do not promise that a hidden model remains usable merely because the picker omits it or a proxy alias exists. Verify with a real subagent task and inspect the child model identity or gateway request record.

If stable UI/configuration cannot express the requested hidden route, report it as unsupported or unverified. Do not manufacture a hidden route with hand-edited aliases.

## Plugins, skills, and connectors

An empty organization plugin directory is expected when no Anthropic organization provisions plugins. It is not evidence that arbitrary marketplace plugins should be installed. Inventory built-in skills and native tools first; admit external plugins/connectors individually under the capability-admission process, including their auth and executable surface.

## Verification checklist

1. Restart through normal application controls after supported configuration changes.
2. Confirm provider health is healthy.
3. Open the picker and count/identify visible models.
4. Confirm the permission selector visibly shows Auto.
5. Run one ordinary inference on each visible model.
6. For any hidden subagent route, run a child task and verify the actual child model.
7. Verify image generation with a real image task before claiming an image model is selected automatically.
