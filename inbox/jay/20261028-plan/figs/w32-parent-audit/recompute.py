"""W32 CPU-only independent audit. Reads stored arrays, never imports Isaac."""
from pathlib import Path
import json, csv, hashlib, os, sys
os.environ['CUDA_VISIBLE_DEVICES']=''
sys.dont_write_bytecode=True
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

OUT=Path(__file__).resolve().parent
R=Path('C:/mai/wt/foothold-lab/impl-turncases/logs')
TRAIN=Path('C:/mai/wt/foothold-lab/impl-sb/logs/rsl_rl/foothold_s2_sb/2026-10-26_01-17-47_sb-main')
NS=list(range(1050,1501,50)); MODES=('eval_gt','probe_prop_only')
CASES=('indep_left','indep_right','fwd_then_left','fwd_then_right','right_then_left','left_then_right')
FEET=[4,8,14,18]; sources={}; contract=[]
COLORS=['#126B62','#A34B16']; LABEL=['GT on','map masked']

def source(p):
    b=p.read_bytes();sources[str(p)]={'path':str(p),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()};return b
def read(p):return json.loads(source(p).decode('utf-8-sig'))
def jl(p):return [json.loads(s) for s in source(p).decode('utf-8-sig').splitlines() if s.strip()]
def dump(name,x): (OUT/name).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
def csvout(name,rows):
    with (OUT/name).open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(dict.fromkeys(k for row in rows for k in row)));w.writeheader();w.writerows(rows)
def circ(aa):
    if not aa:return None,None
    z=np.mean(np.exp(1j*np.deg2rad(aa)))
    return float(np.angle(z,deg=True)%360) if abs(z)>1e-10 else None,float(abs(z))
def phase(a,b,valid):
    ha=np.flatnonzero(~a[:-1]&a[1:]&valid[:-1]&valid[1:])+1
    hb=np.flatnonzero(~b[:-1]&b[1:]&valid[:-1]&valid[1:])+1
    ang=[];period=[]
    for lo,hi in zip(ha[:-1],ha[1:]):
        if not valid[lo:hi+1].all():continue
        hit=hb[(hb>=lo)&(hb<hi)]
        if len(hit):ang.append(360*(hit[0]-lo)/(hi-lo));period.append((hi-lo)/200)
    deg,rr=circ(ang)
    return {'deg':deg,'R':rr,'cycles':len(ang),'period':float(np.median(period)) if period else None}
def avg(x):return float(np.mean(x)) if len(x) else None
def qstat(z,sign):
    a=z['alive'].astype(bool);k=z['kept'].astype(bool)&a.any(1)
    return {'Q':avg([np.mean(z['wz'][e,a[e]],dtype=np.float64)*sign for e in np.flatnonzero(k)]),
            'C':avg([(z['force'][e,a[e]][:,FEET]>1).all(1).mean() for e in np.flatnonzero(k)]),'kept':int(k.sum())}

# Answer-known inputs: equal env weighting and full, unbroken contact cycles.
fake={'alive':np.array([[1,1,1,1],[1,0,0,0]],bool),'kept':np.ones(2,bool),'wz':np.array([[0,0,0,0],[4,0,0,0]]),'force':np.full((2,4,19),2)}
assert qstat(fake,1)['Q']==2 and qstat(fake,-1)['Q']==-2
fake['kept'][1]=False;assert qstat(fake,1)['Q']==0
t=np.arange(1000);a=t%100<50;b=(t+50)%100<50;v=np.ones(1000,bool)
assert phase(a,b,v)['deg']==180 and phase(a,a,v)['deg']==0
assert phase(v,v,v)['cycles']==0
v[250]=False;assert phase(a,b,v)['cycles']<phase(a,b,np.ones(1000,bool))['cycles']

