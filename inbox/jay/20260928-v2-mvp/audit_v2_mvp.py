"""Read-only independent recount. Run with IsaacLab's Python; no simulation."""
from pathlib import Path
import csv, json, hashlib, statistics, math, sys, re, difflib
from collections import defaultdict, Counter

ROOT = Path(__file__).resolve().parents[3]
RES = ROOT / 'sim/eval/results'
OUT = Path(__file__).parent
LOG = Path('C:/isaac/IsaacLab/logs/rsl_rl/unitree_go2_gap_nvidia')
ROUGH = Path('C:/isaac/IsaacLab/logs/rsl_rl/unitree_go2_rough/2026-08-11_20-32-58')
def js(p): return json.loads(p.read_text(encoding='utf-8'))
def rows(p):
    with p.open(encoding='utf-8-sig',newline='') as f: return list(csv.DictReader(f))
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def avg(xs): return statistics.mean(xs) if xs else None
def truth(x): return str(x).lower() in ('true','1','1.0')
def wilson(k,n):
    p=k/n; z=1.959963984540054; a=1+z*z/n
    b=(p+z*z/(2*n))/a; c=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/a
    return [b-c,b+c]

def eval_cells(base, allowed_difficulties=None):
    out={}; errors=[]; manifests=[]
    for p in sorted(base.rglob('generalization_raw.csv')):
        if not p.with_name('run_manifest.json').exists() or not p.with_name('generalization_summary.csv').exists():
            continue
        m=js(p.with_name('run_manifest.json'))
        if allowed_difficulties is not None and float(m['terrain_difficulty_range'][0]) not in allowed_difficulties:
            continue
        manifests.append(m)
        by=defaultdict(list)
        for r in rows(p): by[r['terrain']].append(r)
        sm={r['terrain']:r for r in rows(p.with_name('generalization_summary.csv'))}
        for t, rr in by.items():
            key=(m['terrain_set'],float(m['terrain_difficulty_range'][0]),float(m['command_vx_mps']),t)
            counts={a:sum(truth(r[a]) for r in rr) for a in ['overall_success','survival_success','progress_success','tracking_success','direction_success']}
            for a,k in counts.items():
                col='overall_success_rate' if a=='overall_success' else a.replace('_success','_success_rate')
                if a=='survival_success': col='survival_rate'
                if abs(k/len(rr)-float(sm[t][col]))>1e-10: errors.append([str(p),t,col])
            if any(truth(r['overall_success']) != all(truth(r[a]) for a in ['survival_success','progress_success','tracking_success','direction_success']) for r in rr): errors.append([str(p),t,'AND'])
            if any(r.get('policy_sha256',m['policy_sha256'])!=m['policy_sha256'] for r in rr): errors.append([str(p),t,'sha'])
            if key in out: errors.append([str(p),t,'duplicate cell'])
            out[key]={'n':len(rr),'k':counts['overall_success'],'counts':counts,'raw':str(p.relative_to(ROOT)),
                      'unique_env_episode':len({(r['env_id'],r['episode']) for r in rr}),
                      'unique_episode_id':len({r.get('episode_id') for r in rr})}
    return out,errors,manifests

