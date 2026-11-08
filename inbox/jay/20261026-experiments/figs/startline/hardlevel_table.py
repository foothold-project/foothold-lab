"""지도가 쓸모 있나: 레벨 0~2 (기존 칸) · 6 · 9 에서 지도 켬 대 가림, 64 env 6 초 전진 1.0 거리 m (생존). lead 10/26."""
import json
from pathlib import Path
L = Path("C:/mai/wt/foothold-lab/impl-turncases/logs")
SRC = {
 "B1500": {"0~2": L/"b1500_baseline/rep1/map64", "6": L/"hardlevel/b1500_L6/map64", "9": L/"hardlevel/b1500_L9/map64"},
 "G0-B": {"0~2": L/"g0b_eval/m1500/map64", "6": L/"hardlevel/g0b_L6/map64", "9": L/"hardlevel/g0b_L9/map64"},
 "S-B50": {"0~2": L/"sb50_eval/m1500/map64", "6": L/"hardlevel/sb50_L6/map64", "9": L/"hardlevel/sb50_L9/map64"},
 "S-B10": {"0~2": L/"sb10_eval/m1500/map64", "6": L/"hardlevel/sb10_L6/map64", "9": L/"hardlevel/sb10_L9/map64"},
}
out = {}
print("| 판 | 레벨 | 켬 (none) 전진 1.0 | 가림 전진 1.0 | 켬 - 가림 | 켬 좌/우 추종 | 가림 좌/우 추종 |")
print("|---|---|---|---|---|---|---|")
for name, lv in SRC.items():
    for lvl, d in lv.items():
        r = json.loads((d / "map_modes.json").read_text(encoding="utf-8"))
        fl = r.get("fixed_terrain", {}).get("fixed_level")
        m = r["modes"]
        on = m.get("eval_gt") or m.get("none"); off = m.get("probe_prop_only")
        f = lambda x: f"{x['fwd1.0']['body_vx_integral_median_m']:.2f} ({x['fwd1.0']['alive_envs_at_end']})"
        s = lambda x: f"{x['spin+1.2']['yaw_follow_median']:.2f}/{x['spin-1.2']['yaw_follow_median']:.2f}"
        diff = f"{on['fwd1.0']['body_vx_integral_median_m'] - off['fwd1.0']['body_vx_integral_median_m']:+.2f}" if off else "-"
        print(f"| {name} | {lvl} (기록 {fl}) | {f(on)} | {f(off) if off else '-'} | {diff} | {s(on)} | {s(off) if off else '-'} |")
        out[f"{name}|{lvl}"] = {"on": on["fwd1.0"], "off": off["fwd1.0"] if off else None, "fixed_level": fl}
Path(__file__).with_name("hardlevel_table.json").write_text(json.dumps(out, indent=1, default=float), encoding="utf-8")
