#!/usr/bin/env bash
# 학습 진행을 «대군이 여러 험지에서» 시점으로 담는다.
#
# 분류: 운영
# 작성: 오흥재 · 2026-09-29
# 근거: 팀장 지시 「아 학습이 이렇게 되는구나, 이렇게 전체 마리가 여러가지
#       지형에서 따로 각각의 에피소드를 갖고 학습이 되는구나? 라고 알 수
#       있는 영상」
# 요지: 한 마리 추적 컷은 그것을 못 보인다. 격자 전체를 본다
#
# **이 파일을 도는 중에 고치지 않는다.**
#
# ## 왜 600 인가 · 칸당 밀도를 학습과 맞춘다 (2026-09-29 · 팀장 지적)
#
# 학습은 env 4096 을 **10 x 20 = 200 칸**에 놓는다 (`params/env.yaml`
# 86 · 189 · 200 · 201 행). 곧 **칸당 약 20 마리**다.
#
# 이 컷은 칸을 5 x 6 = 30 으로 줄여 로봇이 보이게 한다 (200 칸이면
# 지형이 80 x 160 m 가 되어 로봇이 8 px 이다 · 앞서 버린 컷과 같은 자리).
#
# 그래서 **마리 수를 600 으로 두어 칸당 밀도를 학습과 같게** 맞춘다.
# 4096 을 30 칸에 넣으면 칸당 136 마리로 흰 덩이가 된다 `확인됨`. bash 가 조금씩 읽어 오프셋이 밀린다.
#
# ## 왜 이 시점인가
#
# 세 컷의 축척을 재서 골랐다. 로봇 0.7 m 가 몇 px 인가.
#
# ```
#   army-side/wide      9.9 px/m   ->  7 px   안 보인다
#   army-side/section  11.5 px/m   ->  8 px   안 보인다
#   army/wide          37.8 px/m   -> 26 px   **이 인자를 쓴다**
# ```
#
# `--terrain all --terrain_set rough6 --terrain_cols 6` 이면 **열마다 다른
# 하위 지형**이 오고, `--max_init_level 4` 가 로봇을 다섯 행에 퍼뜨린다.
# 그래서 한 화면에 여섯 지형 x 다섯 난이도 층의 무리가 같이 나온다.
#
# ## iter 를 어떻게 보이나
#
# 이 시점에는 HUD 가 없다 (HUD 는 한 마리를 따라가며 trace 를 읽어 그린다).
# 대신 **조각마다 `iter N` 을 ffmpeg 으로 태워 넣는다.** 글꼴은 저장소 안
# 것을 쓰고 글자는 ASCII 라 부분집합 글꼴로도 난다.
#
# ## 짜임 (약 44 초)
#
# ```
#   0 ~ 10 초   model_0     10.0 초
#  10 ~ 32 초   14 자리      1.6 초씩
#  32 ~ 44 초   model_3000  12.0 초
# ```
set -u
cd "$(dirname "$0")/../.." || exit 1
PY=C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe
L=C:/isaac/IsaacLab/logs/rsl_rl/unitree_go2_gap_nvidia
RUN=$L/2026-09-25_17-29-36_20260925_v2g2-feetair01_seed42_iter3000
OUT=sim/eval/results/20260929-train-army-d20
export OMNI_KIT_ACCEPT_EULA=YES
export KMP_DUPLICATE_LIB_OK=TRUE

say() { echo "[$(date +%H:%M:%S)] $*"; }
[ -d "$RUN" ] || { say "** 학습 폴더 없음 ** $RUN"; exit 1; }

SLOW="0:10.0 3000:12.0"
SWEEP="200 400 600 800 1000 1200 1400 1600 1800 2000 2200 2400 2600 2800"

shoot() {   # 체크포인트 · 시간 · 이름
  local it="$1" dur="$2" name="$3"
  local ck="$RUN/model_$it.pt"
  local odir="$OUT/$name"

  if ls "$odir"/*.mp4 >/dev/null 2>&1; then
    say "건너뜀 (이미 있음) $name"; return 0
  fi
  [ -f "$ck" ] || { say "** 체크포인트 없음 ** model_$it.pt"; return 1; }
  mkdir -p "$odir"

  say "$name · model_$it · ${dur}초 · env 600 (칸당 20)"
  "$PY" sim/eval/record_terrain_demo.py \
    --checkpoint "$ck" --output_dir "$odir" \
    --terrain all --terrain_set rough6 --difficulty 0.5 \
    --terrain_rows 5 --terrain_cols 6 --max_init_level 4 \
    --cut A --view topdown \
    --num_envs 600 --columns 25 --rows 24 --spacing 2.5 \
    --width 1920 --height 1080 \
    --eval_duration "$dur" --command_vx 1.0 --gate off \
    --preset slow --crf 20 > "$odir/record.log" 2>&1
  local rc=$?

  if ls "$odir"/*.mp4 >/dev/null 2>&1; then
    say "  exit=$rc · 산출물 있음"
  else
    say "  exit=$rc · ** 없음 ** · $(grep -oE '(RuntimeError|ValueError|SystemExit|Error):.*' "$odir/record.log" 2>/dev/null | tail -1 | cut -c1-84)"
    return 1
  fi
}

for pair in $SLOW; do
  it="${pair%%:*}"; dur="${pair##*:}"
  shoot "$it" "$dur" "slow-$it"
done
for it in $SWEEP; do
  shoot "$it" 1.6 "sweep-$it"
done

say "조각 세기"
n=$(find "$OUT" -name "*.mp4" 2>/dev/null | grep -vc "labeled" || true)
say "  조각 $n 편 (기대 16)"

say "iter 를 태우고 한 편으로 잇는다"
"$PY" _out/loop/train_army_join.py 2>&1 | sed 's/^/          /'
say "끝"
