#!/usr/bin/env bash
# EX-23 (SONNET-X23): START 구조 G1(지각 모듈 + 정답/복원 지도 입력, est learned) + EX-11 환경 + v2 처럼 약한 DR + 행동 지연 끔. 1501 회 · 50 회마다 저장.
# usage: run_s2_x23.sh <cuda:N> [추가 train_start 인자...]    (3072 env · seed 42 · run 이름 ex23-g1)
# 실행 중에는 이 저장소의 소비 코드를 고치지 않는다(manifest 가 저장 때 감시).
set -u
DEV="$1"; shift 1
ENV=/c/Users/AI-WS01/anaconda3/envs/isaac311
export PATH="$ENV:$ENV/Library/mingw-w64/bin:$ENV/Library/usr/bin:$ENV/Library/bin:$ENV/Scripts:$ENV/bin:$PATH"
export CONDA_PREFIX="$ENV" OMNI_KIT_ACCEPT_EULA=YES CUDA_DEVICE_ORDER=PCI_BUS_ID PYTHONUNBUFFERED=1 KMP_DUPLICATE_LIB_OK=TRUE
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
STAMP="$(date +%Y%m%d_%H%M%S)"
OUT="$ROOT/logs/s2_x23_ex23-g1_${STAMP}"
mkdir -p "$OUT"
git rev-parse HEAD > "$OUT/git_head.txt"
git status --short foothold_s2 > "$OUT/git_status.txt"
"$ENV/python.exe" foothold_s2/scripts/train_start.py --task FootholdS2-Go2-S2-X23-v0 --headless --device "$DEV"     --num_envs 3072 --max_iterations 1501 --seed 42 --run_name ex23-g1 --map_input reconstruction "$@" > "$OUT/run.log" 2>&1
echo "rc=$?" > "$OUT/rc.txt"
