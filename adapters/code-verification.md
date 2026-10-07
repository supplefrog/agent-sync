# Codex access to native code verification

Use for nontrivial local code verification, simplification or readiness review before commit, push, PR handoff or release. A review request permits inspection and verification; edits need their own authorized scope. Skip greenfield design, broad debugging and tiny obvious changes with a direct check.

The procedure owner is Hermes's native `skills/software-development/code-change-verification/SKILL.md`. Read its full current body rather than inferring the procedure from its description or reproducing it here. Codex can read it as a file; Hermes uses its normal native skill loader. This adapter establishes source access, not a second verifier or a new skill admission.

## Resolve and load the source

1. Resolve Agent Sync from `source_snapshot` in the shared skill root's `.agent-signal-fleet.json`, stripping `render/fleet`.
2. Prefer the intended Hermes profile's home from its explicit launch configuration or `HERMES_HOME`, expanding user/environment syntax. Otherwise use the native default: `%LOCALAPPDATA%/hermes` on Windows (with the user's `AppData/Local/hermes` fallback), or `~/.hermes` elsewhere; respect `HERMES_DATA_DIR_SUFFIX` when set. Verify the path rather than assuming `.hermes` is active. Codex cannot observe another process's context-local profile override; resolve a material profile ambiguity before claiming active-native identity. Do not import runtime/plugin modules merely to find a text file or bypass a disabled native capability. Read the verifier at the relative path above and retain its source path and version or hash in substantial review evidence.
3. If the native source is absent or inaccessible, use Agent Sync's captured `recovery/current/hosts/hermes/skills/software-development/code-change-verification/SKILL.md` and its captured dependency tree. Label it as a recovery snapshot, including revision/hash; it is available guidance, not proof of the newest upstream or active native version. If neither source is available, report the missing verifier and continue checks whose evidence is independently sufficient; do not claim its gate ran.

Keep relative references within the selected native or captured tree. If a required dependency is unavailable, report that gap rather than silently treating a partial read as the whole procedure. Reading live source afresh follows local native updates; recovery changes still use the checked capture path. A path alone promises no upstream update service.

## Follow the conditional dependencies

- New or materially changed tests => read sibling `test-driven-development/SKILL.md` and apply its test-validity gate, including independent expectations and relevant failing controls. The base verifier's metadata alone does not load it.
- A merge/cherry-pick, durable lifecycle, structured contract, event integration or another specialist risk => read sibling `software-verification-workflows/SKILL.md`, then the applicable routed reference and linked controls. Its merge and structured-contract branches supplement the base verifier. Do not load every branch for an ordinary diff.
- A named dependency outside the three siblings => resolve the exact native/captured owner referenced by the router. Host-only operations remain with their host; reading guidance grants no native tool or deployment permission.

Use the existing standing model and fresh-review contract for delegation. Preserve risk-scaled production-path checks, test validity, evidence-bound parent acceptance and separate ship verdicts from work state and publication authority. Do not replace those mechanisms with an always-on reviewer swarm or a passing-test count.

## Evidence boundary

Verify that the chosen source and conditional dependencies are readable before claiming availability. File reads and generated-overlay checks prove source access and installation; they do not prove natural triggering, better outputs, semantic merge success or cross-host behavioral parity. A claimed quality improvement needs an appropriate comparable task, not this adapter's existence.
