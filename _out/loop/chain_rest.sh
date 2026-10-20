#!/usr/bin/env bash
# 지형 한 장을 확인한 뒤 «남은 것 전부» 를 순서대로 돌린다.
#
# 분류: 운영
# 작성: 오흥재 · 2026-09-28
# 근거: 팀장 지시 「갤러리 끝나면 순서대로 다 돌려」
# 요지: Isaac 은 한 판씩만 돈다. 한 줄로 이어 붙인다
#
# **이 파일을 도는 중에 고치지 않는다.**
#
# ## 차례
#
# ```
#   2    지형 나머지 15장        약 20 분
#   11   v2g2 확장 축 2         약 12 분
#   3-1  한 섹션 확대 컷          약  5 분
#   3-2  학습 진행 영상 (48.4 초)  약 20 분
# ```
#
# 각 단계는 **산출물로 성공을 판정한다.** 종료 코드를 안 믿는다.
# 한 단계가 실패해도 **멈추지 않고 다음으로 간다.** 마지막에 모아서 적는다.
set -u
cd "$(dirname "$0")/../.." || exit 1

say() { echo "[$(date +%H:%M:%S)] $*"; }
FAIL=""

# ---------------------------------------------------------------- 2 · 지형 15장
say "=== 2 · 지형 나머지 15장 ==="
cp _out/loop/shoot_terrains.sh _out/loop/.shots_running.sh
SHOT_DEV=cuda:0 bash _out/loop/.shots_running.sh 2>&1 | grep -vE "^\s*$" | tail -24
n=$(ls sim/eval/results/20260928-terrain-shots/stills/*.png 2>/dev/null | wc -l)
say "지형 스틸 $n / 16"
[ "$n" -ge 16 ] || FAIL="$FAIL 지형($n/16)"

# ---------------------------------------------------------------- 11 · 확장 축
say "=== 11 · v2g2 확장 축 2 ==="
cp _out/loop/v2g2_axis2_ext.sh _out/loop/.ext_running.sh
bash _out/loop/.ext_running.sh 2>&1 | tail -26
if [ -f sim/eval/results/20260928-v2g2-axis2-ext/v2g2-feetair01-iter3000/probe_manifest.json ]; then
  say "확장 축 산출물 있음"
else
  say "** 확장 축 산출물 없음 **"; FAIL="$FAIL 확장축"
fi

# ---------------------------------------------------------------- 3-1 · 확대 컷
say "=== 3-1 · 한 섹션 확대 컷 ==="
L=C:/isaac/IsaacLab/logs/rsl_rl/unitree_go2_gap_nvidia
CK=$L/2026-09-25_17-29-36_20260925_v2g2-feetair01_seed42_iter3000/model_3000.pt
OD=sim/eval/results/20260928-v2-clips/army-section
export OMNI_KIT_ACCEPT_EULA=YES
export KMP_DUPLICATE_LIB_OK=TRUE

if ls "$OD"/*.mp4 >/dev/null 2>&1; then
  say "건너뜀 (이미 있음)"
else
  mkdir -p "$OD"
  # 전체 컷은 로봇이 점처럼 작다. `macro` 로 한 구역만 크게 본다.
  C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe sim/eval/record_terrain_demo.py \
    --checkpoint "$CK" --output_dir "$OD" \
    --terrain random_rough --terrain_set rough6 --difficulty 0.5 \
    --terrain_rows 8 --terrain_cols 8 --max_init_level 5 \
    --cut A --view macro --title "v2 · one section" \
    --num_envs 32 --columns 8 --rows 4 --spacing 2.5 \
    --width 1920 --height 1080 \
    --eval_duration 10.0 --command_vx 1.0 --gate off \
    --preset slow --crf 20 > "$OD/render.log" 2>&1
  if ls "$OD"/*.mp4 >/dev/null 2>&1; then
    say "확대 컷 산출물 있음"
  else
    say "** 확대 컷 없음 ** · $(grep -oE '(RuntimeError|ValueError|SystemExit|Error):.*' "$OD/render.log" 2>/dev/null | tail -1 | cut -c1-84)"
    FAIL="$FAIL 확대컷"
  fi
fi

# ---------------------------------------------------------------- 3-2 · 학습 영상
say "=== 3-2 · 학습 진행 영상 ==="
cp _out/loop/train_progress.sh _out/loop/.train_running.sh
bash _out/loop/.train_running.sh 2>&1 | tail -30
if [ -f sim/eval/results/20260928-train-progress/train-progress.mp4 ]; then
  say "학습 영상 산출물 있음"
else
  say "** 학습 영상 없음 **"; FAIL="$FAIL 학습영상"
fi

# ---------------------------------------------------------------- 정리
say "=== 끝 ==="
if [ -n "$FAIL" ]; then
  say "** 못 끝낸 것:$FAIL **"
else
  say "네 단계 다 산출물 있음"
fi
say "남은 Isaac 프로세스"
powershell -NoProfile -Command "@(Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { \$_.CommandLine -match 'record_terrain_demo|render_gallery|eval_command_response' }).Count" 2>/dev/null | tr -d '\r'
