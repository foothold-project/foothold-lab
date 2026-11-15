import pathlib,subprocess as s,json,numpy as np,hashlib
from PIL import Image
R=pathlib.Path('/home/user/e5-transition-v8');R.mkdir(exist_ok=True)
def run(a):return s.run(a,check=True,stdout=s.PIPE,stderr=s.PIPE).stdout
def ff(a):return run(['ffmpeg','-y','-v','error']+a)
url='https://d2ol7oe51mr4n9.cloudfront.net/user_2vTkMQm9Kz0TWEHiovxqGSzlE6v/58d3bc1f-d674-4c39-adb9-3d9e804103b4.mp4'
run(['curl','-fsSL',url,'-o',str(R/'master-v7.mp4')])
W,H=854,480;first=1193;count=20
raw=ff(['-i',str(R/'master-v7.mp4'),'-vf','select=between(n\\,1193\\,1212)','-fps_mode','passthrough','-f','rawvideo','-pix_fmt','rgb24','-'])
src=np.frombuffer(raw,np.uint8).reshape(-1,H,W,3);assert len(src)==count
out=[];params=[]
for i,frame in enumerate(src):
 q=i/(count-1);w=1-q*q*(3-2*q);scale=1+.18*w;x=-60*w;y=-64*w
 im=Image.fromarray(frame).transform((W,H),Image.Transform.AFFINE,(1/scale,0,-x/scale,0,1/scale,-y/scale),resample=Image.Resampling.BICUBIC)
 out.append(np.array(im));params.append({'frame':first+i,'scale':scale,'x':x,'y':y})
p=s.Popen(['ffmpeg','-y','-v','error','-f','rawvideo','-pix_fmt','rgb24','-s','854x480','-r','24','-i','-','-an','-c:v','libx264','-crf','15','-preset','fast','-pix_fmt','yuv420p',str(R/'patch.mp4')],stdin=s.PIPE)
p.communicate(np.stack(out).tobytes());assert p.returncode==0
ff(['-i',str(R/'master-v7.mp4'),'-i',str(R/'patch.mp4'),'-filter_complex','[0:v]split=2[a][b];[a]trim=end_frame=1193,setpts=PTS-STARTPTS[head];[1:v]setpts=PTS-STARTPTS[patch];[b]trim=start_frame=1213,setpts=PTS-STARTPTS[tail];[head][patch][tail]concat=n=3:v=1:a=0[v]','-map','[v]','-map','0:a','-c:v','libx264','-crf','16','-preset','fast','-c:a','copy','-t','80.625','-movflags','+faststart',str(R/'film-master-v8.mp4')])
ff(['-i',str(R/'film-master-v8.mp4'),'-ss','31.125','-t','49.5','-c:v','libx264','-crf','16','-preset','fast','-c:a','aac','-b:a','256k','-movflags','+faststart',str(R/'film-ending-v8.mp4')])
ff(['-i',str(R/'film-master-v8.mp4'),'-ss','47.5','-t','6','-c:v','libx264','-crf','16','-preset','fast','-c:a','aac','-b:a','256k','-movflags','+faststart',str(R/'film-e5-transition-v8.mp4')])
jsx="""export default async ({project})=>{
const r='/home/user/e5-transition-v8';const p=await project({dir:r+'/comparison-project',size:'854x480',fps:24,background:'#000'});
for(const [label,file,at] of [['BEFORE','master-v7.mp4',0],['AFTER','film-master-v8.mp4',6.5]]){
const m=await p.add(r+'/'+file);p.compose(<media file={m} trimStart={47.504} x={0} y={0} width={854} height={480} muted={true}/>,{at,dur:6,name:label});
p.compose(<group><rect x={12} y={12} width={130} height={34} fill="#06131d" opacity={.85}/><text x={22} y={19} width={114} height={22} fontFamily="Metropolis" fontSize={18} color="#fff">{label}</text></group>,{at,dur:6,name:label+' title'});
}await p.render(r+'/compare-picture.mp4',{draft:false,bitrate:3500000});};"""
(R/'edit.jsx').write_text(jsx);run(['higgsedit','build',str(R/'edit.jsx')])
# Identical six-second audio on both halves: only visual continuity is under review.
ff(['-i',str(R/'master-v7.mp4'),'-filter_complex','[0:a]atrim=start=47.5:end=53.5,asetpts=PTS-STARTPTS,asplit=2[a][b];anullsrc=r=48000:cl=stereo,atrim=duration=0.5[z];[a][z][b]concat=n=3:v=0:a=1[m]','-map','[m]','-c:a','pcm_s16le',str(R/'compare.wav')])
ff(['-i',str(R/'compare-picture.mp4'),'-i',str(R/'compare.wav'),'-map','0:v','-map','1:a','-c:v','copy','-c:a','aac','-b:a','256k','-movflags','+faststart',str(R/'film-e5-transition-comparison-v8.mp4')])
def audiohash(f):return hashlib.sha256(ff(['-i',str(R/f),'-map','0:a','-c','copy','-f','adts','-'])).hexdigest()
a,b=audiohash('master-v7.mp4'),audiohash('film-master-v8.mp4')
qa={'source_url':url,'changed_frames':[1193,1212],'changed_seconds':[1193/24,1213/24],'method':'Reframe first 20 E5 frames to align target cabinet with outgoing POV. Smoothly release to native rear view. No dissolve, hold, optical-flow or speed change.','parameters':params,'audio_bitstream_preserved':a==b,'audio_sha256':b,'master_frames':1935,'duration_seconds':80.625,'ending_duration_seconds':49.5,'opening_unchanged':'film-opening-v7.mp4','native_comparison_script':jsx}
assert a==b,'Audio changed unexpectedly'
(R/'film-e5-transition-v8-audit.json').write_text(json.dumps(qa,indent=2));print(json.dumps({k:v for k,v in qa.items() if k not in ['parameters','native_comparison_script']}))

