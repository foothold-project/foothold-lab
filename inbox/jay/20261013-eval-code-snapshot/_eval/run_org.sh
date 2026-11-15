#!/usr/bin/env bash
# Terrain env origins of the 36 full-record runs (q_eval --fingerprint_only with the exact arguments, GPU 0, guarded).
# Runs after run_hud_prep.sh (which skipped this stage through placeholder files so model_19500 came first).
set -u
cd "$(dirname "$0")"
until grep -q "HUD PREP DONE\|STOP" out/hud_prep.log; do sleep 30; done
grep -q "HUD PREP DONE" out/hud_prep.log || { echo "STOP: HUD prep did not finish"; exit 5; }
PY=C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe
E1=C:/isaac/ext/go2_rl_robotlab/logs/rsl_rl/go2_moe_cts/2026-10-10_12-47-48_e1_seed42_n8192
E2=C:/isaac/ext/go2_rl_robotlab/logs/rsl_rl/go2_moe_cts/2026-10-11_12-39-32_e2_seed43_n8192
GPU=0
export CUDA_DEVICE_ORDER=PCI_BUS_ID CUDA_VISIBLE_DEVICES=$GPU OMNI_KIT_ACCEPT_EULA=YES PYTHONUNBUFFERED=1
FAMS="flat wave slope_up slope_down rough_slope stairs_up stairs_down obstacles"
OFF="--families wave,slope_up,slope_down,rough_slope,stairs_up,stairs_down,obstacles --cells stand,stop03,yawL05,yawR05 --spawn_offset stand=2.5,yaw=2.5,stop=1.75"
for f in out/org_*/env_origins.npy; do
  if head -c 11 "$f" | grep -q PLACEHOLDER; then rm "$f"; fi
done
one() {
  local tag=$1; shift
  if [ -f "out/$tag/env_origins.npy" ]; then echo "RUN $tag SKIP"; return 0; fi
  local t0=$(date +%s)
  "$PY" gpu_guard.py --gpu "$GPU" --log "out/$tag.log" --summary "out/$tag.guard.json" -- "$PY" q_eval.py --headless --tag "$tag" "$@"
  local rc=$?
  echo "RUN $tag GPU$GPU EXIT $rc $(( $(date +%s) - t0 ))s $(date +%H:%M:%S)"
  if [ "$rc" = "99" ]; then echo "STOP: guard stopped $tag (free < 4 GiB)"; exit 99; fi
  if [ "$rc" != "0" ]; then echo "STOP: $tag failed"; exit 4; fi
}
for pair in "fr_:$E1" "e2_:$E2"; do
  pre=${pair%%:*}; dir=${pair#*:}
  for it in 20499 20000; do
    for fam in $FAMS; do one "org_${pre}m${it}_${fam}" --policy student --checkpoint "$dir/model_${it}.pt" --families "$fam" --episodes 100 --fingerprint_only; done
    one "org_${pre}m${it}_offplat" --policy student --checkpoint "$dir/model_${it}.pt" $OFF --episodes 100 --fingerprint_only
  done
done
echo "ORIGINS DONE $(date +%H:%M:%S)"
