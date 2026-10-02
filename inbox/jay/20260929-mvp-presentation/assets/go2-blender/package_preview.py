from pathlib import Path
import json,av,numpy as np
from PIL import Image
ROOT=Path(__file__).resolve().parent
files=sorted((ROOT/'frames').glob('frame-*.png'))
assert len(files)==264,len(files)
web=ROOT/'web-frames';web.mkdir(exist_ok=True)
out=av.open(str(ROOT/'go2-spec-preview.mp4'),'w')
stream=out.add_stream('libx264',rate=24);stream.width=640;stream.height=480;stream.pix_fmt='yuv420p';stream.options={'crf':'19','preset':'medium'}
for i,path in enumerate(files):
    im=Image.open(path).convert('RGBA');im.save(web/f'frame-{i+1:04d}.webp',quality=88,method=6)
    bg=Image.new('RGB',im.size,'#f6f5f1');bg.paste(im,mask=im.getchannel('A'))
    frame=av.VideoFrame.from_ndarray(np.array(bg),format='rgb24')
    for packet in stream.encode(frame):out.mux(packet)
for packet in stream.encode():out.mux(packet)
out.close()
with av.open(str(ROOT/'go2-spec-preview.mp4')) as f:
    frames=list(f.decode(video=0));count=len(frames);rate=str(f.streams.video[0].average_rate)
assert count==264
manifest={'framePattern':'web-frames/frame-{frame:04d}.webp','frameCount':264,'fps':24,'size':[640,480],'stops':[1,96,156,216,240],'labels':['정면','턴테이블','강체 링크 분리','재조립','12개 관절'],'preview':'go2-spec-preview.mp4','source':'go2-presentation-v3.blend','kind':'USD-based kinematic illustration, not learned policy rollout','validatedFrames':count,'validatedRate':rate}
(ROOT/'playback-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(manifest,ensure_ascii=False))
