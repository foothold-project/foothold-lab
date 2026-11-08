"""CPU-only, immutable-source N21 parent -> EX42 stage-zero comparison.

Reuses the morning definitions and reopens every parent and endpoint NPZ.
Seed ranges are descriptive references, not confidence intervals or gates.
"""
from pathlib import Path
from collections import Counter
from datetime import datetime
import contextlib
import importlib.util
import io
import json
import argparse
import numpy as np

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('seedwidth', HERE.parent / 'N21-seedwidth-1108/n21_seedwidth_1108.py')
old = importlib.util.module_from_spec(spec)
spec.loader.exec_module(old)
END = Path('D:/mai-tmp/lead/ex42_s0_end')
CHILD = '20365a2c6d70f94f65f1114471f7df198e56d86db6d02d89cea43c666b95e768'
EPS = 1e-12


def change(parent, child):
    a = np.asarray(parent, float)
    assert a.shape == (3,) and np.isfinite(a).all() and np.isfinite(child)
    lo, hi = float(a.min()), float(a.max())
    delta, width = float(child-a[0]), hi-lo
    return {'parent42': float(a[0]), 'endpoint42': float(child), 'delta': delta,
            'parent_min': lo, 'parent_max': hi, 'parent_width': width,
            'delta_exceeds_width': bool(abs(delta) > width+EPS),
            'outside_parent_range': bool(child < lo-EPS or child > hi+EPS)}


def components(per, command, thresholds):
    errors = np.asarray([[e[old.FIELDS[k][0]] for k in old.metrics(command)] for e in per], float)
    assert np.isfinite(errors).all()
    reached = (errors <= np.asarray(thresholds)).all(1)
    alive = np.asarray([e['alive_at_end'] for e in per], bool)
    return {'reached': int(reached.sum()), 'alive': int(alive.sum()), 'both': int((reached & alive).sum())}


def known_answers():
    n = old.known_answers()
    a = change([1, 2, 3], 3)
    assert not a['delta_exceeds_width'] and not a['outside_parent_range']
    a = change([2, 1, 3], 3.5)
    assert not a['delta_exceeds_width'] and a['outside_parent_range']
    a = change([64, 64, 64], 63)
    assert a['delta'] == -1 and a['delta_exceeds_width']
    # A smaller on-minus-off gap alone does NOT mean DR-on got better.
    assert (.4-.3) < (.4-.1) and .4 == .4
    try:
        change([1, 2, 3], float('nan'))
    except AssertionError:
        pass
    else:
        raise AssertionError('NaN accepted')
    fake = [{'vx_abs_error_mean_alive_mps': .1, 'alive_at_end': False},
            {'vx_abs_error_mean_alive_mps': .3, 'alive_at_end': True}]
    assert components(fake, 'fwd1.0', [.2]) == {'reached': 1, 'alive': 1, 'both': 0}
    return n + 6


