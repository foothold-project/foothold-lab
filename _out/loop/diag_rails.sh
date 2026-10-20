#!/usr/bin/env bash
# rails 가 왜 0 인지 «난이도 축 하나만» 흔들어 본다.
#
# 분류: 진단
# 작성: 오흥재 · 2026-09-28
# 근거: 팀장 지시 「rails 가 왜 0인지 따로 봐」
# 묻는 것: fs1 이 rails 를 «못 넘는» 것인가, «안 가는» 것인가.
#   난이도를 0.5 에서 0.05 까지 내린다. 턱 높이가 0.115 m -> 0.056 m 로 낮아진다
#   (`mesh_terrains.py:401` rail_height = 0.05 + d x 0.13).
#   낮춰도 안 가면 턱 높이가 아니라 «출발을 안 하는 것» 이다.
#
# 다른 칸은 야간 하네스와 «한 칸도» 다르지 않게 둔다 (v1.0 칸 그대로).
#   command_vx 1.0 · eval_duration 6.0 · min_progress_m 3.0
#   max_lateral_drift 0.75 · seed 42 · envs_per_terrain 10
# 에피소드만 100 -> 30 으로 줄인다. 이건 진단이고 판정이 아니다.
set -u
cd "$(dirname "$0")/../.." || exit 1
PY=C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe
LOGS=C:/isaac/IsaacLab/logs/rsl_rl/unitree_go2_gap_nvidia
OUT=_out/loop/diag-rails
DEV=cuda:0
export OMNI_KIT_ACCEPT_EULA=YES   # eval_runner.py:270 과 같은 칸. 없으면 EOF 로 죽는다

declare -a CK=(
  "fs1@2500|$LOGS/2026-09-28_01-04-22_20260928_fs1-scratch-f001/model_2500.pt"
  "fs1@3000|$LOGS/2026-09-28_01-04-22_20260928_fs1-scratch-f001/model_3000.pt"
  "v2g2@3000|$LOGS/2026-09-25_17-29-36_20260925_v2g2-feetair01_seed42_iter3000/model_3000.pt"
)
for D in 0.05 0.15 0.30 0.50; do
  for row in "${CK[@]}"; do
    lab="${row%%|*}"; ckpt="${row##*|}"
    tag="$(echo "$lab" | tr '@' '-')-d$D"
    odir="$OUT/$tag"
    if [ -f "$odir/generalization_summary.csv" ]; then
      echo "[$(date +%H:%M:%S)] 건너뜀 (이미 있음) $tag"; continue
    fi
    if [ ! -f "$ckpt" ]; then
      echo "[$(date +%H:%M:%S)] ** 체크포인트 없음 ** $ckpt"; continue
    fi
    echo "[$(date +%H:%M:%S)] $tag 시작"
    "$PY" sim/eval/eval_generalization.py \
      --checkpoint "$ckpt" \
      --terrain_set unseen10 --terrains rails \
      --difficulty "$D" \
      --episodes 30 --envs_per_terrain 10 \
      --command_vx 1.0 --eval_duration 6.0 \
      --min_progress_m 3.0 --max_lateral_drift 0.75 \
      --seed 42 --headless --device "$DEV" \
      --note "진단 · rails 난이도 축 · 팀장 지시" \
      --output_dir "$odir" > "$OUT/$tag.log" 2>&1
    RC=$?
    if [ -f "$odir/generalization_summary.csv" ]; then HAVE="산출물 있음"; else HAVE="** 산출물 없음 **"; fi
    echo "[$(date +%H:%M:%S)] $tag exit=$RC · $HAVE"
  done
done
echo "[$(date +%H:%M:%S)] 끝"
