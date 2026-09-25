#!/usr/bin/env bash
# 학습 -> 평가 -> 판정 -> 상호작용 을 «한 사슬» 로 돈다.
#
# 분류: 운영
# 작성: 오흥재 · 2026-09-26
# 근거: 2026-09-25 팀장 지적 · 「완료되면 다음 작업 진행하겠습니다 라고 해도
#       그 사항이 안 지켜져서 계속 중간에 체크를 내가 손으로 하고 있네」
# 요지: 사슬 중간에 사람이 필요 없게 한다. 끝에서 «한 번» 깨운다.
#
# 왜 이 모양인가
#   전에는 「평가를 거는 명령」을 배경에 뒀다. 그것이 30 초 뒤 끝나서
#   내가 «걸었다» 만 확인하고 손을 뗐다. 이 스크립트는 «끝날 때까지» 막는다.
#
# 침묵이 성공이 아니게
#   학습이 죽어도, 평가가 죽어도 빠져나와 «무엇이 어떻게 됐는지» 적는다.

set -u
cd "C:/Users/AI-WS01/Desktop/jay/인공지능사관학교/foothold-lab" || exit 1

RUNS="C:/isaac/IsaacLab/logs/rsl_rl/unitree_go2_gap_nvidia"
LOGS="C:/isaac/IsaacLab/logs/gap_run_logs"
A1="sim/eval/results/20260923-v2rs"
A2="sim/eval/results/20260923-v2rs-axis2"
WATCH="v2sg-stones10feet01 v2g3-feetair01-s43"

say() { echo "[사슬 $(date '+%m/%d %H:%M:%S')] $*"; }

trainers_left() {
  powershell -NoProfile -Command \
    "(Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { \$_.CommandLine -match 'run_name' }).Count" \
    2>/dev/null | tr -d '\r '
}
evals_left() {
  powershell -NoProfile -Command \
    "(Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { \$_.CommandLine -match 'eval_' }).Count" \
    2>/dev/null | tr -d '\r '
}

# ---------------------------------------------------------------- 1 단계 · 학습
say "학습이 끝나기를 기다린다 · $WATCH"
while :; do
  N=$(trainers_left)
  [ "${N:-0}" = "0" ] && break
  sleep 120
done
say "도는 학습이 없다"

for r in $WATCH; do
  if ls "$RUNS"/*"$r"*/model_3000.pt >/dev/null 2>&1; then
    say "  $r · 완주 (model_3000.pt 있음)"
  else
    LAST=$(grep -o "Learning iteration *[0-9]*" "$LOGS"/*"$r"*.log 2>/dev/null | tail -1)
    ERR=$(grep -o "RuntimeError:.*" "$LOGS"/*"$r"*.log 2>/dev/null | tail -1)
    say "  $r · **완주 못 함** · $LAST · ${ERR:-오류 문구 없음}"
  fi
done

# ------------------------------------------------- 2 단계 · 등록과 평가 걸기
say "끝난 학습을 상태 파일에 반영한다"
python _out/loop/register.py 2>&1 | sed 's/^/          /'

say "평가를 건다"
python _out/loop/eval_runner.py 2>&1 | tail -4 | sed 's/^/          /'

# ---------------------------------------------------------------- 3 단계 · 대기
say "평가가 끝나기를 기다린다"
STALL=0
while :; do
  E=$(evals_left)
  if [ "${E:-0}" = "0" ]; then
    STALL=$((STALL + 1))
    # 두 번 연속 0 이면 정말 끝난 것이다 (다음 건을 띄우는 사이의 0 을 피한다)
    [ "$STALL" -ge 2 ] && break
  else
    STALL=0
  fi
  sleep 60
done
say "도는 평가가 없다"

for r in $WATCH; do
  a1=$(find "$A1" -path "*$r*" -name generalization_summary.csv 2>/dev/null | wc -l)
  a2=$(find "$A2" -path "*$r*" -name probe_manifest.json 2>/dev/null | wc -l)
  say "  $r · 축1 $a1/24 · 축2 $a2/4"
done

# ---------------------------------------------------------- 4 단계 · 판정과 상호작용
say "판정문을 낸다"
for r in v2b-r v2g-feetair1 v2g2-feetair01 v2n-noise02 v2s-stones10 $WATCH; do
  if python _out/loop/verdict.py --run "$r" \
       --out "inbox/jay/20260923-lineage/VERDICT-$r.md" >/dev/null 2>&1; then
    say "  판정문 $r"
  else
    say "  판정문 «못 냈다» $r"
  fi
done

say "상호작용을 센다"
python _out/loop/interaction.py > _out/loop/interaction-out.txt 2>&1
sed 's/^/          /' _out/loop/interaction-out.txt

# ---------------------------------------------------------------- 5 단계 · 알림
say "텔레그램을 보낸다"
python _out/loop/heartbeat.py 2>&1 | sed 's/^/          /'

say "사슬 끝. 판정문과 _out/loop/interaction-out.txt 를 읽을 것."