maps=[];turn=[];gait=[];envg=[]
for n in NS:
    d=R/'sb10_eval'/f'm{n}';mp=d/'map64/map_modes.json';j=read(mp)
    contract.append({'iter':n,'kind':'map64','task':j['task'],'terrain_hash':j['terrain_hash'],'envs':j['envs'],'steps':j['steps'],'dr_off':j['dr_off'],'curriculum_off':j['curriculum_off'],'checkpoint_sha256':j['checkpoint_sha256']})
    for mode in MODES:
        for c,x in j['modes'][mode].items():
            maps.append({'iter':n,'mode':mode,'case':c,'distance_m':x['body_vx_integral_median_m'],'follow':x['yaw_follow_median'],'alive':x['alive_envs_at_end'],'tilt_rad':x['tilt_rad_mean_alive'],'stall':x['stalled_fraction_2to4s'],'path':str(mp)})
        td=d/f'turn16_{mode}';meta=read(td/'probe_result.json')
        assert meta['envs']==16 and meta['static']['sample_hz']==200
        assert [meta['static']['link_names'][i] for i in FEET]==['FL_foot','FR_foot','RL_foot','RR_foot']
        # pre-motion changes the starting pose by design. Compare prescribed pre/command, not achieved pose.
        sig={c:{k:meta['protocols'][c].get(k) for k in ('cmd','pre','terrain_levels_per_env','terrain_types_per_env')} for c in CASES}
        contract.append({'iter':n,'kind':mode,'terrain_hash':meta['fixed_terrain']['assignment_sha256'],'logic':meta['logic_blob_sha'],'protocol_sha':hashlib.sha256(json.dumps(sig,sort_keys=True).encode()).hexdigest(),'checkpoint_sha256':meta['checkpoint_sha256']})
        for c in CASES:
            p=td/f'arrays_{c}.npz';source(p)
            with np.load(p,allow_pickle=False) as z: s=qstat(z,1 if c.endswith('left') else -1)
            turn.append({'iter':n,'mode':mode,'case':c,**s,'path':str(p)})
        for c in ('fwd0.5','fwd1.0'):
            p=td/f'arrays_{c}.npz';source(p)
            with np.load(p,allow_pickle=False) as z:
                alive=z['alive'].astype(bool);kept=z['kept'].astype(bool);contact=z['force'][...,FEET]>1
                for e in np.flatnonzero(kept):
                    valid=alive[e];on=contact[e];base={'iter':n,'mode':mode,'case':c,'env':int(e),'C':float(on[valid].all(1).mean()),'duty':float(on[valid].mean()),'vx':float(z['vx'][e,valid].mean()),'slip_proxy_mps':float(z['link_xy_speed'][e][:,FEET][valid][on[valid]].mean())}
                    for pair,(a,b) in {'between':(on[:,0]&on[:,3],on[:,1]&on[:,2]),'FL_RR':(on[:,0],on[:,3]),'FR_RL':(on[:,1],on[:,2])}.items():
                        ph=phase(a,b,valid);target=180 if pair=='between' else 0
                        envg.append({**base,'pair':pair,**ph,'abs_phase_error':abs((ph['deg']-target+180)%360-180) if ph['deg'] is not None else None})
            for pair in ('between','FL_RR','FR_RL'):
                rr=[r for r in envg if r['iter']==n and r['mode']==mode and r['case']==c and r['pair']==pair];vv=[r for r in rr if r['deg'] is not None];deg,res=circ([r['deg'] for r in vv])
                gait.append({'iter':n,'mode':mode,'case':c,'pair':pair,'kept':int(kept.sum()),'valid_envs':len(vv),'cycles':sum(r['cycles'] for r in vv),'deg':deg,'R':res,'abs_phase_error':avg([r['abs_phase_error'] for r in vv]),'period_s':avg([r['period'] for r in vv]),**{k:avg([r[k] for r in rr]) for k in ('C','duty','vx','slip_proxy_mps')}})

