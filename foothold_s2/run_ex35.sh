#!/usr/bin/env bash
# EX-35 (S-B10 m1500 -> 회전 명령 과정 첫 판) 전용 기동 스크립트. run_sb.sh 는 1501 고정이라 쓰지 않는다.
# 인자는 ex35_launch.py 가 정하고 validate_launch 로 검증하며 부모 SHA 를 카드와 대조한 뒤 영수증을 찍는다. 기동은 팀장 승인 뒤 lead 가 한다.
# usage: run_ex35.sh <main|smoke2> <cuda:N> <model_1500.pt 경로>        (DRY=1 이면 영수증만 찍고 학습은 띄우지 않는다)
set -u
KIND="$1"; DEV="$2"; PARENT="$3"
ENV=/c/Users/AI-WS01/anaconda3/envs/isaac311
export PATH="$ENV:$ENV/Library/mingw-w64/bin:$ENV/Library/usr/bin:$ENV/Library/bin:$ENV/Scripts:$ENV/bin:$PATH"
export CONDA_PREFIX="$ENV" OMNI_KIT_ACCEPT_EULA=YES CUDA_DEVICE_ORDER=PCI_BUS_ID PYTHONUNBUFFERED=1 KMP_DUPLICATE_LIB_OK=TRUE PYTHONUTF8=1
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
[ -z "$(git status --short foothold_s2)" ] || { echo "거절: foothold_s2 더러움"; exit 3; }
STAMP="$(date +%Y%m%d_%H%M%S)"
END_BY="$(date -d '+24 hours' --iso-8601=seconds)"
OUT="$ROOT/logs_gate/ex35_${KIND}_${STAMP}"
mkdir -p "$OUT"
git rev-parse HEAD > "$OUT/git_head.txt"
git status --short foothold_s2 > "$OUT/git_status.txt"
PYTHONPATH="$ROOT" "$ENV/python.exe" -m foothold_s2.ex35_launch "$KIND" "$DEV" "$PARENT" --end-by "$END_BY" > "$OUT/launch_receipt.json" || { echo "거절: 인자 영수증 실패"; exit 4; }
cat "$OUT/launch_receipt.json"
mapfile -t ARGS < <(PYTHONPATH="$ROOT" "$ENV/python.exe" -m foothold_s2.ex35_launch "$KIND" "$DEV" "$PARENT" --end-by "$END_BY" --print-args)
printf '%s\n' "${ARGS[@]}" > "$OUT/launch_args.txt"
[ "${DRY:-0}" = "1" ] && { echo "DRY: 학습은 띄우지 않음 ($OUT)"; exit 0; }
"$ENV/python.exe" foothold_s2/scripts/train_sb.py "${ARGS[@]}" > "$OUT/run.log" 2>&1
echo "rc=$?" > "$OUT/rc.txt"
grep -q "TRAIN_START_STATUS done" "$OUT/run.log" || echo "DONE 줄 없음(Isaac 은 예외 뒤에도 0 을 낼 수 있다)" >> "$OUT/rc.txt"
