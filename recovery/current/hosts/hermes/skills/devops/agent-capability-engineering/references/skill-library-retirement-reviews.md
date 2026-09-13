# Skill-library retirement reviews

Use this procedure when auditing enabled skills, deciding what to keep or disable, or claiming that one capability supersedes another.

## Decision ledger

Track each candidate as `undecided`, `keep`, `disable`, `repair`, or `defer`, with one evidence-based reason. Once the user decides an item, remove it from subsequent decision views unless they explicitly ask for a recap. Do not repeatedly display completed decisions.

Treat `keep` and `disable` as decisions, not recommendations to revisit in the next response. Reopen one only when new concrete evidence changes the comparison, and name that evidence before changing the recommendation.

## Exact overlap test

Before saying a skill is redundant or superseded:

1. Load both entrypoints and inventory every routed branch, linked reference, script, template, external integration, and verification gate.
2. Map each old branch to its proposed owner. Mark coverage as stronger, equivalent, weaker, missing, or unsafe/stale.
3. Inspect the replacement's nested implementation where correctness matters; a richer umbrella description does not prove its routed branch is better.
4. Call the old skill fully superseded only when every material branch has an equal-or-better owner and routing remains unambiguous. Otherwise recommend keep, repair, or staged consolidation and name the gaps.
5. Separate a defective nested file from the whole capability. Do not dismiss a skill with vague labels such as “sucks” or infer total redundancy from partial overlap.

## Disabled-discovery trade-off

A disabled skill may disappear from the model-visible catalog in fresh sessions. Before disabling a niche capability, ask whether the user expects automatic routing from an ordinary future request. If yes, either keep its lightweight trigger enabled or verify an enabled class-level router can discover and load the deferred capability. Do not promise that a fresh session will rediscover an invisible disabled skill without such a route.

## Applying decisions

Use the supported capability/configuration surface, preserve the existing disabled set, and verify the exact skill is absent from the enabled inventory. Report only the newly changed state; keep the active decision list limited to unresolved candidates.