# Tensorboard scalars retain each update. We do not import simulation/training code.
from tensorboard.backend.event_processing.event_accumulator import EventAccumulator
ev=next(TRAIN.glob('events.out*'));source(ev);ea=EventAccumulator(str(ev),size_guidance={'scalars':0});ea.Reload()
tags=ea.Tags()['scalars'];dump('tensorboard_tags.json',tags)
curve={}
for tag in tags:
    for x in ea.Scalars(tag):
        if 1000<=x.step<=1500:curve.setdefault(x.step,{'iter':x.step})[tag]=float(x.value)
extra=jl(TRAIN/'train_extra.jsonl');switch=jl(TRAIN/'map_switch.jsonl')
for x in extra:
    if x['it'] in curve:
        for stage in ('ppo','phi'):
            for subset in ('all','spin','walk'):
                curve[x['it']][f'probe_{stage}_{subset}_KL']=x['kl_probe'][stage][subset]['mean']
windows=[]
for lo,hi in ((1001,1100),(1101,1200),(1201,1300),(1301,1400),(1401,1500)):
    rr=[r for it,r in curve.items() if lo<=it<=hi];ss=[r for r in switch if lo<=r['it']<=hi]
    row={'first':lo,'last':hi,'n':len(rr)}
    for k in sorted({k for r in rr for k in r if k!='iter'}):
        vals=[r[k] for r in rr if r.get(k) is not None];row[k]=avg(vals)
    for mode in ('on','off'):
        denom=sum(r[mode]['env_steps'] for r in ss)
        for k in ('terrain_level_mean','track_lin_vel_per_s','track_ang_vel_per_s'):
            row[f'{mode}_{k}']=sum(r[mode][k]*r[mode]['env_steps'] for r in ss)/denom
    row['off_frac']=sum(r['off']['env_steps'] for r in ss)/sum(r['off']['env_steps']+r['on']['env_steps'] for r in ss)
    windows.append(row)

# Descriptive Pearson correlations only, no independence test/p value on checkpoints.
cors=[]
for mode in MODES:
    xx=np.array([next(r['distance_m'] for r in maps if r['iter']==n and r['mode']==mode and r['case']=='fwd1.0') for n in NS])
    for c in CASES:
        yy=np.array([next(r['Q'] for r in turn if r['iter']==n and r['mode']==mode and r['case']==c) for n in NS])
        cors.append({'mode':mode,'case':c,'n':len(NS),'pearson_levels':float(np.corrcoef(xx,yy)[0,1]),'pearson_first_differences':float(np.corrcoef(np.diff(xx),np.diff(yy))[0,1]),'note':'descriptive; checkpoints dependent; no causal or p-value claim'})
noise=[]
j1=read(R/'b1500_baseline/rep1/map64/map_modes.json');j2=read(R/'b1500_baseline/rep2/map64/map_modes.json')
for mode,d in j1['modes'].items():
    for c,x in d.items():
        y=j2['modes'][mode][c];noise.append({'mode':mode,'case':c,'alive1':x['alive_envs_at_end'],'alive2':y['alive_envs_at_end'],'abs_distance_diff':abs(x['body_vx_integral_median_m']-y['body_vx_integral_median_m']),'abs_follow_diff':abs(x['yaw_follow_median']-y['yaw_follow_median'])})
for name,rows in [('map64.csv',maps),('turn16.csv',turn),('gait.csv',gait),('gait_env.csv',envg),('training_raw.csv',[curve[n] for n in sorted(curve)]),('training_windows.csv',windows),('correlations.csv',cors),('repeat_noise_B.csv',noise)]:csvout(name,rows)
dump('contracts.json',contract)
for kind in ('map64',)+MODES:
    rr=[r for r in contract if r['kind']==kind]
    hashes={h for r in rr for h in (r['terrain_hash'].values() if isinstance(r['terrain_hash'],dict) else [r['terrain_hash']])}
    assert len(hashes)==1
    if kind!='map64':assert len({r['protocol_sha'] for r in rr})==1 and len({json.dumps(r['logic'],sort_keys=True) for r in rr})==1

