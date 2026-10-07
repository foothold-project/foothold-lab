#!/usr/bin/env bash
# 회전 낙상을 «장면» 으로 보여 주는 컷. v2a 대 v2b.
#
# 분류: 운영
# 작성: 오흥재 · 2026-09-28
# 근거: 팀장 지시 「회전 낙상 v2a, v2b 또한 영상으로 보여줘서 글과 함께 설명으로
#       보여지면 좋겠다」
# 요지: `rel_standing_envs` 를 0.02 에서 0.10 으로 올린 «한 칸» 이 회전 낙상을
#       0.9219 에서 0.0625 로 바꿨다. 그것을 숫자가 아니라 장면으로 보인다.
#
# **이 파일을 도는 중에 고치지 않는다.**
#
# ## 실측 · 회전 낙상 (64 판 중 넘어진 판)
#
#   체크포인트      1500      2000      2500      3000
#   v2a           0.9219    0.1562    0.2812    0.3438     네 점 전부 미달
#   v2b           0.0625    0        0.2969    0.04688     네 점 중 셋 통과
#
# **iter1500 이 가장 크게 갈린다.** 64 판 중 v2a 는 59 판이 넘어지고 v2b 는
# 4 판이다. 그래서 그 시점을 찍는다.
#
# 두 판은 `rel_standing_envs` 말고 다른 칸이 전부 같다. 그래서 나란히 놓으면
# **그 한 칸의 효과** 를 보는 것이 된다.
set -u
cd "$(dirname "$0")/../.." || exit 1
PY=C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe
L=C:/isaac/IsaacLab/logs/rsl_rl/unitree_go2_gap_nvidia
OUT=sim/eval/results/20260928-turnfall-clips
export OMNI_KIT_ACCEPT_EULA=YES

V2A=$L/2026-09-21_11-03-23_20260921_v2a_seed42_iter3000/model_1500.pt
V2B=$L/2026-09-21_11-03-28_20260921_v2b_seed42_iter3000/model_1500.pt

say() { echo "[$(date +%H:%M:%S)] $*"; }
for f in "$V2A" "$V2B"; do [ -f "$f" ] || { say "** 없음 ** $f"; exit 1; }; done

# 축 2 의 `turn` 시나리오를 영상 켜고 돈다. env 는 기존 축 2 와 같은 64 로 둔다.
# **장치 인자를 안 준다** (`turn1024.sh` 머리말 참조).
for row in "v2a|$V2A" "v2b|$V2B"; do
  who="${row%%|*}"; ck="${row##*|}"
  o="$OUT/$who"
  if [ -f "$o/probe_manifest.json" ]; then say "건너뜀 (이미 있음) $who"; continue; fi
  mkdir -p "$o"
  say "$who iter1500 · turn · 영상 켜고 env 64"
  "$PY" sim/eval/eval_command_response.py \
    --checkpoint "$ck" --label "$who-iter1500" \
    --scenario turn --num_envs 64 --seed 42 --headless \
    --video --video_env 0 --video_width 1920 --video_height 1080 --video_crf 20 \
    --output_dir "$o" > "$OUT/$who.log" 2>&1
  rc=$?
  n=$(find "$o" -name "*.mp4" 2>/dev/null | wc -l)
  say "  exit=$rc · mp4 $n 편"
  [ "$n" -eq 0 ] && grep -oE '(RuntimeError|ValueError|Error):.*' "$OUT/$who.log" 2>/dev/null | tail -2
done

say "낙상 수를 읽는다"
"$PY" - <<'PY' 2>&1 | sed 's/^/          /'
import json, io, os, math
B = "sim/eval/results/20260928-turnfall-clips"


def wilson(k, n, z=1.959964):
    if not n or k is None:
        return (None, None)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - h) / d, (c + h) / d)


print("%-8s %8s %8s %10s %22s" % ("판", "env", "낙상", "비율", "Wilson 95 %"))
for who in ("v2a", "v2b"):
    f = os.path.join(B, who, "probe_manifest.json")
    if not os.path.isfile(f):
        print("%-8s 산출물이 없다" % who)
        continue
    s = (json.load(io.open(f, encoding="utf-8")).get("summary") or {}).get("turn") or {}
    n, k = s.get("envs") or 0, s.get("fell_count")
    lo, hi = wilson(k, n)
    print("%-8s %8d %8s %10.4f %22s" % (
        who, n, k, (k / n if n else float("nan")),
        "[%.4f, %.4f]" % (lo, hi) if lo is not None else "없음"))
PY

say "프레임 전수 검사"
"$PY" _out/loop/video_scan.py --allow-black --json "$OUT/scan.json" "$OUT/*/*.mp4" \
  2>&1 | sed 's/^/          /'

say "미리보기 png"
"$PY" - <<'PY' 2>&1 | sed 's/^/          /'
import os
try:
    import imageio.v2 as iio
    import numpy as np
except ImportError:
    print("imageio 가 없다"); raise SystemExit(0)
B = "sim/eval/results/20260928-turnfall-clips"
P = os.path.join(B, "previews"); os.makedirs(P, exist_ok=True)
n = 0
for dirpath, _d, files in os.walk(B):
    if "previews" in dirpath:
        continue
    for f in files:
        if not f.endswith(".mp4"):
            continue
        tag = os.path.relpath(os.path.join(dirpath, f), B).replace(os.sep, "_")[:-4]
        out = os.path.join(P, tag + ".png")
        if os.path.isfile(out):
            n += 1; continue
        try:
            r = iio.get_reader(os.path.join(dirpath, f))
            c = r.count_frames()
            # 회전은 뒤로 갈수록 계단이 커진다. 3/4 지점을 뽑는다.
            im = np.asarray(r.get_data(max(0, int(c * 0.75))))
            r.close()
            iio.imwrite(out, im); n += 1
        except Exception as exc:                                   # noqa: BLE001
            print("  ** %s · %s **" % (tag, exc))
print("미리보기 %d 장" % n)
PY
say "끝"
