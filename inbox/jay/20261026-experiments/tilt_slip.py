# -*- coding: utf-8 -*-
"""부모 저장본 평가 원자료(turn16_<mode>/arrays_<case>.npz) 에서 몸 기울기 · 발 미끄럼 기준선.
tilt_deg = arccos(1 - 2(x^2+y^2)) (root_quat = w,x,y,z; 몸 z 축과 세계 z 축 사이 각). slip = 접촉(force > 1 N) 중인 발의 평면 속도 평균.
사용: python -I tilt_slip.py <eval_root> m900 m1000 ... (eval_root/<m>/turn16_<mode>/arrays_*.npz)"""
import sys, os, glob, json
import numpy as np

FEET = [4, 8, 14, 18]
MODES = ("eval_gt", "probe_prop_only")

def one(npz):
    z = np.load(npz)
    alive = z["alive"].astype(bool)                      # (16, T)
    kept = z["kept"].astype(bool)
    q = z["root_quat"]                                   # (16, T, 4) w x y z
    x, y = q[..., 1], q[..., 2]
    cos_t = np.clip(1.0 - 2.0 * (x * x + y * y), -1.0, 1.0)
    tilt = np.degrees(np.arccos(cos_t))                  # (16, T)
    force = z["force"][..., FEET] > 1.0                  # (16, T, 4)
    sp = z["link_xy_speed"][..., FEET]                   # (16, T, 4)
    out = []
    for e in range(alive.shape[0]):
        a = alive[e]
        if a.sum() == 0:
            out.append((kept[e], np.nan, np.nan, np.nan, np.nan)); continue
        t = tilt[e][a]
        c = force[e][a]
        s = sp[e][a]
        slip = s[c].mean() if c.any() else np.nan
        p95 = np.percentile(s[c], 95) if c.any() else np.nan
        out.append((kept[e], t.mean(), np.percentile(t, 95), slip, p95))
    return out

root = sys.argv[1]
print("| 저장본 | 모드 | kept env 수 | tilt 평균 중앙값(deg) | tilt p95 중앙값 | tilt p95 최대 env | slip 평균 중앙값(m/s) | slip p95 중앙값 | slip 평균 최대 env |")
print("|---|---|---:|---:|---:|---:|---:|---:|---:|")
summary = {}
for m in sys.argv[2:]:
    for mode in MODES:
        rows = []
        for f in sorted(glob.glob(os.path.join(root, m, "turn16_" + mode, "arrays_*.npz"))):
            rows += [r for r in one(f) if r[0]]
        if not rows:
            print("| %s | %s | 0 | 없음 |" % (m, mode)); continue
        a = np.array([r[1:] for r in rows], dtype=float)
        med = np.nanmedian(a, axis=0)
        print("| %s | %s | %d | %.2f | %.2f | %.2f | %.3f | %.3f | %.3f |" % (m, mode, len(rows), med[0], med[1], np.nanmax(a[:, 1]), med[2], med[3], np.nanmax(a[:, 2])))
        summary[(m, mode)] = dict(n=len(rows), tilt_mean_med=float(med[0]), tilt_p95_med=float(med[1]), tilt_p95_max=float(np.nanmax(a[:, 1])), slip_mean_med=float(med[2]), slip_p95_med=float(med[3]), slip_mean_max=float(np.nanmax(a[:, 2])))
json.dump({"%s/%s" % k: v for k, v in summary.items()}, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "tilt_slip_summary.json"), "w"), indent=1)
