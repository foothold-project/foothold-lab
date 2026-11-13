"""TensorBoard window observations. Warnings cannot prescribe PPO changes."""
from pathlib import Path
import hashlib
import math
import re
import numpy as np

LR='Loss/learning_rate'
KL='Loss/kl_probe/ppo_mean'
STD='Policy/mean_noise_std'
EP='Train/mean_episode_length'
CORE=(LR,KL,'Loss/kl_probe/phi_mean',STD,EP,'Train/mean_reward','Loss/value_function')


def summarize_events(events,iteration,window=250,desired_kl=.01):
    latest={};duplicates=0
    for step,wall,tag,value in events:
        if step>iteration:continue
        key=(step,tag)
        if key in latest:duplicates+=1
        if key not in latest or wall>latest[key][0]:latest[key]=(wall,value)
    def part(lo,hi):
        tags={};bad=[]
        for tag in sorted({t for _,t in latest}):
            rows=sorted((n,x[1]) for (n,t),x in latest.items() if t==tag and lo<=n<=hi)
            if not rows:continue
            vals=[v for _,v in rows]
            if not all(math.isfinite(v) for v in vals):bad.append(tag);continue
            tags[tag]=dict(n=len(vals),first_step=rows[0][0],last_step=rows[-1][0],first=vals[0],last=vals[-1],
                           min=min(vals),median=float(np.median(vals)),mean=float(np.mean(vals)),max=max(vals))
        lr=[v for (n,t),(_,v) in latest.items() if t==LR and lo<=n<=hi and math.isfinite(v)]
        kl=[v for (n,t),(_,v) in latest.items() if t==KL and lo<=n<=hi and math.isfinite(v)]
        return dict(window=[lo,hi],tags=tags,nonfinite_tags=bad,lr_n=len(lr),
                    lr_floor_count=sum(math.isclose(v,1e-5,rel_tol=1e-6) for v in lr),
                    lr_floor_fraction=(sum(math.isclose(v,1e-5,rel_tol=1e-6) for v in lr)/len(lr) if lr else None),
                    kl_probe_n=len(kl),kl_probe_spikes=sum(v>2*desired_kl for v in kl) if kl else None,
                    kl_probe_spike_reference=2*desired_kl)
    now=part(max(1,iteration-window+1),iteration)
    prev=part(max(1,iteration-2*window+1),iteration-window) if iteration>window else None
    warnings=[]
    if now['lr_floor_count']:warnings.append('학습률 바닥 관측. 진동의 해로움은 이 비율만으로 판정하지 않음')
    if now['kl_probe_spikes']:warnings.append('진단 KL > 2×desired_kl 관측. 실제 scheduler minibatch KL과 다름')
    if STD in now['tags'] and now['tags'][STD]['min']<=0:warnings.append('noise std 0 이하. 원자료 확인 필요')
    if now['nonfinite_tags']:warnings.append('곡선에 비유한 값: '+','.join(now['nonfinite_tags']))
    if prev and EP in now['tags'] and EP in prev['tags'] and now['tags'][EP]['mean']<prev['tags'][EP]['mean']:
        warnings.append('에피소드 길이 창 평균 감소. 재개 버퍼 초기화·과제 조건도 확인')
    return dict(state='RECORDED' if latest else 'MISSING',current=now,previous=prev,
                duplicate_tag_steps=duplicates,warnings=warnings,prescription=None,
                interpretation='진단 기록만. noise std 붕괴의 임의 수치 문턱 없음. 승인 밖 PPO 변경 없음',
                lr_floor=dict(value=1e-5,grade='코드',source='rsl_rl adaptive scheduler 하한'),
                desired_kl=desired_kl)


def read_curves(run,iteration,out):
    from tensorboard.backend.event_processing.event_accumulator import EventAccumulator
    run=Path(run);out=Path(out);events=[];sources=[];errors=[]
    agent=run/'params/agent.yaml';desired=.01;config={}
    if agent.is_file():
        raw=agent.read_bytes();m=re.search(r'^\s*desired_kl:\s*([0-9.eE+-]+)',raw.decode(),re.M)
        if m:desired=float(m[1])
        config={'path':str(agent),'sha256':hashlib.sha256(raw).hexdigest(),'desired_kl':desired}
    files=sorted(run.glob('events.out.tfevents*'))
    for p in files:
        raw=p.read_bytes();digest=hashlib.sha256(raw).hexdigest()
        dst=out/'curve_snapshots'/(p.name+'.'+digest[:12]);dst.parent.mkdir(parents=True,exist_ok=True)
        if not dst.exists():dst.write_bytes(raw)
        if hashlib.sha256(dst.read_bytes()).hexdigest()!=digest:raise ValueError('curve snapshot hash differs')
        sources.append(dict(path=str(p),snapshot=str(dst),bytes=len(raw),sha256=digest))
        try:
            acc=EventAccumulator(str(dst),size_guidance={'scalars':0});acc.Reload()
            for tag in acc.Tags()['scalars']:
                if tag not in CORE and not tag.startswith('Episode_Reward/'):continue
                events.extend((e.step,e.wall_time,tag,e.value) for e in acc.Scalars(tag))
        except (OSError,ValueError,KeyError) as exc:errors.append(str(exc))
    d=summarize_events(events,iteration,desired_kl=desired)
    d.update(sources=sources,config=config,errors=errors,
             source_note='학습 중 append 파일을 읽은 바이트 사본. 경계 이후 값은 제외. 부분 마지막 event는 라이브러리가 제외')
    return d
