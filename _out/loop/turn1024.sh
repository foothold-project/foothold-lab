#!/usr/bin/env bash
# `turn` 한 칸을 **1024 env** 로 다시 잰다. 두 후보만.
#
# 분류: 진단
# 작성: 오흥재 · 2026-09-28
# 근거: 팀장 질문 「v2b-r 로 해야겠네? 둘다 비교 해봐야하나?」
# 묻는 것: `turn/fell_ratio` 문턱 0.10 을 두 후보가 «정말» 넘나 못 넘나.
#
# 지금 64 env 에서는 둘 다 «판정할 수 없다». Wilson 95 % 가 문턱을 품는다.
#   v2g2@3000    7/64 = 0.1094  [0.0540, 0.2090]   문턱 0.10 포함
#   v2b-r@2500   2/64 = 0.0312  [0.0086, 0.1070]   문턱 0.10 포함
#
# 비율이 유지된다고 보면 env 를 늘렸을 때 이렇게 갈린다.
#   env  128   v2g2 [0.0663, 0.1752] 포함   v2b-r [0.0122, 0.0776] **안 포함 · 통과 확정**
#   env 1024   v2g2 [0.0917, 0.1300] 포함   v2b-r [0.0222, 0.0438] 안 포함
#   env 2048   v2g2 [0.0966, 0.1236] 포함   v2b-r [0.0245, 0.0397] 안 포함
#
# **v2g2 는 표본을 늘려도 통과로 뒤집히지 않는다.** 점추정이 문턱 위다.
# 그래서 이 실험의 목적은 「v2g2 를 통과시키기」가 «아니다».
#   1. v2b-r@2500 의 2/64 가 «실력인지 운인지» 가른다.
#      이웃 점이 0.1094 (2000) 과 0.3125 (3000) 이라 한 점만 내려앉았다.
#   2. v2g2@3000 의 0.1094 가 문턱 위인지 아래인지 좁힌다.
#
# ## 미리 못 박는 것 (astra 검증 지적)
#
# 「통과할 때까지 다시 평가해서 좋은 결과만 채택해서는 안 된다」.
# 그래서 **돌리기 전에** 적는다.
#
#   표본        env 1024 · 시나리오 turn 만 · seed 42 · 한 번씩
#   판정        Wilson 95 % 가 0.10 을 품으면 «미확인» 으로 둔다. 다시 안 돌린다
#   대상        v2b-r@2500 · v2g2@3000 «둘만». 좋은 쪽을 찾으러 더 안 돈다
#   기록        이 결과가 어느 쪽이든 보고서에 그대로 싣는다
#
# 이 넷을 바꾸려면 이 파일을 고치고 그 이유를 커밋에 적어야 한다.
set -u
cd "$(dirname "$0")/../.." || exit 1
PY=C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe
L=C:/isaac/IsaacLab/logs/rsl_rl/unitree_go2_gap_nvidia
OUT=sim/eval/results/20260928-turn1024
# **장치 인자를 «안» 준다.** 두 가지 이유다.
#   1. `--device cuda:1` 은 sim 만 옮기고 `GRAVITY_VEC_W` 는 cuda:0 에 남아
#      16 초에 죽는다. 실측한 예외다.
#        RuntimeError: Expected all tensors to be on the same device,
#        but found at least two devices, cuda:1 and cuda:0!
#          articulation_data.py:790 projected_gravity_b
#   2. 기존 축 2 서른여섯 칸이 «장치 인자 없이» 나왔다
#      (`eval_runner.py:222-229` 의 argv 에 `--device` 가 없다. `AXIS2_DEVICE`
#      는 큐를 가르는 데만 쓰고 프로세스에 안 넘긴다). 기본값 `cuda:0` 이다.
#      장치를 바꾸면 그것이 두 번째 변수가 된다.
N="${TURN_ENVS:-1024}"
export OMNI_KIT_ACCEPT_EULA=YES

declare -a JOBS=(
  "v2b-r-iter2500|$L/2026-09-23_14-42-33_20260923_v2b-r_seed42_iter3000/model_2500.pt"
  "v2g2-feetair01-iter3000|$L/2026-09-25_17-29-36_20260925_v2g2-feetair01_seed42_iter3000/model_3000.pt"
)

mkdir -p "$OUT"
for row in "${JOBS[@]}"; do
  tag="${row%%|*}"; ckpt="${row##*|}"
  odir="$OUT/$tag"
  if [ -f "$odir/probe_manifest.json" ]; then
    echo "[$(date +%H:%M:%S)] 건너뜀 (이미 있음) $tag"; continue
  fi
  if [ ! -f "$ckpt" ]; then
    echo "[$(date +%H:%M:%S)] ** 체크포인트 없음 ** $ckpt"; continue
  fi
  echo "[$(date +%H:%M:%S)] $tag · turn · env $N · 장치 인자 없음 (기본 cuda:0) 시작"
  "$PY" sim/eval/eval_command_response.py \
    --checkpoint "$ckpt" \
    --label "$tag" \
    --scenario turn \
    --num_envs "$N" \
    --seed 42 \
    --headless \
    --output_dir "$odir" > "$OUT/$tag.log" 2>&1
  RC=$?
  if [ -f "$odir/probe_manifest.json" ]; then H="산출물 있음"; else H="** 산출물 없음 **"; fi
  echo "[$(date +%H:%M:%S)] $tag exit=$RC · $H"
done

echo "[$(date +%H:%M:%S)] 읽는다"
"$PY" - <<'PY'
import json, io, math, os
OUT = "sim/eval/results/20260928-turn1024"
TH = 0.10


def wilson(k, n, z=1.959964):
    if not n:
        return (None, None)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - h) / d, (c + h) / d)


print("  %-26s %8s %8s %10s %22s %s" % (
    "판", "env", "낙상", "비율", "Wilson 95 %", "문턱 0.10 판정"))
for tag in sorted(os.listdir(OUT)) if os.path.isdir(OUT) else []:
    f = os.path.join(OUT, tag, "probe_manifest.json")
    if not os.path.isfile(f):
        continue
    s = (json.load(io.open(f, encoding="utf-8")).get("summary") or {}).get("turn")
    if not isinstance(s, dict):
        print("  %-26s turn 요약이 없다" % tag)
        continue
    n = s.get("envs") or 0
    k = s.get("fell_count")
    lo, hi = wilson(k, n) if isinstance(k, int) else (None, None)
    if lo is None:
        verdict = "못 쟀다"
    elif hi < TH:
        verdict = "**통과** (구간이 문턱 아래)"
    elif lo > TH:
        verdict = "**미달** (구간이 문턱 위)"
    else:
        verdict = "미확인 (구간이 문턱을 품는다)"
    yf = s.get("yaw_follow_ratio") or {}
    print("  %-26s %8d %8s %10.4f %22s %s" % (
        tag, n, k, (k / n if n else float("nan")),
        "[%.4f, %.4f]" % (lo, hi) if lo is not None else "없음", verdict))
    if yf:
        print("  %-26s   요 추종비 %.3f ~ %.3f · 0.40 넘은 칸 %d/%d" % (
            "", min(yf.values()), max(yf.values()),
            sum(1 for v in yf.values() if v >= 0.40), len(yf)))
PY
