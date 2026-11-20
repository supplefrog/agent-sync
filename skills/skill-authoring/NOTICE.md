# Upstream provenance

This package adapts Anthropic's [Skill Creator](https://github.com/anthropics/skills/tree/e4bb5d960d87126ff3b3a8af1a104b7db67560ba/skills/skill-creator), revision `e4bb5d960d87126ff3b3a8af1a104b7db67560ba`, under Apache-2.0. Agent Sync adapted the entrypoint for its host-neutral workflow, extended the viewer to show nested deliverables, and preserved recorded token usage in the benchmark. It moved the viewer into `scripts/` and `assets/`, renamed the upstream license file to `LICENSE`, and constrained how the viewer reads and renders trial files.
