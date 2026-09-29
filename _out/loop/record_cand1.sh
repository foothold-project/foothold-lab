#!/usr/bin/env bash
# 후보1 영상 · «놀란 자리» 만 찍는다 (분기표 자동 실행 규칙 4)
#
# 작성: 오흥재 · 2026-09-24
# 근거: sim/eval/results/20260911-v1-clips/*/`*.json` 의 argv 형식
# 요지: v2b-r iter2500 의 최저 칸과 뜻밖의 칸만 찍는다. 전부 찍지 않는다.
set -u
PY="C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe"
CK="C:/isaac/IsaacLab/logs/rsl_rl/unitree_go2_gap_nvidia/2026-09-23_14-42-33_20260923_v2b-r_seed42_iter3000/model_2500.pt"
OUT="sim/eval/results/20260924-cand1-clips"
export OMNI_KIT_ACCEPT_EULA=YES

# 이름 | 지형 | 난이도 | 속도 | 왜 찍나
CLIPS=(
  "stepping_stones|stepping_stones|0.5|1.0|절대 최저 칸 · 0 %. 무엇이 안 되는지 눈으로 본다"
  "rails-fast|rails|0.5|1.5|배포본 21 % 를 91 % 로 올린 칸"
  "gap-slow|gap|0.5|0.5|iter1500 에서 떨어졌던 칸 (2500 은 98 %)"
  "floating_ring-easy|floating_ring|0.1|1.5|난이도 0.1 인데 1 % · «단조롭지 않다»"
  "backward|gap|0.5|-1.0|후진 명령 · 생존은 하는데 안 물러난다"
)

for spec in "${CLIPS[@]}"; do
  IFS='|' read -r name terrain diff vx why <<< "$spec"
  for view in track_side track_high; do
    d="$OUT/$name-$view"
    [ -f "$d/flat_army_A_1_$view.mp4" ] && { echo "건너뜀 $name-$view"; continue; }
    mkdir -p "$d"
    echo "# $why" > "$d/why.txt"
    echo "찍는 중 $name $view ($why)"
    "$PY" sim/eval/record_terrain_demo.py \
      --checkpoint "$CK" --output_dir "$d" \
      --terrain "$terrain" --difficulty "$diff" \
      --cut A --view "$view" \
      --num_envs 1 --columns 1 --rows 1 --spacing 3.0 \
      --width 1280 --height 720 \
      --eval_duration 6 --command_vx "$vx" \
      > "$d/run.log" 2>&1 || echo "  «실패» exit=$?"
  done
done
echo "끝. 깨짐 검사로 넘어간다"
# video_check.py 는 라이브러리라 CLI 가 없다. verify_render 를 부른다.
# **찍은 것을 «전부» 검사한다.** 2026-09-20 에 새 영상만 검사해서
# 이미 올라가 있던 깨진 영상을 사흘 못 잡았다.
"$PY" - "$OUT" <<'PYEOF'
import os, sys
sys.path.insert(0, "sim/eval")
from video_check import verify_render
root = sys.argv[1]
ok = bad = 0
for dirpath, _, files in os.walk(root):
    for f in files:
        if not f.endswith(".mp4"):
            continue
        p = os.path.join(dirpath, f)
        log = os.path.join(dirpath, "run.log")
        try:
            verify_render(p, log_path=log if os.path.isfile(log) else None)
            ok += 1
            print("  통과 %s" % p)
        except Exception as e:
            bad += 1
            print("  «막힘» %s
    %s" % (p, e))
print("영상 검사 · 통과 %d · 막힘 %d" % (ok, bad))
sys.exit(1 if bad else 0)
PYEOF
