from pathlib import Path
import sys,io,base64
sys.path.insert(0,str(Path.home()/'AppData/Local/Temp/foothold-mvp-render-deps'))
from playwright.sync_api import sync_playwright
from PIL import Image,ImageDraw
r=Path(__file__).resolve().parents[1]
times=[49.25,49.42,49.66,49.74,49.83,49.96,50.08,50.21,50.33]
with sync_playwright() as pw:
 b=pw.chromium.launch(executable_path=r'C:\Program Files\Google\Chrome\Application\chrome.exe',headless=True,args=['--allow-file-access-from-files'])
 p=b.new_page();p.goto((r/'output/FOOTHOLD-film-storyboard.html').as_uri())
 sheet=Image.new('RGB',(1281,810));d=ImageDraw.Draw(sheet)
 for i,t in enumerate(times):
  z=p.evaluate("""async t=>{let v=document.querySelector('#masterVideo');v.muted=true;if(v.readyState<2)await new Promise(r=>v.onloadeddata=r);await new Promise(r=>{v.onseeked=r;v.currentTime=t});let c=document.createElement('canvas');c.width=854;c.height=480;c.getContext('2d').drawImage(v,0,0);return c.toDataURL().split(',')[1]}""",t)
  im=Image.open(io.BytesIO(base64.b64decode(z)));im.save(r/'output'/f'e5-transition-source-{i}.png');x=i%3*427;y=i//3*270;sheet.paste(im.resize((427,240)),(x,y+25));d.text((x+4,y+4),str(t),fill='white')
 sheet.save(r/'output/e5-transition-source-sheet.jpg');b.close()

