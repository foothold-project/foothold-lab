#!/usr/bin/env bash
# QC-E1: E1 student capability along checkpoints. Declared before launch 2026-10-11
# (pre-check: GPU1 315d098f 3926 MiB used, pid 25916 on GPU1, E2 pid 173044 on GPU0; neither touched).
#   condition : exactly the Q-E1 main runs (q_eval.py defaults: terrain seed 1000, difficulty 0.5, one family per run,
#               11 cells x 100 episodes at the tile centre; band = 7 rough families x stand/stop03/yawL05/yawR05 x 100,
#               offsets stand/yaw 2.5 m, stop 1.75 m), deployed student path, extended fingerprint in meta.json
#   repro     : current q_eval.py re-runs m20000_noise_flat and m20000_flat; traj must equal the stored runs bitwise
#               (links the stored 20000 / 20499 results to this code)
#   order     : 19500 noise on, 19500 noise off, 15000 on, 10000 on, 5000 on (8 centre runs + band each)
#   rules     : q_post writes the current and the proposed (span) definitions, proposal (a) for low speed
#   guard     : GPU1 free - expected (centre 5.3 GB, band 6.4 GB) >= 4 GiB before each run; stop if a run's recorded
#               peak left < 4 GiB. Budget 7200 s from the first run: a run that would not fit is skipped and listed.
set -u
cd "$(dirname "$0")"
PY=C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe
RUN=C:/isaac/ext/go2_rl_robotlab/logs/rsl_rl/go2_moe_cts/2026-10-10_12-47-48_e1_seed42_n8192
export CUDA_DEVICE_ORDER=PCI_BUS_ID CUDA_VISIBLE_DEVICES=1 OMNI_KIT_ACCEPT_EULA=YES PYTHONUNBUFFERED=1
BUDGET=7200
T0FILE=out/qc_t0.txt
[ -f $T0FILE ] || date +%s > $T0FILE
free1() { nvidia-smi --query-gpu=index,memory.total,memory.used --format=csv,noheader,nounits | awk -F', ' '$1==1{print $2-$3}'; }
one() {  # tag need_MiB expect_s args...
  local tag=$1 need=$2 exp=$3; shift 3
  if [ -f "out/$tag/cells.json" ]; then echo "RUN $tag SKIP"; return 0; fi
  local now=$(date +%s) t0=$(cat $T0FILE)
  if [ $(( now - t0 + exp )) -gt $BUDGET ]; then echo "BUDGET LEFT-OUT $tag"; return 0; fi
  local f=$(free1)
  if [ $(( f - need )) -lt 4096 ]; then echo "STOP before $tag: GPU1 free ${f} MiB - expected ${need} < 4096"; exit 3; fi
  "$PY" q_eval.py --headless --tag "$tag" "$@" > "out/$tag.log" 2>&1
  local rc=$?
  local pf=$("$PY" -c "import json;m=json.load(open('out/$tag/meta.json'));g=lambda s:int(s[1].split(',')[2].split()[0]);print(16303-max(g(m[k]) for k in ('smi_start','smi_after_env','smi_mid','smi_end') if m.get(k)))" 2>/dev/null || echo NA)
  echo "RUN $tag EXIT $rc $(( $(date +%s) - now ))s elapsed=$(( $(date +%s) - t0 ))s peak_free_MiB=$pf $(nvidia-smi --query-gpu=index,memory.used --format=csv,noheader | tr '\n' ' ')"
  if [ "$rc" != "0" ]; then echo "STOP: $tag failed"; exit 4; fi
  if [ "$pf" != "NA" ] && [ "$pf" -lt 4096 ]; then echo "STOP after $tag: peak free ${pf} MiB < 4096"; exit 5; fi
}
FAMS="flat wave slope_up slope_down rough_slope stairs_up stairs_down obstacles"
OFF="--families wave,slope_up,slope_down,rough_slope,stairs_up,stairs_down,obstacles --cells stand,stop03,yawL05,yawR05 --spawn_offset stand=2.5,yaw=2.5,stop=1.75"
ckpt() {  # it noise(on|off)
  local it=$1 nn=$2 nf="" pre="m${1}_"
  if [ "$nn" = on ]; then nf="--obs_noise"; pre="m${1}_noise_"; fi
  for fam in $FAMS; do
    one "${pre}${fam}" 5300 100 --policy student --checkpoint "$RUN/model_${it}.pt" --families "$fam" --episodes 100 $nf
  done
  one "${pre}offplat" 6400 140 --policy student --checkpoint "$RUN/model_${it}.pt" $OFF --episodes 100 $nf
}
one qc_repro_m20000_noise_flat 5300 100 --policy student --checkpoint "$RUN/model_20000.pt" --families flat --episodes 100 --obs_noise
one qc_repro_m20000_flat 5300 100 --policy student --checkpoint "$RUN/model_20000.pt" --families flat --episodes 100
ckpt 19500 on
ckpt 19500 off
ckpt 15000 on
ckpt 10000 on
ckpt 5000 on
echo "QC DONE"
