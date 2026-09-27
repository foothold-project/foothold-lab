#!/usr/bin/env bash
# 밤새 혼자 끝낸다. 학습 -> 등록 -> 평가 -> 판정 -> 영상 -> 자료 묶음.
#
# 분류: 운영
# 작성: 오흥재 · 2026-09-28
# 근거: 팀장 지시 「학습 fs1, fs2 끝나면 절대 지시했다고 멈추지 말고 watchdog 으로
#       다시 세팅해서 전체 과정 실패 없이 진행해」
#       `_out/loop/supervisor.sh` 의 관문 · `_out/loop/record_cand1.sh` 의 영상 형식
# 요지: **한 회차에 한 단계만** 하고 나간다. 예약 작업이 10 분마다 다시 부른다.
#       단계마다 표식 파일을 남겨서 중간에 죽어도 다음 회차가 이어서 한다.
#
# 비교 대상 셋 (팀장 지시)
#   v2g2-feetair01   resume 계보에서 일반화가 가장 좋았던 판 (이미 평가됨)
#   fs1-scratch-f001 처음부터 · feet_air_time 0.01
#   fs2-scratch-f01  처음부터 · feet_air_time 0.1
#
# 내가 «안» 하는 것
#   보고서 본문을 자동 생성하지 않는다. 숫자와 영상과 표만 모아 둔다.
#   서사는 사람이 쓴다. 자동 생성한 산문은 근거 없는 문장을 만든다.

set -u
set -o pipefail

LAB="C:/Users/AI-WS01/Desktop/jay/인공지능사관학교/foothold-lab"
ISAAC="C:/isaac/IsaacLab"
RUNS="$ISAAC/logs/rsl_rl/unitree_go2_gap_nvidia"
LOGS="$ISAAC/logs/gap_run_logs"
OUT="$LAB/_out/loop"
LOG="$OUT/night.log"
LOCK="$OUT/night.lock"
STAGE="$OUT/night.stage"
BUNDLE="$LAB/sim/eval/results/20260928-scratch-vs-resume"
PY="C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe"

cd "$LAB" || exit 1
say() { echo "[밤 $(date '+%m/%d %H:%M:%S')] $*" | tee -a "$LOG"; }

# ---------------------------------------------------------------- 자물쇠
if [ -f "$LOCK" ]; then
  AGE=$(( $(date +%s) - $(stat -c %Y "$LOCK" 2>/dev/null || echo 0) ))
  [ "$AGE" -lt 5400 ] && exit 0
  say "자물쇠가 ${AGE}초 묵었다. 버린다"
fi
echo $$ > "$LOCK"
trap 'rm -f "$LOCK"' EXIT

done_stage() { grep -qx "$1" "$STAGE" 2>/dev/null; }
mark_stage() { echo "$1" >> "$STAGE"; }

FS1=20260928_fs1-scratch-f001
FS2=20260928_fs2-scratch-f01

