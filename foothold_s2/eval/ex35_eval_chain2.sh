#!/usr/bin/env bash
# SONNET-X27h2: EX-35 저장본 자동 평가 사슬 2판 (reviewer REVIEW-adad7d5e 고침 3). 1판(ex35_eval_chain.sh)은 돌고 있어서 고치지 않고 새 이름으로 둔다.
# usage: ex35_eval_chain2.sh <cuda:N> <학습 체크포인트 폴더> <out 상위 폴더>      (고정 사본 worktree 안에서 부른다: 하네스 · 판정 코드 · 이 스크립트가 모두 이 사본에서 읽힌다)
#   저장본마다 단계(stage)별 표식 m<N>/stage_<이름>.done 으로 이어 한다(빠진 단계만 덧붙임, 처음부터 다시 하지 않음):
#     core : turn16 켬 · 가림 (--cases all = 여섯 + walk_turn 둘, 전진 걸음) + map64 켬 · 가림 -> run_sb_eval.sh, 뒤이어 ex35_gate.judge_ex35 판정(ex35_verdict.json)
#     pred : turn16_eval_pred (여덟 경우 + 전진 걸음) + map64_eval_pred (eval_pred 한 모드, map64/ 와 같은 조건)
#     L6   : hardlevel/L6 (fwd1.0 · fwd0.5, 켬 · 가림, --fixed-level 6)
#     L9   : hardlevel/L9 (같은 조건, --fixed-level 9)
#   창 경계 쌍(N 이 250 의 배수이거나 그 직전 50)은 네 단계 전부(카드 §4b.5), 그 밖의 저장본은 core 만(시간 때문, 한 저장본 전부는 60 분 안팎).
#   순서: 경계 쌍 먼저(큰 N 부터), 그 밖의 저장본은 그 뒤 최신부터. 한 번에 Isaac 하나: cuda:N 에 다른 --device cuda:N python 이 있으면 기다린다.
#   판정 python 실패 · 평가 rc 실패는 단계 완료로 치지 않는다(stage_<이름>.failed, 두 번까지 다시 시도).
#   저장본마다 judge_code_sha256.txt(ex35_gate · judge_gate · judge_stats · 이 스크립트 · 하네스 turn_probe/run_sb_eval)와 inputs_list.txt(카드 §4b.5 입력 파일 sha256 · MISSING)를 남긴다.
set -u
DEV="$1"; CKDIR="$2"; OUTTOP="$3"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PY=/c/Users/AI-WS01/anaconda3/envs/isaac311/python.exe
BASE=C:/mai/wt/foothold-lab/impl-turncases/logs/sb10_eval/m1500
TASK="${TASK:-FootholdS2-Go2-S2-SB-v0}"
POLL="${POLL_SECONDS:-60}"
TRAIN_PATTERN="${TRAIN_PROC_PATTERN:-scripts.train_sb.*--run_name ex35-s2a}"
DEVNUM="${DEV#cuda:}"
KIT="$ROOT/foothold_s2/eval/run_kit.sh"
mkdir -p "$OUTTOP"
LOG="$OUTTOP/chain2.log"
say() { echo "$(date '+%Y-%m-%d %H:%M:%S') $*" | tee -a "$LOG"; }

count_ps() {   # $1 = 정규식. 일치하는 python.exe 개수(도구 오류면 99 = 「있음」)
  local out
  out="$(powershell.exe -NoProfile -Command "try { @(Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { \$_.CommandLine -match '$1' }).Count } catch { 'ERR' }" 2>/dev/null | tr -d '\r\n ')"
  case "$out" in ''|*[!0-9]*) echo 99 ;; *) echo "$out" ;; esac
}

is_pair() { local n=$1; [ $((n % 250)) -eq 0 ] || [ $(((n + 50) % 250)) -eq 0 ]; }

stage_done() {   # $1=N $2=stage. core 는 1판 사슬이 정상으로 끝낸 m1750 도 인정한다(script_rc= 가 든 CHAIN_ITEM_DONE)
  [ -f "$OUTTOP/m$1/stage_$2.done" ] && return 0
  [ "$2" = core ] && grep -q "^script_rc=" "$OUTTOP/m$1/CHAIN_ITEM_DONE" 2>/dev/null && [ -f "$OUTTOP/m$1/ex35_verdict.json" ] && return 0
  return 1
}

