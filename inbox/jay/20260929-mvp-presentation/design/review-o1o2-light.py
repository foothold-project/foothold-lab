from pathlib import Path
import sys,base64,io
sys.path.insert(0,str(Path.home()/'AppData/Local/Temp/foothold-mvp-render-deps'))
from playwright.sync_api import sync_playwright
from PIL import Image,ImageDraw
r=Path(__file__).resolve().parents[1]
pairs=[('opening-o1-seedance25-v4.mp4',7.5),('opening-o1-seedance25-v4.mp4',7.8),('opening-o1-seedance25-v4.mp4',7.99),('opening-o2-seedance25-v1.mp4',.04),('opening-o2-seedance25-v1.mp4',.3),('opening-o2-seedance25-v1.mp4',.7)]
with sync_playwright() as pw:
 b=pw.chromium.launch(executable_path=r'C:\Program Files\Google\Chrome\Application\chrome.exe',headless=True,args=['--allow-file-access-from-files'])
 p=b.new_page();p.goto((r/'output/FOOTHOLD-film-storyboard.html').as_uri())
 sheet=Image.new('RGB',(1281,540));d=ImageDraw.Draw(sheet)
 for i,(f,t) in enumerate(pairs):
  encoded=p.evaluate("""async ([f,t])=>{const v=document.querySelector('#masterVideo');v.muted=true;v.src='../assets/'+f;await new Promise(r=>v.onloadeddata=r);await new Promise(r=>{v.onseeked=r;v.currentTime=t});let c=document.createElement('canvas');c.width=854;c.height=480;c.getContext('2d').drawImage(v,0,0);return c.toDataURL().split(',')[1]}""",[f,t])
  im=Image.open(io.BytesIO(base64.b64decode(encoded)));im.save(r/'output'/f'o1o2-match-{i}.png');x=i%3*427;y=i//3*270;sheet.paste(im.resize((427,240)),(x,y+25));d.text((x+5,y+5),f'{f} {t}',fill='white')
 sheet.save(r/'output/o1o2-light-before.jpg');b.close()

