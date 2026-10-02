"""Verify local playback, shot links and selected edit-boundary frames."""
from pathlib import Path
import sys,json,base64,io
sys.path.insert(0,str(Path.home()/'AppData/Local/Temp/foothold-mvp-render-deps'))
from playwright.sync_api import sync_playwright
from PIL import Image,ImageDraw
r=Path(__file__).resolve().parents[1]
errors=[]
with sync_playwright() as pw:
 b=pw.chromium.launch(executable_path=r'C:\Program Files\Google\Chrome\Application\chrome.exe',headless=True,args=['--allow-file-access-from-files'])
 p=b.new_page(viewport={'width':1440,'height':1000});p.on('pageerror',lambda e:errors.append(str(e)))
 p.goto((r/'output/FOOTHOLD-film-storyboard.html').as_uri());p.wait_for_timeout(1200)
 result=p.evaluate('''async ()=>{
 const out=[];for(const v of document.querySelectorAll('#film-deliverables video')){
 if(v.readyState<1)await new Promise((resolve,reject)=>{v.onloadedmetadata=resolve;v.onerror=()=>reject(v.error.message)});
 out.push({file:v.src.split('/').pop(),duration:v.duration,width:v.videoWidth,height:v.videoHeight});}
 return {videos:out,shots:masterPlan.clips.map(c=>({id:c.shot,button:!!document.querySelector('[data-video="'+c.shot.toLowerCase()+'master"]')})),missingFiles:Object.values(videoAssets).filter(x=>!x.file).length};
 }''')
 times=[44.75,45.25,46,47,49,50.25,50.75,69.75,81.1]
 sheet=Image.new('RGB',(1068,226*3),(12,16,18));d=ImageDraw.Draw(sheet)
 for i,t in enumerate(times):
  data=p.evaluate('''async t=>{const v=document.querySelector('#masterVideo');v.muted=true;await v.play();v.pause();await new Promise(r=>{v.onseeked=r;v.currentTime=t===0?.001:t});const c=document.createElement('canvas');c.width=v.videoWidth;c.height=v.videoHeight;c.getContext('2d').drawImage(v,0,0);return c.toDataURL().split(',')[1]}''',t)
  im=Image.open(io.BytesIO(base64.b64decode(data))).convert('RGB').resize((356,200));x=i%3*356;y=i//3*226;sheet.paste(im,(x,y+26));d.text((x+8,y+5),f'{t:.3f}s',fill='white')
 sheet.save(r/'output/film-master-audio-boundary-v4.jpg',quality=92)
 p.evaluate("showVideo('e7master',all.findIndex(x=>x.d[0]==='E7'))")
 p.wait_for_timeout(600)
 result['e7Modal']=p.evaluate("({open:viewer.open,time:viewer.querySelector('video').currentTime,file:viewer.querySelector('video').src.split('/').pop()})")
 p.evaluate('viewer.close()');p.screenshot(path=str(r/'output/film-master-page-v4.png'))
 result['pageErrors']=errors
 result['audioMeasurement']={'status':'Audio patch audited in film-footsteps-v4.audit.json. Not final music or mix.'}
 result['status']='480p review, user approval pending; frame review does not certify every generated motion'
 (r/'assets/film-master-v4.qa.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(result,ensure_ascii=False,indent=2));b.close()