from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import json,av,numpy as np
from PIL import Image
ROOT=Path(__file__).resolve().parent
segments=json.loads((ROOT/'v4-segments.json').read_text(encoding='utf-8'))
web=ROOT/'v4-web-frames';web.mkdir(exist_ok=True)
paths=sorted((ROOT/'v4-frames').glob('*.png'))
assert len(paths)==432,len(paths)
def webp(path):
    Image.open(path).save(web/(path.stem+'.webp'),quality=88,method=3)
with ThreadPoolExecutor(max_workers=6) as ex:list(ex.map(webp,paths))
videos=[]
for seg in segments:
    files=[ROOT/'v4-frames'/f"{seg['id']}-{f:04d}.png" for f in range(seg['start'],seg['end']+1)]
    outpath=ROOT/('go2-'+seg['id']+'-v4.mp4');out=av.open(str(outpath),'w')
    st=out.add_stream('libx264',rate=24);st.width=960;st.height=720;st.pix_fmt='yuv420p';st.options={'crf':'19','preset':'medium'}
    for p in files:
        im=Image.open(p).convert('RGBA');bg=Image.new('RGB',im.size,'#f6f5f1');bg.paste(im,mask=im.getchannel('A'))
        vf=av.VideoFrame.from_ndarray(np.array(bg),format='rgb24')
        for packet in st.encode(vf):out.mux(packet)
    for packet in st.encode():out.mux(packet)
    out.close()
    with av.open(str(outpath)) as container:
        n=sum(1 for _ in container.decode(video=0));rate=str(container.streams.video[0].average_rate)
    assert n==len(files)
    seg.update({'pattern':f"v4-web-frames/{seg['id']}-{{frame:04d}}.webp",'fps':24,'width':960,'height':720,'poster':f"go2-{seg['id']}-v4.png",'preview':outpath.name,'verifiedFrames':n,'verifiedRate':rate})
    videos.append({'id':seg['id'],'frames':n,'duration':n/24})
manifest={'version':4,'source':'go2-technical-v4.blend','states':{'front':{'image':'go2-front-v4.png','width':1600,'height':1600},'three_axes':{'image':'go2-three-axes-v4.png','width':1280,'height':960},'single_leg':{'image':'go2-fl-leg-v4.png','width':1280,'height':960},'twelve_axes':{'image':'go2-twelve-axes-v4.png','width':1280,'height':960}},'segments':{s['id']:s for s in segments},'anchors':'v4-sensor-and-joint-anchors.json','caveat':'Explanatory kinematic animation. Not an Isaac policy rollout or calibrated sensor measurement.'}
(ROOT/'v4-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
(ROOT/'v4-manifest.js').write_text('window.GO2_TECHNICAL_MANIFEST='+json.dumps(manifest,ensure_ascii=False)+';\n',encoding='utf-8')
(ROOT/'v4-video-verification.json').write_text(json.dumps(videos,indent=2))
print(json.dumps({'segments':len(segments),'frames':len(paths),'webpBytes':sum(p.stat().st_size for p in web.glob('*.webp'))}))
