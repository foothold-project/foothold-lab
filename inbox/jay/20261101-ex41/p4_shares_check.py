"""P4 대조: 실행 YAML 의 좌 = 우 몫 · 실제 env.yaml 의 리셋 yaw 범위 · 정사각 타일 · 점수표 좌우 부호 뒤집힘.

사용: python -X utf8 p4_shares_check.py [ex41-fixed5000.yaml] [env.yaml] [scores-b 폴더]
종료 0 = 문서 §2 · §3 의 사실이 그대로 · 1 = 어긋남 · 2 = 입력 없음.
- YAML: 모든 단계(S2a~T0_prime 여섯)의 shares 에서 *_left == *_right 이고 side 는 0.06(S2a · S2b) → 0.07.
- env.yaml: reset_base.pose_range.yaw == (-3.14, 3.14), terrain size 8 x 8, pyramid_stairs size 8 x 8.
- scores-b: m4500 이상 저장본의 옆 걸음 vy 오차(우 − 좌) 부호가 정답 · 끔 모두 양쪽으로 나온다(뒤집힘).
"""
import glob
import json
import os
import re
import sys
from pathlib import Path

import yaml

yml = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("D:/mai-wt/foothold-lab/analyst-ex41-score-name-1102/foothold_s2/curriculum/ex41-fixed5000.yaml")
envy = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("C:/Users/AI-WS01/s2_lab/ex40_main_20261031_041313/main/EX-40-B-main_20261031_041337_26240/params/env.yaml")
scores = Path(sys.argv[3]) if len(sys.argv) > 3 else Path("C:/Users/AI-WS01/s2_lab/ex40_main_20261031_041313/scores-b")
for p in (yml, envy, scores):
    if not p.exists():
        print("없음:", p)
        sys.exit(2)

bad = 0
def ok(cond, label):
    global bad
    print(("ok  " if cond else "MISS") + " " + label)
    bad += 0 if cond else 1

# 1. YAML 좌 = 우
d = yaml.safe_load(yml.read_text(encoding="utf-8"))
stages = d.get("stages") or []
ok(len(stages) >= 6, f"단계 수 {len(stages)} ≥ 6")
side_seq = []
for s in stages:
    sh = s.get("shares") or {}
    sid = s.get("id") or s.get("name") or "?"
    for key in ("side", "walk", "spin", "diag_fwd", "diag_back"):
        l, r = sh.get(f"{key}_left"), sh.get(f"{key}_right")
        ok(l is not None and l == r, f"{sid} {key} 좌 {l} = 우 {r}")
    side_seq.append(sh.get("side_left"))
ok(side_seq[:2] == [0.06, 0.06] and all(v == 0.07 for v in side_seq[2:]), f"side 몫 순서 {side_seq} = 0.06 x2 → 0.07")

# 2. env.yaml (python 태그는 Loader 로 튜플 복원)
class L(yaml.SafeLoader):
    pass
L.add_constructor("tag:yaml.org,2002:python/tuple", lambda ld, node: tuple(ld.construct_sequence(node)))
L.add_multi_constructor("tag:yaml.org,2002:python/", lambda ld, suffix, node: None)
e = yaml.load(envy.read_text(encoding="utf-8"), Loader=L)
pr = e["events"]["reset_base"]["params"]["pose_range"]
ok(tuple(pr["yaw"]) == (-3.14, 3.14), f"reset yaw {pr['yaw']}")
ok(tuple(pr["x"]) == (-0.5, 0.5) and tuple(pr["y"]) == (-0.5, 0.5), f"reset x {pr['x']} y {pr['y']}")
tg = e["scene"]["terrain"]["terrain_generator"]
ok(tuple(tg["size"]) == (8.0, 8.0), f"타일 {tg['size']}")
ps = tg["sub_terrains"]["pyramid_stairs"]
ok(tuple(ps["size"]) == (8.0, 8.0) and ps["platform_width"] == 3.0, f"pyramid_stairs size {ps['size']} platform {ps['platform_width']}")

# 3. 점수표 부호 뒤집힘
files = sorted(glob.glob(os.path.join(scores, "score_*_*.json")), key=lambda p: int(re.search(r"score_(\d+)_", p).group(1)))
signs = {"eval_gt": [], "probe_prop_only": []}
for p in files:
    it = int(re.search(r"score_(\d+)_", p).group(1))
    if it < 4500:
        continue
    c = json.load(open(p, encoding="utf-8-sig"))["cells"]
    for mode in signs:
        a, b = c.get(f"{mode}/side+0.5"), c.get(f"{mode}/side-0.5")
        if not a or not b:
            continue
        diff = b["tracking_medians"]["vy_abs_error_mean_alive_mps"] - a["tracking_medians"]["vy_abs_error_mean_alive_mps"]
        signs[mode].append((it, 1 if diff > 0 else -1))
for mode, rows in signs.items():
    neg = sum(1 for _, s in rows if s < 0); pos = len(rows) - neg
    ok(neg > 0 and pos > 0 and len(rows) >= 10, f"{mode} 옆 걸음 우−좌 부호: 음(좌 나쁨) {neg} · 양(우 나쁨) {pos} · 저장본 {len(rows)}")
print(("ok" if bad == 0 else "FAIL") + f" 어긋남 {bad}")
sys.exit(0 if bad == 0 else 1)
