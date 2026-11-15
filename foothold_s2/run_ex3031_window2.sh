#!/usr/bin/env bash
# EX-30 / EX-31 창 2 한 판 (SONNET-X25 후속): 창 1 자식 model_1750 에서 정확 재개 -> 추가 250 갱신 -> model_2000. 자동 기동 판정(window2_gate.py)이 통과시킨 뒤에만 부른다.
# usage: run_ex3031_window2.sh <EX-30|EX-31> <cuda:0> <창 1 model_1750.pt> <출력 폴더>
set -u
EXP="$1"; DEV="$2"; CKPT="$3"; OUT="$4"
ENV=/c/Users/AI-WS01/anaconda3/envs/isaac311
export PATH="$ENV:$ENV/Library/mingw-w64/bin:$ENV/Library/usr/bin:$ENV/Library/bin:$ENV/Scripts:$ENV/bin:$PATH"
export CONDA_PREFIX="$ENV" OMNI_KIT_ACCEPT_EULA=YES CUDA_DEVICE_ORDER=PCI_BUS_ID PYTHONUNBUFFERED=1 KMP_DUPLICATE_LIB_OK=TRUE
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
mkdir -p "$OUT"
git rev-parse HEAD > "$OUT/git_head.txt"
git status --short foothold_s2 > "$OUT/git_status.txt"
"$ENV/python.exe" -m foothold_s2.scripts.train_ex3031_window2 --exp "$EXP" --child_ckpt "$CKPT" --headless --device "$DEV" > "$OUT/train.log" 2>&1
echo "rc=$?" > "$OUT/rc.txt"
grep -q "EX3031_W2_DONE" "$OUT/train.log" || echo "DONE 줄 없음(Isaac 은 예외 뒤에도 0 을 낼 수 있다)" >> "$OUT/rc.txt"
