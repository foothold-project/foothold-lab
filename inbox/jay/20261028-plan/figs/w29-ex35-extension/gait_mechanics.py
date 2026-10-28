"""W29 CPU figures: contact, stance locations, joints, and video termination timing."""
from pathlib import Path
import json,csv,hashlib
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
O=Path(__file__).resolve().parent
R=Path('C:/mai/wt/foothold-lab/impl-turncases/logs')
dirs={1500:R/'sb10_eval/m1500',2000:R/'ex35_eval/m2000',3000:R/'ex35ext_eval/m3000'}
F=[4,8,14,18];names=['FL','FR','RL','RR'];colors=['#126B62','#A34B16','#634E8E','#254D78']
g=pd.read_csv(O/'gait_env.csv')
summary=g.groupby(['iter','mode','case','pair']).agg(envs=('env','count'),valid_phase_envs=('deg','count'),cycles=('cycles','sum'),phase_error_deg=('error_abs','mean'),R_mean=('R','mean'),period_s=('period','mean'),C=('C','mean'),duty=('duty','mean'),contact_xy_proxy=('contact_xy_proxy','mean'),vx=('vx','mean')).reset_index()
summary.to_csv(O/'gait_summary.csv',index=False,encoding='utf-8-sig')
fig,axs=plt.subplots(4,3,figsize=(15,12),sharex=True)
fig2,axy=plt.subplots(4,3,figsize=(14,13))
for row,(mode,case) in enumerate((('eval_gt','fwd0.5'),('eval_gt','fwd1.0'),('probe_prop_only','fwd0.5'),('probe_prop_only','fwd1.0'))):
 for col,(n,d) in enumerate(dirs.items()):
  with np.load(d/f'turn16_{mode}'/f'arrays_{case}.npz',allow_pickle=False) as z:
   on=z['force'][0][:,F]>1;t=np.arange(on.shape[0])/200;al=z['alive'][0].astype(bool)
   ax=axs[row,col]
   for f in range(4):
    idx=np.flatnonzero(on[:,f]&al);ax.scatter(t[idx],np.full(len(idx),f),s=4,marker='|',color=colors[f])
   ax.set_yticks(range(4),names);ax.set_ylim(-.5,3.5);ax.set_title(f'm{n} {mode} {case}\nenv0 kept={bool(z["kept"][0])}',fontsize=9);ax.grid(axis='x',alpha=.2)
   xy=axy[row,col];pos=z['feet_pos'][0];start=z['root_pos'][0,0,:2]
   for f in range(4):
    ids=on[:,f]&al;xy.scatter(pos[ids,f,0]-start[0],pos[ids,f,1]-start[1],s=3,color=colors[f],label=names[f])
   xy.plot(z['root_pos'][0,al,0]-start[0],z['root_pos'][0,al,1]-start[1],color='#222222',lw=.7,label='root path')
   xy.set_aspect('equal',adjustable='datalim');xy.set_title(f'm{n} {mode} {case}',fontsize=9);xy.grid(alpha=.2)
for ax in axs[-1]:ax.set_xlabel('Recorded segment time (s)')
for ax in axy[-1]:ax.set_xlabel('World X relative to root start (m)')
for ax in axy[:,0]:ax.set_ylabel('World Y (m)')
axy[0,0].legend(fontsize=7,ncol=2)
fig.suptitle('Forward contact bars: one fixed environment, 1 N contact, pre-reset only\nPopulation statistics use all kept environments; this is an illustrative env0 trace.');fig.tight_layout(rect=[0,0,1,.94]);fig.savefig(O/'forward_contacts.png',dpi=150);plt.close(fig)
fig2.suptitle('Stance foot locations, env0; points are contact samples, not discrete footsteps\nWorld-frame positions relative to root start; no COM or support-surface assumption.');fig2.tight_layout(rect=[0,0,1,.94]);fig2.savefig(O/'stance_xy.png',dpi=150);plt.close(fig2)

# Entire-population pre-first-fall joints, separated from survivor-only Q.
fig,axs=plt.subplots(4,3,figsize=(15,12),sharex=True)
for col,(n,d) in enumerate(dirs.items()):
 for case,c in [('indep_left','#A34B16'),('indep_right','#126B62')]:
  with np.load(d/'turn16_eval_gt'/f'arrays_{case}.npz',allow_pickle=False) as z:
   t=np.arange(z['alive'].shape[1])/200;e=0;alive=z['alive'][e].astype(bool);q=z['root_quat'][e]
   tilt=np.rad2deg(np.arccos(np.clip(1-2*(q[:,1]**2+q[:,2]**2),-1,1)))
   axs[0,col].plot(t[alive],tilt[alive],label=case,color=c)
   axs[1,col].plot(t[alive],z['wz'][e,alive],label=case,color=c)
   for f in range(4):
    # Joint order is grouped by joint kind: four hip, four thigh, four calf.
    axs[2,col].plot(t[alive],np.rad2deg(z['q'][e,alive,4+f]),color=colors[f],ls='-' if case=='indep_left' else ':',lw=.8,label=names[f]+' '+case)
    axs[3,col].plot(t[alive],np.rad2deg(z['q'][e,alive,8+f]),color=colors[f],ls='-' if case=='indep_left' else ':',lw=.8)
 axs[0,col].set_title(f'm{n}, env0, valid segment only')
for i,lab in enumerate(('Tilt (deg)','Yaw speed (rad/s)','Thigh position (deg)','Calf position (deg)')):
 for ax in axs[i]:ax.set_ylabel(lab);ax.grid(alpha=.2)
axs[0,0].legend(fontsize=8);axs[2,0].legend(fontsize=6,ncol=2)
fig.suptitle('Left/right spin posture and joints, selected env0\nSolid left, dotted right for joint traces. No causal attribution from one environment.');fig.tight_layout(rect=[0,0,1,.94]);fig.savefig(O/'spin_joints.png',dpi=150);plt.close(fig)

video=json.loads((O/'video_audit.json').read_text(encoding='utf-8'));rows=[]
for v in video:
 p=Path(v['path']).with_name('review_feet.npz')
 with np.load(p,allow_pickle=False) as z:
  for event in v['resets']:
   ti=event['t'];ids=np.flatnonzero((z['t']>=max(0,ti-.6))&(z['t']<=ti))
   for i in ids:
    rows.append({'video':str(p.parent),'t':z['t'][i],'reset_t':ti,'roll_deg':np.rad2deg(z['roll'][i]),'pitch_deg':np.rad2deg(z['pitch'][i]),'wz':z['wz'][i],**{f'contact_{name}':bool(z['foot_contact'][i,k]) for k,name in enumerate(names)},'done':bool(z['done'][i])})
pd.DataFrame(rows).to_csv(O/'video_pretermination.csv',index=False,encoding='utf-8-sig')
print(summary[(summary['pair']=='between')&(summary['iter'].isin([1500,2000,3000]))].round(4).to_string(index=False))