def main():
    result={}
    bases={'v2d05':RES/'20260923-v2rs/v2g2-feetair01-iter3000',
           'v2sweep':RES/'20260924-observe/sweep/v2g2-feetair01-iter3000',
           'v1':RES/'maindata-v1/foothold-v1','nv':RES/'20260921-nvidia-axis1',
           'ctrl':RES/'20260928-ctrl-scratch/nvcfg-scratch-iter1500'}
    for model in ['v2g2-feetair01','fs1-scratch-f001','fs2-scratch-f01']:
        for it in [1500,2000,2500,3000,4500]:
            p=RES/f'20260923-v2rs/{model}-iter{it}'
            if p.exists(): bases[f'{model}@{it}']=p
    data={}; result['axis1']={}
    for name,base in bases.items():
        allowed={.1,.3,.7,.9} if name=='v2sweep' else None
        cells,errors,manifests=eval_cells(base,allowed); data[name]=cells
        result['axis1'][name]={'cells':len(cells),'episodes':sum(x['n'] for x in cells.values()),'errors':errors,
            'n_values':sorted({x['n'] for x in cells.values()}),
            'overall_pct':avg([100*x['k']/x['n'] for x in cells.values()]),
            'by_set':{s:avg([100*x['k']/x['n'] for k,x in cells.items() if k[0]==s]) for s in ['rough6','unseen10']},
            'manifest_sets':{k:sorted({str(m.get(k)) for m in manifests}) for k in ['observation_dim','eval_spec_version','policy_sha256','seed','envs_per_terrain','gap_aware_scan','joint_pos_scale','max_velocity_mae_mps']},
            'episode_id_collisions':sum(x['n']-x['unique_episode_id'] for x in cells.values()),
            'env_episode_collisions':sum(x['n']-x['unique_env_episode'] for x in cells.values())}
    data['v2']={**data['v2d05'],**data['v2sweep']}
    long=rows(RES/'20260928-v2-sweep/sweep_long.csv'); errs=[]
    for r in long:
        key=(r['set'],float(r['difficulty']),float(r['speed']),r['terrain'])
        v=data[r['model']].get(key)
        if v is None or v['n']!=int(r['episodes']) or abs(v['k']/v['n']-float(r['overall_success_rate']))>1e-10: errs.append(r)
    result['long']={'rows':len(long),'models':dict(Counter(r['model'] for r in long)),'errors':errs,
        'unique_keys':len({(r['model'],r['set'],r['difficulty'],r['speed'],r['terrain']) for r in long})}
    result['sweep']={}
    for model in ['v2','v1','nv']:
        c=data[model]; agg={}
        for s,d,v,t in c:
            for speed in [v,'all']:
                key=f'{s}/d{d}/v{speed}'
                if key not in agg: agg[key]=avg([100*x['k']/x['n'] for k,x in c.items() if k[0]==s and k[1]==d and (speed=='all' or k[2]==v)])
        result['sweep'][model]=agg
    result['axis1_gates']={}
    for it in [1500,2000,2500,3000]:
        c=data[f'v2g2-feetair01@{it}']; g={}
        for baseline in ['v1','nv']:
            down=[]; up=[]; overlap=0
            for k,x in c.items():
                b=data[baseline][k]; w=wilson(x['k'],x['n']); wb=wilson(b['k'],b['n'])
                if w[1]<wb[0]: down.append([list(k),x['k'],b['k']])
                elif w[0]>wb[1]: up.append([list(k),x['k'],b['k']])
                else: overlap+=1
            g[baseline]={'down':down,'up':up,'overlap':overlap}
        g['zero']=[list(k) for k,x in c.items() if x['k']==0]; g['min_pct']=min(100*x['k']/x['n'] for x in c.values()); result['axis1_gates'][str(it)]=g
    result['axis2']={}
    for model in ['v2g2-feetair01','fs1-scratch-f001','fs2-scratch-f01']:
        for it in [1500,2000,2500,3000]:
            base=RES/f'20260923-v2rs-axis2/{model}-iter{it}'; m=js(base/'probe_manifest.json'); a={}; errors=[]
            for s in ['stop','hold','turn']:
                rr=js(base/s/'per_env.json'); sm=m['summary'][s]
                a[s]={'n':len(rr),'fell':sum(r['fell'] for r in rr),
                      'residual':avg([r['residual_speed_mps'] for r in rr if r.get('residual_speed_mps') is not None]),
                      'target_delta':avg([r['joint_target_delta_tail'] for r in rr if r.get('joint_target_delta_tail') is not None]),
                      'stop_reached':sum(r.get('stop_time_s') is not None for r in rr)}
                if a[s]['fell']/len(rr)!=sm['fell_ratio']: errors.append(s+' fell')
                if s=='turn':
                    a[s]['yaw']={key:{'n':sum(key in r.get('yaw_follow',{}) for r in rr),'ratio':avg([r['yaw_follow'][key]['ratio'] for r in rr if key in r.get('yaw_follow',{})])} for key in ['-1.00','-0.50','+0.50','+1.00']}
                    for key,v in a[s]['yaw'].items():
                        if abs(v['ratio']-sm['yaw_follow_ratio'][key])>1e-12: errors.append('yaw '+key)
            vals=[a['stop']['fell']/64,a['hold']['fell']/64,a['hold']['residual'],a['hold']['target_delta'],a['turn']['fell']/64]+[v['ratio'] for v in a['turn']['yaw'].values()]
            a['values']=vals; a['passes']=[v<=limit for v,limit in zip(vals[:5],[.03,.03,.005,.01,.1])]+[v>=.4 for v in vals[5:]]
            a['pass_count']=sum(a['passes']); a['errors']=errors
            a['parquets']=len(list(base.rglob('*.parquet'))); result['axis2'][f'{model}@{it}']=a
    result['wilson_turn']=wilson(7,64)
    html=RES/'report-v1/report-v1.html'; s=html.read_text(encoding='utf-8')
    result['report_v1']={'bytes':html.stat().st_size,'sha256':sha(html),'counts':{t:len(re.findall('<'+t+r'\b',s)) for t in ['section','h2','table','video']},'headings':re.findall(r'<h2[^>]*>(.*?)</h2>',s,re.S)}
    result['v2_cells']=[dict(key=list(k),**v) for k,v in data['v2'].items()]
    (OUT/'audit_v2_mvp_results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print('raw recount saved',len(data['v2']),result['long'])
    print('axis2', {k:v['pass_count'] for k,v in result['axis2'].items()})

if __name__=='__main__': main()
