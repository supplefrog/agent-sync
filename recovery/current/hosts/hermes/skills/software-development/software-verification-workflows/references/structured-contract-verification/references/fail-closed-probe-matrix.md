# Fail-Closed Probe Matrix

Use this matrix when a structured intake patch can promote or persist work.

| Case | Expected result | Durable assertion |
|---|---|---|
| malformed JSON / scalar output | reject | source remains in its intake/triage state |
| missing contract object | reject | no promotion, no children |
| invalid mode/type/blank reason | reject | no promotion, no children |
| valid research-required complete output | accept | gate/metadata is persisted before execution |
| valid reuse-established output | accept | explicit reuse reason is persisted |
| valid not-applicable output | accept | explicit bounded/mechanical reason is persisted |
| research fanout without evidence child | reject | root remains intake state; zero children |
| evidence child has a parent | reject | root remains intake state; zero children |
| execution/verification disconnected from evidence | reject | root remains intake state; zero children |
| execution/verification transitively follows evidence | accept | persisted links and statuses reflect the dependency graph |
| minimal accepted output (title-only/empty body) | contract-specific | never accept a path that omits the promised durable gate |

## Evidence to capture

1. Invoke the real CLI/service/module entry point, patching only the external model/network seam.
2. Record return code or outcome, source status, child count, persisted body/metadata, and links.
3. Reload through a fresh database connection when persistence is part of the claim.
4. Run the focused regression suite and the nearby lifecycle suite; report actual counts.
5. Check staged, unstaged, and untracked imported files so a missing new module is not mistaken for a complete diff.
