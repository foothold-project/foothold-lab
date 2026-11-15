from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import json,av,numpy as np,sys
from PIL import Image

ROOT=Path(__file__).resolve().parent
web=ROOT/'v5-web-frames';web.mkdir(exist_ok=True)
files=sorted((ROOT/'v5-frames').glob('frame-*.png'))
assert len(files)==289,len(files)
def convert(p):Image.open(p).save(web/(p.stem+'.webp'),quality=90,method=3)
metadata_only='--metadata-only' in sys.argv
if not metadata_only:
    with ThreadPoolExecutor(max_workers=6) as pool:list(pool.map(convert,files))
def video(name,paths):
    path=ROOT/name;out=av.open(str(path),'w');st=out.add_stream('libx264',rate=24)
    st.width=960;st.height=720;st.pix_fmt='yuv420p';st.options={'crf':'19','preset':'medium'}
    for p in paths:
        im=Image.open(p).convert('RGBA');bg=Image.new('RGB',im.size,'#f6f5f1');bg.paste(im,mask=im.getchannel('A'))
        for packet in st.encode(av.VideoFrame.from_ndarray(np.array(bg),format='rgb24')):out.mux(packet)
    for packet in st.encode():out.mux(packet)
    out.close()
    with av.open(str(path)) as src:n=sum(1 for _ in src.decode(video=0))
    assert n==len(paths)
    return {'file':name,'frames':n,'fps':24}
videos=json.loads((ROOT/'v5-video-verification.json').read_text()) if metadata_only else [video('go2-continuous-v5-preview.mp4',files)]
anchors=json.loads((ROOT/'v5-static-anchors.json').read_text())
states={name:{'image':f'go2-{name}-v5.png','frame':row['frame'],'width':1600,'height':1200,'anchors':row} for name,row in anchors.items()}
segments=json.loads((ROOT/'v5-segments.json').read_text())
endstates={'turntable':'three_quarter','four_legs':'four_legs','assemble':'assembled','to_side':'side_grid','scan':'scan'}
for seg in segments:
    seg.update({'pattern':'v5-web-frames/frame-{frame:04d}.webp','width':960,'height':720,'fps':24,'endState':endstates[seg['id']]})
    if not metadata_only:videos.append(video('go2-'+seg['id']+'-v5-preview.mp4',files[seg['start']-1:seg['end']]))
manifest={'version':5,'canvas':{'width':1600,'height':1200},'source':'go2-continuous-v5.blend','states':states,'segments':{seg['id']:seg for seg in segments},'frameAnchors':'v5-frame-anchors.json','preview':'go2-continuous-v5-preview.mp4','notes':'Actual USD geometry. Assembly motion and 187-point teaching grid are explanatory, not a recorded policy rollout. Transparent WebP frames; preview video uses paper background.'}
(ROOT/'v5-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
(ROOT/'v5-manifest.js').write_text('window.GO2_V5_MANIFEST='+json.dumps(manifest,ensure_ascii=False)+';\n',encoding='utf-8')
frame_anchors=json.loads((ROOT/'v5-frame-anchors.json').read_text())
(ROOT/'v5-frame-anchors.js').write_text('window.GO2_V5_FRAME_ANCHORS='+json.dumps(frame_anchors,separators=(',',':'))+';\n',encoding='utf-8')
(ROOT/'v5-video-verification.json').write_text(json.dumps(videos,indent=2),encoding='utf-8')
print(json.dumps({'files':len(files),'webpBytes':sum(p.stat().st_size for p in web.glob('*.webp')),'videos':videos}))
