from pathlib import Path
import json,sys
sys.path.insert(0,str(Path.home()/'AppData/Local/Temp/foothold-mvp-render-deps'))
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parent
with sync_playwright() as pw:
    browser=pw.chromium.launch(executable_path='C:/Program Files/Google/Chrome/Application/chrome.exe',headless=True,args=['--allow-file-access-from-files'])
    page=browser.new_page();errors=[]
    page.on('console',lambda m:print(m.text,flush=True))
    page.on('pageerror',lambda e:(errors.append(str(e)),print('PAGEERROR '+str(e),flush=True)))
    page.goto((ROOT/'v5-player.js').as_uri())
    page.evaluate("document.body.innerHTML='<canvas id=go2></canvas>'")
    for name in ['v5-manifest.js','v5-frame-anchors.js','v5-player.js']:page.add_script_tag(url=(ROOT/name).as_uri())
    result=page.evaluate('''async(base)=>{
      const frames=[];const p=new Go2V5Player(document.querySelector('canvas'),base,{onFrame:s=>frames.push(s.frame)});window.player=p;
      await p.ready;console.log('ready');const states=[];for(const id of Object.keys(p.manifest.states)){await p.setState(id);states.push({...p.current});console.log('state '+id);}
      const segments=[];for(const id of Object.keys(p.manifest.segments)){console.log('start '+id);await Promise.race([p.playSegment(id,{speed:8}),new Promise((_,reject)=>setTimeout(()=>reject(Error('Timed out '+id+' '+JSON.stringify(p.current)+' loading '+JSON.stringify([...p.loading].map(([k,v])=>[k,v.complete,v.naturalWidth])))),15000))]);segments.push({...p.current});console.log('end '+id);}
      await p.playSegment('to_side',{reverse:true,speed:8});const reverse={...p.current};
      const ongoing=p.playSegment('turntable',{speed:1});await p.setState('front');await ongoing;
      return {states,segments,reverse,afterCancellation:p.current,canvas:[p.canvas.width,p.canvas.height],onFrameCalls:frames.length,cacheSize:p.cache.size};
    }''',ROOT.as_uri())
    browser.close()
assert not errors,errors
assert result['canvas']==[1600,1200]
assert result['reverse']['frame']==193
assert result['afterCancellation']['state']=='front'
assert result['cacheSize']<=110
assert [x['frame'] for x in result['segments']]==[97,145,193,241,289]
result['errors']=errors
(ROOT/'v5-player-test.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result))
