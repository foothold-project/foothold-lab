"""CPU-only per-video foot audit. Exact contact + explicitly approximate clearance."""
import csv
import hashlib
import json
from pathlib import Path
import numpy as np

OUT=Path(__file__).parent
OLD=Path('C:/Users/AI-WS01/s2_lab/ex40_main_20261031_041313/video_a/ex40_m6000')
NEW=Path('D:/mai-tmp/runner/ex41_stage_video/model_6000_1c6af6319c82')
TRAIN=Path('C:/Users/AI-WS01/s2_lab/ex41_main_20261104_235522/eval/score-watch/model_6000_1c6af6319c82/training')
FEET=['FL_foot','FR_foot','RL_foot','RR_foot']

def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()
def dump(name,x):(OUT/name).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf8')
def mean(x):return float(np.mean(x)) if len(x) else None
def runs(c,value):
 b=np.asarray(c)==value
 starts=np.flatnonzero(b & np.r_[True,~b[:-1]])
 ends=np.flatnonzero(b & np.r_[~b[1:],True])+1
 return [(s,e) for s,e in zip(starts,ends) if s>0 and e<len(b)]

def terrain_clearance(n):
 """Nearest GT grid sample, only locally flat 3x3 patches. NOT W86 exact foot rays."""
 root=n['root_pos_w']; feet=n['foot_pos_w']; q=n['root_quat_w']; gt=n['gt_map']
 yaw=np.arctan2(2*(q[:,0]*q[:,3]+q[:,1]*q[:,2]),1-2*(q[:,2]**2+q[:,3]**2))
 rel=feet-root[:,None,:]; c=np.cos(yaw)[:,None];s=np.sin(yaw)[:,None]
 x=c*rel[:,:,0]+s*rel[:,:,1];y=-s*rel[:,:,0]+c*rel[:,:,1]
 ix=np.rint((x+.475)/.05).astype(int);iy=np.rint((y+.375)/.05).astype(int)
 h=np.full(x.shape,np.nan); valid=np.zeros(x.shape,bool)
 for t in range(min(len(root),len(gt))):
  for j in range(4):
   a,b=ix[t,j],iy[t,j]
   if not (1<=a<=30 and 1<=b<=14):continue
   patch=gt[t,a-1:a+2,b-1:b+2]
   if not np.isfinite(patch).all() or np.ptp(patch)>.02 or patch.min()<=-.999:continue
   # Foot-body sphere centre offset is up to 2 mm; quaternion of each foot is not recorded.
   h[t,j]=feet[t,j,2]-.022-(gt[t,a,b]+root[t,2]);valid[t,j]=True
 return h,valid

