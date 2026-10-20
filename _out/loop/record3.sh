#!/usr/bin/env bash
# 비교 대상 «셋» 의 영상을 같은 칸에서 찍는다.
#
# 분류: 운영
# 작성: 오흥재 · 2026-09-28
# 근거: 팀장 지시 「영상, csv, 데이터 등 보고서 기록하고 만들고 웹에 올려」
#       `_out/loop/record_cand1.sh` 의 호출 형식 (2026-09-24 에 실제로 돈 것)
# 요지: **같은 지형·난이도·속도**에서 셋을 찍는다. 그래야 나란히 놓고 볼 수 있다.
#
# 왜 이 칸들인가
#   stepping_stones  축 1 최대 구멍. resume 최고 모델도 d0.5 · 1.0 m/s 에서 24 %
#   gap              omni_gap 으로 학습한 것이 gap 으로 옮겨가나
#   rails            학습 지형이라 「미경험」주장에서 빠지지만 성적이 가장 크게 올랐다
#   pit              학습에 없는데 100 % 나온 칸. 처음부터도 그런가
#
# 전부 찍지 않는다. 48 칸을 다 찍으면 아무도 안 본다.

set -u
LAB="C:/Users/AI-WS01/Desktop/jay/인공지능사관학교/foothold-lab"
RUNS="C:/isaac/IsaacLab/logs/rsl_rl/unitree_go2_gap_nvidia"
PY="C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe"
OUT="$LAB/sim/eval/results/20260928-scratch-clips"
export OMNI_KIT_ACCEPT_EULA=YES
cd "$LAB" || exit 1

say() { echo "[영상 $(date '+%H:%M:%S')] $*"; }

# 판 이름 | 체크포인트 이름 조각 | 어느 iter
MODELS=(
  "v2g2-feetair01|v2g2-feetair01|3000"
  "fs1-scratch-f001|20260928_fs1-scratch-f001|4500"
  "fs2-scratch-f01|20260928_fs2-scratch-f01|4500"
)

# 이름 | 지형 | 난이도 | 속도 | 왜 찍나
CLIPS=(
  "stepping_stones|stepping_stones|0.5|1.0|축 1 최대 구멍"
  "gap|gap|0.5|1.0|omni_gap 학습이 gap 으로 옮겨가나"
  "rails|rails|0.5|1.5|성적이 가장 크게 오른 칸 (학습 지형이다)"
  "pit|pit|0.5|1.0|학습에 없는데 잘 되던 칸"
)

mkdir -p "$OUT"
FAIL=0

for m in "${MODELS[@]}"; do
  IFS='|' read -r label frag iter <<< "$m"

  # 체크포인트를 «찾는다». 없으면 그 판은 건너뛰고 «적어 둔다».
  d=$(ls -d "$RUNS"/*"$frag"* 2>/dev/null | head -1)
  CK="$d/model_$iter.pt"
  if [ ! -f "$CK" ]; then
    say "** $label · model_$iter.pt 가 없다. 건너뛴다 **"
    echo "$label · model_$iter.pt 없음" >> "$OUT/MISSING.txt"
    FAIL=$((FAIL+1))
    continue
  fi
  say "$label · $CK"

  for spec in "${CLIPS[@]}"; do
    IFS='|' read -r name terrain diff vx why <<< "$spec"
    od="$OUT/$label/$name"
    if ls "$od"/*.mp4 >/dev/null 2>&1; then say "  건너뜀 $name (이미 있다)"; continue; fi
    mkdir -p "$od"
    printf '%s\n%s\n' "# $why" "# $label · $terrain d$diff ${vx} m/s" > "$od/why.txt"
    say "  찍는 중 $name ($why)"
    "$PY" sim/eval/record_terrain_demo.py \
      --checkpoint "$CK" --output_dir "$od" \
      --terrain "$terrain" --difficulty "$diff" \
      --cut A --view track_side \
      --num_envs 1 --columns 1 --rows 1 --spacing 3.0 \
      --width 1280 --height 720 \
      --eval_duration 8 --command_vx "$vx" \
      > "$od/run.log" 2>&1 || { say "    «실패» exit=$?"; FAIL=$((FAIL+1)); }
  done
done

say "찍기 끝. 깨짐을 «전부» 검사한다"
# 근거: 2026-09-20 에 새 영상만 검사해서 이미 올라가 있던 깨진 영상을 사흘 못 잡았다.
"$PY" - "$OUT" <<'PYEOF'
import os, sys
root = sys.argv[1]
bad, ok = [], 0
for dp, _, fns in os.walk(root):
    for fn in fns:
        if not fn.endswith(".mp4"): continue
        p = os.path.join(dp, fn)
        sz = os.path.getsize(p)
        if sz < 20000: bad.append((p, sz)); continue
        with open(p, "rb") as fh:
            head = fh.read(12)
        if b"ftyp" not in head: bad.append((p, "ftyp 없음")); continue
        ok += 1
print("  멀쩡한 mp4 %d 개" % ok)
if bad:
    print("  ** 깨진 것 %d 개 **" % len(bad))
    for p, r in bad: print("    ", os.path.relpath(p, root), r)
    sys.exit(1)
PYEOF
VCHK=$?

say "영상 단계 끝 · 실패 $FAIL · 깨짐검사 종료코드 $VCHK"
exit 0
