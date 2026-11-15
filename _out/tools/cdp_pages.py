# 페이지마다 모든 <video> 의 목차(metadata)를 강제로 읽어 오류 · 미응답을 센다. 헤드리스 Chrome · 운영 주소.
import json, subprocess, sys, tempfile, time, urllib.request, websocket
CH = r'C:\Program Files\Google\Chrome\Application\chrome.exe'
pages = sys.argv[1:]
port = 9351
p = subprocess.Popen([CH, '--headless=new', f'--remote-debugging-port={port}', f'--user-data-dir={tempfile.mkdtemp()}',
                      '--no-first-run', '--mute-audio', '--window-size=1400,900', 'about:blank'],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    for _ in range(50):
        try:
            pg = [t for t in json.load(urllib.request.urlopen(f'http://127.0.0.1:{port}/json')) if t['type'] == 'page'][0]; break
        except Exception: time.sleep(0.2)
    ws = websocket.create_connection(pg['webSocketDebuggerUrl'], timeout=120, suppress_origin=True); i = [0]
    def call(m, prm=None):
        i[0] += 1; ws.send(json.dumps({'id': i[0], 'method': m, 'params': prm or {}}))
        while True:
            r = json.loads(ws.recv())
            if r.get('id') == i[0]: return r
    def ev(e):
        r = call('Runtime.evaluate', {'expression': e, 'awaitPromise': True, 'returnByValue': True})
        if 'exceptionDetails' in r.get('result', {}): return {'js_error': r['result']['exceptionDetails'].get('text')}
        return r.get('result', {}).get('result', {}).get('value')
    call('Page.enable')
    for url in pages:
        call('Page.navigate', {'url': url})
        # 준비 조건: 문서 완료 + 영상 수가 2초 동안 그대로
        ev("""new Promise(res=>{let last=-1,same=0;const t0=Date.now();const iv=setInterval(()=>{const n=document.querySelectorAll('video').length;
              if(document.readyState==='complete'&&n===last){same++}else{same=0;last=n}
              if(same>=4||Date.now()-t0>15000){clearInterval(iv);res(n)}},500)})""")
        ev("[...document.querySelectorAll('button.poster')].forEach(b=>b.click()); new Promise(r=>setTimeout(()=>r(1),1500))")
        r = ev("""(async()=>{const vs=[...document.querySelectorAll('video')];const out={n:vs.length,ok:0,err:[],timeout:[]};
              await Promise.all(vs.map(v=>new Promise(res=>{const src=()=>(v.currentSrc||v.src||(v.querySelector('source')||{}).src||'').split('/').slice(-2).join('/');
                if(v.readyState>=1){out.ok++;return res()}
                const done=(k)=>{clearTimeout(to);k==='ok'?out.ok++:out[k].push(src());res()};
                const to=setTimeout(()=>done('timeout'),25000);
                v.addEventListener('loadedmetadata',()=>done('ok'),{once:true});
                v.addEventListener('error',()=>done('err'),{once:true});
                if(!v.src&&!v.querySelector('source')){done('err');return}
                v.preload='metadata';try{v.load()}catch(e){done('err')}})));
              return out})()""")
        print(json.dumps({'url': url.replace('https://foothold-project.vercel.app', ''), **(r or {})}, ensure_ascii=False)[:400])
finally:
    p.kill()
