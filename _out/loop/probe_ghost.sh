#!/usr/bin/env bash
# 깜빡임 가설 하나를 시험한다. NVIDIA `stop` 한 편만 다시 찍는다.
#
# 분류: 진단
# 작성: 오흥재 · 2026-09-29
# 근거: 팀장 지적 「stop 영상 첫번째꺼 화면 왜 깜빡여?」
# 요지: 카메라를 옮긴 뒤 랜더 한 장을 버리면 하늘돔이 사라지나
#
# 판정: 깜빡임 지표(인접 장 밝기 차 6 넘는 이음). 지금 19 이고 0~2 면 맞다.
set -u
cd "$(dirname "$0")/../.." || exit 1

PY=C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe
NV=C:/isaac/IsaacLab/.pretrained_checkpoints/rsl_rl/Isaac-Velocity-Rough-Unitree-Go2-v0/checkpoint.pt
OUT=sim/eval/results/20260929-ghost-probe
export OMNI_KIT_ACCEPT_EULA=YES
export KMP_DUPLICATE_LIB_OK=TRUE

say() { echo "[$(date +%H:%M:%S)] $*"; }
[ -f "$NV" ] || { say "** 체크포인트 없음 **"; exit 1; }
mkdir -p "$OUT"

say "NVIDIA stop 한 편 · env 8 · 버리는 랜더 넣은 판"
"$PY" sim/eval/eval_command_response.py \
  --checkpoint "$NV" --label nvidia-probe \
  --scenario stop \
  --num_envs 64 --seed 42 --headless \
  --video --video_env 8 \
  --video_width 1280 --video_height 720 --video_crf 26 \
  --output_dir "$OUT" > "$OUT/probe.log" 2>&1
say "  exit=$? · mp4 $(find "$OUT" -name '*.mp4' | wc -l) 편"

f=$(find "$OUT" -name "*.mp4" | head -1)
if [ -n "$f" ]; then
  "$PY" - "$f" <<'PYJ'
import sys
import imageio.v2 as iio
import numpy as np

r = iio.get_reader(sys.argv[1])
c = r.count_frames()
m = np.array([float(np.asarray(r.get_data(i))[:, :, :3].mean())
              for i in range(c)])
r.close()

jumps = int((np.abs(np.diff(m)) > 6.0).sum())
print("  %s" % sys.argv[1])
print("  장 %d · 밝기 %.1f ~ %.1f · 깜빡임 이음 %d (전에는 19)"
      % (c, m.min(), m.max(), jumps))
print("  가설: %s" % ("맞다" if jumps <= 2 else "** 틀렸다 · 다른 데를 본다 **"))
PYJ
else
  say "  ** 산출물 없음 ** · $(grep -oE '(RuntimeError|ValueError|SystemExit):.*' "$OUT/probe.log" 2>/dev/null | tail -1 | cut -c1-90)"
fi
say "끝"
