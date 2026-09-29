#!/usr/bin/env bash
# 빠져 있던 «처음부터 학습» 대조군을 잰다.
#
# 분류: 진단
# 작성: 오흥재 · 2026-09-28
# 근거: 팀장 지적 「NVIDIA 도 처음에는 1e-3 으로 1500 번 돈 거 맞잖아」
#       -> 확인했다. `go2/agents/rsl_rl_ppo_cfg.py:33` learning_rate=1.0e-3 이다.
#       그러면 fs1/fs2 의 lr 1e-3 은 NVIDIA 의 «처음부터» 값과 같다.
#       1e-4 는 우리가 resume 용으로 낮춘 값이다 (`gap_ppo_cfg.py:20`).
# 묻는 것: 처음부터 학습이 «환경 때문에» 늦은 것인가.
#   `unitree_go2_rough/2026-08-11_20-32-58` 은 NVIDIA 설정 그대로 처음부터
#   1499 회 돈 «우리» 실행이다 (resume false · lr 1e-3 · max_init 5 ·
#   lin_vel_x (-1,1) · rel_standing 0.02 · 지형 6 종). 4096 env · 10x20 격자.
#   이것을 우리 하네스로 재면 fs1@1500 과 «반복 수가 같은 처음부터» 대조가 된다.
#   다른 것은 «환경 하나» 다.
#
# 이 체크포인트는 지금까지 한 번도 우리 하네스로 안 쟀다. 그래서 빈 칸이었다.
# `nvidia_pretrained.pt` 는 이것과 가중치가 «다르다» (전수 대조 확인).
set -u
cd "$(dirname "$0")/../.." || exit 1
PY=C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe
CK=C:/isaac/IsaacLab/logs/rsl_rl/unitree_go2_rough/2026-08-11_20-32-58/model_1499.pt
OUT=sim/eval/results/20260928-ctrl-scratch/nvcfg-scratch-iter1500
DEV=cuda:0
export OMNI_KIT_ACCEPT_EULA=YES

[ -f "$CK" ] || { echo "** 체크포인트 없음 ** $CK"; exit 1; }
mkdir -p "$OUT"
for TS in rough6 unseen10; do
  for pair in "0.5 12.0" "1.0 6.0" "1.5 4.0"; do
    set -- $pair; VX=$1; DUR=$2
    odir="$OUT/$TS/d0.5/v$VX"
    if [ -f "$odir/generalization_summary.csv" ]; then
      echo "[$(date +%H:%M:%S)] 건너뜀 $TS v$VX"; continue
    fi
    echo "[$(date +%H:%M:%S)] $TS v$VX 시작"
    "$PY" sim/eval/eval_generalization.py \
      --checkpoint "$CK" \
      --terrain_set "$TS" --terrains all \
      --difficulty 0.5 \
      --episodes 100 --envs_per_terrain 10 \
      --command_vx "$VX" --eval_duration "$DUR" \
      --min_progress_m 3.0 --max_lateral_drift 0.75 \
      --seed 42 --headless --device "$DEV" \
      --note "대조군 · NVIDIA 설정 처음부터 1499 · 2026-08-11 실행" \
      --output_dir "$odir" > "$OUT/$TS-v$VX.log" 2>&1
    RC=$?
    if [ -f "$odir/generalization_summary.csv" ]; then H="산출물 있음"; else H="** 산출물 없음 **"; fi
    echo "[$(date +%H:%M:%S)] $TS v$VX exit=$RC · $H"
  done
done
echo "[$(date +%H:%M:%S)] 끝"
