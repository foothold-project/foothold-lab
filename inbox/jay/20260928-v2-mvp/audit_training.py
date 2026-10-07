"""CPU-only checkpoint and event-file recount, no training or simulation."""
from audit_v2_mvp import *
import torch
from tensorboard.backend.event_processing.event_accumulator import EventAccumulator

def run(name): return next(LOG.glob('*_'+name+'*'))
def load(p): return torch.load(p,map_location='cpu',weights_only=False)
def tensors(obj,prefix=''):
    if torch.is_tensor(obj): yield prefix,obj
    elif isinstance(obj,dict):
        for k,v in obj.items(): yield from tensors(v,prefix+'/'+str(k))
    elif isinstance(obj,(tuple,list)):
        for k,v in enumerate(obj): yield from tensors(v,prefix+'/'+str(k))
def compare(a,b):
    ta=dict(tensors(a)); tb=dict(tensors(b)); diffs=[]; mx=0
    for k,x in ta.items():
        if k not in tb or x.shape!=tb[k].shape: diffs.append(k); continue
        if not torch.equal(x,tb[k]):
            diffs.append(k); mx=max(mx,float((x-tb[k]).abs().max()))
    return {'tensor_count':len(ta),'key_equal':ta.keys()==tb.keys(),'diffs':diffs,'max_abs_diff':mx}

torch.set_num_threads(2)
paths={'nv':LOG/'nvidia_pretrained_source/nvidia_pretrained.pt',
       'v2':run('v2g2-feetair01_')/'model_3000.pt',
       'fs1':run('fs1-scratch-f001')/'model_3000.pt',
       'ctrl':ROUGH/'model_1499.pt'}
r={'checkpoints':{},'events':{},'diffs':{}}
for name,p in paths.items():
    x=load(p); d=x['model_state_dict']; r['checkpoints'][name]={'path':str(p),'sha256':sha(p),'iter':x['iter'],'tensor_count':len(d),'actor':list(d['actor.0.weight'].shape),'critic':list(d['critic.0.weight'].shape),'optimizer_steps':sorted({float(v['step']) for v in x['optimizer_state_dict']['state'].values()})}
nv=load(paths['nv'])['model_state_dict']; r['rough_vs_nv']={}
for p in sorted(ROUGH.glob('model_*.pt')): r['rough_vs_nv'][p.name]=compare(nv,load(p)['model_state_dict'])
for name,d in {'ctrl':ROUGH,'v2':run('v2g2-feetair01_'),'fs1':run('fs1-scratch-f001'),'fs2':run('fs2-scratch-f01')}.items():
    ea=EventAccumulator(str(d),size_guidance={'scalars':0}); ea.Reload(); tags=ea.Tags()['scalars']; e={}
    for tag in tags:
        if tag=='Curriculum/terrain_levels' or 'learning_rate' in tag.lower() or 'termination' in tag.lower() or 'computation' in tag.lower() or 'time' in tag.lower():
            ss=ea.Scalars(tag); vals={v.step:v.value for v in ss}
            e[tag]={'count':len(ss),'unique_steps':len(vals),'min_step':min(vals),'max_step':max(vals),
                'points':{str(k):vals.get(k) for k in [0,6,8,175,500,1499,1500,3000,4500]},
                'ge5_9':sum(v>=5.9 for v in vals.values()),'peak':[max(vals,key=vals.get),max(vals.values())],
                'mean':avg(list(vals.values()))}
    r['events'][name]=e
v=run('v2g2-feetair01_')
for name,d in {'fs1':run('fs1-scratch-f001'),'fs2':run('fs2-scratch-f01'),'ctrl':ROUGH}.items():
    for file in ['env.yaml','agent.yaml']:
        a=(v/'params'/file).read_text(encoding='utf-8').splitlines(); b=(d/'params'/file).read_text(encoding='utf-8').splitlines()
        r['diffs'][name+'/'+file]=list(difflib.unified_diff(a,b,n=1))
