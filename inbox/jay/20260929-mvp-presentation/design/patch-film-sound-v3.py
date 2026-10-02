from pathlib import Path
import numpy as np, subprocess, wave,json
r=Path('/home/user/e5-audio-v3'); sr=48000
def read(name):
 raw=subprocess.check_output(['ffmpeg','-v','error','-i',str(r/name),'-f','f32le','-ac','2','-ar',str(sr),'-'])
 return np.frombuffer(raw,np.float32).reshape(-1,2).copy()
old=read('master-v2.mp4'); corrected=read('mix.wav')
# Replace only the POV and short joining handles. No picture re-encode.
a,b=round(45.0*sr),round(50.5*sr); n=b-a; w=np.ones(n,np.float32)
f=round(.25*sr); w[:f]=np.linspace(0,1,f);w[-f:]=np.linspace(1,0,f)
old[a:b]=old[a:b]*(1-w[:,None])+corrected[a:b]*w[:,None]
with wave.open(str(r/'patched.wav'),'wb') as out:
 out.setnchannels(2);out.setsampwidth(2);out.setframerate(sr);out.writeframes((np.clip(old,-1,1)*32767).astype('<i2').tobytes())
(r/'patch-audit.json').write_text(json.dumps({'audio_only_patch':[45.0,50.5],'core':[45.25,50.25],'original_source_gain':.10,'restored_source_gain':.62,'removed':'8 repetitions of same E4 foot excerpt','score':'Existing procedural temporary texture retained, no cinematic music generated','picture':'Existing master-v2 and ending-v2 video stream copied unchanged'},indent=2))

