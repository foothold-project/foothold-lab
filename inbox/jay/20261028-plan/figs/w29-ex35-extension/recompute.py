"""W29 stored-data CPU audit. No Isaac, CUDA execution, or source mutation."""
from pathlib import Path
import ast,csv,json,hashlib,os,sys,subprocess
os.environ['CUDA_VISIBLE_DEVICES']='';sys.dont_write_bytecode=True
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from tensorboard.backend.event_processing.event_accumulator import EventAccumulator

OUT=Path(__file__).resolve().parent
R=Path('C:/mai/wt/foothold-lab/impl-turncases/logs')
T=Path('C:/mai/wt/foothold-lab/impl-sb/logs/rsl_rl/foothold_s2_sb')
BASE='2026-10-26_01-17-47_sb-main'
OLD=BASE+'_resume_20261026_232446_120476';EXT=OLD+'_resume_20261028_050035_157468'
MODES=('eval_gt','probe_prop_only','eval_pred')
CASES=('indep_left','indep_right','fwd_then_left','fwd_then_right','right_then_left','left_then_right','walk_turn_left','walk_turn_right')
FEET=[4,8,14,18];COLORS=['#126B62','#A34B16','#634E8E'];sources={};meta=[];missing=[]
def src(p):
 b=p.read_bytes();sources[str(p)]={'path':str(p),'sha256':hashlib.sha256(b).hexdigest(),'bytes':len(b)};return b
def read(p):return json.loads(src(p).decode('utf-8-sig'))
def jl(p):return [json.loads(s) for s in src(p).decode('utf-8-sig').splitlines() if s.strip()]
def dump(name,obj): (OUT/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
def csvout(name,rr):
 with (OUT/name).open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(dict.fromkeys(k for r in rr for k in r)),lineterminator='\n');w.writeheader();w.writerows(rr)
def avg(x):return float(np.mean(x)) if len(x) else None

# Reuse the audited complete-cycle formula exactly, without running the earlier audit.
formula=OUT.parent/'w32-parent-audit/recompute.py';tree=ast.parse(src(formula).decode('utf-8'))
for node in tree.body:
 if isinstance(node,ast.FunctionDef) and node.name in ('circ','phase','qstat'):
  exec(compile(ast.Module(body=[node],type_ignores=[]),str(formula),'exec'))
t=np.arange(1000);a=t%100<50;v=np.ones(1000,bool)
assert phase(a,(t+50)%100<50,v)['deg']==180 and phase(a,a,v)['deg']==0 and phase(v,v,v)['cycles']==0
fake={'alive':np.array([[1,1],[1,0]],bool),'kept':np.ones(2,bool),'wz':np.array([[0,0],[4,0]]),'force':np.full((2,2,19),2)}
assert qstat(fake,1)['Q']==2

maps=[];turn=[];gait=[];joint=[];verdicts=[]
locations=[('parent',1500,R/'sb10_eval/m1500'),('first',2000,R/'ex35_eval/m2000')]+[('extend',n,R/'ex35ext_eval'/f'm{n}') for n in range(2050,3001,50)]
for kind,n,d in locations:
 p=d/'map64/map_modes.json'
 if not p.exists():missing.append(str(p));continue
