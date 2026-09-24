"""Offline browser checks for render_lesson.py output; not semantic acceptance.

Requires websockets and a Chromium browser. Uses a disposable profile; never
attaches to the user's browser or changes its configuration.
"""
import argparse
import asyncio
import base64
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import urllib.request

import websockets


def browser_path(explicit):
    candidates = [explicit] if explicit else [shutil.which(n) for n in ('chromium','chromium-browser','google-chrome','chrome','msedge')]
    if not explicit:
        for folder in (os.environ.get('PROGRAMFILES'), os.environ.get('LOCALAPPDATA')):
            if folder:
                candidates += [str(Path(folder)/'Google/Chrome/Application/chrome.exe'), str(Path(folder)/'Microsoft/Edge/Application/msedge.exe')]
        candidates.append('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome')
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return str(candidate)
    raise ValueError('No Chromium found; supply --browser with an installed binary')


async def inspect(ws_url, page, output):
    async with websockets.connect(ws_url, max_size=32_000_000) as ws:
        serial=0
        async def cmd(method, **params):
            nonlocal serial
            serial+=1
            await ws.send(json.dumps({'id':serial,'method':method,'params':params}))
            while True:
                message=json.loads(await asyncio.wait_for(ws.recv(),20))
                if message.get('id')==serial:
                    if 'error' in message: raise RuntimeError(message['error'])
                    return message.get('result',{})
        async def js(expression):
            result=await cmd('Runtime.evaluate',expression=expression,returnByValue=True,awaitPromise=True)
            if 'exceptionDetails' in result: raise RuntimeError(result['exceptionDetails'])
            return result['result'].get('value')
        async def key(name, code):
            await cmd('Input.dispatchKeyEvent',type='keyDown',key=name,code=name,windowsVirtualKeyCode=code,**({'text':'\r'} if name=='Enter' else {}))
            await cmd('Input.dispatchKeyEvent',type='keyUp',key=name,code=name,windowsVirtualKeyCode=code)
        await cmd('Page.enable')
        await cmd('Network.enable')
        await cmd('Network.emulateNetworkConditions',offline=True,latency=0,downloadThroughput=-1,uploadThroughput=-1)
        await cmd('Page.navigate',url=page.as_uri())
        for _ in range(100):
            if await js('document.readyState==="complete" && !!document.querySelector("#reading")'): break
            await asyncio.sleep(.05)
        else: raise RuntimeError('Reader did not load')
        await js('Promise.all([...document.images].map(i=>{i.loading="eager";return i.decode()})).then(()=>true)')
        structure=await js('''(()=>{const ids=[...document.querySelectorAll('[id]')].map(e=>e.id);return {
          title:document.title,image_count:document.images.length,h1:document.querySelectorAll('h1').length,
          duplicate_ids:ids.filter((id,i)=>ids.indexOf(id)!==i),
          broken_anchors:[...document.querySelectorAll('a[href^="#"]')].filter(a=>!document.getElementById(a.getAttribute('href').slice(1))).map(a=>a.getAttribute('href'))}})()''')
        assert structure['h1']==1 and not structure['duplicate_ids'] and not structure['broken_anchors'], structure
        views=[]
        for width in (320,768,1440):
            await cmd('Emulation.setDeviceMetricsOverride',width=width,height=1000,deviceScaleFactor=1,mobile=False)
            await js('scrollTo(0,0);true')
            await js('new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(()=>r(true))))')
            layout=await js('({width:innerWidth,scroll:document.documentElement.scrollWidth,client:document.documentElement.clientWidth,figures_fit:[...document.querySelectorAll("figure")].every(f=>f.scrollWidth<=f.clientWidth)})')
            assert layout['width']==width and layout['scroll']<=layout['client'] and layout['figures_fit'], layout
            shot=await cmd('Page.captureScreenshot',format='png',captureBeyondViewport=False)
            (output/f'reader-{width}.png').write_bytes(base64.b64decode(shot['data']))
            if structure['image_count']:
                await js('document.querySelector("button.zoom").focus();true')
                await key('Enter',13)
                await js('document.querySelector(".image-view img").decode().then(()=>true)')
                assert await js('document.querySelector("dialog").open && document.activeElement.id==="figure-close"')
                shot=await cmd('Page.captureScreenshot',format='png',captureBeyondViewport=False)
                (output/f'zoom-{width}.png').write_bytes(base64.b64decode(shot['data']))
                await js('document.querySelector("#figure-size").click();true')
                assert await js('document.querySelector(".image-view").classList.contains("actual")')
                await key('Escape',27)
                await js('new Promise(r=>requestAnimationFrame(()=>r(true)))')
                assert await js('!document.querySelector("dialog").open && document.activeElement.matches("button.zoom")')
            views.append(layout)
        answers=await js('document.querySelectorAll("details:not(.contents)").length')
        if answers:
            await js('document.querySelector("details:not(.contents) summary").focus();true')
            await key('Enter',13)
            assert await js('document.querySelector("details:not(.contents)").open')
            await key('Enter',13)
            assert not await js('document.querySelector("details:not(.contents)").open')
        if await js('!!document.querySelector(".contents a")'):
            await js('document.querySelector(".contents").open=true;document.querySelector(".contents a").click();true')
            await js('new Promise(r=>requestAnimationFrame(()=>r(true)))')
            assert await js('!document.querySelector(".contents").open && /^H[23]$/.test(document.activeElement.tagName)')
        await cmd('Browser.close')
        return {'status':'mechanical_pass_not_semantic_acceptance','offline':True,'structure':structure,'viewports':views,'answer_count':answers,'html_sha256':hashlib.sha256(page.read_bytes()).hexdigest(),'limits':'Inspect screenshots separately. No source fidelity, comprehension, full accessibility or user taste certification.'}


def verify(page, output, browser=None):
    page,output=Path(page).resolve(),Path(output).resolve()
    if not page.is_file(): raise ValueError('HTML file missing')
    executable=browser_path(browser)
    output.mkdir(parents=True,exist_ok=False)
    result={'status':'blocked_browser_check_incomplete'}
    try:
        with tempfile.TemporaryDirectory(prefix='lesson-reader-') as profile:
            proc=subprocess.Popen([executable,'--headless=new','--disable-gpu','--no-first-run','--no-default-browser-check','--remote-debugging-port=0',f'--user-data-dir={profile}','about:blank'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            try:
                portfile=Path(profile)/'DevToolsActivePort'
                deadline=time.monotonic()+20
                while not portfile.exists():
                    if proc.poll() is not None or time.monotonic()>deadline: raise RuntimeError('Browser startup failed')
                    time.sleep(.1)
                port=portfile.read_text().splitlines()[0]
                with urllib.request.urlopen(f'http://127.0.0.1:{port}/json',timeout=5) as response:
                    tabs=json.load(response)
                tab=next(t for t in tabs if t.get('type')=='page')
                result=asyncio.run(asyncio.wait_for(inspect(tab['webSocketDebuggerUrl'],page,output),120))
            finally:
                try: proc.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    if os.name=='nt': subprocess.run(['taskkill','/PID',str(proc.pid),'/T','/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=10)
                    else: proc.terminate()
                    proc.wait(timeout=10)
        result['temporary_profile_removed']=True
    except Exception as exc:
        result={'status':'blocked','error':type(exc).__name__+': '+str(exc)[:800]}
    (output/'checks.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('html',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--browser')
    args=parser.parse_args()
    result=verify(args.html,args.output,args.browser)
    print(json.dumps(result,indent=2))
    raise SystemExit(0 if result['status']=='mechanical_pass_not_semantic_acceptance' else 1)