# ---------------------------------------------------------------- 조회
trainers() {
  local out
  out=$(powershell -NoProfile -Command \
    "@(Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { \$_.CommandLine -match 'run_name' }).Count" \
    2>/dev/null | tr -d '\r ')
  case "$out" in ''|*[!0-9]*) echo -1 ;; *) echo "$out" ;; esac
}
evals() {
  local out
  out=$(powershell -NoProfile -Command \
    "@(Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { \$_.CommandLine -match 'eval_|record_' }).Count" \
    2>/dev/null | tr -d '\r ')
  case "$out" in ''|*[!0-9]*) echo -1 ;; *) echo "$out" ;; esac
}
ckpt_max() {   # $1 = 판 이름
  local d; d=$(ls -d "$RUNS"/*"$1"* 2>/dev/null | head -1)
  [ -z "$d" ] && { echo 0; return; }
  ls "$d"/model_*.pt 2>/dev/null | sed 's/.*model_//;s/\.pt//' | sort -n | tail -1
}
run_over() {   # 완주했거나 죽었거나
  ls "$RUNS"/*"$1"*/model_4500.pt >/dev/null 2>&1 && return 0
  local l; l=$(ls -t "$LOGS"/*"$1"*.log 2>/dev/null | head -1)
  [ -z "$l" ] && return 1
  grep -q "exit=" "$l" 2>/dev/null
}

N=$(trainers); E=$(evals)
if [ "$N" = "-1" ] || [ "$E" = "-1" ]; then say "프로세스를 못 읽었다. 이번 회차는 넘긴다"; exit 0; fi

# ---------------------------------------------------------------- 1 · 학습
if ! done_stage "train"; then
  if run_over "$FS1" && run_over "$FS2"; then
    say "**학습 둘이 끝났다**"
    for r in "$FS1" "$FS2"; do
      if ls "$RUNS"/*"$r"*/model_4500.pt >/dev/null 2>&1; then
        say "  $r · 완주 4500"
      else
        l=$(ls -t "$LOGS"/*"$r"*.log 2>/dev/null | head -1)
        say "  $r · **완주 못 함** · 최대 $(ckpt_max "$r") · $(grep -o 'RuntimeError:.*' "$l" 2>/dev/null | tail -1 | cut -c1-56)"
      fi
    done
    mark_stage "train"
  else
    say "학습 중 · fs1 $(ckpt_max "$FS1") / 4500 · fs2 $(ckpt_max "$FS2") / 4500 · 도는 판 $N"
    exit 0
  fi
fi

# ---------------------------------------------------------------- 2 · 등록
if ! done_stage "register"; then
  say "상태 파일에 반영한다"
  $PY _out/loop/register.py 2>&1 | tail -6 | sed 's/^/          /' | tee -a "$LOG"
  mark_stage "register"
  exit 0
fi

# ---------------------------------------------------------------- 3 · 평가
if ! done_stage "eval"; then
  if [ "$E" -gt 0 ]; then say "평가가 도는 중 ($E 개). 기다린다"; exit 0; fi
  if [ -f "$OUT/night.eval-started" ]; then
    say "평가가 끝났다"
    mark_stage "eval"
  else
    say "평가를 건다 (두 축을 두 GPU 에 나눈다 · 4500 까지 다섯 점)"
    date > "$OUT/night.eval-started"
    # 관문은 여전히 넷(1500·2000·2500·3000)을 본다. 4500 은 «보고용» 이다.
    # 근거: verdict.py:41 이 넷을 보므로 기본값을 안 바꿨다 (eval_runner.py 주석).
    FOOTHOLD_EVAL_CKPTS=1500,2000,2500,3000,4500       $PY _out/loop/eval_runner.py 2>&1 | tail -4 | sed 's/^/          /' | tee -a "$LOG"
    exit 0
  fi
fi

# ---------------------------------------------------------------- 4 · 판정
if ! done_stage "verdict"; then
  say "판정문을 낸다 (비교 대상 셋)"
  for r in v2g2-feetair01 fs1-scratch-f001 fs2-scratch-f01; do
    $PY _out/loop/verdict.py --run "$r" \
      --out "inbox/jay/20260927-methodology/VERDICT-$r.md" >/dev/null 2>&1 \
      && say "  판정문 $r" || say "  판정문 «못 냈다» $r"
  done
  mark_stage "verdict"
  exit 0
fi

# ---------------------------------------------------------------- 5 · 자료 묶음
if ! done_stage "bundle"; then
  say "숫자를 한 곳에 모은다 -> $BUNDLE"
  mkdir -p "$BUNDLE"
  $PY _out/loop/bundle3.py --out "$BUNDLE" 2>&1 | tail -8 | sed 's/^/          /' | tee -a "$LOG"
  mark_stage "bundle"
  exit 0
fi

# ---------------------------------------------------------------- 6 · 영상
if ! done_stage "video"; then
  if [ "$E" -gt 0 ]; then say "영상이 도는 중. 기다린다"; exit 0; fi
  if [ -f "$OUT/night.video-started" ]; then
    say "영상이 끝났다"
    mark_stage "video"
  else
    say "영상을 찍는다 (셋 × 놀란 자리)"
    date > "$OUT/night.video-started"
    bash _out/loop/record3.sh >> "$LOG" 2>&1 &
    exit 0
  fi
fi

# ---------------------------------------------------------------- 7 · 알림
if ! done_stage "notify"; then
  say "텔레그램을 보낸다"
  $PY _out/loop/heartbeat.py 2>&1 | tail -3 | sed 's/^/          /' | tee -a "$LOG"
  mark_stage "notify"
  say "**밤 작업이 다 끝났다.**"
  say "  판정문   inbox/jay/20260927-methodology/VERDICT-*.md"
  say "  자료     $BUNDLE"
  say "  영상     sim/eval/results/20260928-scratch-clips"
  say "  남은 것  보고서 두 장의 «본문» 은 사람이 쓴다"
fi

exit 0
