# Current native skill selector

This narrow successor records the reviewed selector applied to native Hermes commit `9fe737aef2dd18a351dff3c4de608d63879a6524` (runtime reports 0.21.4). It does not install the historical whole-file guidance bundle in the parent directory. The two targets and exact baseline/applied hashes are in `manifest.json`; source is MIT under [the parent license](../LICENSE).

The ordinary catalog loads skills for explicit requests or material specialist/local value, not partial topic overlap. Duplicate maintenance coaching is removed from this catalog only: standing instruction-authoring routing, tool guidance, authoring tools and safety remain. Catalog discovery, organization collisions, ordering, compact categories and the one-shot path remain native.

## Restore and rollback boundary

This is a manual native prerequisite, not fleet content or automatic updater enrollment. Require the recorded native revision and exact hashes of both baseline targets before applying. Initialize a disposable Git fixture, populate its two targets from the recorded revision, and check/apply with `git -c core.autocrlf=false apply` to preserve the recorded LF bytes. Compare both complete resulting hashes with the manifest; stop on drift. Apply only these hunks to the reviewed native owner using the same line-ending setting, verify both hashes and rerun the named checks. Do not replace newer whole files, reset the native worktree, or absorb unrelated updater/delegation/browser edits.

Rollback likewise requires the exact applied hashes, a successful reverse check on a copy, and resulting baseline identities. If unrelated edits affect either target, rebase/review instead. A fresh Hermes process is needed for changed imported prompt-building code; do not restart active user work automatically. Existing conversations retain injected instructions. A runtime update must revalidate this patch; automatic survival is not claimed.

## Verification and limits

- The actual public prompt-builder entry point passed baseline/candidate comparison in fresh disposable homes with no inference: catalog contents and one-shot output unchanged; repeated output stable; compact nested categories, interactive authoring tools and safety guidance preserved.
- The native canonical runner passed 67 tests in both baseline and candidate runs: `tests/agent/test_external_skills.py`, `test_project_skills.py`, `test_org_skill_namespace.py`, `test_oneshot_footprint.py`, and `test_skills_guidance_content_filter.py`, using `HERMES_TEST_FILE_RETRIES=0 bash scripts/run_tests.sh` with `-j 2`.
- Parent repeated the candidate public-entry-point probe and fixture apply/reverse checks. The exported patch needed a final line terminator, and inherited Git CRLF conversion initially changed file hashes; preserving LF makes both resulting hashes match the tested candidate exactly.
- The broader baseline `tests/agent/test_prompt_builder.py` cannot collect on Windows because an existing test calls `os.geteuid()`. It is not reported as passing. No model-quality improvement, backend identity, cross-provider parity, or active-process restart is claimed.
