# cc-dynamic-workflows routing adapter

Status: staged candidate; no live route policy was promoted.

This directory mirrors the current Hermes-native workflow runner bundle for review. Evidence-selected tasks set `model`, `provider`, `reasoning_effort`, and `decision_receipt` together. The runner validates that the receipt targets `cc-dynamic-workflow`, matches the exact tuple, and carries policy, requirement, and evidence references. It persists the receipt on the task and every attempt before launch; resume reuses the stored tuple. Receipt-pinned tasks cannot silently escalate to another model.

Unreceipted low/medium/high tiers remain only as a backward-compatible fallback for existing workflows. They are not the shared routing policy.

Checks:

- From a Hermes source checkout with the native ephemeral-session schema: `python <agent-signal>/integrations/hermes/cc-dynamic-workflows/scripts/workflow_runner_tests.py WorkflowRunnerTests.test_evidence_receipt_pins_exact_route_outside_legacy_tiers WorkflowRunnerTests.test_receipt_route_must_match_exact_task_route WorkflowRunnerTests.test_fixed_task_route_cannot_bypass_required_policy WorkflowRunnerTests.test_role_defaults_and_explicit_mini_route_to_four_pinned_tiers`
- Real Luna-high and Sol-low smoke: `evals/results/adaptive-routing-cc-workflow-smoke-2026-08-16.json`

Known boundary: the current installed Hermes CLI does not accept the runner's ephemeral-session registration flags. The successful smoke therefore scrubbed controller identity and deleted both generated sessions through `hermes sessions delete --yes`; the evidence record preserves this limitation. Do not promote the bundle until the native lifecycle adapter and runner are reviewed together.
