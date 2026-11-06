"""Read-only EX41 stage analysis. CPU only; writes only --out and --scratch.

Raw training/evaluation sources are never imported or edited. Snapshot hashes and
JSON pointers are recorded; numeric tables and report numbers are generated.
"""
from __future__ import annotations
import argparse, csv, hashlib, io, json, math, re, subprocess
from datetime import datetime
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
from tensorboard.backend.event_processing.event_accumulator import EventAccumulator

RUN = Path('C:/Users/AI-WS01/s2_lab/ex41_main_20261104_235522')
TRAIN = RUN/'main/EX-41-B-main_20261104_235522'
BASE = Path('C:/Users/AI-WS01/s2_lab/ex40_main_20261031_041313/score-watch-b/model_6000_d5e9ec400f33/map64/map_modes.json')
PLAYLIST = Path('C:/Users/AI-WS01/s2_lab/_playlists/EX41-ALL-stages-1106.m3u8')
STAGES = [('S2a',1,750),('S2b',751,2750),('S2c',2751,3750),('S2d',3751,5000)]
MODES = ['eval_gt','eval_pred','probe_prop_only']
MODE_LABEL = {'eval_gt':'GT 정답','eval_pred':'Pred 복원','probe_prop_only':'지도 끔'}
COLORS = ['#007C83','#C35A00','#74528E']
FEET = ['FL','FR','RL','RR']
KEYS = {'vx':'vx_abs_error_mean_alive_mps','vy':'vy_abs_error_mean_alive_mps','wz':'wz_abs_error_mean_alive_radps'}
SOURCES = {}; VALIDATION=[]
plt.rcParams.update({'font.family':'Malgun Gothic','axes.unicode_minus':False,'font.size':10,
                     'axes.spines.top':False,'axes.spines.right':False,'savefig.facecolor':'white'})

def raw(path):
    p=Path(path); b=p.read_bytes()
    SOURCES[str(p)]={'path':str(p),'sha256':hashlib.sha256(b).hexdigest(),'bytes':len(b)}
    return b

def read(path): return json.loads(raw(path).decode('utf-8-sig'))
def lines(path): return [json.loads(x) for x in raw(path).decode('utf-8-sig').splitlines() if x.strip()]
def clean(x):
    if isinstance(x,dict): return {str(k):clean(v) for k,v in x.items()}
    if isinstance(x,(list,tuple)): return [clean(v) for v in x]
    if isinstance(x,np.generic): return clean(x.item())
    if isinstance(x,float) and not math.isfinite(x): return None
    return x
