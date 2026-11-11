"""CPU request builder for paper, named-kind, cross-direction and G18 cells.

No implicit GPU launch. --execute is an explicit operator action. Each child
uses 64 isolated copies and all three map modes. A record-only failure never
becomes a terrain promotion failure. Exact case IDs are derived from the plan.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import subprocess
import sys

import yaml
from foothold_s2.eval.ex42_task_cells import MODES,sha256

STAGES=('E0','E1','E1F','E2','E3','E4','E5','M','E6a','E6b')
FORMAT='foothold-ex42-task-request/1'


def cross_settings(plan):
    cfg=plan['evaluation'].get('cross_dir_half_flat',{})
    expected={'statistic':'median_signed_projection_all_initial_64','ratio_min':.5,
        'survival_min':60,'valid_min':48,'threshold_scaling':'ceil_threshold_times_valid_over_64',
        'flat_nonpositive':'HOLD','judge_from_window':2,'steps':300,
        'commands':{'forward':[1.,0.,0.],'reverse':[-.5,0.,0.],'side_left':[0.,.5,0.],'side_right':[0.,-.5,0.]},
        'match':['checkpoint_sha256','seed','map_mode','command_b','steps','dt']}
    if any(cfg.get(k)!=v for k,v in expected.items()):
        raise ValueError('cross-direction plan differs from lead 11/11 15:05 contract')
    return cfg


def push_applicability(plan,family,kind):
    # Existing training entry reads the first stage kind_task; preserve that same source.
    stages=plan['stages'];initial=next(s for s in stages if s['id']=='E0')
    declaration=initial['terrain']['kind_task']
    value=declaration.get(family,{}).get(kind,{}).get('push')
    if value is None: raise ValueError('missing training push mask for named kind')
    # YAML 1.1 can decode unquoted on/off as booleans.
    if value not in ('on','off',True,False):raise ValueError('invalid training push mask')
    return {'status':'enabled' if value in ('on',True) else 'n/a',
            'role':'record_only','mask_source':'stages[E0].terrain.kind_task','family':family,'kind':kind}


def _forward_task(family,kind):
    if (family,kind)==('C','box'):return 'box_center_pass'
    if kind.startswith(('eval_stairs_','eval_slope_')) or kind=='high_ledge_075':return 'surface_hold'
    if kind in ('crawl','crawl_020'):return 'tunnel_exit_no_contact'
    return 'tile_end_reach'


def case_specs(plan,*,stage,group,family,kind,window_index,steps):
    if stage not in STAGES or type(steps) is not int or steps<2 or window_index<1:
        raise ValueError('stage, window or steps invalid')
    cfg=cross_settings(plan)
    if group=='directions' and steps!=cfg['steps']:raise ValueError('direction test must use 300 steps')
    if group=='push' and push_applicability(plan,family,kind)['status']=='n/a':return {}
    if group not in ('paper','kind','directions','push'):raise ValueError('unknown task group')
    if group=='kind' and not ((family,kind)==('C','box') or
            (family=='E' and kind in ('slope_steep','slope_steep_inv','stairs_high','stairs_high_inv'))):
        raise ValueError('this completion evaluator handles C box and expanded E; use the kind-specific completion evaluator')
    if kind in ('eval_stairs_landing_016','eval_stair_surface_spin'):
        raise ValueError('landing/spin needs its maneuver evaluator, not a forward completion cell')
    commands=cfg['commands'] if group=='directions' else {'reverse' if kind in ('eval_stairs_010','eval_stairs_015_reverse','eval_stairs_020_reverse') else 'forward':
        cfg['commands']['reverse' if kind in ('eval_stairs_010','eval_stairs_015_reverse','eval_stairs_020_reverse') else 'forward']}
    paper=plan['evaluation']['paper_cells']
    paper_judges=set().union(*(set(paper[k]['judge']) for k in ('slope','stairs_forward','stairs_reverse')))
    rows={}
    for direction,command in commands.items():
        task='push_record' if group=='push' else ('cross_dir_half_flat' if group=='directions' and direction!='forward' else _forward_task(family,kind))
        eligible=(group in ('kind','directions') or (kind in paper_judges and STAGES.index(stage)>=STAGES.index('E4')))
        if group=='directions' and STAGES.index(stage)<STAGES.index('E5'):eligible=False
        if group=='directions' and direction=='forward':eligible=False  # 300-step forward is record only; separate geometry-timed completion cell.
        if task=='cross_dir_half_flat' and window_index<cfg['judge_from_window']:eligible=False
        for mode in MODES:
            case=f'{kind if family=="V" else family+"_"+kind}_{direction}_{mode}'
            role='judge' if eligible and mode!='probe_prop_only' and group!='push' else 'record_only'
            rows[case]={'case_id':case,'task':task,'map_mode':mode,'role':role,'direction':direction,
                'command_b':list(command),'steps':steps,'dt':.02,'hold_s':.5,
                'foot_height_tolerance_m':.08,'valid_min':48 if task=='cross_dir_half_flat' else 64,'success_min':52,'survival_min':60,
                'stop_at_goal':task not in ('cross_dir_half_flat','push_record') and group!='directions',
                'approach_yaw_rad':-math.atan2(command[1],command[0]),
                'source':'CG 368d03e2:299,316,387,393,394; lead 11/11 15:05',
                'measurement_assumptions':{'hold_s':.5,'foot_height_tolerance_m':.08,
                    'reset_heading':'rotate body to keep requested displacement along world +x'}}
    return rows


def create_request(*,plan_path,checkpoint,source_mesh,out,family,kind,level,stage,group,window_index,steps,seed=42,dr_table=None):
    from foothold_s2.eval.ex42_task_mesh import build_replicas,select_tile,task_anchors
    plan_path=Path(plan_path).resolve();checkpoint=Path(checkpoint).resolve();out=Path(out).resolve()
    if out.exists():raise FileExistsError(out)
    if type(seed) is not int or seed<0:raise ValueError('nonnegative integer seed required')
    plan=yaml.safe_load(plan_path.read_text(encoding='utf-8-sig'))
    geometry=kind.removesuffix('_reverse')
    timing=None
    if group in ('paper','kind'):
        tile=select_tile(source_mesh,family=family,kind=geometry,level=level)
        validate_geometry_calibration(plan,tile)
        reverse=kind in ('eval_stairs_010','eval_stairs_015_reverse','eval_stairs_020_reverse')
        timing=completion_timing(plan,origin=tile['origin'],anchors=task_anchors(tile),speed=.5 if reverse else 1.)
        steps=timing['steps']
    cases=case_specs(plan,stage=stage,group=group,family=family,kind=kind,window_index=window_index,steps=steps)
    checkpoint_sha=sha256(checkpoint)
    record={'format':FORMAT,'plan':str(plan_path),'plan_sha256':sha256(plan_path),
        'checkpoint':str(checkpoint),'checkpoint_sha256':checkpoint_sha,'source_mesh':str(Path(source_mesh).resolve()),
        'family':family,'kind':kind,'level':level,'stage_id':stage,'group':group,'window_index':window_index,
        'seed':seed,'envs':64,'case_specs':cases,'judge_cases':[k for k,v in cases.items() if v['role']=='judge'],
        'record_cases':[k for k,v in cases.items() if v['role']=='record_only'],
        'cross_settings':cross_settings(plan),'dr_mode':'on' if group=='push' else 'off','completion_timing':timing}
    if group=='push':
        record['push_mask']=push_applicability(plan,family,kind)
        if cases:
            if not dr_table:raise ValueError('DR push request requires pinned range table')
            from foothold_s2.eval.eval_dr_mode import load_table
            table=load_table(dr_table)
            record.update(dr_table=table['path'],dr_table_sha256=table['sha256'],dr_scale=1.)
    out.mkdir(parents=True,exist_ok=False)
    if cases:
        # Aliases use the same saved geometry, never another generated tile.
        replica=build_replicas(source_mesh,out/'replica',family=family,kind=geometry,level=level)
        record.update(replica_dir=str(out/'replica'),replica_receipt_sha256=sha256(out/'replica/replica_receipt.json'),
                      source_mesh_sha256=replica['source_mesh_sha256'])
        if any(s['task']=='cross_dir_half_flat' for s in cases.values()):
            build_replicas(source_mesh,out/'flat_replica',family=family,kind=geometry,level=level,flat=True)
            record.update(flat_replica_dir=str(out/'flat_replica'),flat_replica_receipt_sha256=sha256(out/'flat_replica/replica_receipt.json'))
    else: record['state']='n/a'
    path=out/'request.json';path.write_text(json.dumps(record,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    return path


def completion_timing(plan,*,origin,anchors,speed):
    cfg=plan['evaluation'].get('forward_completion_timing',{})
    if cfg.get('rule')!='distance_over_speed_plus_hold_plus_margin' or cfg.get('hold_s')!=.5 or cfg.get('margin_s')!=2.:
        raise ValueError('completion timing rule absent or not pinned')
    if speed<=0:raise ValueError('positive completion speed required')
    distance=max(0.,anchors['exit_x']-float(origin[0]));seconds=distance/speed+cfg['hold_s']+cfg['margin_s']
    steps=math.ceil(seconds/.02)
    return {'distance_m':distance,'speed_mps':speed,'hold_s':.5,'margin_s':2.,'dt':.02,'steps':steps,
            'seconds':steps*.02,'grade':'lead decision 11/11 15:20; timing margin is assumption'}


def validate_geometry_calibration(plan,tile):
    """The prep pins the CPU-measured per-cell geometry before policy results."""
    import numpy as np
    from foothold_s2.eval.ex42_task_mesh import task_anchors
    pin=plan['evaluation']['forward_completion_timing'].get('calibration_table',{})
    path=Path(pin.get('path',''))
    if not path.is_absolute():path=Path(__file__).resolve().parents[2]/path
    if not path.is_file() or sha256(path)!=pin.get('sha256'):raise ValueError('geometry timing table not pinned')
    table=json.loads(path.read_text(encoding='utf-8'))
    if tile['source_mesh_sha256'] not in {v['mesh_sha256'] for v in table['sources'].values()}:
        raise ValueError('source mesh has no premeasured geometry timing table')
    rows=[r for r in table['rows'] if (r['family'],r['kind'],r['level'])==(tile['family'],tile['kind'],tile['level'])]
    if len(rows)!=1 or not np.allclose(rows[0]['origin_m'],tile['origin'],atol=1e-6,rtol=0) or rows[0]['anchors']!=task_anchors(tile):
        raise ValueError('geometry timing table row differs from source')
    return pin['sha256']


def validate_request(path):
    path=Path(path);d=json.loads(path.read_text(encoding='utf-8'))
    if d.get('format')!=FORMAT or d.get('envs')!=64:raise ValueError('invalid task request')
    for file,sha in (('plan','plan_sha256'),('checkpoint','checkpoint_sha256')):
        if sha256(d[file])!=d[sha]:raise ValueError(f'request {file} changed')
    plan=yaml.safe_load(Path(d['plan']).read_text(encoding='utf-8-sig'))
    if not d['case_specs']:
        if d['group']!='push' or push_applicability(plan,d['family'],d['kind'])['status']!='n/a':raise ValueError('empty task suite')
        return d
    steps=next(iter(d['case_specs'].values()))['steps']
    if d['group'] in ('paper','kind'):
        from foothold_s2.eval.ex42_task_mesh import select_tile,task_anchors
        tile=select_tile(d['source_mesh'],family=d['family'],kind=d['kind'].removesuffix('_reverse'),level=d['level'])
        validate_geometry_calibration(plan,tile)
        speed=abs(next(iter(d['case_specs'].values()))['command_b'][0])
        timing=completion_timing(plan,origin=tile['origin'],anchors=task_anchors(tile),speed=speed)
        if d.get('completion_timing')!=timing or steps!=timing['steps']:raise ValueError('completion geometry/timing differs')
    expected=case_specs(plan,stage=d['stage_id'],group=d['group'],family=d['family'],kind=d['kind'],window_index=d['window_index'],steps=steps)
    if d['case_specs']!=expected or d['cross_settings']!=cross_settings(plan):raise ValueError('task case contract changed')
    for role,key in (('judge','judge_cases'),('record_only','record_cases')):
        if set(d[key])!={k for k,v in expected.items() if v['role']==role}:raise ValueError('task role list changed')
    if d['dr_mode']!=('on' if d['group']=='push' else 'off'):raise ValueError('task DR mode differs')
    for prefix in ('replica','flat_replica'):
        if prefix+'_dir' not in d:continue
        if sha256(Path(d[prefix+'_dir'])/'replica_receipt.json')!=d[prefix+'_receipt_sha256']:raise ValueError('replica receipt changed')
    if d['group']=='push':
        if (push_applicability(plan,d['family'],d['kind'])['status']!='enabled'
                or sha256(d['dr_table'])!=d['dr_table_sha256'] or d.get('dr_scale')!=1.):
            raise ValueError('push mask/table differs')
    return d


def run_request(path,*,device,python=sys.executable):
    d=validate_request(path)
    if not d['case_specs']:return {'state':'n/a','role':'record_only','reason':'training_push_mask_off'}
    out=Path(path).parent
    for flat in ((True,False) if 'flat_replica_dir' in d else (False,)):
        target=out/('flat_result' if flat else 'result')
        command=[python,'-m','foothold_s2.eval.ex42_task_eval','--request',str(path),
                 '--out',str(target),'--device',device,'--headless']
        if flat:command.append('--flat-reference')
        with (out/('flat.log' if flat else 'task.log')).open('x',encoding='utf-8') as log:
            subprocess.run(command,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,check=True)
    from foothold_s2.eval.ex42_task_evidence import read_evidence
    return read_evidence(out/'result',request_path=path)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('plan','checkpoint','source-mesh','out'):p.add_argument('--'+name,type=Path,required=True)
    for name in ('family','kind','stage'):p.add_argument('--'+name,required=True)
    p.add_argument('--group',choices=['paper','kind','directions','push'],required=True)
    for name in ('level','window-index','steps'):p.add_argument('--'+name,type=int,required=True)
    p.add_argument('--seed',type=int,default=42);p.add_argument('--dr-table',type=Path)
    p.add_argument('--execute',action='store_true');p.add_argument('--device')
    a=p.parse_args()
    if a.execute and not a.device:p.error('explicit --device required to execute')
    path=create_request(plan_path=a.plan,checkpoint=a.checkpoint,source_mesh=a.source_mesh,out=a.out,
        family=a.family,kind=a.kind,level=a.level,stage=a.stage,group=a.group,
        window_index=a.window_index,steps=a.steps,seed=a.seed,dr_table=a.dr_table)
    print(path,flush=True)
    if a.execute:print(json.dumps(run_request(path,device=a.device),ensure_ascii=False))


if __name__=='__main__':main()
