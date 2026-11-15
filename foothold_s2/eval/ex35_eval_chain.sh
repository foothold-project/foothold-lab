#!/usr/bin/env bash
# SONNET-X27h: EX-35 저장본 자동 평가 사슬 (카드 §2 「저장본마다 자동으로 재고」). 평가만 한다. 학습 폴더는 읽기만 한다.
# usage: ex35_eval_chain.sh <cuda:N> <학습 체크포인트 폴더> <out 상위 폴더> <평가 하네스 worktree(고정 사본)>
#   - 하네스는 고정 사본(run_sb_eval.sh = turn16 켬 · 가림 8 경우 + 전진 걸음 + map64 두 모드)을 쓰고, 판정은 ex35_gate.judge_ex35 (이 스크립트가 있는 저장소의 코드)로 한다.
#   - 새 저장본(m1550 ... m3000, 50 간격)이 생기면 최신부터 평가한다. 한 번에 Isaac 하나: 평가 시작 전에 이 GPU 에 다른 평가 · 촬영 python 이 있으면 기다린다.
#   - 저장본마다 <out>/m<N>/ (평가 원자료 + ex35_verdict.json + timing.txt), 끝나면 CHAIN_ITEM_DONE. 이미 있으면 건너뛴다. 판정은 각 저장본마다 한 번 낸다(consume 은 소비자가 마지막 두 개를 본다).
#   - 학습 python(PID 파일 또는 명령줄 패턴)이 사라지고 대기 저장본이 없으면 끝낸다.
set -u
DEV="$1"; CKDIR="$2"; OUTTOP="$3"; HARNESS="$4"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"       # 판정 코드(저장소 루트)
PY=/c/Users/AI-WS01/anaconda3/envs/isaac311/python.exe
BASE=C:/mai/wt/foothold-lab/impl-turncases/logs/sb10_eval/m1500
POLL="${POLL_SECONDS:-60}"
TRAIN_PATTERN="${TRAIN_PROC_PATTERN:-scripts.train_sb.*--run_name ex35-s2a}"
DEVNUM="${DEV#cuda:}"
mkdir -p "$OUTTOP"
LOG="$OUTTOP/chain.log"
say() { echo "$(date '+%Y-%m-%d %H:%M:%S') $*" | tee -a "$LOG"; }

count_ps() {   # $1 = 정규식. 일치하는 python.exe 개수(도구 오류면 99 = 「있음」으로 본다)
  local out
  out="$(powershell.exe -NoProfile -Command "try { @(Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { \$_.CommandLine -match '$1' }).Count } catch { 'ERR' }" 2>/dev/null | tr -d '\r\n ')"
  case "$out" in ''|*[!0-9]*) echo 99 ;; *) echo "$out" ;; esac
}

say "EX35 EVAL CHAIN start dev=$DEV ckdir=$CKDIR out=$OUTTOP harness=$HARNESS harness_head=$(git -C "$HARNESS" rev-parse HEAD) judge_head=$(git -C "$HERE" rev-parse HEAD)"
echo "harness_head=$(git -C "$HARNESS" rev-parse HEAD)" > "$OUTTOP/receipt.txt"
git -C "$HARNESS" status --short >> "$OUTTOP/receipt.txt"
echo "judge_head=$(git -C "$HERE" rev-parse HEAD)" >> "$OUTTOP/receipt.txt"

while true; do
  PENDING=""
  for n in $(seq 3000 -50 1550); do
    [ -f "$CKDIR/model_$n.pt" ] && [ ! -f "$OUTTOP/m$n/CHAIN_ITEM_DONE" ] && [ ! -f "$OUTTOP/m$n/CHAIN_ITEM_FAILED" ] && PENDING="$PENDING $n"
  done
  if [ -z "$PENDING" ]; then
    if [ "$(count_ps "$TRAIN_PATTERN")" = "0" ]; then say "DONE 학습 python 없음 · 대기 저장본 없음"; echo DONE > "$OUTTOP/DONE"; exit 0; fi
    sleep "$POLL"; continue
  fi
  N="${PENDING# }"; N="${N%% *}"
  CK="$CKDIR/model_$N.pt"
  # 저장 직후 파일이 덜 써졌을 수 있다: 크기가 5 초 사이 같을 때까지 기다린다
  S1=$(stat -c %s "$CK"); sleep 5; S2=$(stat -c %s "$CK"); [ "$S1" = "$S2" ] || { sleep 20; }
  # 한 번에 Isaac 하나: 이 GPU 에 다른 평가 · 촬영 python(--device cuda:N, 대기 중인 촬영 큐 렌더 대기 프로세스는 세지 않는다)이 없을 때만
  while [ "$(count_ps "--device cuda:$DEVNUM( |$)")" != "0" ]; do say "m$N 대기: cuda:$DEVNUM 에 다른 python 이 있다"; sleep "$POLL"; done
  T0=$(date +%s)
  say "ITEM m$N start $CK"
  MODES="eval_gt probe_prop_only" bash "$HARNESS/foothold_s2/eval/run_sb_eval.sh" "$DEV" "$CK" "$OUTTOP/m$N" < /dev/null
  RC=$?
  T1=$(date +%s)
  echo "start=$T0 end=$T1 seconds=$((T1-T0))" > "$OUTTOP/m$N/timing.txt"
  BAD=0
  grep -q "없음" "$OUTTOP/m$N/rc.txt" 2>/dev/null && BAD=1
  grep -E "rc=[1-9]" "$OUTTOP/m$N/rc.txt" > /dev/null 2>&1 && BAD=1
  if [ "$RC" -ne 0 ] || [ "$BAD" -ne 0 ]; then
    say "ITEM m$N end FAIL script_rc=$RC seconds=$((T1-T0))"; echo "script_rc=$RC bad=$BAD" > "$OUTTOP/m$N/CHAIN_ITEM_FAILED"; continue
  fi
  PYTHONPATH="$HERE" PYTHONUTF8=1 "$PY" -m foothold_s2.eval.ex35_gate \
    --latest-turn eval_gt="$OUTTOP/m$N/turn16_eval_gt" probe_prop_only="$OUTTOP/m$N/turn16_probe_prop_only" --latest-map64 "$OUTTOP/m$N/map64/map_modes.json" \
    --base-turn eval_gt="$BASE/turn16_eval_gt" probe_prop_only="$BASE/turn16_probe_prop_only" --base-map64 "$BASE/map64/map_modes.json" \
    --it-in-stage $((N-1500)) --min-stay 500 --out "$OUTTOP/m$N/ex35_verdict.json" > "$OUTTOP/m$N/ex35_verdict.stdout" 2>&1
  echo "verdict_rc=$?" >> "$OUTTOP/m$N/timing.txt"
  STATE="$(grep -m1 '"state"' "$OUTTOP/m$N/ex35_verdict.json" 2>/dev/null | tr -d ' \r')"
  say "ITEM m$N end ok seconds=$((T1-T0)) verdict $STATE"
  echo "script_rc=$RC" > "$OUTTOP/m$N/CHAIN_ITEM_DONE"
done
