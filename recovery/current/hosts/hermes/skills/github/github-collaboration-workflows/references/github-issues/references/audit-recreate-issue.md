# Audit-before-recreate issue triage

Use this reference when a user asks to audit an existing GitHub issue and recreate it only if a prior agent made a poor issue.

## Durable workflow

1. Fetch the issue body, labels, comments, author, state, and URL before deciding.
2. Search duplicates by exact title terms and by the underlying failure area.
3. Inspect enough source/docs to validate whether the issue maps to a real code path or product behavior.
4. Prefer preserving a valid issue. Apply minimal triage edits: labels, priority, component, title/body cleanup, or a comment.
5. Recreate/delete only when the existing artifact is actively harmful or not salvageable.
6. Verify final state with a read-back after every mutation.

## Permission pitfall

GitHub issue mutations can partially succeed. For example, a bulk label edit may apply some labels, then later label additions can fail with a GraphQL permission error such as:

```text
<user> does not have the correct permissions to execute AddLabelsToLabelable
```

When this happens:

- Read back the issue state.
- Report exactly which labels/actions succeeded and which are blocked.
- Do not claim the requested triage is complete unless the verified state matches it.
- Do not retry destructively or recreate the issue just to work around missing repo permissions.

## Decision rule

A well-formed issue with environment, logs, workaround, expected behavior, and a plausible source-code path should usually be kept, even if a different title or labels would improve it.
