#!/usr/bin/env bash
# 갤러리가 끝나기를 기다렸다가 **지형 한 장** 을 찍고 멈춘다.
#
# 분류: 운영
# 작성: 오흥재 · 2026-09-28
# 근거: 팀장 지시 「갤러리 끝나면 순서대로 다 돌려」 · 앞선 지시 「지형 16장
#       한 장 먼저 보여줘」
# 요지: Isaac 은 한 판씩만 돈다. 그래서 «기다렸다가» 잇는다
#
# **이 파일을 도는 중에 고치지 않는다.**
#
# ## 왜 한 장에서 멈추나
#
# 1 차에서 16장을 한 번에 돌려 **전부 버렸다.** 카메라가 무너진 그림이었는데
# 밝기 관문이 통과라고 말했다. 그래서 한 장을 먼저 내고 **사람이 보고**
# 나머지를 건다.
#
# ## 왜 갤러리를 기다리나
#
# Isaac 두 판을 같이 돌리면 둘 다 멈춘다. 오늘 두 번 당했고, 두 번 다
# 고아 프로세스가 물고 있던 것이었다. 그래서 **끝난 것을 확인하고** 잇는다.
set -u
cd "$(dirname "$0")/../.." || exit 1

say() { echo "[$(date +%H:%M:%S)] $*"; }

GAL=sim/eval/results/20260928-v2-gallery/web
WANT=48

say "갤러리를 기다린다 (지금 $(ls $GAL/*.mp4 2>/dev/null | wc -l) / $WANT)"

stall=0
last=-1
while true; do
  n=$(ls $GAL/*.mp4 2>/dev/null | wc -l)
  [ "$n" -ge "$WANT" ] && break

  if [ "$n" -eq "$last" ]; then
    stall=$((stall+1))
  else
    stall=0; last=$n
  fi

  # 20 분 (30 초 x 40) 동안 한 칸도 안 늘면 멈춘 것으로 본다.
  if [ "$stall" -ge 40 ]; then
    say "** 갤러리가 20 분간 안 늘었다 ($n / $WANT). 잇지 않고 멈춘다 **"
    exit 1
  fi

  sleep 30
done

say "갤러리 $WANT 칸 완료"

# 남은 Isaac 프로세스를 확인한다. TaskStop 은 껍데기만 죽인다.
say "남은 Isaac 프로세스 확인"
for i in 1 2 3 4 5 6; do
  left=$(powershell -NoProfile -Command "@(Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { \$_.CommandLine -match 'record_terrain_demo|render_gallery' }).Count" 2>/dev/null | tr -d '\r')
  [ -z "$left" ] && left=0
  say "  남은 것 $left"
  [ "$left" = "0" ] && break
  sleep 10
done

# ---------------------------------------------------------------- 지형 한 장
say "지형 한 장 먼저 (rails) · 격자 2x2"
cp _out/loop/shoot_terrains.sh _out/loop/.shots_running.sh
rm -rf sim/eval/results/20260928-terrain-shots
SHOT_ONE=rails SHOT_DEV=cuda:0 bash _out/loop/.shots_running.sh 2>&1 | tail -20

say "한 장 결과"
ls -l sim/eval/results/20260928-terrain-shots/stills/*.png 2>/dev/null | awk '{print "  "$5" bytes  "$9}'
say "여기서 멈춘다. 사람이 보고 나머지를 건다"