jm=None
for kind,n,d in locations:
 p=d/'map64/map_modes.json'
 if p.exists():
  j=read(p);meta.append({'kind':kind,'iter':n,'type':'map64','task':j['task'],'checkpoint_sha':j['checkpoint_sha256'],'terrain':j['terrain_hash'],'envs':j['envs'],'steps':j['steps'],'dr_off':j['dr_off'],'curriculum_off':j['curriculum_off']})
  for mode,dd in j['modes'].items():
   for c,x in dd.items():maps.append({'iter':n,'kind':kind,'mode':mode,'case':c,'distance_m':x['body_vx_integral_median_m'],'follow':x['yaw_follow_median'],'alive':x['alive_envs_at_end'],'tilt_rad':x['tilt_rad_mean_alive'],'stall':x['stalled_fraction_2to4s'],'path':str(p)})
 if (d/'ex35_verdict.json').exists():
  j=read(d/'ex35_verdict.json');verdicts.append({'iter':n,'state':j['state'],'reasons':j['reasons']})
 for mode in MODES:
  td=d/f'turn16_{mode}';mp=td/'probe_result.json'
  if not mp.exists():continue
  mj=read(mp);assert mj['envs']==16 and mj['static']['sample_hz']==200
  assert [mj['static']['link_names'][i] for i in FEET]==['FL_foot','FR_foot','RL_foot','RR_foot']
  meta.append({'kind':kind,'iter':n,'type':mode,'terrain':mj['fixed_terrain'],'logic':mj['logic_blob_sha'],'checkpoint_sha':mj['checkpoint_sha256'],'dr_off':mj['dr_off'],'curriculum_off':mj['curriculum_off']})
  for c in CASES:
   p=td/f'arrays_{c}.npz'
   if not p.exists():p=d/f'turn16_walk_{mode}'/f'arrays_{c}.npz'
   if not p.exists():missing.append(str(p));continue
   src(p)
   with np.load(p,allow_pickle=False) as z:
    ss=qstat(z,1 if c.endswith('left') else -1)
    turn.append({'iter':n,'kind':kind,'mode':mode,'case':c,**ss,'Q_reportable':ss['Q'] if ss['kept']>=12 else None,'path':str(p)})
    if n in (1500,2000,2500,2700,3000) and mode=='eval_gt' and c in ('indep_left','indep_right'):
     # Observed pre-first-fall signals, equal env weighting. All env, no survivor selection.
     for e in range(16):
      al=z['alive'][e].astype(bool);on=z['force'][e][:,FEET]>1;q=z['root_quat'][e]
      tilt=np.rad2deg(np.arccos(np.clip(1-2*(q[:,1]**2+q[:,2]**2),-1,1)))
      hh=np.array(mj['static']['hard_limits']);lim=(z['q'][e]<hh[:,0]+.05)|(z['q'][e]>hh[:,1]-.05)
      joint.append({'iter':n,'case':c,'env':e,'kept':bool(z['kept'][e]),'first_invalid_s':float(np.argmax(~al)/200) if (~al).any() else None,'tilt_mean_deg':float(tilt[al].mean()),'tilt_max_deg':float(tilt[al].max()),'C_alive':float(on[al].all(1).mean()),'hardlimit_near_frac':float(lim[al].mean()),'torque_clip_frac':float((np.abs(z['computed'][e,al]-z['applied'][e,al])>1e-4).mean())})
  if n not in (1500,2000,2500,2700,3000) or mode=='eval_pred':continue
  for c in ('fwd0.5','fwd1.0'):
   p=td/f'arrays_{c}.npz'
   if not p.exists():continue
   src(p)
   with np.load(p,allow_pickle=False) as z:
    al=z['alive'].astype(bool);k=z['kept'].astype(bool);on=z['force'][...,FEET]>1
    for e in np.flatnonzero(k):
     a=al[e];cc=on[e]
     for pair,(aa,bb) in {'between':(cc[:,0]&cc[:,3],cc[:,1]&cc[:,2]),'FL_RR':(cc[:,0],cc[:,3]),'FR_RL':(cc[:,1],cc[:,2])}.items():
      ph=phase(aa,bb,a);target=180 if pair=='between' else 0
      gait.append({'iter':n,'mode':mode,'case':c,'env':int(e),'pair':pair,**ph,'error_abs':abs((ph['deg']-target+180)%360-180) if ph['deg'] is not None else None,'C':float(cc[a].all(1).mean()),'duty':float(cc[a].mean()),'contact_xy_proxy':float(z['link_xy_speed'][e][:,FEET][a][cc[a]].mean()),'vx':float(z['vx'][e,a].mean())})

# Independent reruns, not replacement of original chain results.
repeats=[]
for n in (2700,3000):
 d=R/'w26_fall/repro'/f'm{n}'
 p=d/'map64/map_modes.json'
 if p.exists():
  j=read(p)
  for m,dd in j['modes'].items():
   for c,x in dd.items():repeats.append({'iter':n,'type':'map64','mode':m,'case':c,'alive':x['alive_envs_at_end'],'distance':x['body_vx_integral_median_m'],'follow':x['yaw_follow_median']})
 for p in sorted(d.glob('turn16_*/arrays_*.npz')):
  c=p.stem.removeprefix('arrays_')
  if c not in CASES:continue
  src(p)
  with np.load(p,allow_pickle=False) as z:ss=qstat(z,1 if c.endswith('left') else -1)
  repeats.append({'iter':n,'type':'turn16','mode':p.parent.name.removeprefix('turn16_'),'case':c,**ss})

