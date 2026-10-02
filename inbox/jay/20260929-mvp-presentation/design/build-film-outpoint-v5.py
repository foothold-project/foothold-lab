import pathlib,subprocess as s,json,numpy as np,wave
R=pathlib.Path('/home/user/e5-out-v5');R.mkdir(exist_ok=True)
def run(a):return s.run(a,check=True,stdout=s.PIPE,stderr=s.PIPE).stdout
def ff(a):return run(['ffmpeg','-y','-v','error']+a)
if not (R/'master-v4.mp4').exists():run(['curl','-fsSL','https://d2ol7oe51mr4n9.cloudfront.net/user_2vTkMQm9Kz0TWEHiovxqGSzlE6v/889bf76b-9aee-4280-9cf2-d12694b7d0e7.mp4','-o',str(R/'master-v4.mp4')])
# Physical source frame 1207 is the first E5 frame. Two POV tail frames: 1205,1206.
fps=24;cut=1207/24;delta=2/24;newcut=cut-delta
# Native edit holds the explicit 0/1/2 frame comparison and final picture timeline.
jsx="""export default async ({project})=>{
const r='/home/user/e5-out-v5';const src=r+'/master-v4.mp4';
const p=await project({dir:r+'/master-project',size:'854x480',fps:24,background:'#000'});const m=await p.add(src);
p.compose(<media file={m} trimStart={0} x={0} y={0} width={854} height={480} muted={true}/>,{at:0,dur:1205/24,name:'Before shortened POV out'});
p.compose(<media file={m} trimStart={1207/24+.004} x={0} y={0} width={854} height={480} muted={true}/>,{at:1205/24,dur:(1949-1207)/24,name:'E5 and remaining ending'});
await p.render(r+'/picture-v5.mp4',{draft:false,bitrate:4500000});
const q=await project({dir:r+'/comparison-project',size:'854x480',fps:24,background:'#000'});const a=await q.add(src);
for(const [i,n] of [0,1,2].entries()){
const at=i*7.5,begin=47.5,tail=1207/24-n/24;
q.compose(<media file={a} trimStart={begin+.004} x={0} y={0} width={854} height={480} muted={true}/>,{at,dur:tail-begin,name:'POV '+n});
q.compose(<media file={a} trimStart={1207/24+.004} x={0} y={0} width={854} height={480} muted={true}/>,{at:at+tail-begin,dur:7-(tail-begin),name:'Climb '+n});
q.compose(<group><rect x={12} y={12} width={255} height={34} fill="#06131d" opacity={.85}/><text x={22} y={19} width={240} height={22} fontFamily="Metropolis" fontSize={18} color="#fff">{['ORIGINAL','POV OUT -1 FRAME','POV OUT -2 FRAMES'][i]}</text></group>,{at,dur:7,name:'Label '+n});
}
await q.render(r+'/compare-picture.mp4',{draft:false,bitrate:3500000});
};"""
(R/'edit.jsx').write_text(jsx)
run(['higgsedit','build',str(R/'edit.jsx')])
sr=48000
base=np.frombuffer(ff(['-i',str(R/'master-v4.mp4'),'-vn','-ar',str(sr),'-ac','2','-f','f32le','-']),dtype='<f4').reshape(-1,2).copy()
# Audio follows the same ripple. A 4ms local fade avoids a waveform discontinuity.
def trim(n):
 b=round(cut*sr);a=b-round(n/fps*sr)
 out=np.concatenate([base[:a],base[b:]])
 if n:
  k=round(.004*sr);out[a-k:a]*=np.linspace(1,0,k)[:,None];out[a:a+k]*=np.linspace(0,1,k)[:,None]
 return out
def wav(name,a):
 with wave.open(str(R/name),'wb') as w:
  w.setparams((2,2,sr,0,'NONE','none'));w.writeframes((np.clip(a,-1,1)*32767).astype('<i2').tobytes())
new=trim(2);wav('mix.wav',new)
ff(['-i',str(R/'picture-v5.mp4'),'-i',str(R/'mix.wav'),'-map','0:v','-map','1:a','-c:v','copy','-c:a','aac','-b:a','256k','-t',str(1947/24),'-movflags','+faststart',str(R/'film-master-v5.mp4')])
ff(['-i',str(R/'film-master-v5.mp4'),'-ss','31.125','-t','50','-c:v','libx264','-crf','17','-preset','fast','-c:a','aac','-b:a','256k','-movflags','+faststart',str(R/'film-ending-v5.mp4')])
parts=[]
for n in [0,1,2]:
 a=trim(n);start=round(47.5*sr);parts.append(a[start:start+7*sr])
 if n<2:parts.append(np.zeros((sr//2,2)))
wav('comparison.wav',np.concatenate(parts))
ff(['-i',str(R/'compare-picture.mp4'),'-i',str(R/'comparison.wav'),'-map','0:v','-map','1:a','-c:v','copy','-c:a','aac','-b:a','256k','-movflags','+faststart',str(R/'film-e5pre-outpoint-comparison-v5.mp4')])
qa={'source':'film-master-v4.mp4','fps':24,'removed_source_frame_indices':[1205,1206],'first_e5_source_frame':1207,'removed_seconds':delta,'new_e5_frame_index':1205,'audio':'Same v4 mix ripple trimmed with 4ms seam fade. Footstep contacts precede removed interval.','comparison':'Original / minus 1 frame / minus 2 frames, seven seconds each, half second black gaps','native_script':jsx,'status':'Review candidate; not user approved'}
(R/'film-outpoint-v5-audit.json').write_text(json.dumps(qa,indent=2));print(json.dumps({k:v for k,v in qa.items() if k!='native_script'}))

