#!/usr/bin/env bash
# SONNET-X25h: B1500 을 S-B 와 같은 꼴(task B, 16 env 여섯 경우 + map64, 모드 eval_gt · probe_prop_only · eval_pred)로 두 번(rep1 · rep2: 재실행 폭) 잰다. 평가만 한다. lead 가 띄운다.
# usage: baseline_b1500.sh <cuda:N> <out 상위 폴더> <기다릴 rc.txt 경로>
#   <기다릴 rc.txt> 가 생기면 시작한다(같은 GPU 의 학습이 끝나기 전에 평가를 돌리지 않으려고). 이미 끝난 rep(<out>/rep<K>/CHAIN_ITEM_DONE)은 건너뛴다. 끝에 <out>/DONE
# B1500 체크포인트: B_CK 환경변수(기본 lead-tmp-start-b 의 2026-10-24_06-52-56_ex28-b-main/model_1500.pt)
set -u
DEV="$1"; OUTTOP="$2"; WAIT_RC="$3"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN="$HERE/run_sb_eval.sh"
POLL="${POLL_SECONDS:-60}"
B_CK="${B_CK:-C:/mai/wt/foothold-lab/lead-tmp-start-b/logs/rsl_rl/foothold_s2_23f_b/2026-10-24_06-52-56_ex28-b-main/model_1500.pt}"
mkdir -p "$OUTTOP"
LOG="$OUTTOP/chain.log"
say() { echo "$(date '+%Y-%m-%d %H:%M:%S') $*" | tee -a "$LOG"; }

say "B1500 start dev=$DEV wait_rc=$WAIT_RC ck=$B_CK"
[ -f "$B_CK" ] || { say "B1500 체크포인트 없음: $B_CK"; echo "DONE ok=0 fail=2 (체크포인트 없음)" > "$OUTTOP/DONE"; exit 1; }
while [ ! -f "$WAIT_RC" ]; do sleep "$POLL"; done
say "WAIT_RC found: $(tr -d '\r\n' < "$WAIT_RC" | head -c 80)"
OK=0; FAIL=0
for K in 1 2; do
  D="$OUTTOP/rep$K"
  if [ -f "$D/CHAIN_ITEM_DONE" ]; then say "rep$K skip (이미 끝남)"; continue; fi
  say "rep$K start"
  TASK=FootholdS2-Go2-S2-23f-B-v0 MODES="eval_gt probe_prop_only eval_pred" bash "$RUN" "$DEV" "$B_CK" "$D" < /dev/null
  RC=$?
  BAD=0
  grep -q "없음" "$D/rc.txt" 2>/dev/null && BAD=1
  grep -E "rc=[1-9]" "$D/rc.txt" > /dev/null 2>&1 && BAD=1
  if [ "$RC" -eq 0 ] && [ "$BAD" -eq 0 ]; then OK=$((OK+1)); echo "script_rc=$RC" > "$D/CHAIN_ITEM_DONE"; say "rep$K end ok"; else FAIL=$((FAIL+1)); echo "script_rc=$RC bad=$BAD" > "$D/CHAIN_ITEM_FAILED"; say "rep$K end FAIL script_rc=$RC (rc.txt 를 볼 것)"; fi
done
say "DONE ok=$OK fail=$FAIL"
echo "DONE ok=$OK fail=$FAIL" > "$OUTTOP/DONE"
