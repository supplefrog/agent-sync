# Worktree publication

Independent changes develop in separate Git worktrees based on the published commit. Only committed ready changes enter publication; development branches, indexes, and unfinished files remain untouched. Worktrees use the existing repository, remote, permissions, and reconciler rather than a separate scheduling service.

Create a development worktree from the discovered published source with Git's normal `worktree add -b` command, outside live skill discovery. Commit only the authorized, checked change. In that development worktree:

```text
python tools/run.py reconcile plan --ready COMMIT --adopt OWNER --include FILE
python tools/run.py reconcile sync --ready COMMIT --adopt OWNER --include FILE
```

Repeat selectors as needed; an owner or exact-file scope is required. Owners must already be admitted. Includes select reviewed publication content, not deployment authority. The ready input freezes a linear, non-merge commit range from its public base and rejects unselected paths. Uncommitted work is outside that range.

Readiness checks run before the common Git-directory publication lock. Once ready, a caller waits up to 120 seconds, fetches the latest configured upstream, and uses Git's three-way cherry-pick to compose its changes in a tool-owned integration worktree. Independent edits, including separated hunks in one file, merge normally. Real conflicts stop the affected change before deployment, retain its ready identity and conflict evidence, and release the integration lane for independent work.

The existing reconciler then checks, deploys, commits, pushes, and verifies the exact selected result. Development can continue during this serialized publication. Hash-only generated metadata is recomputed for the selected scope instead of coupling independent changes through aggregate hashes. Policy and selected same-source readback changes require explicit manifest review.

The shared Git directory contains two tool-owned worktrees:

- `agent-signal-integration-worktree`, branch `agent-sync/integration`, composes and publishes ready changes.
- `agent-signal-published`, branch `agent-sync/published`, holds only verified published commits and is the durable source agents discover through the managed skill manifest.

The published source stays stable during composition, conflicts, and an unsuccessful push. After publication, it advances to the verified commit, its fleet snapshot is rendered, and managed global source provenance moves there under existing root locks and state identity checks. Origin migration is restricted to the same shared Git repository and preserves installed content and owner records. These paths are maintained state, not temporary candidates to delete. The launcher reuses the primary checkout's dependency-ready runtime for linked worktrees; it installs nothing.

Before composing or deploying, the common-directory journal records the frozen ready input and selection. A failed deployed or published attempt retains that journal and the existing publisher's pending receipt. Retry the same command; every publication path, including legacy and native maintenance, honors that pending attempt. A completed publisher receipt stays durable until published-source readback succeeds, so a crash after push cannot turn into another deployment. A failure while refreshing published source or provenance resumes that phase. Retry checks reject integration edits and extra files outside the frozen composition. Unexpected worktree identity, HEAD, index, source, or state changes stop rather than overwrite outside work. Never reset pending integration or rewrite remote history.

Resolve a source conflict in the development worktree and submit a new ready commit. Explicit legacy working-file publication uses `--shared-checkout`. Native capture and configured-default changes remain on the existing native maintenance path without `--ready`, in a development checkout with the correct upstream; the stable published source rejects direct maintenance. Exact source-authored generated overlays may be included, then restored through the native recovery owner. Ready integration rejects capability admission and lifecycle changes even through exact-file selection, and does not change provider, authentication, or running-session defaults.

Mechanism tests establish integration, preservation, conflict, lock, and retry behavior against local Git/fleet fixtures. Installed content and remote readback are separate deployment evidence. Neither establishes a model-quality gain, universal host parity, or billed savings.
