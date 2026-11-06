"""CPU decoding of an existing playlist, deterministic case selection, no new render."""
from pathlib import Path
import json,hashlib,datetime
import cv2
from PIL import Image,ImageDraw,ImageFont

OUT=Path(__file__).parent; TMP=Path('D:/mai-tmp/analyst/ex41-stage-reports-1106/media');TMP.mkdir(parents=True,exist_ok=True)
PLAYLIST=Path('C:/Users/AI-WS01/s2_lab/_playlists/EX41-ALL-stages-1106.m3u8')
b=PLAYLIST.read_bytes();paths=[Path(x.strip()) for x in b.decode('utf-8-sig').splitlines() if x.strip() and not x.startswith('#')]
rows=[];chosen={};cases=['fwd10','back10','sidem05']; font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',17)
for n in [750,2750,3750,5000]:
    for case in cases:
        matches=[p for p in paths if f'-m{n}-w57_{case}_eval_gt-1x-' in p.name]
        if not matches: rows.append({'iteration':n,'case':case,'state':'not_in_playlist'});continue
        assert len(matches)==1
        p=matches[0]; cap=cv2.VideoCapture(str(p)); count=int(cap.get(cv2.CAP_PROP_FRAME_COUNT));fps=cap.get(cv2.CAP_PROP_FPS)
        assert count and fps
        allframes=[];black=0;success=True
        for i in range(count):
            ok,frame=cap.read()
            if not ok: success=False;break
            black+=int(frame.mean()<2)
            if i%round(fps/2)==0:allframes.append((i/fps,cv2.cvtColor(frame,cv2.COLOR_BGR2RGB)))
        cap.release();assert success
        sheet=Image.new('RGB',(1600,4*248),(255,255,255));draw=ImageDraw.Draw(sheet)
        draw.text((10,8),f'm{n} / {case} / GT / every {round(fps/2)} frames / source {fps:g} fps, 1x',font=font,fill='black')
        for k,(t,im) in enumerate(allframes[:16]):
            thumb=Image.fromarray(im);thumb.thumbnail((400,218));x=(k%4)*400;y=35+(k//4)*238
            sheet.paste(thumb,(x,y));draw.text((x+6,y+218),f'{t:.2f} s',font=font,fill='black')
        dst=OUT/'figs'/f'm{n}-{case}-frames.jpg';sheet.save(dst,quality=88)
        row={'iteration':n,'case':case,'state':'decoded','path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),
             'frames':count,'fps':fps,'decoded_frames':count,'black_frames':black,'sampled_frames':len(allframes),'sheet':str(dst.relative_to(OUT))}
        rows.append(row);chosen[(n,case)]=p

cmps=[]
for left,right in [(750,2750),(2750,3750),(3750,5000)]:
    for case in cases:
        if (left,case) not in chosen or (right,case) not in chosen:continue
        out=TMP/f'CMP-EX41-m{left}-m{right}-{case}-GT-1x.mp4'
        # CPU OpenCV writer avoids local ffmpeg filter crash; no speed changes.
        import numpy as np
        a=cv2.VideoCapture(str(chosen[(left,case)]));bcap=cv2.VideoCapture(str(chosen[(right,case)]))
        fps=a.get(cv2.CAP_PROP_FPS);assert fps==bcap.get(cv2.CAP_PROP_FPS)
        writer=cv2.VideoWriter(str(out),cv2.VideoWriter_fourcc(*'mp4v'),fps,(1280,360));assert writer.isOpened()
        frames=0
        while True:
            oka,fa=a.read();okb,fb=bcap.read()
            if not oka or not okb:break
            fa=cv2.resize(fa,(640,360));fb=cv2.resize(fb,(640,360))
            for f,n in [(fa,left),(fb,right)]:
                cv2.rectangle(f,(0,0),(180,35),(0,0,0),-1)
                cv2.putText(f,f'm{n} / 1x',(8,24),cv2.FONT_HERSHEY_SIMPLEX,.6,(255,255,255),1)
            writer.write(np.concatenate([fa,fb],axis=1));frames+=1
        a.release();bcap.release();writer.release();assert frames==150
        check=cv2.VideoCapture(str(out));decoded=0
        while check.read()[0]:decoded+=1
        check.release();assert decoded==frames
        cmps.append({'left':left,'right':right,'case':case,'path':str(out),'sha256':hashlib.sha256(out.read_bytes()).hexdigest(),
                     'conditions':'same named terrain L1 and command/map mode; not the same trajectory or a paired statistical sample'})
out={'captured_at':datetime.datetime.now().astimezone().isoformat(),'playlist':str(PLAYLIST),'playlist_sha256':hashlib.sha256(b).hexdigest(),
     'playlist_counts':{str(n):sum(f'-m{n}-' in p.name for p in paths) for n in [750,2750,3750,5000]},'videos':rows,'comparisons':cmps}
(OUT/'data/media.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'counts':out['playlist_counts'],'selected':len(chosen),'cmp':len(cmps)},ensure_ascii=False))
