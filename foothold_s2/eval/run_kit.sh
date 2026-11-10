#!/usr/bin/env bash
# Kit 환경에서 평가 한 번. usage: run_kit.sh <out_dir> <run_eval 인자...>
# 로그는 <out_dir>/run.log. GPU 는 --device cuda:0 (PCI 순서), CUDA_VISIBLE_DEVICES 로 가리지 않는다.
set -u
OUT="$1"; shift 1
if [ "$(uname -s)" = "Linux" ]; then
  # ai-lx01: the interpreter comes from the machine profile environment (machines/AI-WS01-linux.env.example)
  : "${ISAAC311_PYTHON:?ISAAC311_PYTHON is not set (source the machine env file)}"
  PY="$ISAAC311_PYTHON"
  ENV="$(dirname "$(dirname "$PY")")"
  export PATH="$ENV/bin:$PATH"
  export CONDA_PREFIX="$ENV"
else
  ENV=/c/Users/AI-WS01/anaconda3/envs/isaac311
  PY="$ENV/python.exe"
  export PATH="$ENV:$ENV/Library/mingw-w64/bin:$ENV/Library/usr/bin:$ENV/Library/bin:$ENV/Scripts:$ENV/bin:$PATH"
  export CONDA_PREFIX="$ENV"
fi
export OMNI_KIT_ACCEPT_EULA=YES
export CUDA_DEVICE_ORDER=PCI_BUS_ID
export PYTHONUNBUFFERED=1
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
mkdir -p "$OUT"
cd "$ROOT"
"$PY" -m "${MODULE:-foothold_s2.eval.run_eval}" "$@" --out "$OUT" --headless --device "${DEVICE:-cuda:0}" > "$OUT/run.log" 2>&1
exit $?
