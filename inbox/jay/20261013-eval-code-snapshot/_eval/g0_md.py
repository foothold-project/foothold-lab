# G0 tables from out/G0-fixture.json and out/g0_probe/{G0-results.json, meta.json}.
# Usage: python g0_md.py > out/G0-tables.md
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
fx = json.load(open(os.path.join(HERE, "out", "G0-fixture.json")))
res = json.load(open(os.path.join(HERE, "out", "g0_probe", "G0-results.json")))
meta = json.load(open(os.path.join(HERE, "out", "g0_probe", "meta.json")))
names = {"flat": "평지", "step_up_0.2": "0.2 m 올라간 단차", "step_down_0.2": "0.2 m 내려간 단차", "wall_1.0": "1.0 m 높이 면",
         "deep_finite_hole_-10": "바닥이 10 m 아래인 구멍 (finite)", "no_hit_inf": "no-hit (inf)", "nan": "NaN",
         "all_invalid_inf": "전체 no-hit", "all_invalid_nan": "전체 NaN", "minus_inf": "-inf (레이캐스터는 내지 않음)"}

print("### 표 1 · CPU fixture · 몸통 0.38 m · 레이 셋 (hit z → legacy · G0 최종 출력)\n")
print("| 경우 | hit z | legacy | G0 |")
print("|---|---|---|---|")
for k, v in fx["cases"].items():
    fmt = lambda xs: " · ".join("NaN" if x != x else f"{x:+.2f}" for x in xs)  # noqa: E731
    print(f"| {names.get(k, k)} | {' · '.join(v['hit_z'])} | {fmt(v['legacy'])} | {fmt(v['g0'])} |")
print()

print("### 표 2 · GPU 실제 대조 · 지형 열별 no-hit 레이 (레이 x, y 로 tile 을 정함)\n")
print("| 열 | 학습 비중 | 레이 수 | no-hit 합계 | 메시 안 구멍 (CPU 레이도 못 맞힘) | 메시 표면이 있는데 GPU 만 놓침 | 메시 밖 |")
print("|---|---|---|---|---|---|---|")
train = set(meta["families"]) - set(meta["eval_only_columns"])
for f, v in res["miss_by_family"].items():
    tot = v["hole_in_mesh"] + v["mesh_surface_but_gpu_missed"] + v["outside_mesh"]
    w = "학습 지형" if f in train else ("평가 전용 열" if f in meta["eval_only_columns"] else "tile 격자 밖 (25 m 테두리와 그 너머)")
    print(f"| {f} | {w} | {v['rays_in_family']:,} | {tot:,} | {v['hole_in_mesh']:,} | {v['mesh_surface_but_gpu_missed']:,} | {v['outside_mesh']:,} |")
print()

print("### 표 3 · gap 열의 no-hit 위치 · 행별 (tile 중심에서 체비쇼프 거리 · platform 반폭 "
      f"{res['gap_platform_half_m']} m)\n")
print("| 행 (난이도 구간) | no-hit 레이 | 거리 최소 m | 거리 최대 m | 레이 격자로 본 gap 폭 하한 m |")
print("|---|---|---|---|---|")
for rr, v in res["gap_rows"].items():
    if v["n_miss_rays"]:
        w = v["cheb_max_m"] - res["gap_platform_half_m"]
        print(f"| {rr} ({int(rr) / 10:.1f}~{(int(rr) + 1) / 10:.1f}) | {v['n_miss_rays']:,} | {v['cheb_min_m']:.2f} | {v['cheb_max_m']:.2f} | {w:.2f} |")
    else:
        print(f"| {rr} | 0 | - | - | - |")
print()

pc = res["positive_control"]
print("### 표 4 · GPU 대조의 판정과 점검\n")
print("| 항목 | 기대 | 결과 |")
print("|---|---|---|")
rows = [
    ("레이 수 · no-hit (inf) · NaN", "-", f"{res['rays_total']:,} · {res['inf']:,} · {res['nan']:,}"),
    ("finite hit 에서 legacy 대 G0 최대 차", "≤ 1e-6", f"{res['finite_legacy_vs_g0_max_abs']:.3g}"),
    ("no-hit 의 legacy 값", "(반전이면 -2.5)", ", ".join(f"{x:+.2f}" for x in res["nohit_legacy_values"])),
    ("no-hit 의 G0 값", "+2.5", ", ".join(f"{x:+.2f}" for x in res["nohit_g0_values"])),
    ("G0 비유한 출력", "0", f"{res['g0_nonfinite_outputs']}"),
    ("legacy 비유한 출력 (NaN 입력이 없어서)", "-", f"{res['legacy_nonfinite_outputs']}"),
    ("finite hit 가운데 legacy 가 -2.5 · +2.5 로 포화된 레이", "-", f"{res['finite_rays_at_legacy_minus_2p5']} · {res['finite_rays_at_legacy_plus_2p5']}"),
    ("내 legacy 식 대 실제 ObservationManager critic height block", "0", f"{meta['my_legacy_formula_vs_pipeline_max_abs']:.3g}"),
    ("양성 대조: GPU hit 표본을 CPU (trimesh) 로 다시 쏨", "모두 hit · 높이 차 작음", f"{pc['cpu_hit']} / {pc['n']} hit · 최대 높이 차 절대값 {pc['max_abs_dz_m']:.2g} m"),
    ("메시 밖 no-hit 이 시작되는 거리 (tile 격자 끝에서)", f"테두리 {res['border_width_m']} m 너머", f"{res['outside_grid_miss_min_distance_beyond_grid_m']:.2f} m (테두리 위 hit 는 {res['outside_grid_hit_max_distance_beyond_grid_m']:.2f} m 까지)"),
    ("stepping_stones 열의 no-hit · 10 m 아래 hit", "-", f"{res['stepping_stones']['miss']} · {res['stepping_stones']['finite_hits_below_minus_5m']}"),
]
for a, b, c in rows:
    print(f"| {a} | {b} | {c} |")
print()
