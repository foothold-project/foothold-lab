#!/usr/bin/env bash
# 1) `foothold-v1` 의 d0.9 여섯 칸을 채운다.  2) 평가 장치가 결과를 바꾸는지 «잰다».
#
# 분류: 운영
# 작성: 오흥재 · 2026-09-28
# 근거: 팀장 지시 「3 도 채워」 · 「3도 채워서 보고서 2에는 채운 상태로 비교해」
# 요지: v1 이 d0.1~0.7 까지만 있어 d0.9 에서 v2 와 나란히 못 선다. 그 여섯 칸을 채운다.
#
# ## 처음에 이것을 미루자고 한 이유가 «틀렸다»
#
# 「기준선을 우리가 다시 재면 report-v1 숫자와 갈릴 수 있다」고 했다. 그런데
# `maindata-v1` 의 `run_manifest.json` 을 열어 보니 **그것도 우리 하네스로
# 우리가 잰 것**이다. 발표 표를 덮어쓰는 것이 아니라 «우리 스윕을 잇는» 것이다.
#   체크포인트  models/foothold-v1.pt
#   sha256     c7612aef... 모델 카드의 값과 일치 `확인됨`
#   조건       episodes 100 · spec 2 · min_progress 3.0 · drift 0.75 · seed 42
#              창 12 / 6 / 4 초
# 그래서 같은 조건으로 d0.9 만 이어 붙인다.
#
# 속도 폴더 이름을 형제와 «같게» 둔다. `maindata-v1` 은 1.0 m/s 를 `v1` 로
# 적었다 (`v1.0` 이 아니다). `v2_sweep.py:speed_dir` 는 둘 다 받지만 폴더가
# 섞이면 사람이 헷갈린다.
#
# ## 둘째 일 · 평가 장치를 «잰다»
#
# 스윕 자료의 장치가 양쪽 다 섞여 있다 (실측).
#   v1  cuda:0 33 칸 · cuda:1  9 칸
#   v2  cuda:0 42 칸 · cuda:1  6 칸
# 주의 문구로 남기지 말고, 같은 칸을 두 장치에서 돌려 «같은지» 본다.
# 고른 칸은 `v2g2@3000 · unseen10 · d0.5 · 1.0 m/s` 다. 원래 `cuda:1` 에서
# 쟀으므로 `cuda:0` 으로 다시 돌려 열 지형 성공률을 대조한다.
set -u
cd "$(dirname "$0")/../.." || exit 1
PY=C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe
V1=models/foothold-v1.pt
OUT=sim/eval/results/maindata-v1/foothold-v1
DEV="${FILL_DEV:-cuda:0}"
export OMNI_KIT_ACCEPT_EULA=YES

[ -f "$V1" ] || { echo "** 체크포인트 없음 ** $V1"; exit 1; }
GOT=$(sha256sum "$V1" | cut -d' ' -f1)
WANT=c7612aef0b3c49b876c610d6d1c4f507eba666a4ffa03797760ad4a896ee7aca
if [ "$GOT" != "$WANT" ]; then
  echo "** sha256 이 모델 카드와 다르다 **"; echo "  잰 것 $GOT"; echo "  카드 $WANT"; exit 1
fi
echo "[$(date +%H:%M:%S)] sha256 확인 · 모델 카드와 같다"

# ---------------------------------------------------------------- 1 · v1 d0.9
for TS in rough6 unseen10; do
  for pair in "0.5 12.0 v0.5" "1.0 6.0 v1" "1.5 4.0 v1.5"; do
    set -- $pair; VX=$1; DUR=$2; VDIR=$3
    odir="$OUT/$TS/d0.9/$VDIR"
    if [ -f "$odir/generalization_summary.csv" ]; then
      echo "[$(date +%H:%M:%S)] 건너뜀 v1 d0.9 $TS $VDIR"; continue
    fi
    echo "[$(date +%H:%M:%S)] v1 d0.9 $TS $VDIR 시작"
    "$PY" sim/eval/eval_generalization.py \
      --checkpoint "$V1" \
      --terrain_set "$TS" --terrains all \
      --difficulty 0.9 \
      --episodes 100 --envs_per_terrain 10 \
      --command_vx "$VX" --eval_duration "$DUR" \
      --min_progress_m 3.0 --max_lateral_drift 0.75 \
      --seed 42 --headless --device "$DEV" \
      --note "기준선 v1 의 d0.9 를 이어 붙임 · 팀장 지시 2026-09-28 · 조건은 형제 칸과 같다" \
      --output_dir "$odir" > "$OUT/fill-d0.9-$TS-$VDIR.log" 2>&1
    RC=$?
    if [ -f "$odir/generalization_summary.csv" ]; then H="산출물 있음"; else H="** 산출물 없음 **"; fi
    echo "[$(date +%H:%M:%S)] v1 d0.9 $TS $VDIR exit=$RC · $H"
  done