curve=[];trmeta=[]
for label,dirname,bounds in [('SB10',BASE,(0,1500)),('EX35-first',OLD,(1501,2000)),('EX35-extend',EXT,(2001,3000))]:
 d=T/dirname;manifest=read(d/'manifest.json');extra=jl(d/'train_extra.jsonl');ev=next(d.glob('events.out*'));src(ev)
 ea=EventAccumulator(str(ev),size_guidance={'scalars':0});ea.Reload();data={}
 for tag in ea.Tags()['scalars']:
  if tag.endswith('/time'):continue
  for s in ea.Scalars(tag):
   if bounds[0]<=s.step<=bounds[1]:data.setdefault(s.step,{'iter':s.step,'run':label})[tag]=float(s.value)
 for x in extra:
  if x['it'] not in data:continue
  r=data[x['it']]
  for stage in ('ppo','phi'):
   for branch in ('all','walk','spin'):
    ss=x['kl_probe'][stage][branch]
    for k in ('mean','p95','max'):r[f'{stage}_{branch}_{k}']=ss[k]
  for k,vv in (x.get('command_slots') or {}).get('counts',{}).items():r[f'slot_count/{k}']=vv
  for k in ('element_saturation_rate','torque_clipped_frac','target_out_of_limit_frac'):
   r['action/'+k]=(x.get('action_stats') or {}).get(k)
 curve.extend(data[i] for i in sorted(data))
 trmeta.append({'run':label,'dir':str(d),'manifest_git':manifest['git'],'modes':manifest['modes'],'progress':manifest['progress'],'yaml':manifest['yaml'],'events_tags':ea.Tags()['scalars']})
 assert len(data)==bounds[1]-bounds[0]+1,(label,len(data))
 for nm in ('params/agent.yaml','params/env.yaml','train_start_status.json'):
  if (d/nm).exists():src(d/nm)

windows=[]
for name,lo,hi in [('SB10-late',1001,1500),('EX35-first',1501,2000),('EX35-ext-early',2001,2500),('EX35-ext-late',2501,3000)]+[(f'w{lo}',lo,lo+99) for lo in range(2001,3001,100)]+[('restart10',2001,2010)]:
 rr=[r for r in curve if lo<=r['iter']<=hi];lr=[r['Loss/learning_rate'] for r in rr]
 row={'window':name,'first':lo,'last':hi,'n':len(rr),'lr_min':min(lr),'lr_max':max(lr),'lr_at_floor_count':sum(x<=1e-5*(1+1e-6) for x in lr)}
 for k in ('Loss/learning_rate','Policy/mean_noise_std','Loss/entropy','Loss/value_function','Train/mean_reward','Train/mean_episode_length','Curriculum/terrain_levels','Episode_Reward/track_lin_vel','Episode_Reward/track_ang_vel','ppo_all_mean','ppo_spin_mean','phi_all_mean','phi_spin_mean','Loss/perception/kl','Episode_Termination/bad_orientation','action/torque_clipped_frac'):
  row[k]=avg([r[k] for r in rr if r.get(k) is not None])
 counts={k:sum(r.get('slot_count/'+k,0) for r in rr) for k in ('forward','walk_left','walk_right','spin_left','spin_right')};tot=sum(counts.values())
 for k,x in counts.items():row['slot_fraction/'+k]=x/tot if tot else None
 windows.append(row)

csvout('map64.csv',maps);csvout('turn16.csv',turn);csvout('gait_env.csv',gait);csvout('joint_posture.csv',joint);csvout('repeat.csv',repeats);csvout('training_by_update.csv',curve);csvout('training_windows.csv',windows)
dump('training_metadata.json',trmeta);dump('eval_metadata.json',meta);dump('verdicts.json',verdicts);dump('missing.json',missing)
fig,axs=plt.subplots(4,2,figsize=(14,13),sharex=True)
for j,case in enumerate(('fwd0.5','fwd1.0')):
 for mode,col in zip(MODES,COLORS):
  rr=[r for r in maps if r['mode']==mode and r['case']==case];axs[0,j].plot([r['iter'] for r in rr],[r['distance_m'] for r in rr],'o-',ms=3,color=col,label=mode);axs[1,j].plot([r['iter'] for r in rr],[r['alive'] for r in rr],'o-',ms=3,color=col)
 axs[0,j].set_title(case);axs[0,j].set_ylabel('Body vx integral median (m)');axs[1,j].set_ylabel('Forward alive / 64')
 for mode,col in zip(MODES,COLORS):
  rr=[r for r in maps if r['mode']==mode and r['case']==('spin+1.2' if j==0 else 'spin-1.2')];axs[2,j].plot([r['iter'] for r in rr],[r['follow'] for r in rr],'o-',ms=3,color=col);axs[3,j].plot([r['iter'] for r in rr],[r['alive'] for r in rr],'o-',ms=3,color=col)
 axs[2,j].set_ylabel(('Left' if j==0 else 'Right')+' spin follow median');axs[3,j].set_ylabel('Spin alive / 64');axs[3,j].axhline(48,color='#555555',ls=':',label='legacy STOP <48')
