# Hermes native prompt guidance

This recovery bundle records the installed guidance policy for Hermes native prompt construction. It changes only `hermes-agent/agent/prompt_builder.py`: skills load when explicitly requested or materially useful, and reusable skill writes require authorized durable work rather than ordinary task completion.

The native base is commit `59d330fd15a692b439219e505bc704fcde0b2b6f`. Before applying, require the exact baseline target and all seven source-binding hashes in `manifest.json`. Stop on drift. Validate `guidance.patch` against an exact baseline copy and confirm its normalized text equals the bundled candidate; then install the bundled candidate bytes and require the candidate SHA-256. Git patching alone can normalize line endings and is not the byte installer.

Rollback requires the native target to match the candidate SHA-256. Reverse-check the patch and its normalized output, restore the bundled baseline bytes, and require the baseline SHA-256. Start a fresh Hermes process after apply or rollback because existing processes may retain imported prompt-builder code.

The patch does not install Hermes or its dependencies, restore credentials or state, or establish generic provider compatibility. The retained candidate comment records its Astra evaluation context and historical Anthropic OAuth context; it is not a generic Anthropic or cross-provider claim.

The included MIT license is copied byte-for-byte from the installed Hermes source, copyright 2025 Nous Research. Selection evidence is recorded separately in `evidence/hermes-native-guidance-selection.json` so recovery files remain focused on source identity and restoration.
