# Breadcrumb helper

[`breadcrumb.py`](../scripts/breadcrumb.py) is a manually invoked, stdlib-only CLI for one explicitly named JSON record. It never scans for records, starts a daemon, calls providers, or edits evidence files. It has no watcher, automatic capture, networking or agent hooks. It checks shape and local file existence, not evidence truth, freshness, authorization or hashes.

Resolve the script from this loaded skill directory, not the project working directory. Use the host's available Python 3.11+ interpreter (`python` or `python3`). Do not store credentials, raw private transcripts or hidden prompts.

## Commands

```text
python <skill-dir>/scripts/breadcrumb.py init RECORD
python <skill-dir>/scripts/breadcrumb.py check RECORD
python <skill-dir>/scripts/breadcrumb.py update RECORD --from INPUT
python <skill-dir>/scripts/breadcrumb.py render RECORD
```

`init` refuses to overwrite an existing path. It writes an intentionally incomplete scaffold and records the missing intent provenance explicitly. The exact scaffold is a permitted starting draft for `update`; completing it appends the scaffold to `history` with `draft: true`, where it remains historical and is never presented as validated evidence. `check` exits nonzero for missing or malformed fields, an invalid deployment status, unsupported network/UNC references, or broken **current** local references. Historical broken or unavailable evidence is retained and reported as a warning; it does not invalidate the current record. Successful structural validation does not inspect or prove evidence contents.

`update` validates the replacement as the new current record, including its current local references, before writing. Existing current references are not required to exist because an update may repair them. The replacement must keep the immutable `id`; the old current revision is appended to `history`, the revision is incremented, and the write uses a same-directory temporary file plus replace. This atomic replacement assumes a single writer. Relative references resolve from `RECORD`'s directory, including references to files elsewhere in the project; absolute local paths are also allowed. Only local paths are supported: URLs and UNC/network-share paths are rejected without probing or fetching them. No evidence path is modified.

`render` emits Markdown to stdout only after validation. It labels the current state, scoped supersession, evidence references, limits, rollback, and historical revisions; current references are clickable absolute `file:` links with URL-escaped paths, and historical revisions are explicitly marked as not current. Draft snapshots are labeled as drafts, not evidence; historical reference failures are shown as warnings.

## Write and interpret a record

Complete a copy of the initialized scaffold as INPUT, preserving its ID; later updates also use a copy. One designated writer owns updates; other agents contribute evidence to it. The JSON is authoritative and Markdown is a generated view. Direct edits bypass history preservation.

Map decision reasons and material alternatives to `change.text`, and evidence that would reopen a decision to `checks.limits`. Record missing intent provenance explicitly. For research or non-deployment work, state that deployment/rollback is not applicable; use `planned`/`in_progress` for unfinished work, never `deployed`. This schema has no generic completed-research status.

The helper does not fetch URLs. Use an already-authorized local source extract with its original URL in prose, or an existing research record. Interpret actual evidence using the record rules in the entrypoint; validation alone grants no action authority.

## Record shape

```json
{
  "schema_version": 1,
  "id": "immutable-id",
  "title": "Short title",
  "intent": {
    "text": "Why this change exists",
    "provenance": {"refs": ["evidence/intent.txt"]}
  },
  "change": {"text": "What changed", "refs": ["evidence/change.txt"]},
  "checks": {
    "text": "What was checked",
    "refs": ["evidence/check.txt"],
    "limits": ["What was not checked"]
  },
  "deployment": {
    "status": "planned",
    "refs": ["evidence/deploy.txt"],
    "session_limits": ["Manual session only"]
  },
  "rollback": "How to undo it",
  "supersedes": {
    "scope": "Exactly which prior statement this replaces",
    "refs": ["evidence/supersedes.txt"]
  },
  "revision": 1,
  "history": []
}
```

Allowed deployment statuses are `planned`, `in_progress`, `deployed`, `rolled_back`, and `blocked`. `schema_version` must be the integer `1`, and `revision` must be a positive integer. Intent provenance must contain either one or more local refs or a non-empty `missing_reason`. `history` is managed by the CLI; its snapshots are historical, and only an exact scaffold may carry `draft: true`.

## When changing the helper

Run [the CLI regression suite](../scripts/test_breadcrumb.py):

```text
python -m unittest discover -s <skill-dir>/scripts -p test_breadcrumb.py
```

Preserve draft completion, rejected-update nonmutation, scoped history, clean malformed-input errors and broken historical-link warnings. Interpret prior validation and deployment evidence through [provenance and scope](provenance.md).
