#!/bin/bash
# AME-2 app handoff for X7C = derived_ctl424/avg_X7C_13000_14999/model_avg.pt (user 11-27: the simulation final is the teacher
# the REQ428 students were distilled from), the same jobs as the X9C bundle ame2-m30001 (step2.sh + x9c_gpu.sh), without the three
# void-depth benchmark runs:
#   0 export (CPU): export_ame2_onnx.py wraps the original AME2GazeModel.forward
#   1 GPU lock of this pod, enough free GPU memory: record 200 steps flat / stairs (rec_onnx_vectors.py), speed with the goal re-sent
#     (speed_goal.py); unlock
#   2 the PyTorch reference on CPU (parity_ref.py)
#   POD_HOST=<host name> setsid nohup bash /root/onnx_x7c/x7c_run.sh > /root/onnx_x7c/run.out 2>&1 < /dev/null &
set -u
D=/root/onnx_x7c; S=$D/status.txt; n() { echo "$1 $(date -u +%FT%TZ)" >> $S; }
[ "$(hostname)" = "${POD_HOST:?}" ] || { n "X7C_FAILED host $(hostname)"; exit 1; }
V=/network-volume/limseokheon
B=$V/ame2_x4; AV=$V/derived_ctl424/avg_X7C_13000_14999; CK=$AV/model_avg.pt; CKSHA=b6aa0adc371089fd0bb02252169de2c3350626c627f6a284e2a67ea81bb3e625
PY=/workspace/isaaclab/_isaac_sim/python.sh
AG="agent.algorithm.optimizer=adam agent.algorithm.use_mixed_precision=false agent.algorithm.num_learning_epochs=4 agent.algorithm.num_mini_batches=3 agent.actor.crop_x=12 agent.actor.crop_y=10 agent.actor.roi_margin=0.45"
LOCK=$V/ame2/go2/_runs/gpu_job.lock
for p in export rec meas; do [ -e $D/$p ] && { n "X7C_FAILED $D/$p exists"; exit 1; }; done
[ "$(sha256sum < $CK | cut -c1-64)" = $CKSHA ] || { n "X7C_FAILED checkpoint sha256"; exit 1; }
cd $D && sed -i 's/\r$//' *.py && md5sum *.py *.sh > $D/tools.md5
n "X7C_START pid $$"
# 0 export on the CPU
CUDA_VISIBLE_DEVICES= nice -n 10 timeout 900 $PY $D/export_ame2_onnx.py $B $AV model_avg.pt $D/export > $D/export.log 2>&1
grep -q '^EXPORT_DONE' $D/export.log && n "EXPORT_OK $(grep '^EXPORT_INFO' $D/export.log | cut -c1-400)" || { n "X7C_FAILED export $(tail -2 $D/export.log | tr '\n' ' ' | cut -c1-250)"; exit 1; }
# 1 GPU part
exec 9> $LOCK
flock -w 21600 9 || { n "X7C_FAILED GPU lock busy 6 h"; exit 1; }
used() { timeout 60 nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | head -1 | tr -d ' '; }
for i in $(seq 180); do u=$(used); [ -n "$u" ] && [ "$u" -lt 12000 ] && break; sleep 10; done
u=$(used); { [ -n "$u" ] && [ "$u" -lt 12000 ]; } || { n "X7C_FAILED GPU memory used ${u:-?} MiB"; exit 1; }
n "X7C_LOCKED gpu_used_MiB $u"
run() { local log=$1; shift; setsid timeout -k 60 3600 "$@" > $log 2>&1 9>&- & local ch=$!; wait $ch; local rc=$?
  for i in $(seq 24); do pgrep -g $ch > /dev/null || break; sleep 5; done
  pgrep -g $ch > /dev/null && { kill -TERM -- -$ch; sleep 15; kill -KILL -- -$ch; }
  return $rc; }
mkdir -p $D/meas
cd $B
run $D/rec.log go2/scripts/run.sh py $D/rec_onnx_vectors.py --headless --task Ame2-Go2-Gaze-N9P12 --checkpoint $CK --out_dir $D/rec $AG
grep -q '^REC_DONE ' $D/rec.log && n "REC_OK $(grep '^REC_CHECKS' $D/rec.log | cut -c1-300)" || n "REC_FAILED $(grep -E 'Error|error:' $D/rec.log | tail -2 | tr '\n' ' ' | cut -c1-250)"
n "REC_POSE $(grep '^REC_POSE' $D/rec.log | cut -c1-200)"
run $D/speed.log go2/scripts/run.sh py $D/speed_goal.py --headless --task Ame2-Go2-Gaze-N9P12 --checkpoint $CK --out $D/meas/speed.json $AG
n "SPEED rc $? $(grep '^SPEED ' $D/speed.log | cut -c1-200)"
flock -u 9; exec 9>&-
n "UNLOCKED"
# 2 PyTorch reference on the CPU
[ -s $D/rec/rec_flat.npz ] || { n "X7C_FAILED no recording"; exit 1; }
cd $D && CUDA_VISIBLE_DEVICES= nice -n 10 timeout 900 $PY $D/parity_ref.py $B $AV model_avg.pt $D/rec > $D/ref.log 2>&1
grep -q '^REF_DONE' $D/ref.log && n "REF_OK $(grep '^REF_INFO' $D/ref.log | cut -c1-300)" || n "REF_FAILED $(tail -2 $D/ref.log | tr '\n' ' ' | cut -c1-200)"
n "X7C_DONE"
