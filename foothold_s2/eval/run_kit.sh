#!/usr/bin/env bash
# Kit 환경에서 평가 한 번. usage: run_kit.sh <out_dir> <run_eval 인자...>
# 로그는 <out_dir>/run.log. GPU 는 --device cuda:0 (PCI 순서), CUDA_VISIBLE_DEVICES 로 가리지 않는다.
set -u
OUT="$1"; shift 1
ENV=/c/Users/AI-WS01/anaconda3/envs/isaac311
export PATH="$ENV:$ENV/Library/mingw-w64/bin:$ENV/Library/usr/bin:$ENV/Library/bin:$ENV/Scripts:$ENV/bin:$PATH"
export CONDA_PREFIX="$ENV"
export OMNI_KIT_ACCEPT_EULA=YES
export CUDA_DEVICE_ORDER=PCI_BUS_ID
export PYTHONUNBUFFERED=1
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
mkdir -p "$OUT"
cd "$ROOT"
"$ENV/python.exe" -m "${MODULE:-foothold_s2.eval.run_eval}" "$@" --out "$OUT" --headless --device "${DEVICE:-cuda:0}" > "$OUT/run.log" 2>&1
exit $?
