"""Original nonvocal atmospheric score and unified diegetic mix, after picture render."""
import json, subprocess, wave, math
from pathlib import Path
import numpy as np
root=Path('/home/user/e5-audio-v3')
assert (root/'master-v2.mp4').exists(), 'Existing approved picture is required'
plan=json.loads((root/'plan.json').read_text())
sr=48000;n=round(plan['total']*sr);t=np.arange(n,dtype=np.float32)/sr
mix=np.zeros((n,2),np.float32)
def read_audio(path,dur,offset=0):
 raw=subprocess.check_output(['ffmpeg','-v','error','-ss',str(offset),'-i',str(path),'-t',str(dur),'-f','f32le','-ac','2','-ar',str(sr),'-'])
 return np.frombuffer(raw,np.float32).reshape(-1,2).copy()
def add(buf,at,gain=1):
 start=round(at*sr);end=min(n,start+len(buf))
 if start>=0 and end>start:mix[start:end]+=buf[:end-start]*gain
def ramp(buf,sec=.04):
 k=min(round(sec*sr),len(buf)//2)
 if k:buf[:k]*=np.linspace(0,1,k)[:,None];buf[-k:]*=np.linspace(1,0,k)[:,None]
 return buf
# Preserve source effects; small overlaps carry room tails across hard picture cuts.
source={}
for c in plan['clips']:
 a=read_audio(root/'media'/c['file'],c['dur'],c['from']);source[c['shot']]=a
 add(ramp(a.copy(),.12 if c['shot'] in ['E5pre','E5'] else .04),c['at'],.62)
# A shared low room bed removes silence and tonal discontinuity at camera cuts.
amb=source['E6'];loop=np.tile(amb,(math.ceil(n/len(amb)),1))[:n]
mix+=loop*.055
# Carry each adjacent source's decaying room tail once, with no repeated foot sample.
for previous,current in [('E4','E5pre'),('E5pre','E5')]:
 c=next(c for c in plan['clips'] if c['shot']==current)
 tail=source[previous][-int(.18*sr):].copy()
 tail*=np.linspace(1,0,len(tail))[:,None]
 add(tail,c['at'],.12)
# One continuous evolving original texture: sub foundation, bowed-like harmonic bed,
# restrained pulse and a wider fifth at robot reveal, resolving at receipt.
end=plan['total'];reveal=next(c['at'] for c in plan['clips'] if c['shot']=='E2')
env=np.minimum(1,t/3)*np.minimum(1,np.maximum(0,(end-.25-t)/2))
rise=np.clip((t-reveal)/12,0,1)
foundation=(np.sin(2*np.pi*36.708*t+.13*np.sin(.29*t))*.026+
            np.sin(2*np.pi*55.0*t+.18*np.sin(.17*t))*.010)
for side in range(2):
 pad=np.zeros(n,np.float32)
 for f,g in [(73.416,.010),(110.0,.008),(146.832,.005),(164.814,.0025)]:
  pad+=g*np.sin(2*np.pi*f*t+side*.27+.16*np.sin(.35*t))* (0.6+.4*np.sin(.21*t+f)**2)
 pulse=(np.maximum(0,np.sin(2*np.pi*.43*t))**12)*np.sin(2*np.pi*73.416*t)*.008
 mix[:,side]+=(foundation+pad*(.55+rise*.8)+pulse)*env
def ping(at,d,f,amp):
 q=np.arange(round(d*sr),dtype=np.float32)/sr
 b=np.sin(2*np.pi*f*q)*np.sin(np.pi*q/d)**2*amp
 add(np.column_stack([b,b]),at)
o4=next(c['at'] for c in plan['clips'] if c['shot']=='O4')
ping(o4+.12,.08,920,.045);ping(o4+.27,.09,1160,.025)
for dt in [.2,.55,.9,1.25,1.6,1.95,2.3]:ping(plan['e7']+dt,.035,1150,.025)
ping(plan['e7']+2.62,.13,440,.045);ping(plan['e7']+2.78,.18,660,.035)
# Long but quiet low-frequency resonance gives the foot exit a tail into black.
foot=next(c for c in plan['clips'] if c['shot']=='O7')
tail=source['O7'][-int(.3*sr):].copy()
for dt,g in [(.12,.12),(.29,.07),(.48,.035)]:add(ramp(tail.copy(),.025),foot['at']+foot['dur']-.3+dt,g)
rng=np.random.default_rng(7)
for dt in [4.25,4.417,4.5]:
 q=rng.uniform(-.025,.025,(round(.022*sr),2)).astype(np.float32)
 add(ramp(q,.006),plan['e7']+dt)
# Ensure the final signal cutoff resolves to silence, preserving no stray tails.
fade=np.clip((end-.12-t)/.45,0,1);mix*=fade[:,None]
peak=float(np.max(np.abs(mix)));mix*=min(1,.88/max(peak,1e-6))
with wave.open(str(root/'mix-unmastered.wav'),'wb') as w:
 w.setnchannels(2);w.setsampwidth(2);w.setframerate(sr);w.writeframes((mix*32767).astype('<i2').tobytes())
subprocess.run(['ffmpeg','-v','error','-y','-i',str(root/'mix-unmastered.wav'),'-af','loudnorm=I=-18:TP=-1.5:LRA=10','-ar',str(sr),str(root/'mix.wav')],check=True)
(root/'sound-design.json').write_text(json.dumps({'order':'picture render -> unified soundtrack -> mux full master -> split','score':'original procedural nonvocal texture, not licensed music or artist imitation','source_effects':'generated clip audio','E5pre_contacts':'Native v3 audio restored; repeated E4 contact excerpt removed','mix_target_lufs':-18,'listening_review':'not claimed; user playback review required','duration':plan['total']},indent=2))
