# Audiovisual evidence and source figures

Use when a lesson depends on recordings, imperfect transcripts, slides, figures or demonstrations. These are evidence boundaries, not a requirement to exhaustively decode every frame.

## Keep the channels distinct

Record what was available, acquired, inspected and incorporated for each channel: captions/ASR, perceptual audio listening, slide text, slide images, recording frames and clip sequences. A count of files or segments establishes inventory only. State the sampled scope and unresolved gaps without implying complete audiovisual understanding.

Review the selected scope against the original clock. Validate segment bounds, missing intervals and repetitions before citing. Preserve repairs as flags; padding, resampling or timestamp clamping does not recover missing evidence. On multilingual speech, inspect whether language changes were captured; a multilingual setting alone is not an accuracy test. Use targeted listening where a consequential spoken claim remains unclear, or label it unresolved when listening is unavailable.

Slides and recordings can differ. A companion page may recover a readable diagram but cannot establish that it was shown, animated or explained at an assumed time. Record the page reference separately from approximate recording seeks. Inspect before/during/after states when change conveys the mechanism; do not invent unseen motion or dialogue.

## Acquisition readiness and bounded recovery

The parent owns acquisition before lesson-worker dispatch. Verify the resolved extractor binary/version, decoder and runtime, then fetch a short clip from the intended interval and decode it before fetching the bounded work packet. Cache the verified packet for the worker. Fail closed on missing media, decoder errors, inadequate duration or unreadable required screen content; metadata/caption success cannot override a failed video gate. Record original source bounds separately from local presentation timestamps and keyframe preroll.

Use wall-clock, network and storage limits; kill the acquisition process tree on timeout and do not pass partial files to workers. Retry only when evidence supports a changed method. A format-unavailable error calls for inspecting current formats, not blindly repeating a stale selector. Select original-language audio explicitly when auto-dubbed tracks exist. Do not use account cookies or bypass access controls without the applicable authority.

For FFmpeg remote-MP4 seeks that stall after HTTP access succeeds, inspect a bounded debug log. Some builds drain a large open-ended response during a soft seek; a network read timeout does not stop an actively progressing drain. If `ffmpeg -h protocol=http` exposes the options and a range probe returns usable partial content, test input options `-request_size 1048576 -initial_request_size 1048576` on a short clip. With yt-dlp, pass them through `--downloader-args 'ffmpeg_i:-rw_timeout 15000000 -request_size 1048576 -initial_request_size 1048576'`. This is a conditional transport fix, not a generic cure for 403s. Verify the selected packet's duration and decoding afterward; redact expiring signed media URLs from durable diagnostics.

For cached clips up to ten minutes, run `python scripts/source_ready.py CLIP --duration SECONDS --min-height PIXELS --receipt RECEIPT.json`, adding `--require-audio` when sound is required. Require exit 0 in the dispatch chain, not merely the existence of a receipt from an older attempt. Test missing/corrupt/truncated inputs as well as a valid clip. Recheck source identity when reusing an earlier receipt.

## Select meaningful tutorial states

Preserve a visual when it carries a relationship, sequence, comparison or example that prose does not adequately retain; naming its topic is not coverage. For procedural tutorials, map each substantive step to its starting state, action/target, relevant settings or values, and observable result. Capture readable before/after states and transient menus, selections or intermediate states when needed to reproduce the action. If motion matters, inspect a bounded sequence rather than presenting one still as the whole demonstration.

Use coarse scene detection only to find candidates. Keyframe-only decoding, sparse time sampling, tiny grayscale frames and whole-frame difference thresholds can miss brief events, color-only changes and small but decisive UI updates. Lecturer movement can produce irrelevant candidates. Combine visual changes with demonstrated-step boundaries and speech cues; review visually active intervals even when narration is silent. Inspect bounded candidate intervals more densely with ordinary frame decoding and readable resolution; compare relevant regions when global differences hide local changes. Do not mask a screen region unless it is irrelevant for that source.

Verify the selection method against manually reviewed examples from the actual source: a small meaningful change, a brief intermediate state, a substantial transition and irrelevant motion where present. Synthetic probes establish mechanism limits, not source-level recall. Misses require adjusted sampling/regions and reinspection of affected intervals, or an explicit coverage gap. No universal sampling interval or scene score proves that every teaching step was found.

Before delivery, trace each substantive demonstrated step to its explanation and visual evidence or a justified text-only treatment. Distinguish intentional redundancy from an uninspected or missed state. This does not require screenshots for talking-head passages or actions adequately taught without them.

## Recover the best real asset

1. Inspect the supplied PDF/vector/native image before cropping a recording. Extract only the useful objects or selected pages; do not make a bulk frame dump.
2. Maintain a compact asset manifest: source ID, page/object or frame locator, teaching purpose, adopted placement or exclusion, format/dimensions and any uncertainty. Deduplicate by actual content and role, not by filename alone.
3. Inspect chart axes, legends, panel names and units at native and final reader size. A contact sheet may reveal layout while leaving labels unresolved. Do not normalize labels into familiar but different constructs.
4. Preserve native encoded bytes when re-encoding adds no benefit. Detect raster MIME from content rather than extension. Preserve aspect ratio and embedded credits; provide meaningful alternatives and captions.
5. Put load-bearing source figures next to their explanation. Optional evidence links supplement teaching; they do not replace an illustration the learner needs. Prefer fitted inline figures with click/keyboard enlargement for dense stills; keep wide-table scrolling local. Verify labels in the detail view and preserve aspect ratio, Escape and focus restoration. Do not hide inaccessible content through global overflow clipping.
6. If native recovery is insufficient, redraw only verified structure/labels and identify the redraw. Generated illustrations may explain an idea when authorized; they must not reconstruct unknown source data, exact axes, numbers, quotations or speaker-specific evidence. No model name guarantees availability or source fidelity.

A picture of an apparatus, stimulus, outcome table and explanatory cartoon supplies different evidence. Describe what is actually visible before interpreting what it demonstrates. Reconcile conflicting annotations against the original, including plausible-looking corrections from reviewers.

## Teach and verify

For each retained figure, explain what to notice, the relationship it clarifies and the inference it cannot establish. Separate original source content from the added reading guidance and verified external context. Keep qualitative curves qualitative when scales cannot be read.

Check the built artifact, not just the extraction script: correct source bytes/MIME, placement, source captions, image loading, actual reader-size legibility, links and relevant interactions. Report automated consistency checks separately from visual inspection, listening and scientific claim verification. Evidence tables and test totals cannot certify comprehension.

Keep source media read-only. Reuse available evidence; bound temporary audio/rendering and check free space before substantial work. Do not sacrifice useful final imagery merely to minimize a small file, but remove superseded generated intermediates after verifying their replacement. Preserve original evidence and necessary audit history.
