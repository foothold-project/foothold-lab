#!/usr/bin/env bash
# 대군 컷을 «배속 곡선» 판으로 다시 굽는다.
#
# 분류: 운영 · 작성: 오흥재 · 2026-09-29
# 근거: 팀장 지시 「중간 iter 들도 10초 정도 뽑던가? ... 처음 slow-0 은 정속에서
#       200 iter 보여주면서 부터 가속 되서 5배속으로 하면? ... 10배속으로
#       올라갔다가, 다시 3000에서 정속해서 보여주는 형태로 돌면 되지 않을까」
#
# ## 앞 판이 왜 안 됐나
#
# 가운데 열넷이 **1.6 초** 였다. 에피소드의 첫 토막이라 「걷기 시작하는
# 장면」만 열네 번 반복됐고 무리가 정돈되는 과정이 안 보였다 `확인됨`
# (팀장 지적 「중간에 200 iter 부터 2800 iter 까지는 처음 일부만 보여줘서
# 큰 의미가 없어보여」).
#
# ## 이 판
#
#   slow-0       10 초  ·  1 배속으로 낸다
#   sweep-200 ~ 2800    각 10 초 ·  5 배 -> 10 배로 올려 가며 낸다
#   slow-3000    12 초  ·  1 배속으로 낸다
#
# 배속은 **잇는 단계** 에서 준다 (`train_army_ramp_join.py`). 여기서는
# 원본을 10 초로 찍는 것만 한다.
#
# ## 이미 있는 둘은 다시 안 찍는다
#
# `slow-0`(10 초) 과 `slow-3000`(12 초) 은 `20260929-train-army-d20` 에
# 그대로 있다. 바이트로 복사한다. 같은 설정으로 찍은 것이라 다시 찍을
# 까닭이 없다 (4 분을 아낀다).
set -u
cd "$(dirname "$0")/../.." || exit 1

PY=C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe
L=C:/isaac/IsaacLab/logs/rsl_rl/unitree_go2_gap_nvidia
RUN=$L/2026-09-25_17-29-36_20260925_v2g2-feetair01_seed42_iter3000
OLD=sim/eval/results/20260929-train-army-d20
OUT=sim/eval/results/20260929-train-army-ramp

export OMNI_KIT_ACCEPT_EULA=YES
export KMP_DUPLICATE_LIB_OK=TRUE

# **CUDA_VISIBLE_DEVICES 를 건드리지 않는다.** 랜더는 화면용 GPU 를 쓴다.

SWEEP="200 400 600 800 1000 1200 1400 1600 1800 2000 2200 2400 2600 2800"

say() { echo "[$(date +%H:%M:%S)] $*"; }
[ -d "$RUN" ] || { say "** 학습 폴더 없음 ** $RUN"; exit 1; }

mkdir -p "$OUT"

# 이미 있는 둘을 그대로 가져온다
for name in slow-0 slow-3000; do
  if find "$OUT/$name" -name '*.mp4' 2>/dev/null | grep -q .; then
    say "$name 이미 있다"
    continue
  fi
  if find "$OLD/$name" -name '*.mp4' 2>/dev/null | grep -q .; then
    mkdir -p "$OUT/$name"
    cp -p "$OLD/$name"/* "$OUT/$name"/ 2>/dev/null
    say "$name 을 d20 에서 복사했다 ($(find "$OUT/$name" -name '*.mp4' | wc -l) 편)"
  else
    say "** $name 이 d20 에도 없다 **"
    exit 1
  fi
done

shoot() {   # 체크포인트 · 시간 · 이름
  local it="$1" dur="$2" name="$3"
  local ck="$RUN/model_$it.pt"
  local odir="$OUT/$name"

  if find "$odir" -name '*.mp4' 2>/dev/null | grep -q .; then
    say "건너뜀 (이미 있음) $name"
    return 0
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

  if find "$odir" -name '*.mp4' 2>/dev/null | grep -q .; then
    say "  exit=$rc · 산출물 있음"
  else
    say "  exit=$rc · ** 없음 ** · $(grep -oE '(RuntimeError|ValueError|SystemExit|Error):.*' "$odir/record.log" 2>/dev/null | tail -1 | cut -c1-84)"
    return 1
  fi
}

fail=0
for it in $SWEEP; do
  shoot "$it" 10.0 "sweep-$it" || fail=1
done

n=$(find "$OUT" -name '*.mp4' 2>/dev/null | grep -vc '\.label\.' || true)
say "조각 $n 편 (기대 16)"
exit $fail
