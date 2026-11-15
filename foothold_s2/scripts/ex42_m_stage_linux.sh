#!/usr/bin/env bash
# M1 through M4 bounded speed probes. Default is CPU-only command review.
set -euo pipefail

source_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
profile="${FOOTHOLD_LINUX_ENV:-$HOME/mai/foothold-linux.env}"
if [[ ! -f "$profile" ]]; then
    echo "Linux machine profile not found: $profile" >&2
    exit 2
fi
set -a
# shellcheck disable=SC1090
source "$profile"
set +a
export PYTHONPATH="$source_root${PYTHONPATH:+:$PYTHONPATH}"

: "${ISAAC311_PYTHON:?ISAAC311_PYTHON is required}"
: "${GPU_JOBS_QUEUE:?GPU_JOBS_QUEUE is required}"
: "${EX42_M_PARENT_MANIFEST:?Set the manifest beside the pinned m12000 model_6000.pt}"
export CUDA_DEVICE_ORDER=PCI_BUS_ID OMNI_KIT_ACCEPT_EULA=YES PYTHONUNBUFFERED=1
unset CUDA_VISIBLE_DEVICES

out_root="${EX42_M_OUT_ROOT:-/mnt/win-d/mai/data/foothold/s2_lab/ex42_speed_probe_$(date +%Y%m%d_%H%M%S)}"
argv=(
    "$ISAAC311_PYTHON" "$source_root/foothold_s2/scripts/ex42_m_stage_linux.py"
    --source-root "$source_root"
    --source-ref "${EX42_M_SOURCE_REF:-origin/scripter/m-launch-1110}"
    --parent-manifest "$EX42_M_PARENT_MANIFEST"
    --out-root "$out_root"
    --python "$ISAAC311_PYTHON"
    --queue "$GPU_JOBS_QUEUE"
)
if [[ "${LIVE:-0}" == "1" ]]; then
    argv+=(--execute)
fi
exec "${argv[@]}" "$@"