stages_for() { if is_pair "$1"; then echo "core pred L6 L9"; else echo core; fi; }

next_item() {   # 출력: "N stage" 또는 빈 줄. 경계 쌍(큰 N 먼저) -> 그 밖(큰 N 먼저)
  local tier n st fails
  for tier in 1 2; do
    for n in $(seq 3000 -50 1550); do
      [ -f "$CKDIR/model_$n.pt" ] || continue
      if is_pair "$n"; then [ "$tier" = 1 ] || continue; else [ "$tier" = 2 ] || continue; fi
      for st in $(stages_for "$n"); do
        stage_done "$n" "$st" && continue
        fails=0; [ -f "$OUTTOP/m$n/stage_$st.failed" ] && fails=$(wc -l < "$OUTTOP/m$n/stage_$st.failed")
        [ "$fails" -ge 2 ] && continue
        echo "$n $st"; return
      done
    done
  done
}

wait_gpu() {   # 한 번에 Isaac 하나
  while [ "$(count_ps "--device cuda:$DEVNUM( |\$)")" != "0" ]; do say "대기: cuda:$DEVNUM 에 다른 python 이 있다"; sleep "$POLL"; done
}

run_stage() {   # $1=N $2=stage -> 0 이면 성공
  local n=$1 st=$2 ck="$CKDIR/model_$1.pt" o="$OUTTOP/m$1" rc=0 bad=0
  mkdir -p "$o"
  case "$st" in
    core)
      [ -f "$o/checkpoint_sha256.txt" ] || sha256sum "$ck" > "$o/checkpoint_sha256.txt"
      MODES="eval_gt probe_prop_only" bash "$ROOT/foothold_s2/eval/run_sb_eval.sh" "$DEV" "$ck" "$o" < /dev/null; rc=$?
      grep -q "없음" "$o/rc.txt" 2>/dev/null && bad=1
      grep -E "rc=[1-9]" "$o/rc.txt" > /dev/null 2>&1 && bad=1
      if [ "$rc" -eq 0 ] && [ "$bad" -eq 0 ]; then
        PYTHONPATH="$ROOT" PYTHONUTF8=1 "$PY" -m foothold_s2.eval.ex35_gate \
          --latest-turn eval_gt="$o/turn16_eval_gt" probe_prop_only="$o/turn16_probe_prop_only" --latest-map64 "$o/map64/map_modes.json" \
          --base-turn eval_gt="$BASE/turn16_eval_gt" probe_prop_only="$BASE/turn16_probe_prop_only" --base-map64 "$BASE/map64/map_modes.json" \
          --it-in-stage $((n-1500)) --min-stay 500 --out "$o/ex35_verdict.json" > "$o/ex35_verdict.stdout" 2>&1
        vrc=$?
        echo "verdict_rc=$vrc" >> "$o/rc.txt"
        [ "$vrc" -eq 0 ] && [ -s "$o/ex35_verdict.json" ] || { rc=97; }
      fi ;;
    pred)
      MODULE=foothold_s2.eval.turn_probe DEVICE="$DEV" bash "$KIT" "$o/turn16_eval_pred" \
        --task "$TASK" --checkpoint "$ck" --envs 16 --map-mode eval_pred --fixed-terrain --cases all --forward-gaits < /dev/null; r1=$?
      grep -q "TURNPROBE_DONE" "$o/turn16_eval_pred/run.log" || r1=98
      MODULE=foothold_s2.eval.eval_map_modes DEVICE="$DEV" bash "$KIT" "$o/map64_eval_pred" \
        --task "$TASK" --checkpoint "$ck" --envs 64 --steps 300 --modes eval_pred --fixed-terrain < /dev/null; r2=$?
      [ -f "$o/map64_eval_pred/map_modes.json" ] || r2=98
      echo "pred turn16_eval_pred rc=$r1 map64_eval_pred rc=$r2" >> "$o/rc.txt"
      rc=$((r1 + r2)) ;;
    L6|L9)
      MODULE=foothold_s2.eval.eval_map_modes DEVICE="$DEV" bash "$KIT" "$o/hardlevel/$st" \
        --task "$TASK" --checkpoint "$ck" --envs 64 --steps 300 --modes eval_gt,probe_prop_only --fixed-terrain --fixed-level "${st#L}" --commands fwd1.0,fwd0.5 < /dev/null; rc=$?
      [ -f "$o/hardlevel/$st/map_modes.json" ] || rc=98
      echo "hardlevel/$st rc=$rc" >> "$o/rc.txt" ;;
  esac
  return $rc
}

