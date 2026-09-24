"""Capture a bounded batch of review candidates from read-only local media.

Requires ffmpeg and ffprobe on PATH. Requested timestamps are approximate seek
positions, NOT exact PTS or proof that a demonstrated state was captured.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys

from source_ready import MEDIA_INPUT_OPTIONS


def capture(media, output, times, reason, source_origin=0, width=1920,
            max_bytes=50_000_000, timeout=60):
    media, output = Path(media).resolve(), Path(output).resolve()
    if not 1 <= len(times) <= 12 or len(set(times)) != len(times):
        raise ValueError('Use 1–12 distinct timestamps per reviewed batch')
    if any(not math.isfinite(t) or t < 0 for t in [*times, source_origin]):
        raise ValueError('Timestamps and source origin must be finite and nonnegative')
    if not 1 <= width <= 3840 or not 1 <= timeout <= 120 or not 1 <= max_bytes <= 100_000_000:
        raise ValueError('Capture bounds exceeded')
    if not reason.strip():
        raise ValueError('A teaching/review purpose is required')
    before = media.stat()
    # A fresh batch prevents stale receipts or unreviewed overwrite on failure.
    output.mkdir(parents=True, exist_ok=False)
    receipt = {'status':'capture_incomplete','media':str(media),
               'source_bytes':before.st_size,'source_mtime_ns':before.st_mtime_ns,
               'source_origin_seconds':source_origin,'reason':reason,'frames':[],
               'timing':'Requested local seek plus supplied source origin; approximate, not exact decoded PTS.',
               'perceptually_reviewed':False,'semantic_coverage_verified':False}
    used = 0
    try:
        for index, second in enumerate(times, 1):
            target = output / f'frame-{index:03d}.png'
            subprocess.run(['ffmpeg','-nostdin','-hide_banner','-v','error',
                            *MEDIA_INPUT_OPTIONS,'-ss',str(second),'-i',str(media),'-map','0:v:0','-an','-sn',
                            '-frames:v','1','-vf',f'scale=min({width}\\,iw):-2',
                            '-fs',str(max_bytes-used),'-update','1','-n',str(target)],
                           capture_output=True, text=True, timeout=timeout, check=True)
            size = target.stat().st_size
            if size <= 0 or used + size > max_bytes:
                target.unlink()
                raise ValueError('Captured image exceeds batch storage bound')
            probe = subprocess.run(['ffprobe','-v','error','-show_streams','-of','json',str(target)],
                                   capture_output=True,text=True,timeout=10,check=True)
            streams = json.loads(probe.stdout)['streams']
            if not streams or streams[0].get('codec_name') != 'png':
                raise ValueError('Capture is not a decodable PNG')
            # Full single-image decode catches partial PNG writes at the file cap.
            subprocess.run(['ffmpeg','-nostdin','-v','error','-xerror','-i',str(target),
                            '-f','null','-'],capture_output=True,text=True,timeout=10,check=True)
            used += size
            receipt['frames'].append({'file':target.name,'requested_local_seconds':second,
                                     'requested_source_seconds':source_origin+second,
                                     'actual_source_seconds':None,
                                     'width':streams[0]['width'],'height':streams[0]['height'],
                                     'bytes':size,'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),
                                     'review':'pending'})
        receipt['status'] = 'captured_candidates_not_reviewed'
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
        receipt['status'] = 'blocked'
        receipt['error'] = type(exc).__name__ + ': ' + str(exc)[:600]
    finally:
        after = media.stat()
        receipt['source_size_mtime_unchanged'] = (before.st_size,before.st_mtime_ns) == (after.st_size,after.st_mtime_ns)
        if not receipt['source_size_mtime_unchanged']:
            receipt['status'], receipt['error'] = 'blocked', 'Source changed during capture'
        receipt['captured_bytes'] = used
        (output/'capture.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('media', type=Path)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--times',type=float,nargs='+',required=True)
    parser.add_argument('--reason',required=True)
    parser.add_argument('--source-origin',type=float,default=0)
    parser.add_argument('--width',type=int,default=1920)
    parser.add_argument('--max-bytes',type=int,default=50_000_000)
    parser.add_argument('--timeout',type=int,default=60)
    args=parser.parse_args()
    try:
        result=capture(args.media,args.output,args.times,args.reason,args.source_origin,args.width,args.max_bytes,args.timeout)
        print(json.dumps(result,indent=2))
        return 0 if result['status']=='captured_candidates_not_reviewed' else 1
    except (OSError,ValueError) as exc:
        print(str(exc),file=sys.stderr)
        return 1


if __name__=='__main__':
    sys.exit(main())
