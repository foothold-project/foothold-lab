#!/usr/bin/env bash
# 「네 판 + 검증 둘」이 «다» 끝날 때까지 기다렸다가 한 번에 깨운다.
#
# 분류: 운영
# 작성: 오흥재 · 2026-09-27
# 근거: 팀장 지시 「네 판이랑 검증 둘 다 끝나면 보고해」 · _out/loop/RULES.md
# 요지: 학습 다섯 -> 평가 -> 판정 -> 상호작용 둘 -> astra 문서 -> 깨운다.
#
# 이 파일이 지키는 것 (내가 «틀렸던» 자리들)
#   @()  으로 싼다            .Count 가 «정확히 1 개» 일 때 빈다
#   -1   로 「모른다」를 낸다   조회 실패가 「없음」과 구별되어야 한다
#   0 을 두 번 연속 확인       프로세스 교체 사이의 빈 순간에 안 빠져나오게
#   nohup & 를 «안» 쓴다       배경 작업 «자체» 가 기다려야 나를 깨운다
#   침묵이 성공이 아니게        죽어도 «무엇이 어떻게» 됐는지 적고 넘어간다

set -u
set -o pipefail
cd "C:/Users/AI-WS01/Desktop/jay/인공지능사관학교/foothold-lab" || exit 1

RUNS="C:/isaac/IsaacLab/logs/rsl_rl/unitree_go2_gap_nvidia"
LOGS="C:/isaac/IsaacLab/logs/gap_run_logs"
A1="sim/eval/results/20260923-v2rs"
A2="sim/eval/results/20260923-v2rs-axis2"
ASTRA="C:/Users/AI-WS01/orca/workspaces/foothold-lab/crash-seed43/inbox/jay/20260923-lineage/AUDIT13-holdout.md"

WATCH="v2LG-log-feet01-s44 s42A-scalar-f001-noopt s42B-scalar-f01-noopt s42C-log-f001 s42D-log-f01"

say() { echo "[모음 $(date '+%m/%d %H:%M:%S')] $*"; }

count_ps() {   # $1 = 명령줄 정규식
  local out
  out=$(powershell -NoProfile -Command \
    "@(Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { \$_.CommandLine -match '$1' }).Count" \
    2>/dev/null | tr -d '\r ')
  case "$out" in ''|*[!0-9]*) echo -1 ;; *) echo "$out" ;; esac
}

# ------------------------------------------------------ 1 · 학습이 다 끝나기를
say "학습 다섯이 끝나기를 기다린다 · $WATCH"
ZERO=0; UNK=0
while :; do
  N=$(count_ps 'run_name')
  if [ "$N" = "-1" ]; then
    UNK=$((UNK+1)); ZERO=0
    say "  프로세스를 «못 읽었다» ($UNK 회). 계속 기다린다"
    [ "$UNK" -ge 20 ] && { say "** 스무 번 연속 못 읽었다. 멈춘다 **"; exit 3; }
  elif [ "$N" = "0" ]; then
    UNK=0; ZERO=$((ZERO+1)); [ "$ZERO" -ge 2 ] && break
  else
    UNK=0; ZERO=0
  fi
  sleep 180
done
say "도는 학습이 없다"

for r in $WATCH; do
  if ls "$RUNS"/*"$r"*/model_3000.pt >/dev/null 2>&1; then
    say "  $r · 완주"
  else
    L=$(ls -t "$LOGS"/*"$r"*.log 2>/dev/null | head -1)
    LAST=$(grep -o "Learning iteration *[0-9]*" "$L" 2>/dev/null | tail -1)
    ERR=$(grep -o "RuntimeError:.*" "$L" 2>/dev/null | tail -1 | cut -c1-60)
    say "  $r · **완주 못 함** · ${LAST:-판 수 못 읽음} · ${ERR:-오류 문구 없음}"
  fi
done

# ------------------------------------------------------ 2 · 등록과 평가
say "끝난 학습을 상태 파일에 반영한다"
python _out/loop/register.py 2>&1 | sed 's/^/          /'

say "평가를 건다 (두 축을 두 GPU 에 나눈다)"
python _out/loop/eval_runner.py 2>&1 | tail -3 | sed 's/^/          /'

say "평가가 끝나기를 기다린다"
ZERO=0; UNK=0
while :; do
  E=$(count_ps 'eval_')
  if [ "$E" = "-1" ]; then
    UNK=$((UNK+1)); ZERO=0
    [ "$UNK" -ge 20 ] && { say "** 평가 프로세스를 스무 번 연속 못 읽었다 **"; break; }
  elif [ "$E" = "0" ]; then
    UNK=0; ZERO=$((ZERO+1)); [ "$ZERO" -ge 2 ] && break
  else
    UNK=0; ZERO=0
  fi
  sleep 60
done
say "도는 평가가 없다"

for r in $WATCH; do
  a1=$(find "$A1" -path "*$r*" -name generalization_summary.csv 2>/dev/null | wc -l)
  a2=$(find "$A2" -path "*$r*" -name probe_manifest.json 2>/dev/null | wc -l)
  say "  $r · 축1 $a1/24 · 축2 $a2/4"
done

# ------------------------------------------------------ 3 · 판정과 상호작용
say "판정문을 낸다"
for r in v2b-r v2g-feetair1 v2g2-feetair01 v2g3-feetair01-s43 v2g4-feetair01-s44 \
         v2n-noise02 v2s-stones10 v2sg-stones10feet01 v2L-logstd-s44 $WATCH; do
  python _out/loop/verdict.py --run "$r" \
    --out "inbox/jay/20260923-lineage/VERDICT-$r.md" >/dev/null 2>&1 \
    && say "  판정문 $r" || say "  판정문 «못 냈다» $r"
done

say "상호작용을 «두 배치» 다 센다"
{
  python _out/loop/interaction.py --design stones-x-feet
  echo
  python _out/loop/interaction.py --design logstd-x-feet
} > _out/loop/interaction-out.txt 2>&1
sed 's/^/          /' _out/loop/interaction-out.txt

# ------------------------------------------------------ 4 · astra 문서
say "astra 의 AUDIT13 을 기다린다 (파일이 «있고» 60 초간 «안 자라면» 끝난 것)"
STABLE=0; LAST=-1; TICK=0
while :; do
  TICK=$((TICK+1))
  [ "$TICK" -gt 240 ] && { say "** astra 문서가 두 시간째 안 나온다. 사람이 확인할 것 **"; break; }
  if [ -f "$ASTRA" ]; then
    SZ=$(stat -c%s "$ASTRA" 2>/dev/null || echo 0)
    if [ "$SZ" = "$LAST" ] && [ "$SZ" -gt 0 ]; then STABLE=$((STABLE+1)); else STABLE=0; fi
    LAST="$SZ"
    [ "$STABLE" -ge 2 ] && { say "astra 문서 «끝났다» · $SZ bytes"; cp "$ASTRA" inbox/jay/20260923-lineage/AUDIT13-holdout.md; break; }
  fi
  sleep 30
done

# ------------------------------------------------------ 5 · 알림
say "텔레그램을 보낸다"
python _out/loop/heartbeat.py 2>&1 | sed 's/^/          /'

say "**다 끝났다.** 판정문 · interaction-out.txt · AUDIT13 둘을 읽을 것"
