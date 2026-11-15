"""미경험 지형 영상 페이지 2판 렌더 확인 (lead · 10/13 저녁). Chrome DevTools 로 1920 x 1080 · 1366 x 768 · 390 x 844 (모바일),
라이트 · 다크에서 각 절을 찍고, 가로 넘침 · 몸 배경 · 재생기 동작 (단추 → 네 영상 src · 배속) 을 잰다.
사용: python render_unseen.py <index.html 경로 또는 URL> <출력 폴더> [절 id ...]"""
import base64
import json
import os
import subprocess
import sys
import time
import urllib.request

import websocket

CH = "C:/Program Files/Google/Chrome/Application/chrome.exe"
SRC = sys.argv[1]
URL = SRC if SRC.startswith("http") else "file:///" + SRC.replace("\\", "/")
T = sys.argv[2]
SECS = sys.argv[3:] or ["read", "why", "table", "play", "list"]
os.makedirs(T, exist_ok=True)
prof = os.path.join(os.environ.get("TEMP", "."), "cdp_prof_unseen")
p = subprocess.Popen([CH, "--headless=new", "--disable-gpu", "--remote-debugging-port=9334", "--remote-allow-origins=*", f"--user-data-dir={prof}",
                      "--autoplay-policy=no-user-gesture-required", "about:blank"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
res = []
try:
    for _ in range(50):
        try:
            tabs = json.load(urllib.request.urlopen("http://127.0.0.1:9334/json"))
            page = next(t for t in tabs if t.get("type") == "page")
            break
        except Exception:
            time.sleep(0.2)
    ws = websocket.create_connection(page["webSocketDebuggerUrl"], timeout=120)
    n = [0]

    def call(method, **params):
        n[0] += 1
        ws.send(json.dumps({"id": n[0], "method": method, "params": params}))
        while True:
            m = json.loads(ws.recv())
            if m.get("id") == n[0]:
                return m.get("result", m)

    def ev(expr):
        r = call("Runtime.evaluate", expression=expr, returnByValue=True, awaitPromise=True)
        return r.get("result", {}).get("value")

    for (W, H, mob) in ((1920, 1080, False), (1366, 768, False), (390, 844, True)):
        call("Emulation.setDeviceMetricsOverride", width=W, height=H, deviceScaleFactor=1, mobile=mob)
        for scheme in ("light", "dark"):
            call("Emulation.setEmulatedMedia", features=[{"name": "prefers-color-scheme", "value": scheme}])
            call("Page.navigate", url=URL)
            time.sleep(5)
            info = ev("(()=>({sw:document.documentElement.scrollWidth,iw:innerWidth,bg:getComputedStyle(document.body).backgroundColor,"
                      "wrap:Math.round(document.querySelector('.wrap').getBoundingClientRect().width),"
                      "quad:[...document.querySelectorAll('#quad video')].map(v=>v.getAttribute('src')).length,"
                      "rows:document.querySelectorAll('#vlist tr[data-i]').length,mx:document.querySelectorAll('#mx tbody tr').length}))()")
            rec = {"w": W, "scheme": scheme, **info, "shots": []}
            for sec in SECS:
                b = ev(f"(()=>{{const e=document.getElementById('{sec}');const r=e.getBoundingClientRect();return [Math.round(r.top+scrollY),Math.round(r.height)]}})()")
                top, hgt = b
                hgt = min(hgt, 2600)
                shot = call("Page.captureScreenshot", format="png", captureBeyondViewport=True, clip={"x": 0, "y": top, "width": W, "height": hgt, "scale": 1})
                out = os.path.join(T, f"un2_{sec}_{W}_{scheme}.png")
                open(out, "wb").write(base64.b64decode(shot["data"]))
                rec["shots"].append(out)
            if W == 1920 and scheme == "light":
                # 재생기 동작: 예시 단추 → 지형 바뀜 · 네 영상 src · 배속 0.25 → 모든 영상 playbackRate
                rec["player"] = ev("""(async()=>{
                  const b=[...document.querySelectorAll('button.ex')].find(x=>x.dataset.open.startsWith('stepping_stones'));
                  b.click(); await new Promise(r=>setTimeout(r,800));
                  const head=document.getElementById('quadhead').textContent;
                  const r25=[...document.querySelectorAll('.trow .chip')].find(x=>x.textContent==='0.25×'); r25.click();
                  const vids=[...document.querySelectorAll('#quad video')];
                  const rates=vids.map(v=>v.playbackRate);
                  const go=[...document.querySelectorAll('.trow .chip')].find(x=>x.textContent==='함께 재생'); go.click();
                  await new Promise(r=>setTimeout(r,2500));
                  const t=vids.map(v=>+v.currentTime.toFixed(2)), paused=vids.map(v=>v.paused);
                  const chip=[...document.querySelectorAll('#pick .chip[aria-pressed=true]')].map(x=>x.textContent);
                  return {head, n:vids.length, rates, t, paused, chip, srcs:vids.map(v=>v.getAttribute('src'))};
                })()""")
                shot = call("Page.captureScreenshot", format="png", captureBeyondViewport=True,
                            clip={"x": 0, "y": ev("Math.round(document.getElementById('play').getBoundingClientRect().top+scrollY)"), "width": W, "height": 900, "scale": 1})
                out = os.path.join(T, f"un2_play_after_click_{W}.png")
                open(out, "wb").write(base64.b64decode(shot["data"]))
                rec["shots"].append(out)
            res.append(rec)
            print(json.dumps({k: v for k, v in rec.items() if k != "shots"}, ensure_ascii=False))
    ws.close()
finally:
    p.terminate()
json.dump(res, open(os.path.join(T, "render_unseen.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
