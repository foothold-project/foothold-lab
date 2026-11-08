"""출발선 비교 표 (B1500 · G0-B · S-B50 · S-B10, m1500, 같은 칸 · 같은 시드). lead 10/26 13시.
64 env: map_modes.json 의 전진 거리 중앙값 · 회전 추종 중앙값 · 생존. 16 env: impl-judge judge_stats.turn_stats (Q = 명령 부호 x env 평균 요, env 같은 무게, C = 네 발 동시 접촉).
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, "C:/mai/wt/foothold-lab/impl-judge")
from foothold_s2.eval.judge_stats import turn_stats  # noqa: E402

L = Path("C:/mai/wt/foothold-lab/impl-turncases/logs")
RUNS = {
    "B1500": {"map64": L / "b1500_baseline/rep1/map64/map_modes.json", "turn": {m: L / f"b1500_baseline/rep1/turn16_{m}" for m in ("eval_gt", "probe_prop_only", "eval_pred")}},
    "G0-B": {"map64": L / "g0b_eval/m1500/map64/map_modes.json", "turn": {"none": L / "g0b_eval/m1500/turn16"}},
    "S-B50": {"map64": L / "sb50_eval/m1500/map64/map_modes.json", "turn": {m: L / f"sb50_eval/m1500/turn16_{m}" for m in ("eval_gt", "probe_prop_only", "eval_pred")}},
    "S-B10": {"map64": L / "sb10_eval/m1500/map64/map_modes.json", "turn": {m: L / f"sb10_eval/m1500/turn16_{m}" for m in ("eval_gt", "probe_prop_only", "eval_pred")}},
}
CASES = ["indep_left", "indep_right", "fwd_then_left", "fwd_then_right", "right_then_left", "left_then_right"]
out = {"map64": {}, "turn": {}}
print("## 64 env 6 초 (전진 거리 m / 회전 추종 / 생존 64)")
print("| 판 | 모드 | 전진 0.5 | 전진 1.0 | 좌 제자리 | 우 제자리 |")
print("|---|---|---|---|---|---|")
for name, r in RUNS.items():
    j = json.loads(r["map64"].read_text(encoding="utf-8"))
    for mode, m in j["modes"].items():
        row = {k: (v["body_vx_integral_median_m"], v["yaw_follow_median"], v["alive_envs_at_end"]) for k, v in m.items()}
        out["map64"][f"{name}|{mode}"] = row
        f = lambda k, d: f"{row[k][0]:.2f} ({row[k][2]})" if d else f"{row[k][1]:.2f} ({row[k][2]})"
        print(f"| {name} | {mode} | {f('fwd0.5', 1)} | {f('fwd1.0', 1)} | {f('spin+1.2', 0)} | {f('spin-1.2', 0)} |")
print()
print("## 16 env 회전 여섯 경우 (Q 명령 방향 rad/s / C 네 발 동시, 괄호 = 끝까지 선 env /16)")
print("| 판 | 모드 | " + " | ".join(CASES) + " |")
print("|---|---|" + "---|" * len(CASES))
for name, r in RUNS.items():
    for mode, d in r["turn"].items():
        cells = []
        for c in CASES:
            s = turn_stats(d / f"arrays_{c}.npz", c)
            out["turn"][f"{name}|{mode}|{c}"] = {k: s[k] for k in ("Q", "C", "kept", "n_fallen", "alive_end") if k in s}
            cells.append(f"{s['Q']:+.2f} / {s['C']:.2f} ({s['alive_end']})")
        print(f"| {name} | {mode} | " + " | ".join(cells) + " |")
Path(__file__).with_name("startline_table.json").write_text(json.dumps(out, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
