#!/bin/bash
# AME-2 app handoff for X9C = derived_ctl424/avg_X9C_13000_14999/model_avg.pt (user 11-25: "x9c 모델도 똑같이 onnx 뽑아서 올려"),
# the GPU part, the same jobs as the m27001 bundle (pp1_all.sh + rerun_np2.sh):
#   1 record 200 steps flat / stairs (rec_onnx_vectors.py)  2 speed with the goal re-sent (speed_goal.py)
#   3 benchmark seed 1001 (tool of tpevf46 = eval_gaze.py 4ed5c4a6, task N9P12-Eval5): depth 0.7 | depth 0.7 without the virtual plane
#     (tool copy with one added line, hydra cannot add sparse_terrains) | reference re-run
#   then the PyTorch reference (CPU) and the comparisons with the tpevf46 output of the same checkpoint.
# Order on pod 2: it waits until the final student evaluation (q428f.sh pass) and the student video smoke test (vidsmoke428.sh) are over
# and no training / evaluator / recorder runs; the aux evaluation (q428x.sh pass) yields to the file ev428x/yield_pass.txt, which this
# script makes at its start and removes at its end (trap). Then the pod-2 GPU lock and an empty GPU.
#   POD_HOST=<pod 2 host name> setsid nohup bash /root/onnx_x9c/x9c_gpu.sh > /root/onnx_x9c/gpu.out 2>&1 < /dev/null &
set -u
D=/root/onnx_x9c; S=$D/gpu_status.txt; n() { echo "$1 $(date -u +%FT%TZ)" >> $S; }
[ "$(hostname)" = "${POD_HOST:?}" ] || { n "X9C_FAILED host $(hostname)"; exit 1; }
V=/network-volume/limseokheon
B=$V/ame2_x8; AV=$V/derived_ctl424/avg_X9C_13000_14999; CK=$AV/model_avg.pt; CKSHA=517900f35f6bfae0021929dac68f85d5243127b3390548e8dc6f85aaca60f4d2
EV=$V/ame2_ev12; T=$EV/go2/_runs/evalgz_tpevf46_b1
REF=$(ls $T/2*/evg_x9avg_14999_s1001.pt | head -1)
PY=/workspace/isaaclab/_isaac_sim/python.sh
AG="agent.algorithm.optimizer=adam agent.algorithm.use_mixed_precision=false agent.algorithm.num_learning_epochs=4 agent.algorithm.num_mini_batches=3 agent.actor.crop_x=12 agent.actor.crop_y=10 agent.actor.roi_margin=0.45"
CA="agent.actor.crop_x=12 agent.actor.crop_y=10 agent.actor.roi_margin=0.45"
LOCK=$V/ame2/go2/_runs/gpu_job_${POD_HOST}.lock
YF=$EV/go2/_runs/ev428x/yield_pass.txt
FST=$EV/go2/_runs/ev428f/status_pass.txt
BUSY='train_stu[.]sh|resume_pass[.]sh|eval_student[.]py|eval_gaze_map5[.]py|record_traj[a-z0-9_]*[.]py|^bash .*/q428f[.]sh |^bash .*/vidsmoke428[.]sh |^bash .*/vidmain428[.]sh '
for p in rec meas evnp; do [ -e $D/$p ] && { n "X9C_FAILED $D/$p exists"; exit 1; }; done
[ -s $D/export/ame2-demo.onnx ] || { n "X9C_FAILED no export"; exit 1; }
[ -n "$REF" ] || { n "X9C_FAILED no tpevf46 reference"; exit 1; }
[ "$(md5sum < $T/eval_gaze.py | cut -c1-8)" = 4ed5c4a6 ] || { n "X9C_FAILED tool md5"; exit 1; }
[ "$(sha256sum < $CK | cut -c1-64)" = $CKSHA ] || { n "X9C_FAILED checkpoint sha256"; exit 1; }
echo "onnx_x9c (user 11-25: X9C ONNX bundle measurements, about 1 h) pid $$" > $YF || { n "X9C_FAILED yield file"; exit 1; }
trap 'rm -f $YF; n "X9C_YIELD_FILE_REMOVED"' EXIT
n "X9C_WAIT pid $$ ref=$REF yield=$YF"
# 1 wait: a final line (DONE / FAILED / ABORTED) after the last WAIT line of the pass final queue, and nothing busy, twice 60 s apart
fin_over() { awk '/^Q428F_PASS_WAIT /{w=NR} /^Q428F_PASS_(DONE|FAILED|ABORTED)/{f=NR} END{exit !(w && f > w)}' $FST; }
idle() { pgrep -f -- "$BUSY" > /dev/null; [ $? = 1 ]; }
t0=$(date +%s); ok=0
while :; do
  [ $(( $(date +%s) - t0 )) -lt 129600 ] || { n "X9C_FAILED waited 36 h"; exit 1; }
  if fin_over && idle; then ok=$((ok + 1)); else ok=0; fi
  [ $ok -ge 2 ] && break
  sleep 60
