# Hermes-only recovery verification

## Result and scope

The existing Agent Sync recovery path can restore the reviewed curated Hermes setup without configuring Codex or OMP. This is a public-safe setup snapshot, not a machine image or runtime installer.

The disposable Windows receiving-home test exercised real `recovery.bootstrap(..., hosts=["hermes"])`, native Hermes version readback, fleet apply, file restore, postflight, and a fresh Hermes-Python process:

| Check | Observed result |
| --- | --- |
| Dry-run target filesystem changes | None |
| Applied Hermes recovery artifacts | 932 in the final end-to-end probe |
| Required selected-host readback | Passed; Hermes entries only |
| Repeat restore changes/conflicts | None |
| Codex/OMP homes created | Neither |
| Private state copied | None of the tested session, memory, auth, environment, database, log, or cache targets |
| Fresh visible skill names | 69, identical to fresh source-host discovery; no missing or unexpected names |
| Restored LCM registration | 15 tools, four hooks, bundled `hermes-lcm` skill |
| LCM shutdown | SQLite file cleanup succeeded on Windows after unload callbacks |

The receiving fixture preinstalled only the required native link from its Hermes plugin directory to this checkout's `integrations/hermes/routed-delegation`. Runtime/dependency installation and account authentication were not automated. No model inference or conversation creation was used for the restore/registration probe.

## Preserved state

- The final inventory declares 101 Hermes-local packages and 859 package files. Package restoration compares every declared file with the expanded snapshot and parses restored Python files. Rewritten MIT PowerPoint support and the local career-positioning workflow are included; PowerPoint's repacked binary dependency and rendering runtime remain separate prerequisites documented in [native recovery](native-skill-recovery.md#advanced-powerpoint-dependency-limit).
- The full disabled-skill list, plugin selections, plugin override controls, and bundled-origin metadata were checked independently of content. Capturing disabled material does not enable it.
- LCM contributes 70 source/manifest/license/bundled-skill files. The original patch manifests remain historical byte-hash evidence; recovery verifies canonical public text and portable path expansion.
- Shared skills retain their canonical Agent Sync owner. Host-local packages remain native recovery artifacts rather than newly admitted fleet skills.
- Restricted PowerPoint content and the inventory's other exclusions are not public recovery payloads. Refer to `recovery/hermes-local-inventory.json` for the exact per-file exclusions and provenance.

## Regressions caught and corrected

1. Required native prerequisites previously failed after target writes. Selected bootstrap now checks them before fleet/config application.
2. Native CLI initialization wrote `SOUL.md` and an update marker during dry-run. Version checks now use disposable homes. Hook absence is checked directly in the selected config; curator state is checked against the recovery settings artifact.
3. A selected skill's references to an uninstalled host expanded to empty paths. They now rebase to target-local conventional paths without reading or creating those homes.
4. Default restore incorrectly demanded all supported hosts for a one-host policy. It now retains the policy's original host scope when no selector is supplied.
5. Explicit mounted-source capture is read-only. Regression tests cover unlisted/nested links and attempted writes through a mounted owner, including the force-text path.

Tests also cover whole-snapshot validation before host filtering, unknown selectors, conflict handling, target-local skill placement, repeated restore, preservation of unknown/private target config, and atomic file-write rollback.

The final full Agent Sync suite returned **556 passed, three skipped, 277 subtests passed** with `python -m pytest tests -q`. An initial relocated-test bytecode failure was resolved by removing only the stale compiled test cache; the trusted source-pinning guard was not weakened.

Publication of the expanded snapshot exposed Windows' command-line length limit in both Git staging and index reconciliation. The publisher now sends exact literal paths as NUL-delimited standard input. A real temporary-repository/remote regression reproduced `WinError 206` before the fix and passed afterward with a file list exceeding 32,767 command-line characters, including a Unicode/bracketed filename. All 20 sync-completion tests passed; the isolated index, exact reviewed scope, and remote readback checks remain intact.

## Automatic learning audit

Automatic background review remains enabled. Source inspection found dispatch-side tool restrictions, skill-management preflight, ownership/provenance controls, write-approval staging, mutation ledger, and rollback paths. This is source/test evidence, not an independent adversarial security certification.

The focused Hermes safeguard run returned **82 passed, three skipped, one deselected**. The omitted symlink test required Windows symlink privilege. Two additional ledger tests initially failed because their assertions assumed LF bytes and forward-slash paths. A disposable copy of those tests, changed only to hash actual file bytes and normalize path separators, returned **two passed**. No Hermes production safeguard was modified to obtain that result.

## Limits and receiving-host instructions

- Use `python tools/recovery.py bootstrap --host hermes` for preview and add `--apply` only after reviewing prerequisites/conflicts. A custom `--root hermes=PATH` is supported.
- Install the native Hermes runtime and required dependencies locally. Register the routed-delegation link at its canonical checkout. Apply applicable native runtime patch records explicitly; optional missing patch prerequisites remain visible in readback.
- Windows-specific executable integrations require receiving-agent adaptation on Linux/macOS. The real end-to-end probe was Windows, not a cross-OS execution claim.
- The stock LCM Plugin Doctor run still has manifest/capability warnings and a Windows temporary SQLite cleanup failure. That doctor failure remains unresolved. The fresh restored-plugin probe above verified registration with the explicit tool-forwarding capability and unload callbacks; it does not claim that the unmodified doctor itself passed.
- Restart Hermes after restoring startup-read settings, plugin source, or runtime patches. Existing processes may keep old imported modules.
- Keep existing local conflicts for review. Do not use force-text to overwrite an unrelated recipient customization or write through linked native source.
- The file-restore phase rolls back its own failed writes; fleet apply plus file restore is not represented as one global disk transaction. Re-run preview after interruption.

Transient clone directories, native-version homes, and Windows-normalized ledger fixtures are verification aids, not recovery content. No sessions, memories, credentials, runtime databases, or raw transcripts belong in the public repository.
