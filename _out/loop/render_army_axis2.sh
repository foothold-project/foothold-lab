#!/usr/bin/env bash
# 4096 마리 · 축 2 · 그리고 d0.9 하락 컷을 굽는다.
#
# 분류: 운영
# 작성: 오흥재 · 2026-09-28
# 근거: 팀장 지시 「4096 마리랑 축2 굽고 site 통해서 웹에 올려」
#       · 앞선 승인 「pyramid_stairs_inv 하락은 영상이 있어야 한다」
# 요지: 축 1 48 칸 말고 남은 셋을 한 번에 굽는다.
#
# **이 파일을 도는 중에 고치지 않는다.** bash 가 조금씩 읽어서 오프셋이 밀리면
# 없는 문법 오류로 죽고 뒤쪽 단계가 조용히 안 돈다. 오늘 실제로 그랬다.
#
# ## 굽는 것 셋
#
# 1. 4096 마리 · 전체 컷과 한 구역 확대 컷
#    지형은 `rough6` 다. 우리 학습 지형 여덟 종 중 «여섯» 이다.
#    `omni_gap` 과 `rails` 가 빠진다. 집합 등록이 `unseen10` · `rough6` 둘뿐이고
#    (`sim/eval/terrains.py:TERRAIN_SETS`) 여덟 종 집합은 없다.
#    그래서 캡션에 **「학습에 쓴 험지 6종」** 이라고 적는다. 「학습 지형」이라고
#    뭉뚱그리면 틀린 말이 된다.
#
# 2. 축 2 · stop · hold · turn 컷
#    NVIDIA 와 foothold-v1 의 같은 컷은 `gallery/H/clips` 에 이미 있다
#    (`nvidia-zero_*` · `foothold-v1_*`). v2 것만 찍는다.
#    **env 는 64 로 둔다.** 판정은 1024 로 다시 쟀지만 영상은 한 마리를
#    따라가는 것이라 env 수가 화면을 안 바꾸고, 기존 축 2 와 같은 조건으로
#    두는 편이 비교에 낫다.
#
# 3. `pyramid_stairs_inv` · d0.9 · 1.5 m/s
#    v2 가 3 % 이고 `foothold-v1` 이 90 % 인 자리다. 87 %p 하락을 숫자가
#    아니라 «장면» 으로 보여 주는 유일한 자료다. 48 칸은 전부 d0.5 라 없다.
#    **기준선 v1 것도 같이 찍는다.** 나란히 놓아야 하락이 보인다.
set -u
cd "$(dirname "$0")/../.." || exit 1
PY=C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe
L=C:/isaac/IsaacLab/logs/rsl_rl/unitree_go2_gap_nvidia
V2=$L/2026-09-25_17-29-36_20260925_v2g2-feetair01_seed42_iter3000/model_3000.pt
V1=models/foothold-v1.pt
OUT=sim/eval/results/20260928-v2-clips
DEV="${RENDER_DEV:-cuda:0}"
export OMNI_KIT_ACCEPT_EULA=YES

say() { echo "[$(date +%H:%M:%S)] $*"; }
[ -f "$V2" ] || { say "** v2 체크포인트 없음 **"; exit 1; }
[ -f "$V1" ] || { say "** v1 체크포인트 없음 **"; exit 1; }