for ax in axs.flat:ax.grid(alpha=.2);ax.axvline(2000,color='#777777',ls=':')
for ax in [*axs[1],*axs[3]]:ax.set_ylim(0,66)
axs[0,0].legend(fontsize=8);fig.suptitle('EX-35 extension: forward preserved, left spin survival deteriorates\nParent m1500, EX-35 m2000, then m2050..3000. Missing PRED measurements are not filled.');fig.tight_layout(rect=[0,0,1,.94]);fig.savefig(OUT/'evaluation64.png',dpi=150);plt.close(fig)
fig,axs=plt.subplots(6,3,figsize=(16,17),sharex=True)
for i,c in enumerate(CASES[:6]):
 for j,key in enumerate(('Q','C','kept')):
  ax=axs[i,j]
  for mode,col in zip(MODES,COLORS):
   rr=[r for r in turn if r['mode']==mode and r['case']==c];ax.plot([r['iter'] for r in rr],[r[key] for r in rr],'o-',ms=3,color=col,label=mode)
   if key=='Q':
    bad=[r for r in rr if r['kept']<12];ax.scatter([r['iter'] for r in bad],[r['Q'] for r in bad],marker='x',s=40,color='#111111',zorder=5)
  ax.set_ylabel(c+'\n'+key if j==0 else key);ax.grid(alpha=.2)
  if key=='kept':ax.set_ylim(0,17);ax.axhline(12,color='#555555',ls=':')
axs[0,0].legend(fontsize=7);fig.suptitle('Six turn protocols: Q, all-four contact C, and kept /16\nBlack x = Q of fewer than 12 survivors; descriptive only, not valid success.');fig.tight_layout(rect=[0,0,1,.96]);fig.savefig(OUT/'turn_six.png',dpi=140);plt.close(fig)
fig,axs=plt.subplots(6,1,figsize=(14,16),sharex=True)
fields=[('Loss/learning_rate','PPO end-of-update lr'),('ppo_all_mean','PPO policy KL probe'),('phi_all_mean','Perception-update policy KL probe'),('Policy/mean_noise_std','Mean action noise std'),('Loss/value_function','Value loss'),('Train/mean_reward','Training reward')]
for ax,(key,lab) in zip(axs,fields):
 for label,col in zip(('SB10','EX35-first','EX35-extend'),COLORS):
  rr=[r for r in curve if r['run']==label and r['iter']>=1000];x=[r['iter'] for r in rr];y=[r[key] for r in rr];ax.plot(x,y,color=col,lw=.5,alpha=.45)
  if len(rr)>=50:ax.plot(x[49:],np.convolve(y,np.ones(50)/50,'valid'),color=col,lw=1.4,label=label)
 ax.set_ylabel(lab);ax.grid(alpha=.2);ax.axvline(1500,color='#777777',ls=':');ax.axvline(2000,color='#777777',ls=':')
axs[0].axhline(1e-5,color='#111111',ls=':',label='lr floor 1e-5');axs[0].set_yscale('log');axs[0].legend(fontsize=8,ncol=4);axs[-1].set_xlabel('Checkpoint/update index');fig.suptitle('Learning-rate, distinct policy KL probes, std and losses\nThin raw, thick trailing 50 updates. PPO scheduler minibatch KL is not directly logged.');fig.tight_layout(rect=[0,0,1,.96]);fig.savefig(OUT/'learning_lr_kl_std.png',dpi=150);plt.close(fig)
dump('sources.json',list(sources.values()));assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==r['sha256'] for p,r in sources.items())
dump('audit.json',{'known_answer_checks':4,'map_rows':len(maps),'turn_rows':len(turn),'training_updates':len(curve),'raw_sources':len(sources),'sources_unchanged':True,'missing_paths':len(missing)})
print(json.dumps({'windows':windows[:4],'last_map':[r for r in maps if r['iter']==3000],'audit':read(OUT/'audit.json')},ensure_ascii=False))
