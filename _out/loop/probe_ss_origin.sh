#!/usr/bin/env bash
# `stepping_stones` 에서 «출발 자리» 가 결과를 가르는지 한 번에 가른다.
#
# 분류: 진단
# 작성: 오흥재 · 2026-09-29
# 근거: 스윕 100 판의 전진 중앙값 2.71 m · 3 m 넘음 45 % 인데, 같은 잣대로
#       찍은 내 컷 12 판은 중앙값 0.89 m · 3 m 넘음 0 개였다. 스윕의
#       «최솟값» 0.96 m 이 내 «중앙값» 보다 크다
# 요지: 한 가설만 본다. 「8x8 격자의 모서리 칸이 유난히 어렵다」
#
# ## 무엇이 이미 같은가 (전부 확인함)
#
#   통과선 3.0 m · 시간 6.0 초 · 스폰 ±0.10 m · 요 ±5 도
#   gap_aware_scan True · height_scan_miss_value 1.0
#   difficulty_range [0.5, 0.5] · dt 0.02 · eval_spec_version 2
#   체크포인트 파일 같음
#
# ## 남은 차이 하나
#
# 녹화기는 지형 하나로 걸러 **8x8 격자**를 만들고 env 1 개를 칸 (0,0) 에
# 놓는다. 그 자리는 **(-28, -28)** 로 격자의 모서리다 `확인됨`.
#
# 스윕은 지형마다 env 10 개이고 그 env 별 전진 중앙값이 2.43 ~ 5.42 m 로
# 갈린다. **자리에 따라 난이도가 크게 다르다는 뜻이다.**
#
# 격자를 1x1 로 두면 칸 중심이 지형 중심 (0, 0) 이 된다. 자리가 바뀐다.
#
#   거리가 2 ~ 5 m 대로 오르면   자리 탓이다. 그 규격으로 컷을 다시 찍는다
#   그대로 1 m 아래면           자리 탓이 아니다. 열어 둔 물음으로 남긴다
#
# **한 실험에 한 가설이다.** 시드는 8x8 회차와 «같은 셋» 을 쓴다.
set -u
cd "$(dirname "$0")/../.." || exit 1

PY=C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe
L=C:/isaac/IsaacLab/logs/rsl_rl/unitree_go2_gap_nvidia
V2=$L/2026-09-25_17-29-36_20260925_v2g2-feetair01_seed42_iter3000/model_3000.pt
OUT=sim/eval/results/20260929-ss-origin
DEV="${SHOT_DEV:-cuda:0}"
export OMNI_KIT_ACCEPT_EULA=YES
export KMP_DUPLICATE_LIB_OK=TRUE

say() { echo "[$(date +%H:%M:%S)] $*"; }
[ -f "$V2" ] || { say "** 체크포인트 없음 **"; exit 1; }

mkdir -p "$OUT"

for seed in 42 43 44; do
  o="$OUT/rows1-s$seed"
  mkdir -p "$o"

  "$PY" sim/eval/record_terrain_demo.py \
    --checkpoint "$V2" --output_dir "$o" \
    --terrain stepping_stones --terrain_set unseen10 --difficulty 0.5 \
    --terrain_rows 1 --terrain_cols 1 \
    --cut A --view track_high --title "v2 · stepping_stones · 1.0 m/s" \
    --num_envs 1 --columns 1 --rows 1 --spacing 3.0 \
    --width 1280 --height 720 --seed "$seed" \
    --eval_duration 6.0 --command_vx 1.0 \
    --trace_csv "$o/trace.csv" \
    --gate_m 3.0 --max_lateral_drift 0.75 --max_velocity_mae 0.25 \
    --preset medium --crf 26 --device "$DEV" > "$o/render.log" 2>&1

  if [ ! -f "$o/trace.csv" ]; then
    say "  시드 $seed · ** trace 없음 ** · $(grep -oE '(RuntimeError|ValueError|SystemExit):.*' "$o/render.log" 2>/dev/null | tail -1 | cut -c1-80)"
    continue
  fi

  say "  시드 $seed · $("$PY" - "$o/trace.csv" "$o/render.log" <<'PYJ'
import csv
import io
import re
import sys

rows = [l for l in io.open(sys.argv[1], encoding="utf-8") if not l.startswith("#")]
fwd = [float(r["fwd_m"]) for r in csv.DictReader(rows) if r.get("fwd_m")]

place = "?"
for line in io.open(sys.argv[2], encoding="utf-8", errors="replace"):
    m = re.search(r"\[지형\].*x (-?[\d.]+)~(-?[\d.]+) y (-?[\d.]+)~(-?[\d.]+)", line)
    if m:
        place = "(%s, %s)" % (m.group(1), m.group(3))

print("전진 %.2f m · %s · 자리 %s"
      % (fwd[-1] if fwd else 0.0,
         "pass" if fwd and fwd[-1] >= 3.0 else "fail", place))
PYJ
)"
done

say "끝 · 8x8 회차는 0.86 / 0.89 / 2.09 m 였다 (같은 시드 셋)"