def measure(n,idx,foot,h,valid):
 dt=float(n['dt']);c=n['foot_contact'][idx,foot].astype(bool);z=n['foot_pos_w'][idx,foot,2]
 st=runs(c,True);sw=runs(c,False)
 # Raw force-threshold flicker is not a stride. Retain raw counts separately.
 sustained_st=[(a,b) for a,b in st if b-a>=3]
 sustained_sw=[(a,b) for a,b in sw if b-a>=3]
 peaks=[]
 for a,b in sustained_sw:
  baseline=np.linspace(z[a-1],z[b],b-a+2)[1:-1]
  peaks.append(float(np.max(z[a:b]-baseline)))
 v=np.full(len(n['t']),np.nan)
 v[1:]=np.linalg.norm(np.diff(n['foot_pos_w'][:,foot,:2],axis=0),axis=1)/dt
 v[1:][n['done'][:-1].astype(bool)]=np.nan
 speed=v[idx];hv=h[idx,foot];ok=valid[idx,foot]&np.isfinite(speed)
 stance=c&ok; swing=~c&ok
 drag=stance&(hv<.02)&(speed>.05)
 low_swing=swing&(hv<.02)&(speed>.05)
 off_starts=np.flatnonzero(~c & np.r_[True,c[:-1]])
 off_ends=np.flatnonzero(~c & np.r_[c[1:],True])+1
 max_off=max((b-a for a,b in zip(off_starts,off_ends)),default=0)*dt
 return dict(frames=len(idx),seconds=len(idx)*dt,contact_ratio=float(c.mean()),contact_time_s=float(c.sum()*dt),
             max_observed_noncontact_s=float(max_off),
             complete_stances=len(st),mean_stance_s=mean([(b-a)*dt for a,b in st]),
             complete_swings=len(sw),mean_swing_s=mean([(b-a)*dt for a,b in sw]),
             sustained_stances=len(sustained_st),sustained_swings=len(sustained_sw),
             sustained_stance_s=mean([(b-a)*dt for a,b in sustained_st]),
             sustained_swing_s=mean([(b-a)*dt for a,b in sustained_sw]),
             trajectory_swing_peak_m=mean(peaks),swing_clearance_proxy_m=mean(hv[swing]),
             clearance_valid_fraction=float(ok.mean()),stance_proxy_frames=int(stance.sum()),
             drag_proxy_frames=int(drag.sum()),drag_all_proxy_fraction=float(drag.sum()/max(ok.sum(),1)),
             drag_contact_proxy_fraction=float(drag.sum()/stance.sum()) if stance.any() else None,
             low_swing_proxy_fraction=float(low_swing.sum()/swing.sum()) if swing.any() else None,
             contact_xy_speed_mps=mean(speed[c&np.isfinite(speed)]),force_n=None)

def known_tests():
 assert runs([0,1,1,0,0,1,0],True)==[(1,3),(5,6)]
 assert runs([1,1,0,0,1,1],True)==[]
 # A perfectly stationary contacting foot must not be labelled drag.
 n=dict(t=np.arange(20)*.02,dt=np.array(.02),foot_contact=np.ones((20,4),bool),foot_pos_w=np.zeros((20,4,3)),done=np.zeros(20,bool))
 h=np.zeros((20,4));valid=np.ones((20,4),bool)
 m=measure(n,np.arange(20),0,h,valid);assert m['drag_proxy_frames']==0 and m['contact_ratio']==1
 n['foot_pos_w'][:,0,0]=np.arange(20)*.002
 m=measure(n,np.arange(20),0,h,valid);assert m['drag_proxy_frames']==19 and m['drag_contact_proxy_fraction']==1
 # Without a valid terrain sample, drag is unknown rather than zero.
 m=measure(n,np.arange(20),0,h,np.zeros_like(valid));assert m['drag_contact_proxy_fraction'] is None
 # Flat ground at z=0, foot sphere bottom at z=.08, yaw 0 and pi/2.
 for yaw in (0,np.pi/2):
  nn={'root_pos_w':np.array([[0.,0.,.3]]),'foot_pos_w':np.tile([0.,0.,.102],(1,4,1)),
      'root_quat_w':np.array([[np.cos(yaw/2),0,0,np.sin(yaw/2)]]),'gt_map':np.full((1,32,16),-.3)}
  hh,vv=terrain_clearance(nn); assert vv.all() and np.allclose(hh,.08)
 print('known-input 7 PASS')

