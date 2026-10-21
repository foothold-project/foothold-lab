#!/usr/bin/env bash
# S1a-v1.1 본 학습 (6,000 회, 4096 env, 시드 42). usage: run_s1_v11.sh <scan|blind> <cuda:N> [추가 train_s1 인자...]
#   이어 학습: 끝에 --resume --load_run <폴더> --checkpoint latest.pt --load_experiment foothold_s1a_v11
# 판정은 종료 코드가 아니라 logs/s1a_v11_<variant>_*/run.log 의 Traceback 과 train_start_status.json 으로 한다.
set -u
# 팀장 승인 「멈춰」 (lead 10/21): S1a-v1.1 은 종료됐다. 사슬의 재시도가 같은 학습을 다시 띄우지 않게, 이 표시 파일이 있으면 아무것도 하지 않고 끝낸다.
if [ -f /c/Users/AI-WS01/s2_lab/chain/v11_cancelled ]; then echo "S1a-v1.1 취소됨(v11_cancelled): 띄우지 않음"; exit 0; fi
V="$1"; DEV="$2"; shift 2
ENV=/c/Users/AI-WS01/anaconda3/envs/isaac311
export PATH="$ENV:$ENV/Library/mingw-w64/bin:$ENV/Library/usr/bin:$ENV/Library/bin:$ENV/Scripts:$ENV/bin:$PATH"
export CONDA_PREFIX="$ENV" OMNI_KIT_ACCEPT_EULA=YES CUDA_DEVICE_ORDER=PCI_BUS_ID PYTHONUNBUFFERED=1
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
STAMP="$(date +%Y%m%d_%H%M%S)"
OUT="$ROOT/logs/s1a_v11_${V}_${STAMP}"
mkdir -p "$OUT"
git rev-parse HEAD > "$OUT/git_head.txt"
git status --short foothold_s2 > "$OUT/git_status.txt"
"$ENV/python.exe" -m foothold_s2.train_s1 --task "FootholdS2-Go2-S1a-v11-${V}-v0" --headless --device "$DEV" \
    --num_envs 4096 --seed 42 --max_iterations 6000 --run_name "s1a_v11_${V}" "$@" > "$OUT/run.log" 2>&1
echo "rc=$?" > "$OUT/rc.txt"