def run(out, scratch):
    tests = known_answers()
    with contextlib.redirect_stdout(io.StringIO()):
        parent = old.inspect(scratch / 'parent_recheck')
    assert parent['complete'] and parent['npz_count'] == 288
    docs = {(t,c,s): json.loads(old.path_for(t,c,s).read_text(encoding='utf-8-sig'))
            for t in old.TERRAINS for c in old.CONDS for s in old.SEEDS}
    morning = json.loads((HERE.parent/'N21-1108/audit.json').read_text(encoding='utf-8'))
    baseline = {(r['terrain'],r['mode'],r['command']): r for r in morning['cells']}
    inputs = list(parent['inputs'])
    protocol, cells, physical, source_changes, all_components, reaches = [], [], [], [], [], []
    for t in old.TERRAINS:
      for c in old.CONDS:
        p = END / f'n21_{t}_{c}' / 'n21_record_only.json'
        before = (p.stat().st_size, p.stat().st_mtime_ns)
        d = json.loads(p.read_text(encoding='utf-8-sig'))
        assert d['record_only'] and d['checkpoint_sha256'] == CHILD
        assert d['eval_seed'] == d['run_identity']['eval_seed'] == 42
        assert d['envs'] == 64 and d['steps'] == 300 and d['policy_dt_s'] == .02
        assert d['n21_point'] == 'parent_e0' and d['dr_mode']['mode'] == c
        assert d['dr_mode']['scale'] == (1. if c == 'on' else 0.)
        assert len(d['env_arrays']) == 24
        b = docs[t,c,42]
        for k in ['commands','terrain_set','terrain_tiles','terrain_columns','fixed_terrain','restored_modes']:
            assert d[k] == b[k], (t,c,k)
        identity = d['run_identity']
        assert identity['code_head'] == '7916a52fa07c6774eb59db2b69f4b7a5068cea63' and identity['code_dirty_files'] == 0
        protocol.append({'terrain':t,'dr':c,'parent_gpu':b['run_identity']['device'],
                         'child_gpu':identity['device'],'parent_gpu_uuid':b['run_identity']['gpu_uuid'],
                         'child_gpu_uuid':identity['gpu_uuid'],'child_code_head':identity['code_head'],
                         'parent_code_head':b['run_identity']['code_head'],
                         'assignment_sha256':d['fixed_terrain']['assignment_sha256'],
                         'terrain_counts':dict(Counter(x['kind'] for x in d['terrain_tiles'])),
                         'child_path':str(p)})
        for s in old.SEEDS:
            a = docs[t,c,s]['source_sha256']
            changes = {k:[a.get(k),d['source_sha256'].get(k)] for k in sorted(set(a)|set(d['source_sha256'])) if a.get(k)!=d['source_sha256'].get(k)}
            source_changes.append({'terrain':t,'dr':c,'parent_seed':s,'changes':changes})
            if s in [43,44]: assert not changes
        for mode in old.MODES:
          for cmd in old.CMDS:
            row = d['modes'][mode][cmd]
            per = sorted(row['per_env'], key=lambda e:e['env'])
            assert [e['env'] for e in per] == list(range(64))
            npath = p.parent/d['env_arrays'][f'{mode}/{cmd}']
            nbefore = (npath.stat().st_size,npath.stat().st_mtime_ns)
            with np.load(npath,allow_pickle=False) as q:
                assert q['vx'].shape == q['alive'].shape == (300,64)
                assert row['alive_envs_at_end'] == int(q['alive_end'].sum()) == sum(x['alive_at_end'] for x in per)
                assert np.array_equal(q['alive'].sum(0),[e['samples_alive'] for e in per])
                assert np.array_equal(q['alive'][-1],q['alive_end'])
                assert np.all(np.diff(q['alive'].astype(int),axis=0)<=0)
                qid = json.loads(str(q['run_identity']))
                for k in ['device','gpu_uuid','code_head','checkpoint_sha256','eval_seed']: assert qid[k] == identity[k]
                calc = (np.abs(q['vx']-d['commands'][cmd][0])*q['alive']).sum(0)/np.maximum(q['alive'].sum(0),1)
                np.testing.assert_allclose(calc,[e[old.FIELDS['vx'][0]] for e in per],atol=2e-6)
                assert str(q['assignment_sha256']) == d['fixed_terrain']['assignment_sha256']
            assert nbefore == (npath.stat().st_size,npath.stat().st_mtime_ns)
            inputs.append({'path':str(npath),'sha256':old.sha(npath),'kind':'npz'})
            cell = {'terrain':t,'dr':c,'mode':mode,'command':cmd,'alive':row['alive_envs_at_end']}
            for k,(key,unit) in old.FIELDS.items():
                a = np.asarray([e[key] for e in per],float)
                assert np.isfinite(a).all()
                cell[k] = float(np.median(a))
            cells.append(cell)
            for k in ['vx','vy','wz']:
                pa = [float(np.median([e[old.FIELDS[k][0]] for e in docs[t,c,s]['modes'][mode][cmd]['per_env']])) for s in old.SEEDS]
                all_components.append({'terrain':t,'dr':c,'mode':mode,'command':cmd,'metric':k,'unit':old.FIELDS[k][1],**change(pa,cell[k])})
            ref = baseline[t,mode,cmd]
            oldcomp = components(b['modes'][mode][cmd]['per_env'],cmd,ref['baseline'])
            assert all(oldcomp[k] == ref[c][k] for k in oldcomp)
            newcomp = components(per,cmd,ref['baseline'])
            reaches.append({'terrain':t,'dr':c,'mode':mode,'command':cmd,'thresholds_parent_off':ref['baseline'],
                            **{f'parent_{k}':v for k,v in oldcomp.items()}, **{f'endpoint_{k}':v for k,v in newcomp.items()}})
        if c == 'on':
            br=b['dr']['readback']; cr=d['dr']['readback']
            assert len(cr)==24
            mass_equal=material_equal=push_equal=0
            push_max_delta=0.0
            for key,r in cr.items():
                a=r['actual_values_by_env']; ba=br[key]['actual_values_by_env']
                mass=np.asarray(a['mass_kg_by_env_body']); mat=np.asarray(a['material_coefficients_by_env_shape'])
                assert mass.shape==(64,19) and mat.shape==(64,27,3)
                base=mass[:,a['body_names'].index('base')]
                assert np.all(base-6.921000003814697>=-1-1e-6) and np.all(base-6.921000003814697<=3+1e-6)
                assert np.all(mat[:,:,:2]>=.2-1e-6) and np.all(mat[:,:,:2]<=1.2+1e-6)
                assert np.all(mat[:,:,1]<=mat[:,:,0]+1e-6)
                mass_equal+=int(np.array_equal(mass,ba['mass_kg_by_env_body']))
                material_equal+=int(np.array_equal(mat,ba['material_coefficients_by_env_shape']))
                push_equal+=int(np.array_equal(r['push_events'][0]['dv_xyz_w_mps'],br[key]['push_events'][0]['dv_xyz_w_mps']))
                push_max_delta=max(push_max_delta,float(np.max(np.abs(np.asarray(r['push_events'][0]['dv_xyz_w_mps'])-np.asarray(br[key]['push_events'][0]['dv_xyz_w_mps'])))))
                assert r['push_events'][0]['seed']==br[key]['push_events'][0]['seed']
                assert r['push_events'][0]['step']==100 and r['push_events'][0]['t_s']==2.0
            physical.append({'terrain':t,'cells':len(cr),'mass_equal_parent_cells':mass_equal,
                             'material_equal_parent_cells':material_equal,'push_equal_parent_cells':push_equal,
                             'push_max_delta_parent_mps':push_max_delta,
                             'base_mass_range': [float(base.min()),float(base.max())],
                             'static_range':[float(mat[:,:,0].min()),float(mat[:,:,0].max())],
                             'dynamic_range':[float(mat[:,:,1].min()),float(mat[:,:,1].max())]})
        assert before == (p.stat().st_size,p.stat().st_mtime_ns)
        inputs.append({'path':str(p),'sha256':old.sha(p),'kind':'receipt'})

    pl={(r['terrain'],r['dr'],r['seed'],r['mode'],r['command']):r for r in parent['cells']}
    cl={(r['terrain'],r['dr'],r['mode'],r['command']):r for r in cells}
    comparisons=[]
    for r in cells:
        t,c,m,cmd=[r[k] for k in ['terrain','dr','mode','command']]
        for metric in ['alive']+old.metrics(cmd):
            pvals=[pl[t,c,s,m,cmd][metric] for s in old.SEEDS]
            comparisons.append({'terrain':t,'dr':c,'mode':m,'command':cmd,'metric':metric,
                                'unit':'env/64' if metric=='alive' else old.FIELDS[metric][1],**change(pvals,r[metric])})
    gaps=[]
    for r in parent['comparison']:
        if r['metric']=='alive': continue
        t,m,cmd,k=[r[x] for x in ['terrain','mode','command','metric']]
        off=cl[t,'off',m,cmd][k]; on=cl[t,'on',m,cmd][k]; gap=on-off
        gaps.append({'terrain':t,'mode':m,'command':cmd,'metric':k,'unit':r['unit'],
                     'parent_off42':r['off'][0],'parent_on42':r['on'][0],
                     'endpoint_off42':off,'endpoint_on42':on,
                     'parent_gap42':r['delta42'],'endpoint_gap42':gap,'gap_change':gap-r['delta42'],
                     'parent_width_max':r['width_max'],'parent_gap_min':r['delta_min'],'parent_gap_max':r['delta_max'],
                     'endpoint_gap_exceeds_width':bool(abs(gap)>r['width_max']+EPS),
                     'endpoint_gap_outside_parent_gap_range':bool(gap<r['delta_min']-EPS or gap>r['delta_max']+EPS),
                     'gap_smaller':bool(gap<r['delta42']-EPS),
                     'on_error_smaller':bool(on<r['on'][0]-EPS),'off_error_smaller':bool(off<r['off'][0]-EPS),
                     'target18':cmd in ['fwd1.0','side+0.5','side-0.5']})
    targets=[r for r in gaps if r['target18']]
    assert len(targets)==18
    assert all(r['parent_gap42']>r['parent_width_max']+EPS for r in targets)
    sums=[]
    for t in old.TERRAINS:
      for c in old.CONDS:
        subset=[r for r in comparisons if r['terrain']==t and r['dr']==c]
        er=[r for r in subset if r['metric']!='alive']; al=[r for r in subset if r['metric']=='alive']
        sums.append({'terrain':t,'dr':c,'cells':len(al),'error_components':len(er),
                     'parent_alive_sum':sum(int(r['parent42']) for r in al),
                     'endpoint_alive_sum':sum(int(r['endpoint42']) for r in al),'exposures':len(al)*64,
                     'error_lower':sum(r['delta'] < -EPS for r in er),'error_higher':sum(r['delta'] > EPS for r in er),
                     'error_delta_over_width':sum(r['delta_exceeds_width'] for r in er),
                     'error_lower_over_width':sum(r['delta_exceeds_width'] and r['delta']<0 for r in er),
                     'error_higher_over_width':sum(r['delta_exceeds_width'] and r['delta']>0 for r in er),
                     'survival_delta_over_width':sum(r['delta_exceeds_width'] for r in al)})
    summary={'parent_checkpoint':old.PARENT,'endpoint_checkpoint':CHILD,'known_answer_tests':tests,
             'npz_checked':sum(x['kind']=='npz' for x in inputs),'raw_json_runs':16,
             'summary':sums,'target18':{'count':len(targets),'gap_smaller':sum(r['gap_smaller'] for r in targets),
               'gap_larger':sum(not r['gap_smaller'] for r in targets),'on_error_smaller':sum(r['on_error_smaller'] for r in targets),
               'gap_positive':sum(r['endpoint_gap42']>EPS for r in targets),
               'gap_above_old_width':sum(r['endpoint_gap42']>r['parent_width_max']+EPS for r in targets),
               'gap_smaller_but_on_not_smaller':sum(r['gap_smaller'] and not r['on_error_smaller'] for r in targets)}}
    audit={'generated_at':datetime.now().isoformat(timespec='seconds'),**summary,'protocol':protocol,
           'physical_checks':physical,'source_changes':source_changes,'inputs':inputs,
           'parent_recheck':{'known_answers':parent['known_answer_tests'],'npz_count':parent['npz_count'],
                            'all_seed_trajectory_pairs_different':all(not x['vx_equal'] for x in parent['array_seed_checks'])}}
    out.mkdir(parents=True,exist_ok=True)
    (out/'audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8',newline='\n')
    for name,rows in [('cells',cells),('comparison',comparisons),('all_axis_components',all_components),
                      ('reach_survival',reaches),('dr_gaps',gaps),('target18',targets),('protocol',protocol)]:
        old.csvout(out/(name+'.csv'),rows)
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    return audit,comparisons,reaches,gaps


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--out',type=Path,default=HERE)
    parser.add_argument('--scratch',type=Path,default=Path('D:/mai-tmp/analyst/n21-s0end-1108'))
    args=parser.parse_args()
    run(args.out,args.scratch)
