"""CPU frame extraction for declared sampling intervals, without modifying sources."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import numpy as np
from PIL import Image, ImageDraw, ImageFont

p=argparse.ArgumentParser()
p.add_argument('video');p.add_argument('out');p.add_argument('--fps',type=float,default=2)
p.add_argument('--start',type=float,default=0);p.add_argument('--duration',type=float,default=12)
p.add_argument('--width',type=int,default=480);p.add_argument('--cols',type=int,default=4)
a=p.parse_args();src=Path(a.video);out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-count_frames','-show_entries','stream=width,height,nb_read_frames,r_frame_rate:format=duration','-of','json',str(src)]))
s=probe['streams'][0];w=a.width;h=round(w*s['height']/s['width']);h+=h%2
cmd=['ffmpeg','-hide_banner','-loglevel','error','-nostdin','-ss',str(a.start),'-i',str(src),'-t',str(a.duration),'-vf',f'fps={a.fps},scale={w}:{h}', '-f','rawvideo','-pix_fmt','rgb24','pipe:1']
raw=subprocess.check_output(cmd);frames=np.frombuffer(raw,dtype=np.uint8).reshape(-1,h,w,3)
expected=round(a.duration*a.fps);assert len(frames)==expected,(len(frames),expected)
font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',18)
pages=[]
for base in range(0,len(frames),24):
    part=frames[base:base+24];rows=(len(part)+a.cols-1)//a.cols
    grid=Image.new('RGB',(w*a.cols,(h+30)*rows),'#f4f4f0');d=ImageDraw.Draw(grid)
    for j,frame in enumerate(part):
        x=j%a.cols*w;y=j//a.cols*(h+30);grid.paste(Image.fromarray(frame),(x,y+30))
        d.text((x+8,y+4),f'{a.start+(base+j)/a.fps:.2f} s',font=font,fill='#14222b')
    name=f'grid_{base//24:02d}.jpg';grid.save(out/name,quality=93);pages.append(name)
(out/'frames.json').write_text(json.dumps({'source':str(src.resolve()),'sha256':hashlib.sha256(src.read_bytes()).hexdigest(),'probe':probe,'sample_fps':a.fps,'start':a.start,'duration':a.duration,'sampled_frames':len(frames),'pages':pages},indent=2),encoding='utf-8')
print(json.dumps({'sampled_frames':len(frames),'grids':[str(out/n) for n in pages]}))
