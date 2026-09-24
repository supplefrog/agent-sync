# Portable tools and fresh-workspace operation

Use this when a complex video needs saved evidence or an offline learning page. Resolve `SKILL_DIR` to the directory of the loaded skill; none of these commands depends on a previous project. Put this source's outputs in its own workspace. The tools acquire and present evidence; they do not choose the lesson, transcribe speech, verify scientific claims or certify learning.

## Prerequisites and source packet

Inspect available commands/modules before use. Capture/readiness requires Python, FFmpeg and FFprobe. The optional reader uses `markdown`, `beautifulsoup4` and `Pillow`; its browser checker uses `websockets` plus an installed Chromium browser. Missing packages, models, browser binaries or paid services require their applicable authorization; never silently install them.

Acquire the source through the appropriate source-access workflow. Caption fetching remains with `youtube-content`; clean VTT with this skill's `scripts/clean_vtt.py`. Retain original-language captions and their clock. With local recordings, preserve originals and work with bounded evidence. OCR and ASR are optional, separately verified evidence channels—not built-in capabilities of these helpers.

For an acquired clip, record original interval, local duration, source identity, any preroll/clock uncertainty and required channels, then run [source_ready.py](../scripts/source_ready.py):

```text
python SKILL_DIR/scripts/source_ready.py WORK/segment.mp4 --duration EXPECTED_SECONDS --min-height REQUIRED_HEIGHT --receipt WORK/source-ready.json
```

Add `--require-audio` only when sound is needed. This validates clips up to ten minutes and checks decoded video and required audio endpoints independently, not semantic fidelity. Required sound needs speech/audio review beyond detecting an audio stream. A failed receipt blocks dependent work. Readiness and capture accept self-contained MOV/MP4, Matroska/WebM, AVI, MPEG/TS, FLV and Ogg media with local-file access only; playlists and other reference demuxers are rejected because their referenced bytes are not bound by the source identity. Receipt writes reject source aliases and atomically replace the receipt without truncating a shared inode.

## Readable visual evidence

Choose timestamps from the instructional question and source review—not a screenshot quota. Start with the setup; expand around meaningful transitions or ambiguous intermediate states. Capture a small candidate batch with [capture_frames.py](../scripts/capture_frames.py):

```text
python SKILL_DIR/scripts/capture_frames.py WORK/segment.mp4 --output WORK/capture-01 --times 0 8.5 14 --source-origin ORIGINAL_START_SECONDS --reason "Compare the setup, changed setting and result"
```

The output directory must be new. Defaults bound each invocation to 12 distinct timestamps, 1920px maximum width without upscaling, 50 MB of images and 60 seconds per seek. Large original recordings may be addressed directly; these captures do not establish readiness of an entire long recording. A source timestamp is **requested local seek + supplied origin**, not a decoded exact timestamp. Packet gaps and keyframe alignment remain relevant. The manifest records no actual source time when it cannot establish one.

Inspect the native saved images; record observed labels, relationships, teaching use and remaining ambiguity separately. OCR is a reading aid, not proof. If stills cannot represent motion or audio, inspect a bounded sequence with an available tool or leave the gap explicit. This helper is not the experimental automatic scene detector and makes no instructional-recall claim.

## Optional offline reader

Write the lesson as ordinary Markdown with a single `#` title, meaningful headings, local image paths with useful alt text, and normal source links. An italic-only paragraph immediately after an image becomes its caption. Native answer reveals may use `<details markdown="1"><summary>Check your answer</summary>` and a blank line before the answer. No fixed headings, number of images or exercises are required.

```text
python SKILL_DIR/scripts/render_lesson.py WORK/lesson.md WORK/reader-v1.html
python SKILL_DIR/scripts/check_reader.py WORK/reader-v1.html --output WORK/render-check-01
```

The [renderer](../scripts/render_lesson.py) embeds local images, [reader.css](../assets/reader.css) and [reader.js](../assets/reader.js) into one HTML file. Images retain their encoded bytes and MIME from content. Images must resolve within the manuscript directory; remote or escaping image paths are rejected. Source HTML is sanitized; SVG is limited to static drawing/text elements with no processing instructions, animation, scripts or external references. Existing outputs are never overwritten. Revise the manuscript and choose a new output filename, then keep the accepted version. Do not edit generated HTML as the maintained source.

This is a restrained, optional starting point—not a prescribed style or an automatic lesson writer. The frontend owner and current user brief govern presentation. The [browser checker](../scripts/check_reader.py) runs offline in an isolated browser profile, records the exact HTML hash and screenshots, and checks image decoding, narrow/wide layout, anchors, keyboard reveals, enlargement and focus restoration. `--browser PATH` selects an installed Chromium if discovery fails. Inspect its screenshots yourself. Mechanical passes do not establish comprehension, factual accuracy, full accessibility or user approval.

## Preservation and handoff

Keep one compact source/coverage record per task: source identity and channels, scope and timestamp mapping, useful claims/examples/visuals, their destinations or exclusions, and unresolved gaps. Keep review/correction history outside the learner-facing opening. Give a worker validated inputs and a teaching outcome; acquisition and acceptance remain with the parent. User approval of a prototype's appearance does not establish whole-source coverage.

An editorial rebuild should preserve the source evidence and use one maintained manuscript. Compare load-bearing concepts, source-image identities and citation destinations before and after rewriting. Re-run checks affected by a changed artifact, not every extraction stage.

## Maintenance probes

```text
python SKILL_DIR/scripts/test_source_ready.py
python SKILL_DIR/scripts/test_portable_tools.py
```

The probes are [readiness tests](../scripts/test_source_ready.py) and [portable-tool regression tests](../scripts/test_portable_tools.py). After changing tools, use [test_portability_smoke.py](../scripts/test_portability_smoke.py) with `CLIP --duration SECONDS --output NEW_CHECK_DIRECTORY` to copy this skill into an unrelated temporary location and run the actual CLIs from a fresh workspace with valid media, a plain article and an illustrated article. Exercise at least one blocked-input case. Remove temporary media/profiles after recording results. Synthetic fixtures establish mechanics; an existing real packet establishes that packet's path. Neither alone supports a general arbitrary-video quality claim.
