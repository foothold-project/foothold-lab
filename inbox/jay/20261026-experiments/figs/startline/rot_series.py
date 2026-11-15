"""S-B50 · S-B10 저장본별 회전 (64 env 제자리 추종 중앙값 · 16 env Q 평균) 과 전진. 회전이 학습 중 오르내리는지 본다. lead 10/26."""
import json, sys
from pathlib import Path
sys.path.insert(0, "C:/mai/wt/foothold-lab/impl-judge")
from foothold_s2.eval.judge_stats import turn_stats  # noqa: E402
L = Path("C:/mai/wt/foothold-lab/impl-turncases/logs")
CASES = ["indep_left", "indep_right", "fwd_then_left", "fwd_then_right", "right_then_left", "left_then_right"]
rows = []
for run in ("sb50_eval", "sb10_eval"):
    for n in range(100, 1501, 100):
        d = L / run / f"m{n}"
        f = d / "map64/map_modes.json"
        if not f.exists():
            continue
        m = json.loads(f.read_text(encoding="utf-8"))["modes"]
        r = {"run": run[:4], "it": n}
        for mode in ("eval_gt", "probe_prop_only"):
            mm = m[mode]
            r[f"{mode}_L"] = mm["spin+1.2"]["yaw_follow_median"]; r[f"{mode}_R"] = mm["spin-1.2"]["yaw_follow_median"]
            r[f"{mode}_F1"] = mm["fwd1.0"]["body_vx_integral_median_m"]
            t = d / f"turn16_{mode}"
            qs = [turn_stats(t / f"arrays_{c}.npz", c)["Q"] for c in CASES] if (t / "probe_result.json").exists() else []
            r[f"{mode}_Qmin"] = min(qs) if qs else None; r[f"{mode}_Qmax"] = max(qs) if qs else None
        rows.append(r)
print("| 판 | 회차 | 켬 전진1.0 | 가림 전진1.0 | 켬 좌/우 추종 | 가림 좌/우 | 켬 16env Q 최소~최대 | 가림 Q 최소~최대 |")
print("|---|---|---|---|---|---|---|---|")
for r in rows:
    q = lambda a, b: f"{a:.2f}~{b:.2f}" if a is not None else "-"
    print(f"| {r['run']} | {r['it']} | {r['eval_gt_F1']:.2f} | {r['probe_prop_only_F1']:.2f} | {r['eval_gt_L']:.2f}/{r['eval_gt_R']:.2f} | {r['probe_prop_only_L']:.2f}/{r['probe_prop_only_R']:.2f} | {q(r['eval_gt_Qmin'], r['eval_gt_Qmax'])} | {q(r['probe_prop_only_Qmin'], r['probe_prop_only_Qmax'])} |")
Path(__file__).with_name("rot_series.json").write_text(json.dumps(rows, indent=1, default=float), encoding="utf-8")