done_ok() { ls "$1"/*.mp4 >/dev/null 2>&1; }

# ---------------------------------------------------------------- 1 · 4096 마리
for row in "wide|topdown|v2 · 4096 · rough6" "section|macro|v2 · 4096 · zoom"; do
  name="${row%%|*}"; rest="${row#*|}"; view="${rest%%|*}"; title="${rest#*|}"
  odir="$OUT/army/$name"
  if done_ok "$odir"; then say "건너뜀 (이미 있음) 4096 $name"; continue; fi
  mkdir -p "$odir"
  say "4096 마리 · $name · view $view"
  "$PY" sim/eval/record_terrain_demo.py \
    --checkpoint "$V2" --output_dir "$odir" \
    --terrain random_rough --terrain_set rough6 --difficulty 0.5 \
    --terrain_rows 20 --terrain_cols 20 \
    --cut A --view "$view" --title "$title" \
    --num_envs 4096 --columns 64 --rows 64 --spacing 2.5 \
    --width 1920 --height 1080 \
    --eval_duration 12.0 --command_vx 1.0 \
    --gate off \
    --preset slow --crf 20 --device "$DEV" > "$odir/render.log" 2>&1
  RC=$?
  if done_ok "$odir"; then say "  exit=$RC · 산출물 있음"
  else say "  exit=$RC · ** 산출물 없음 ** · $(grep -oE '(RuntimeError|ValueError|Error):.*' "$odir/render.log" 2>/dev/null | tail -1 | cut -c1-90)"; fi
done

# ---------------------------------------------------------------- 2 · 축 2
odir="$OUT/axis2"
if [ -f "$odir/probe_manifest.json" ]; then
  say "건너뜀 (이미 있음) 축2"
else
  mkdir -p "$odir"
  say "축2 · stop · hold · turn · 영상 켜고 env 64"
  "$PY" sim/eval/eval_command_response.py \
    --checkpoint "$V2" --label "v2" \
    --scenario stop,hold,turn \
    --num_envs 64 --seed 42 --headless \
    --video --video_env 0 --video_width 1920 --video_height 1080 --video_crf 20 \
    --output_dir "$odir" > "$OUT/axis2.log" 2>&1
  RC=$?
  n=$(find "$odir" -name "*.mp4" 2>/dev/null | wc -l)
  say "  exit=$RC · mp4 $n 편"
  [ "$n" -eq 0 ] && grep -oE '(RuntimeError|ValueError|Error):.*' "$OUT/axis2.log" 2>/dev/null | tail -2
fi

# ---------------------------------------------------------------- 3 · d0.9 하락 컷
for row in "v2|$V2|v2 · stairs_inv · d0.9" "v1|$V1|v1 · stairs_inv · d0.9"; do
  who="${row%%|*}"; rest="${row#*|}"; ck="${rest%%|*}"; title="${rest#*|}"
  odir="$OUT/regression/pyramid_stairs_inv-d0.9-v1.5-$who"
  if done_ok "$odir"; then say "건너뜀 (이미 있음) 하락 컷 $who"; continue; fi
  mkdir -p "$odir"
  say "하락 컷 · $who · pyramid_stairs_inv · d0.9 · 1.5 m/s"
  "$PY" sim/eval/record_terrain_demo.py \
    --checkpoint "$ck" --output_dir "$odir" \
    --terrain pyramid_stairs_inv --terrain_set rough6 --difficulty 0.9 \
    --cut A --view track_high --title "$title" \
    --num_envs 1 --columns 1 --rows 1 --spacing 3.0 \
    --width 1920 --height 1080 \
    --eval_duration 4.0 --command_vx 1.5 \
    --trace_csv "$odir/trace.csv" \
    --gate_m 3.0 --max_lateral_drift 0.75 --max_velocity_mae 0.25 \
    --preset slow --crf 20 --device "$DEV" > "$odir/render.log" 2>&1
  RC=$?
  if done_ok "$odir"; then
    say "  exit=$RC · 산출물 있음"
    raw=$(ls "$odir"/*.mp4 2>/dev/null | grep -v '\.hud\.mp4$' | head -1)
    "$PY" sim/eval/overlay/render.py --video "$raw" --trace "$odir/trace.csv" \
      --out "$odir/$(basename "$odir").hud.mp4" > "$odir/hud.log" 2>&1
  else
    say "  exit=$RC · ** 산출물 없음 ** · $(grep -oE '(RuntimeError|ValueError|Error):.*' "$odir/render.log" 2>/dev/null | tail -1 | cut -c1-90)"
  fi
done

# ---------------------------------------------------------------- 4 · 검사
say "프레임 전수 검사"
"$PY" _out/loop/video_scan.py --allow-black --json "$OUT/scan-army-axis2.json" \
  "$OUT/army/*/*.mp4" "$OUT/axis2/*/*.mp4" "$OUT/axis2/*.mp4" "$OUT/regression/*/*.mp4" \
  2>&1 | sed 's/^/          /'

say "미리보기 png"
"$PY" - <<'PY' 2>&1 | sed 's/^/          /'
import os
try:
    import imageio.v2 as iio
    import numpy as np
except ImportError:
    print("imageio 가 없다"); raise SystemExit(0)
B = "sim/eval/results/20260928-v2-clips"
P = os.path.join(B, "previews")
os.makedirs(P, exist_ok=True)
n = 0
for sub in ("army", "axis2", "regression"):
    root = os.path.join(B, sub)
    for dirpath, _d, files in os.walk(root):
        for f in files:
            if not f.endswith(".mp4"):
                continue
            tag = os.path.relpath(os.path.join(dirpath, f), B).replace(os.sep, "_")[:-4]
            out = os.path.join(P, tag + ".png")
            if os.path.isfile(out):
                n += 1
                continue
            try:
                r = iio.get_reader(os.path.join(dirpath, f))
                c = r.count_frames()
                im = np.asarray(r.get_data(max(0, c // 2)))
                r.close()
                iio.imwrite(out, im)
                n += 1
            except Exception as exc:                               # noqa: BLE001
                print("  ** %s · %s **" % (tag, exc))
print("미리보기 %d 장" % n)
PY

say "끝"
