"""EX41 numeric score contract from original map64 and three flat-stand files.

No Kit imports. The EX40 per-env stance definition is reused, while EX41's
restoration threshold remains 61/64 in its runtime. map64_b3 is not a substitute.
"""
from pathlib import Path
import copy
import json

from foothold_s2.curriculum.ex41_fixed import CASES, build_maintenance_counts, baseline_counts, maintenance
from foothold_s2.ex40_score import config, sha256, _map_rows, _stand_rows, _stand_pass

MODES=('eval_gt','probe_prop_only','eval_pred')
DEFAULT_CONFIG=Path(__file__).with_name('ex40_score_config.json')


def maintenance_counts_from_map_modes(map_modes, baseline):
    """Exact numeric producer used by the runner, not a second set of rules."""
    if (not isinstance(map_modes,dict) or type(map_modes.get('envs')) is not int
        or map_modes['envs']!=64 or map_modes.get('command_suite')!='extended'
        or not isinstance(map_modes.get('modes'),dict) or set(map_modes['modes'])!=set(MODES)):
        raise ValueError('EX41 needs map64 extended and all three 64-env modes')
    cells={}
    for mode in MODES:
        cases=map_modes['modes'][mode]
        if not isinstance(cases,dict) or not set(CASES)<=set(cases):
            raise ValueError('EX41 map64 cases incomplete: '+mode)
        for case in CASES:
            row=cases[case]
            per=row.get('per_env') if isinstance(row,dict) else None
            if (not isinstance(per,list) or len(per)!=64 or type(row.get('env_count')) is not int
                or row['env_count']!=64 or any(not isinstance(e,dict) or type(e.get('env')) is not int
                    or type(e.get('alive_at_end')) is not bool for e in per)
                or sorted(e['env'] for e in per)!=list(range(64))
                or type(row.get('alive_envs_at_end')) is not int
                or row['alive_envs_at_end']!=sum(e['alive_at_end'] for e in per)):
                raise ValueError('EX41 per-env survival/count mismatch: '+mode+'/'+case)
            key=f'{mode}/{case}'+('_record_only' if mode=='eval_pred' else '')
            cells[key]={'alive_envs_at_end':row['alive_envs_at_end']}
    return build_maintenance_counts({'cells':cells},baseline,total_envs=64)


def measurement_bundle(map_modes_path, stand_paths, checkpoint_path, baseline, *, score_config_path=DEFAULT_CONFIG):
    """Read raw files and return metrics plus their exact evidence hashes.

    stand_paths is a mapping with all MODES, each pointing to stand.json.
    Missing/NaN/invalid stand evidence raises; it is never replaced with 64.
    """
    if not isinstance(stand_paths,dict) or set(stand_paths)!=set(MODES):
        raise ValueError('EX41 stand evidence requires all three modes')
    cp=Path(checkpoint_path).resolve(strict=True)
    map_path=Path(map_modes_path).resolve(strict=True)
    cfg_path=Path(score_config_path).resolve(strict=True); cfg=config(cfg_path)
    data=_map_rows(map_path,cp,cfg)
    counts=maintenance_counts_from_map_modes(data,baseline)
    stands={}; evidence=[map_path,cfg_path]
    for mode in MODES:
        path=Path(stand_paths[mode]).resolve(strict=True)
        rows=_stand_rows(path,cp,mode,cfg)
        if any(type(row.get('alive_at_end')) is not bool for row in rows):
            raise ValueError('EX41 stand alive flag must be boolean')
        passed=sum(bool(_stand_pass(row,cfg['stand'])) for row in rows)
        stands[mode]={'passed':passed,'total':64}
        evidence.extend((path,path.parent/'stand_raw.npz'))
    return {'metrics':{'record_counts':counts,'stand_counts':stands,
                       'stand_min_passed':min(r['passed'] for r in stands.values())},
            'checkpoint_iteration':data['checkpoint_iter'],'checkpoint_sha256':data['checkpoint_sha256'],
            'evidence':[{'path':str(p),'sha256':sha256(p)} for p in evidence]}


def enrich_score_metrics(draft, map_modes_path, stand_paths, plan, *, score_config_path=DEFAULT_CONFIG):
    """Runner's one score/1 enrichment entry; existing stage verdict is preserved."""
    if (not isinstance(draft,dict) or draft.get('format')!='foothold-ex41-score/1'
        or type(draft.get('iteration')) is not int or not isinstance(draft.get('metrics'),dict)
        or not isinstance(draft.get('evidence'),list)
        or any(type(draft.get(k)) is not bool for k in ('maintenance_pass','stage_pass','safety_stop'))
        or draft.get('schedule_sha256')!=plan.effective_sha256
        or draft.get('parent_sha256')!=plan.parent_sha256
        or draft.get('baseline_checkpoint_sha256')!=plan.parent_sha256):
        raise ValueError('EX41 score draft identity/fields differ')
    baseline=baseline_counts(plan,include_record_only=True)  # D133 records all 39
    bundle=measurement_bundle(map_modes_path,stand_paths,draft['checkpoint_path'],baseline,
                              score_config_path=score_config_path)
    if (bundle['checkpoint_iteration']!=draft['iteration'] or bundle['checkpoint_sha256']!=draft.get('checkpoint_sha256')):
        raise ValueError('EX41 measured checkpoint differs from draft')
    result=copy.deepcopy(draft); result['metrics'].update(bundle['metrics'])
    judged=baseline_counts(plan)
    result['metrics']['maintenance_counts']={k:copy.deepcopy(bundle['metrics']['record_counts'][k]) for k in judged}
    result['maintenance_pass']=maintenance(result['metrics']['maintenance_counts'],judged)==[]
    for row in bundle['evidence']:
        if row not in result['evidence']:result['evidence'].append(row)
    json.dumps(result,allow_nan=False)
    return result
