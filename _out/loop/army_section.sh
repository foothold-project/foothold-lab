#!/usr/bin/env bash
# 「한 섹션 확대 컷」 한 편.
#
# 분류: 운영
# 작성: 오흥재 · 2026-09-28
# 근거: 팀장 작업 목록 3 「한 섹션 확대 컷」
# 요지: 전체 컷은 로봇이 점이다. 한 마리를 크게 본다
#
# **이 파일을 도는 중에 고치지 않는다.**
#
# ## 1 차에서 무엇이 틀렸나
#
# `--view macro --terrain_rows 8 --terrain_cols 8 --num_envs 32` 로 찍었다.
# 10 초짜리가 나왔고 종료 코드도 0 이었는데 **로봇이 지평선의 흰 점**이었다.
# 로봇 원점은 세계 원점(0,0)인데 지형 상자 중심은 cx = -12 다 (trace 실측).
# 지형을 키울수록 무리가 화면 밖으로 밀린다. HUD 도 없었다.
#
# 그래서 갤러리 48 칸과 **같은 길**로 간다. `track_side` 는 로봇을 따라가므로
# 지형 상자가 어디 있든 틀이 맞는다. HUD 는 `overlay/render.py` 로 따로 건다.
set -u
cd "$(dirname "$0")/../.." || exit 1
PY=C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe
L=C:/isaac/IsaacLab/logs/rsl_rl/unitree_go2_gap_nvidia
CK=$L/2026-09-25_17-29-36_20260925_v2g2-feetair01_seed42_iter3000/model_3000.pt
OD=sim/eval/results/20260928-v2-clips/army-section
export OMNI_KIT_ACCEPT_EULA=YES
export KMP_DUPLICATE_LIB_OK=TRUE

say() { echo "[$(date +%H:%M:%S)] $*"; }
[ -f "$CK" ] || { say "** 체크포인트 없음 **"; exit 1; }

rm -rf "$OD"; mkdir -p "$OD"
NAME=army-section

say "촬영 · random_rough d0.5 · 10 초 · track_side"
"$PY" sim/eval/record_terrain_demo.py \
  --checkpoint "$CK" --output_dir "$OD" \
  --terrain random_rough --terrain_set rough6 --difficulty 0.5 \
  --cut A --view track_side --title "v2 · one section" \
  --num_envs 1 --columns 1 --rows 1 --spacing 3.0 \
  --width 1920 --height 1080 \
  --eval_duration 10.0 --command_vx 1.0 --gate off \
  --trace_csv "$OD/$NAME.trace.csv" \
  --preset slow --crf 20 > "$OD/1-record.log" 2>&1
rc=$?

RAW=$(ls "$OD"/*.mp4 2>/dev/null | grep -v '\.hud\.mp4$' | head -1)
if [ -z "$RAW" ] || [ ! -f "$OD/$NAME.trace.csv" ]; then
  say "** 촬영이 산출물을 안 남겼다 ** exit=$rc"
  grep -oE '(RuntimeError|ValueError|SystemExit|Error):.*' "$OD/1-record.log" 2>/dev/null | tail -1
  exit 1
fi

say "HUD"
"$PY" sim/eval/overlay/render.py \
  --video "$RAW" --trace "$OD/$NAME.trace.csv" \
  --out "$OD/$NAME.hud.mp4" --preset slow > "$OD/2-hud.log" 2>&1

if [ -f "$OD/$NAME.hud.mp4" ]; then
  say "산출물 있음 · $(ls -l "$OD/$NAME.hud.mp4" | awk '{printf "%.1f MB", $5/1048576}')"
else
  say "** HUD 가 안 붙었다 **"; exit 1
fi
say "끝"
