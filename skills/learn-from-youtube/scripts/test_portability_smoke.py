"""Copy the skill to a temporary location and exercise its real CLI seams.

Provide an already authorized local clip; no network, models or source writes.
The fixture articles test portability and reader mechanics, not teaching quality.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


def run(media, duration, output):
    skill=Path(__file__).resolve().parent.parent
    media=Path(media).resolve()
    output=Path(output).resolve()
    if not 0 < media.stat().st_size <= 250_000_000:
        raise ValueError('Use an existing bounded clip no larger than 250 MB')
    output.mkdir(parents=True,exist_ok=False)
    results=[]
    with tempfile.TemporaryDirectory(prefix='portable-video-skill-') as tmp:
        root=Path(tmp)
        copied=root/'toolkit'
        shutil.copytree(skill,copied,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
        work=root/'fresh-workspace'
        work.mkdir()
        shutil.copy2(media,work/'segment.mp4')
        def command(script,*args):
            env=os.environ.copy()
            env['PYTHONPATH']=''
            result=subprocess.run([sys.executable,str(copied/'scripts'/script),*map(str,args)],cwd=work,env=env,capture_output=True,text=True,encoding='utf-8',timeout=220)
            if result.returncode:
                raise RuntimeError(script+': '+result.stderr[-1800:]+result.stdout[-1800:])
            results.append({'script':script,'exit':result.returncode})
            return result
        command('source_ready.py','segment.mp4','--duration',duration,'--receipt','ready.json')
        command('capture_frames.py','segment.mp4','--output','frames','--times',0,duration/2,'--reason','Portability probe, not semantic coverage')
        (work/'lesson.md').write_text('# From a frame to an explanation\n\nA portability fixture, not a lesson about this recording.\n\n## Observe before interpreting\n\nThe frame below is captured from the supplied test clip. No interpretation of its labels or claims has been made.\n\n![An unreviewed frame from the supplied clip](frames/frame-001.png)\n\n*Source capture; semantic review pending.*\n\n## What has been established?\n\n<details markdown="1"><summary>Check your answer</summary>\n\nOnly that the source decoded, an image was captured, and this reader works. These facts do not establish a useful lesson.\n\n</details>\n',encoding='utf-8')
        command('render_lesson.py','lesson.md','reader.html')
        command('check_reader.py','reader.html','--output','browser')
        (work/'plain.md').write_text('# A plain article\n\nThis fixture tests the no-image path.\n\n## A useful distinction\n\nRendering a paragraph is not a test of whether it teaches.\n',encoding='utf-8')
        command('render_lesson.py','plain.md','plain.html')
        command('check_reader.py','plain.html','--output','plain-browser')
        # Negative control: a plausible layout regression must not receive PASS.
        broken=(work/'plain.html').read_text(encoding='utf-8').replace('</style>','body{min-width:1200px}</style>')
        (work/'broken.html').write_text(broken,encoding='utf-8')
        bad=subprocess.run([sys.executable,str(copied/'scripts/check_reader.py'),'broken.html','--output','broken-browser'],cwd=work,capture_output=True,text=True,timeout=160)
        assert bad.returncode==1 and json.loads((work/'broken-browser/checks.json').read_text())['status']=='blocked'
        for directory in ('browser','plain-browser'):
            shutil.copytree(work/directory,output/directory)
        ready=json.loads((work/'ready.json').read_text())
        capture=json.loads((work/'frames/capture.json').read_text())
        report={'status':'portable_mechanics_pass_not_semantic_acceptance','isolated_skill_copy':True,'fresh_cwd':True,'pythonpath_empty':True,'commands':results,'overflow_negative_control_rejected':True,'source_full_decode':ready['full_decode_passed'],'captured_frames':len(capture['frames']),'source_unchanged':capture['source_size_mtime_unchanged'],'limits':'Existing real packet, illustrated fixture and plain fixture. Not an unrelated real-video teaching trial or a model/skill quality comparison.'}
    report['temporary_skill_workspace_media_removed']=not root.exists()
    (output/'portability.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('media',type=Path)
    parser.add_argument('--duration',type=float,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(run(args.media,args.duration,args.output),indent=2))
