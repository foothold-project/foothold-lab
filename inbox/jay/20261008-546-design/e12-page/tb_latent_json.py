# 학습 기록 (tensorboard) 의 Loss/mean_latent_loss 를 구간 평균으로 뽑아 latent.json 으로 쓴다. isaac311-moects 파이썬으로 돈다 (tensorboard 필요).
import glob, json, math, os
from tensorboard.backend.event_processing.event_accumulator import EventAccumulator
RUNS = {'E1': 'C:/isaac/ext/go2_rl_robotlab/logs/rsl_rl/go2_moe_cts/2026-10-10_12-47-48_e1_seed42_n8192',
        'E2': 'C:/isaac/ext/go2_rl_robotlab/logs/rsl_rl/go2_moe_cts/2026-10-11_12-39-32_e2_seed43_n8192'}
WIN = {'early': (900, 1000), 'mid': (9900, 10000), 'pre': (19500, 20000), 'post': (20400, 20500)}
out = {}
for run, d in RUNS.items():
    ea = EventAccumulator(glob.glob(d + '/events.out.tfevents.*')[0], size_guidance={'scalars': 0}); ea.Reload()
    pick = {e.step: e.value for e in ea.Scalars('Loss/mean_latent_loss')}
    for k, (a, b) in WIN.items():
        v = [pick[s] for s in range(a, b) if s in pick]
        m = sum(v) / len(v)
        d2 = 32 * m  # 칸당 제곱 평균 × 32 칸 = 두 단위 벡터 사이 거리의 제곱
        out[f'{run}_{k}'] = {'mse': m, 'angle_deg': 2 * math.degrees(math.asin(math.sqrt(d2) / 2)), 'cos': 1 - d2 / 2, 'n': len(v)}
json.dump(out, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'latent.json'), 'w'), indent=1)
print(json.dumps({k: round(v['angle_deg'], 1) for k, v in out.items()}))
