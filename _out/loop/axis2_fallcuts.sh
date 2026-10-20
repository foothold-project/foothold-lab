#!/usr/bin/env bash
# 축 2 컷을 «넘어지는 판» 으로 다시 굽는다. 세 판 · 세 시나리오.
#
# 분류: 운영
# 작성: 오흥재 · 2026-09-29
# 근거: 팀장 지시 「stop foothold-v1 64판 중 13판이 넘어진다 -> 이건 넘어지는
#       영상으로 해주면 더 비교가 좋지 않겠냐」 · 「hold도 마찬가지로
#       foothold-v1 5판 넘어지는 것중에 보여줘야 더 의미있지」
# 요지: 앞 컷은 env 0 이었고 v1 이 거기서는 안 넘어졌다
#
# **이 파일을 도는 중에 고치지 않는다.**
#
# ## 왜 env 8 인가
#
# `per_env.json` 을 읽어 «넘어진 env» 를 셌다 `확인됨`.
#
# ```
#   foothold-v1  stop  13/64  [8, 9, 18, 20, 25, ...]
#   foothold-v1  hold   5/64  [8, 9, 16, 28, 47]
#   foothold-v1  turn  64/64  전부
#   nvidia-zero  stop   0/64
#   nvidia-zero  hold   0/64
#   nvidia-zero  turn   4/64  [4, 19, 32, 43]
# ```
#
# **8 은 v1 이 셋 다 넘어지는 유일한 번호대다.** 그리고 세 판에 «같은 번호» 를
# 주면 초기 자세가 같아 나란히 놓고 견줄 수 있다. NVIDIA 와 v2 가 그 자리에서
# 안 넘어지는 것이 결과다.
#
# ## 체크포인트
#
# 세 파일의 sha256 을 축 2 기록(`probe_manifest.json`)과 맞춰 봤다. 셋 다 같다
# `확인됨`. 곧 같은 판을 다시 찍는 것이다.
set -u
cd "$(dirname "$0")/../.." || exit 1
PY=C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe
L=C:/isaac/IsaacLab/logs/rsl_rl/unitree_go2_gap_nvidia
V2=$L/2026-09-25_17-29-36_20260925_v2g2-feetair01_seed42_iter3000/model_3000.pt
V1=models/foothold-v1.pt
NV=C:/isaac/IsaacLab/.pretrained_checkpoints/rsl_rl/Isaac-Velocity-Rough-Unitree-Go2-v0/checkpoint.pt
OUT=sim/eval/results/20260929-axis2-fall
ENV_PICK=8
export OMNI_KIT_ACCEPT_EULA=YES
export KMP_DUPLICATE_LIB_OK=TRUE

say() { echo "[$(date +%H:%M:%S)] $*"; }

for row in "nvidia|$NV" "v1|$V1" "v2|$V2"; do
  who="${row%%|*}"; ck="${row#*|}"
  odir="$OUT/$who"

  if [ -f "$odir/probe_manifest.json" ]; then
    say "건너뜀 (이미 있음) $who"; continue
  fi
  if [ ! -f "$ck" ]; then
    say "** 체크포인트 없음 ** $who · $ck"; continue
  fi
  mkdir -p "$odir"

  say "$who · stop · hold · turn · env $ENV_PICK 을 찍는다"
  "$PY" sim/eval/eval_command_response.py \
    --checkpoint "$ck" --label "$who" \
    --scenario stop,hold,turn \
    --num_envs 64 --seed 42 --headless \
    --video --video_env "$ENV_PICK" \
    --video_width 1280 --video_height 720 --video_crf 26 \
    --output_dir "$odir" > "$OUT/$who.log" 2>&1
  rc=$?
  n=$(find "$odir" -name "*.mp4" 2>/dev/null | wc -l)
  say "  exit=$rc · mp4 $n 편"
  if [ "$n" -eq 0 ]; then
    grep -oE '(RuntimeError|ValueError|SystemExit|Error):.*' "$OUT/$who.log" 2>/dev/null | tail -2
  fi
done

say "무엇을 얻었나"
"$PY" - <<'PY' 2>&1 | sed 's/^/          /'
# -*- coding: utf-8 -*-
"""찍은 env 가 «정말 넘어졌나» 를 per_env 로 되짚는다. 영상만 보고 안 믿는다."""
import glob
import io
import json
import os

B = 'sim/eval/results/20260929-axis2-fall'
PICK = 8

for who in ('nvidia', 'v1', 'v2'):
    for sc in ('stop', 'hold', 'turn'):
        p = os.path.join(B, who, sc, 'per_env.json')
        mp4 = glob.glob(os.path.join(B, who, sc, '*.mp4'))
        if not os.path.isfile(p):
            print('%-7s %-5s ** per_env 없음 **' % (who, sc)); continue
        d = json.load(io.open(p, encoding='utf-8'))
        rows = d if isinstance(d, list) else (d.get('envs') or [])
        fell = bool(rows[PICK].get('fell')) if len(rows) > PICK else None
        print('%-7s %-5s env %d 낙상 %-5s · mp4 %d 편'
              % (who, sc, PICK, str(fell), len(mp4)))
PY
say "끝"
