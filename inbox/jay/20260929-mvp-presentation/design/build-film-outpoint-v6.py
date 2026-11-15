import pathlib,subprocess as s,json,numpy as np,wave
R=pathlib.Path('/home/user/e5-out-v6');R.mkdir(exist_ok=True)
def run(a):return s.run(a,check=True,stdout=s.PIPE,stderr=s.PIPE).stdout
def ff(a):return run(['ffmpeg','-y','-v','error']+a)
for name,url in {'master-v4.mp4':'https://d2ol7oe51mr4n9.cloudfront.net/user_2vTkMQm9Kz0TWEHiovxqGSzlE6v/889bf76b-9aee-4280-9cf2-d12694b7d0e7.mp4','master-v5.mp4':'https://d2ol7oe51mr4n9.cloudfront.net/user_2vTkMQm9Kz0TWEHiovxqGSzlE6v/082bd1d8-17ea-4e94-b4d5-48065a95c3b7.mp4'}.items():run(['curl','-fsSL',url,'-o',str(R/name)])
sr=48000;fps=24;out_frame=1193;old_in=1207;removed=14
def pcm(f):return np.frombuffer(ff(['-i',str(R/f),'-vn','-ar',str(sr),'-ac','2','-f','f32le','-']),dtype='<f4').reshape(-1,2).copy()
base=pcm('master-v4.mp4');a=out_frame*2000;b=old_in*2000;mix=np.concatenate([base[:a],base[b:]])
k=192;mix[a-k:a]*=np.linspace(1,0,k)[:,None];mix[a:a+k]*=np.linspace(0,1,k)[:,None]
def wav(name,x):
 with wave.open(str(R/name),'wb') as w:w.setparams((2,2,sr,0,'NONE','none'));w.writeframes((np.clip(x,-1,1)*32767).astype('<i2').tobytes())
wav('mix.wav',mix)
# Preserve exactly the selected source frames; no speed change, held frame or dissolve.
ff(['-i',str(R/'master-v4.mp4'),'-i',str(R/'mix.wav'),'-map','0:v','-map','1:a','-vf',"select='lt(n,1193)+gte(n,1207)',setpts=N/(24*TB)",'-r','24','-c:v','libx264','-crf','16','-preset','fast','-c:a','aac','-b:a','256k','-t',str((1949-14)/24),'-movflags','+faststart',str(R/'film-master-v6.mp4')])
ff(['-i',str(R/'film-master-v6.mp4'),'-ss','31.125','-t','49.5','-c:v','libx264','-crf','16','-preset','fast','-c:a','aac','-b:a','256k','-movflags','+faststart',str(R/'film-ending-v6.mp4')])
jsx="""export default async ({project})=>{
const r='/home/user/e5-out-v6';const p=await project({dir:r+'/comparison-project',size:'854x480',fps:24,background:'#000'});
for(const [label,file,at] of [['PREVIOUS -2 FRAMES','master-v5.mp4',0],['HOLD REMOVED','film-master-v6.mp4',7.5]]){
const m=await p.add(r+'/'+file);
p.compose(<media file={m} trimStart={47.5+.004} x={0} y={0} width={854} height={480} muted={true}/>,{at,dur:7,name:label});
p.compose(<group><rect x={12} y={12} width={260} height={34} fill="#06131d" opacity={.85}/><text x={22} y={19} width={240} height={22} fontFamily="Metropolis" fontSize={18} color="#fff">{label}</text></group>,{at,dur:7,name:label+' title'});
}await p.render(r+'/comparison-picture.mp4',{draft:false,bitrate:3500000});};"""
(R/'edit.jsx').write_text(jsx);run(['higgsedit','build',str(R/'edit.jsx')])
before=pcm('master-v5.mp4');start=round(47.5*sr);dur=7*sr
wav('comparison.wav',np.concatenate([before[start:start+dur],np.zeros((sr//2,2)),mix[start:start+dur]]))
ff(['-i',str(R/'comparison-picture.mp4'),'-i',str(R/'comparison.wav'),'-map','0:v','-map','1:a','-c:v','copy','-c:a','aac','-b:a','256k','-movflags','+faststart',str(R/'film-e5pre-outpoint-comparison-v6.mp4')])
# Measure delivered frames, including the join, to ensure the almost-held tail is gone.
x=np.frombuffer(ff(['-i',str(R/'film-master-v6.mp4'),'-vf','select=between(n\\,1186\\,1197),scale=214:120,format=gray','-fps_mode','passthrough','-f','rawvideo','-']),np.uint8).reshape(-1,120,214)
d=[dict(frame=1187+i,mean_abs_change=float(np.abs(x[i+1].astype(float)-x[i]).mean())) for i in range(len(x)-1)]
qa={'source':'film-master-v4.mp4','rejected':'v5 -2 frames leaves near-static tail','removed_source_frames':[1193,1206],'removed_count':14,'removed_seconds':14/24,'first_e5_frame':1193,'last_contact_global_seconds':49.37,'last_contact_tail_seconds':49.575,'outpoint_seconds':1193/24,'delivered_frame_change':d,'native_comparison_script':jsx,'status':'Review candidate, not approved'}
(R/'film-outpoint-v6-audit.json').write_text(json.dumps(qa,indent=2));print(json.dumps(d))