record_receipts() {   # $1=N
  local o="$OUTTOP/m$1" f
  {
    for f in foothold_s2/eval/ex35_gate.py foothold_s2/eval/judge_gate.py foothold_s2/eval/judge_stats.py foothold_s2/eval/ex35_eval_chain2.sh foothold_s2/eval/turn_probe.py foothold_s2/eval/turn_probe_plan.py foothold_s2/eval/run_sb_eval.sh foothold_s2/eval/eval_map_modes.py; do
      sha256sum "$ROOT/$f" | sed "s#$ROOT/##"
    done
    echo "head $(git -C "$ROOT" rev-parse HEAD)"
    echo "dirty $(git -C "$ROOT" status --short foothold_s2 | wc -l)"
    [ -f "$o/ex35_verdict.json" ] && sha256sum "$o/ex35_verdict.json" | sed "s#.*/m$1/#verdict #"
  } > "$o/judge_code_sha256.txt"
  : > "$o/inputs_list.txt"
  for f in map64/map_modes.json map64_eval_pred/map_modes.json hardlevel/L6/map_modes.json hardlevel/L9/map_modes.json \
           turn16_eval_gt/probe_result.json turn16_probe_prop_only/probe_result.json turn16_eval_pred/probe_result.json ex35_verdict.json; do
    if [ -f "$o/$f" ]; then sha256sum "$o/$f" | sed "s#$o/##" >> "$o/inputs_list.txt"; else echo "MISSING $f" >> "$o/inputs_list.txt"; fi
  done
  for d in turn16_eval_gt turn16_probe_prop_only turn16_eval_pred; do
    for c in indep_left indep_right fwd_then_left fwd_then_right left_then_right right_then_left walk_turn_left walk_turn_right fwd0.5 fwd1.0; do
      [ -f "$o/$d/arrays_$c.npz" ] || echo "MISSING $d/arrays_$c.npz" >> "$o/inputs_list.txt"
    done
  done
}

say "EX35 EVAL CHAIN2 start dev=$DEV ckdir=$CKDIR out=$OUTTOP root=$ROOT head=$(git -C "$ROOT" rev-parse HEAD) dirty=$(git -C "$ROOT" status --short foothold_s2 | wc -l)"
[ -z "$(git -C "$ROOT" status --short foothold_s2)" ] || { say "거절: 고정 사본 foothold_s2 가 더럽다"; exit 3; }

while true; do
  ITEM="$(next_item)"
  if [ -z "$ITEM" ]; then
    if [ "$(count_ps "$TRAIN_PATTERN")" = "0" ]; then say "DONE 학습 python 없음 · 대기 단계 없음"; echo DONE > "$OUTTOP/DONE2"; exit 0; fi
    sleep "$POLL"; continue
  fi
  N="${ITEM% *}"; ST="${ITEM#* }"
  S1=$(stat -c %s "$CKDIR/model_$N.pt"); sleep 5; S2=$(stat -c %s "$CKDIR/model_$N.pt"); [ "$S1" = "$S2" ] || sleep 20
  wait_gpu
  T0=$(date +%s)
  say "m$N $ST start"
  run_stage "$N" "$ST"; RC=$?
  T1=$(date +%s)
  echo "$ST start=$T0 end=$T1 seconds=$((T1-T0)) rc=$RC" >> "$OUTTOP/m$N/timing.txt"
  if [ "$RC" -eq 0 ]; then
    echo "rc=0 seconds=$((T1-T0))" > "$OUTTOP/m$N/stage_$ST.done"
    VS=""; [ "$ST" = core ] && VS="verdict $(grep -m1 '"state"' "$OUTTOP/m$N/ex35_verdict.json" 2>/dev/null | tr -d ' \r')"
    say "m$N $ST end ok seconds=$((T1-T0)) $VS"
  else
    echo "rc=$RC at $(date +%s)" >> "$OUTTOP/m$N/stage_$ST.failed"
    say "m$N $ST end FAIL rc=$RC seconds=$((T1-T0))"
  fi
  record_receipts "$N"
done
