#!/usr/bin/env bash
# 지형 열여섯 종을 «위에서» 한 장씩 찍는다. 학습 6종과 미학습 10종 대조용.
#
# 분류: 운영
# 작성: 오흥재 · 2026-09-28
# 근거: 팀장 지시 「학습 지형 가능하면 지형 이미지 캡쳐해서 학습 지형 6종과
#       미학습 지형 10종 보여줘」 · 「topdown 16장 새로 구워」
# 요지: 글로만 「미경험 여덟 종」이라고 적으면 보는 사람이 그 지형을 모른다
#
# **이 파일을 도는 중에 고치지 않는다.** bash 가 조금씩 읽어 오프셋이 밀린다.
#
# ## 왜 포스터를 안 쓰나
#
# 갤러리 포스터가 이미 48장 있다. 그런데 그것은 «지형 x 속도» 이고 옆에서
# 본 것이라 **지형의 생김새가 안 보인다.** 위에서 봐야 틈이 어디 있고
# 테두리가 몇 겹인지 보인다.
#
# ## 로봇을 빼지 않는다
#
# 한 마리를 남긴다. **자가 없으면 틈이 20 cm 인지 2 m 인지 모른다.**
# Go2 의 몸 길이가 약 0.65 m 라 그것이 자가 된다.
#
# ## «격자» 로 찍는다 · 환경 하나면 카메라가 무너진다 `확인됨`
#
# 1 차 16장이 전부 못 쓸 그림이었다. 하늘이 절반이거나 그냥 회색 벽이었다.
#
#   record_terrain_demo.py:287-291
#     x0,x1,y0,y1,z = TERRAIN_BOX        # 환경 «원점» 의 min/max
#     span = max(x1-x0, y1-y0)
#     eye_m = [cx-1, cy, z + span*1.1]   # topdown
#
# `--num_envs 1` 이면 원점이 하나라 `x0 == x1` 이고 **span 이 0** 이다.
# 그러면 카메라가 지형과 같은 높이에서 1 m 옆에 앉아 수평을 본다.
# 로그에 증거가 찍혀 있었는데 안 읽었다.
#
#   [지형] pyramid_stairs · x -28.0~-28.0 y -28.0~-28.0 z 0.98
#
# **`topdown` 은 여러 환경을 전제로 한 시점이다.** 4096 마리 컷이 제대로
# 나왔던 것이 그 때문이다. 그래서 2 x 2 격자로 찍어 span 을 만든다.
#
# ## 한 장 먼저 컨펌한다
#
# `SHOT_ONE=<지형>` 을 주면 그 한 장만 찍고 멈춘다. **전량 돌리기 전에
# 한 장을 눈으로 본다.** 1 차에서 그 절차를 건너뛰어 16장을 통째로 버렸다.
#
# ## 난이도는 0.5 로 못 박는다
#
# 판정이 0.5 에서 이뤄진다. 그림도 같은 난이도라야 「이 지형에서 88 %」가
# 그 그림의 지형을 가리킨다.
set -u
cd "$(dirname "$0")/../.." || exit 1
PY=C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe
L=C:/isaac/IsaacLab/logs/rsl_rl/unitree_go2_gap_nvidia
CK=$L/2026-09-25_17-29-36_20260925_v2g2-feetair01_seed42_iter3000/model_3000.pt
OUT=sim/eval/results/20260928-terrain-shots
DEV="${SHOT_DEV:-cuda:0}"
export OMNI_KIT_ACCEPT_EULA=YES
export KMP_DUPLICATE_LIB_OK=TRUE

say() { echo "[$(date +%H:%M:%S)] $*"; }
[ -f "$CK" ] || { say "** 체크포인트 없음 ** $CK"; exit 1; }

