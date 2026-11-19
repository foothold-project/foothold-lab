#!/usr/bin/env bash
# CPU rehearsal of the new-OUT E2 start seeded from this E2 run's own boundary checkpoint (lead-lx 11/19 07:1x). Starts no training, no GPU.
#   ex42_e2_reentry_rehearse.sh <iteration> <draft folder name>      e.g.  ... 550 reentry_m550
# 1. builds the draft plan + approvals (ex42_e2_reentry_draft: parent pin = model_<iteration>.pt of the run, beam mesh pin, terrain_promotion cell);
# 2. loads the parent checkpoint through the real parent loader (inspect_ex42_stage_parent);
# 3. runs the stage launcher --dry-run (canon check, mesh pin, parent pin, approval, cumulative update) and --print (the P1 evaluation
#    argv must carry the new mesh dir and its geometry sha).
# When the m750 checkpoint exists: the same script with 750 and a new folder name.
# Settings by environment (defaults are today's run): E2_RUN, E2_SOURCE_DIR, E2_MESH_DIR, E2_ADJUST_FROM, E2_OUT_ROOT,
# E2_DRAFT_ARGS (extra draft flags, e.g. "--keep-mesh --no-promotion" for the rollback draft: same weights, old mesh and rule).
set -euo pipefail
it="${1:?iteration}"; name="${2:?draft folder name}"
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; repo="$(cd "$here/../.." && pwd)"
data=/home/jay/data/foothold
run="${E2_RUN:-$data/s2_lab/ex42_main_20261119_013854/main/EX-42-B-E2_20261119_020447}"
src="${E2_SOURCE_DIR:-$data/s2_lab/ex42_record/e2_handoff_20261119_013854/materialized_E2}"
mesh="${E2_MESH_DIR:-$data/sonnet_beam_mesh_1119/b2m_rpy_lv}"
root="${E2_OUT_ROOT:-$data/sonnet_beam_mesh_1119}"
adjust="${E2_ADJUST_FROM:-$data/s2_lab/ex42_record/e2_handoff_20261119_013854/e2-update-adjust.json}"
py="${ISAAC311_PYTHON:-/home/jay/miniforge3/envs/isaac311/bin/python}"
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 CUDA_VISIBLE_DEVICES= PYTHONPATH="$repo"
pin="taskset -c 37-44"
cd "$repo"
out="$root/$name"
$pin "$py" -m foothold_s2.tools.ex42_e2_reentry_draft --source-dir "$src" --run-dir "$run" --iteration "$it" --mesh-dir "$mesh" \
    --out "$out" --adjust-from "$adjust" ${E2_DRAFT_ARGS:-} > "$out.draft.json"
echo "draft: $out ($(grep -o '"new_plan_sha256": "[0-9a-f]*"' "$out.draft.json"))"
$pin "$py" - "$out" "$run" <<'PY'
import sys
from pathlib import Path
from foothold_s2.curriculum.ex42_prep import EX42Plan
from foothold_s2.scripts import ex42_training_entry as t
out, run = Path(sys.argv[1]), sys.argv[2]
plan = EX42Plan.load(out / "ex42-prep.yaml")
t.E_STAGE_SPECS.clear(); t.E_STAGE_SPECS.update(t.e_stage_table(plan.document["stages"]))
ck, r = t.inspect_ex42_stage_parent(plan=plan, stage_id="E2", approvals_path=out / "ex42-approvals.yaml", parent_manifest_path=f"{run}/manifest.json")
print("parent loader: OK local", r["parent_local_update"], "cumulative", r["parent_cumulative_update"], "saved stage", ck["continuous_curriculum"]["stage_id"], "bound", ck["continuous_curriculum"]["maximum_updates"])
PY
export EX42_AUTO_ACTION=next_stage EX42_AUTO_TARGET_STAGE=E2 EX42_AUTO_PLAN="$out/ex42-prep.yaml" EX42_AUTO_APPROVALS="$out/ex42-approvals.yaml"
export EX42_AUTO_PARENT_MANIFEST="$run/manifest.json" EX42_AUTO_PARENT_CHECKPOINT="$run/model_$it.pt"
export EX42_AUTO_GATE_RECEIPT=/nonexistent EX42_AUTO_GATE_SHA256=0
export EX42_SOURCE_REF="$(git rev-parse HEAD)" EX42_MAIN_ROOT="${TMPDIR:-/tmp}/ex42_reentry_rehearsal_main" GPU_JOBS_QUEUE="${GPU_JOBS_QUEUE:-/tmp/ex42_reentry_dry_queue.json}"
mkdir -p "$EX42_MAIN_ROOT"
$pin "$here/ex42_stage_launcher.sh" --dry-run > "$out.dry.log" 2>&1 && echo "launcher --dry-run: rc 0 ($(grep -o 'EX42_STAGE_E2_PREFLIGHT' "$out.dry.log" | head -1))" || { echo "launcher --dry-run REFUSED"; tail -3 "$out.dry.log" | cut -c1-300; exit 1; }
$pin "$here/ex42_stage_launcher.sh" --print > "$out.print.log" 2>&1
grep -o -- '"--mesh-dir", "[^"]*", "--expected-mesh-sha256", "[^"]*"' "$out.print.log" | head -1
grep -o -- '--ex42_plan[= ][^ ]*' "$out.print.log" | head -1
grep -o -- '--ex42_resume_from' "$out.print.log" | head -1 || true
echo "files: $out.draft.json $out.dry.log $out.print.log (nothing started)"