def dump(p,x): p.write_text(json.dumps(clean(x),ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
def csvout(p,rows):
    if not rows: return
    keys=list(dict.fromkeys(k for r in rows for k in r))
    with p.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(clean(rows))
def median(xs):
    v=[float(x) for x in xs if x is not None and math.isfinite(float(x))]
    return float(np.median(v)) if v else None
def fmt(x,n=3): return '미측정' if x is None else f'{x:.{n}f}'
def table_cell(value):
    # Escape only raw pipes; both header and data cells use this path.
    return re.sub(r'(?<!\\)\|', r'\\|', str(value))
def table(headers,rows):
    return '\n'.join(['| '+' | '.join(table_cell(v) for v in headers)+' |','| '+' | '.join(['---']*len(headers))+' |']+
                     ['| '+' | '.join(table_cell(v) for v in r)+' |' for r in rows])
def primary(c): return 'wz' if c.startswith('spin') else ('vy' if c.startswith('side') else 'vx')
def circ(angles):
    if not len(angles): return None,None
    z=np.mean(np.exp(1j*np.deg2rad(angles)))
    return (float(np.angle(z,deg=True)%360),float(abs(z))) if abs(z)>1e-10 else (None,float(abs(z)))
def phase(a,b,valid,dt):
    ha=np.flatnonzero(~a[:-1]&a[1:]&valid[:-1]&valid[1:])+1
    hb=np.flatnonzero(~b[:-1]&b[1:]&valid[:-1]&valid[1:])+1
    angles=[];period=[]
    for lo,hi in zip(ha[:-1],ha[1:]):
        if not valid[lo:hi+1].all(): continue
        ch=hb[(hb>=lo)&(hb<hi)]
        if len(ch): angles.append(360*(ch[0]-lo)/(hi-lo));period.append((hi-lo)*dt)
    deg,R=circ(angles)
    return {'deg':deg,'R':R,'cycles':len(angles),'period_s':median(period)}

def known_answers():
    t=np.arange(500); a=t%20<10; b=~a;v=np.ones(500,bool)
    assert abs(phase(a,b,v,.02)['deg']-180)<1e-9
    assert phase(a,a,v,.02)['deg']==0
    assert abs(phase(a,b,v,.02)['period_s']-.4)<1e-9
    assert phase(v,v,v,.02)['deg'] is None
    bad=v.copy();bad[35]=False
    assert phase(a,b,bad,.02)['cycles']<phase(a,b,v,.02)['cycles']
    assert median([1,None,3])==2
    assert primary('side-0.5')=='vy' and primary('spin+1.2')=='wz'
    assert [s for s,a,b in STAGES if a<=750<=b]==['S2a']
    assert [s for s,a,b in STAGES if a<=751<=b]==['S2b']
    VALIDATION.append('9 known-answer assertions passed: phase, missing cycles, dt, median, axis, boundary')

def get_maps():
    maps={0:read(BASE)};scores={};paths={0:str(BASE)}
    for p in sorted((RUN/'eval/scores').glob('score_*.json')):
        s=read(p); n=s['iteration']
        if n>5000: continue
        assert n not in scores,'duplicate score iteration'
        scores[n]=s
        es=[e for e in s['evidence'] if e['path'].replace('\\','/').endswith('/map64/map_modes.json')]
        assert len(es)==1
        e=es[0]; maps[n]=read(e['path']);paths[n]=e['path']
        assert SOURCES[str(Path(e['path']))]['sha256']==e['sha256']
        assert maps[n]['checkpoint_sha256']==s['checkpoint_sha256']
        cp=TRAIN/f'model_{n}.pt';raw(cp)
        assert SOURCES[str(cp)]['sha256']==s['checkpoint_sha256']
    assert set(scores)==set(range(250,5001,250))
    ref=maps[750]
    for n,m in maps.items():
        for key in ['envs','steps','eval_seed','command_suite','commands','terrain_columns']:
            assert m[key]==ref[key],(n,key)
        assert m['fixed_terrain']['assignment_sha256']==ref['fixed_terrain']['assignment_sha256']
    VALIDATION.append('20 score/map/checkpoint SHA matches; parent+20 maps env/step/seed/command/tile assignment matched')
    rows=[]
    for n,m in sorted(maps.items()):
        for mode in MODES:
            for case,c in m['modes'][mode].items():
                pe=c['per_env']; r={'iteration':n,'mode':mode,'case':case,'envs':len(pe),
                 'alive':sum(e['alive_at_end'] for e in pe),'source':paths[n],
                 'pointer':f'/modes/{mode}/{case}/per_env','tilt_rad':c['tilt_rad_mean_alive']}
                for ax,key in KEYS.items(): r[ax]=median(e.get(key) for e in pe)
                r['error']=r[primary(case)]; r['primary_axis']=primary(case)
                r['projected_distance_m']=median(e.get('command_xy_projection_integral_m') for e in pe)
                rows.append(r)
                if n:
                    suffix='_record_only' if mode=='eval_pred' else ''
                    counts=scores[n]['metrics']['record_counts'][f'{mode}/{case}{suffix}']
                    assert counts['passed']==r['alive'],(n,mode,case,counts)
    return maps,scores,rows,paths

def get_tb(scratch):
    files=list(TRAIN.glob('events.out.tfevents.*')); assert len(files)==1
    snap=scratch/files[0].name;snap.write_bytes(raw(files[0]))
    ea=EventAccumulator(str(snap),size_guidance={'scalars':0}).Reload(); series={}
    for tag in ea.Tags()['scalars']:
        if tag.endswith('/time'): continue
        vals={e.step:float(e.value) for e in ea.Scalars(tag) if 1<=e.step<=5000}
        if tag in ['Train/mean_reward','Train/mean_episode_length','Policy/mean_noise_std','Loss/learning_rate','Loss/kl_probe/ppo_mean','Loss/value_function']:
            assert len(vals)==5000,(tag,len(vals))
        elif len(vals)!=5000: VALIDATION.append(f'TB missing samples retained empty: {tag} {len(vals)}/5000')
        series[tag]=vals
    rows=[{'iteration':n,**{t:v.get(n) for t,v in series.items()}} for n in range(1,5001)]
    VALIDATION.append('TensorBoard snapshot: 6 core tags have all 5000 local updates; wall-time tags excluded')
    return series,rows

def get_w57():
    docs={};rows=[];gaits=[];rasters={}
    for stage,lo,hi in STAGES:
        root=next((RUN/'eval/score-watch').glob(f'model_{hi}_*'))
        p=root/'stage_end_auxiliary_eval/axis_v2/axis_v2/axis_v2.json'
        if not p.exists(): continue
        d=read(p);docs[hi]=d
        assert d['foot_order']==['FL_foot','FR_foot','RL_foot','RR_foot'],d['foot_order']
        for mode,cs in d['modes'].items():
            for case,c in cs.items():
                row={'iteration':hi,'mode':mode,'case':case,'alive':c['alive_at_end'],
                     'yaw_delta_deg':math.degrees(c['yaw_final_minus_start_median_rad']),
                     'stop_error_deg':math.degrees(c['stop_end_error_median_rad']) if c['stop_end_error_median_rad'] is not None else None,
                     'stop_abs_wz':c['stop_wz_mean_abs_median_radps'],
                     'stop_heading_signed_deg':math.degrees(c['stop_heading_flow_signed_median_rad']) if c['stop_heading_flow_signed_median_rad'] is not None else None,
                     'source':str(p),'pointer':f'/modes/{mode}/{case}'}
                rows.append(row)
                if case not in ['fwd0.5','fwd1.0']:continue
                f=p.parent/c['raw_file'];b=raw(f);assert hashlib.sha256(b).hexdigest()==c['raw_sha256']
                with np.load(io.BytesIO(b),allow_pickle=False) as z:
                    on=z['contact'].astype(bool);valid=z['alive'].astype(bool);dt=float(z['dt'])
                    rasters[(hi,mode,case)]=(on.copy(),valid.copy(),dt)
                    for env in range(on.shape[1]):
                        v=valid[:,env];o=on[:,env,:];r={'iteration':hi,'mode':mode,'case':case,'env':env,
                        'kind':str(z['terrain_kind'][env]),'level':int(z['terrain_level'][env]),
                        'samples':int(v.sum()),'four_contact':float(o[v].all(-1).mean()) if v.any() else None,
                        'source':str(f)}
                        r.update({f'duty_{ft}':float(o[v,j].mean()) if v.any() else None for j,ft in enumerate(FEET)})
                        for name,a,b in [('FL_RR',o[:,0],o[:,3]),('FR_RL',o[:,1],o[:,2]),('diagonal',o[:,0]&o[:,3],o[:,1]&o[:,2])]:
                            pp=phase(a,b,v,dt);r.update({f'{name}_{k}':x for k,x in pp.items()})
                        gaits.append(r)
    return docs,rows,gaits,rasters

def get_push():
    periodic=[];ends=[];record=[]
    for p in (RUN/'eval/push250').glob('*.json'):
        if not re.fullmatch(r'[1-9][0-9]*\.json',p.name):continue
        j=read(p);n=int(j['global_iteration'])-6000
        if not 1<=n<=5000:continue
        if 'terrains' not in j:
            VALIDATION.append(f'push250 evidence incomplete (not counted PASS): {p.name}, state={j.get("state")}')
        for t in j.get('terrains',[]):
            x=t['summary']; q=x['d171_1_5_worst_direction']
            periodic.append({'iteration':n,'terrain':x['terrain'],'mode':x['map_mode'],
             'worst_survival':q['survival_fraction'],'passed':q['passed'],'source':str(p),
             'command':x['command'],'level':x['level']})
    for stage,lo,hi in STAGES:
        root=next((RUN/'eval/score-watch').glob(f'model_{hi}_*'))
        p=root/'stage_end_auxiliary_eval/push_ladder/push_ladder/push_ladder_bundle.json'
        if not p.exists():continue
        j=read(p);assert j['state']=='done'
        for cell,x in j['stage_criteria']['walk_1.5mps_worst_direction'].items():
            ends.append({'iteration':hi,'cell':cell,**x,'source':str(p)})
        for cell,x in j['stage_criteria']['push_2.0mps_vs_m6000'].items():
            record.append({'iteration':hi,'cell':cell,**x,'source':str(p)})
    return periodic,ends,record

def get_w86():
    rows=[]
    for x in lines(TRAIN/'ex41_w86.jsonl'):
        n=x['iteration']
        if not 1<=n<=5000: continue
        f=x['feet'];r={'iteration':n,'quarantined':x['quarantine_env_count']}
        for i,ft in enumerate(FEET):
            r[f'drag_{ft}']=f['drag_frames'][i]/max(1,f['contact_moving_frames'][i])
            r[f'swing_peak_{ft}']=f['complete_swing_peak_sum_m'][i]/max(1,f['complete_swing_count'][i])
            r[f'knee_limit_{ft}']=f['knee_limit_frames'][i]/max(1,f['knee_valid_frames'][i])
        rows.append(r)
    return rows

def figsave(fig,p): fig.savefig(p,dpi=135,bbox_inches='tight');plt.close(fig)
def metric_fig(out,stage,lo,hi,rows,series,apps,push,phase_rows,rasters):
    prev=0 if lo==1 else lo-1
    cases=list(dict.fromkeys(r['case'] for r in rows))
    fig,axs=plt.subplots(5,3,figsize=(15,16))
    for ax,case in zip(axs.flat,cases):
        for mode,color in zip(MODES,COLORS):
            rr=[r for r in rows if r['case']==case and r['mode']==mode and prev<=r['iteration']<=hi]
            ax.plot([r['iteration'] for r in rr],[r['error'] for r in rr],'.-',color=color,label=MODE_LABEL[mode])
        ax.axhline(.15,color='#A62C2B',ls=':',lw=1);ax.set_title(case+' · '+primary(case));ax.grid(alpha=.2)
        ax.set_ylabel('rad/s' if primary(case)=='wz' else 'm/s')
    for ax in list(axs.flat)[len(cases):]:ax.axis('off')
    axs.flat[0].legend(fontsize=8);fig.suptitle(f'{stage} · 13 명령 주축 오차 · 점선 0.15는 기존 기록선\n각 env의 살아 있던 동안 평균 절대오차를 계산한 뒤 env 중앙값. 대각 vy·정지 yaw는 CSV 별도.',fontsize=13)
    fig.tight_layout(rect=[0,0,1,.96]);figsave(fig,out/f'{stage}-commands.png')
    ns=sorted({r['iteration'] for r in rows if prev<=r['iteration']<=hi})
    mat=np.array([[next(r['alive'] for r in rows if r['iteration']==n and r['mode']==m and r['case']==c) for n in ns] for m in MODES for c in cases])
    fig,ax=plt.subplots(figsize=(max(8,len(ns)*.6),13));im=ax.imshow(mat,vmin=55,vmax=64,aspect='auto',cmap='YlGnBu')
    ax.set_yticks(range(39),[f'{MODE_LABEL[m]} / {c}' for m in MODES for c in cases],fontsize=8)
    ax.set_xticks(range(len(ns)),['부모6000' if n==0 else str(n) for n in ns])
    for y,x in np.argwhere(mat<64):ax.text(x,y,str(mat[y,x]),ha='center',va='center',fontsize=7,color='black' if mat[y,x]<61 else 'white')
    fig.colorbar(im,ax=ax,label='종료까지 생존 / 64');ax.set_title(f'{stage} · 생존. 숫자가 없는 칸은 64/64');figsave(fig,out/f'{stage}-survival.png')
    specs=[('Loss/learning_rate','학습률',True),('Loss/kl_probe/ppo_mean','PPO KL probe',False),('Policy/mean_noise_std','행동 std',False),('Loss/value_function','value loss',False),('Train/mean_reward','평균 에피소드 보상',False),('Train/mean_episode_length','평균 에피소드 길이(step)',False),('reward_per_step','보상 / 길이',False),('Curriculum/terrain_levels','학습 지형 레벨',False)]
    fig,axs=plt.subplots(4,2,figsize=(14,14));xs=np.arange(lo,hi+1)
    for ax,(tag,label,log) in zip(axs.flat,specs):
        ys=np.array([series['Train/mean_reward'][int(n)]/series['Train/mean_episode_length'][int(n)] if tag=='reward_per_step' else series[tag][int(n)] for n in xs])
        ax.plot(xs,ys,color=COLORS[0],alpha=.3,lw=.5)
        bins=[(int(a),int(min(a+49,hi))) for a in range(lo,hi+1,50)]
        ax.plot([(a+b)/2 for a,b in bins],[np.median(ys[a-lo:b-lo+1]) for a,b in bins],color=COLORS[0],lw=1.4)
        if log:
            ax.set_yscale('log');ax.axhline(1e-5,color='#A62C2B',ls=':')
            ax.yaxis.set_major_formatter(FuncFormatter(lambda value,pos:f'{value:.0e}'))
        if tag=='Loss/kl_probe/ppo_mean':ax.axhline(.05,color='#A62C2B',ls=':')
        ax.set_title(label);ax.grid(alpha=.2)
    fig.suptitle(f'{stage} · 학습 곡선(연한 선: 매 갱신 / 진한 선: 50갱신 중앙값)');fig.tight_layout(rect=[0,0,1,.97]);figsave(fig,out/f'{stage}-training.png')
    fig,axs=plt.subplots(2,2,figsize=(14,8))
    groups=[['track_lin_vel','track_ang_vel'],['ex41_swing','ex41_zero_yaw','stumble'],['collision','joint_acc','action_rate','action_smoothness'],['ex40_stand_gap','ex40_stand_load','ex39_four_foot_stop']]
    for ax,gr in zip(axs.flat,groups):
        for tag in gr:
            vals=series['Episode_Reward/'+tag];xx=list(range(lo,hi+1,50))
            ax.plot(xx,[np.median([vals[k] for k in range(x,min(x+50,hi+1))]) for x in xx],label=tag)
        ax.legend(fontsize=8);ax.grid(alpha=.2)
    fig.suptitle(f'{stage} · 보상항 로그(가중·정규화된 Episode_Reward, 단위 혼합 합산 안 함)');fig.tight_layout(rect=[0,0,1,.96]);figsave(fig,out/f'{stage}-reward-terms.png')
    fig,axs=plt.subplots(1,2,figsize=(14,5))
    for kind,color in zip(['flat','random_rough','pyramid_stairs'],COLORS):
        rr=sorted([r for r in push if r['terrain']==kind and prev<=r['iteration']<=hi],key=lambda r:r['iteration'])
        axs[0].plot([r['iteration'] for r in rr],[r['worst_survival'] for r in rr],'.-',color=color,label=kind)
    axs[0].axhline(.9,ls=':',color='#A62C2B');axs[0].set(title='정기 밀기 · 걷기 1.0 · 외란 Δv 1.5 m/s',ylabel='8방향 중 최저 생존 비율',ylim=(0,1.04));axs[0].legend(fontsize=8)
    rr=[r for r in apps if lo<=r['iteration']<=hi and r.get('status')=='applied']; xx=[prev]+[r['iteration'] for r in rr]+[hi]
    scales=[rr[0]['after']['dr']['scale']]+[r['after']['dr']['scale'] for r in rr]+[rr[-1]['after']['dr']['scale']]
    axs[1].plot(xx,scales,'.-',color=COLORS[0]);axs[1].set(title='DR 경계 적용값',ylabel='무작위화 배율')
    for ax in axs:ax.grid(alpha=.2)
    fig.tight_layout();figsave(fig,out/f'{stage}-push-dr.png')
    fig,axs=plt.subplots(2,3,figsize=(15,7))
    for i,case in enumerate(['fwd0.5','fwd1.0']):
        for j,mode in enumerate(MODES):
            ax=axs[i,j];key=(hi,mode,case)
            if key not in rasters:ax.text(.5,.5,'원자료 미도착');continue
            on,valid,dt=rasters[key]
            # Fixed env 0, same kind/level across all W57 stage-end data.
            z=np.ma.array(on[:,0,:].T,mask=np.repeat(~valid[:,0][None,:],4,0))
            ax.imshow(z,aspect='auto',interpolation='nearest',cmap='Greys',vmin=0,vmax=1,extent=[0,len(on)*dt,3.5,-.5])
            ax.set_yticks(range(4),FEET);ax.set_title(f'{case} · {MODE_LABEL[mode]} · env0');ax.set_xlabel('초')
    fig.suptitle(f'{stage} · W57 접촉 위상(접촉 검정, 공중 흰색). 대표 env는 선택 고정, 전체 표본 통계는 CSV.');fig.tight_layout(rect=[0,0,1,.95]);figsave(fig,out/f'{stage}-contact.png')
    fig,axs=plt.subplots(1,3,figsize=(15,5))
    for ax,pair,target in zip(axs,['FL_RR','FR_RL','diagonal'],[0,0,180]):
        for j,mode in enumerate(MODES):
            for i,case in enumerate(['fwd0.5','fwd1.0']):
                pp=[r for r in phase_rows if r['iteration']==hi and r['mode']==mode and r['case']==case and r[pair+'_deg'] is not None]
                ys=[(r[pair+'_deg']-target+180)%360-180 for r in pp]
                ax.scatter(np.full(len(ys),i+(j-1)*.16),ys,s=11,alpha=.45,color=COLORS[j],label=MODE_LABEL[mode] if i==0 else None)
        ax.axhline(0,color='black',lw=.7);ax.set_xticks([0,1],['fwd0.5','fwd1.0']);ax.set(title=pair,ylabel='기준 위상과 차이(도)',ylim=(-180,180));ax.grid(alpha=.2)
    axs[0].legend(fontsize=8);fig.suptitle(f'{stage} · 완전 착지 주기 위상, 점 하나=env 하나. 수치 0 근처만으로 trot 합격을 선언하지 않음.');fig.tight_layout(rect=[0,0,1,.94]);figsave(fig,out/f'{stage}-phase.png')

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,default=Path(__file__).parent);ap.add_argument('--scratch',type=Path,default=Path('D:/mai-tmp/analyst/ex41-stage-reports-1106'));args=ap.parse_args()
    out=args.out;out.mkdir(parents=True,exist_ok=True);figs=out/'figs';figs.mkdir(exist_ok=True);data=out/'data';data.mkdir(exist_ok=True);args.scratch.mkdir(parents=True,exist_ok=True)
    known_answers();print('known-answer checks PASS',flush=True)
    maps,scores,rows,paths=get_maps();csvout(data/'command_cells.csv',rows);print('maps PASS',flush=True)
    tb,tbrows=get_tb(args.scratch);csvout(data/'training.csv',tbrows);print('TB PASS',flush=True)
    apps=[x for x in lines(TRAIN/'ex41_application.jsonl') if x['iteration']<=5001];dump(data/'application.json',apps)
    docs,w57,gait,rasters=get_w57();csvout(data/'w57.csv',w57);csvout(data/'phase_env.csv',gait)
    periodic,ends,record=get_push();csvout(data/'push250.csv',periodic);csvout(data/'push_stage_end.csv',ends);csvout(data/'push2_record.csv',record)
    w86=get_w86();csvout(data/'w86_training.csv',w86)
    # Extract all numbers first; prose and numeric tables are also generated below.
    for stage,lo,hi in STAGES:
        metric_fig(figs,stage,lo,hi,rows,tb,apps,periodic,gait,rasters)
        print('figures',stage,flush=True)
    summary={}
    for stage,lo,hi in STAGES:
        rr=[r for r in rows if lo<=r['iteration']<=hi];tr=[r for r in tbrows if lo<=r['iteration']<=hi]
        summary[stage]={'range':[lo,hi],'min_alive':min(r['alive'] for r in rr),'max_error':max(r['error'] for r in rr),
         'end_gt':{r['case']:{k:r[k] for k in ['vx','vy','wz','error','alive']} for r in rr if r['mode']=='eval_gt' and r['iteration']==hi},
         'lr_floor_count':sum(r['Loss/learning_rate']<=1.00001e-5 for r in tr),
         'kl_above_005':sum(r['Loss/kl_probe/ppo_mean']>.05 for r in tr),
         'training_first50':{k:median(r[k] for r in tr[:50]) for k in ['Train/mean_reward','Train/mean_episode_length','Policy/mean_noise_std','Loss/value_function','Loss/learning_rate']},
         'training_last50':{k:median(r[k] for r in tr[-50:]) for k in ['Train/mean_reward','Train/mean_episode_length','Policy/mean_noise_std','Loss/value_function','Loss/learning_rate']}}
    dump(data/'summary.json',summary);dump(data/'source_manifest.json',{'captured_at':datetime.now().astimezone().isoformat(),'sources':list(SOURCES.values()),'checks':VALIDATION})
    dump(data/'checks.json',VALIDATION);print(json.dumps(summary,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
