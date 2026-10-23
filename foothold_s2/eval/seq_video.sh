#!/usr/bin/env bash
# Project-owned replacement for s2_lab/seq_video.sh. Seven positional arguments stay the same.
# The caller must use a fresh output name and verify <name>.done before consuming files.
set -euo pipefail

if [ "$#" -ne 7 ]; then
  echo 'usage: seq_video.sh OUT NAME POLICY CHECKPOINT LABEL flat|rough DEVICE' >&2
  exit 2
fi

REPO=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
ENV=${SEQ_VIDEO_ENV:-/c/Users/AI-WS01/anaconda3/envs/isaac311}
PYTHON=${SEQ_VIDEO_PYTHON:-$ENV/python.exe}
RECORDER=${SEQ_VIDEO_RECORDER:-C:/Users/AI-WS01/s2_lab/record_seq.py}
export PATH="$ENV:$ENV/Library/mingw-w64/bin:$ENV/Library/usr/bin:$ENV/Library/bin:$ENV/Scripts:$ENV/bin:$PATH"
export CONDA_PREFIX="$ENV" OMNI_KIT_ACCEPT_EULA=YES CUDA_DEVICE_ORDER=PCI_BUS_ID PYTHONUNBUFFERED=1 KMP_DUPLICATE_LIB_OK=TRUE
cd "$REPO"
exec "$PYTHON" -m foothold_s2.eval.seq_video "$@" --python "$PYTHON" --recorder "$RECORDER"
