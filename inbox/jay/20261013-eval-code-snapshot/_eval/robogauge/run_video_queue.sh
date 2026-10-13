#!/usr/bin/env bash
# Videos after the stress queue (one pipeline at a time, single process each).
# Friction 0.6 (middle of the 0.2..1.0 stress range), seed 0 (= first level-search seed).
# Levels: the reference's max passed level at friction 0.6 (from its stress run), for both policies;
#         plus E1 model_20000 at its own max passed level at friction 0.6 where that differs.
set -uo pipefail
HERE=C:/isaac/ext/go2_rl_robotlab/_eval/robogauge
OUT=C:/isaac/ext/go2_rl_robotlab/_eval/out/robogauge
REF=C:/isaac/checkpoints/robogauge/go2_rl_robotlab/go2_moe_cts_symmetry_v5.1_52k_0.6953_20260703/exported/policy.pt
E1=$OUT/jit/e1_model_20000.pt
F=0.6
nvidia-smi > "$OUT/videos_nvsmi_before.txt" 2>&1
JOBS=(
  "ref_sym_v5.1|$REF|flat|-"
  "e1_model_20000|$E1|flat|-"
  "ref_sym_v5.1|$REF|wave|8"
  "e1_model_20000|$E1|wave|8"
  "e1_model_20000|$E1|wave|6"
  "ref_sym_v5.1|$REF|slope_fd|8"
  "e1_model_20000|$E1|slope_fd|8"
  "e1_model_20000|$E1|slope_fd|5"
  "ref_sym_v5.1|$REF|slope_bd|9"
  "e1_model_20000|$E1|slope_bd|9"
  "e1_model_20000|$E1|slope_bd|7"
  "ref_sym_v5.1|$REF|stairs_fd|10"
  "e1_model_20000|$E1|stairs_fd|10"
  "e1_model_20000|$E1|stairs_fd|9"
  "ref_sym_v5.1|$REF|stairs_bd|10"
  "e1_model_20000|$E1|stairs_bd|10"
  "e1_model_20000|$E1|stairs_bd|7"
  "ref_sym_v5.1|$REF|obstacle|10"
  "e1_model_20000|$E1|obstacle|10"
)
first=1
for j in "${JOBS[@]}"; do
  IFS='|' read -r label model terrain level <<< "$j"
  if [ $first -eq 1 ]; then
    ( sleep 20; nvidia-smi > "$OUT/videos_nvsmi_during.txt" 2>&1 ) &
    first=0
  fi
  bash "$HERE/run_video.sh" "$label" "$model" "$terrain" "$level" "$F" 0
done
wait
echo "[videos] done $(date '+%F %T')"
