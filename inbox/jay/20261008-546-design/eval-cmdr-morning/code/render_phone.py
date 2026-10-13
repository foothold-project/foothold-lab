"""Render a page section at a true 390 px phone viewport through the Chrome DevTools protocol (headless --window-size cannot
go below ~500 px). Light and dark. Prints the layout width and the section box; saves the section as PNG.
Usage: python render_phone.py <section id> [width]"""
import base64
import json
import os
import subprocess
import sys
import time
import urllib.request

import websocket

SP = "C:/Users/AI-WS01/AppData/Local/Temp/claude/C--Users-AI-WS01-Desktop-jay----------foothold-lab/09bbf294-fda0-4c7b-81c5-e23f793f2be2/scratchpad"
T = "C:/Users/AI-WS01/.claude/jobs/09bbf294/tmp/e12page/shots5"
CH = "C:/Program Files/Google/Chrome/Application/chrome.exe"
SEC = sys.argv[1] if len(sys.argv) > 1 else "cmdr"
W = int(sys.argv[2]) if len(sys.argv) > 2 else 390
URL = "file:///" + os.path.join(SP, "e12page", "index.html").replace("\\", "/")
prof = os.path.join(os.environ.get("TEMP", "."), "cdp_prof_390")
p = subprocess.Popen([CH, "--headless=new", "--disable-gpu", "--remote-debugging-port=9333", "--remote-allow-origins=*", f"--user-data-dir={prof}", "about:blank"],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    for _ in range(50):
        try:
            tabs = json.load(urllib.request.urlopen("http://127.0.0.1:9333/json"))
            page = next(t for t in tabs if t.get("type") == "page")
            break
        except Exception:
            time.sleep(0.2)
    ws = websocket.create_connection(page["webSocketDebuggerUrl"], timeout=60)
    n = [0]

    def call(method, **params):
        n[0] += 1
        ws.send(json.dumps({"id": n[0], "method": method, "params": params}))
        while True:
            m = json.loads(ws.recv())
            if m.get("id") == n[0]:
                return m.get("result", m)

    call("Emulation.setDeviceMetricsOverride", width=W, height=844, deviceScaleFactor=1, mobile=True)
    for scheme in ("light", "dark"):
        call("Emulation.setEmulatedMedia", features=[{"name": "prefers-color-scheme", "value": scheme}])
        call("Page.navigate", url=URL)
        time.sleep(4)
        r = call("Runtime.evaluate", returnByValue=True, expression=(
            "(()=>{const e=document.getElementById('%s');const b=e.getBoundingClientRect();"
            "return [Math.round(b.top+scrollY),Math.round(b.height),document.documentElement.scrollWidth,innerWidth,"
            "getComputedStyle(document.body).backgroundColor]})()") % SEC)
        top, hgt, sw, iw, bg = r["result"]["value"]
        shot = call("Page.captureScreenshot", format="png", captureBeyondViewport=True,
                    clip={"x": 0, "y": top, "width": W, "height": hgt, "scale": 1})
        out = os.path.join(T, f"v17_{SEC}_{W}phone_{scheme}.png")
        open(out, "wb").write(base64.b64decode(shot["data"]))
        print(scheme, "innerWidth", iw, "scrollWidth", sw, "section", top, hgt, "body bg", bg, "->", out)
    ws.close()
finally:
    p.terminate()
