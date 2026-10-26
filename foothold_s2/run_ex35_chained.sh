#!/usr/bin/env bash
# SONNET-X27l: EX-35 기동기 2판. 학습을 띄울 때 저장본 평가 사슬(ex35_eval_chain2.sh)과 PRIORITY_BUSY 감시기(ex35_priority_marker.py)를 함께 띄운다.
# run_ex35.sh 는 지금 도는 EX-35 학습의 부모 bash 가 읽고 있어서 고치지 않고 새 이름으로 둔다.
# usage: run_ex35_chained.sh <main|smoke2> <학습 cuda:N> <model_1500.pt 경로> [평가 cuda:M (기본 cuda:1)]      (DRY=1 이면 사전 점검 · 영수증만, 아무것도 띄우지 않는다)
# 순서: 사전 점검(전부 학습 전에) -> 학습 -> 체크포인트 폴더가 생기면 사슬 -> 감시기 -> 세 PID 와 사슬 출력 자리를 launch_pids.json 에 적는다.
# 사슬이나 감시기가 안 뜨면 방금 띄운 학습(이 스크립트의 자식)을 끄고 거절한다(학습만 뜨는 일이 없게). 거절은 rc.txt 에 남는다.
set -u
KIND="$1"; DEV="$2"; PARENT="$3"; EVAL_DEV="${4:-cuda:1}"
ENV=/c/Users/AI-WS01/anaconda3/envs/isaac311
export PATH="$ENV:$ENV/Library/mingw-w64/bin:$ENV/Library/usr/bin:$ENV/Library/bin:$ENV/Scripts:$ENV/bin:$PATH"
export CONDA_PREFIX="$ENV" OMNI_KIT_ACCEPT_EULA=YES CUDA_DEVICE_ORDER=PCI_BUS_ID PYTHONUNBUFFERED=1 KMP_DUPLICATE_LIB_OK=TRUE PYTHONUTF8=1
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
TRAIN_SCRIPT="${TRAIN_SCRIPT:-foothold_s2/scripts/train_sb.py}"          # 시험용 덮어쓰기
CHAIN_SCRIPT="${CHAIN_SCRIPT:-foothold_s2/eval/ex35_eval_chain2.sh}"
MARKER="${MARKER:-C:/mai/wt/foothold-lab/impl-turncases/logs/ex35_eval/PRIORITY_BUSY}"
LOGROOT="${LOGROOT:-$ROOT/logs/rsl_rl/foothold_s2_sb}"
WAIT_DIR_S="${WAIT_DIR_S:-300}"
refuse() { echo "거절: $1"; [ -n "${OUT:-}" ] && echo "refused: $1" >> "$OUT/rc.txt"; exit "${2:-6}"; }
winpids() {   # $1 = 정규식. 일치하는 python.exe · bash.exe 의 Windows PID (PowerShell 자신은 제외)
  powershell.exe -NoProfile -Command "try { @(Get-CimInstance Win32_Process | Where-Object { (\$_.Name -eq 'python.exe' -or \$_.Name -eq 'bash.exe') -and \$_.CommandLine -match '$1' } | ForEach-Object { \$_.ProcessId }) -join ',' } catch { 'ERR' }" 2>/dev/null | tr -d '\r\n '
}