# `지형|집합|꼬리표`
#
# **꼬리표를 ASCII 로 쓴다.** HUD 글꼴은 `overlay/hud.py:charset()` 이 굽는
# 부분집합이라 ASCII 와 «정해진 한글 낱말 열몇 개» 만 들어 있다. 「미경험」의
# 「험」이 없어서 16장이 전부 거부됐다 `확인됨` (2026-09-28). 그 사실을 전에도
# 한 번 겪고 기억에 적어 놓고 또 밟았다.
#
# 꼬리표는 **v2 기준**이다. `env.yaml` 의 `sub_terrains` 실측으로 정했다.
#   v2 학습 8종 = rough6 6종 + omni_gap + rails
#   그래서 평가 열여섯 중 rails 는 «학습» 이고, gap 은 «친척(omni_gap)» 이다.
TERR="pyramid_stairs|rough6|trained
pyramid_stairs_inv|rough6|trained
boxes|rough6|trained
random_rough|rough6|trained
hf_pyramid_slope|rough6|trained
hf_pyramid_slope_inv|rough6|trained
rails|unseen10|v2-trained
gap|unseen10|kin
discrete_obstacles|unseen10|unseen
wave|unseen10|unseen
stepping_stones|unseen10|unseen
pit|unseen10|unseen
star|unseen10|unseen
floating_ring|unseen10|unseen
repeated_boxes|unseen10|unseen
repeated_cylinders|unseen10|unseen"

n_ok=0
n_bad=0
ONE="${SHOT_ONE:-}"

while IFS='|' read -r terr tset tag; do
  [ -z "$terr" ] && continue
  if [ -n "$ONE" ] && [ "$terr" != "$ONE" ]; then continue; fi
  odir="$OUT/$terr"

  if ls "$odir"/*.mp4 >/dev/null 2>&1; then
    say "건너뜀 (이미 있음) $terr"; n_ok=$((n_ok+1)); continue
  fi
  mkdir -p "$odir"

  # HUD 제목 상한 34 자. 가장 긴 것이 `hf_pyramid_slope_inv · trained` = 30 자다.
  title="$terr · $tag"

  say "$terr ($tset · $tag) · topdown"
  "$PY" sim/eval/record_terrain_demo.py \
    --checkpoint "$CK" --output_dir "$odir" \
    --terrain "$terr" --terrain_set "$tset" --difficulty 0.5 \
    --terrain_rows 2 --terrain_cols 2 \
    --cut A --view topdown --title "$title" \
    --num_envs 4 --columns 2 --rows 2 --spacing 2.5 \
    --width 1920 --height 1080 \
    --eval_duration 3.0 --command_vx 1.0 --gate off \
    --preset slow --crf 20 --device "$DEV" > "$odir/record.log" 2>&1
  rc=$?

  if ls "$odir"/*.mp4 >/dev/null 2>&1; then
    say "  exit=$rc · 산출물 있음"; n_ok=$((n_ok+1))
  else
    say "  exit=$rc · ** 없음 ** · $(grep -oE '(RuntimeError|ValueError|SystemExit|Error):.*' "$odir/record.log" 2>/dev/null | tail -1 | cut -c1-88)"
    n_bad=$((n_bad+1))
  fi
done <<TERRAINS
$TERR
TERRAINS

say "찍은 것 $n_ok · 못 찍은 것 $n_bad (기대 ${ONE:+1}${ONE:-16})"

# ---------------------------------------------------------------- 스틸 뽑기
#
# **판정을 여기 두지 않는다.** 예전에는 이 자리에 인라인으로 두었는데,
# 「밝기 + 흩어짐」 관문이 일곱 종을 「내용 없음」으로 버렸다. 열어 보니
# 지형은 있었고 대비가 없었을 뿐이다 `확인됨`. 뽑는 규칙을 한 곳에 둔다.
say "스틸을 뽑는다 (_out/loop/terrain_stills.py)"
"$PY" _out/loop/terrain_stills.py 2>&1 | sed 's/^/          /'

say "끝"
