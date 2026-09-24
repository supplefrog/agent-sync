"""Validate a bounded local video before dispatch; no network or worker launch.

Exit 0 means decodable media, NOT source fidelity or lesson acceptance.
Requires ffmpeg and ffprobe on PATH. A failed attempt replaces stale readiness.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile

# Reject playlist/reference demuxers before they can open nested resources.
# MOV external data references remain disabled by FFmpeg's default demuxer policy.
MEDIA_INPUT_OPTIONS = ['-protocol_whitelist', 'file', '-format_whitelist',
                       'mov,matroska,webm,avi,mpegts,mpeg,flv,ogg']


def write_receipt(path, value):
    """Replace the directory entry; never truncate a potentially aliased inode."""
    path = Path(path)
    name = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                         prefix='.readiness-', suffix='.json', delete=False) as output:
            name = output.name
            json.dump(value, output, indent=2)
        os.replace(name, path)
    finally:
        if name and Path(name).exists(): Path(name).unlink()


def check(media, duration, min_height=1, require_audio=False, max_bytes=250_000_000):
    media = Path(media).resolve()
    if not math.isfinite(duration) or not 0 < duration <= 600:
        raise ValueError('Expected duration must be finite and within 600 seconds; validate larger sources in bounded packets')
    before = media.stat()
    if not 0 < before.st_size <= max_bytes:
        raise ValueError('Empty media or storage budget exceeded')
    probe = subprocess.run(['ffprobe', '-v', 'error', *MEDIA_INPUT_OPTIONS, '-show_format', '-show_streams', '-of', 'json', str(media)], capture_output=True, text=True, timeout=20, check=True)
    data = json.loads(probe.stdout)
    video = next((s for s in data['streams'] if s['codec_type'] == 'video'), None)
    audio = next((s for s in data['streams'] if s['codec_type'] == 'audio'), None)
    if not video or video.get('height', 0) < min_height:
        raise ValueError('Missing video or insufficient image height')
    if require_audio and not audio:
        raise ValueError('Required audio unavailable')
    for stream in [video] + ([audio] if require_audio else []):
        actual = float(stream.get('duration', data['format'].get('duration', 'nan')))
        if not math.isfinite(actual) or not duration - 0.15 <= actual <= duration + 1:
            raise ValueError('Media duration does not cover the expected bounded interval')
    coverage = {}
    frames = 0
    for kind in ['video'] + (['audio'] if require_audio else []):
        mapping = '0:v:0' if kind == 'video' else '0:a:0'
        decode = subprocess.run(['ffmpeg', '-v', 'error', '-nostdin', '-xerror', '-err_detect', 'explode',
                                 *MEDIA_INPUT_OPTIONS, '-i', str(media), '-map', mapping,
                                 '-progress', 'pipe:1', '-f', 'null', '-'],
                                capture_output=True, text=True, timeout=180, check=True)
        progress = dict(line.split('=', 1) for line in decode.stdout.splitlines() if '=' in line)
        endpoint = float(progress.get('out_time_us', '0')) / 1_000_000
        if not math.isfinite(endpoint) or not duration - 0.15 <= endpoint <= duration + 1:
            raise ValueError(f'Decoded {kind} did not cover the expected bounded interval')
        coverage[kind] = endpoint
        if kind == 'video':
            frames = int(progress.get('frame', '0'))
            if frames <= 0: raise ValueError('No video frames decoded')
    digest = hashlib.sha256()
    with media.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            digest.update(block)
    after = media.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ValueError('Source changed during validation')
    return {'status': 'media_ready_not_semantically_reviewed', 'media': str(media), 'bytes': after.st_size, 'mtime_ns': after.st_mtime_ns, 'sha256': digest.hexdigest(), 'expected_duration': duration, 'video': {'codec': video['codec_name'], 'width': video['width'], 'height': video['height'], 'duration': video.get('duration')}, 'audio_present': bool(audio), 'full_decode_passed': True, 'decoded_frames': frames, 'decoded_end_seconds': coverage, 'perceptual_review': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('media', type=Path)
    parser.add_argument('--duration', type=float, required=True)
    parser.add_argument('--min-height', type=int, default=1)
    parser.add_argument('--require-audio', action='store_true')
    parser.add_argument('--max-bytes', type=int, default=250_000_000)
    parser.add_argument('--receipt', type=Path, required=True)
    args = parser.parse_args()
    if args.media.resolve() == args.receipt.resolve() or (
            args.media.exists() and args.receipt.exists() and args.media.samefile(args.receipt)):
        parser.error('Receipt must not overwrite source')
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    write_receipt(args.receipt, {'status': 'blocked_validation_incomplete'})
    try:
        result = check(args.media, args.duration, args.min_height, args.require_audio, args.max_bytes)
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
        result = {'status': 'blocked', 'error_type': type(exc).__name__, 'reason': str(exc)[:600]}
    write_receipt(args.receipt, result)
    print(json.dumps(result, indent=2))
    return 0 if result['status'] == 'media_ready_not_semantically_reviewed' else 1


if __name__ == '__main__':
    sys.exit(main())