[ -z "$(git status --short foothold_s2)" ] || { echo "거절: foothold_s2 더러움"; exit 3; }
STAMP="$(date +%Y%m%d_%H%M%S)"
END_BY="$(date -d '+24 hours' --iso-8601=seconds)"
OUT="$ROOT/logs_gate/ex35_${KIND}_${STAMP}"
EVALOUT="$OUT/eval"
mkdir -p "$OUT" "$EVALOUT"
git rev-parse HEAD > "$OUT/git_head.txt"
git status --short foothold_s2 > "$OUT/git_status.txt"
PYTHONPATH="$ROOT" "$ENV/python.exe" -m foothold_s2.ex35_launch "$KIND" "$DEV" "$PARENT" --end-by "$END_BY" > "$OUT/launch_receipt.json" || { echo "거절: 인자 영수증 실패"; exit 4; }
cat "$OUT/launch_receipt.json"
mapfile -t ARGS < <(PYTHONPATH="$ROOT" "$ENV/python.exe" -m foothold_s2.ex35_launch "$KIND" "$DEV" "$PARENT" --end-by "$END_BY" --print-args | tr -d '\r')
[ "${#ARGS[@]}" -gt 0 ] || { echo "거절: 인자 목록이 비었다"; exit 5; }
: > "$OUT/launch_argv_repr.txt"
for A in "${ARGS[@]}"; do
  printf '%q\n' "$A" >> "$OUT/launch_argv_repr.txt"
  case "$A" in ""|*[[:space:]]*|*$'\r'*) echo "거절: argv 에 CR · 공백 · 빈 값 (${A@Q})"; exit 5;; esac
done
printf '%s\n' "${ARGS[@]}" > "$OUT/launch_args.txt"

# ---- 사전 점검 (학습을 띄우기 전에 전부) ----
[ "$EVAL_DEV" != "$DEV" ] || refuse "평가 장치가 학습 장치와 같다 ($DEV)"
case "$EVAL_DEV" in cuda:[0-9]) ;; *) refuse "평가 장치 형식 ($EVAL_DEV)";; esac
[ -f "$ROOT/$CHAIN_SCRIPT" ] || refuse "사슬 스크립트 없음 ($CHAIN_SCRIPT)"
bash -n "$ROOT/$CHAIN_SCRIPT" || refuse "사슬 스크립트 문법 오류"
[ -f "$ROOT/foothold_s2/eval/ex35_priority_marker.py" ] || refuse "감시기 스크립트 없음"
[ -f "$ROOT/$TRAIN_SCRIPT" ] || refuse "학습 스크립트 없음 ($TRAIN_SCRIPT)"
[ -d "$LOGROOT" ] || mkdir -p "$LOGROOT" || refuse "학습 로그 폴더를 만들 수 없다 ($LOGROOT)"
mkdir -p "$(dirname "$MARKER")" || refuse "표식 폴더를 만들 수 없다"
[ -d "$(dirname "$MARKER")" ] || refuse "표식 폴더 없음"
PYTHONPATH="$ROOT" "$ENV/python.exe" "$ROOT/foothold_s2/eval/ex35_priority_marker.py" --top "$EVALOUT" --marker "$OUT/marker_selftest" --chain-pattern "NO_SUCH_CHAIN_$STAMP" --once > "$OUT/marker_selftest.txt" 2>&1 || refuse "감시기 자체 시험 실패 ($(tail -c 200 "$OUT/marker_selftest.txt"))"
grep -qx "idle" "$OUT/marker_selftest.txt" || refuse "감시기 자체 시험 결과가 idle 이 아님 ($(tail -c 200 "$OUT/marker_selftest.txt"))"
CHAIN_TAG="$(basename "$OUT")"
cat > "$OUT/launch_plan.json" <<EOF
{"kind": "$KIND", "train_device": "$DEV", "eval_device": "$EVAL_DEV", "out": "$OUT", "chain_out": "$EVALOUT", "marker": "$MARKER", "chain_script": "$CHAIN_SCRIPT", "log_root": "$LOGROOT", "preflight": "ok"}
EOF
if [ "${DRY:-0}" = "1" ]; then
  echo "DRY: 사전 점검 통과 · 학습 · 사슬 · 감시기는 띄우지 않음 ($OUT)"
  exit 0
fi

