# Model-scoped skills

LeanREA stays outside the shared skill directory. Native adapters add its
discovery entry only when the current request's exact provider/model pair is
recorded as open-weight. The skill body loads on demand for an applicable task;
it is not inserted into every open-weight request.

| Host | Discovery and loading |
| --- | --- |
| Hermes | Request-time catalog and the existing `skills_list` / `skill_view` interface |
| OMP | Request-time catalog and `model_skill_view`, with native skill settings retained |
| Codex | Withheld; current documented skill settings provide enable/disable controls rather than a supported live model predicate |

The policy is [skill-model-policy.json](../contracts/skill-model-policy.json).
The [model weights index](../contracts/model-weights.json) records exact routes
from the public [Models.dev API](https://models.dev/api.json), with acquisition
date and source digest. This is catalog evidence, not an attestation of a remote
server's implementation. Interface names, endpoint vendors, fuzzy matches and
unknown model aliases do not grant access. New unknown routes remain hidden
until their metadata is reviewed and the index is refreshed through normal
source synchronization.

The shared registry remains `blocked` for LeanREA: it controls universal fleet
distribution, while the separate policy controls request-local access. No
shared folder is moved or rewritten when a model changes. Concurrent sessions
can therefore make different eligibility decisions safely.

Hermes keeps native tool authorization, approval and disabled-skill checks. OMP
reads its effective `skills.enabled`, include/ignore patterns and per-skill
disabled entries on each request and load. Its adapter also respects explicit
CLI skill controls. Missing or malformed policy, unknown metadata and missing
native settings support withhold the restricted entry.

Adapter-generated catalog entries, list rows and loaded bodies are marked.
They are removed from the outbound copy for an ineligible model, including
after a model or settings switch. Stored history and unrelated user text are
preserved. This filters managed discovery and loading; it does not isolate
filesystem access or remove analysis previously derived from a skill. Use a
fresh conversation when complete context separation is required.

The Python policy engine is [model_skills.py](../tools/model_skills.py).
Host glue lives in [the native adapters](../integrations/model-skills/).
Recovery carries complete native adapter packages. Existing agent processes
need one reload or restart to discover the new adapter; subsequent model
switches require no folder changes or restart.

The [qualification record](../evals/results/model-scoped-skills-20261103.json)
separates functional checks from deployment. Native registration, RPC model
switching and loopback fake-provider requests verify the mechanism without
claiming genuine model inference or comparative output quality. Google and
Bedrock payload checks use their version-bound native source shapes. Native
loading and the final installation state require their own readback.