done

# ---------------------------------------------------------------- 2 · 장치 대조
CK=C:/isaac/IsaacLab/logs/rsl_rl/unitree_go2_gap_nvidia/2026-09-25_17-29-36_20260925_v2g2-feetair01_seed42_iter3000/model_3000.pt
DCHK=sim/eval/results/20260928-devicecheck/v2g2-iter3000-unseen10-d0.5-v1.0-cuda0
if [ ! -f "$DCHK/generalization_summary.csv" ]; then
  echo "[$(date +%H:%M:%S)] 장치 대조 · v2g2@3000 unseen10 d0.5 1.0 m/s 를 cuda:0 에서 시작"
  mkdir -p "$(dirname "$DCHK")"
  "$PY" sim/eval/eval_generalization.py \
    --checkpoint "$CK" \
    --terrain_set unseen10 --terrains all \
    --difficulty 0.5 \
    --episodes 100 --envs_per_terrain 10 \
    --command_vx 1.0 --eval_duration 6.0 \
    --min_progress_m 3.0 --max_lateral_drift 0.75 \
    --seed 42 --headless --device cuda:0 \
    --note "장치 대조 · 원래 칸은 cuda:1 에서 쟀다" \
    --output_dir "$DCHK" > "$(dirname "$DCHK")/devicecheck.log" 2>&1
  RC=$?
  if [ -f "$DCHK/generalization_summary.csv" ]; then H="산출물 있음"; else H="** 산출물 없음 **"; fi
  echo "[$(date +%H:%M:%S)] 장치 대조 exit=$RC · $H"
fi

echo "[$(date +%H:%M:%S)] 대조한다"
"$PY" - <<'PY'
import csv, io, os
A = "sim/eval/results/20260923-v2rs/v2g2-feetair01-iter3000/unseen10/d0.5/v1.0/generalization_summary.csv"
B = "sim/eval/results/20260928-devicecheck/v2g2-iter3000-unseen10-d0.5-v1.0-cuda0/generalization_summary.csv"


def load(p):
    if not os.path.isfile(p):
        return None
    return {r["terrain"]: 100.0 * float(r["overall_success_rate"])
            for r in csv.DictReader(io.open(p, encoding="utf-8", newline=""))}


a, b = load(A), load(B)
if not a or not b:
    print("  대조할 자료가 아직 없다")
else:
    print("  평가 장치 대조 · v2g2@3000 · unseen10 · d0.5 · 1.0 m/s")
    print("  %-22s %10s %10s %8s" % ("지형", "cuda:1 (원래)", "cuda:0 (새로)", "차"))
    diff = 0
    for t in sorted(set(a) | set(b)):
        x, y = a.get(t), b.get(t)
        d = None if (x is None or y is None) else y - x
        if d not in (None, 0.0):
            diff += 1
        print("  %-22s %10s %10s %8s" % (
            t, "없음" if x is None else "%.0f" % x,
            "없음" if y is None else "%.0f" % y,
            "없음" if d is None else "%+.0f" % d))
    print()
    print("  값이 다른 지형 %d / %d" % (diff, len(set(a) | set(b))))
    if diff == 0:
        print("  **평가 장치는 결과를 바꾸지 않는다** (이 칸에서)")
    else:
        print("  ** 장치가 결과를 바꾼다. 스윕 표에 주의를 달아야 한다 **")
PY

echo "[$(date +%H:%M:%S)] 표를 다시 굽는다"
"$PY" _out/loop/v2_sweep.py --out sim/eval/results/20260928-v2-sweep
