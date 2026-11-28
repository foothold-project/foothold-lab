#!/bin/bash
# AME-2 app handoff for X7C, the void-depth part (the same three runs as x9c_gpu.sh for X9C): benchmark seed 1001 with the tool of the
# X7C reference evaluation tpevf43 (eval_gaze.py md5 4ed5c4a6, task N9P12-Eval5, 2400 robots, 5 episodes): reference re-run |
# depth fixed 0.7 | depth 0.7 without the virtual plane (tool copy with one added line, hydra cannot add sparse_terrains), then the
# per-terrain comparisons with the tpevf43 output of the same checkpoint (cmp_depth07.py).
#   POD_HOST=<host name> setsid nohup bash /root/onnx_x7c/x7c_void.sh > /root/onnx_x7c/void.out 2>&1 < /dev/null &
set -u
D=/root/onnx_x7c; S=$D/void_status.txt; n() { echo "$1 $(date -u +%FT%TZ)" >> $S; }
[ "$(hostname)" = "${POD_HOST:?}" ] || { n "VOID_FAILED host $(hostname)"; exit 1; }
V=/network-volume/limseokheon
AV=$V/derived_ctl424/avg_X7C_13000_14999; CK=$AV/model_avg.pt; CKSHA=b6aa0adc371089fd0bb02252169de2c3350626c627f6a284e2a67ea81bb3e625
EV=$V/ame2_ev12; T=$EV/go2/_runs/evalgz_tpevf43_b1
REF=$T/20261120T162222Z_353089/evg_x7avg_14999_s1001.pt
PY=/workspace/isaaclab/_isaac_sim/python.sh
CA="agent.actor.crop_x=12 agent.actor.crop_y=10 agent.actor.roi_margin=0.45"
LOCK=$V/ame2/go2/_runs/gpu_job.lock
[ -e $D/evnp ] && { n "VOID_FAILED $D/evnp exists"; exit 1; }
[ -s $REF ] || { n "VOID_FAILED no tpevf43 reference"; exit 1; }
[ "$(md5sum < $T/eval_gaze.py | cut -c1-8)" = 4ed5c4a6 ] || { n "VOID_FAILED tool md5"; exit 1; }
[ "$(sha256sum < $CK | cut -c1-64)" = $CKSHA ] || { n "VOID_FAILED checkpoint sha256"; exit 1; }
sed -i 's/\r$//' $D/cmp_depth07.py
n "VOID_START pid $$ ref=$REF"
exec 9> $LOCK
flock -w 21600 9 || { n "VOID_FAILED GPU lock busy 6 h"; exit 1; }
used() { timeout 60 nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | head -1 | tr -d ' '; }
for i in $(seq 180); do u=$(used); [ -n "$u" ] && [ "$u" -lt 8000 ] && break; sleep 10; done
u=$(used); { [ -n "$u" ] && [ "$u" -lt 8000 ]; } || { n "VOID_FAILED GPU memory used ${u:-?} MiB"; exit 1; }
n "VOID_LOCKED gpu_used_MiB $u"
run() { local log=$1; shift; setsid timeout -k 60 5400 "$@" > $log 2>&1 9>&- & local ch=$!; wait $ch; local rc=$?
  for i in $(seq 24); do pgrep -g $ch > /dev/null || break; sleep 5; done
  pgrep -g $ch > /dev/null && { kill -TERM -- -$ch; sleep 15; kill -KILL -- -$ch; }
  return $rc; }
E=$D/evnp; mkdir -p $E $D/meas; cp $T/eval_gaze.py $T/fpc_lib.py $E/ || { n "VOID_FAILED tool copy"; exit 1; }
$PY - "$E/eval_gaze.py" <<'PY'
import sys
p = sys.argv[1]; s = open(p).read()
a = "    env_cfg.scene.num_envs = args.num_envs\n"
assert s.count(a) == 1
s = s.replace(a, a + '    env_cfg.events.virtual_floor.params["sparse_terrains"] = ()  # onnx_x7c 11-27: app condition, no virtual plane\n')
open(p, "w").write(s)
PY
[ $? = 0 ] || { n "VOID_FAILED tool patch"; exit 1; }
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
for v in d07 d07np rerun; do [ -s $D/meas/ev_$v.pt ] && $PY $D/cmp_depth07.py $REF $D/meas/ev_$v.pt $D/meas/cmp_$v.json > $D/meas/cmp_$v.txt 2>&1; n "CMP_$v $(grep '_all' $D/meas/cmp_$v.txt | tr -s ' ' | cut -c1-120)"; done
n "VOID_DONE"
