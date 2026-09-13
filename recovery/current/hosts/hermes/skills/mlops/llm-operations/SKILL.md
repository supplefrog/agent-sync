---
name: llm-operations
description: Use for model discovery, inference, and ML tracking.
---
# LLM operations

Route by lifecycle stage and combine branches when needed.

## Routing
- Hub discovery and transfers: `references/huggingface-hub/SKILL.md`
- Local GGUF and llama.cpp inference/server: `references/llama-cpp/SKILL.md`
- Experiment tracking, artifacts, sweeps, and registry: `references/weights-and-biases/SKILL.md`

## Shared workflow
1. Establish model identity, revision, license, task, hardware, memory, and privacy constraints.
2. Prefer pinned revisions and record exact filenames, quants, commands, and configuration.
3. Verify credentials and CLIs without exposing secrets. Credential presence is not validity; use one bounded provider request when the distinction matters.
4. Treat catalog visibility as discovery, not proof of account entitlement. Check account-specific quota/limits, distinguish historical peak-versus-limit dashboards from instantaneous remaining capacity, and confirm the exact API model ID in provider documentation.
5. Run a bounded smoke test before expensive downloads, serving, training, sweeps, or production configuration changes.
6. Capture versions, seed, hardware/backend, parameters, and hashes when needed.
7. For comparative evaluations, keep the model/revision fixed across systems; label a strongest-current-model lane as practical configuration, not backend-quality evidence.
8. Report actual execution and distinguish local checks from remote assumptions.

Each provider guide remains a complete nested package under `references/<provider>/`.