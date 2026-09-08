#!/bin/bash
VOL="${VOL:-/data/$USER}"   # 네트워크 볼륨. 다른 자리면 VOL=... 로 덮어쓴다
HERE="$(cd "$(dirname "$0")" && pwd)"   # 형제 러너를 자기 위치 기준으로 부른다
# 지형검사 18개 -> 전부 통과했을 때만 평가(브리지4 + FLAT7 + ROUGH7 + 영상14).
# 🔴 관문을 사람의 기억이 아니라 여기서 강제한다. 하나라도 실패하면 평가를 시작하지 않는다.
O=$VOL/experiments/20260907_gap-threshold
bash "$HERE/run_audits.sh" > $O/RUNNER_audit.log 2>&1
if ! grep -q "AUDITS DONE fail=0" $O/RUNNER_audit.log; then
  echo "🔴 지형검사 실패 - 평가를 시작하지 않는다"
  grep -E "FAIL|실패" $O/RUNNER_audit.log
  exit 1
fi
echo "지형검사 18/18 통과. 평가 시작 $(date -u +%H:%M:%S)"
bash "$HERE/run_gap.sh"
