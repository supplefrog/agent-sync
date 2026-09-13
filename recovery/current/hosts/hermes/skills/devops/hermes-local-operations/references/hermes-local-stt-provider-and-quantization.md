# Hermes local STT provider and faster-whisper quantization

Use when the user wants free speech-to-text, asks whether OpenAI OAuth can be used for STT, or needs to know whether a local machine can run `large-v3`.

## Durable facts

- Hermes `stt.provider: openai` uses the OpenAI Speech API and reads `VOICE_TOOLS_OPENAI_KEY`; OpenAI Codex OAuth/device-code credentials are for LLM routing and do not satisfy STT/TTS OpenAI API auth.
- Hermes local STT uses faster-whisper when available. Current local model load path is effectively:

```python
WhisperModel(model_name, device="auto", compute_type="auto")
```

- `compute_type="auto"` can still select a quantized mode. Do not guess from GPU model alone; instantiate the model and inspect the inner CTranslate2 model.

## Verification probes

Check installed runtime and CUDA visibility:

```bash
python - <<'PY'
import importlib.util
for m in ['faster_whisper','ctranslate2','torch']:
    print(m, bool(importlib.util.find_spec(m)))
try:
    import ctranslate2
    print('ctranslate2', ctranslate2.__version__)
    print('cuda devices', ctranslate2.get_cuda_device_count())
except Exception as e:
    print('ctranslate2 error', repr(e))
PY
```

Check actual faster-whisper device and quantization for a model:

```bash
python - <<'PY'
from faster_whisper import WhisperModel
m = WhisperModel('base', device='auto', compute_type='auto')
print('device:', m.model.device)
print('compute_type:', m.model.compute_type)
PY
```

Replace `base` with `large-v3` only if the user accepts the model download and has enough disk. On a 6 GB RTX 3060 Laptop GPU, `auto` may resolve to `cuda` + `int8_float16`, which is quantized GPU inference.

## Practical guidance

- `large-v3` is usually a quality improvement, not a speed improvement. If `base` is already slow on `cuda/int8_float16`, `large-v3` will almost certainly be slower.
- Set `stt.local.language en` when the user mostly speaks English; skipping auto language detection can reduce overhead.
- Try `small` or `medium` before `large-v3` when balancing speed and quality.
- Check disk before first `large-v3` run. Model cache downloads can consume several GB; low free space is a real blocker even when CPU/GPU/RAM are sufficient.

Config commands:

```bash
hermes config set stt.enabled true
hermes config set stt.provider local
hermes config set stt.local.model medium   # or small / large-v3
hermes config set stt.local.language en
```

OpenAI cloud STT, if the user accepts paid API-key usage:

```bash
hermes config set stt.enabled true
hermes config set stt.provider openai
hermes config set stt.openai.model gpt-4o-transcribe
# add to hermes config env-path file:
# VOICE_TOOLS_OPENAI_KEY=sk-...
```
