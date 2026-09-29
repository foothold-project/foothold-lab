#!/usr/bin/env bash
# 실패하는 판을 찾아 찍는다. 시드를 훑고 «원하는 결과» 가 난 판만 남긴다.
#
# 분류: 운영
# 작성: 오흥재 · 2026-09-29
# 근거: 팀장 지시 「stepping stones 영상 3개 비교해서 열로, v1 못넘는거,
#       v2 못넘는거, v2 넘는거(8%중)」 · 「pyramid_stairs_inv d0.9 1.5 m/s
#       foothold-v2. 3 %. 계단 코에 걸려 넘어진다 => 이것도 맞는 영상인지
#       확인해봐, 성공한 영상 같은데?」 · 「gap D 는 성공하는 영상이라
#       설명과 일치하지가 않아」
# 요지: 자막이 「실패한다」면 실패하는 판을 보여야 한다
#
# **이 파일을 도는 중에 고치지 않는다.**
#
# ## 왜 시드를 훑나
#
# `--num_envs 1` 이라 한 번 돌리면 한 판이다. 그 판이 붙을지 떨어질지는
# 시드가 정한다. 그래서 **원하는 결과가 날 때까지 시드를 바꿔 돌린다.**
#
# 몇 판이면 될지는 실측 성공률에서 나온다 (`sweep_long.csv` · 100 판씩).
#
#   지형 · 난이도 · 속도            판   종합   전진   원하는 것   실제 타수
#   stepping_stones d0.5 1.0    v1    0 %    0 %   실패        1 (시드 42)
#   stepping_stones d0.5 1.0    v2   24 %   45 %   실패        1 (시드 42)
#   stepping_stones d0.5 1.0    v2   24 %   45 %   성공        **0 / 12**
#   pyramid_stairs_inv d0.9 1.5 v2    3 %   99 %   실패        (rough6 로 고친 뒤)
#   gap d0.5 1.0                D    33 %      -   실패        5 (시드 46)
#
# **성공률은 «종합» 이 아니라 «전진» 과 견주어야 한다.** 이 스크립트의
# 판정은 전진 거리 하나이고, 종합은 생존 · 추종 · 방향까지 and 로 묶은
# 값이다. `stepping_stones` v2 는 종합 24 % 인데 전진만 보면 45 % 다.
#
# **`stepping_stones` v2 의 8.0 % 는 세 속도 평균이다.** 이 컷은 1.0 m/s 라
# 그 칸의 값인 24.0 % 로 읽어야 한다 (0.5 와 1.5 는 둘 다 0.0 % 다).
#
# ## 무엇으로 붙었다 떨어졌다 하나
#
# trace 의 마지막 `fwd_m` 을 통과선 3.0 m 와 견준다. 녹화기가 판정하는 것과
# 같은 잣대다. **집계 숫자로 한 판을 말하지 않는다.**
set -u
cd "$(dirname "$0")/../.." || exit 1

PY=C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe
L=C:/isaac/IsaacLab/logs/rsl_rl/unitree_go2_gap_nvidia
V1=models/foothold-v1.pt
D=$L/2026-09-18_11-19-19_20260918_gapwidecmd_seed42_iter1500/model_1500.pt
V2=$L/2026-09-25_17-29-36_20260925_v2g2-feetair01_seed42_iter3000/model_3000.pt
OUT=sim/eval/results/20260929-failcuts
DEV="${SHOT_DEV:-cuda:0}"
export OMNI_KIT_ACCEPT_EULA=YES
export KMP_DUPLICATE_LIB_OK=TRUE

say() { echo "[$(date +%H:%M:%S)] $*"; }

for f in "$V1" "$D" "$V2"; do
  [ -f "$f" ] || { say "** 체크포인트 없음 ** $f"; exit 1; }
done

