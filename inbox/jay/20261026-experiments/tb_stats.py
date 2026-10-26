# -*- coding: utf-8 -*-
"""부모 학습 곡선(tfevents) 의 50 회 창 통계. 사용: python -I tb_stats.py <run_dir> <start_it> <end_it>"""
import sys, json, os
import numpy as np
from tensorboard.backend.event_processing import event_accumulator as ea

TAGS = ["Train/mean_reward", "Train/mean_episode_length", "Loss/value_function", "Loss/surrogate", "Loss/entropy", "Policy/mean_noise_std",
        "Loss/kl_probe/ppo_mean", "Loss/learning_rate", "Episode_Termination/bad_orientation", "Episode_Termination/foot_below_ground",
        "Metrics/base_velocity/error_vel_xy", "Metrics/base_velocity/error_vel_yaw", "Episode_Reward/track_lin_vel", "Episode_Reward/track_ang_vel",
        "Episode_Reward/stumble", "Loss/map_switch/on_terrain_level_mean", "Loss/map_switch/off_terrain_level_mean", "Loss/reward_split/frac_stalled"]
acc = ea.EventAccumulator(sys.argv[1], size_guidance={ea.SCALARS: 0}); acc.Reload()
s, e = int(sys.argv[2]), int(sys.argv[3])
out = {}
print("| 지표 | 창(50 회) 평균: " + " · ".join("m%d" % w for w in range(s + 50, e + 1, 50)) + " | 전체 중앙값 | MAD | 최소 | 최대 | 창 평균 최대/최소 비 |")
print("|---|---|---:|---:|---:|---:|---:|")
for t in TAGS:
    if t not in acc.Tags()["scalars"]:
        print("| %s | 없음 |" % t); continue
    ev = acc.Scalars(t)
    it = np.array([x.step for x in ev]); v = np.array([x.value for x in ev], dtype=float)
    sel = (it > s) & (it <= e)
    it, v = it[sel], v[sel]
    wins = []
    for w in range(s + 50, e + 1, 50):
        m = (it > w - 50) & (it <= w)
        wins.append(float(np.mean(v[m])) if m.any() else float("nan"))
    med = float(np.median(v)); mad = float(np.median(np.abs(v - med)))
    ratio = (max(wins) / min(wins)) if min(wins) not in (0.0,) and np.isfinite(min(wins)) and min(wins) > 0 else float("nan")
    print("| %s | %s | %.4g | %.4g | %.4g | %.4g | %.3g |" % (t, " · ".join("%.4g" % x for x in wins), med, mad, v.min(), v.max(), ratio))
    out[t] = dict(windows=wins, median=med, mad=mad, min=float(v.min()), max=float(v.max()), n=int(len(v)))
json.dump(out, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "tb_stats_%d_%d.json" % (s, e)), "w"), indent=1)
