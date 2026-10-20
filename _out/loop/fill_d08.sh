#!/usr/bin/env bash
# 난이도 0.8 을 «두 판 다» 잰다. 곡선의 구멍을 메운다.
#
# 분류: 운영
# 작성: 오흥재 · 2026-09-28
# 근거: 팀장 지적 「어떤 도식화 그래프는 왜 0.8 수치 없는거야?」
# 요지: 0.8 은 v1 스윕에도 v2 스윕에도 없다. 곡선이 0.7 과 0.9 를 곧은 선으로
#       이어서 **안 잰 값을 잰 것처럼** 보이게 했다. 실제로 잰다.
#
# **이 파일을 도는 중에 고치지 않는다.** bash 가 조금씩 읽어 오프셋이 밀린다.
#
# ## 지금 있는 난이도
#
#   v1   0.1 0.2 0.3 0.4 0.5 0.6 0.7     0.9      <- 0.8 만 없다
#   v2   0.1 0.2 0.3 0.4 0.5 0.6 0.7     0.9      <- 0.8 만 없다
#   NV                   0.5                      <- 한 점만 있다
#
# **NVIDIA 는 안 잰다.** 기준선 난이도 곡선은 이번 판정 범위 밖이고, 한 점
# 자료를 여덟 점으로 늘리는 것은 이 지적이 요구한 일이 아니다. 곡선 그림도
# NVIDIA 를 «이 한 점만 쟀다» 로 적어 둔다.
#
# ## 조건은 기존 칸과 한 글자도 안 바꾼다
#
# `fill_v2_difficulty.sh` 가 0.2 · 0.4 · 0.6 을 채울 때 쓴 것과 같다.
# 하나라도 다르면 0.8 만 다른 자로 잰 칸이 되어 곡선에 섞을 수 없다.
#
#   episodes 100 · envs_per_terrain 10 · min_progress 3.0 · drift 0.75
#   seed 42 · 속도마다 시간 (0.5 -> 12.0 · 1.0 -> 6.0 · 1.5 -> 4.0)
#
# 칸 수는 판 둘 x 집합 둘 x 속도 셋 = 12 칸이다.
set -u
cd "$(dirname "$0")/../.." || exit 1
PY=C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe
L=C:/isaac/IsaacLab/logs/rsl_rl/unitree_go2_gap_nvidia
DEV="${FILL_DEV:-cuda:0}"
export OMNI_KIT_ACCEPT_EULA=YES

V2CK=$L/2026-09-25_17-29-36_20260925_v2g2-feetair01_seed42_iter3000/model_3000.pt
V1CK=models/foothold-v1.pt

V2OUT=sim/eval/results/20260924-observe/sweep/v2g2-feetair01-iter3000
V1OUT=sim/eval/results/maindata-v1/foothold-v1

say() { echo "[$(date +%H:%M:%S)] $*"; }
for f in "$V2CK" "$V1CK"; do
  [ -f "$f" ] || { say "** 체크포인트 없음 ** $f"; exit 1; }
done

D=0.8
done_n=0
fail_n=0

for row in "v2|$V2CK|$V2OUT" "v1|$V1CK|$V1OUT"; do
  who="${row%%|*}"; rest="${row#*|}"; CK="${rest%%|*}"; OUT="${rest##*|}"

  for TS in rough6 unseen10; do
    for pair in "0.5 12.0" "1.0 6.0" "1.5 4.0"; do
      set -- $pair; VX=$1; DUR=$2

      # v1 쪽은 1.0 을 `v1` 로 적는다 (기존 폴더 이름 규칙 그대로).
      VDIR="v$VX"
      if [ "$who" = "v1" ] && [ "$VX" = "1.0" ]; then VDIR="v1"; fi

      odir="$OUT/$TS/d$D/$VDIR"
      if [ -f "$odir/generalization_summary.csv" ]; then
        say "건너뜀 (이미 있음) $who $TS $VDIR"; done_n=$((done_n+1)); continue
      fi

      say "$who · d$D · $TS · $VX m/s 시작"
      "$PY" sim/eval/eval_generalization.py \
        --checkpoint "$CK" \
        --terrain_set "$TS" --terrains all \
        --difficulty "$D" \
        --episodes 100 --envs_per_terrain 10 \
        --command_vx "$VX" --eval_duration "$DUR" \
        --min_progress_m 3.0 --max_lateral_drift 0.75 \
        --seed 42 --headless --device "$DEV" \
        --note "난이도 0.8 · 곡선의 구멍을 메운다 · 조건은 0.2/0.4/0.6 칸과 같다" \
        --output_dir "$odir" > "$OUT/fill-d$D-$TS-$VDIR.log" 2>&1
      rc=$?

      if [ -f "$odir/generalization_summary.csv" ]; then
        say "  exit=$rc · 산출물 있음"; done_n=$((done_n+1))
      else
        say "  exit=$rc · ** 산출물 없음 **"; fail_n=$((fail_n+1))
        grep -oE '(RuntimeError|ValueError|SystemExit|Error):.*' \
          "$OUT/fill-d$D-$TS-$VDIR.log" 2>/dev/null | tail -1 | cut -c1-96
      fi
    done
  done
done

say "찬 칸 $done_n · 못 채운 칸 $fail_n (기대 12)"
say "표를 다시 굽는다"
"$PY" _out/loop/v2_sweep.py --out sim/eval/results/20260928-v2-sweep 2>&1 | tail -6
say "도식을 다시 굽는다"
"$PY" tools/make_v2_figs.py --write 2>&1 | tail -6
say "끝"
