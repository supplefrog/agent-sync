"""Optional real-browser smoke for the taste picker. Needs Chrome + websockets.

No downloads, accounts, real conversation messages or persistent profiles.
Run with --file for a host-adapted preview. Output defaults to ignored .evals.
"""
from __future__ import annotations

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

ROOT = Path(__file__).resolve().parents[1]


async def inspect(endpoint: str, page: Path, out: Path) -> dict:
    async with websockets.connect(endpoint, max_size=None) as ws:
        sequence = 0

        async def call(method: str, **params):
            nonlocal sequence
            sequence += 1
            ident = sequence
            await ws.send(json.dumps({'id': ident, 'method': method, 'params': params}))
            while True:
                result = json.loads(await asyncio.wait_for(ws.recv(), timeout=15))
                if result.get('id') == ident:
                    if 'error' in result:
                        raise RuntimeError(result['error'])
                    return result.get('result', {})

        async def evaluate(expression: str):
            result = await call('Runtime.evaluate', expression=expression,
                                returnByValue=True, awaitPromise=True)
            if 'exceptionDetails' in result:
                raise RuntimeError(result['exceptionDetails'])
            return result['result'].get('value')

        await call('Page.enable')
        await call('Page.navigate', url=page.as_uri())
        for _ in range(100):
            if await evaluate('document.readyState === "complete" && !!document.querySelector("#send")'):
                break
            await asyncio.sleep(.05)
        else:
            raise RuntimeError('Picker did not load')
        await call('Page.bringToFront')
        await evaluate("document.body.style.fontFamily='system-ui'; true")
        assert await evaluate('document.querySelectorAll("input[name=direction]").length === 3 && document.querySelector("#send").disabled')
        widths = []
        for width in (360, 1000):
            await call('Emulation.setDeviceMetricsOverride', width=width, height=1000,
                       deviceScaleFactor=1, mobile=False)
            await evaluate('window.scrollTo(0,0); new Promise(r=>requestAnimationFrame(()=>r(true)))')
            dims = await evaluate('({width:innerWidth,scroll:document.documentElement.scrollWidth})')
            assert dims['scroll'] <= width, dims
            shot = await call('Page.captureScreenshot', format='png')
            (out / f'picker-{width}.png').write_bytes(base64.b64decode(shot['data']))
            widths.append(dims)
        # Keyboard selects a native radio. Observe effects, not CSS/source text.
        await evaluate('document.querySelector("input[name=direction]").focus(); true')
        await call('Input.dispatchKeyEvent', type='keyDown', key=' ', code='Space', windowsVirtualKeyCode=32)
        await call('Input.dispatchKeyEvent', type='keyUp', key=' ', code='Space', windowsVirtualKeyCode=32)
        assert await evaluate('document.querySelector("input[name=direction]").checked && !document.querySelector("#send").disabled')
        await evaluate('window.events=[];window.addEventListener("taste-choice",e=>window.events.push(e.detail));true')
        await evaluate('document.querySelector("#density").value="compact";document.querySelector("#density").dispatchEvent(new Event("input"));document.querySelector("#size").value="18";document.querySelector("#size").dispatchEvent(new Event("input"));true')
        assert await evaluate('window.events.length === 0 && getComputedStyle(document.querySelector(".sample")).fontSize === "18px" && document.querySelector("#chooser").dataset.density === "compact"')
        await evaluate('document.querySelector("#nearby").click();true')
        detail = await evaluate('window.events[0]')
        assert detail['action'] == 'nearby' and detail['direction'] == 'Quiet reader' and detail['size'] == 18
        assert await evaluate('document.querySelector("#choice").value === window.events[0].message && document.querySelector("#handoff").open')
        await evaluate('document.querySelector("#mix").click();document.querySelector("#wider").click();true')
        assert await evaluate('window.events.map(e=>e.action).join() === "nearby,mix,wider"')
        # Test a host connection without sending a real user turn.
        await evaluate('window.sent=[];window.hermes={send:m=>window.sent.push(m)};true')
        await evaluate('document.querySelector("#send").click();true')
        host_count = await evaluate('window.sent.length')
        adapted = "window.hermes?.send" in page.read_text(encoding='utf-8')
        assert host_count == (1 if adapted else 0)
        await evaluate('document.querySelector("#reset").click();true')
        assert await evaluate('!document.querySelector("input:checked") && document.querySelector("#send").disabled && document.querySelector("#size").value === "14" && !document.querySelector("#handoff").open')
        return {'status': 'PASS', 'html_sha256': hashlib.sha256(page.read_bytes()).hexdigest(),
                'viewports': widths, 'keyboard_selection': True, 'local_controls_no_messages': True,
                'reactions': ['nearby', 'mix', 'wider', 'explore'], 'reset': True,
                'host_adapter_stub_messages': host_count,
                'limits': 'Browser smoke, not taste approval or live host delivery certification.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--file', type=Path, default=ROOT / 'skills/frontend-ui-engineering/templates/taste-picker.html')
    parser.add_argument('--out', type=Path, default=ROOT / '.evals/taste-picker')
    parser.add_argument('--chrome', default=shutil.which('google-chrome') or shutil.which('chrome') or
                        str(Path(os.environ.get('PROGRAMFILES', '')) / 'Google/Chrome/Application/chrome.exe'))
    args = parser.parse_args()
    page = args.file.resolve()
    if not Path(args.chrome).is_file():
        parser.error('Installed Chrome not found; supply --chrome. No installation attempted.')
    args.out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='taste-browser-') as profile:
        with (args.out / 'chrome.log').open('wb') as log:
            proc = subprocess.Popen([args.chrome, '--headless=new', '--disable-gpu', '--no-first-run',
                                     '--disable-background-networking', '--disable-extensions',
                                     '--no-default-browser-check', '--remote-debugging-port=0',
                                     '--remote-debugging-address=127.0.0.1', f'--user-data-dir={profile}',
                                     'about:blank'], stdout=log, stderr=log)
            try:
                port_file = Path(profile) / 'DevToolsActivePort'
                deadline = time.monotonic() + 15
                while not port_file.exists() and time.monotonic() < deadline:
                    if proc.poll() is not None:
                        raise RuntimeError('Chrome exited before readiness')
                    time.sleep(.1)
                if not port_file.exists():
                    raise TimeoutError('Chrome did not expose CDP')
                port = int(port_file.read_text().splitlines()[0])
                with urllib.request.urlopen(f'http://127.0.0.1:{port}/json/list', timeout=5) as response:
                    tabs = json.load(response)
                endpoint = next(t['webSocketDebuggerUrl'] for t in tabs if t['type'] == 'page')
                report = asyncio.run(inspect(endpoint, page, args.out))
            finally:
                proc.terminate()
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=10)
    report['temporary_profile_removed'] = not Path(profile).exists()
    (args.out / 'receipt.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
