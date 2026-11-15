#!/usr/bin/env bash
# SONNET-X25g: 학습이 끝나면 저장본을 차례로 평가하는 사슬. 평가만 한다(학습 아님). lead 가 띄운다.
# usage: post_train_eval.sh <cuda:N> <체크포인트 폴더> <out 상위 폴더> <학습 rc.txt 경로>
#   1) 학습 rc.txt 가 생길 때까지 기다린다(학습 중에는 같은 GPU 에서 평가를 돌리지 않는다). 학습 rc 가 0 이 아니어도 있는 저장본은 잰다(사슬 로그에 학습 rc 를 적는다)
#   2) 순서: m100 단위(100, 200, ... 1500) 먼저, 그다음 나머지 50 단위(50, 150, ... 1450). 없는 저장본은 건너뛴다
#   3) 저장본마다 run_sb_eval.sh -> <out 상위>/m<N>/ . 이미 <out 상위>/m<N>/CHAIN_ITEM_DONE(성공할 때만 만든다)이 있으면 다시 하지 않는다(사슬을 다시 띄우면 실패한 것부터 이어진다). 한 건이 실패해도 다음으로 간다
#   4) 끝에 <out 상위>/chain.log 와 DONE 파일에 DONE 줄
# 첫 증거: chain.log 의 "ITEM m<N> start/end rc=" 줄과 m<N>/rc.txt
set -u
DEV="$1"; CKDIR="$2"; OUTTOP="$3"; TRAIN_RC="$4"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN="$HERE/run_sb_eval.sh"
POLL="${POLL_SECONDS:-60}"
mkdir -p "$OUTTOP"
LOG="$OUTTOP/chain.log"
say() { echo "$(date '+%Y-%m-%d %H:%M:%S') $*" | tee -a "$LOG"; }

say "CHAIN start dev=$DEV ckdir=$CKDIR train_rc=$TRAIN_RC poll=${POLL}s"
while [ ! -f "$TRAIN_RC" ]; do sleep "$POLL"; done
say "TRAIN_RC found: $(tr -d '\r\n' < "$TRAIN_RC" | head -c 80)"

ORDER=""
for n in $(seq 100 100 1500); do ORDER="$ORDER $n"; done
for n in $(seq 50 100 1450); do ORDER="$ORDER $n"; done

DONE_N=0; FAIL_N=0; SKIP_N=0
for n in $ORDER; do
  CK="$CKDIR/model_$n.pt"
  if [ ! -f "$CK" ]; then say "ITEM m$n skip (저장본 없음)"; SKIP_N=$((SKIP_N+1)); continue; fi
  if [ -f "$OUTTOP/m$n/CHAIN_ITEM_DONE" ]; then say "ITEM m$n skip (이미 끝남)"; continue; fi
  say "ITEM m$n start $CK"
  bash "$RUN" "$DEV" "$CK" "$OUTTOP/m$n" < /dev/null
  RC=$?
  BAD=0
  grep -q "DONE 줄 없음\|json 없음\|없음" "$OUTTOP/m$n/rc.txt" 2>/dev/null && BAD=1
  grep -E "rc=[1-9]" "$OUTTOP/m$n/rc.txt" > /dev/null 2>&1 && BAD=1
  if [ "$RC" -ne 0 ] || [ "$BAD" -ne 0 ]; then FAIL_N=$((FAIL_N+1)); say "ITEM m$n end FAIL script_rc=$RC (rc.txt 를 볼 것)"; else DONE_N=$((DONE_N+1)); say "ITEM m$n end ok"; fi
  if [ "$RC" -eq 0 ] && [ "$BAD" -eq 0 ]; then echo "script_rc=$RC" > "$OUTTOP/m$n/CHAIN_ITEM_DONE"; else echo "script_rc=$RC bad=$BAD" > "$OUTTOP/m$n/CHAIN_ITEM_FAILED"; fi
done
say "DONE ok=$DONE_N fail=$FAIL_N skipped=$SKIP_N"
echo "DONE ok=$DONE_N fail=$FAIL_N skipped=$SKIP_N" > "$OUTTOP/DONE"
