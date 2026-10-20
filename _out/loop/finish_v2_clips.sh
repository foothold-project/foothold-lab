#!/usr/bin/env bash
# v2 갤러리 컷을 **48 칸까지** 끝내고 검사까지 돌린다.
#
# 분류: 운영
# 작성: 오흥재 · 2026-09-28
# 근거: 팀장 지시 「48칸 다 굽고 영상 랜더 된 결과 제대로 문제 없는지 실측으로
#       눈으로 보고 확인한 뒤 site에게 말해서 웹까지 올려」
# 요지: 앞 작업이 끝나기를 «기다린 뒤» 정리 · 렌더 · HUD · 전수 검사 · 미리보기
#       뽑기까지 한 줄로 간다. 중간에 사람이 안 껴도 된다.
#
# ## 이 파일을 «고치지 않는다»
#
# bash 는 스크립트를 조금씩 읽는다. 도는 중에 고치면 오프셋이 밀려 없는 문법
# 오류로 죽고, **뒤쪽 단계가 조용히 안 돈다.** 오늘 실제로 그렇게 HUD 와 전수
# 검사를 통째로 건너뛰었고 종료 코드는 0 이었다. 고칠 것이 생기면 이 파일을
# 그대로 두고 끝나게 둔 뒤 새로 돌린다.
#
# ## 단계
#   0 앞 렌더가 끝나기를 기다린다 (파일 잠금 때문에 정리가 실패한다)
#   1 폴더 이름 정리 · 중복과 덜 구운 것 제거
#   2 빈 칸 렌더 · 16 지형 x 3 속도 = 48
#   3 HUD 패스
#   4 프레임 «전수» 검사
#   5 칸마다 가운데 프레임을 png 로 뽑는다 (사람이 눈으로 볼 자료)
set -u
cd "$(dirname "$0")/.." || exit 1
cd .. || exit 1
PY=C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe
OUT=sim/eval/results/20260928-v2-clips
DEV="${RENDER_DEV:-cuda:0}"
export OMNI_KIT_ACCEPT_EULA=YES

say() { echo "[$(date +%H:%M:%S)] $*"; }

running() {
  powershell -NoProfile -Command \
    "@(Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { \$_.CommandLine -match 'record_terrain_demo' }).Count" \
    2>/dev/null | tr -d '\r '
}

# ------------------------------------------------------------ 0 · 기다린다
say "앞 렌더가 끝나기를 기다린다"
for i in $(seq 1 120); do            # 최대 60 분
  n=$(running)
  case "$n" in ''|*[!0-9]*) n=-1 ;; esac
  if [ "$n" = "0" ]; then say "  앞 렌더 없음. 이어서 간다"; break; fi
  [ $((i % 10)) -eq 0 ] && say "  아직 $n 개 · $((i / 2)) 분째"
  sleep 30
done

# ------------------------------------------------------------ 1 · 정리
say "폴더 이름을 정리한다"
"$PY" _out/loop/rename_cuts.py --write 2>&1 | sed 's/^/          /'
RC=$?
if [ "$RC" -ne 0 ]; then
  say "** 정리가 실패했다 (종료 $RC). 여기서 멈춘다 **"
  exit 1
fi

# ------------------------------------------------------------ 2 · 48 칸
say "빈 칸을 굽는다 (16 지형 x 3 속도 = 48)"
RENDER_DEV="$DEV" RENDER_ONLY=axis1 bash _out/loop/.render48.sh 2>&1 | sed 's/^/          /'

# ------------------------------------------------------------ 3 · 칸 수 확인
say "칸을 센다"
"$PY" - <<'PY' 2>&1 | sed 's/^/          /'
import io, json, os
C = "sim/eval/results/20260928-v2-clips/cuts"
T = ['discrete_obstacles', 'wave', 'stepping_stones', 'gap', 'pit', 'rails',
     'star', 'floating_ring', 'repeated_boxes', 'repeated_cylinders',
     'pyramid_stairs', 'pyramid_stairs_inv', 'boxes', 'random_rough',
     'hf_pyramid_slope', 'hf_pyramid_slope_inv']
want = {"%s-v%s" % (t, s) for t in T for s in ("0.5", "1", "1.5")}
have = set()
broken = []
for n in sorted(os.listdir(C)):
    d = os.path.join(C, n)
    if not os.path.isdir(d):
        continue
    js = [f for f in os.listdir(d) if f.endswith(".json")]
    mp4 = [f for f in os.listdir(d)
           if f.endswith(".mp4") and not f.endswith(".hud.mp4")]
    if js and mp4:
        have.add(n)
    else:
        broken.append(n)
print("목표 %d · 있는 것 %d · 빠진 것 %d" % (len(want), len(want & have), len(want - have)))
for n in sorted(want - have):
    print("  빠짐 %s" % n)
for n in broken:
    print("  ** 덜 구움 %s **" % n)
PY

# ------------------------------------------------------------ 4 · 미리보기 png
say "칸마다 가운데 프레임을 png 로 뽑는다 (눈으로 볼 자료)"
"$PY" - <<'PY' 2>&1 | sed 's/^/          /'
import io, json, os
try:
    import imageio.v2 as iio
    import numpy as np
except ImportError:
    print("imageio 가 없어 미리보기를 못 뽑는다")
    raise SystemExit(0)

C = "sim/eval/results/20260928-v2-clips/cuts"
P = "sim/eval/results/20260928-v2-clips/previews"
os.makedirs(P, exist_ok=True)
n = 0
for name in sorted(os.listdir(C)):
    d = os.path.join(C, name)
    if not os.path.isdir(d):
        continue
    hud = [f for f in os.listdir(d) if f.endswith(".hud.mp4")]
    raw = [f for f in os.listdir(d)
           if f.endswith(".mp4") and not f.endswith(".hud.mp4")]
    pick = os.path.join(d, (hud or raw)[0]) if (hud or raw) else None
    if not pick:
        continue
    out = os.path.join(P, "%s.png" % name)
    if os.path.isfile(out):
        n += 1
        continue
    try:
        r = iio.get_reader(pick)
        cnt = r.count_frames()
        f = np.asarray(r.get_data(max(0, cnt // 2)))
        r.close()
        iio.imwrite(out, f)
        n += 1
    except Exception as exc:                                   # noqa: BLE001
        print("  ** %s · %s **" % (name, exc))
print("미리보기 %d 장 · %s" % (n, P))
PY

say "끝. 다음은 사람이 눈으로 본다"
