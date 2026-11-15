#!/usr/bin/env bash
# One CPU dry run of the stage launcher per EX-42 stage (E1 .. E6b); prints a table: stage, rc, first error line.
# No Kit, no GPU, no output folder. Stand-in parent for stages whose real parent run does not exist yet:
#   EX42_MATRIX_PARENT_MANIFEST / EX42_MATRIX_PARENT_CHECKPOINT (default: the finished E0 run, as the E1 dry run uses).
# Usage: ex42_launcher_dry_matrix.sh [stage ...]    (default: E1 E1F E2 E3 E4 E5 M E6a E6b)
set -uo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
E0="${EX42_MATRIX_E0_RUN:-/home/jay/data/foothold/s2_lab/ex42_main_20261111_072218/main/EX-42-B-E0_20261111_072218}"
export EX42_AUTO_ACTION=next_stage
export EX42_AUTO_PARENT_MANIFEST="${EX42_MATRIX_PARENT_MANIFEST:-$E0/manifest.json}"
export EX42_AUTO_PARENT_CHECKPOINT="${EX42_MATRIX_PARENT_CHECKPOINT:-$E0/model_250.pt}"
export EX42_AUTO_GATE_RECEIPT=/nonexistent EX42_AUTO_GATE_SHA256=0
export EX42_MESH_DIR="${EX42_MESH_DIR:-/home/jay/data/foothold/s2_lab/ex42_mesh_1111/seed42_E0_c333}"
export EX42_MESH_SHA256="${EX42_MESH_SHA256:-88197b3adfdde327edc633c025c6ad9aa690ea59aa7df5d51d548f7f56c12a95}"
export EX42_SOURCE_REF="${EX42_SOURCE_REF:-$(git -C "$here" rev-parse HEAD)}"
export EX42_MAIN_ROOT="${EX42_MAIN_ROOT:-${TMPDIR:-/tmp}/ex42_dry_matrix_main}"
export CUDA_VISIBLE_DEVICES=
stages=("$@"); [[ ${#stages[@]} -eq 0 ]] && stages=(E1 E1F E2 E3 E4 E5 M E6a E6b)
printf '%-5s %-4s %s\n' stage rc first_error
for s in "${stages[@]}"; do
    log="$(mktemp)"
    EX42_AUTO_TARGET_STAGE="$s" timeout 400 "$here/ex42_stage_launcher.sh" --dry-run >"$log" 2>&1
    rc=$?
    err="$(grep -E 'Error|refused|Traceback' "$log" | grep -v '^Traceback' | tail -1 | cut -c1-230)"
    [[ $rc -eq 0 ]] && err="$(grep -o 'EX42_[A-Z0-9_]*PREFLIGHT' "$log" | head -1)"
    printf '%-5s %-4s %s\n' "$s" "$rc" "$err"
    rm -f "$log"
done