fig,axs=plt.subplots(3,2,figsize=(13,11),sharex=True)
for j,mode in enumerate(MODES):
    for c,ls in [('fwd1.0','-'),('fwd0.5',':')]:
        rr=[r for r in maps if r['mode']==mode and r['case']==c]
        axs[0,j].plot(NS,[r['distance_m'] for r in rr],ls+'o',label=c,color=COLORS[j]);axs[1,j].plot(NS,[r['alive'] for r in rr],ls+'o',label=c,color=COLORS[j])
    for c,cc in zip(('spin+1.2','spin-1.2'),COLORS):
        rr=[r for r in maps if r['mode']==mode and r['case']==c];axs[2,j].plot(NS,[r['follow'] for r in rr],'o-',label=c,color=cc)
    axs[0,j].set_title(LABEL[j]);axs[0,j].set_ylabel('Body-forward integral median (m), 6 s');axs[1,j].set_ylabel('Alive / 64');axs[1,j].set_ylim(58,65);axs[2,j].set_ylabel('Yaw / commanded yaw (64-env median)')
for ax in axs.flat:ax.grid(alpha=.2);ax.legend(fontsize=8)
for ax in axs[-1]:ax.set_xlabel('S-B10 checkpoint')
fig.suptitle('S-B10 m1050..1500: forward loss exists with both map conditions\nFixed low-level 64-env evaluation; not terrain-wise completion distance.');fig.tight_layout(rect=[0,0,1,.94]);fig.savefig(OUT/'forward_rotation64.png',dpi=160);plt.close(fig)
fig,axs=plt.subplots(3,2,figsize=(13,11),sharex=True)
for ax,c in zip(axs.flat,CASES):
    for mode,cc,lab in zip(MODES,COLORS,LABEL):
        rr=[r for r in turn if r['mode']==mode and r['case']==c];ax.plot(NS,[r['Q'] for r in rr],'o-',color=cc,label=lab)
        for r in rr:
            if r['kept']<16:ax.annotate(str(r['kept']), (r['iter'],r['Q']),fontsize=7)
    ax.set_title(c);ax.set_ylabel('Q (rad/s), kept-env average');ax.grid(alpha=.2)
axs[0,0].legend();fig.suptitle('Same parent checkpoints, six 16-env turn protocols\nNumbers annotate kept < 16; 64-env median and 16-env mean are different statistics.');fig.tight_layout(rect=[0,0,1,.94]);fig.savefig(OUT/'rotation_six.png',dpi=160);plt.close(fig)
fig,axs=plt.subplots(3,2,figsize=(13,10),sharex=True)
for j,c in enumerate(('fwd0.5','fwd1.0')):
    for mode,cc,lab in zip(MODES,COLORS,LABEL):
        rr=[r for r in gait if r['mode']==mode and r['case']==c and r['pair']=='between']
        for i,(key,label) in enumerate([('abs_phase_error','Mean absolute diagonal phase error (deg)'),('C','Four-feet contact fraction'),('slip_proxy_mps','Contact-link XY speed proxy (m/s)')]):axs[i,j].plot(NS,[r[key] for r in rr],'o-',color=cc,label=lab);axs[i,j].set_ylabel(label)
    axs[0,j].set_title(c)
for ax in axs.flat:ax.grid(alpha=.2)
axs[0,0].legend();fig.suptitle('Parent gait audit, 16-env forward protocols, complete cycles only\nXY link speed is a slip proxy; no contact-point tangential velocity.');fig.tight_layout(rect=[0,0,1,.94]);fig.savefig(OUT/'forward_gait.png',dpi=160);plt.close(fig)
dump('sources.json',list(sources.values()))
assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==r['sha256'] for p,r in sources.items())
dump('audit.json',{'known_answer_checks':7,'checkpoints':NS,'map_rows':len(maps),'turn_rows':len(turn),'gait_rows':len(gait),'unchanged_source_files':len(sources),'nan_fields':sum(v is None for r in gait for v in r.values())})
print(json.dumps({'map_at_1050_1500':[r for r in maps if r['iter'] in (1050,1500)],'audit':read(OUT/'audit.json')},ensure_ascii=False))