# ---- 학습 ----
T0FILE="$OUT/.t0"; : > "$T0FILE"; sleep 1
"$ENV/python.exe" "$TRAIN_SCRIPT" "${ARGS[@]}" > "$OUT/run.log" 2>&1 &
TRAIN_BASH_PID=$!
CKDIR=""
for ((i = 0; i < WAIT_DIR_S; i += 5)); do
  CKDIR="$(find "$LOGROOT" -maxdepth 1 -mindepth 1 -type d -name '*ex35-s2a*' -newer "$T0FILE" 2>/dev/null | head -1)"
  [ -n "$CKDIR" ] && break
  kill -0 "$TRAIN_BASH_PID" 2>/dev/null || break
  sleep 5
done
TRAIN_PID="$(winpids "$TRAIN_SCRIPT.*--run_name ex35-s2a" | awk -F, '{print $NF}')"

abort() {   # 이 스크립트가 방금 띄운 학습만 끈다
  echo "거절: $1"
  echo "refused: $1" >> "$OUT/rc.txt"
  [ -n "$TRAIN_PID" ] && taskkill //PID "$TRAIN_PID" //T //F > /dev/null 2>&1
  kill "$TRAIN_BASH_PID" 2>/dev/null
  exit 7
}
[ -n "$CKDIR" ] || abort "학습 체크포인트 폴더가 ${WAIT_DIR_S} 초 안에 안 생겼다 (학습이 죽었을 수 있다)"
[ -n "$TRAIN_PID" ] || abort "학습 python PID 를 못 찾았다"

# ---- 사슬 ----
TRAIN_PROC_PATTERN="${TRAIN_PROC_PATTERN:-$TRAIN_SCRIPT.*--run_name ex35-s2a}" nohup bash "$ROOT/$CHAIN_SCRIPT" "$EVAL_DEV" "$CKDIR" "$EVALOUT" < /dev/null > "$OUT/chain.stdout" 2>&1 &
CHAIN_BASH_PID=$!
sleep 15
kill -0 "$CHAIN_BASH_PID" 2>/dev/null || abort "평가 사슬이 안 떴다 ($(tail -c 200 "$OUT/chain.stdout" | tr -d '\r'))"
grep -q "CHAIN2 start" "$EVALOUT/chain2.log" 2>/dev/null || abort "평가 사슬 시작 줄이 없다 (chain2.log)"
CHAIN_PID="$(winpids "ex35_eval_chain2.sh.*$CHAIN_TAG|$CHAIN_SCRIPT.*$CHAIN_TAG" | awk -F, '{print $1}')"
[ -n "$CHAIN_PID" ] || abort "사슬 Windows PID 를 못 찾았다"

# ---- 감시기 ----
PYTHONPATH="$ROOT" nohup "$ENV/python.exe" "$ROOT/foothold_s2/eval/ex35_priority_marker.py" --top "$EVALOUT" --marker "$MARKER" --chain-pattern "$CHAIN_TAG" < /dev/null > "$OUT/watcher.stdout" 2>&1 &
sleep 5
WATCH_PID="$(winpids "ex35_priority_marker.py.*$CHAIN_TAG" | awk -F, '{print $1}')"
[ -n "$WATCH_PID" ] || abort "PRIORITY_BUSY 감시기가 안 떴다 ($(tail -c 200 "$OUT/watcher.stdout" | tr -d '\r'))"

cat > "$OUT/launch_pids.json" <<EOF
{"time": "$(date --iso-8601=seconds)", "train_pid": $TRAIN_PID, "chain_pid": $CHAIN_PID, "watcher_pid": $WATCH_PID, "checkpoint_dir": "$CKDIR", "chain_out": "$EVALOUT", "chain_log": "$EVALOUT/chain2.log", "marker": "$MARKER", "eval_device": "$EVAL_DEV"}
EOF
cat "$OUT/launch_pids.json"
wait "$TRAIN_BASH_PID"
echo "rc=$?" > "$OUT/rc.txt"
grep -q "TRAIN_START_STATUS done" "$OUT/run.log" || echo "DONE 줄 없음(Isaac 은 예외 뒤에도 0 을 낼 수 있다)" >> "$OUT/rc.txt"
