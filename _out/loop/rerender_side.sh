#!/usr/bin/env bash
# 축 1 48칸을 **v1 과 같은 카메라** 로 다시 굽는다. 그리고 무리 컷 둘.
#
# 분류: 운영
# 작성: 오흥재 · 2026-09-28
# 근거: 팀장이 3열 비교 화면에서 직접 지적 「카메라 레이아웃도 다르고 허드도
#       없고 영상 없음, 선택 패널에 필요 없는 것들도 껴있고」
# 요지: v1 과 한 칸이라도 다르면 «세 열을 나란히 견준다» 가 성립하지 않는다
#
# **이 파일을 도는 중에 고치지 않는다.** bash 가 조금씩 읽어 오프셋이 밀린다.
#
# ## 무엇이 달랐나 (파일에서 실측)
#
#   v1 컷 json   flat_army_A_1_track_side.json    <- track_side
#   v2 컷 json   flat_army_A_1_track_high.json    <- track_high
#
#   v1 배포본    1.52 MB · 2031 kb/s · HUD 있음
#   v2 배포본    3.93 MB · 5236 kb/s · HUD «없음»  <- raw 를 올렸다
#
# 셋 다 1920x1080 · 50 fps · 300 장 · 6.00 초다. 다른 것은 **카메라 시점** 과
# **HUD 유무** 와 **웹용 재인코딩** 셋뿐이다.
#
# 그리고 비교 화면 아래에 이 문장이 적혀 있다.
#
#   「카메라 시점은 세 열이 같습니다 (시점은 모델이 아니라 지형이 정합니다)」
#
# **내 컷이 저 문장을 거짓말로 만들었다.** 그래서 다시 굽는다.
#
# ## 옛 판을 안 지운다
#
# `cuts/` 는 그대로 두고 `cuts-side/` 에 새로 굽는다. 무엇이 어떻게 달랐는지
# 나중에 다시 볼 수 있어야 한다. 갤러리는 `gallery_pack.py --cuts` 로 새 판을
# 가리킨다.
set -u
cd "$(dirname "$0")/../.." || exit 1
PY=C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe
L=C:/isaac/IsaacLab/logs/rsl_rl/unitree_go2_gap_nvidia
CK=$L/2026-09-25_17-29-36_20260925_v2g2-feetair01_seed42_iter3000/model_3000.pt
OUT=sim/eval/results/20260928-v2-clips
CUTS=$OUT/cuts-side
DEV="${RENDER_DEV:-cuda:0}"
export OMNI_KIT_ACCEPT_EULA=YES

say() { echo "[$(date +%H:%M:%S)] $*"; }
[ -f "$CK" ] || { say "** 체크포인트 없음 ** $CK"; exit 1; }

# 지형 열여섯 종. `지형|집합|짧은이름` 이고 짧은 이름이 갤러리 파일 이름이 된다.
TERR="discrete_obstacles|unseen10|discrete_obstacles
wave|unseen10|wave
stepping_stones|unseen10|stepping_stones
gap|unseen10|gap
pit|unseen10|pit
rails|unseen10|rails
star|unseen10|star
floating_ring|unseen10|floating_ring
repeated_boxes|unseen10|repeated_boxes
repeated_cylinders|unseen10|repeated_cylinders
pyramid_stairs|rough6|pyramid_stairs
pyramid_stairs_inv|rough6|pyramid_stairs_inv
boxes|rough6|boxes
random_rough|rough6|random_rough
hf_pyramid_slope|rough6|hf_pyramid_slope
hf_pyramid_slope_inv|rough6|hf_pyramid_slope_inv"

n_ok=0
n_bad=0

