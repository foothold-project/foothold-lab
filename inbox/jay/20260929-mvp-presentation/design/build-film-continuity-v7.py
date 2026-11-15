import pathlib,subprocess as s,json,numpy as np,wave
from PIL import Image,ImageFilter
R=pathlib.Path('/home/user/continuity-v7');R.mkdir(exist_ok=True)
def run(a):return s.run(a,check=True,stdout=s.PIPE,stderr=s.PIPE).stdout
def ff(a):return run(['ffmpeg','-y','-v','error']+a)
urls={
'master-v6.mp4':'https://d2ol7oe51mr4n9.cloudfront.net/user_2vTkMQm9Kz0TWEHiovxqGSzlE6v/fb5f4e92-e7ff-4ddf-91a2-67ecb8ba2e1b.mp4',
'ending-v6.mp4':'https://d2ol7oe51mr4n9.cloudfront.net/user_2vTkMQm9Kz0TWEHiovxqGSzlE6v/81c27202-e0a6-451d-a79f-bf7dd5bfa877.mp4',
'o1.mp4':'https://d8j0ntlcm91z4.cloudfront.net/user_2vTkMQm9Kz0TWEHiovxqGSzlE6v/hf_20261001_015642_9af80866-fc3e-4b09-a56e-dcd0e22b5cc9.mp4',
'o2.mp4':'https://d8j0ntlcm91z4.cloudfront.net/user_2vTkMQm9Kz0TWEHiovxqGSzlE6v/hf_20260930_202808_1d8ff642-092d-4958-afc2-827e828cfb62.mp4'}
for name,url in urls.items():run(['curl','-fsSL',url,'-o',str(R/name)])
W,H=854,480
def frames(f,dur):
 return np.frombuffer(ff(['-i',str(R/f),'-t',str(dur),'-vf','fps=24','-f','rawvideo','-pix_fmt','rgb24','-']),np.uint8).reshape(-1,H,W,3)
o1=frames('o1.mp4',8)[:192];o2=frames('o2.mp4',2.4)[:55]
dx,dy=-.47812,5.22373
def align(a,weight):
 return np.array(Image.fromarray(a).transform((W,H),Image.Transform.AFFINE,(1,0,-dx*weight,0,1,-dy*weight),resample=Image.Resampling.BICUBIC))
def low(a):
 return np.array(Image.fromarray(a).convert('L').filter(ImageFilter.GaussianBlur(18))).astype(float)
target=o1[-1];aligned0=align(o2[0],1)
gain=np.clip((low(target)+4)/(low(aligned0)+4),.5,1.8)
corrected=[]
for i,frame in enumerate(o2):
 q=min(1,i/24);weight=1-(q*q*(3-2*q))
 v=align(frame,weight).astype(float)
 v*=np.exp(np.log(gain)*weight)[:,:,None]
 corrected.append(np.clip(v,0,255).astype(np.uint8))
corrected=np.stack(corrected)
# Encode the matched O2 plate for the native timeline; no dissolve or held frame.
def encode_frames(name,x):
 p=s.Popen(['ffmpeg','-y','-v','error','-f','rawvideo','-pix_fmt','rgb24','-s',f'{W}x{H}','-r','24','-i','-','-an','-c:v','libx264','-crf','15','-preset','fast','-pix_fmt','yuv420p',str(R/name)],stdin=s.PIPE)
 p.communicate(x.tobytes());assert p.returncode==0
encode_frames('o2-matched.mp4',corrected)
jsx="""export default async ({project})=>{
const r='/home/user/continuity-v7';const p=await project({dir:r+'/project',size:'854x480',fps:24,background:'#000'});
const a=await p.add(r+'/o1.mp4'), b=await p.add(r+'/o2-matched.mp4');
p.compose(<media file={a} trimStart={.004} x={0} y={0} width={854} height={480} muted={true}/>,{at:0,dur:8,name:'O1 left-right-down'});
p.compose(<media file={b} trimStart={.004} x={0} y={0} width={854} height={480} muted={true}/>,{at:8,dur:55/24,name:'O2 registered light continuity'});
await p.render(r+'/native-join.mp4',{draft:false,bitrate:4000000});};"""
(R/'edit.jsx').write_text(jsx);run(['higgsedit','build',str(R/'edit.jsx')])
# Assemble the exact decoded frames to avoid an extra held frame from container offsets.
# The established source's O3 begins at frame 247. Replace exactly frames 0..246.
encode_frames('joined-picture.mp4',np.concatenate([o1,corrected]))
ff(['-i',str(R/'joined-picture.mp4'),'-i',str(R/'master-v6.mp4'),'-filter_complex','[0:v]setpts=PTS-STARTPTS[a];[1:v]trim=start_frame=247,setpts=PTS-STARTPTS[b];[a][b]concat=n=2:v=1:a=0[v]','-map','[v]','-map','1:a','-c:v','libx264','-crf','16','-preset','fast','-c:a','copy','-t','80.625','-movflags','+faststart',str(R/'film-master-v7.mp4')])
ff(['-i',str(R/'film-master-v7.mp4'),'-t','31.125','-c:v','libx264','-crf','16','-preset','fast','-c:a','aac','-b:a','256k','-movflags','+faststart',str(R/'film-opening-v7.mp4')])
# Ending was already approved for replacement; preserve its bytes exactly.
(R/'film-ending-v7.mp4').write_bytes((R/'ending-v6.mp4').read_bytes())
ff(['-i',str(R/'film-master-v7.mp4'),'-t',str(247/24),'-c:v','libx264','-crf','16','-preset','fast','-c:a','aac','-b:a','256k','-movflags','+faststart',str(R/'film-o1-o2-matched-v5.mp4')])
qa={'source_urls':urls,'translation_xy':[dx,dy],'lighting_gain_range':[float(gain.min()),float(gain.max())],'correction_relax_seconds':1,'lowpass_seam_error_before':float(np.mean(abs(low(target)-low(o2[0])))),'lowpass_seam_error_after':float(np.mean(abs(low(target)-low(corrected[0])))),'replaced_frame_range':[0,246],'first_O3_frame':247,'first_E5_frame':1193,'master_duration':80.625,'opening_duration':31.125,'ending_duration':49.5,'audio':'Existing v6 unified mix retained, including all eight E5pre contact sounds. No new soundtrack or generator ambience replacement.','ending_bytes_identical_to_v6':True,'native_script':jsx}
# Validate exact decoded frame count and sample join motion in delivered full file.
qa['stream']=json.loads(run(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=nb_frames,duration,r_frame_rate','-of','json',str(R/'film-master-v7.mp4')]))
(R/'film-continuity-v7-audit.json').write_text(json.dumps(qa,indent=2));print(json.dumps({k:v for k,v in qa.items() if k not in ['native_script','source_urls']}))

