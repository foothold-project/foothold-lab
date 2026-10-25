#!/usr/bin/env bash
# SONNET-X25h: post_train_eval.sh 의 고친 판(새 이름: 돌고 있는 셸은 고치지 않는다). 학습이 끝나면 저장본을 차례로 평가하는 사슬. 평가만 한다. lead 가 띄운다.
# usage: post_train_eval2.sh <cuda:N> <체크포인트 폴더> <out 상위 폴더> <학습 rc.txt 경로> <학습 run.log 경로>
#   1) 학습 rc.txt 가 생길 때까지 기다린다(학습 중에는 같은 GPU 에서 평가를 돌리지 않는다).
#      학습이 rc.txt 없이 죽은 경우: 학습 run.log 가 DEAD_SECONDS(기본 1800 = 30 분) 넘게 안 바뀌었고, 이 GPU 에서 도는 학습 python 이 없으면
#      chain.log 에 TRAIN_DEAD 를 적고 그 시점의 저장본까지 평가한 뒤 끝낸다. 학습 python 은 명령줄이 TRAIN_PROC_PATTERN(기본 "scripts.train_.*--device <cuda:N>": 점이 / 와 역슬래시를 모두 받는다. 역슬래시는 셸 따옴표에서 깨져 쓰지 않는다)과 맞는 python.exe 로 본다
#   2) 순서: m100 단위(100, 200, ... 1500) 먼저, 그다음 나머지 50 단위(50, 150, ... 1450). 없는 저장본은 건너뛴다
#   3) 저장본마다 run_sb_eval.sh -> <out 상위>/m<N>/ . m1500 에만 배포 모드 eval_pred 를 더한다(MODES_1500, 기본 "eval_gt probe_prop_only eval_pred"). 나머지는 run_sb_eval.sh 기본 두 모드
#      <out 상위>/m<N>/CHAIN_ITEM_DONE(성공할 때만 만든다)이 있으면 다시 하지 않는다. 한 건이 실패해도 다음으로 간다
#   4) 끝에 <out 상위>/chain.log 와 DONE 파일에 DONE 줄(죽은 학습이면 "DONE ... train_dead=1")
# 첫 증거: chain.log 의 "ITEM m<N> start/end" 줄과 m<N>/rc.txt
set -u
DEV="$1"; CKDIR="$2"; OUTTOP="$3"; TRAIN_RC="$4"; TRAIN_LOG="$5"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN="$HERE/run_sb_eval.sh"
POLL="${POLL_SECONDS:-60}"
DEAD_SECONDS="${DEAD_SECONDS:-1800}"
MODES_1500="${MODES_1500:-eval_gt probe_prop_only eval_pred}"
PATTERN="${TRAIN_PROC_PATTERN:-scripts.train_.*--device $DEV}"
mkdir -p "$OUTTOP"
LOG="$OUTTOP/chain.log"
say() { echo "$(date '+%Y-%m-%d %H:%M:%S') $*" | tee -a "$LOG"; }

# 학습 python 이 이 GPU 에 있는가(반환 0 = 있음, 1 = 없음). 세어서 정확히 0 일 때만 「없음」이다. 도구 오류(ERR) · 빈 출력은 「있음」으로 본다(살아 있는 학습을 죽었다고 하지 않는다)
train_python_alive() {
  local out
  out="$(powershell.exe -NoProfile -Command "try { @(Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { \$_.CommandLine -match '$PATTERN' }).Count } catch { 'ERR' }" 2>/dev/null | tr -d '\r\n ')"
  case "$out" in
    0) return 1 ;;
    *) return 0 ;;
  esac
}

log_age() {
  local m now
  m="$(stat -c %Y "$TRAIN_LOG" 2>/dev/null)" || { echo 0; return; }
  now="$(date +%s)"
  echo $((now - m))
}

say "CHAIN2 start dev=$DEV ckdir=$CKDIR train_rc=$TRAIN_RC train_log=$TRAIN_LOG dead_after=${DEAD_SECONDS}s poll=${POLL}s pattern=$PATTERN"
TRAIN_DEAD=0
while [ ! -f "$TRAIN_RC" ]; do
  if [ -f "$TRAIN_LOG" ] && [ "$(log_age)" -gt "$DEAD_SECONDS" ] && ! train_python_alive; then
    TRAIN_DEAD=1
    say "TRAIN_DEAD: run.log 가 $(log_age) 초째 안 바뀌고 학습 python 이 없다. rc.txt 도 없다. 그 시점의 저장본까지 평가하고 끝낸다"
    break
  fi
  sleep "$POLL"
done
[ "$TRAIN_DEAD" -eq 0 ] && say "TRAIN_RC found: $(tr -d '\r\n' < "$TRAIN_RC" | head -c 80)"

ORDER=""
for n in $(seq 100 100 1500); do ORDER="$ORDER $n"; done
for n in $(seq 50 100 1450); do ORDER="$ORDER $n"; done

DONE_N=0; FAIL_N=0; SKIP_N=0
for n in $ORDER; do
  CK="$CKDIR/model_$n.pt"
  if [ ! -f "$CK" ]; then say "ITEM m$n skip (저장본 없음)"; SKIP_N=$((SKIP_N+1)); continue; fi
  if [ -f "$OUTTOP/m$n/CHAIN_ITEM_DONE" ]; then say "ITEM m$n skip (이미 끝남)"; continue; fi
  if [ "$n" -eq 1500 ]; then ITEM_MODES="$MODES_1500"; else ITEM_MODES="eval_gt probe_prop_only"; fi
  say "ITEM m$n start $CK modes=[$ITEM_MODES]"
  MODES="$ITEM_MODES" bash "$RUN" "$DEV" "$CK" "$OUTTOP/m$n" < /dev/null
  RC=$?
  BAD=0
  grep -q "없음" "$OUTTOP/m$n/rc.txt" 2>/dev/null && BAD=1
  grep -E "rc=[1-9]" "$OUTTOP/m$n/rc.txt" > /dev/null 2>&1 && BAD=1
  if [ "$RC" -ne 0 ] || [ "$BAD" -ne 0 ]; then FAIL_N=$((FAIL_N+1)); say "ITEM m$n end FAIL script_rc=$RC (rc.txt 를 볼 것)"; else DONE_N=$((DONE_N+1)); say "ITEM m$n end ok"; fi
  if [ "$RC" -eq 0 ] && [ "$BAD" -eq 0 ]; then echo "script_rc=$RC" > "$OUTTOP/m$n/CHAIN_ITEM_DONE"; else echo "script_rc=$RC bad=$BAD" > "$OUTTOP/m$n/CHAIN_ITEM_FAILED"; fi
done
say "DONE ok=$DONE_N fail=$FAIL_N skipped=$SKIP_N train_dead=$TRAIN_DEAD"
echo "DONE ok=$DONE_N fail=$FAIL_N skipped=$SKIP_N train_dead=$TRAIN_DEAD" > "$OUTTOP/DONE"
