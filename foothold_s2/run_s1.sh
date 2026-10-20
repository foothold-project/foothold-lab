#!/usr/bin/env bash
# S1-a 본 학습 실행 (6,000 회, 4096 env). usage: run_s1.sh <scan|blind> <cuda:N> [추가 train_s1 인자...]
# 예) scan 을 GPU 0, blind 를 GPU 1 에 (CUDA_DEVICE_ORDER=PCI_BUS_ID 라 번호는 nvidia-smi 번호):
#   bash foothold_s2/run_s1.sh scan cuda:0 ; bash foothold_s2/run_s1.sh blind cuda:1
# 이어 학습: 끝에 --resume --load_run <폴더> --checkpoint latest.pt (rsl_rl 인자)
# 판정은 종료 코드가 아니라 logs/s1a_<variant>_*/run.log 의 Traceback 과 «Learning iteration» 줄로 한다 (Isaac 은 예외 뒤에도 0 을 낸다).
set -u
V="$1"; DEV="$2"; shift 2
ENV=/c/Users/AI-WS01/anaconda3/envs/isaac311
export PATH="$ENV:$ENV/Library/mingw-w64/bin:$ENV/Library/usr/bin:$ENV/Library/bin:$ENV/Scripts:$ENV/bin:$PATH"
export CONDA_PREFIX="$ENV" OMNI_KIT_ACCEPT_EULA=YES CUDA_DEVICE_ORDER=PCI_BUS_ID PYTHONUNBUFFERED=1
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
STAMP="$(date +%Y%m%d_%H%M%S)"
OUT="$ROOT/logs/s1a_${V}_${STAMP}"
mkdir -p "$OUT"
git rev-parse HEAD > "$OUT/git_head.txt"
git status --short foothold_s2 > "$OUT/git_status.txt"
"$ENV/python.exe" -m foothold_s2.train_s1 --task "FootholdS2-Go2-S1a-${V}-v0" --headless --device "$DEV" \
    --num_envs 4096 --max_iterations 6000 --run_name "s1a_${V}" "$@" > "$OUT/run.log" 2>&1
echo "rc=$?" > "$OUT/rc.txt"
