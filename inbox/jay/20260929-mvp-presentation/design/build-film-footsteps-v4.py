import subprocess as sp, json, numpy as np, wave, pathlib, hashlib
R=pathlib.Path('/home/user/e5-contact-v4'); R.mkdir(exist_ok=True)
urls={
'master-v3.mp4':'https://d2ol7oe51mr4n9.cloudfront.net/user_2vTkMQm9Kz0TWEHiovxqGSzlE6v/d75cfc3a-d42c-4aea-9c22-60d343c60256.mp4',
'ending-v3.mp4':'https://d2ol7oe51mr4n9.cloudfront.net/user_2vTkMQm9Kz0TWEHiovxqGSzlE6v/3b13ea35-5e83-4892-b712-0656c350a91b.mp4',
'e4.mp4':'https://d8j0ntlcm91z4.cloudfront.net/user_2vTkMQm9Kz0TWEHiovxqGSzlE6v/hf_20260930_203205_2e241d00-5897-43dc-a4e1-bb91dfbc70f8.mp4',
'e5.mp4':'https://d8j0ntlcm91z4.cloudfront.net/user_2vTkMQm9Kz0TWEHiovxqGSzlE6v/hf_20260930_203204_66633ecd-c928-4165-b344-9b001b894dd6.mp4'}
def run(a): return sp.run(a,check=True,stdout=sp.PIPE,stderr=sp.PIPE).stdout
def ff(a): return run(['ffmpeg','-y','-v','error']+a)
for name,url in urls.items(): run(['curl','-fsSL',url,'-o',str(R/name)])
sr=48000
def pcm(file,filters=None):
 a=['-i',str(R/file),'-vn']
 if filters:a+=['-af',filters]
 return np.frombuffer(ff(a+['-ar',str(sr),'-ac','2','-f','f32le','-']),dtype='<f4').reshape(-1,2).copy()
def wav(file,x):
 with wave.open(str(R/file),'wb') as w:
  w.setparams((2,2,sr,0,'NONE','not compressed'));w.writeframes((np.clip(x,-1,1)*32767).astype('<i2').tobytes())
src={k:pcm(k+'.mp4','highpass=f=100,lowpass=f=6500') for k in ['e4','e5']}
beats=[.28,.78,1.29,1.86,2.38,2.97,3.53,4.12]
choices=[('e4',1.23),('e5',.83),('e4',2.67),('e5',1.86),('e4',3.03),('e5',2.8),('e4',1.23),('e5',1.86)]
gains=[1,.90,1.04,.94,1,.94,.86,.78]
events=[]
for i,((key,t),beat,gain) in enumerate(zip(choices,beats,gains)):
 x=src[key][round((t-.035)*sr):round((t+.205)*sr)].copy()
 n=len(x);env=np.ones(n);fade=round(.010*sr);tail=round(.105*sr)
 env[:fade]=np.linspace(0,1,fade);env[-tail:]=np.linspace(1,0,tail)**1.5
 x*=env[:,None]
 rms=float(np.sqrt(np.mean(x*x)));x*=min(2.5,.065/max(rms,1e-9))*gain
 wav(f'contact-{i}.wav',x)
 events.append(dict(index=i,source=key,source_peak=t,contact_at=beat,start=beat-.035,gain=gain,rms=float(np.sqrt(np.mean(x*x)))))
(R/'events.json').write_text(json.dumps(dict(events=events,source_urls=urls,note='Contact alignment follows authored POV camera keyframes, not physical telemetry.'),indent=2))
jsx="""export default async ({project})=>{
const r='/home/user/e5-contact-v4';const p=await project({dir:r+'/contact-project',size:'320x180',fps:24,background:'#000'});
p.compose(<rect x={0} y={0} width={320} height={180} fill="#000"/>,{at:0,dur:5,name:'Contact stem'});
"""
for e in events:
 jsx+=f"const a{e['index']}=await p.add(r+'/contact-{e['index']}.wav');p.cut(a{e['index']},{{at:{e['start']},from:0,dur:.24}});\n"