# ---------------------------------------------------------------- 48 칸
while IFS='|' read -r terr tset short; do
  [ -z "$terr" ] && continue

  for vx in 0.5 1.0 1.5; do
    case "$vx" in 0.5) dur=12.0 ;; 1.0) dur=6.0 ;; 1.5) dur=4.0 ;; esac
    base="$short-v${vx%.0}"
    odir="$CUTS/$base"

    if [ -f "$odir/$base.hud.mp4" ]; then
      say "건너뜀 (이미 있음) $base"; n_ok=$((n_ok+1)); continue
    fi
    mkdir -p "$odir"

    # HUD 제목은 34 자 상한이 있다 (`overlay/hud.py`). 넘으면 속도를 뗀다.
    title="v2 · $short · $vx m/s"
    if [ "${#title}" -gt 34 ]; then title="v2 · $short"; fi

    say "$base · $tset · track_side"
    "$PY" sim/eval/record_terrain_demo.py \
      --checkpoint "$CK" --output_dir "$odir" \
      --terrain "$terr" --terrain_set "$tset" --difficulty 0.5 \
      --cut A --view track_side --title "$title" \
      --num_envs 1 --columns 1 --rows 1 --spacing 3.0 \
      --width 1920 --height 1080 \
      --eval_duration "$dur" --command_vx "$vx" \
      --trace_csv "$odir/trace.csv" \
      --gate_m 3.0 --max_lateral_drift 0.75 --max_velocity_mae 0.25 \
      --preset slow --crf 20 --device "$DEV" > "$odir/1-record.log" 2>&1
    rc=$?

    raw=$(ls "$odir"/*.mp4 2>/dev/null | grep -v '\.hud\.mp4$' | head -1)
    if [ -z "$raw" ]; then
      say "  exit=$rc · ** 산출물 없음 ** · $(grep -oE '(RuntimeError|ValueError|Error):.*' "$odir/1-record.log" 2>/dev/null | tail -1 | cut -c1-88)"
      n_bad=$((n_bad+1)); continue
    fi

    # **HUD 를 여기서 굽는다.** 갤러리에 올라가는 것이 이것이다.
    "$PY" sim/eval/overlay/render.py --video "$raw" --trace "$odir/trace.csv" \
      --out "$odir/$base.hud.mp4" > "$odir/2-hud.log" 2>&1
    hrc=$?

    if [ -f "$odir/$base.hud.mp4" ]; then
      say "  exit=$rc · HUD exit=$hrc · 둘 다 있음"; n_ok=$((n_ok+1))
    else
      say "  exit=$rc · ** HUD 없음 ** · $(tail -1 "$odir/2-hud.log" 2>/dev/null | cut -c1-88)"
      n_bad=$((n_bad+1))
    fi
  done
done <<TERRAINS
$TERR
TERRAINS

say "축1 찬 칸 $n_ok · 못 채운 칸 $n_bad (기대 48)"

# ---------------------------------------------------------------- 무리 컷 둘
# 팀장 지시 [35] 「4096마리 다 보여주는 것은 너무 작게 보인다고 해서 한
# 섹션이었나? 파트였나? 부분만 따로 보여준다고 했었는데 그 부분 이행할 것」
#
# 지금 있는 것은 `army/wide` 한 편뿐이고 프레임을 열어 보니 로봇이 점처럼
# 작다. **확대 컷이 있어야 의미가 생기는 영상인데 그것이 없다.**
for row in "wide|topdown|1024|v2 · many robots · rough6|12.0" \
           "section|macro|1024|v2 · one section|10.0"; do
  name="${row%%|*}"; r="${row#*|}"
  view="${r%%|*}"; r="${r#*|}"
  envs="${r%%|*}"; r="${r#*|}"
  title="${r%%|*}"; dur="${r##*|}"
  odir="$OUT/army-side/$name"

  if ls "$odir"/*.mp4 >/dev/null 2>&1; then
    say "건너뜀 (이미 있음) 무리 $name"; continue
  fi
  mkdir -p "$odir"

  say "무리 · $name · view $view · env $envs"
  "$PY" sim/eval/record_terrain_demo.py \
    --checkpoint "$CK" --output_dir "$odir" \
    --terrain random_rough --terrain_set rough6 --difficulty 0.5 \
    --terrain_rows 20 --terrain_cols 20 \
    --max_init_level 9 \
    --cut A --view "$view" --title "$title" \
    --num_envs "$envs" --columns 32 --rows 32 --spacing 2.5 \
    --width 1920 --height 1080 \
    --eval_duration "$dur" --command_vx 1.0 --gate off \
    --preset slow --crf 20 --device "$DEV" > "$odir/render.log" 2>&1
  rc=$?

  if ls "$odir"/*.mp4 >/dev/null 2>&1; then
    say "  exit=$rc · 산출물 있음"
  else
    say "  exit=$rc · ** 산출물 없음 ** · $(grep -oE '(RuntimeError|ValueError|Error):.*' "$odir/render.log" 2>/dev/null | tail -1 | cut -c1-88)"
  fi
done

# ---------------------------------------------------------------- 검사
say "프레임 전수 검사 (검은 장)"
"$PY" _out/loop/video_scan.py --allow-black --json "$OUT/scan-side.json" \
  "$CUTS/*/*.mp4" "$OUT/army-side/*/*.mp4" 2>&1 | sed 's/^/          /'

say "카메라가 v1 과 같아졌나"
"$PY" - <<'PY' 2>&1 | sed 's/^/          /'
import glob, json, io, os
side = sorted(glob.glob("sim/eval/results/20260928-v2-clips/cuts-side/*/*.json"))
bad = [f for f in side if "track_side" not in os.path.basename(f)]
print("컷 %d 편 · track_side 아닌 것 %d 편" % (len(side), len(bad)))
for f in bad[:5]:
    print("  ** %s **" % os.path.basename(f))
PY

say "미리보기 png"
"$PY" - <<'PY' 2>&1 | sed 's/^/          /'
import os
try:
    import imageio.v2 as iio
    import numpy as np
except ImportError:
    print("imageio 가 없다"); raise SystemExit(0)
B = "sim/eval/results/20260928-v2-clips"
P = os.path.join(B, "previews-side"); os.makedirs(P, exist_ok=True)
n = 0
for sub in ("cuts-side", "army-side"):
    for dp, _d, fs in os.walk(os.path.join(B, sub)):
        for f in fs:
            if not f.endswith(".hud.mp4") and sub == "cuts-side":
                continue
            if not f.endswith(".mp4"):
                continue
            tag = os.path.relpath(os.path.join(dp, f), B).replace(os.sep, "_")[:-4]
            out = os.path.join(P, tag + ".png")
            if os.path.isfile(out):
                n += 1; continue
            try:
                r = iio.get_reader(os.path.join(dp, f))
                c = r.count_frames()
                im = np.asarray(r.get_data(max(0, c // 2)))
                r.close(); iio.imwrite(out, im); n += 1
            except Exception as exc:                           # noqa: BLE001
                print("  ** %s · %s **" % (tag, exc))
print("미리보기 %d 장" % n)
PY
say "끝"
