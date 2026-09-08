#!/usr/bin/env bash
# 알림 전달기. 이 저장소에서 «알림은 관문이 아니다».
#
# 왜 있나 (2026-09-08 실측 · 이슈 #307):
#   inbox-pr-alert.yml 이 텔레그램 HTTP 400 하나로 exit 1 을 냈다. 그러면 PR 이
#   빨간불이 되고 «내용에 문제가 있는 것»처럼 보인다. #250 #177 #304 가 닷새
#   막혔는데 내용에는 아무 문제가 없었다. 알림이 죽은 것이 검수가 죽은 것으로
#   보인 것이다 (docs/PR-REVIEW-FLOW.md 「알림 실패와 검수 실패는 다르다」).
#
#   더 나쁜 것은 고쳐도 안 닿는다는 점이다. GitHub 는 «재실행» 을 원래 런에 묶인
#   워크플로 판으로 돌린다. 2026-09-08 05:46Z 에 main 에 길이 제한을 넣었는데
#   06:20Z 재실행이 여전히 옛 판을 실행해 똑같이 400 이 났다. 런 로그로 확인했다
#   (run 33955321883 att2: names[:15] 없음 · 3500자 컷 없음).
#
# 그래서 이 스크립트는 «절대 실패하지 않는다». 대신 실패를 세 자리에 남긴다.
#   1  ::warning:: 주석 (런 화면)
#   2  $GITHUB_STEP_SUMMARY 한 줄 (런 요약)
#   3  «다른 채널»로 짧은 알림. 본문이 길어서 실패한 경우 짧은 것은 들어간다
#
# 쓰는 법
#   notify_send.sh telegram <본문파일> <라벨>     TG_TOKEN · TG_CHAT 필요
#   notify_send.sh discord  <payload.json> <라벨>  HOOK 필요
#   notify_send.sh verdict                          런 요약에 판정 한 줄
#
# 상태는 $NOTIFY_STATE (기본 notify-state.txt) 에 «ok|fail<TAB>채널<TAB>라벨<TAB>코드»
# 로 쌓인다. verdict 가 그것을 읽는다. 파일이 비어 있으면 «아무것도 안 보냈다» 이고
# 그것도 판정에 적는다 (빈 산출물이 조용한 성공이 되지 않게).

set -uo pipefail        # -e 는 일부러 안 켠다. 여기서 죽으면 PR 이 빨간불이 된다.

# ★ -u 가 켜져 있으므로 «없는 변수»를 건드리는 순간 이 스크립트가 죽는다.
#   그러면 «절대 실패하지 않는다»는 약속이 깨지고 PR 이 다시 빨간불이 된다.
#   안전망이 스스로 죽지 않게 먼저 빈 값으로 박아 둔다.
TG_TOKEN="${TG_TOKEN:-}"
TG_CHAT="${TG_CHAT:-}"
HOOK="${HOOK:-}"

STATE="${NOTIFY_STATE:-notify-state.txt}"
TAB=$(printf '\t')
TRIES="${NOTIFY_TRIES:-3}"

note()    { printf '%s\n' "$*"; }
# ★ 경고는 stderr 로 보낸다. stdout 으로 내면 $(...) 안에서 불렸을 때 «HTTP 코드»
#   자리에 경고문이 섞여 들어간다. 2026-09-08 실측에서 실제로 그렇게 깨졌다.
warn()    { printf '::warning::%s\n' "$*" >&2; }
summary() { [ -n "${GITHUB_STEP_SUMMARY:-}" ] && printf '%s\n' "$*" >> "$GITHUB_STEP_SUMMARY"; return 0; }
record()  { printf '%s%s%s%s%s%s%s\n' "$1" "$TAB" "$2" "$TAB" "$3" "$TAB" "$4" >> "$STATE"; }

# 429 와 5xx 는 잠깐 뒤 다시 하면 되는 것들이다. 000 은 curl 이 아예 못 붙은 것.
retryable() { case "$1" in 429|5??|000) return 0 ;; *) return 1 ;; esac; }

# 텔레그램 본문은 4096자가 한계다. 넘으면 400 이 난다(#302 · 영상 42개짜리 #301).
# 자르기는 «보내는 쪽»의 일이다. 부르는 곳마다 따로 자르면 한 군데는 빠진다.
# 실제로 pr-notify.yml 에는 자르는 코드가 없었다. 바이트가 아니라 «글자»로 잘라야
# 한글이 안 깨진다.
cap_telegram() {    # $1=본문파일. 필요하면 제자리에서 줄인다
  python3 - "$1" <<'PY'
import io, sys
p = sys.argv[1]
s = io.open(p, encoding='utf-8', errors='replace').read()
if len(s) > 3500:
    io.open(p, 'w', encoding='utf-8').write(s[:3500] + chr(10) + '... (길어서 줄였습니다)')
PY
  # ★ 자르기가 «돌았는지» 를 되재 본다. 2026-09-08 에 이 함수를 2>/dev/null 로
  #   감쌌더니 python3 가 없는 환경에서 조용히 아무 일도 안 하고 성공을 반환했다.
  #   종료코드 0 은 결과의 증거가 아니다. 산출물을 다시 세어야 안다.
  local n
  n=$(wc -m < "$1" 2>/dev/null | tr -d ' ')
  case "$n" in ''|*[!0-9]*) return 0 ;; esac
  [ "$n" -gt 4000 ] && warn "본문이 ${n}자입니다. 길이 제한 처리가 안 돌았습니다 (python3 확인)"
  return 0
}

