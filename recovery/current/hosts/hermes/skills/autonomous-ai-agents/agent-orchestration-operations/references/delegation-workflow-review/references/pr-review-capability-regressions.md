# PR review capability-regression note

Scenario observed in review:

- A workflow coordinator stopped passing node-level `toolsets` into delegated workers.
- The helper also changed validation to reject `toolsets` outright.
- Tests were updated around completion/reconciliation, but no test covered the lost capability.

Why this matters:

- The change preserved observability but regressed behavior.
- Existing workflows that rely on specialized worker capabilities now fail or run with the wrong tool surface.

Review takeaway:

- When a PR changes async delegation or workflow orchestration, check for:
  - dropped child capabilities (`toolsets`, role flags, permissions);
  - completion callback ordering;
  - pruning/reconciliation paths;
  - sibling flows that still need the same argument or hook.

If a patch removes an argument from one helper, search all callers and all wrappers before deciding it is safe.
