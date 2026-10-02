from pathlib import Path
import sys,json,base64,io
sys.path.insert(0,str(Path.home()/'AppData/Local/Temp/foothold-mvp-render-deps'))
from playwright.sync_api import sync_playwright
from PIL import Image,ImageDraw
r=Path(__file__).resolve().parents[1];errors=[]
with sync_playwright() as pw:
 b=pw.chromium.launch(executable_path=r'C:\Program Files\Google\Chrome\Application\chrome.exe',headless=True,args=['--allow-file-access-from-files'])
 p=b.new_page();p.on('pageerror',lambda e:errors.append(str(e)));p.goto((r/'output/FOOTHOLD-film-storyboard.html').as_uri());p.wait_for_timeout(700)
 meta=p.evaluate("""async()=>{const out=[];for(const v of document.querySelectorAll('#film-deliverables video')){if(v.readyState<1)await new Promise((r,j)=>{v.onloadedmetadata=r;v.onerror=()=>j(v.error.message)});out.push({file:v.src.split('/').pop(),duration:v.duration})}return {players:out,plan:masterPlan,activeCutFiles:[...new Set(Object.entries(videoAssets).filter(([k])=>k.endsWith('master')).map(([k,v])=>v.file))]}}""")
 sheet=Image.new('RGB',(1281,810));d=ImageDraw.Draw(sheet)
 for i,t in enumerate([49.65,49.735,49.875,50,50.125,50.25,50.375,50.5,50.625]):
  encoded=p.evaluate("""async t=>{const v=document.querySelector('#masterVideo');v.muted=true;await new Promise(r=>{v.onseeked=r;v.currentTime=t});const c=document.createElement('canvas');c.width=854;c.height=480;c.getContext('2d').drawImage(v,0,0);return c.toDataURL().split(',')[1]}""",t)
  im=Image.open(io.BytesIO(base64.b64decode(encoded)));x=i%3*427;y=i//3*270;sheet.paste(im.resize((427,240)),(x,y+25));d.text((x+5,y+5),f'{t:.3f}s',fill='white')
 sheet.save(r/'output/film-e5-transition-v8-boundary.jpg')
 p.evaluate("showVideo('e5master',all.findIndex(x=>x.d[0]==='E5'))");p.wait_for_timeout(300)
 meta['e5Modal']=p.evaluate("({file:viewer.querySelector('video').src.split('/').pop(),time:viewer.querySelector('video').currentTime})")
 p.evaluate('viewer.close()')
 p.goto((r/'output/FOOTHOLD-MVP-cover.html').as_uri());p.wait_for_timeout(500)
 meta['presentationFilms']=p.evaluate("[...document.querySelectorAll('video')].map(v=>v.getAttribute('src')).filter(x=>x&&x.includes('film-'))")
 meta['errors']=errors
 assert not errors,errors
 assert meta['activeCutFiles']==['film-master-v8.mp4']
 assert 'film-opening-v7.mp4' in str(meta['presentationFilms']) and 'film-ending-v8.mp4' in str(meta['presentationFilms'])
 (r/'assets/film-e5-transition-v8.qa.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps({k:v for k,v in meta.items() if k!='plan'},ensure_ascii=False,indent=2));b.close()

