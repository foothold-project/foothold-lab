"""Isolated CPU evidence reader. Its imports cannot change the live-plan parser."""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import math
import os
import subprocess
import sys
from zipfile import BadZipFile
from types import SimpleNamespace
import numpy as np
import yaml

ROOT=Path(__file__).resolve().parents[4]
MODES=('eval_gt','eval_pred','probe_prop_only')
CONTINUOUS={'pyramid_stairs','pyramid_stairs_inv','boxes','random_rough',
            'hf_pyramid_slope','hf_pyramid_slope_inv','stage_stairs'}
MAINT=('fwd0.5','fwd1.0','spin+1.2','spin-1.2','back0.5','back1.0',
       'side+0.5','side-0.5','diag-fwd+side+','diag-fwd+side-',
       'diag-back+side+','diag-back+side-','stop')


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):
    obj=json.loads(Path(p).read_text(encoding='utf-8-sig'),parse_constant=lambda x:(_ for _ in ()).throw(ValueError(x)))
    if not isinstance(obj,dict):raise ValueError('object required: '+str(p))
    return obj


def source_module(path,name):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def policy_for(score_path):
    score_path=Path(score_path);s=read(score_path);p=read(score_path.with_name('p1_score.json'))
    n=int(score_path.parent.name[1:]);ref=p['evaluation_plan'];path=Path(ref['path'])
    if (p.get('state')!='complete' or p.get('stage_id')!='E1' or p.get('checkpoint_iteration')!=n
        or p.get('checkpoint_sha256')!=s['checkpoint_sha256']
        or p.get('plan_sha256')!=s['execution_plan_sha256']
        or Path(p['measurement']).resolve()!=score_path.resolve() or p['measurement_sha256']!=sha(score_path)
        or not path.is_absolute() or sha(path)!=ref['sha256']):
        raise ValueError('P1 score/plan/checkpoint pin differs')
    return s,p,yaml.safe_load(path.read_bytes())


def put_gap(out,key,value,low=0,high=math.inf):
    if type(value) not in (int,float) or not math.isfinite(value):raise ValueError('finite metric required: '+key)
    out['gaps'][key]=max(low-value,value-high,0.)


def off_raw(folder,s,output):
    """All expected continuous map-off cases, traced to NPZ, no survivor selection."""
    for sub,expected in [('map64',MAINT),('e1_v2/L0',('fwd0.1','fwd0.2','side+0.2','side-0.2','side+0.4','side-0.4')),
                         ('e1_v2/L5',('fwd0.1','fwd0.2','side+0.2','side-0.2','side+0.4','side-0.4'))]:
        path=folder/sub/'map_modes.json';doc=read(path)
        if (doc.get('checkpoint_sha256')!=s['checkpoint_sha256'] or doc.get('eval_seed')!=42
                or doc.get('envs')!=64 or doc.get('steps')!=300
                or set(doc['modes']['probe_prop_only'])!=set(expected)):
            raise ValueError('off source identity/coverage differs: '+sub)
        for case in expected:
            mode='probe_prop_only';name=doc['env_arrays'][mode+'/'+case]
            if name!=f'env_arrays_{mode}_{case}.npz':raise ValueError('off raw filename differs')
            raw=path.parent/name
            with np.load(raw,allow_pickle=False) as z:
                ident=json.loads(str(z['run_identity'].item()));alive=z['alive'];valid=int((alive.sum(0)>0).sum())
                if (alive.shape!=(300,64) or alive.dtype!=bool or np.any(alive[1:] & ~alive[:-1])
                    or ident['checkpoint_sha256']!=s['checkpoint_sha256'] or ident['eval_seed']!=42
                    or str(z['assignment_sha256'].item())!=doc['fixed_terrain']['assignment_sha256']
                    or not set(z['kind'].tolist())<=CONTINUOUS
                    or not np.array_equal(alive[-1],z['alive_end'])):
                    raise ValueError('off NPZ identity differs: '+sub+'/'+case)
                count=int(alive[-1].sum())
            if count!=doc['modes'][mode][case]['alive_envs_at_end']:raise ValueError('off survival summary differs')
            fp=dict(seed=42,command=doc['commands'][case],steps=300,dt=.02,
                    mesh=doc['ex42_mesh']['mesh_sha256'],assignment=doc['fixed_terrain']['assignment_sha256'])
            judge=(sub!='e1_v2/L5' or case in ('fwd0.1','fwd0.2'))
            target=output['off_cells'] if judge else output['off_record_cells']
            target[sub+'/'+case]=dict(survival=count,valid=valid,fingerprint=fp,
                                                  raw_file=str(raw),raw_sha256=sha(raw))
            if judge:put_gap(output,'off/'+sub+'/'+case,count,60,64)


