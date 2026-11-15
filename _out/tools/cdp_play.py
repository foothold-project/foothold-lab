# -*- coding: utf-8 -*-
"""헤드리스 Chrome 으로 갤러리 「함께 재생」을 눌러 칸마다 실제로 움직이기까지 걸린 시간을 잰다.

사용: python cdp_play.py <url> <label> [public]
public 이면 NAS 주소를 Funnel 공개 IP 로 강제해 휴대폰(테일넷 밖) 경로를 흉내 낸다.
"""
import json, os, subprocess, sys, tempfile, time, urllib.request
import websocket

CHROME = r'C:\Program Files\Google\Chrome\Application\chrome.exe'
url, label = sys.argv[1], sys.argv[2]
public = len(sys.argv) > 3 and sys.argv[3] == 'public'
port = 9333 if not public else 9334
prof = tempfile.mkdtemp(prefix='cdp_')
args = [CHROME, '--headless=new', f'--remote-debugging-port={port}', f'--user-data-dir={prof}',
        '--no-first-run', '--mute-audio', '--window-size=1400,900', 'about:blank']
if public:
    args.insert(1, '--host-resolver-rules=MAP ai-nas01.tail025053.ts.net 103.84.155.153')
proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    for _ in range(50):
        try:
            tabs = json.load(urllib.request.urlopen(f'http://127.0.0.1:{port}/json'))
            page = [t for t in tabs if t.get('type') == 'page'][0]
            break
        except Exception:
            time.sleep(0.2)
    ws = websocket.create_connection(page['webSocketDebuggerUrl'], timeout=60, suppress_origin=True)
    mid = [0]
    def call(method, params=None):
        mid[0] += 1
        ws.send(json.dumps({'id': mid[0], 'method': method, 'params': params or {}}))
        while True:
            m = json.loads(ws.recv())
            if m.get('id') == mid[0]:
                return m.get('result', {})
    def ev(expr):
        r = call('Runtime.evaluate', {'expression': expr, 'awaitPromise': True, 'returnByValue': True})
        return r.get('result', {}).get('value')
    call('Page.enable')
    call('Page.navigate', {'url': url})
    time.sleep(4)
    n = ev('document.querySelectorAll("video").length')
    ev('''window.__t0=performance.now(); window.__log=[...document.querySelectorAll("video")].map(()=>({}));
      [...document.querySelectorAll("video")].forEach((v,i)=>["loadedmetadata","canplay","playing","stalled","error"].forEach(e=>v.addEventListener(e,()=>{if(!(e in __log[i]))__log[i][e]=Math.round(performance.now()-__t0)})));
      true''')
    # 사람이 누르는 것과 같게 실제 마우스 클릭을 보낸다 (사용자 활성화)
    box = ev('''(()=>{const b=[...document.querySelectorAll("button")].find(b=>b.textContent.trim()==="함께 재생"); if(!b) return null; b.scrollIntoView({block:"center"}); const r=b.getBoundingClientRect(); return [r.x+r.width/2, r.y+r.height/2];})()''')
    if box:
        for t in ('mousePressed', 'mouseReleased'):
            call('Input.dispatchMouseEvent', {'type': t, 'x': box[0], 'y': box[1], 'button': 'left', 'clickCount': 1})
    moved = {}
    for k in range(30):
        time.sleep(1)
        st = ev('[...document.querySelectorAll("video")].map(v=>[v.readyState,+v.currentTime.toFixed(2),v.paused,v.error&&v.error.code])')
        for i, s in enumerate(st or []):
            if i not in moved and s[1] > 0.3:
                moved[i] = k + 1
        if st and len(moved) == len(st):
            break
    log = ev('JSON.stringify(__log)')
    srcs = ev('[...document.querySelectorAll("video")].map(v=>v.currentSrc.split("/").pop())')
    note = ev('(document.querySelector(".tag.warn")||{}).textContent||""')
    print(json.dumps({'label': label, 'public': public, 'videos': n, 'clicked': bool(box),
                      'moved_after_s': {srcs[i] if srcs else i: moved.get(i) for i in range(n or 0)},
                      'events_ms': json.loads(log or '[]'), 'final': st, 'note': note}, ensure_ascii=False))
finally:
    proc.kill()
