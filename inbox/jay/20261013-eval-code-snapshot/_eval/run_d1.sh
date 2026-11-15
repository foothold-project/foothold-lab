#!/usr/bin/env bash
# D1 (teacher height-layout diagnosis) declared before launch 2026-10-11:
#   what: E1 teacher mean path, normal vs one frozen height permutation (seed 2026), checkpoints 20000 and 20499
#   episodes: same as Q-E1 main (8 terrains x 11 cells x 100, difficulty 0.5, noise off, eval seed 1000)
#             plus Q-E1 off-platform run (7 rough x stand,stop03,yawL05,yawR05 x 100, offsets stand/yaw 2.5 stop 1.75)
#             = 36 runs, 2 x 2 x (8 x 1100 + 2800) = 46,400 episodes. Student condition reuses Q-E1 runs (pairing hash).
#   GPU: GPU 1 only (CUDA_DEVICE_ORDER=PCI_BUS_ID CUDA_VISIBLE_DEVICES=1). GPU 0 (E2) and pid 25916 untouched.
#   guard: a run starts only if GPU 1 free minus its expected use (5.3 GB, offplat 6.4 GB) stays >= 4 GiB;
#          after each run, stop the batch if the run's recorded peak left < 4 GiB free.
#   stage: `bash run_d1.sh first` runs only t20000_flat (then meta is re-read by hand); `bash run_d1.sh rest` runs the rest.
set -u
cd "$(dirname "$0")"
PY=C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe
RUN=C:/isaac/ext/go2_rl_robotlab/logs/rsl_rl/go2_moe_cts/2026-10-10_12-47-48_e1_seed42_n8192
export CUDA_DEVICE_ORDER=PCI_BUS_ID CUDA_VISIBLE_DEVICES=1 OMNI_KIT_ACCEPT_EULA=YES PYTHONUNBUFFERED=1
free1() { nvidia-smi --query-gpu=index,memory.total,memory.used --format=csv,noheader,nounits | awk -F', ' '$1==1{print $2-$3}'; }
one() {  # tag expected_MiB args...
  local tag=$1 need=$2; shift 2
  if [ -f "out/$tag/cells.json" ]; then echo "RUN $tag SKIP"; return 0; fi
  local f=$(free1)
  if [ $(( f - need )) -lt 4096 ]; then echo "STOP before $tag: GPU1 free ${f} MiB - expected ${need} < 4096"; exit 3; fi
  local t0=$(date +%s)
  "$PY" q_eval.py --headless --tag "$tag" "$@" > "out/$tag.log" 2>&1
  local rc=$?
  local peakfree=$("$PY" -c "import json;m=json.load(open('out/$tag/meta.json'));g=lambda s:int(s[1].split(',')[2].split()[0]);print(16303-max(g(m[k]) for k in ('smi_after_env','smi_mid','smi_end') if m.get(k)))" 2>/dev/null || echo NA)
  echo "RUN $tag EXIT $rc $(( $(date +%s) - t0 ))s peak_free_MiB=$peakfree $(nvidia-smi --query-gpu=index,memory.used --format=csv,noheader | tr '\n' ' ')"
  if [ "$rc" != "0" ]; then echo "STOP: $tag failed"; exit 4; fi
  if [ "$peakfree" != "NA" ] && [ "$peakfree" -lt 4096 ]; then echo "STOP after $tag: peak free ${peakfree} MiB < 4096"; exit 5; fi
}
OFF="--families wave,slope_up,slope_down,rough_slope,stairs_up,stairs_down,obstacles --cells stand,stop03,yawL05,yawR05 --spawn_offset stand=2.5,yaw=2.5,stop=1.75"
if [ "${1:-rest}" = "first" ]; then
  one t20000_flat 5400 --policy teacher --checkpoint "$RUN/model_20000.pt" --families flat --episodes 100
  echo "D1 FIRST DONE"; exit 0
fi
for it in 20000 20499; do
  for fam in flat wave slope_up slope_down rough_slope stairs_up stairs_down obstacles; do
    one "t${it}_${fam}" 5400 --policy teacher --checkpoint "$RUN/model_${it}.pt" --families "$fam" --episodes 100
    one "tp${it}_${fam}" 5400 --policy teacher --height_perm_seed 2026 --checkpoint "$RUN/model_${it}.pt" --families "$fam" --episodes 100
  done
  one "t${it}_offplat" 6500 --policy teacher --checkpoint "$RUN/model_${it}.pt" $OFF --episodes 100
  one "tp${it}_offplat" 6500 --policy teacher --height_perm_seed 2026 --checkpoint "$RUN/model_${it}.pt" $OFF --episodes 100
done
echo "D1 DONE"