done
n "X9C_FREE $(grep -E '^Q428F_PASS_(DONE|FAILED|ABORTED)' $FST | tail -1 | cut -c1-120)"
exec 9> $LOCK
flock -w 1800 9 || { n "X9C_FAILED GPU lock busy"; exit 1; }
gpu_empty() { local out; out=$(timeout 60 nvidia-smi --query-compute-apps=pid --format=csv,noheader 2>&1) || return 2; [ -z "$(printf '%s' "$out" | tr -d '[:space:]')" ]; }
for i in $(seq 30); do gpu_empty && break; sleep 10; done
gpu_empty || { n "X9C_FAILED GPU not free"; exit 1; }
idle || { n "X9C_FAILED busy after the lock"; exit 1; }
n "X9C_LOCKED"
run() { local log=$1; shift; setsid timeout -k 60 5400 "$@" > $log 2>&1 9>&- & local ch=$!; wait $ch; local rc=$?
  for i in $(seq 24); do pgrep -g $ch > /dev/null || break; sleep 5; done
  pgrep -g $ch > /dev/null && { kill -TERM -- -$ch; sleep 15; kill -KILL -- -$ch; }
  for i in $(seq 24); do gpu_empty && break; sleep 5; done; return $rc; }
mkdir -p $D/meas
cd $B
run $D/rec.log go2/scripts/run.sh py $D/rec_onnx_vectors.py --headless --task Ame2-Go2-Gaze-N9P12 --checkpoint $CK --out_dir $D/rec $AG
grep -q '^REC_DONE ' $D/rec.log && n "REC_OK $(grep '^REC_CHECKS' $D/rec.log | cut -c1-300)" || n "REC_FAILED $(grep -E 'Error|error:' $D/rec.log | tail -2 | tr '\n' ' ' | cut -c1-250)"
n "REC_POSE $(grep '^REC_POSE' $D/rec.log | cut -c1-200)"
run $D/speed.log go2/scripts/run.sh py $D/speed_goal.py --headless --task Ame2-Go2-Gaze-N9P12 --checkpoint $CK --out $D/meas/speed.json $AG
n "SPEED rc $? $(grep '^SPEED ' $D/speed.log | cut -c1-200)"
E=$D/evnp; mkdir -p $E; cp $T/eval_gaze.py $T/fpc_lib.py $E/ || { n "X9C_FAILED tool copy"; exit 1; }
$PY - "$E/eval_gaze.py" <<'PY'
import sys
p = sys.argv[1]; s = open(p).read()
a = "    env_cfg.scene.num_envs = args.num_envs\n"
assert s.count(a) == 1
s = s.replace(a, a + '    env_cfg.events.virtual_floor.params["sparse_terrains"] = ()  # onnx_x9c 11-25: app condition, no virtual plane\n')
open(p, "w").write(s)
PY
[ $? = 0 ] || { n "X9C_FAILED tool patch"; exit 1; }
n "NP_TOOL $(md5sum $E/eval_gaze.py $E/fpc_lib.py | cut -c1-12 | tr '\n' ' ')"
cd $EV
EA="--headless --task Ame2-Go2-Gaze-N9P12-Eval5 --num_envs 2400 --episodes 5 --checkpoint $CK --seed 1001"
run $D/ev_d07.log go2/scripts/run.sh py $T/eval_gaze.py $EA --out $D/meas/ev_d07.pt $CA "env.events.virtual_floor.params.depth_range=[-0.7,-0.7]"
n "EV_D07 rc $? $(tail -1 $D/ev_d07.log | cut -c1-80)"
run $D/ev_d07np.log go2/scripts/run.sh py $E/eval_gaze.py $EA --out $D/meas/ev_d07np.pt $CA "env.events.virtual_floor.params.depth_range=[-0.7,-0.7]"
n "EV_D07NP rc $? $(tail -1 $D/ev_d07np.log | cut -c1-80)"
run $D/ev_rerun.log go2/scripts/run.sh py $T/eval_gaze.py $EA --out $D/meas/ev_rerun.pt $CA
n "EV_RERUN rc $? $(tail -1 $D/ev_rerun.log | cut -c1-80)"
flock -u 9; exec 9>&-
n "UNLOCKED"
rm -f $YF
cd $D && nice -n 10 timeout 900 $PY $D/parity_ref.py $B $AV model_avg.pt $D/rec > $D/ref.log 2>&1
grep -q '^REF_DONE' $D/ref.log && n "REF_OK $(grep '^REF_INFO' $D/ref.log | cut -c1-300)" || n "REF_FAILED $(tail -2 $D/ref.log | tr '\n' ' ' | cut -c1-200)"
for v in d07 d07np rerun; do [ -s $D/meas/ev_$v.pt ] && $PY $D/cmp_depth07.py $REF $D/meas/ev_$v.pt $D/meas/cmp_$v.json > $D/meas/cmp_$v.txt 2>&1; n "CMP_$v $(grep '_all' $D/meas/cmp_$v.txt | tr -s ' ' | cut -c1-120)"; done
n "X9C_DONE"