def wide_worker(score_path,code_root):
    """Use the caller-selected frozen C1 consumer, never synthesize C1 results."""
    sys.path.insert(0,str(code_root))
    from foothold_s2.ex42_e1_wide import read_cells,judge_cells,cap_from_training
    s,p,plan=policy_for(score_path);folder=Path(score_path).parent
    base=read(folder/'map64/map_modes.json');mesh=base['ex42_mesh']['mesh_sha256']
    cells=read_cells(folder,s['checkpoint_sha256'],42,plan,mesh)
    cap=cap_from_training(Path(s['checkpoint']),s['execution_plan_sha256'],mesh)
    judged=judge_cells(cells,plan,cap)
    return dict(cells=cells,judged=judged,code=str(Path(code_root).resolve()),
                code_sha256=sha(Path(code_root)/'foothold_s2/ex42_e1_wide.py'))


def add_wide(out,w,cfg):
    """Interpret verified C1 cells; record-only rows cannot block graduation."""
    raw=w['cells'];j=w['judged']
    expected={f'{case}/{mode}' for mode in MODES[:2]
              for case in ('side+0.8','side-0.8','symmetry/side0.8')}
    expected.update(f'wide_L{level}_fwd1.0/{mode}' for level in (3,6) if j['cap']>=level for mode in MODES[:2])
    if any(j['items'].get(key,{}).get('role')!='judge' for key in expected):
        raise ValueError('C1 required judged cell missing or demoted')
    out['wide']={'reached_level':j['reached_level'],'cap':j['cap'],
                 'L9':{m:raw.get('fixed',{}).get('L9',{}).get(m,{}).get('fwd1.0') for m in MODES},
                 'code_sha256':w['code_sha256'],'code':w['code']}
    for key,row in j['items'].items():
        if row.get('role')!='judge' or key.startswith('wide_L9_') or 'probe_prop_only' in key:continue
        if row.get('valid',64)!=64:raise ValueError('C1 valid count below64: '+key)
        out['cells'][key]=row
        if 'S' in row:put_gap(out,key+'/S',row['S'],cfg['symmetry_min'])
        else:
            for metric,limit in [('success','success_min'),('survival','survival_min')]:
                put_gap(out,key+'/'+metric,row[metric],row[limit],64)
            if key.startswith(('side+0.8/','side-0.8/')):
                case,mode=key.split('/');endpoint=raw['endpoints'][mode][case]
                put_gap(out,key+'/R',endpoint['R'],cfg['R_min'],cfg['R_max'])
                put_gap(out,key+'/mae_mps',endpoint['mae_mps'],0,cfg['mae_fraction']*.8)
    for level in (3,6):
        row=raw.get('fixed',{}).get(f'L{level}',{}).get(MODES[2],{}).get('fwd1.0')
        if j['cap']<level:continue
        if not row:
            out['wide'].setdefault('record_warnings',[]).append(f'L{level} map-off record missing');continue
        out['off_record_cells'][f'wide/L{level}/fwd1.0']=dict(survival=row['survival_count'],valid=row['valid_count'],
            fingerprint={'level':level,'seed':42,'mesh':raw['mesh_sha256'],'steps':475},raw_file=row['raw_file'],raw_sha256=row['raw_sha256'])
    for case in ('side+0.8','side-0.8'):
        row=raw.get('endpoints',{}).get(MODES[2],{}).get(case)
        if not row:
            out['wide'].setdefault('record_warnings',[]).append(case+' map-off record missing');continue
        out['off_record_cells']['endpoints/'+case]=dict(survival=row['survival'],valid=row['envs'],
            fingerprint={'case':case,'seed':42,'mesh':raw['mesh_sha256'],'steps':300},raw_file=row['raw_file'],raw_sha256=row['raw_sha256'])
    # Missing record-only rows never become a new graduation veto.
    if any(out['wide']['L9'][m] is None for m in MODES):out['wide']['record_warning']='L9 record missing'


