from pathlib import Path
import sys,base64,io,json
sys.path.insert(0,str(Path.home()/'AppData/Local/Temp/foothold-mvp-render-deps'))
from playwright.sync_api import sync_playwright
from PIL import Image,ImageDraw
r=Path(__file__).resolve().parents[1]
with sync_playwright() as pw:
 b=pw.chromium.launch(executable_path=r'C:\Program Files\Google\Chrome\Application\chrome.exe',headless=True,args=['--allow-file-access-from-files'])
 p=b.new_page();p.goto((r/'output/FOOTHOLD-film-storyboard.html').as_uri())
 p.evaluate("document.querySelector('#masterVideo').src='../assets/film-master-v5.mp4'")
 p.wait_for_timeout(600)
 sheet=Image.new('RGB',(1281,540));d=ImageDraw.Draw(sheet)
 for i,n in enumerate(range(1202,1208)):
  encoded=p.evaluate("""async t=>{const v=document.querySelector('#masterVideo');v.muted=true;await new Promise(r=>{v.onseeked=r;v.currentTime=t});const c=document.createElement('canvas');c.width=854;c.height=480;c.getContext('2d').drawImage(v,0,0);return c.toDataURL().split(',')[1]}""",(n+.4)/24)
  im=Image.open(io.BytesIO(base64.b64decode(encoded))).resize((427,240));x=i%3*427;y=i//3*270;sheet.paste(im,(x,y+25));d.text((x+5,y+5),f'v5 frame {n}',fill='white')
 sheet.save(r/'output/e5pre-out-v5-boundary.jpg')
 result=p.evaluate("({duration:document.querySelector('#masterVideo').duration,comparison:!!document.querySelector('#e5pre-outpoint-review video'),file:document.querySelector('#masterVideo').src})")
 (r/'assets/film-outpoint-v5-playback.qa.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(result)
 b.close()

