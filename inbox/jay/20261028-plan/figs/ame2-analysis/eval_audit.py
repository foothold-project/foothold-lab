from pathlib import Path
import os,json,csv,hashlib
os.environ['CUDA_VISIBLE_DEVICES']=''
import torch,numpy as np
R=Path('D:/mai-data/ame2');O=Path('C:/mai/wt/foothold-lab/analyst-ame2/inbox/jay/20261028-plan/figs/ame2-analysis')
def counted(rows,fields,n,eps):
    f={k:i for i,k in enumerate(fields)};keep=torch.zeros(len(rows),dtype=torch.bool)
    for e in range(n):
        ix=torch.nonzero((rows[:,f['env']]==e)&(rows[:,f['played']]==1)).flatten()
        assert len(ix)==eps+1
        keep[ix[1:]]=True
    return rows[keep]
# Known answer: first played episode of each env is discarded, unplayed reset ignored.
dummy=torch.tensor([[0,0,1],[0,1,1],[1,0,0],[0,1,0],[1,1,1],[1,1,1]],dtype=torch.float64)
z=counted(dummy,('env','played','success'),2,1)
assert z.tolist()==[[0,1,0],[1,1,1]]
manifest=json.loads((R/'eval_download_manifest.json').read_text());allrows=[];dig=[]
for p in manifest:
    d=torch.load(p['path'],map_location='cpu',weights_only=True);f={k:i for i,k in enumerate(d['fields'])}
    r=counted(d['rows'],d['fields'],d['num_envs'],d['episodes']);e=r[:,f['env']].long();assert len(r)==12000
    dig.append(d['digests']);ty=d['env_type'][e];lv=d['level'][e]
    assert torch.all(r[:,f['level']].long()==lv)
    for k,name in enumerate(d['type_names']):
        m=ty==k;assert int(m.sum())==1000
        allrows.append(dict(checkpoint=d['completed_updates'],seed=d['seed'],terrain=name,episodes=int(m.sum()),success=float(r[m,f['success']].mean()),distance_to_goal=float(r[m,f['dist']].mean()),episode_steps=float(r[m,f['ep_len']].mean()),source=p['path'],sha256=p['sha256']))
    print(d['completed_updates'],d['seed'],'counted12000 SR',float(r[:,f['success']].mean()))
assert dig[0]==dig[1] and dig[2]==dig[3]
with (O/'fixed_eval_comparison.csv').open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(allrows[0]));w.writeheader();w.writerows(allrows)
for t in [r['terrain'] for r in allrows[:12]]:
    v=[np.mean([r['success'] for r in allrows if r['terrain']==t and r['checkpoint']==c]) for c in [9001,20000]]
    print(t,*[round(x,4) for x in v],round(100*(v[1]-v[0]),2))
# Independent cross-check against existing analyzer's row-selection logic, without executing its CLI.
p=R/'raw/ame2/go2/scripts/gap12_eval_tables.py';ss=p.read_text(encoding='utf-8').splitlines()
(O/'eval_method.txt').write_text('Known input PASS. Four datasets, 2400 env x 5 counted episodes each. First played episode per env excluded.\n'+ '\n'.join(f'{i+1}: {ss[i]}' for i in range(66,86)),encoding='utf-8')

meta=json.loads((R/'derived/runs.json').read_text());find={x['run_id']:x for x in meta}
def a(key,t):
    r=find[key];z=np.load(R/'derived'/(key+'.npz'));i=r['tags'].index(t);return z['x'+str(i)],z['y'+str(i)]
for key in ['b03ec9c305f8','865546d51560','edf618d3c0e6']:
    x,k=a(key,'Loss/kl_fp32');_,b=a(key,'Loss/kl_bf16');_,lr=a(key,'Loss/learning_rate')
    print('KL',key,'n',len(x),'bf16>fp32',int((b>k).sum()),'mean',k.mean(),b.mean(),'lr>floor',int((lr>1.00001e-5).sum()))
for key,lo,hi in [('06fb5c1cf3a1',9000,9499),('06fb5c1cf3a1',19500,19999),('865546d51560',19500,19999)]:
    r=find[key];o={}
    for t in r['tags']:
        if t.startswith('Episode_Reward/'):
            x,y=a(key,t);o[t]=float(y[(x>=lo)&(x<=hi)].mean())
    print('REW',key,lo,hi,json.dumps(o))
