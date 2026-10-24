#!/usr/bin/env bash
# EX-30 / EX-31 창 1 한 판 (SONNET-X25 후속): B1500 -> 부모 지형 칸 복원 -> 추가 250 갱신 -> model_1750. 팀장 승인 전에는 띄우지 않는다.
# usage: run_ex3031_window1.sh <EX-30|EX-31> <cuda:N> <출력 폴더>      보통 launch_ex3031_window1.py 가 부른다(EX-30 cuda:0, EX-31 cuda:1, 30 초 간격, 숨김).
set -u
EXP="$1"; DEV="$2"; OUT="$3"
ENV=/c/Users/AI-WS01/anaconda3/envs/isaac311
export PATH="$ENV:$ENV/Library/mingw-w64/bin:$ENV/Library/usr/bin:$ENV/Library/bin:$ENV/Scripts:$ENV/bin:$PATH"
export CONDA_PREFIX="$ENV" OMNI_KIT_ACCEPT_EULA=YES CUDA_DEVICE_ORDER=PCI_BUS_ID PYTHONUNBUFFERED=1 KMP_DUPLICATE_LIB_OK=TRUE
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
mkdir -p "$OUT"
git rev-parse HEAD > "$OUT/git_head.txt"
git status --short foothold_s2 > "$OUT/git_status.txt"
"$ENV/python.exe" -m foothold_s2.scripts.train_ex3031_window1 --exp "$EXP" --headless --device "$DEV" > "$OUT/train.log" 2>&1
echo "rc=$?" > "$OUT/rc.txt"
grep -q "EX3031_W1_DONE" "$OUT/train.log" || echo "DONE 줄 없음(Isaac 은 예외 뒤에도 0 을 낼 수 있다)" >> "$OUT/rc.txt"
