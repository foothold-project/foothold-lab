from pathlib import Path
import sys,base64,io
sys.path.insert(0,str(Path.home()/'AppData/Local/Temp/foothold-mvp-render-deps'))
from playwright.sync_api import sync_playwright
from PIL import Image,ImageDraw
r=Path.cwd()
with sync_playwright() as pw:
 b=pw.chromium.launch(executable_path=r'C:\Program Files\Google\Chrome\Application\chrome.exe',headless=True,args=['--allow-file-access-from-files'])
 p=b.new_page();p.goto((r/'output/FOOTHOLD-film-storyboard.html').as_uri())
 sheet=Image.new('RGB',(1281,1080));d=ImageDraw.Draw(sheet)
 for i,n in enumerate(range(1198,1210)):
  t=(n+.2)/24
  encoded=p.evaluate("""async t=>{let v=document.querySelector('#masterVideo');v.muted=true;if(v.readyState<2)await new Promise(r=>v.onloadeddata=r);await new Promise(r=>{v.onseeked=r;v.currentTime=t});let c=document.createElement('canvas');c.width=854;c.height=480;c.getContext('2d').drawImage(v,0,0);return c.toDataURL().split(',')[1]}""",t)
  im=Image.open(io.BytesIO(base64.b64decode(encoded))).resize((427,240));x=i%3*427;y=i//3*270;sheet.paste(im,(x,y+25));d.text((x+5,y+5),f'Frame {n}, {n/24:.5f}s',fill='white')
 sheet.save(r/'output/e5pre-out-frame-review.jpg')
 b.close()

