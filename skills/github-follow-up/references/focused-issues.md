# Focused issue procedure access

The procedure owner is Hermes's native `github/github-collaboration-workflows/references/github-issues/SKILL.md`. Its nested location is intentional consolidation; it need not appear as a standalone catalog entry. This reference supplies access, not another issue policy.

1. Resolve the intended Hermes home from its explicit launch configuration or `HERMES_HOME`; otherwise use `%LOCALAPPDATA%/hermes` on Windows or `~/.hermes` elsewhere, appending the literal `HERMES_DATA_DIR_SUFFIX` to that default directory name when set. Verify the selected path; do not import runtime modules or inspect credentials to locate a text file.
2. Read the full `skills/github/github-collaboration-workflows/references/github-issues/SKILL.md` from that home. Hermes may use `skill_view` on `github-collaboration-workflows` with this relative linked-file path; other agents can read the file directly. Keep conditional references relative to that procedure's directory.
3. If the native source is unavailable, resolve Agent Sync from the shared skill root's `.agent-signal-fleet.json` `source_snapshot`, stripping `render/fleet`. Read the same relative package under `recovery/current/hosts/hermes/skills/`. Identify it as a recovery snapshot, not current native source.

If neither source is readable, report the missing procedure and continue independently supported read-only work. Do not silently draft or publish under a procedure claimed to be loaded. File access grants no native tool, credentials, publication permission or cross-machine runtime parity.
