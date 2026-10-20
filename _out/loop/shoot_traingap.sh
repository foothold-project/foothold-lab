#!/usr/bin/env bash
# 학습 지형 둘을 찍는다. `forward_gap` 과 `omni_gap`.
#
# 분류: 운영
# 작성: 오흥재 · 2026-09-29
# 근거: 팀장 지시 「omni_gap 이 어떻게 생겼는지, forward_gap 은 어떻게
#       생겼는지 보고 『아 이렇게 학습 지형이 바뀐거구나』 하는 정도의
#       인사이트를 주고 싶다」
# 요지: 둘 다 «학습» 지형이라 평가 목록에 없고 그래서 컷이 없었다
#
# **이 파일을 도는 중에 고치지 않는다.**
#
# ## 무엇이 다른가 (보고서 6-4 · 6-6)
#
# ```
#   forward_gap   스폰 +x 쪽에만 틈이 있다   -> 앞으로만 가면 된다
#   omni_gap      스폰을 둘러싼 고리다       -> 어느 쪽으로 가도 틈을 만난다
# ```
#
# 명령을 열었을 때 `forward_gap` 만 배운 판이 옆·뒤 틈에서 무너졌고
# (`D` 의 `gap` 33.3 %), `omni_gap` 으로 바꾼 것이 되돌렸다 (99.7 %).
# **그 차이를 지형 생김새로 보인다.**
#
# 지형 카탈로그(그림 1)와 같은 방식이다.
#
# ## 왜 3x3 인가
#
# 2x2 로 먼저 찍었더니 `omni_gap` 은 고리 넷이 또렷했는데 `forward_gap` 은
# **도랑이 화면 맨 아래에 잘렸다** `확인됨`. 고리는 스폰 자리에 있어서 화면에
# 들어오고, 직선 도랑은 타일 안쪽 다른 자리에 있어서 테두리로 밀린다.
#
# 3x3 이면 도랑이 여러 줄 들어와 **패턴으로** 읽힌다. 「직선 도랑 대 고리」가
# 보이는 것이 이 컷의 용건이다. 둘 다 같은 규격으로 찍어야 견줄 수 있다.
#
# 저 띠가 타일 경계가 아니라 도랑인 것은 `omni_gap` 에 직선 띠가 **없는**
# 것으로 갈랐다. 같은 격자 · 같은 테두리인데 한쪽에만 난다 `확인됨`.
set -u
cd "$(dirname "$0")/../.." || exit 1
PY=C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe
L=C:/isaac/IsaacLab/logs/rsl_rl/unitree_go2_gap_nvidia
CK=$L/2026-09-25_17-29-36_20260925_v2g2-feetair01_seed42_iter3000/model_3000.pt
OUT=sim/eval/results/20260929-traingap
DEV="${SHOT_DEV:-cuda:0}"
export OMNI_KIT_ACCEPT_EULA=YES
export KMP_DUPLICATE_LIB_OK=TRUE

say() { echo "[$(date +%H:%M:%S)] $*"; }
[ -f "$CK" ] || { say "** 체크포인트 없음 **"; exit 1; }

# 지형 | 집합 | 꼬리표 (ASCII 만. HUD 글꼴이 부분집합이다)
read -r -d '' TERR <<'TERRAINS'
forward_gap|train_fwdgap|v1 trained
omni_gap|train_omnigap|v2 trained
TERRAINS

n_ok=0
while IFS='|' read -r terr tset tag; do
  [ -z "$terr" ] && continue
  odir="$OUT/$terr"

  if ls "$odir"/*.mp4 >/dev/null 2>&1; then
    say "건너뜀 (이미 있음) $terr"; n_ok=$((n_ok+1)); continue
  fi
  mkdir -p "$odir"

  say "$terr ($tset · $tag) · topdown"
  "$PY" sim/eval/record_terrain_demo.py \
    --checkpoint "$CK" --output_dir "$odir" \
    --terrain "$terr" --terrain_set "$tset" --difficulty 0.5 \
    --terrain_rows 3 --terrain_cols 3 \
    --cut A --view topdown --title "$terr · $tag" \
    --num_envs 9 --columns 3 --rows 3 --spacing 2.5 \
    --width 1920 --height 1080 \
    --eval_duration 3.0 --command_vx 1.0 --gate off \
    --preset slow --crf 20 --device "$DEV" > "$odir/record.log" 2>&1
  rc=$?

  if ls "$odir"/*.mp4 >/dev/null 2>&1; then
    say "  exit=$rc · 산출물 있음"; n_ok=$((n_ok+1))
  else
    say "  exit=$rc · ** 없음 ** · $(grep -oE '(RuntimeError|ValueError|SystemExit|ModuleNotFoundError|Error):.*' "$odir/record.log" 2>/dev/null | tail -1 | cut -c1-96)"
  fi
done <<TERRAINS
$TERR
TERRAINS

say "찍은 것 $n_ok / 2"
say "스틸을 뽑는다 (휘도만 편다 · 지형 카탈로그와 같은 방식)"
"$PY" - <<'PY' 2>&1 | sed 's/^/          /'
# -*- coding: utf-8 -*-
import glob
import os

import imageio.v2 as iio
import numpy as np

B = 'sim/eval/results/20260929-traingap'
P = os.path.join(B, 'stills')
if not os.path.isdir(P):
    os.makedirs(P)

for d in sorted(os.listdir(B)):
    if d == 'stills':
        continue
    mp4 = glob.glob(os.path.join(B, d, '*.mp4'))
    if not mp4:
        continue
    r = iio.get_reader(mp4[0])
    c = r.count_frames()
    best = None
    for frac in (0.20, 0.35, 0.50, 0.70, 0.90):
        im = np.asarray(r.get_data(min(c - 1, int(c * frac))))[:, :, :3]
        if best is None or im.std() > best.std():
            best = im
    r.close()
    y = (0.299 * best[:, :, 0] + 0.587 * best[:, :, 1]
         + 0.114 * best[:, :, 2]).astype(np.float32)
    a, b = float(np.percentile(y, 0.5)), float(np.percentile(y, 99.5))
    y = np.clip((y - a) * (255.0 / max(b - a, 1e-3)), 0, 255).astype(np.uint8)
    out = np.dstack([y, y, y])
    iio.imwrite(os.path.join(P, d + '.png'), out)
    print('  %-14s 흩어짐 %5.1f -> %5.1f' % (d, best.std(), out.std()))
PY
say "끝"
