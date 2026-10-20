#!/usr/bin/env bash
# 학습이 되어 가는 과정을 40~50 초에 담는다.
#
# 분류: 운영
# 작성: 오흥재 · 2026-09-28
# 근거: 팀장 설계 [51] 「처음에 정속으로 에피소드 20초, 20초 두번을 보여주고,
#       이렇게 학습된다 -> 빨리감기 -> 학습되는 영상으로 보여질 수 있을 것
#       같아서 ... 이 전체 길이가 40초 - 50초면 되지 않을까?」 · [52] 승인
# 요지: 숫자 표로는 「학습이 된다」가 안 보인다. 같은 지형·같은 카메라에서
#       **정책만 갈아 끼워** 그것을 보인다
#
# **이 파일을 도는 중에 고치지 않는다.** bash 가 조금씩 읽어 오프셋이 밀린다.
#
# ## 1 차에서 무엇이 틀렸나 (2026-09-28 · 다 굽고 열어 보고 알았다)
#
# 1 차는 `--view macro --terrain_rows 8 --terrain_cols 8 --num_envs 32` 로
# 돌았다. 48.4 초짜리가 나왔고 종료 코드도 0 이었다. **그런데 못 쓴다.**
#
# ```
#   로봇이 안 보인다   로봇 원점은 «세계 원점(0,0)» 인데 지형 상자 중심은
#                      cx = -12 다 (trace 실측). 지형을 키울수록 무리가
#                      화면 밖으로 밀린다. 8x8 타일이면 span 64 m 라
#                      카메라가 28.8 m 뒤, 높이 1.2 m 에 선다. 지평선의 흰 점.
#
#   HUD 가 없다        `--title` 을 줘도 녹화기는 HUD 를 «굽지 않는다.»
#                      `overlay/render.py` 를 따로 걸어야 하고, 그것이 읽는
#                      trace 는 `--trace_csv` 로 «따로» 내야 한다.
#                      녹화기가 내는 `.json` 은 manifest 지 trace 가 아니다.
#                      그래서 어느 조각이 iter 몇인지 볼 방법이 없었다.
# ```
#
# 둘 다 갤러리 48 칸에서 이미 겪고 고친 것이다. 그래서 **갤러리와 같은 길**로
# 간다 (`render_gallery.py:one_cut`).
#
# ## 왜 한 마리인가
#
# `--num_envs 12` 로도 찍어 봤다. 그림이 한 글자도 안 달라졌다 `확인됨`.
# 지형이 주어지면 환경마다 «제 타일» 에 놓여서 한 화면에 안 들어온다.
# 그래서 갤러리와 같이 한 마리를 크게 본다. **정량 근거는 이 영상이 아니라
# 48 칸 x 100 판이 댄다.** 이 영상은 「학습이 된다」를 보이는 몫이다.
#
# ## 이 영상이 «아닌» 것
#
# **맨바닥에서 배우는 과정이 아니다.** `params/agent.yaml` 을 열어 확인했다.
#
# ```
#   resume: true
#   load_run: nvidia_pretrained_source
#   load_checkpoint: nvidia_pretrained.pt
# ```
#
# 그래서 `model_0` 이 이미 1 m/s 로 걷는다. 「학습 전이라 서지도 못한다」고
# 적었던 것은 **틀렸다.** 찍어 놓고 열어 보고 알았다.
#
# `model_0` 을 「NVIDIA 원본」이라고 부르지도 않는다. actor 가중치를 직접
# 맞춰 봤더니 원본과 다르다 `확인됨` (a32b4ad7.. 대 df93a7e1..). 첫 갱신
# «뒤» 저장본이다.
#
# 이 영상이 보이는 것은 **NVIDIA 가중치에서 이어 학습한 3000 회 동안 걸음이
# 어떻게 다듬어지는가** 다. 「못 걷다가 걷게 된다」가 아니다.
#
# ## 짜임
#
# ```
#   0 ~ 12 초   model_0     정속   이어 학습 시작점 (이미 걷는다)
#  12 ~ 34 초   14 자리     훑기   200 -> 2800 · 자리마다 1.6 초
#  34 ~ 48 초   model_3000  정속   3000 회 뒤
# ```
#
# ## 왜 체크포인트가 열여섯인가
#
# 저장본이 121 개다 (0 ~ 3000 · 25 간격). 전부 쓰면 자리마다 0.2 초라 아무것도
# 안 보이고, Isaac 을 121 번 띄워야 한다. **고르게 열여섯**을 뽑는다.
#
# ## 비용
#
# 자리마다 Isaac 을 새로 띄운다 (`record_terrain_demo.py` 는 체크포인트 하나를
# 받는다). 한 판에 약 1 분이라 **열여섯이면 20 분 안팎**이다.
set -u
cd "$(dirname "$0")/../.." || exit 1
PY=C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe
L=C:/isaac/IsaacLab/logs/rsl_rl/unitree_go2_gap_nvidia
RUN=$L/2026-09-25_17-29-36_20260925_v2g2-feetair01_seed42_iter3000
OUT=sim/eval/results/20260928-train-progress
export OMNI_KIT_ACCEPT_EULA=YES
export KMP_DUPLICATE_LIB_OK=TRUE
# **CUDA_VISIBLE_DEVICES 를 쓰지 않는다.** Kit 이 화면용 GPU 를 못 찾아
# 창 생성에서 조용히 멈춘다 (2026-09-28 에 세 번 당했다).

