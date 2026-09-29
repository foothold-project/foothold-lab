#!/usr/bin/env bash
# `stop` 과 `hold` 도 1024 env 로 재서 **아홉 칸을 같은 표본으로 닫는다.**
#
# 분류: 진단
# 작성: 오흥재 · 2026-09-28
# 근거: `turn1024.md` 마지막 줄 「이 표는 아홉 칸 판정이 아니다. 다섯 칸이다」
# 요지: `turn` 다섯 칸만 1024 로 재 놓고 아홉 칸을 말하면 안 된다.
#       나머지 넷을 같은 표본으로 재서 두 후보의 아홉 칸을 1024 env 로 닫는다.
#
# ## 이것이 「통과할 때까지 다시 돌리기」가 아닌 이유
#
# 그 넷은 64 env 에서 **두 후보 모두 여유가 컸다.**
#   정지 낙상      0        문턱 <= 0.03
#   유지 낙상      0        문턱 <= 0.03
#   유지 잔류속도   ~0.0005  문턱 <= 0.005   (열 배 여유)
#   유지 목표각    ~0.0003  문턱 <= 0.01    (서른 배 여유)
# 표본을 늘려서 이 넷이 «통과로 바뀔» 여지가 없다. **미달이 드러날 수만 있다.**
# 한쪽으로만 움직이는 검사라 사후 선택이 안 된다.
#
# ## 미리 못 박는 것
#   표본   env 1024 · stop 과 hold · seed 42 · 칸마다 «한 번»
#   대상   v2b-r@2500 · v2g2-feetair01@3000 «둘만»
#   판정   낙상 두 칸은 Wilson 95 % · 잔류속도와 목표각은 값 그대로 문턱 대조
#   기록   결과가 어느 쪽이든 그대로 싣는다. 미달이 나오면 그것을 적는다
#
# 장치 인자를 안 준다. 까닭은 `turn1024.sh` 머리말에 있다.
set -u
cd "$(dirname "$0")/../.." || exit 1
PY=C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe
L=C:/isaac/IsaacLab/logs/rsl_rl/unitree_go2_gap_nvidia
OUT=sim/eval/results/20260928-stophold1024
N="${SH_ENVS:-1024}"
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
  echo "[$(date +%H:%M:%S)] $tag · stop,hold · env $N 시작"
  "$PY" sim/eval/eval_command_response.py \
    --checkpoint "$ckpt" \
    --label "$tag" \
    --scenario stop,hold \
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
OUT = "sim/eval/results/20260928-stophold1024"
OLD = "sim/eval/results/20260923-v2rs-axis2"
# (프로브, 칸, 연산, 문턱) · `verdict_manifest.py:80-87` 에서 그대로 가져왔다
GATES = (
    ("stop", "fell_ratio", "<=", 0.03, "정지 낙상"),
    ("hold", "fell_ratio", "<=", 0.03, "유지 낙상"),
    ("hold", "residual_speed_mps", "<=", 0.005, "유지 잔류속도"),
    ("hold", "joint_target_delta_tail", "<=", 0.01, "유지 목표각"),
)


def wilson(k, n, z=1.959964):
    if not n or k is None:
        return (None, None)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - h) / d, (c + h) / d)


def load(root, tag):
    f = os.path.join(root, tag, "probe_manifest.json")
    if not os.path.isfile(f):
        return None
    return json.load(io.open(f, encoding="utf-8")).get("summary") or {}


tags = ("v2b-r-iter2500", "v2g2-feetair01-iter3000")
print("  %-26s %-14s %12s %12s %s" % ("판", "칸", "64 env", "1024 env", "1024 판정"))
for tag in tags:
    a, b = load(OLD, tag), load(OUT, tag)
    if b is None:
        print("  %-26s 1024 env 산출물이 없다" % tag)
        continue
    for probe, key, op, th, label in GATES:
        sa = (a or {}).get(probe) or {}
        sb = b.get(probe) or {}
        va, vb = sa.get(key), sb.get(key)
        n = sb.get("envs") or 0
        if key == "fell_ratio":
            k = sb.get("fell_count")
            lo, hi = wilson(k, n)
            if hi is None:
                verdict = "못 쟀다"
            elif hi <= th:
                verdict = "**통과** [%.4f, %.4f]" % (lo, hi)
            elif lo > th:
                verdict = "**미달** [%.4f, %.4f]" % (lo, hi)
            else:
                verdict = "미확인 [%.4f, %.4f]" % (lo, hi)
        else:
            verdict = ("**통과**" if (vb is not None and vb <= th)
                       else "**미달**" if vb is not None else "못 쟀다")
        f = lambda x: "없음" if x is None else ("%.6g" % x)
        print("  %-26s %-14s %12s %12s %s (문턱 %s %g)" % (
            tag, label, f(va), f(vb), verdict, op, th))
    print()
PY
