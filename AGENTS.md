# Repository rules

Use `capability-curator` before adding, installing, replacing, or materially changing a skill or persistent instruction surface.

Use `surface-convergence` when a persistent behavior targets multiple agents, adds a host, or may have drifted after host changes. Optimize semantic parity, preserve useful native differences, and record unsupported mappings explicitly.

Keep `skills/` compatible with the Agent Skills standard. Put host-specific behavior in adapters, not portable skill instructions.

Do not promote a capability without a checked-in suite and a current evidence summary showing baseline-versus-candidate results. No change is preferable to an unproven change.

Treat `contracts/surface-matrix.json` as the cross-host behavior contract and `evidence/findings.json` as the public-safe findings and contradiction ledger. Never erase contradictory evidence merely to present a unified result.

Keep the repository small: extend or replace an existing capability when its scope substantially overlaps; do not add aliases or speculative skills.

Do not delegate research, architecture, evaluation design, or synthesis to a fixed weak worker route. Use task-tiered routing: main model low for substantive work, medium for verification, high for refutation or synthesis; weak models are for mechanical checks only.

Never commit generated run transcripts, credentials, private paths, or third-party content without a compatible license.