say() { echo "[$(date +%H:%M:%S)] $*"; }
[ -d "$RUN" ] || { say "** 학습 폴더 없음 ** $RUN"; exit 1; }

# 정속 둘 + 훑기 열넷.
SLOW="0:12.0 3000:14.0"
SWEEP="200 400 600 800 1000 1200 1400 1600 1800 2000 2200 2400 2600 2800"

TERR=random_rough
TSET=rough6
VIEW=track_side

shoot() {   # 체크포인트 · 시간 · 이름
  local it="$1" dur="$2" name="$3"
  local ck="$RUN/model_$it.pt"
  local odir="$OUT/$name"

  if [ -f "$odir/$name.hud.mp4" ]; then
    say "건너뜀 (이미 있음) $name"; return 0
  fi

  [ -f "$ck" ] || { say "** 체크포인트 없음 ** model_$it.pt"; return 1; }
  mkdir -p "$odir"

  # HUD 제목은 34 자 상한 (`overlay/hud.py:TITLE_MAX`). `v2 · iter 2800`
  # 은 14 자다. 글꼴이 부분집합이라 한글은 아는 낱말만 쓴다.
  say "$name · model_$it · ${dur}초"
  "$PY" sim/eval/record_terrain_demo.py \
    --checkpoint "$ck" --output_dir "$odir" \
    --terrain "$TERR" --terrain_set "$TSET" --difficulty 0.5 \
    --cut A --view "$VIEW" --title "v2 · iter $it" \
    --num_envs 1 --columns 1 --rows 1 --spacing 3.0 \
    --width 1920 --height 1080 \
    --eval_duration "$dur" --command_vx 1.0 --gate off \
    --trace_csv "$odir/$name.trace.csv" \
    --preset slow --crf 20 > "$odir/1-record.log" 2>&1
  local rc=$?

  local raw
  raw=$(ls "$odir"/*.mp4 2>/dev/null | grep -v '\.hud\.mp4$' | head -1)
  if [ -z "$raw" ] || [ ! -f "$odir/$name.trace.csv" ]; then
    say "  exit=$rc · ** 촬영이 산출물을 안 남겼다 ** · $(grep -oE '(RuntimeError|ValueError|SystemExit|Error):.*' "$odir/1-record.log" 2>/dev/null | tail -1 | cut -c1-80)"
    return 1
  fi

  # **HUD 는 따로 건다.** 녹화기는 굽지 않는다.
  "$PY" sim/eval/overlay/render.py \
    --video "$raw" --trace "$odir/$name.trace.csv" \
    --out "$odir/$name.hud.mp4" --preset slow \
    > "$odir/2-hud.log" 2>&1
  local hrc=$?

  if [ -f "$odir/$name.hud.mp4" ]; then
    say "  exit=$rc · HUD=$hrc · 산출물 있음"
  else
    say "  exit=$rc · ** HUD 가 안 붙었다 ** · $(grep -oE '(RuntimeError|ValueError|Error):.*' "$odir/2-hud.log" 2>/dev/null | tail -1 | cut -c1-80)"
    return 1
  fi
}

# ---------------------------------------------------------------- 정속 둘
for pair in $SLOW; do
  it="${pair%%:*}"; dur="${pair##*:}"
  shoot "$it" "$dur" "slow-$it"
done

# ---------------------------------------------------------------- 훑기 열넷
for it in $SWEEP; do
  shoot "$it" 1.6 "sweep-$it"
done

say "조각 세기"
n=$(find "$OUT" -name "*.hud.mp4" 2>/dev/null | wc -l)
say "  HUD 조각 $n 편 (기대 16)"

# ---------------------------------------------------------------- 이어 붙이기
say "한 편으로 잇는다"
"$PY" - <<'PY' 2>&1 | sed 's/^/          /'
# -*- coding: utf-8 -*-
import glob
import io
import os
import subprocess

try:
    import imageio_ffmpeg
    FF = imageio_ffmpeg.get_ffmpeg_exe()
except ImportError:
    print("imageio-ffmpeg 가 없다"); raise SystemExit(1)

B = "sim/eval/results/20260928-train-progress"
SWEEP = [200, 400, 600, 800, 1000, 1200, 1400, 1600, 1800,
         2000, 2200, 2400, 2600, 2800]
order = ["slow-0"] + ["sweep-%d" % i for i in SWEEP] + ["slow-3000"]

# **HUD 가 붙은 것만 잇는다.** 예전에는 `.hud.mp4` 를 «빼고» 골랐다.
parts = []
for name in order:
    p = os.path.join(B, name, name + ".hud.mp4")
    if not os.path.isfile(p):
        print("  ** 조각이 없다: %s **" % name)
        continue
    parts.append(os.path.abspath(p))

if len(parts) != len(order):
    print("  ** %d / %d 조각만 있다. 안 잇는다 **" % (len(parts), len(order)))
    raise SystemExit(1)

lst = os.path.join(B, "concat.txt")
io.open(lst, "w", encoding="utf-8", newline="\n").write(
    "".join("file '%s'\n" % p.replace("\\", "/") for p in parts))

out = os.path.join(B, "train-progress.mp4")
cmd = [FF, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
       "-i", lst, "-c:v", "libx264", "-crf", "26", "-preset", "slow",
       "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-an", out]
r = subprocess.run(cmd, capture_output=True, text=True)

if r.returncode != 0 or not os.path.isfile(out):
    print("  ** 잇기 실패 **"); print(r.stderr[-500:]); raise SystemExit(1)

import imageio.v2 as iio
rd = iio.get_reader(out)
meta = rd.get_meta_data()
n = rd.count_frames()
# 검은 장을 **전수로** 센다. 표본만 보면 못 잡는다.
import numpy as np
black = sum(1 for i in range(n)
            if float(np.asarray(rd.get_data(i)).mean()) < 8.0)
rd.close()
print("이었다 · %s · %d 장 · %.1f 초 · %.1f MB · 검은 장 %d"
      % (os.path.basename(out), n, meta.get("duration", 0),
         os.path.getsize(out) / 1e6, black))

if not (38.0 <= meta.get("duration", 0) <= 55.0):
    print("  ** 길이가 40~50 초 밖이다. 조각 시간을 고친다 **")
if black:
    print("  ** 검은 장이 %d 개 있다 **" % black)
PY
say "끝"
