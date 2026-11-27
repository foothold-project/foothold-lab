#!/bin/bash
# app-condition benchmark, try 3: copy of the tool (eval_gaze.py 4ed5c4a6 + fpc_lib.py) with ONE added line that empties the virtual
# floor's sparse_terrains (no plane anywhere); hydra cannot add that key (isaaclab dict.py:167). Depth fixed 0.7 via hydra as before.
D=/root/onnx_pp1; S=$D/all_status.txt; n() { echo "$1 $(date -u +%FT%TZ)" >> $S; }
# 공개용: 원래는 팟 1 컨테이너 호스트 이름을 직접 적어 비교함. 다시 쓸 때 POD1_HOST 에 넣는다
[ "$(hostname)" = "${POD1_HOST:?}" ] || exit 1
T=/network-volume/limseokheon/ame2_ev12/go2/_runs/evalgz_tpevf24_b1
E=$D/evnp; rm -rf $E; mkdir -p $E; cp $T/eval_gaze.py $T/fpc_lib.py $E/ || exit 1
python3 - "$E/eval_gaze.py" <<'PY'
import sys
p = sys.argv[1]; s = open(p).read()
a = "    env_cfg.scene.num_envs = args.num_envs\n"
assert s.count(a) == 1
s = s.replace(a, a + '    env_cfg.events.virtual_floor.params["sparse_terrains"] = ()  # onnx_pp1 11-19: app condition, no virtual plane\n')
open(p, "w").write(s)
PY
[ $? = 0 ] || { n "NP3_FAILED patch"; exit 1; }
diff $T/eval_gaze.py $E/eval_gaze.py; md5sum $E/eval_gaze.py $E/fpc_lib.py
CK=/network-volume/limseokheon/ame2_pp1/logs/rsl_rl/go2_gaze_teacher/tp424_in_p1_s5_from17000/model_16999.pt
REF=$(ls $T/2*/evg_tpa4p1_16999_s1001.pt | head -1)
exec 9> /network-volume/limseokheon/ame2/go2/_runs/gpu_job.lock
flock -w 600 9 || { n "NP3_FAILED lock"; exit 1; }
out=$(nvidia-smi --query-compute-apps=pid --format=csv,noheader); [ -z "$(printf '%s' "$out" | tr -d '[:space:]')" ] || { n "NP3_FAILED GPU busy"; exit 1; }
n "NP3_START"
rm -f $D/meas/ev_d07np.pt
cd /network-volume/limseokheon/ame2_ev12
setsid timeout -k 60 2400 go2/scripts/run.sh py $E/eval_gaze.py --headless --task Ame2-Go2-Gaze-N9P12-Eval5 --num_envs 2400 --episodes 5 \
  --checkpoint $CK --seed 1001 --out $D/meas/ev_d07np.pt agent.actor.crop_x=12 agent.actor.crop_y=10 agent.actor.roi_margin=0.45 \
  "env.events.virtual_floor.params.depth_range=[-0.7,-0.7]" > $D/ev_d07np3.log 2>&1 9>&- &
ch=$!; wait $ch; rc=$?
for i in $(seq 24); do pgrep -g $ch > /dev/null || break; sleep 5; done
n "NP3_EV rc $rc $(tail -1 $D/ev_d07np3.log | cut -c1-80)"
flock -u 9
[ -s $D/meas/ev_d07np.pt ] && /workspace/isaaclab/_isaac_sim/python.sh $D/cmp_depth07.py $REF $D/meas/ev_d07np.pt $D/meas/cmp_d07np.json > $D/meas/cmp_d07np.txt 2>&1
n "NP3_DONE $(grep '_all' $D/meas/cmp_d07np.txt | tr -s ' ')"
