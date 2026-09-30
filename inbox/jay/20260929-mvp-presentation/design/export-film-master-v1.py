import json,subprocess,zipfile
from pathlib import Path
from PIL import Image,ImageDraw
r=Path('/home/user/foothold-master');p=json.loads((r/'plan.json').read_text())
def ff(args):subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y']+args,check=True)
ff(['-i',str(r/'picture.mp4'),'-i',str(r/'mix.wav'),'-map','0:v:0','-map','1:a:0','-c:v','copy','-c:a','aac','-b:a','192k','-movflags','+faststart','-t',str(p['total']),str(r/'master.mp4')])
for name,start,dur in [('opening',0,p['split']),('ending',p['split'],p['total']-p['split'])]:
 ff(['-ss',str(start),'-i',str(r/'master.mp4'),'-t',str(dur),'-c:v','libx264','-preset','fast','-crf','18','-c:a','aac','-b:a','192k','-movflags','+faststart',str(r/(name+'.mp4'))])
times=[.1,2.5,4.5,7.5,next(c['at'] for c in p['clips'] if c['shot']=='O5')+2,p['split'],next(c['at'] for c in p['clips'] if c['shot']=='E5pre')+2,p['e7']+2.5,p['e7']+3.5,p['total']-.12]
sheet=Image.new('RGB',(1065,725),(14,18,20));d=ImageDraw.Draw(sheet)
for i,t in enumerate(times):
 path=r/('qa-'+str(i)+'.png')
 ff(['-ss',str(t),'-i',str(r/'master.mp4'),'-frames:v','1',str(path)])
 im=Image.open(path).convert('RGB').resize((355,200));x=(i%3)*355;y=(i//3)*181
 # Use 177px-high thumbnails to keep a compact 4-row contact sheet.
 im=im.resize((315,177));sheet.paste(im,(x,y+4));d.text((x+5,y+5),str(round(t,2))+'s',fill='white')
sheet.save(r/'qa.jpg',quality=92)
with zipfile.ZipFile(r/'project.zip','w',zipfile.ZIP_DEFLATED) as z:
 for base in ['project']:
  for f in (r/base).rglob('*'):
   if f.is_file():z.write(f,f.relative_to(r))
 for f in ['edit.jsx','plan.json','sound.py','sound-design.json','mix.wav']:z.write(r/f,f)
print(json.dumps({'total':p['total'],'opening':p['split'],'ending':p['total']-p['split'],'outputs':[x.name for x in r.glob('*.mp4')]}),flush=True)