# 시드를 훑어 한 판을 찍는다.
#   이름 · 체크포인트 · 지형 · 집합 · 난이도 · 속도 · 시간 · 원하는것(fail|pass) · 제목
hunt() {
  local name="$1" ck="$2" terr="$3" tset="$4" diff="$5" vx="$6" dur="$7" want="$8" title="$9"
  local final="$OUT/$name"

  if ls "$final"/*.mp4 >/dev/null 2>&1; then
    say "건너뜀 (이미 있음) $name"; return 0
  fi

  local seed
  for seed in 42 43 44 45 46 47 48 49 50 51 52 53; do
    local o="$OUT/.try/$name-s$seed"
    mkdir -p "$o"

    "$PY" sim/eval/record_terrain_demo.py \
      --checkpoint "$ck" --output_dir "$o" \
      --terrain "$terr" --terrain_set "$tset" --difficulty "$diff" \
      --cut A --view track_high --title "$title" \
      --num_envs 1 --columns 1 --rows 1 --spacing 3.0 \
      --width 1920 --height 1080 --seed "$seed" \
      --eval_duration "$dur" --command_vx "$vx" \
      --trace_csv "$o/trace.csv" \
      --gate_m 3.0 --max_lateral_drift 0.75 --max_velocity_mae 0.25 \
      --preset slow --crf 20 --device "$DEV" > "$o/render.log" 2>&1

    if ! ls "$o"/*.mp4 >/dev/null 2>&1; then
      say "  $name seed $seed · ** 산출물 없음 ** · $(grep -oE '(RuntimeError|ValueError|SystemExit|ImportError):.*' "$o/render.log" 2>/dev/null | tail -1 | cut -c1-80)"
      continue
    fi

    # 마지막 fwd_m 을 읽어 판정한다.
    local got
    got=$("$PY" - "$o/trace.csv" <<'PYJUDGE'
import csv
import io
import sys

rows = []
with io.open(sys.argv[1], encoding="utf-8") as f:
    for line in f:
        if line.startswith("#"):
            continue
        rows.append(line)

reader = csv.DictReader(rows)
fwd = [float(r["fwd_m"]) for r in reader if r.get("fwd_m") not in (None, "")]

if not fwd:
    print("none 0.0")
else:
    print("%s %.2f" % ("pass" if fwd[-1] >= 3.0 else "fail", fwd[-1]))
PYJUDGE
)
    local verdict="${got%% *}" dist="${got##* }"
    say "  $name seed $seed · $verdict (전진 $dist m · 통과선 3.0)"

    if [ "$verdict" = "$want" ]; then
      mkdir -p "$final"
      cp "$o"/*.mp4 "$o"/*.json "$o/trace.csv" "$final"/ 2>/dev/null
      echo "$seed $verdict $dist" > "$final/chosen.txt"
      say "  $name · 시드 $seed 채택 ($verdict · $dist m)"

      # HUD 를 얹는다. 축 1 컷이라 지형 모드다.
      local raw
      raw=$(ls "$final"/*.mp4 2>/dev/null | grep -v '\.hud\.mp4$' | head -1)
      "$PY" sim/eval/overlay/render.py --video "$raw" \
        --trace "$final/trace.csv" --out "$final/$name.hud.mp4" \
        > "$final/hud.log" 2>&1
      if [ -f "$final/$name.hud.mp4" ]; then
        say "  $name · HUD 얹음"
      else
        say "  $name · ** HUD 실패 ** · $(tail -2 "$final/hud.log" | tr '\n' ' ' | cut -c1-90)"
      fi
      return 0
    fi
  done

  say "  $name · ** 시드 열둘을 다 훑어도 $want 가 안 났다 **"
  return 1
}

mkdir -p "$OUT"

# **집합을 틀리면 조용히 안 난다.** `pyramid_stairs_inv` 는 «학습» 지형
# 여섯 종(rough6) 쪽이고 `unseen10` 에 없다. unseen10 으로 주면 녹화기가
# Isaac 을 띄운 «뒤» 에 「모르는 지형」으로 죽어서 16 초를 쓰고 산출물만
# 없다. 시드 열둘을 그렇게 날렸다 `확인됨`.
hunt "ss-v1-fail"       "$V1" stepping_stones    unseen10 0.5 1.0 6.0 fail "v1 · stepping_stones · 1.0 m/s"
hunt "ss-v2-fail"       "$V2" stepping_stones    unseen10 0.5 1.0 6.0 fail "v2 · stepping_stones · 1.0 m/s"
hunt "stairsinv-v2-fail" "$V2" pyramid_stairs_inv rough6 0.9 1.5 6.0 fail "v2 · stairs_inv d0.9 · 1.5 m/s"
hunt "gap-D-fail"       "$D"  gap                unseen10 0.5 1.0 6.0 fail "D · gap · 1.0 m/s"

# **`ss-v2-pass` 는 여기서 뺀다.** 시드 열둘을 훑어 0/12 였다. 그 칸의
# 실측 «전진» 성공률이 45 % 이므로 0/12 는 확률 0.0008 이다. 잣대(통과선
# 3.0 m · 6.0 초)와 스폰(±0.10 m · ±5 도)이 스윕과 같은 것을 회차
# manifest 로 확인했으니 **남은 차이를 먼저 찾아야 한다.** 찾기 전에 컷을
# 걸면 「v2 는 못 건넌다」를 자리 하나로 말하게 된다.
#
#   스윕      지형마다 env 10 개 · terrains all · 100 판
#   이 촬영   env 1 개 · 지형 하나로 걸러 8x8 격자 · 언제나 칸 (0,0)
#
# 다음 회차에서 env 를 여럿 두고 «건너는 env» 를 따라가는 길을 만든다.

say "끝"
ls -d "$OUT"/*/ 2>/dev/null | grep -v '\.try' | while read -r d; do
  n=$(basename "$d")
  c=$(cat "$d/chosen.txt" 2>/dev/null || echo "?")
  say "  $n · $c"
done
