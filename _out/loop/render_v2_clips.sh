#!/usr/bin/env bash
# v2 (`v2g2-feetair01` iter3000) 의 갤러리 컷을 굽는다.
#
# 분류: 운영
# 작성: 오흥재 · 2026-09-28
# 근거: 팀장 지시 「영상 굽고 웹에 올려」 · 「축2에 대해서도 NVIDIA, v1, v2 비교할 수
#       있게 영상 뽑아놓고」 · 「4096마리 전체 영상 ... 부분만 따로 보여준다」
# 요지: 축 1 지형별 · 축 2 시나리오별 · 4096 마리 둘. **한 번에 다 굽고 검사한다.**
#
# ## 인자를 어디서 가져왔나
#
# `sim/eval/results/20260911-gallery-1080/cuts/*/*.json` 의 `argv` 를 그대로 읽었다.
# 추측한 인자가 없다.
#   --cut A --view track_high --num_envs 1 --columns 1 --rows 1 --spacing 3.0
#   --width 1920 --height 1080 --preset slow --crf 20
#   --gate_m 3.0 --max_lateral_drift 0.75 --max_velocity_mae 0.25
#   --difficulty 0.5 · 속도마다 창 12 / 6 / 4 초
#
# ## `--title` 을 «반드시» 준다
#
# 자동 제목이 34 자를 넘으면 녹화기가 죽는다 (`overlay/hud.py:167`). 실제로
# `rails · d0.5 · 1.0 m/s · model_3000` 이 35 자로 걸렸다. 그리고 그 관문이
# 「정책을 앞에 두라」고 적어 둔 까닭이 있다. 뒤에 두면 잘려서 **나란히 놓는
# 두 컷의 제목이 같아진다.** 그래서 `v2 · <지형> · <속도>` 로 둔다.
#
# ## 내는 파일 이름
#
# 녹화기는 `flat_army_<cut>_<num_envs>_<view>.mp4` 로 «고정» 해서 쓴다.
# 지형과 속도가 이름에 안 들어간다. 그래서 폴더로 가르고, 갤러리로 옮길 때
# `gallery_pack.py` 가 `<지형약칭>-v<속도>.mp4` 로 바꾼다.
set -u
cd "$(dirname "$0")/../.." || exit 1
PY=C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe
CK=C:/isaac/IsaacLab/logs/rsl_rl/unitree_go2_gap_nvidia/2026-09-25_17-29-36_20260925_v2g2-feetair01_seed42_iter3000/model_3000.pt
OUT=sim/eval/results/20260928-v2-clips
DEV="${RENDER_DEV:-cuda:0}"
ONLY="${RENDER_ONLY:-all}"     # all · axis1 · axis2 · army
export OMNI_KIT_ACCEPT_EULA=YES

[ -f "$CK" ] || { echo "** 체크포인트 없음 ** $CK"; exit 1; }
mkdir -p "$OUT/cuts"

say() { echo "[$(date +%H:%M:%S)] $*"; }

# 지형 · 어느 집합인가 · 파일 이름 (갤러리 규칙)
#
# **이름은 지형 «전체 이름» 을 그대로 쓴다.** 줄이지 않는다.
#
# 처음에 `discrete_obstacles` 를 `obstacles`, `stepping_stones` 를 `stones`,
# `floating_ring` 을 `ring` 으로 줄여 적었다. 그 짧은 이름을 어디서 얻었냐 하면
# `ls gallery/v1/clips | sed 's/.*_//'` 였다. **`sed` 가 마지막 밑줄 앞을 자른
# 것을 갤러리 규칙으로 착각했다.** manifest 를 열어 보니 v1 은 전체 이름을 쓴다
# (`discrete_obstacles-v0.5.mp4` · `hf_pyramid_slope_inv-v1.mp4`).
#
# **그래서 실제 충돌이 생겼다.** 나는 `repeated_boxes` 를 `boxes` 로 줄였는데,
# v1 의 `boxes-*.mp4` 는 rough6 의 `boxes` 다. 그대로 올리면 비교 화면이
# «다른 지형끼리» 짝짓는다.
#
# 아래 표는 이제 **어느 집합에서 굽는지** 를 고르는 데만 쓴다. 갤러리로 옮길
# 이름은 `gallery_pack.py` 가 **컷마다 남은 json 의 `terrain` 에서 읽는다.**
# 내 표를 이름표 경로에서 뺀다. 표가 틀려도 이름은 안 틀리게 한다.
TERR="\
discrete_obstacles|unseen10|discrete_obstacles
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