jsx+="await p.render(r+'/contact-stem.mp4',{draft:false,bitrate:200000});};"
(R/'contact-edit.jsx').write_text(jsx)
run(['higgsedit','build',str(R/'contact-edit.jsx')])
base=pcm('master-v3.mp4');stem=pcm('contact-stem.mp4')
out=base.copy();start=round(45.25*sr);n=min(len(stem),round(5*sr));out[start:start+n]+=stem[:n]
assert np.max(np.abs(out))<1, 'clipping'
assert np.array_equal(out[:start],base[:start])
assert np.array_equal(out[start+n:],base[start+n:])
wav('master-v4.wav',out)
ff(['-i',str(R/'master-v3.mp4'),'-i',str(R/'master-v4.wav'),'-map','0:v:0','-map','1:a:0','-c:v','copy','-c:a','aac','-b:a','256k','-t','81.208333','-movflags','+faststart',str(R/'film-master-v4.mp4')])
wav('ending-v4.wav',out[round(31.125*sr):round(81.208333*sr)])
ff(['-i',str(R/'ending-v3.mp4'),'-i',str(R/'ending-v4.wav'),'-map','0:v:0','-map','1:a:0','-c:v','copy','-c:a','aac','-b:a','256k','-t','50.083333','-movflags','+faststart',str(R/'film-ending-v4.mp4')])
jsx="""export default async ({project})=>{
const r='/home/user/e5-contact-v4';const p=await project({dir:r+'/comparison-project',size:'854x480',fps:24,background:'#000'});
for(const [name,file,at] of [['BEFORE','master-v3.mp4',0],['AFTER','film-master-v4.mp4',15.25]]){
const m=await p.add(r+'/'+file);
p.compose(<media file={m} trimStart={40.25} x={0} y={0} width={854} height={480} muted={true}/>,{at,dur:14.75,name});
p.compose(<group><rect x={12} y={12} width={130} height={34} fill="#06131d" opacity={.85}/><text x={22} y={19} width={114} height={22} fontFamily="Metropolis" fontSize={18} color="#ffffff">{name}</text></group>,{at,dur:14.75,name:name+' label'});
}await p.render(r+'/comparison-picture.mp4',{draft:false,bitrate:2500000});};"""
(R/'comparison-edit.jsx').write_text(jsx)
run(['higgsedit','build',str(R/'comparison-edit.jsx')])
a=round(40.25*sr);b=round(55*sr)
comp=np.concatenate([base[a:b],np.zeros((round(.5*sr),2),np.float32),out[a:b]])
wav('comparison.wav',comp)
ff(['-i',str(R/'comparison-picture.mp4'),'-i',str(R/'comparison.wav'),'-map','0:v','-map','1:a','-c:v','copy','-c:a','aac','-b:a','256k','-movflags','+faststart',str(R/'film-e5pre-footsteps-comparison-v4.mp4')])
def vhash(file):return hashlib.sha256(ff(['-i',str(R/file),'-map','0:v','-c','copy','-f','h264','-'])).hexdigest()
qa=dict(master_video_unchanged=vhash('master-v3.mp4')==vhash('film-master-v4.mp4'),ending_video_unchanged=vhash('ending-v3.mp4')==vhash('film-ending-v4.mp4'),pcm_unchanged_outside_e5pre=True,peak_dbfs=float(20*np.log10(np.max(np.abs(out)))),events=events)
(R/'qa.json').write_text(json.dumps(qa,indent=2));print(json.dumps(qa))
run(['zip','-qr',str(R/'film-footsteps-v4-work.zip'),'contact-edit.jsx','comparison-edit.jsx','events.json','qa.json','contact-project','comparison-project'] if False else ['bash','-c',"cd /home/user/e5-contact-v4 && zip -qr film-footsteps-v4-work.zip contact-edit.jsx comparison-edit.jsx events.json qa.json contact-project comparison-project"])

