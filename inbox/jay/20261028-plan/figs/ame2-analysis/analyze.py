from pathlib import Path
import ast,csv,json,hashlib,difflib,collections
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path('D:/mai-data/ame2');RAW=ROOT/'raw'; DER=ROOT/'derived'
OUT=Path('C:/mai/wt/foothold-lab/analyst-ame2/inbox/jay/20261028-plan/figs/ame2-analysis')
OUT.mkdir(parents=True,exist_ok=True)
RS=json.loads((DER/'runs.json').read_text(encoding='utf-8')); R={r['run_id']:r for r in RS}
def data(r,tag):
    d=np.load(DER/(r['run_id']+'.npz'));i=r['tags'].index(tag)
    return d['x'+str(i)],d['y'+str(i)]
def csvwrite(p,rows):
    if rows:
        with p.open('w',encoding='utf-8-sig',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def mean(r,tag,lo,hi):
    if tag not in r['tags']:return None
    x,y=data(r,tag);v=y[(x>=lo)&(x<=hi)]
    return float(v.mean()) if len(v) else None

branches={
 'NoGap bf16':['87aff28eb73f','06fb5c1cf3a1'],
 'F: KL fp32':['b03ec9c305f8','b89c9f17c350','865546d51560'],
 'E: demote EMA':['c3d770168e6c'],
 'Actor/critic fp32 scratch':['9d8b829c0cf3'],
 'Stones 5%':['f4033663c3db','edf618d3c0e6'],
 'Stones + speed cap 1.2':['24f5a9d0307f'],
}
def merged(ids,tag):
    pts={}
    for k in ids:
        r=R[k]
        if tag not in r['tags']:continue
        x,y=data(r,tag);pts.update(zip(x.tolist(),y.tolist()))
    return np.array(sorted(pts)),np.array([pts[k] for k in sorted(pts)])
def binned(x,y,n=100):
    bins=np.unique(x//n);return np.array([x[x//n==k].mean() for k in bins]),np.array([y[x//n==k].mean() for k in bins])
tags=['Train/mean_reward','Curriculum/terrain_levels','Train/mean_episode_length','Policy/mean_std','Loss/learning_rate','Log/SuccessRateReachEMA']
colors=['#12615B','#C75B35','#80714F','#3465A4','#996A91','#31553A']
plt.rcParams.update({'font.size':10,'axes.labelcolor':'#222222','text.color':'#222222','xtick.color':'#333333','ytick.color':'#333333'})
fig,axes=plt.subplots(3,2,figsize=(14,12))
for ax,t in zip(axes.flat,tags):
 for (label,ids),c in zip(branches.items(),colors):
    x,y=merged(ids,t)
    if not len(x):continue
    xx,yy=binned(x,y);ax.plot(xx,yy,label=label,color=c,lw=1.6)
 ax.set_title(t);ax.set_xlabel('Run-local update index (100-update block means)');ax.grid(alpha=.2)
 if t=='Loss/learning_rate':ax.set_yscale('log')
axes[0,0].legend(fontsize=8);fig.suptitle('Training statistics, NOT a fixed-condition policy evaluation\nStones starts a new counter at F update 10001; full fp32 is a new run',fontsize=14)
fig.tight_layout(rect=[0,0,1,.95]);fig.savefig(OUT/'training_overview.png',dpi=150);plt.close(fig)
rewardtags=[t for t in R['06fb5c1cf3a1']['tags'] if t.startswith('Episode_Reward/')]
fig,axes=plt.subplots(5,4,figsize=(16,18))
for ax,t in zip(axes.flat,rewardtags):
 for (label,ids),c in list(zip(branches.items(),colors))[:4]:
    x,y=merged(ids,t);xx,yy=binned(x,y,250);ax.plot(xx,yy,label=label,color=c,lw=1.1)
 ax.set_title(t.split('/')[-1],fontsize=9);ax.grid(alpha=.2)
axes.flat[0].legend(fontsize=7);fig.suptitle('Weighted per-episode reward terms / seconds, 250-update means');fig.tight_layout(rect=[0,0,1,.97]);fig.savefig(OUT/'reward_components.png',dpi=130);plt.close(fig)

rows=[]
for r in RS:
 a=r['ppo'];cmd=(r.get('commands') or {}).get('base_pose',{})
 rows.append(dict(id=r['run_id'],run=r['relative'],first=r.get('first'),last=r.get('last'),n=r.get('n'),num_envs=r['num_envs'],seed=r['seed'],robot='G1' if 'ame2_gaze' in r['relative'] else 'Go2',resume=r['resume'],parent_run=r['load_run'],parent_ckpt=r['load_checkpoint'],bf16=a.get('use_mixed_precision'),optimizer=a.get('optimizer'),lr=a.get('learning_rate'),epochs=a.get('num_learning_epochs'),minibatches=a.get('num_mini_batches'),rollout=r['rollout'],terrain_proportions=json.dumps(r['terrains']),command_class=cmd.get('class_type'),heading=json.dumps(cmd.get('ranges')),resampling=json.dumps(cmd.get('resampling_time_range')),env_yaml=r['params_env'],agent_yaml=r['params_agent'],event_paths=';'.join(e['path'] for e in r['events'])))
csvwrite(OUT/'run_catalog.csv',rows)
stats=[]
for label,ids in branches.items():
 for tag in tags+['Loss/kl_fp32','Loss/kl_bf16','Loss/kl_main','Loss/kl_fp32_down','Loss/kl_bf16_down','Loss/entropy','Loss/auxiliary','Perf/learning_time','Perf/collection_time']:
  x,y=merged(ids,tag)
  if not len(x):continue
  for lo,hi in [(8500,8999),(9001,9500),(10000,10427),(13501,14000),(14501,15000),(19500,19999),(0,499),(9500,9999)]:
   m=(x>=lo)&(x<=hi)
   if m.sum():stats.append(dict(branch=label,tag=tag,lo=lo,hi=hi,n=int(m.sum()),mean=float(y[m].mean()),min=float(y[m].min()),max=float(y[m].max())))
csvwrite(OUT/'key_windows.csv',stats)
ng=R['06fb5c1cf3a1'];peak={}
for t in tags:
 x,y=data(ng,t);xx,yy=binned(x,y,500);i=yy.argmax();peak[t]=dict(lo=int(x[x//500==int(xx[i]//500)].min()),hi=int(x[x//500==int(xx[i]//500)].max()),mean=float(yy[i]),final500=mean(ng,t,19500,19999))
(OUT/'nogap_peak.json').write_text(json.dumps(peak,indent=2),encoding='utf-8')

# Raw source comparison; new port files remain additions, not falsely equivalent.
UP=Path('C:/mai/wt/foothold-lab/analyst-ame2/_out/ame2_minimal');diffrows=[];difftexts=[]
for branch in ['ame2_nogap20k','ame2_br','ame2_st','ame2_spd','ame2_fp32','ame2_es20','ame2_m035']:
 for sub in ['rsl_rl/rsl_rl','go2/ame2_go2']:
  for p in sorted((RAW/branch/sub).rglob('*.py')):
   rel=p.relative_to(RAW/branch).as_posix();base=UP/rel;mapping='same path'
   if sub=='go2/ame2_go2':
    rem=p.relative_to(RAW/branch/sub).as_posix();mapped={'tasks/go2_env_cfg.py':'tasks/ame2_env_cfg.py','tasks/agents/rsl_rl_cfg.py':'tasks/agents/rsl_rl_ppo_cfg.py','tasks/terrains_go2.py':'tasks/terrains.py'}.get(rem,rem)
    base=UP/'ame2/ame2'/mapped;mapping='Go2 port mapped path'
   src=p.read_text(encoding='utf-8');old=base.read_text(encoding='utf-8') if base.exists() else ''
   status='same' if old==src else ('changed' if base.exists() else 'added')
   diffrows.append(dict(branch=branch,path=rel,official=str(base) if base.exists() else '',mapping=mapping,status=status,sha256=hashlib.sha256(p.read_bytes()).hexdigest(),lines=len(src.splitlines())))
   if branch=='ame2_st' and status=='changed':difftexts.extend(difflib.unified_diff(old.splitlines(True),src.splitlines(True),fromfile=str(base),tofile=str(p)))
csvwrite(OUT/'source_diff_inventory.csv',diffrows)
(DER/'official_vs_stones.diff').write_text(''.join(difftexts),encoding='utf-8')
print('PEAK',json.dumps(peak));print('DIFF',dict(collections.Counter((r['branch'],r['status']) for r in diffrows)))
for row in stats:
 if row['tag'] in tags[:4]+['Loss/learning_rate','Loss/kl_fp32','Loss/kl_bf16'] and (row['lo'],row['hi']) in [(8500,8999),(9001,9500),(14501,15000),(19500,19999),(9500,9999)]:print(json.dumps(row))
