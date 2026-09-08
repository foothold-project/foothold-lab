import json, glob, os

O = os.environ.get("GAP_OUT", "")
if not O:
    raise SystemExit("GAP_OUT 에 결과 폴더를 지정해야 한다. 예: export GAP_OUT=<볼륨>/experiments/20260907_gap-threshold")
print("cfg | hs | gap의도m | gap_px | gap실현m | 측정run_px | 돌_px | 돌실현m | 격자px | 경계x | 끝x | 판침범 | 무구멍차선 | 차선최소구멍 | 판0 | 돌높이[min,max] | 관문")
for p in sorted(glob.glob(os.path.join(O, "audit_*.json"))):
    a = json.load(open(p)); s = a["structure"]; g = s["geometry"]; w = a["worst"]
    gate = "OK" if not a.get("gate_failures") else "FAIL:" + ";".join(a["gate_failures"])
    if a.get("gate_note"): gate += " (틈0: 차선검사 해당없음)"
    print(" | ".join(str(v) for v in (
        os.path.basename(p)[6:-5], g["horizontal_scale_m"], g["intended_gap_m"],
        g["realized_gap_px"], g["realized_gap_m"], g["measured_hole_run_px_mode"],
        g["realized_stone_width_px"], g["realized_stone_width_m"],
        s["grid_pixels"][0], s["boundary_x_m"], s["end_x_m"],
        w["cells_on_platform_max"], w["lanes_without_any_hole_max"], w["holes_per_lane_min"],
        w["platform_all_zero_all"], a["per_seed"][0]["stone_height_range_m"], gate)))
