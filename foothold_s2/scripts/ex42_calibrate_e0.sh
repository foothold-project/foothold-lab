#!/usr/bin/env bash
set -euo pipefail
if (( $# < 4 )); then
  echo 'usage: ex42_calibrate_e0.sh MESH_DIR MESH_SHA256 NEW_OUTPUT_DIR cuda:0|cuda:1 [--execute]' >&2
  exit 2
fi
mesh_dir=$1
mesh_sha256=$2
out_dir=$3
device=$4
shift 4
source_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
set -a
source "$HOME/mai/foothold-linux.env"
set +a
export PYTHONPATH="$source_root"
export OMNI_KIT_ACCEPT_EULA=YES CUDA_DEVICE_ORDER=PCI_BUS_ID PYTHONUNBUFFERED=1
export KMP_DUPLICATE_LIB_OK=TRUE
checkpoint="$HOME/data/foothold/s2_lab/ex42_main_20261108_123914/main/EX-42-B-stagezero_20261108_123914/model_1000.pt"
exec "$HOME/miniforge3/envs/isaac311/bin/python" -m foothold_s2.ex42_calibrate \
  --checkpoint "$checkpoint" \
  --expected-sha256 20365a2c6d70f94f65f1114471f7df198e56d86db6d02d89cea43c666b95e768 \
  --mesh-dir "$mesh_dir" --expected-mesh-sha256 "$mesh_sha256" \
  --out "$out_dir" --device "$device" "$@"
