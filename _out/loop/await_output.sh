#!/usr/bin/env bash
# 검증자(astra·fable)의 «산출물 파일» 이 나올 때까지 막고 기다린다.
#
# 분류: 운영
# 작성: 오흥재 · 2026-09-26
# 근거: 2026-09-26 팀장 지적 (두 번째) · 「검증이 이미 끝났는데 보고 안 받고
#       멋대로 혼자 진행중이라고 파악하고 기다리고 있었네? 내가 분명 이
#       고질적인 문제 해결하라고 했는데?」
# 요지: **터미널 상태가 아니라 «파일» 을 본다.** 나오면 나를 깨우고
#       텔레그램도 보낸다.
#
# 왜 이것이 필요한가 · 내가 두 번 틀린 판별식
#   1 차 (2026-09-25)  «평가를 거는 명령» 을 배경에 뒀다. 30 초 뒤 끝나서
#                      「걸었다」만 확인하고 손을 뗐다. -> chain.sh 로 고쳤다
#   2 차 (2026-09-26)  astra 를 «터미널 status» 로 봤다. 그것은 「터미널이
#                      살아 있다」는 뜻이다. 산출물 파일을 «안 봤다».
#                      파일은 12:58 부터 있었고 내가 15:21 에 알았다.
#                      GPU 가 3 시간 놀았다.
#
#   판별식 · 검증이 끝났는가 = «그 검증자가 쓰기로 한 파일이 있고 더 안 자라는가»
#            터미널이 도는지가 «아니다». codex TUI 는 일이 끝나도 계속 산다.
#
# 돌리는 법
#   bash _out/loop/await_output.sh <파일경로> [설명] [최대분]
#
# 규칙 · **검증자를 띄울 때마다 이것을 «같이» 건다.** 안 걸면 또 기다린다.

set -u
cd "C:/Users/AI-WS01/Desktop/jay/인공지능사관학교/foothold-lab" || exit 1

F="${1:?산출물 파일 경로를 주십시오}"
WHAT="${2:-검증}"
MAXMIN="${3:-180}"

say() { echo "[대기 $(date '+%m/%d %H:%M:%S')] $*"; }

say "«$WHAT» 의 산출물을 기다린다 · $F"
say "  판별식 · 파일이 «있고» 60 초 동안 «안 자라면» 끝난 것이다"

START=$(date +%s)
STABLE=0
LAST=-1

while :; do
  NOW=$(date +%s)
  MIN=$(( (NOW - START) / 60 ))
  if [ "$MIN" -ge "$MAXMIN" ]; then
    say "** $MAXMIN 분을 넘겼다. 파일이 «안 나왔다». 검증자를 직접 확인할 것 **"
    exit 2
  fi

  if [ -f "$F" ]; then
    SZ=$(stat -c%s "$F" 2>/dev/null || echo 0)
    if [ "$SZ" = "$LAST" ] && [ "$SZ" -gt 0 ]; then
      STABLE=$((STABLE + 1))
    else
      STABLE=0
    fi
    LAST="$SZ"
    # 60 초 = 30 초 x 2 회 연속 같은 크기
    if [ "$STABLE" -ge 2 ]; then
      break
    fi
  fi
  sleep 30
done

LINES=$(wc -l < "$F" 2>/dev/null || echo "?")
say "«$WHAT» 끝났다 · $LAST bytes · $LINES 행 · $F"

# **텔레그램도 보낸다.** 내가 깨어 있지 않아도 팀장께 간다.
python - "$WHAT" "$F" "$LAST" "$LINES" <<'PY' 2>/dev/null || say "(텔레그램 실패 · 무시한다)"
import sys, os
sys.path.insert(0, os.path.join("_out", "loop"))
what, path, size, lines = sys.argv[1:5]
from tg import send
send("[검증 끝] %s\n\n%s\n%s bytes · %s 행\n\n다음 칸 · 읽고 보고" % (what, path, size, lines))
PY

say "사슬 끝. 파일을 읽을 것."