# **열여섯 지형 x 세 속도 = 48 칸을 전부 찍는다.**
#
# 처음에는 「1.0 m/s 는 열여섯 지형 · rails 와 stepping_stones 만 세 속도」로
# 스무 칸만 잡았다. 팀장 지시에서 「rails 로 비교」와 「stepping_stones 도
# 보여줘」를 그 두 지형만 채우면 된다고 읽은 것이다. **갤러리가 48 칸 격자라는
# 구조를 안 봤다.**
#
# `foothold-site/gallery/v1/manifest.json` 을 세어 보니 이렇다.
#   모델별 컷   A 48 · baseline(NVIDIA) 48 · foothold-v1 48   = 144
#   칸의 정의   지형 16 종 x 속도 3 개 = 48
#
# 스무 칸만 채우면 비교 화면에서 `gap` 을 고르고 속도를 0.5 로 바꿨을 때
# **v2 열이 빈 채로 나온다.** 48 칸 중 28 칸이 그렇다. 배포할 상태가 아니다.
#
# 기준선 둘(NVIDIA · foothold-v1)의 96 칸은 `gallery/v1` 에서 재사용한다.
# 새로 찍는 것은 v2 의 48 칸뿐이다.
ALL_SPEEDS="0.5 1.0 1.5"

render_axis1() {
  local terr set short vx dur odir title
  echo "$TERR" | while IFS='|' read -r terr set short; do
    [ -z "$terr" ] && continue
    for vx in $ALL_SPEEDS; do
      case "$vx" in 0.5) dur=12.0 ;; 1.0) dur=6.0 ;; 1.5) dur=4.0 ;; esac
      odir="$OUT/cuts/$short-v${vx%.0}"
      if ls "$odir"/*.mp4 >/dev/null 2>&1; then
        say "건너뜀 (이미 있음) $short v$vx"; continue
      fi
      mkdir -p "$odir"
      # **제목과 파일 이름은 다른 것이다.**
      #   파일 이름  갤러리가 짝짓는 자를 만든다. 틀리면 «다른 지형끼리» 붙는다
      #   HUD 제목   화면에 보이는 글자다. 34 자 상한이 있다 (`overlay/hud.py:167`)
      # `v2 · hf_pyramid_slope_inv · 1.5 m/s` 는 35 자라 녹화기가 죽는다.
      # 그때는 속도를 뗀다. 속도는 파일 이름에 있고 HUD 그래프가 「명령 1.00」으로
      # 이미 보여 준다. 제목에서 빠져도 잃는 것이 없다.
      title="v2 · $short · $vx m/s"
      if [ "${#title}" -gt 34 ]; then
        title="v2 · $short"
        say "  제목이 34 자를 넘어 속도를 뗐다 · $title"
      fi
      say "축1 · $terr ($set) · $vx m/s"
      "$PY" sim/eval/record_terrain_demo.py \
        --checkpoint "$CK" --output_dir "$odir" \
        --terrain "$terr" --terrain_set "$set" --difficulty 0.5 \
        --cut A --view track_high --title "$title" \
        --num_envs 1 --columns 1 --rows 1 --spacing 3.0 \
        --width 1920 --height 1080 \
        --eval_duration "$dur" --command_vx "$vx" \
        --trace_csv "$odir/trace.csv" \
        --gate_m 3.0 --max_lateral_drift 0.75 --max_velocity_mae 0.25 \
        --preset slow --crf 20 --device "$DEV" > "$odir/render.log" 2>&1
      local rc=$?
      if ls "$odir"/*.mp4 >/dev/null 2>&1; then
        say "  exit=$rc · 산출물 있음"
      else
        say "  exit=$rc · ** 산출물 없음 ** · $(grep -oE '(RuntimeError|ValueError|Error):.*' "$odir/render.log" 2>/dev/null | tail -1 | cut -c1-90)"
      fi
    done
  done
}

render_axis2() {
  local odir="$OUT/axis2"
  if [ -f "$odir/probe_manifest.json" ]; then
    say "건너뜀 (이미 있음) 축2"; return
  fi
  mkdir -p "$odir"
  say "축2 · stop · hold · turn · 영상 켜고 env 64"
  # `--video` 는 시나리오마다 mp4 한 편을 낸다. 로봇 한 마리를 따라간다.
  # env 수는 «기존 축 2 와 같은 64» 로 둔다. 1024 로 찍으면 화면에 안 담긴다.
  "$PY" sim/eval/eval_command_response.py \
    --checkpoint "$CK" --label "v2" \
    --scenario stop,hold,turn \
    --num_envs 64 --seed 42 --headless \
    --video --video_env 0 --video_width 1920 --video_height 1080 --video_crf 20 \
    --output_dir "$odir" > "$OUT/axis2.log" 2>&1
  local rc=$?
  local n; n=$(find "$odir" -name "*.mp4" 2>/dev/null | wc -l)
  say "  exit=$rc · mp4 $n 편"
  [ "$n" -eq 0 ] && grep -oE '(RuntimeError|ValueError|Error):.*' "$OUT/axis2.log" 2>/dev/null | tail -2
}

render_army() {
  # 4096 = 64 x 64. 지형은 `rough6` (학습 8종 중 6종) 이다.
  # 캡션에 「학습에 쓴 험지 6종」이라고 적는다. 8종 집합은 등록돼 있지 않다.
  local row odir view title
  for row in "wide|topdown|v2 · 4096 마리 · 학습 6종" "section|macro|v2 · 한 구역 확대"; do
    local name="${row%%|*}"; local rest="${row#*|}"
    view="${rest%%|*}"; title="${rest#*|}"
    odir="$OUT/army/$name"
    if ls "$odir"/*.mp4 >/dev/null 2>&1; then
      say "건너뜀 (이미 있음) 4096 $name"; continue
    fi
    mkdir -p "$odir"
    say "4096 마리 · $name · view $view"
    "$PY" sim/eval/record_terrain_demo.py \
      --checkpoint "$CK" --output_dir "$odir" \
      --terrain random_rough --terrain_set rough6 --difficulty 0.5 \
      --terrain_rows 20 --terrain_cols 20 \
      --cut A --view "$view" --title "$title" \
      --num_envs 4096 --columns 64 --rows 64 --spacing 2.5 \
      --width 1920 --height 1080 \
      --eval_duration 12.0 --command_vx 1.0 \
      --gate off \
      --preset slow --crf 20 --device "$DEV" > "$odir/render.log" 2>&1
    local rc=$?
    if ls "$odir"/*.mp4 >/dev/null 2>&1; then
      say "  exit=$rc · 산출물 있음"
    else
      say "  exit=$rc · ** 산출물 없음 ** · $(grep -oE '(RuntimeError|ValueError|Error):.*' "$odir/render.log" 2>/dev/null | tail -1 | cut -c1-90)"
    fi
  done
}

case "$ONLY" in
  axis1) render_axis1 ;;
  axis2) render_axis2 ;;
  army)  render_army ;;
  all)   render_axis1; render_axis2; render_army ;;
  *) echo "RENDER_ONLY 는 all · axis1 · axis2 · army 중 하나다"; exit 2 ;;
esac

# ---------------------------------------------------------------- HUD 후처리
#
# 녹화기는 **HUD 없는 원본**과 `trace.csv` 를 낸다. HUD 는 별도 패스다
# (`sim/eval/overlay/render.py`). 실제로 mp4 프레임을 뽑아 눈으로 확인했다.
#
# 둘 다 남긴다.
#   원본    갤러리용. `gallery_build.py` 머리말이 「갤러리 클립은 계측을 안
#           얹은 원본」이라고 적어 둔 규격이다
#   .hud    종합보고서용. 팀장이 「HUD 등을 동일하게 구성해서」라고 지시했다
#
# 4096 마리 컷에는 HUD 를 안 얹는다. `trace.csv` 가 로봇 «한 마리» 의 계측이라
# 4096 마리 화면에 얹으면 어느 마리 값인지 알 수 없다.
render_hud() {
  local d out n=0
  for d in "$OUT"/cuts/*/; do
    [ -d "$d" ] || continue
    local raw trace
    raw=$(ls "$d"*.mp4 2>/dev/null | grep -v '\.hud\.mp4$' | head -1)
    trace="$d/trace.csv"
    [ -f "$d/rails-v1.trace.csv" ] && trace="$d/rails-v1.trace.csv"
    [ -z "$raw" ] && continue
    [ -f "$trace" ] || { say "HUD 건너뜀 (trace 없음) $(basename "$d")"; continue; }
    out="$d$(basename "$d").hud.mp4"
    [ -f "$out" ] && continue
    "$PY" sim/eval/overlay/render.py --video "$raw" --trace "$trace" --out "$out" \
      > "$d/hud.log" 2>&1
    if [ -f "$out" ]; then n=$((n+1)); else
      say "  ** HUD 실패 ** $(basename "$d") · $(grep -oE '(RuntimeError|ValueError|Error):.*' "$d/hud.log" 2>/dev/null | tail -1 | cut -c1-80)"
    fi
  done
  say "HUD 얹은 컷 $n 편"
}

render_hud

say "굽기 끝. **프레임 전수 검사를 돈다**"
"$PY" _out/loop/video_scan.py --allow-black \
  --json "$OUT/scan.json" "$OUT/cuts/*/*.mp4" "$OUT/axis2/*/*.mp4" "$OUT/army/*/*.mp4"
