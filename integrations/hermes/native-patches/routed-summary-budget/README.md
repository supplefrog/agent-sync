# Routed delegation native summary seam

Historical patch: the current canonical plugin also adapts the tested split-native interface without this patch. See the [current compatibility contract](../../../../skills/openai-delegation-route-research/references/hermes-direct-v3.md). The recorded native patch remains an optional, unresolved recovery prerequisite; do not apply it during router/skills sync or replace its expected hashes with unreviewed live bytes. The procedure below applies only when separately restoring this exact historical pair.

The canonical plugin remains in `integrations/hermes/routed-delegation`. This licensed delta adds a backward-compatible shared summary-count parameter to Hermes's native result helper; it does not create another router or summary policy.

Recovery requires the native Hermes checkout/dependencies at the base revision in `manifest.json`. Verify the helper's before hash, run `git -c core.autocrlf=false -c core.whitespace=cr-at-eol apply --check <absolute-path-to-repair.patch>` from that checkout, then apply with the same Git options and verify the after hash. These options keep ambient Windows newline conversion from changing the reviewed bytes. Preserve unrelated edits. A future remote's availability of the historical base revision is not guaranteed.

Install the native helper first. Then expose the paired canonical `integrations/hermes/routed-delegation` directory at the Hermes profile's `plugins/routed-delegation` path, preserving the supported native plugin registration. A link or managed copy must resolve to the recorded source bytes. Start a fresh Hermes process. Existing processes may retain old imports. The plugin deliberately refuses the incompatible old native summary seam.

Exact file readbacks in `host-deltas.json` check both sides. Missing or different native bytes fail recovery verification. Declarative restore does not install the host, its dependencies or this link. To reverse this exact repair, first remove/restore the new canonical plugin through its owner, then verify the native after hash and reverse-apply the checked patch; never overwrite unrelated changes.

Full raw results are retained. Display summaries share the native batch allowance and spill in the child's captured launch profile. Native summary floors/footer overhead and the separately disclosed reset/accounting limitation remain; no strict whole-context token ceiling or general model-quality gain is claimed.
