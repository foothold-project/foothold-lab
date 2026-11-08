"""RULES-HUB 8.2 회전 판정 (최신 · 직전 · 다섯 저장본의 같은 저장본 min(좌, 우)) 과 몸 기울기 (16 env 여섯 경우, root_quat).
rulecheck N05 · N06 (10/26 18:40). lead 10/26.
"""
import json
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent
L = Path("C:/mai/wt/foothold-lab/impl-turncases/logs")
CASES = ["indep_left", "indep_right", "fwd_then_left", "fwd_then_right", "right_then_left", "left_then_right"]
out = ["# 회전 다섯 저장본 min 과 몸 기울기", "",
       "## 회전 (64 env 제자리 추종 중앙값, 저장본별 min(좌, 우), m1100~m1500)", "",
       "| 판 | 모드 | 저장본별 min(좌, 우) | 최신 m1500 | 직전 m1400 | 다섯 중 최소 |", "|---|---|---|---|---|---|"]
rows = json.loads((HERE / "rot_series.json").read_text(encoding="utf-8"))
res = {"rot": {}, "tilt": {}}
for run in ("sb50", "sb10"):
    rr = sorted([x for x in rows if x["run"] == run and x["it"] >= 1100], key=lambda x: x["it"])
    assert [x["it"] for x in rr] == [1100, 1200, 1300, 1400, 1500], run
    for mo in ("eval_gt", "probe_prop_only"):
        m = [min(x[mo + "_L"], x[mo + "_R"]) for x in rr]
        res["rot"][f"{run}|{mo}"] = m
        out.append(f"| {run} | {mo} | {' · '.join(f'{v:.2f}' for v in m)} | {m[-1]:.2f} | {m[-2]:.2f} | {min(m):.2f} |")
out += ["", "## 몸 기울기 (16 env 여섯 경우, kept env 의 살아 있는 step 평균, 도)", "",
        "기울기 = 몸 z 축과 세계 z 축 사이 각, root_quat (w, x, y, z) 에서 cos = 1 - 2(x^2 + y^2).", "",
        "| 판 | 모드 | 여섯 경우 평균 | 최소 | 최대 |", "|---|---|---|---|---|"]
for run, p in (("B1500", "b1500_baseline/rep1"), ("S-B50", "sb50_eval/m1500"), ("S-B10", "sb10_eval/m1500")):
    for mo in ("eval_gt", "probe_prop_only"):
        vals = []
        for c in CASES:
            z = np.load(L / p / f"turn16_{mo}" / f"arrays_{c}.npz")
            q, a, k = z["root_quat"], z["alive"], z["kept"]
            t = np.degrees(np.arccos(np.clip(1 - 2 * (q[..., 1] ** 2 + q[..., 2] ** 2), -1, 1)))
            vals.append(float(np.nanmean(np.where(a[k], t[k], np.nan))))
        res["tilt"][f"{run}|{mo}"] = vals
        out.append(f"| {run} | {mo} | {np.mean(vals):.2f} | {min(vals):.2f} | {max(vals):.2f} |")
out += ["", "해석 미완. B1500 지도 가림의 큰 기울기는 가림에서 못 걷는 판 (43/64) 이라 넘어지는 중의 자세가 섞인다 (추정)."]
(HERE / "rot_min5_tilt.md").write_text("\n".join(out) + "\n", encoding="utf-8")
(HERE / "rot_min5_tilt.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
print("\n".join(out))