r['gpu_pairs']={}
for label,a,b,limit in [('resume',run('v2b-r_'),run('v2b-p11_'),None),('scratch',run('probe-det-g0'),run('fs2-scratch-f01'),{0,25})]:
    common=sorted({p.name for p in a.glob('model_*.pt')} & {p.name for p in b.glob('model_*.pt')})
    if limit: common=[p for p in common if int(p[6:-3]) in limit]
    records=[]
    for filename in common:
        x=load(a/filename); y=load(b/filename)
        records.append({'file':filename,'same_file_sha':sha(a/filename)==sha(b/filename),
            'model':compare(x['model_state_dict'],y['model_state_dict']),
            'optimizer':compare(x['optimizer_state_dict'],y['optimizer_state_dict']),
            'optimizer_param_groups_equal':x['optimizer_state_dict']['param_groups']==y['optimizer_state_dict']['param_groups'],
            'iter_equal':x['iter']==y['iter']})
    r['gpu_pairs'][label]=records
    r['diffs'][label+'/env.yaml']=list(difflib.unified_diff((a/'params/env.yaml').read_text(encoding='utf-8').splitlines(),(b/'params/env.yaml').read_text(encoding='utf-8').splitlines(),n=1))
    r['diffs'][label+'/agent.yaml']=list(difflib.unified_diff((a/'params/agent.yaml').read_text(encoding='utf-8').splitlines(),(b/'params/agent.yaml').read_text(encoding='utf-8').splitlines(),n=1))
import numpy as np
import pyarrow.parquet as pq
r['timeseries_recount']={'files':0,'errors':[],'max_numeric_error':0.0}
# Parquet stores float32 samples. Compare serialized measurements at 1e-7,
# while retaining the actual maximum difference independently of this limit.
r['timeseries_recount']['absolute_tolerance']=1e-7
for model in ['v2g2-feetair01','fs1-scratch-f001','fs2-scratch-f01']:
    for it in [1500,2000,2500,3000]:
        base=RES/f'20260923-v2rs-axis2/{model}-iter{it}'
        for scenario in ['stop','hold','turn']:
            for entry in js(base/scenario/'per_env.json'):
                p=base/scenario/'timeseries'/entry['timeseries_file']
                t=pq.read_table(p); md=t.schema.metadata
                a=lambda k:t[k].to_numpy().astype(np.float64)
                tail=max(1,round(1/float(md[b'dt_s'])))
                measured={'residual_speed_mps':float(np.mean(a('speed_mps')[-tail:]))}
                targets=np.stack([a(k) for k in t.column_names if k.startswith('joint_target_')],axis=1)
                measured['joint_target_delta_tail']=float(np.mean(np.abs(np.diff(targets,axis=0)).sum(axis=1)[-tail:]))
                for k,v in measured.items():
                    delta=abs(v-entry[k]); r['timeseries_recount']['max_numeric_error']=max(delta,r['timeseries_recount']['max_numeric_error'])
                    if delta>1e-7:r['timeseries_recount']['errors'].append([str(p),k,delta])
                for k,v in entry.get('yaw_follow',{}).items():
                    target=float(k); picked=a('base_wz_rps')[np.abs(a('cmd_wz_rps')-target)<.05]
                    value=float(np.mean(picked[len(picked)//2:])/target)
                    delta=abs(value-v['ratio']); r['timeseries_recount']['max_numeric_error']=max(delta,r['timeseries_recount']['max_numeric_error'])
                    if delta>1e-7:r['timeseries_recount']['errors'].append([str(p),'yaw',k,delta])
                if math.isfinite(float(md[b'fell_at_s']))!=entry['fell']:r['timeseries_recount']['errors'].append([str(p),'fell metadata'])
                r['timeseries_recount']['files']+=1
(OUT/'audit_training_results.json').write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
print('timeseries', {k:(len(v) if k=='errors' else v) for k,v in r['timeseries_recount'].items()})
print('checkpoints',r['checkpoints'])
print('rough',len(r['rough_vs_nv']),'1499',r['rough_vs_nv']['model_1499.pt'])
for name,e in r['events'].items():
    print(name,{k:v for k,v in e.items() if k=='Curriculum/terrain_levels' or 'learning_rate' in k.lower()})
for k,v in r['gpu_pairs'].items(): print('GPU',k,len(v),'model_diffs',sum(bool(x['model']['diffs']) for x in v),'optimizer_diffs',sum(bool(x['optimizer']['diffs']) for x in v),'sha_same',sum(x['same_file_sha'] for x in v))
