"""Read-only CPU evidence extraction. No training, Kit, or live-ledger writes."""
from pathlib import Path
import hashlib
import json
import math
import os
import statistics
import sys
import tempfile

os.environ['CUDA_VISIBLE_DEVICES'] = ''
sys.dont_write_bytecode = True

import torch
import yaml
from tensorboard.backend.event_processing.event_accumulator import EventAccumulator

SOURCE = Path('C:/mai/wt/foothold-lab/analyst-ex40-main-verified-1031')
ROOT = Path('C:/Users/AI-WS01/s2_lab/ex40_main_20261031_041313')
RUN = ROOT / 'main/EX-40-B-main_20261031_041337_26240'
OUT = Path(__file__).with_name('EX41-READINESS-EVIDENCE.json')
sys.path.insert(0, str(SOURCE))
from foothold_s2.curriculum.continuous import Plan
from foothold_s2.curriculum.ex40_dr import dr_scale, delay_limit

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

ck = RUN / 'model_7500.pt'
s = torch.load(ck, map_location='cpu', weights_only=False)
e = EventAccumulator(str(RUN), size_guidance={'scalars': 0})
e.Reload()
tags = ['Train/mean_reward', 'Train/mean_episode_length', 'Loss/learning_rate',
        'Policy/mean_noise_std', 'Loss/value_function', 'Loss/entropy',
        'Loss/kl_probe/ppo_mean', 'Episode_Reward/track_lin_vel', 'Episode_Reward/track_ang_vel']
series = {k: {x.step: x.value for x in e.Scalars(k)} for k in tags}
curves = {}
for n in [5950, 6000, 6001, 6100, 6500, 7000, 7250, 7500]:
    curves[str(n)] = {}
    for k, d in series.items():
        a = [d[i] for i in range(n-49, n+1) if i in d]
        curves[str(n)][k] = {'at_update': d.get(n), 'trailing50_mean': statistics.mean(a), 'n': len(a)}
    d, l = series['Train/mean_reward'], series['Train/mean_episode_length']
    ratios = [d[i]/l[i] for i in range(n-49, n+1) if i in d and i in l and l[i] > 0]
    curves[str(n)]['reward_div_episode_length'] = {'trailing50_mean': statistics.mean(ratios), 'n': len(ratios)}

scores = {}
for n in [5500, 5750, 6000, 6250, 6500, 6750, 7000, 7250, 7500]:
    paths = sorted((ROOT/'scores-b').glob(f'score_{n}_*.json'))
    assert len(paths) == 1, (n, paths)
    p = paths[0]; d = json.loads(p.read_text(encoding='utf-8-sig'))
    scores[str(n)] = {'path': str(p), 'sha256': sha(p), 'verdict': d['verdict'],
                      'reasons': {k:v for k,v in d.items() if 'reason' in k or 'fail' in k or k=='problems'},
                      'sources': d.get('sources'), 'judged_modes': d.get('judged_modes'),
                      'cells': d['cells']}

yaw = []
for p in (ROOT/'axis250').glob('model_*/axis_v2.json'):
    n = int(p.parent.name.removeprefix('model_'))
    if 5500 <= n <= 7500:
        d = json.loads(p.read_text(encoding='utf-8-sig'))
        yaw.append({'update':n,'path':str(p),'sha256':sha(p),'values_deg':{
            m:{c:math.degrees(d['modes'][m][c]['yaw_final_minus_start_median_rad'])
               for c in ['fwd0.5','fwd1.0']} for m in ['eval_gt','probe_prop_only','eval_pred']}})
retry_root = Path('C:/Users/AI-WS01/s2_lab/ex40_w57_retry_separate_20261031')
for p in retry_root.rglob('axis_v2.json'):
    for n in [6000,7500]:
        if f'model_{n}_' in str(p):
            d = json.loads(p.read_text(encoding='utf-8-sig'))
            yaw.append({'update':n,'path':str(p),'sha256':sha(p),'values_deg':{
                m:{c:math.degrees(d['modes'][m][c]['yaw_final_minus_start_median_rad'])
                   for c in ['fwd0.5','fwd1.0']} for m in ['eval_gt','probe_prop_only','eval_pred']}})

