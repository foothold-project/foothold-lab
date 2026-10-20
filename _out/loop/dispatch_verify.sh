#!/usr/bin/env bash
# 검증 의뢰를 astra 와 fable 에 «각각» 건다. **TUI 세션에 붙인다.**
#
# 분류: 운영
# 작성: 오흥재 · 2026-09-28
# 근거: AGENTS.md 6 절 「어떻게 거는가」 (2026-09-28 팀장 확정으로 `codex exec` 금지)
#       Orca CLI 가이드 · `wait.satisfied` 와 `turn_started` 규칙
# 요지: `codex exec` 를 **이 스크립트가 거부한다.** 규칙을 적어 두는 것으로는
#       안 막혔다. 2026-09-28 에 AGENTS.md 가 exec 를 쓰라고 «적혀 있어서»
#       그대로 썼고 팀장이 지적했다. 그래서 문서를 고치고 **코드로도 막는다.**

set -u
LAB="C:/Users/AI-WS01/Desktop/jay/인공지능사관학교/foothold-lab"
cd "$LAB" || exit 1
TASK="${TASK_DOC:-inbox/jay/20260927-methodology/TASK-verify-scratch.md}"

say() { echo "[배정 $(date '+%H:%M:%S')] $*"; }
die() { echo "[배정] ** $* **" >&2; exit 1; }

# ------------------------------------------------------------------ 관문
# 누가 이 스크립트를 exec 로 돌리라고 고쳐도 여기서 멈춘다.
if [ "${ALLOW_CODEX_EXEC:-}" = "1" ]; then
  die "codex exec 는 «금지» 다 (AGENTS.md 6 절). ALLOW_CODEX_EXEC 로 우회하지 않는다"
fi

ORCA="${ORCA_CLI_COMMAND:-orca}"
command -v "$ORCA" >/dev/null 2>&1 || die "$ORCA 를 못 찾았다"

WHO="${1:-}"
case "$WHO" in
  # `terminal create --agent codex` 는 모델·노력 인자를 «못 받는다» (Orca CLI 가이드).
  # 그래서 `--command` 에 전체 명령을 넣는다.
  astra) AGENT="codex --model gpt-6-astra -c model_reasoning_effort=high"
         OUT="${OUT_DOC:-inbox/jay/20260927-methodology/VERIFY-scratch-astra.md}" ;;
  fable) AGENT="claude --model claude-fable-5-1"
         OUT="${OUT_DOC:-inbox/jay/20260927-methodology/VERIFY-scratch-fable.md}" ;;
  *) echo "쓰는 법: bash _out/loop/dispatch_verify.sh {astra|fable}"; exit 2 ;;
esac

[ -f "$TASK" ] || die "의뢰서가 없다: $TASK"

PROMPT="$TASK 를 읽고 그 지시대로 검증하십시오. 이 문서는 «검증 의뢰» 이고, 세션의 해석을 승인해 달라는 것이 아닙니다. 문서가 「확인됨」이라고 적은 값도 직접 다시 재십시오. 동의하는 답이 아니라 틀린 곳을 찾는 것이 목적입니다. 근거 없는 칸은 「미확인」으로 두십시오. 한국어로 쓰고, em dash 를 쓰지 말고, 「씨앗」이 아니라 「시드」라고 적고, actor 와 critic 과 optimizer 는 원어로 두십시오. 답은 $OUT 에 쓰십시오."

# ------------------------------------------------- 1 · 세션을 띄운다
say "$WHO · $AGENT 세션을 띄운다"
CREATE=$("$ORCA" terminal create --worktree active --command "$AGENT" --json 2>&1) \
  || die "terminal create 실패: $CREATE"
HANDLE=$(printf '%s' "$CREATE" | python -c "
import json,sys
try: d=json.load(sys.stdin)
except Exception: sys.exit(1)
def walk(n):
    if isinstance(n,dict):
        for k in ('handle','terminalHandle','id'):
            if isinstance(n.get(k),str) and n[k].startswith('term_'): return n[k]
        for v in n.values():
            r=walk(v)
            if r: return r
    if isinstance(n,list):
        for v in n:
            r=walk(v)
            if r: return r
    return None
h=walk(d)
print(h or '')
" 2>/dev/null)
[ -n "$HANDLE" ] || die "handle 을 못 읽었다. 응답: $(printf '%s' "$CREATE" | head -c 400)"
say "  handle $HANDLE"

# ------------------------------------------------- 2 · TUI 준비를 «확인» 한다
# wait 는 시간이 지나도 정상 결과를 찍는다. 찍혔다는 사실이 아니라
# satisfied 를 읽는다. 그러지 않으면 시작 중인 TUI 에 넣은 프롬프트가 사라진다.
check_satisfied() {
  printf '%s' "$1" | python -c "
import json,sys
try: d=json.load(sys.stdin)
except Exception: print('no'); sys.exit()
def walk(n):
    if isinstance(n,dict):
        if 'satisfied' in n: return bool(n['satisfied'])
        for v in n.values():
            r=walk(v)
            if r is not None: return r
    if isinstance(n,list):
        for v in n:
            r=walk(v)
            if r is not None: return r
    return None
print('yes' if walk(d) else 'no')
" 2>/dev/null
}

OK=no
for ms in 120000 240000; do
  W=$("$ORCA" terminal wait --terminal "$HANDLE" --for tui-idle --timeout-ms "$ms" --json 2>&1)
  OK=$(check_satisfied "$W")
  say "  wait --timeout-ms $ms · satisfied=$OK"
  [ "$OK" = "yes" ] && break
done
[ "$OK" = "yes" ] || die "TUI 가 준비되지 않았다. **프롬프트를 보내지 않는다** (보내면 사라진다)"

# ------------------------------------------------- 3 · 보낸다
say "  프롬프트를 보낸다"
S=$("$ORCA" terminal send --terminal "$HANDLE" --wait-submit 20 --enter --json \
      --text "$PROMPT" 2>&1) || die "terminal send 실패: $S"
printf '%s' "$S" | python -c "
import json,sys
try: d=json.load(sys.stdin)
except Exception: print('  응답을 못 읽었다'); sys.exit()
s=json.dumps(d, ensure_ascii=False)
print('  accepted     :', 'true' if '\"accepted\": true' in s else '확인 못 함')
print('  turn_started :', 'true' if 'turn_started' in s else '아직 (accepted 는 접수 증거일 뿐이다)')
" 2>/dev/null

say "$WHO 배정 끝 · handle $HANDLE · 산출 $OUT"
say "  이어서 물으려면  $ORCA terminal send --terminal $HANDLE --text '...' --enter"
echo "$WHO $HANDLE $OUT" >> _out/loop/verify-handles.txt
