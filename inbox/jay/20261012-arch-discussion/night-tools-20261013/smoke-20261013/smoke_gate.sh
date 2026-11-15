#!/usr/bin/env bash
# lead 10/13 저녁: ASTRA 17c 와 함께 낼 실제 확인 1 (gate 학습 1 회 · GPU 0 · 1024 env · 3 update · cmdr on).
# 전 사슬: isaac_slot v2 -> gpu_guard -> usd_isolate_run -> branch_run --gate. 출력은 _eval/out_smoke 아래만.
set -u
cd C:/isaac/ext/go2_rl_robotlab/_eval/branch || exit 3
PY=C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe
E1=C:/isaac/ext/go2_rl_robotlab/logs/rsl_rl/go2_moe_cts/2026-10-10_12-47-48_e1_seed42_n8192
BRO=../out_smoke/branch
export BRANCH_OUT="$BRO"
export CUDA_DEVICE_ORDER=PCI_BUS_ID CUDA_VISIBLE_DEVICES=0 OMNI_KIT_ACCEPT_EULA=YES PYTHONUNBUFFERED=1
unset BRANCH_CONTRACT_CONFIRMED
mkdir -p "$BRO/_usd" ../slot || exit 3
tag=smoke_gate2_s1043_on
ATT="smoke-$tag-$(date +%m%d%H%M%S)-$$"
SINCE=$(date +%s)
echo "START $(date '+%F %T') attempt $ATT"
"$PY" ../isaac_slot.py --watch_log "$BRO/$tag.log" --record "$BRO/$tag.slot.json" --attempt "$ATT" --usd_root "$BRO/_usd/$ATT" \
    --lock ../slot/isaac_convert.lock --registry ../slot/isaac_usd_registry.json --scan_dirs "$BRO,../out_branch,../out_uncr" -- \
  "$PY" ../gpu_guard.py --gpu 0 --min_free_mib 256 --log "$BRO/$tag.log" --summary "$BRO/$tag.guard.json" -- \
  "$PY" ../usd_isolate_run.py branch_run.py --headless --gate --tag "$tag" --parent "$E1/model_20000.pt" --seed 1043 --num_envs 1024 --updates 3 --cmdr on
rc=$?
echo "EXIT $rc $(( $(date +%s) - SINCE ))s $(date '+%F %T')"
echo "--- slot"; cat "$BRO/$tag.slot.json"; echo
echo "--- guard"; cat "$BRO/$tag.guard.json"; echo
echo "--- assigned"; cat "$BRO/_usd/$ATT/assigned.jsonl"
echo "--- usd dirs"; ls "$BRO/_usd/$ATT/IsaacLab" 2>&1
echo "--- log checks"; grep -c "Traceback (most recent call last)" "$BRO/$tag.log"; grep -c "Unresolved reference" "$BRO/$tag.log"; grep -n "\[BRANCH\] done\|IsaacLab.usd_\|FOOTHOLD" "$BRO/$tag.log" | head -20
echo "--- tmp IsaacLab new since start"; find "$TEMP/IsaacLab" "/tmp/IsaacLab" -maxdepth 1 -newermt "@$SINCE" 2>/dev/null | head
echo "--- out files"; ls -la "$BRO/$tag" 2>&1
cat "$BRO/_usd/$ATT/isolate_state.json"; grep -n "USD-ISOLATE" "$BRO/$tag.log"
