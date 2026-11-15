#!/usr/bin/env bash
# EX-30 / EX-31 짧은 Kit 시험 (SONNET-X25): fresh(부모 전환 + 10 갱신 + 저장) -> 새 프로세스 resume(2 갱신). 실험 하나씩, GPU 한 장.
# usage: run_ex3031_smoke.sh <cuda:N> <EX-30|EX-31>      (학습 본 실행이 아님. 숨김 창으로 띄울 것: Start-Process -WindowStyle Hidden)
set -u
DEV="$1"; EXP="$2"
ENV=/c/Users/AI-WS01/anaconda3/envs/isaac311
export PATH="$ENV:$ENV/Library/mingw-w64/bin:$ENV/Library/usr/bin:$ENV/Library/bin:$ENV/Scripts:$ENV/bin:$PATH"
export CONDA_PREFIX="$ENV" OMNI_KIT_ACCEPT_EULA=YES CUDA_DEVICE_ORDER=PCI_BUS_ID PYTHONUNBUFFERED=1 KMP_DUPLICATE_LIB_OK=TRUE
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
STAMP="$(date +%Y%m%d_%H%M%S)"
OUT="$ROOT/logs/ex3031_smoke_${EXP}_${STAMP}"
mkdir -p "$OUT"
git rev-parse HEAD > "$OUT/git_head.txt"
git status --short foothold_s2 > "$OUT/git_status.txt"
EXPL="$(echo "$EXP" | tr 'A-Z' 'a-z')"
"$ENV/python.exe" -m foothold_s2.scripts.train_ex3031_smoke --exp "$EXP" --mode fresh --headless --device "$DEV" > "$OUT/fresh.log" 2>&1
echo "fresh_rc=$?" > "$OUT/rc.txt"
grep -q "EX3031_SMOKE_DONE" "$OUT/fresh.log" || { echo "fresh: DONE 줄 없음" >> "$OUT/rc.txt"; exit 1; }       # Isaac 은 예외 뒤에도 0 을 낼 수 있어 로그 줄로 판정
CK="$(ls -dt logs/rsl_rl/foothold_s2_ex3031_smoke/*_${EXPL}-fresh 2>/dev/null | head -1)/model_1510.pt"
echo "child_ckpt=$CK" >> "$OUT/rc.txt"
[ -f "$CK" ] || { echo "no model_1510.pt" >> "$OUT/rc.txt"; exit 1; }
"$ENV/python.exe" -m foothold_s2.scripts.train_ex3031_smoke --exp "$EXP" --mode resume --child_ckpt "$CK" --headless --device "$DEV" > "$OUT/resume.log" 2>&1
echo "resume_rc=$?" >> "$OUT/rc.txt"
grep -q "EX3031_SMOKE_DONE" "$OUT/resume.log" || echo "resume: DONE 줄 없음" >> "$OUT/rc.txt"
