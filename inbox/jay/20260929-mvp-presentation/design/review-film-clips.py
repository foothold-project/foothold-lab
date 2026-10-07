"""Sample generated clips for human visual review; this is not automatic approval."""
from pathlib import Path
import base64, io, json, sys
sys.path.insert(0,str(Path.home()/'AppData/Local/Temp/foothold-mvp-render-deps'))
from playwright.sync_api import sync_playwright
from PIL import Image, ImageDraw

root=Path(__file__).resolve().parents[1]
files=sys.argv[1:]
dense='--dense' in files
if dense: files.remove('--dense')
times=[.05,.5,1,1.5,2,2.5,3,3.5,4,4.8] if dense else [.05,2.5,4.8]
results=[]
with sync_playwright() as pw:
    browser=pw.chromium.launch(executable_path=r'C:\Program Files\Google\Chrome\Application\chrome.exe',headless=True,args=['--allow-file-access-from-files'])
    page=browser.new_page()
    page.goto((root/'output/FOOTHOLD-film-storyboard.html').as_uri())
    for filename in files:
        meta=page.evaluate('''async filename=>{
          document.querySelector('#clip-review-video')?.remove();
          const v=document.createElement('video');v.id='clip-review-video';v.muted=true;v.preload='auto';
          document.body.append(v);v.src='../assets/'+filename;
          await new Promise((resolve,reject)=>{v.onloadeddata=resolve;v.onerror=()=>reject(v.error.message)});
          await v.play();await new Promise(r=>setTimeout(r,100));v.pause();
          return {duration:v.duration,width:v.videoWidth,height:v.videoHeight,audioDecodedBytes:v.webkitAudioDecodedByteCount};
        }''',filename)
        cols=2 if dense else 3
        sheet=Image.new('RGB',(427*cols,270*((len(times)+cols-1)//cols)),(18,22,26))
        draw=ImageDraw.Draw(sheet)
        for index,t in enumerate(times):
            col,row=index%cols,index//cols
            encoded=page.evaluate('''async t=>{
              const v=document.querySelector('#clip-review-video');
              await new Promise(resolve=>{v.onseeked=resolve;v.currentTime=t;});
              const c=document.createElement('canvas');c.width=v.videoWidth;c.height=v.videoHeight;
              c.getContext('2d').drawImage(v,0,0);return c.toDataURL('image/png').split(',')[1];
            }''',min(t,meta['duration']-.05))
            im=Image.open(io.BytesIO(base64.b64decode(encoded))).convert('RGB').resize((427,240))
            sheet.paste(im,(col*427,row*270+30));draw.text((col*427+8,row*270+8),f'{filename}  {t:.2f}s',fill='white')
        out=root/'output'/('review-'+Path(filename).stem+('-dense' if dense else '')+'.jpg')
        sheet.save(out,quality=90)
        results.append({'file':filename,**meta,'sheet':out.name,'status':'sampled, not automatically approved'})
    browser.close()
print(json.dumps(results,indent=2))
(root/'assets/film-latest-clips.qa.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
