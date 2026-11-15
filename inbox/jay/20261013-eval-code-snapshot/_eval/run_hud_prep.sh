#!/usr/bin/env bash
# RECORD-HUD preparation on GPU 0, started only after chain_after_e2.sh has printed CHAIN DONE (no training).
#   1. patch q_eval.py (save env_origins.npy) and full_record.py (base_z_w_m), see _mut/patch_origins_and_rename.py
#   2. org_<tag>: q_eval --fingerprint_only with the exact arguments of the 36 full-record runs -> env origins
#      (the pairing fingerprints in meta must equal the original run)
#   3. fr_m19500_* (E1) and e2fr_m19500_* (E2): model_19500, Q main noise off, --full_record
#      (traj must equal the stored m19500_* / e2_m19500_* runs bitwise)
# Every run goes through gpu_guard.py (200 ms, stop below 4096 MiB free).
set -u
cd "$(dirname "$0")"
until grep -q "CHAIN DONE" out/chain_after_e2.log; do
  if grep -q "STOP" out/chain_after_e2.log; then echo "STOP: evaluation chain stopped, not starting"; exit 5; fi
  sleep 30
done
PY=C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe
E1=C:/isaac/ext/go2_rl_robotlab/logs/rsl_rl/go2_moe_cts/2026-10-10_12-47-48_e1_seed42_n8192
E2=C:/isaac/ext/go2_rl_robotlab/logs/rsl_rl/go2_moe_cts/2026-10-11_12-39-32_e2_seed43_n8192
GPU=0
export CUDA_DEVICE_ORDER=PCI_BUS_ID CUDA_VISIBLE_DEVICES=$GPU OMNI_KIT_ACCEPT_EULA=YES PYTHONUNBUFFERED=1
"$PY" _mut/patch_origins_and_rename.py || exit 6
echo "GPU0 baseline before HUD prep: $(nvidia-smi --query-gpu=index,memory.used --format=csv,noheader | head -1)"
FAMS="flat wave slope_up slope_down rough_slope stairs_up stairs_down obstacles"
OFF="--families wave,slope_up,slope_down,rough_slope,stairs_up,stairs_down,obstacles --cells stand,stop03,yawL05,yawR05 --spawn_offset stand=2.5,yaw=2.5,stop=1.75"
one() {  # tag marker args...
  local tag=$1 marker=$2; shift 2
  if [ -f "out/$tag/$marker" ]; then echo "RUN $tag SKIP"; return 0; fi
  local t0=$(date +%s)
  "$PY" gpu_guard.py --gpu "$GPU" --log "out/$tag.log" --summary "out/$tag.guard.json" -- "$PY" q_eval.py --headless --tag "$tag" "$@"
  local rc=$?
  echo "RUN $tag GPU$GPU EXIT $rc $(( $(date +%s) - t0 ))s $(date +%H:%M:%S)"
  if [ "$rc" = "99" ]; then echo "STOP: guard stopped $tag (free < 4 GiB)"; exit 99; fi
  if [ "$rc" != "0" ]; then echo "STOP: $tag failed"; exit 4; fi
}
for pair in "fr_:$E1" "e2_:$E2"; do
  pre=${pair%%:*}; dir=${pair#*:}
  for it in 20000 20499; do
    for fam in $FAMS; do one "org_${pre}m${it}_${fam}" env_origins.npy --policy student --checkpoint "$dir/model_${it}.pt" --families "$fam" --episodes 100 --fingerprint_only; done
    one "org_${pre}m${it}_offplat" env_origins.npy --policy student --checkpoint "$dir/model_${it}.pt" $OFF --episodes 100 --fingerprint_only
  done
done
echo "ORIGINS DONE $(date +%H:%M:%S)"
for pair in "fr_:$E1" "e2fr_:$E2"; do
  pre=${pair%%:*}; dir=${pair#*:}
  for fam in $FAMS; do one "${pre}m19500_${fam}" cells.json --policy student --checkpoint "$dir/model_19500.pt" --families "$fam" --episodes 100 --full_record; done
  one "${pre}m19500_offplat" cells.json --policy student --checkpoint "$dir/model_19500.pt" $OFF --episodes 100 --full_record
done
echo "HUD PREP DONE $(date +%H:%M:%S)"