def main():
 known_tests();items=[];rows=[];sources=[]
 for p in sorted(OLD.glob('*/review.json')):items.append(('EX40_m6000',p,None))
 for rp in sorted((NEW/'receipts').glob('*.json')):
  rec=read(rp);ps=list(Path(rec['attempt_dir']).glob('*/review.json'))
  if len(ps)!=1:raise ValueError((rp,ps))
  items.append(('EX41_m12000',ps[0],str(rp)))
 for model,p,receipt in items:
  r=read(p);f=p.with_name('review_feet.npz');done=read(p.with_name('review.done'))
  expected=done.get('files',{}).get('review_feet.npz');actual=sha(f)
  if expected is not None and expected!=actual:raise ValueError('NPZ hash mismatch '+str(f))
  src=dict(model=model,review=str(p),npz=str(f),sha256=actual,receipt=receipt,receipt_hash_match=actual==expected if expected else None,
           checkpoint_sha256=r['checkpoint_sha256'],seed=r['seed'],terrain=r['task_selection']['kind'],
           tile=r['task_selection'].get('selected_tile'),mode=r['map_modes']['map_mode']['requested'])
  sources.append(src)
  with np.load(f,allow_pickle=False) as n:
   assert list(n['foot_names'])==FEET
   src['raw_force_present']=any('force' in k for k in n.files)
   h,valid=terrain_clearance(n)
   for seg,desc in enumerate(r['segments']):
    ids=np.flatnonzero(n['seg']==seg)
    if not len(ids):continue
    # Same segment only, cut at its first termination; do not mix resets.
    dn=ids[n['done'][ids].astype(bool)]
    if len(dn):ids=ids[ids<=dn[0]]
    ids=ids[n['t'][ids]>=n['t'][ids[0]]+.2-1e-7]
    if len(ids)<10:continue
    for window in ('segment_after_0.2s','tail2s'):
     ix=ids if window=='segment_after_0.2s' else ids[n['t'][ids]>=n['t'][ids[-1]]-2+.02-1e-7]
     for j,foot in enumerate(FEET):
      rows.append(dict(model=model,terrain=src['terrain'],level=src['tile']['level'] if src['tile'] else None,mode=src['mode'],
                       command=desc[0],command_xyz=desc[1],seed=r['seed'],window=window,foot=foot,
                       **measure(n,ix,j,h,valid),actual_vx_mean=float(n['vx'][ix].mean()),
                       actual_vy_mean=float(n['vy'][ix].mean()),actual_wz_mean=float(n['wz'][ix].mean()),
                       npz=str(f),segment=int(seg)))
 dump('feet_rows.json',rows);dump('sources.json',sources)
 with (OUT/'feet_rows.csv').open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,list(rows[0]));w.writeheader();w.writerows(rows)
 trainfile=next(TRAIN.glob('w86_*.json'));tr=read(trainfile)['record'];feet=tr['feet'];train=[]
 for j,name in enumerate(tr['feet_order']):
  link=tr['all_link_contact']['links'][name];ct=link['contact_ratio'];force=link['mean_force_n']
  train.append(dict(foot=name,valid_frames=feet['valid_foot_frames'][j],drag_frames=feet['drag_frames'][j],
                    contact_moving_frames=feet['contact_moving_frames'][j],
                    drag_all_fraction=feet['drag_frames'][j]/feet['valid_foot_frames'][j],
                    drag_contact_fraction=feet['drag_frames'][j]/feet['contact_moving_frames'][j],
                    contact_ratio=ct,swing_all_fraction=feet['swing_frames'][j]/feet['valid_foot_frames'][j],
                    swing_height_m=feet['swing_height_sum_m'][j]/feet['swing_frames'][j],
                    mean_force_n=force,contact_force_lower_n=max(0,(force-(1-ct))/ct),contact_force_upper_n=force/ct))
 dump('training_w86.json',dict(path=str(trainfile),sha256=sha(trainfile),record_iteration=tr['iteration'],env_frames=tr['env_frames'],feet=train))
 print('sources',len(sources),'rows',len(rows),'raw force sources',sum(s['raw_force_present'] for s in sources))
 for model in ('EX40_m6000','EX41_m12000'):
  print(model)
  for cmd in ('fwd1.0','back1.0','side+0.5','side-0.5','spin+1.2','spin-1.2','stop'):
   rr=[r for r in rows if r['model']==model and r['mode']=='eval_gt' and r['command']==cmd and r['window']=='segment_after_0.2s' and (r['terrain']=='pyramid_stairs_inv' or cmd.startswith('spin'))]
   if rr:print(cmd,[(r['foot'],round(r['contact_ratio'],3),None if r['drag_contact_proxy_fraction'] is None else round(r['drag_contact_proxy_fraction'],3),r['complete_swings']) for r in rr])

if __name__=='__main__':main()
