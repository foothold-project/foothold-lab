#!/usr/bin/env bash
# Lead executes after the axis-v2 repeats have finished. Analyst prepared this without Kit/GPU.
# Same frozen code and pinned E0 mesh as the existing seed-42 m2000 axis-v2 receipt.
set -eo pipefail
E1_AXIS_CODE=/home/jay/mai/wt/foothold-lab/ex42-launch-e1-v6
E1_AXIS_PY=/home/jay/miniforge3/envs/isaac311/bin/python
E1_AXIS_CKPT=/home/jay/data/foothold/s2_lab/ex42_main_20261112_164150/main/EX-42-B-E1-cmd7seg_20261112_164150/model_2000.pt
E1_AXIS_MESH=/home/jay/data/foothold/s2_lab/ex42_mesh_1111/seed42_E0_c333
E1_AXIS_BASELINE=/home/jay/data/foothold/s2_lab/ex42_main_20261112_164150/main/EX-42-B-E1-cmd7seg_20261112_164150/eval/scores/m2000/axis_v2/axis_v2.json
cd "$E1_AXIS_CODE"
set -a
. /home/jay/mai/foothold-linux.env
set +a
set -u
export PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONUTF8=1
"$E1_AXIS_PY" -B - "$E1_AXIS_CODE" "$E1_AXIS_CKPT" "$E1_AXIS_MESH" "$E1_AXIS_BASELINE" <<'PY'
import hashlib, json, subprocess, sys
from pathlib import Path
from foothold_s2.terrains.ex42_mesh_mount import load_combined_mesh
code, ckpt, mesh, baseline = map(Path, sys.argv[1:])
def sha(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()
assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=code, text=True).strip() == 'c7692789eb7ce1d61d6530b1aa83be4f3ba6ab67'
assert not subprocess.check_output(['git', 'status', '--porcelain'], cwd=code, text=True).strip(), 'frozen code is dirty'
d = json.loads(baseline.read_text())
assert sha(ckpt) == d['checkpoint_sha256'] == '3937df92866b79581f7b27e8b8c9fbde1f7733a85fe5179388fcfd78aa83c4bb'
assert d['ex42_mesh']['mesh_sha256'] == '88197b3adfdde327edc633c025c6ad9aa690ea59aa7df5d51d548f7f56c12a95'
load_combined_mesh(mesh / 'terrain_mesh.npz', d['ex42_mesh']['mesh_sha256'])
assert sha(mesh / 'terrain_mesh.npz') == 'b3e6ab6f5093cc78ad2cbb8848d8caa2969ad44774ad7889d5e16d1d8ed7734d'
assert sha(code / 'foothold_s2/curriculum/ex42-prep.yaml') == d['evaluation_friction']['plan_sha256']
for name, expected in d['source_sha256'].items():
    assert sha(code / 'foothold_s2/eval' / name) == expected, name
assert (d['envs'], d['steps'], d['fixed_level'], d['dt_s']) == (64, 300, 2, .02)
print('CPU_PREFLIGHT_OK: checkpoint, frozen code, five evaluator hashes, plan and pinned E0 mesh match seed 42')
PY
if [[ "${1:-}" == '--check-only' ]]; then
    exit 0
fi
if [[ $# -ne 0 ]]; then
    echo 'Usage: bash run_m2000_sides_seed_repeats.sh [--check-only]' >&2
    exit 2
fi
E1_AXIS_OUTPUT=/home/jay/data/foothold/s2_lab/e1_sides_repeat_20261113/m2000_$(date +%Y%m%d_%H%M%S)
mkdir -p "$(dirname "$E1_AXIS_OUTPUT")"
mkdir "$E1_AXIS_OUTPUT"
printf '%s\n' "$E1_AXIS_OUTPUT" > "$E1_AXIS_OUTPUT/output_root.txt"
cp -- "$0" "$E1_AXIS_OUTPUT/launch.sh"
run_side_seed() {
    local seed=$1 device=$2
    local out="$E1_AXIS_OUTPUT/seed${seed}"
    mkdir "$out"
    local cmd=("$E1_AXIS_PY" -B -m foothold_s2.eval.eval_map_modes
        --ex42-evaluation-plan "$E1_AXIS_CODE/foothold_s2/curriculum/ex42-prep.yaml"
        --task FootholdS2-Go2-S2-SB-v0 --checkpoint "$E1_AXIS_CKPT"
        --envs 64 --steps 300 --modes eval_gt,eval_pred
        --fixed-terrain --fixed-level 2 --terrain-set default --mesh-dir "$E1_AXIS_MESH"
        --command-suite extended --commands side+0.5,side-0.5
        --eval-seed "$seed" --device "$device" --out "$out" --headless
        --kit_args=--/UJITSO/datastore/localCachePath=/home/jay/mai/cache/isaacsim-5.1/DerivedDataCache)
    printf '%q ' "${cmd[@]}" > "$out/argv.sh"
    printf '\n' >> "$out/argv.sh"
    local rc=0
    "${cmd[@]}" </dev/null > "$out/stdout.log" 2> "$out/stderr.log" || rc=$?
    printf '%s\n' "$rc" > "$out/exit_code.txt"
    printf 'seed=%s device=%s rc=%s output=%s\n' "$seed" "$device" "$rc" "$out"
    return "$rc"
}
run_side_seed 7 cuda:0 &
E1_AXIS_PID7=$!
run_side_seed 13 cuda:1 &
E1_AXIS_PID13=$!
E1_AXIS_RC7=0
E1_AXIS_RC13=0
wait "$E1_AXIS_PID7" || E1_AXIS_RC7=$?
wait "$E1_AXIS_PID13" || E1_AXIS_RC13=$?
printf 'side repeat finished: seed7_rc=%s seed13_rc=%s root=%s\n' "$E1_AXIS_RC7" "$E1_AXIS_RC13" "$E1_AXIS_OUTPUT"
[[ "$E1_AXIS_RC7" == 0 && "$E1_AXIS_RC13" == 0 ]]
