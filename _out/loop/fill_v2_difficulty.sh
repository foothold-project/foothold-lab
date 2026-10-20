#!/usr/bin/env bash
# v2 (v2g2 @3000) 의 난이도 축에서 «빈 칸» 셋을 채운다.
#
# 분류: 운영
# 작성: 오흥재 · 2026-09-28
# 근거: 팀장 지시 「v2g2 3000 에 대해서도 속도3, 지형, 난이도 등에 대해서 스윕표가 필요」
# 요지: v2 는 d0.1 0.3 0.5 0.7 0.9 를 가졌고 기준선 `foothold-v1` 은
#       d0.1 ~ d0.7 을 0.1 간격으로 가졌다. 겹치는 것이 넷뿐이라
#       난이도 곡선을 나란히 못 그린다. **0.2 · 0.4 · 0.6 을 채운다.**
#       그러면 일곱 점에서 v1 과 v2 가 같은 눈금으로 선다.
#
# 조건은 이미 있는 스윕과 «한 칸도» 다르지 않게 둔다.
#   `20260924-observe/sweep/.../run_manifest.json` 에서 읽은 값 그대로다.
#   episodes 100 · envs_per_terrain 10 · min_progress 3.0 · drift 0.75
#   seed 42 · 속도마다 창 12 / 6 / 4 초 (명령 거리 6 m)
#
# 장치는 `cuda:0` 이다. 기존 스윕도 `cuda:0` 에서 쟀다 (manifest 의 device).
# GPU 효과는 0 으로 측정됐지만 (v2b-r 대 v2b-p11 · 121 개 전수) 그래도
# **같은 장치를 쓴다.** 재는 조건을 굳이 하나 더 벌릴 이유가 없다.
set -u
cd "$(dirname "$0")/../.." || exit 1
PY=C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe
CK=C:/isaac/IsaacLab/logs/rsl_rl/unitree_go2_gap_nvidia/2026-09-25_17-29-36_20260925_v2g2-feetair01_seed42_iter3000/model_3000.pt
OUT=sim/eval/results/20260924-observe/sweep/v2g2-feetair01-iter3000
DEV=cuda:0
export OMNI_KIT_ACCEPT_EULA=YES

[ -f "$CK" ] || { echo "** 체크포인트 없음 ** $CK"; exit 1; }

for D in 0.2 0.4 0.6; do
  for TS in rough6 unseen10; do
    for pair in "0.5 12.0" "1.0 6.0" "1.5 4.0"; do
      set -- $pair; VX=$1; DUR=$2
      odir="$OUT/$TS/d$D/v$VX"
      if [ -f "$odir/generalization_summary.csv" ]; then
        echo "[$(date +%H:%M:%S)] 건너뜀 d$D $TS v$VX"; continue
      fi
      echo "[$(date +%H:%M:%S)] d$D $TS v$VX 시작"
      "$PY" sim/eval/eval_generalization.py \
        --checkpoint "$CK" \
        --terrain_set "$TS" --terrains all \
        --difficulty "$D" \
        --episodes 100 --envs_per_terrain 10 \
        --command_vx "$VX" --eval_duration "$DUR" \
        --min_progress_m 3.0 --max_lateral_drift 0.75 \
        --seed 42 --headless --device "$DEV" \
        --note "v2 난이도 축 빈 칸 채우기 · 기준선 foothold-v1 과 같은 일곱 점으로" \
        --output_dir "$odir" > "$OUT/fill-d$D-$TS-v$VX.log" 2>&1
      RC=$?
      if [ -f "$odir/generalization_summary.csv" ]; then H="산출물 있음"; else H="** 산출물 없음 **"; fi
      echo "[$(date +%H:%M:%S)] d$D $TS v$VX exit=$RC · $H"
    done
  done
done
echo "[$(date +%H:%M:%S)] 끝. 표를 다시 굽는다"
"$PY" _out/loop/v2_sweep.py --out sim/eval/results/20260928-v2-sweep
