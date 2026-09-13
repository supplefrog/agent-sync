# Evaluating Codex Plugins for Hermes Use

Use this when the user asks whether a Codex plugin/skill is useful to Hermes.

## Checklist

1. Inspect Codex config/plugin state rather than assuming installed status:
   - Windows Codex config commonly lives at `C:\Users\<user>\.codex\config.toml` / `/mnt/c/Users/<user>/.codex/config.toml` from WSL.
   - `codex plugin list` is the authoritative installed/enabled/not-installed view when Codex is callable.
2. Distinguish three states:
   - Marketplace/cache files exist.
   - Plugin is installed.
   - Plugin is enabled.
   Cached marketplace files can be useful to read even when the plugin is not installed.
3. Read the plugin's `skills/*/SKILL.md` files and any `EVALUATION.md`/README before judging usefulness.
4. Decide whether the content is:
   - Directly portable as a Hermes skill or support reference.
   - Only useful inside Codex because it depends on Codex app/plugin runtime features.
   - Redundant with an existing Hermes skill, but worth patching for a missing pitfall or trigger.
5. Do not enable/install a Codex plugin just so Hermes can benefit from it. Hermes does not automatically load Codex plugins.
6. If useful, import/adapt into a class-level Hermes skill or add a reference under an existing umbrella; avoid one-plugin-one-Hermes-skill sprawl unless the plugin represents a durable class of work.

## Example: Engineering Comms plugin

The local `engineering-comms` plugin may provide useful portable writing/review workflows even if `codex plugin list` reports it as not installed. Its useful patterns are:

- `management-update`: rewrite technical engineering work for Slack/JIRA/email/standup/leadership. Preserve product/team/version/owner context; strip code-level minutiae.
- `bug-postmortem`: write RCA/postmortem only after repro, actual root cause, fix artifact, and validation are known. Do not draft speculative RCAs.
- `change-scrutiny`: review whether a proposed change should exist, whether a simpler path exists, and whether end-to-end code paths support the claim.

These are good candidates for importing into Hermes as class-level communication/review guidance or as subsections of existing review/writing skills.