plan_path = SOURCE/'foothold_s2/curriculum/ex40.yaml'
doc = yaml.safe_load(plan_path.read_text(encoding='utf-8'))
checks = {}
with tempfile.TemporaryDirectory(prefix='ex41_readiness_') as td:
    for name, alter in [
        ('ex41_stage_ids_rejected_by_ex40_parser', lambda d: d['stages'][0].update(id='S2-0')),
        ('new_reward_at_n0_rejected_by_exact_FIRST_REWARDS', lambda d: d['stages'][0]['adds']['rewards'].update(zero_yaw=-.5)),
    ]:
        d = yaml.safe_load(yaml.safe_dump(doc)); alter(d)
        p = Path(td)/f'{name}.yaml'; p.write_text(yaml.safe_dump(d),encoding='utf-8')
        try:
            Plan(p, arm='B')
        except ValueError as ex:
            checks[name] = {'caught': True, 'message': str(ex)}
        else:
            raise AssertionError(name)
checks['shares'] = {'S2a': sum([23,7.5,7.5,9,9,10,14,6,6,1.5,1.5,2.5,2.5]),
                    'S2b': sum([23,6,6,9,9,10,14,7,7,2,2,2.5,2.5])}
assert checks['shares'] == {'S2a':100.0,'S2b':100.0}
out = {
    'source_commit': '2df419b0a4278981f6bd26e5eaedecbf7e8458db',
    'checkpoint': {'path': str(ck), 'sha256': sha(ck), 'iter': s['iter'],
                   'ppo_learning_rate': s['ppo_learning_rate'],
                   'ppo_optimizer_lr': [g['lr'] for g in s['optimizer_state_dict']['param_groups']],
                   'perception_optimizer_lr': [g['lr'] for g in s['perception_optimizer_state_dict']['param_groups']],
                   'std_min_mean_max': [float(s['model_state_dict']['std'].min()),
                                        float(s['model_state_dict']['std'].mean()),float(s['model_state_dict']['std'].max())],
                   'adasmpl': s['adasmpl'],
                   'curriculum_scalars': {k:v for k,v in s['continuous_curriculum'].items()
                                          if isinstance(v,(str,int,float,bool))},
                   'first_layer_shapes': {group: {k:list(v.shape) for k,v in s[group].items()
                     if any(x in k for x in ('actor.0','critic.0','ie.prop_mlp.0','ie.dec_o.4'))}
                     for group in ('model_state_dict','perception_state_dict')}},
    'saved_config_sha256': {str(p):sha(p) for p in (RUN/'params').glob('*.yaml')},
    'dr_schedule': {str(n): {'scale':dr_scale(n),'delay':delay_limit(dr_scale(n))}
                    for n in [1500,1501,6000,6001,7500]},
    'curve_event_file': str(next(RUN.glob('events.out.tfevents.*'))),
    'curve_tags':tags, 'curves':curves, 'scores':scores, 'yaw':yaw, 'known_input_checks':checks,
    'limits':'Single run, serially dependent checkpoints; no DR-only counterfactual. No GPU or Kit used.'}
OUT.write_text(json.dumps(out,indent=2,ensure_ascii=False,allow_nan=False)+'\n',encoding='utf-8')
print('checkpoint',out['checkpoint']['sha256'],out['checkpoint']['std_min_mean_max'])
print('known inputs',checks)
for n in ['5950','6100','7250','7500']:
    x=curves[n];print('curve',n,*[round(x[t]['trailing50_mean'],6) for t in tags],
                     round(x['reward_div_episode_length']['trailing50_mean'],6))
for n in scores:
    d=scores[n];print('score',n,d['verdict'],json.dumps(d['reasons'],ensure_ascii=False))
    print('back1', {mode:d['cells'].get(mode+'/back1.0') for mode in ['eval_gt','eval_pred','probe_prop_only']})
print('saved',OUT)
