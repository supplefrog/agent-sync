#!/usr/bin/env python3
"""Fetch a YouTube transcript as JSON or text."""
import argparse,json,re
def video_id(value):
    value=value.strip()
    for pattern in [r'(?:v=|youtu\.be/|shorts/|embed/|live/)([\w-]{11})',r'^([\w-]{11})$']:
        match=re.search(pattern,value)
        if match:return match.group(1)
    return value
def stamp(seconds):
    total=int(seconds); h,rem=divmod(total,3600); m,s=divmod(rem,60)
    return f'{h}:{m:02d}:{s:02d}' if h else f'{m}:{s:02d}'
def main():
    parser=argparse.ArgumentParser(); parser.add_argument('url'); parser.add_argument('--language','-l'); parser.add_argument('--timestamps','-t',action='store_true'); parser.add_argument('--text-only',action='store_true'); args=parser.parse_args()
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
    except ImportError: raise SystemExit('youtube-transcript-api missing; run: pip install youtube-transcript-api')
    vid=video_id(args.url); languages=[x.strip() for x in args.language.split(',')] if args.language else None
    try: result=YouTubeTranscriptApi().fetch(vid,languages=languages) if languages else YouTubeTranscriptApi().fetch(vid)
    except Exception as exc: print(json.dumps({'error':str(exc)})); raise SystemExit(1)
    segments=[{'text':x.text,'start':x.start,'duration':x.duration} for x in result]
    full=' '.join(x['text'] for x in segments); timed='\n'.join(f"{stamp(x['start'])} {x['text']}" for x in segments)
    if args.text_only: print(timed if args.timestamps else full); return
    out={'video_id':vid,'segment_count':len(segments),'duration':stamp(segments[-1]['start']+segments[-1]['duration']) if segments else '0:00','full_text':full}
    if args.timestamps: out['timestamped_text']=timed
    print(json.dumps(out,ensure_ascii=False,indent=2))
if __name__=='__main__': main()