# 이 함수는 $(...) 안에서 불린다. 여기서는 HTTP 코드 말고 아무것도 stdout 에
# 쓰지 않는다. 자르기는 send() 가 루프 밖에서 미리 해 둔다.
post_telegram() {   # $1=본문파일  -> HTTP 코드를 stdout 으로
  curl -sS -o /dev/null -w '%{http_code}' \
       -X POST "https://api.telegram.org/bot${TG_TOKEN}/sendMessage" \
       --data-urlencode "chat_id=${TG_CHAT}" \
       --data-urlencode "disable_web_page_preview=true" \
       --data-urlencode "text@$1" 2>/dev/null || echo 000
}

post_discord() {    # $1=payload 파일
  curl -sS -o /dev/null -w '%{http_code}' \
       -X POST -H "Content-Type: application/json" \
       -d "@$1" "$HOOK" 2>/dev/null || echo 000
}

# 긴 본문이 원인일 때 «짧은 한 줄»은 들어간다. 그래서 다른 채널로 흘린다.
fallback() {        # $1=실패한 채널  $2=라벨  $3=코드
  local msg="[FOOTHOLD] 알림 전달 실패 · ${2} · ${1} HTTP ${3}"
  msg="${msg} · ${GITHUB_SERVER_URL:-https://github.com}/${GITHUB_REPOSITORY:-}/actions/runs/${GITHUB_RUN_ID:-}"
  if [ "$1" != "telegram" ] && [ -n "${TG_TOKEN:-}" ] && [ -n "${TG_CHAT:-}" ]; then
    printf '%s\n' "$msg" > .notify-fallback.txt
    note "우회 통보 텔레그램 HTTP $(post_telegram .notify-fallback.txt)"
    rm -f .notify-fallback.txt
  elif [ "$1" != "discord" ] && [ -n "${HOOK:-}" ]; then
    printf '{"content":%s}' "$(printf '%s' "$msg" | sed 's/\\/\\\\/g; s/"/\\"/g; s/^/"/; s/$/"/')" > .notify-fallback.json
    note "우회 통보 디스코드 HTTP $(post_discord .notify-fallback.json)"
    rm -f .notify-fallback.json
  else
    warn "우회할 다른 채널이 없습니다. 런 요약에만 남습니다"
  fi
}

send() {            # $1=채널  $2=파일  $3=라벨
  local ch="$1" file="$2" label="$3" code="" i=1
  [ "$ch" = telegram ] && cap_telegram "$file"
  while [ "$i" -le "$TRIES" ]; do
    case "$ch" in
      telegram) code=$(post_telegram "$file") ;;
      discord)  code=$(post_discord  "$file") ;;
    esac
    note "${ch} HTTP ${code} (${i}/${TRIES})"
    case "$code" in 2*) record ok "$ch" "$label" "$code"; note "전송 확인"; return 0 ;; esac
    retryable "$code" || break
    [ "$i" -lt "$TRIES" ] && sleep $(( i * 3 ))
    i=$(( i + 1 ))
  done
  record fail "$ch" "$label" "$code"
  warn "알림 전달 실패 · ${label} · ${ch} HTTP ${code}. PR 내용과는 무관합니다"
  summary "- 전달 실패 · **${label}** · ${ch} HTTP \`${code}\`"
  fallback "$ch" "$label" "$code"
  return 0        # ★ 여기서 절대 실패를 돌려주지 않는다. 알림은 관문이 아니다.
}

verdict() {
  local ok=0 bad=0 line st
  if [ -s "$STATE" ]; then
    while IFS="$TAB" read -r st _ _ _; do
      case "$st" in ok) ok=$(( ok + 1 )) ;; fail) bad=$(( bad + 1 )) ;; esac
    done < "$STATE"
  fi
  # 빈 산출물이 «성공» 으로 읽히지 않게 셋을 구분해 적는다 (커널 원칙 2).
  if [ "$ok" = 0 ] && [ "$bad" = 0 ]; then
    note "판정: 보낸 알림 없음 (제출물이 없거나 시크릿 미설정)"
    summary "판정: **보낸 알림 없음**. 제출물이 없거나 시크릿이 없습니다."
  elif [ "$bad" = 0 ]; then
    note "판정: 알림 ${ok}건 전부 전달"
    summary "판정: 알림 **${ok}건 전부 전달**."
  else
    note "판정: 알림 ${ok}건 전달 · ${bad}건 실패. PR 검수와는 무관합니다"
    summary "판정: 알림 ${ok}건 전달 · **${bad}건 실패**. 전달 실패이지 검수 실패가 아닙니다."
  fi
  cat "$STATE" 2>/dev/null
  return 0
}

case "${1:-}" in
  telegram)
    if [ -z "${TG_TOKEN:-}" ] || [ -z "${TG_CHAT:-}" ]; then
      note "텔레그램 시크릿 없음, 건너뜀"; exit 0
    fi
    send telegram "$2" "${3:-telegram}" ;;
  discord)
    if [ -z "${HOOK:-}" ]; then
      warn "DISCORD_WEBHOOK 미설정. 알림을 못 보냅니다"; summary "- 디스코드 웹훅 미설정"; exit 0
    fi
    send discord "$2" "${3:-discord}" ;;
  verdict) verdict ;;
  *) note "쓰는 법: notify_send.sh telegram|discord <파일> <라벨> · notify_send.sh verdict" ;;
esac
exit 0
