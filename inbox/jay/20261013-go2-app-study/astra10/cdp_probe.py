"""Bounded CDP inspection of offline emulator WebView. No account storage read."""
import asyncio,json,urllib.request,pathlib,base64,sys
import websockets
ROOT=pathlib.Path(__file__).resolve().parent
async def main():
    target=json.load(urllib.request.urlopen('http://127.0.0.1:9229/json'))[0]
    async with websockets.connect(target['webSocketDebuggerUrl'],origin='http://127.0.0.1:9229',max_size=20_000_000) as ws:
        seq=0
        async def send(method,params):
            nonlocal seq
            seq+=1;await ws.send(json.dumps({'id':seq,'method':method,'params':params}))
            while True:
                r=json.loads(await ws.recv())
                if r.get('id')==seq:return r
        expr=sys.argv[1] if len(sys.argv)>1 else '({url:location.href,text:document.body.innerText.slice(0,4000),canvas:document.querySelectorAll("canvas").length})'
        r=await send('Runtime.evaluate',{'expression':expr,'returnByValue':True,'awaitPromise':True})
        print(json.dumps(r,ensure_ascii=False))
        if len(sys.argv)>2:
            r=await send('Page.captureScreenshot',{'format':'png'})
            (ROOT/'evidence'/sys.argv[2]).write_bytes(base64.b64decode(r['result']['data']))
asyncio.run(main())
