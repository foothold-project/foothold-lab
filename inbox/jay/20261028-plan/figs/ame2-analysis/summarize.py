from pathlib import Path
import os,sys,json,csv,hashlib,collections,concurrent.futures
os.environ['CUDA_VISIBLE_DEVICES']=''
os.environ['TF_CPP_MIN_LOG_LEVEL']='3'
import numpy as np,yaml
from tensorboard.backend.event_processing.event_accumulator import EventAccumulator

ROOT=Path('D:/mai-data/ame2/raw'); OUT=ROOT.parent/'derived';OUT.mkdir(exist_ok=True)

def yamlread(p):
    return yaml.load(p.read_text(encoding='utf-8'),Loader=yaml.BaseLoader) if p.exists() else {}
def fields(env,agent):
    terrain=env.get('scene',{}).get('terrain',{}).get('terrain_generator',{}) or {}
    alg=agent.get('algorithm',{})
    return dict(num_envs=env.get('scene',{}).get('num_envs'),seed=agent.get('seed'),rollout=agent.get('num_steps_per_env'),
      max_iterations=agent.get('max_iterations'),resume=agent.get('resume'),load_run=agent.get('load_run'),load_checkpoint=agent.get('load_checkpoint'),
      actor=agent.get('actor'),critic=agent.get('critic'),ppo=alg,clip_actions=agent.get('clip_actions'),
      episode_length_s=env.get('episode_length_s'),decimation=env.get('decimation'),sim_dt=env.get('sim',{}).get('dt'),
      terrains={k:v.get('proportion') for k,v in terrain.get('sub_terrains',{}).items()},rows=terrain.get('num_rows'),columns=terrain.get('num_cols'),
      commands=env.get('commands'),rewards=env.get('rewards'),observations=env.get('observations'),actions=env.get('actions'),curriculum=env.get('curriculum'))

eventgroups=collections.defaultdict(list)
for p in ROOT.rglob('events.out.tfevents*'):
    if '/pre/' in p.as_posix():continue
    eventgroups[p.parent].append(p)
seen={};jobs=[];aliases=[]
for d,ps in sorted(eventgroups.items()):
    ids=tuple(sorted(hashlib.sha256(p.read_bytes()).hexdigest() for p in ps))
    if ids in seen:
        aliases.append({'alias':str(d),'same_events_as':str(seen[ids])});continue
    seen[ids]=d;jobs.append((d,ps))
(OUT/'event_aliases.json').write_text(json.dumps(aliases,indent=2),encoding='utf-8')
print('run_directories',len(eventgroups),'unique',len(jobs),flush=True)

def one(job):
    d,ps=job;key=hashlib.sha256(str(d.relative_to(ROOT)).encode()).hexdigest()[:12]
    ap=d/'params/agent.yaml';ep=d/'params/env.yaml'
    agent=yamlread(ap);env=yamlread(ep)
    ea=EventAccumulator(str(d),size_guidance={'scalars':0},purge_orphaned_data=False);ea.Reload()
    tags=ea.Tags()['scalars'];arrays={};summaries=[]
    for i,t in enumerate(tags):
        ev=ea.Scalars(t);x=np.array([e.step for e in ev],dtype=np.int64);v=np.array([e.value for e in ev],dtype=float)
        wt=np.array([e.wall_time for e in ev],dtype=float)
        order=np.argsort(wt,kind='stable');idx={int(x[k]):int(k) for k in order};sel=np.array([idx[n] for n in sorted(idx)])
        x=x[sel];v=v[sel];wt=wt[sel]
        arrays[f'x{i}']=x;arrays[f'y{i}']=v;arrays[f't{i}']=wt
        for w in np.unique(x//500):
            m=x//500==w;a=v[m]
            summaries.append(dict(run_id=key,run=str(d.relative_to(ROOT)),tag=t,lo=int(x[m].min()),hi=int(x[m].max()),n=int(m.sum()),mean=float(a.mean()),std=float(a.std()),min=float(a.min()),max=float(a.max())))
    np.savez_compressed(OUT/f'{key}.npz',**arrays)
    meta=dict(run_id=key,path=str(d),relative=str(d.relative_to(ROOT)),events=[dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in ps],
      tags=tags,params_agent=str(ap) if ap.exists() else None,params_env=str(ep) if ep.exists() else None,**fields(env,agent))
    if 'Train/mean_reward' in tags:
        i=tags.index('Train/mean_reward');x=arrays[f'x{i}'];v=arrays[f'y{i}'];meta.update(first=int(x[0]),last=int(x[-1]),n=len(x),reward_last100=float(v[-100:].mean()),reward_max=float(v.max()),reward_max_step=int(x[v.argmax()]))
    print('parsed',d.name,meta.get('first'),meta.get('last'),len(tags),flush=True)
    return meta,summaries

allmeta=[];allwindows=[]
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
    for m,w in pool.map(one,jobs):allmeta.append(m);allwindows.extend(w)
(OUT/'runs.json').write_text(json.dumps(allmeta,ensure_ascii=False,indent=2),encoding='utf-8')
with (OUT/'tag_windows500.csv').open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(allwindows[0]));w.writeheader();w.writerows(allwindows)
print('DONE',len(allmeta),'windows',len(allwindows),flush=True)