def read_audit(score_path,c1_code_root=None,extension_code_root=None):
    sys.path.insert(0,str(ROOT))
    from foothold_s2.ex42_e1_v2 import _verified_cells,measure_cells,judge_cells,treatment
    from foothold_s2.eval.ex42_d44_cells import read_evidence
    from foothold_s2.ex42_e1_judge import _landing_window
    out=dict(iteration=int(Path(score_path).parent.name[1:]),errors=[],wide_errors=[],cells={},gaps={},off_cells={},off_record_cells={},
             required_complete=False,all_judge_pass=False,wide={},sources={})
    try:
        s,p,plan=policy_for(score_path);folder=Path(score_path).parent;cp=s['checkpoint_sha256']
        out.update(checkpoint_sha256=cp,evaluation_sha256=p['evaluation_plan']['sha256'],
                   execution_sha256=s['execution_plan_sha256'])
        out['sources'].update({str(score_path):sha(score_path),str(folder/'p1_score.json'):sha(folder/'p1_score.json'),
                               p['evaluation_plan']['path']:p['evaluation_plan']['sha256']})
        cells=_verified_cells(s,folder,42)
        repeats={seed:measure_cells(folder/f'e1_v2_repeat_seed{seed}',cp,seed)
                 for seed in (7,13) if (folder/f'e1_v2_repeat_seed{seed}').exists()}
        judged=judge_cells(cells,plan,repeats=repeats)
        cfg=plan['evaluation']['e1_exit_v2']
        for key,row in judged['items'].items():
            if row.get('role')=='record':continue
            out['cells'][key]={k:v for k,v in row.items() if not k.startswith('per_env_')}
            out['cells'][key]['valid']=row.get('envs',64)
            if key.startswith(('low/','side05/')):
                bounds={'R':(cfg['R_min'],cfg['R_max']),'mae_mps':(0,cfg['mae_fraction']*row['command_mps']),
                        'success':(cfg['success_min'],64),'survival':(cfg['survival_min'],64)}
            elif key.startswith('yaw/'):
                bounds={'median_abs_rad':(0,cfg['yaw_median_max_rad']),'p90_abs_rad':(0,cfg['yaw_p90_max_rad']),
                        'survival':(cfg['survival_min'],64)}
            else:bounds={'S':(cfg['symmetry_min'],math.inf)}
            for metric,(lo,hi) in bounds.items():put_gap(out,key+'/'+metric,row[metric],lo,hi)
        # P1's maintenance floor is already measured against the pinned parent.
        # Keep each scalar and verify raw values via boundary_read independently.
        if set(s['cell_judgments'])!=set(MODES):raise ValueError('maintenance modes missing')
        for mode in MODES[:2]:
            rows=s['cell_judgments'][mode]
            if set(rows)!=set(MAINT):raise ValueError('maintenance 13 names differ')
            for case,row in rows.items():
                if row.get('role')!='judge':raise ValueError('maintenance role differs')
                key=f'maintenance/{mode}/{case}'
                out['cells'][key]=dict(judgement=row['judgment'],valid=64)
                for metric,data in row['metrics'].items():
                    if isinstance(data,dict) and 'adverse_delta' in data:
                        put_gap(out,key+'/'+metric,data['adverse_delta'], -math.inf,data['limit'])
        off_raw(folder,s,out)
        for case,row in cells['yaw']['probe_prop_only'].items():
            out['off_record_cells']['axis/L2/'+case]=dict(survival=row['survival'],valid=row['envs'],
                fingerprint=dict(seed=42,level=2,case=case,steps=300,
                                 mesh=read(folder/'map64/map_modes.json')['ex42_mesh']['mesh_sha256']),
                raw_file=row['raw_file'],raw_sha256=row['raw_sha256'])
        # D44 receipt retains its original absolute path spelling; resolve only
        # to check that it is the same folder, not to rewrite immutable receipts.
        idx=read(folder/'d44/d44_cells.json')
        original=Path(next(iter(idx['cases'].values()))['raw_file']).parent
        if original.resolve()!=(folder/'d44').resolve():raise ValueError('D44 source folder differs')
        # Historical /2 and current /3 traces must use their producing reader.
        policy_root=Path(p['evaluation_plan']['path']).parents[2]
        d44_reader=policy_root/'foothold_s2/eval/ex42_d44_cells.py'
        if not d44_reader.is_file() and c1_code_root is not None:
            d44_reader=Path(c1_code_root)/'foothold_s2/eval/ex42_d44_cells.py'
        read_evidence=source_module(d44_reader,'pinned_d44_reader').read_evidence
        out['sources'][str(d44_reader)]=sha(d44_reader)
        d44=read_evidence(original,plan=plan,plan_sha256=p['evaluation_plan']['sha256'],checkpoint_sha256=cp,seed=42)
        for case,value in d44.items():
            if case.startswith('stop_restart_'):continue
            row=_landing_window(value,plan,case);key='d44/'+case
            out['cells'][key]={**row,'valid':row['valid_count']}
            for metric,limit in [('success_count','success_min'),('survival_count','survival_min')]:
                put_gap(out,key+'/'+metric,row[metric],row[limit],64)
        tr=treatment(Path(s['checkpoint']),out['iteration'],plan,expected_plan_sha256=s['execution_plan_sha256'])
        if tr.get('state')!='complete':raise ValueError('completed-window treatment receipt unavailable: '+str(tr.get('reason')))
        out['treatment_sha256']=tr['sha256']
    except (OSError,ValueError,KeyError,TypeError,IndexError,AttributeError,BadZipFile,EOFError) as exc:
        out['errors'].append(str(exc));return out
    try:
        if c1_code_root is None:c1_code_root=policy_root
        if not (Path(c1_code_root)/'foothold_s2/ex42_e1_wide.py').is_file():
            raise ValueError('C1 consumer code unavailable; use --c1-code-root with a fixed reviewed copy')
        proc=subprocess.run([sys.executable,'-B',str(Path(__file__)), '--score',str(score_path),
                             '--wide-worker',str(c1_code_root)],capture_output=True,text=True,
                            env={**os.environ,'CUDA_VISIBLE_DEVICES':'','PYTHONDONTWRITEBYTECODE':'1'},timeout=60)
        if proc.returncode:raise ValueError('C1 reader: '+proc.stderr[-1000:])
        add_wide(out,json.loads(proc.stdout),cfg)
    except (OSError,ValueError,KeyError,TypeError,AttributeError,BadZipFile,EOFError,subprocess.TimeoutExpired) as exc:
        out['wide_errors'].append(str(exc))
    out['required_complete']=not out['errors'] and not out['wide_errors']
    out['all_judge_pass']=(out['required_complete'] and all(x.get('judgement')=='PASS' for x in out['cells'].values())
                          and all(x['valid']==64 and x['survival']>=60 for x in out['off_cells'].values()))
    if extension_code_root and out['iteration']==1750:
        try:
            path=Path(extension_code_root)/'foothold_s2/ex42_extension_evidence.py'
            module=source_module(path,'approved_extension')
            # The extension module re-opens all three pinned P1 receipts.
            out['extension']=module.improvement_evidence(SimpleNamespace(sha256=s['execution_plan_sha256'],document=plan),
                              'E1',1750,250,Path(score_path).with_name('p1_score.json'))
            out['extension']['code_sha256']=sha(path)
        except (OSError,ValueError,KeyError,TypeError,AttributeError) as exc:out['extension']={'state':'HOLD','reason':str(exc)}
    return out


def main():
    p=argparse.ArgumentParser();p.add_argument('--score',type=Path,required=True)
    p.add_argument('--wide-worker',type=Path);p.add_argument('--c1-code-root',type=Path)
    p.add_argument('--extension-code-root',type=Path);a=p.parse_args()
    obj=wide_worker(a.score,a.wide_worker) if a.wide_worker else read_audit(a.score,a.c1_code_root,a.extension_code_root)
    print(json.dumps(obj,ensure_ascii=False,allow_nan=False))

if __name__=='__main__':main()
