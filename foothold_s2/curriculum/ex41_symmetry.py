"""D101 lead interpretation 2026-11-02 19:3x; record-only mirror candidates.

Signed raw movement ratios are preserved. Derived symmetry never enables PPO.
Map64 uses the median of all 64 per-env actual/planned displacement ratios;
spin uses angular displacement, not absolute tracking error or survival rate.
"""
import math
import statistics

SCHEMA='ex41-critic-mirror-symmetry/1'
MODES=('eval_gt','probe_prop_only','eval_pred')
MAP_PAIRS={'side':('side+0.5','side-0.5'),
           'diag_fwd':('diag-fwd+side+','diag-fwd+side-'),
           'diag_back':('diag-back+side+','diag-back+side-'),
           'spin':('spin+1.2','spin-1.2')}
STAIR_KINDS=('pyramid_stairs','pyramid_stairs_inv')
EXPECTED_PAIRS={'map64/'+k for k in MAP_PAIRS}|{
    f'w78/L{level}_a{angle:03d}_{kind}' for level in (2,5)
    for angle in (0,30,60,90) for kind in STAIR_KINDS}


def finite(value):
    return type(value) in (int,float) and math.isfinite(value)


def pair(left,right):
    if any(x is not None and not finite(x) for x in (left,right)):
        raise ValueError('mirror movement ratios must be finite or missing')
    value=None;reason='missing_side'
    if left is not None and right is not None:
        denominator=max(left,right)
        reason='nonpositive_denominator'
        if denominator>0:
            value=min(left,right)/denominator
            reason=None if math.isfinite(value) else 'nonfinite_quotient'
            if reason:value=None
    return {'left':left,'right':right,'symmetry':value,'valid':value is not None,'reason':reason}


def map_pairs(doc):
    steps,dt=doc.get('steps'),doc.get('policy_dt_s')
    if type(steps) is not int or steps<=0 or not finite(dt) or dt<=0:
        raise ValueError('mirror map planned duration missing')
    result={}
    for mode in MODES:
        result[mode]={}
        for name,cases in MAP_PAIRS.items():
            values=[]
            for case in cases:
                row=doc['modes'][mode][case]; cmd=row['command']; per=row['per_env']
                if (len(per)!=64 or sorted(r['env'] for r in per)!=list(range(64))
                    or len(cmd)!=3 or not all(finite(x) for x in cmd)):
                    raise ValueError('mirror map per-env contract differs')
                speeds=math.hypot(*cmd[:2]); measurements=[]
                for env in per:
                    count=env['samples_alive']
                    if type(count) is not int or not 0<=count<=steps:
                        raise ValueError('mirror alive sample count invalid')
                    if name=='spin':
                        if speeds!=0 or cmd[2]==0:raise ValueError('spin command differs')
                        rate=env['yaw_follow_mean_alive']
                        # yaw_follow is signed wz/cmd. Multiplying by alive
                        # duration and dividing by planned duration gives angle ratio.
                        value=0. if count==0 else rate*count/steps if finite(rate) else None
                    else:
                        if speeds<=0 or cmd[2]!=0:raise ValueError('translation command differs')
                        distance=env['command_xy_projection_integral_m']
                        value=distance/(speeds*steps*dt) if finite(distance) else None
                    if not finite(value):raise ValueError('mirror displacement ratio missing/nonfinite')
                    measurements.append(value)
                values.append(statistics.median(measurements))
            result[mode]['map64/'+name]={**pair(*values),'source_cases':list(cases),
                'unit':'angular_displacement_ratio' if name=='spin' else 'projected_displacement_ratio',
                'aggregation':'median_of_64_per_env_ratios_full_planned_duration'}
    return result


def combine(map_rows,w78_raw):
    result={'schema':SCHEMA,'decision_mode':'eval_gt',
            'interpretation':'lead 2026-11-02 19:3x; S=min(left,right)/max(left,right)',
            'modes':{m:dict(map_rows[m]) for m in MODES}}
    for mode in MODES:
        for level in (2,5):
            for angle in (0,30,60,90):
                for kind in STAIR_KINDS:
                    source=f'L{level}_a{angle:03d}_{mode}_{kind}'
                    raw=w78_raw[source]
                    result['modes'][mode][f'w78/L{level}_a{angle:03d}_{kind}']={
                        **pair(raw['left'],raw['right']),'source_cell':source,
                        'aggregation':'W78_movement_ratio_median_by_terrain_kind',
                        'unit':'projected_displacement_ratio'}
    validate(result)
    return result


def validate(data):
    if (not isinstance(data,dict) or data.get('schema')!=SCHEMA
        or data.get('decision_mode')!='eval_gt' or not isinstance(data.get('modes'),dict)
        or set(data['modes'])!=set(MODES)):
        raise ValueError('mirror symmetry contract differs')
    for rows in data['modes'].values():
        if not isinstance(rows,dict) or set(rows)!=EXPECTED_PAIRS:
            raise ValueError('mirror symmetry pairs incomplete')
        for row in rows.values():
            if (not isinstance(row,dict) or not {'left','right','symmetry','valid','reason'}<=set(row)
                or type(row['valid']) is not bool
                or row['symmetry'] is not None and not finite(row['symmetry'])):
                raise ValueError('mirror pair shape/types differ')
            expected=pair(row.get('left'),row.get('right'))
            if any(row.get(k)!=v for k,v in expected.items()):
                raise ValueError('mirror symmetry differs from raw movement ratios')
