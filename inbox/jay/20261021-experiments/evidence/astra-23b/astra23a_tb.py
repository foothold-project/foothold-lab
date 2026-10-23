from pathlib import Path
import json,yaml,numpy as np,hashlib
from tensorboard.backend.event_processing.event_accumulator import EventAccumulator
OUT=Path('C:/Users/AI-WS01/AppData/Local/Temp/astra23a')
BASE=Path('C:/Users/AI-WS01/orca/workspaces/foothold-lab/sonnet-code/logs/rsl_rl')
runs={'811':Path('C:/isaac/IsaacLab/logs/rsl_rl/unitree_go2_rough/2026-08-11_20-32-58'),'EX11':BASE/'foothold_s2_x11/2026-10-22_01-33-36_ex11-est-zero','EX23':BASE/'foothold_s2_x23/2026-10-22_21-52-26_ex23-g1','EX25':BASE/'foothold_s2_x23/2026-10-22_23-00-45_ex25-g0'}
result={};cfg={}
for name,p in runs.items():
 e=EventAccumulator(str(p),size_guidance={'scalars':0});e.Reload();tags=e.Tags()['scalars'];rr={};cfg[name]={}
 for tag in tags:
  ev=e.Scalars(tag); rr[tag]={}
  for step in [50,100,150,300,500,1000,1499,1500]:
   at=[x for x in ev if x.step==step];win=[x.value for x in ev if step-49<=x.step<=step]
   rr[tag][step]={'exact':float(at[-1].value) if at else None,'mean50':float(np.mean(win)) if win else None,'n':len(win)}
 result[name]={'path':str(p),'scalars':rr,'events':[{'file':str(f),'sha256':hashlib.sha256(f.read_bytes()).hexdigest()} for f in p.glob('events*')]}
 for fn in ['env','agent']:
  cfg[name][fn]=yaml.load((p/'params'/f'{fn}.yaml').read_text(encoding='utf8'),Loader=yaml.BaseLoader)
 print(name,[(t,[(s,round(rr[t][s]['exact'],4) if rr[t][s]['exact'] is not None else None) for s in [300,500,1000,1499,1500]]) for t in tags if t in ['Train/mean_episode_length','Episode_Reward/track_lin_vel','Episode_Reward/track_lin_vel_xy_exp','Episode_Reward/track_ang_vel','Curriculum/terrain_levels','Loss/learning_rate','Loss/reward_split/frac_stalled','Loss/kl_probe/phi_mean']])
def diff(a,b,p=''):
 if isinstance(a,dict) and isinstance(b,dict):
  out=[]
  for k in sorted(set(a)|set(b)):
   if k not in a:out.append([p+k,'<absent>',b[k]])
   elif k not in b:out.append([p+k,a[k],'<absent>'])
   else:out+=diff(a[k],b[k],p+k+'.')
  return out
 return [[p.rstrip('.'),a,b]] if a!=b else []
diffs={}
for aa,bb in [('EX11','EX25'),('EX23','EX25')]:
 for kind in ['env','agent']:
  dd=diff(cfg[aa][kind],cfg[bb][kind]);diffs[f'{aa}-{bb}-{kind}']=dd
  print('DIFF',aa,bb,kind,json.dumps(dd,ensure_ascii=False))
for name in runs:
 print('BUDGET',name,{k:cfg[name]['agent'].get(k) for k in ['seed','num_steps_per_env','max_iterations']},cfg[name]['env'].get('scene',{}).get('num_envs'))
(OUT/'tb_cfg.json').write_text(json.dumps({'tb':result,'diffs':diffs},ensure_ascii=False,indent=2),encoding='utf8')
