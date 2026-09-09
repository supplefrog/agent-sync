# Breadcrumb helper

`breadcrumb.py` is a manually invoked, stdlib-only CLI for one explicitly named JSON record. It never scans for records, starts a daemon, calls providers, or edits evidence files.

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

## Tests

```text
python -m unittest discover -s <skill-dir>/scripts -p test_breadcrumb.py
```
