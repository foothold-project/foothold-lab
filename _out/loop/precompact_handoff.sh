#!/usr/bin/env bash
# 자동 압축이 «일어나기 직전에» 지금 상태를 문서로 떨군다.
#
# 분류: 운영
# 작성: 오흥재 · 2026-09-27
# 근거: 팀장 지적 「내가 Context 가 얼마나 차는지 단번에 파악할 UI 같은 것이
#       필요하고, 아니면 50 % · 75 % 찰 때 어떻게 처리할지 자동화해서 hook 으로
#       인식하는 방향성이 중요하다. 그래야 다음에도 Auto Compact 가 안 일어난다」
#
# 훅으로 «할 수 있는 것과 없는 것» `확인됨` (공식 문서 2026-09-27)
#   할 수 없다  어떤 훅도 **토큰 수나 context 사용량을 받지 않는다.**
#               그래서 「50 % 찼다」 「75 % 찼다」 알림은 훅으로 «못 만든다».
#   할 수 있다  **PreCompact** 는 압축 «직전» 에 돌고, matcher 로
#               `manual` 과 `auto` 를 가른다. 곧 「자동 압축이 지금 시작된다」는
#               신호는 받을 수 있다.
#
# 그래서 이 파일이 하는 일
#   압축을 «막지는» 못한다. 대신 압축 직전에 지금 상태를 파일로 남긴다.
#   압축 뒤 요약본만 받아도 이 파일을 읽으면 흐름이 이어진다.
#
# 훅은 stdin 으로 JSON 을 받는다. 실패해도 세션을 막지 않게 «항상 0» 으로 끝낸다.

# 자리는 기기에 묶지 않는다 (2026-10-09). 이 훅은 저장소의 .claude/settings.json 에 걸려
# 이 프로젝트 세션에서만 돈다. 저장소는 Claude Code 가 주는 CLAUDE_PROJECT_DIR, 없으면 이 파일 자리로 찾는다.
# 학습 로그 자리는 기기마다 다르므로 환경 변수로 바꿀 수 있고, 없으면 지금까지의 기본값을 쓴다.
LAB="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." 2>/dev/null && pwd)}"
OUT="$LAB/_out/loop/HANDOFF-precompact.md"
RUNS="${FOOTHOLD_RUNS_DIR:-C:/isaac/IsaacLab/logs/rsl_rl/unitree_go2_gap_nvidia}"
LOGS="${FOOTHOLD_RUN_LOGS_DIR:-C:/isaac/IsaacLab/logs/gap_run_logs}"
# PowerShell 이 없는 기기(Linux · macOS)에서는 그 줄만 건너뛴다.
PS=$(command -v powershell 2>/dev/null || command -v pwsh 2>/dev/null)

IN=$(cat 2>/dev/null)
TRIG=$(echo "$IN" | grep -oE '"(trigger|matcher|reason)"[[:space:]]*:[[:space:]]*"[^"]*"' | head -1)

{
  echo "# 압축 직전 인계"
  echo
  echo "> 자동 생성 · $(date '+%Y-%m-%d %H:%M:%S')"
  echo "> 방아쇠: ${TRIG:-읽지 못함}"
  echo "> 이 파일은 PreCompact 훅이 씁니다. 압축 뒤 요약본만 받았으면 이것을 먼저 읽으십시오."
  echo
  echo '## 도는 학습'
  [ -n "$PS" ] && "$PS" -NoProfile -Command \
    "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { \$_.CommandLine -match 'run_name' } | ForEach-Object { if (\$_.CommandLine -match 'run_name +([^ ]+)') { '- ' + \$matches[1] } }" \
    2>/dev/null | tr -d '\r'
  echo
  echo '## 런마다 어디까지'
  echo
  echo '| 런 | 마지막 iteration | 마지막 체크포인트 | 완주 | 오류 |'
  echo '|---|---|---|---|---|'
  for L in $(ls -t "$LOGS"/*.log 2>/dev/null | head -12); do
    n=$(basename "$L" .log | sed 's/^[0-9]\{8\}_[0-9]\{6\}_//')
    it=$(grep -o "Learning iteration *[0-9]*" "$L" 2>/dev/null | tail -1 | grep -o '[0-9]*')
    d=$(ls -d "$RUNS"/*"$n"* 2>/dev/null | head -1)
    ck=$(ls "$d"/model_*.pt 2>/dev/null | sed 's/.*model_//;s/\.pt//' | sort -n | tail -1)
    fin=$([ -f "$d/model_3000.pt" ] && echo "예" || echo "아니오")
    err=$(grep -o "RuntimeError:.*" "$L" 2>/dev/null | tail -1 | cut -c1-42)
    echo "| \`$n\` | ${it:-?} | ${ck:-없음} | $fin | ${err:-} |"
  done
  echo
  echo '## 예약 작업'
  [ -n "$PS" ] && "$PS" -NoProfile -Command \
    "Get-ScheduledTask -TaskName 'FOOTHOLD-*' -EA SilentlyContinue | ForEach-Object { '- ' + \$_.TaskName + ' : ' + \$_.State }" \
    2>/dev/null | tr -d '\r'
  echo
  echo '## 저장소'
  echo '```'
  cd "$LAB" 2>/dev/null && git log --oneline -5 2>/dev/null
  echo
  git -C "$LAB" status --porcelain 2>/dev/null | head -15
  echo '```'
  echo
  echo '## 열려 있는 결정'
  echo
  echo '- `inbox/jay/20260927-methodology/DECISIONS-resume-vs-scratch.md` · 상태: 팀장 결정 대기'
  echo '- `inbox/jay/20260927-methodology/QUESTIONS-20260927.md` · 팀장 물음 원본'
  echo '- `_out/loop/supervisor.log` · 감독 스크립트 기록'
} > "$OUT" 2>/dev/null

echo '{}'
exit 0
