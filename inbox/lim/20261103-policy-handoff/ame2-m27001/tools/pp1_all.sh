#!/bin/bash
# AME-2 app handoff for the averaged model tp424_in_p1_s5_from17000/model_16999.pt (user 11-19: "팟1에서 똑같이 onnx 뽑아줘").
# 1 export (CPU)  2 GPU lock + record 200 steps flat / stairs  3 PyTorch reference (CPU)  4 speed with the goal re-sent
# 5 benchmark seed 1001 (tool of tpevf24, task N9P12-Eval5): depth 0.7 | depth 0.7 without the virtual plane | reference re-run
#   setsid nohup bash /root/onnx_pp1/pp1_all.sh > /root/onnx_pp1/all.out 2>&1 < /dev/null &
D=/root/onnx_pp1; S=$D/all_status.txt; n() { echo "$1 $(date -u +%FT%TZ)" >> $S; }
# 공개용: 원래는 팟 1 컨테이너 호스트 이름을 직접 적어 비교함. 다시 쓸 때 POD1_HOST 에 넣는다
[ "$(hostname)" = "${POD1_HOST:?}" ] || { n "ALL_FAILED host $(hostname)"; exit 1; }
B=/network-volume/limseokheon/ame2_pp1; RUN=$B/logs/rsl_rl/go2_gaze_teacher/tp424_in_p1_s5_from17000; CK=$RUN/model_16999.pt
EV=/network-volume/limseokheon/ame2_ev12; TOOL=go2/_runs/evalgz_tpevf24_b1/eval_gaze.py
REF=$(ls $EV/go2/_runs/evalgz_tpevf24_b1/2*/evg_tpa4p1_16999_s1001.pt | head -1)
PY=/workspace/isaaclab/_isaac_sim/python.sh
AG="agent.algorithm.optimizer=adam agent.algorithm.use_mixed_precision=false agent.algorithm.num_learning_epochs=4 agent.algorithm.num_mini_batches=3 agent.actor.crop_x=12 agent.actor.crop_y=10 agent.actor.roi_margin=0.45"
LOCK=/network-volume/limseokheon/ame2/go2/_runs/gpu_job.lock
for p in rec meas; do [ -e $D/$p ] && { n "ALL_FAILED $D/$p exists"; exit 1; }; done
mkdir -p $D/meas
n "ALL_START ref=$REF"
cd $D && timeout 900 $PY $D/export_ame2_onnx.py $B $RUN model_16999.pt $D/export > $D/export.log 2>&1
grep -q '^EXPORT_DONE' $D/export.log || { n "ALL_FAILED export: $(tail -2 $D/export.log | tr '\n' ' ' | cut -c1-200)"; exit 1; }
n "EXPORT_OK $(grep '^EXPORT_INFO' $D/export.log | cut -c1-260)"
exec 9> $LOCK
flock -w 600 9 || { n "ALL_FAILED GPU lock busy"; exit 1; }
gpu_empty() { local out; out=$(timeout 60 nvidia-smi --query-compute-apps=pid --format=csv,noheader 2>&1) || return 2; [ -z "$(printf '%s' "$out" | tr -d '[:space:]')" ]; }
gpu_empty || { n "ALL_FAILED GPU not free"; exit 1; }
n "LOCKED"
run() { local log=$1; shift; setsid timeout -k 60 2400 "$@" > $log 2>&1 9>&- & local ch=$!; wait $ch; local rc=$?
  for i in $(seq 24); do pgrep -g $ch > /dev/null || break; sleep 5; done
  pgrep -g $ch > /dev/null && { kill -TERM -- -$ch; sleep 15; kill -KILL -- -$ch; }
  for i in $(seq 24); do gpu_empty && break; sleep 5; done; return $rc; }
cd $B
run $D/rec.log go2/scripts/run.sh py $D/rec_onnx_vectors.py --headless --task Ame2-Go2-Gaze-N9P12 --checkpoint $CK --out_dir $D/rec $AG
grep -q '^REC_DONE ' $D/rec.log || { n "ALL_FAILED rec: $(grep -E 'Error|error:' $D/rec.log | tail -2 | tr '\n' ' ' | cut -c1-250)"; flock -u 9; exit 1; }
n "REC_OK $(grep '^REC_CHECKS' $D/rec.log | cut -c1-300)"
n "REC_POSE $(grep '^REC_POSE' $D/rec.log | cut -c1-200)"
run $D/speed.log go2/scripts/run.sh py $D/speed_goal.py --headless --task Ame2-Go2-Gaze-N9P12 --checkpoint $CK --out $D/meas/speed.json $AG
n "SPEED rc $? $(grep '^SPEED ' $D/speed.log | cut -c1-200)"
cd $EV
EA="--headless --task Ame2-Go2-Gaze-N9P12-Eval5 --num_envs 2400 --episodes 5 --checkpoint $CK --seed 1001"
CA="agent.actor.crop_x=12 agent.actor.crop_y=10 agent.actor.roi_margin=0.45"
run $D/ev_d07.log go2/scripts/run.sh py $TOOL $EA --out $D/meas/ev_d07.pt $CA "env.events.virtual_floor.params.depth_range=[-0.7,-0.7]"
n "EV_D07 rc $? $(tail -1 $D/ev_d07.log | cut -c1-80)"
run $D/ev_d07np.log go2/scripts/run.sh py $TOOL $EA --out $D/meas/ev_d07np.pt $CA "env.events.virtual_floor.params.depth_range=[-0.7,-0.7]" "env.events.virtual_floor.params.sparse_terrains=[]"
n "EV_D07NP rc $? $(tail -1 $D/ev_d07np.log | cut -c1-80)"
run $D/ev_rerun.log go2/scripts/run.sh py $TOOL $EA --out $D/meas/ev_rerun.pt $CA
n "EV_RERUN rc $? $(tail -1 $D/ev_rerun.log | cut -c1-80)"
flock -u 9; exec 9>&-
n "UNLOCKED"
cd $D && timeout 900 $PY $D/parity_ref.py $B $RUN model_16999.pt $D/rec > $D/ref.log 2>&1
grep -q '^REF_DONE' $D/ref.log && n "REF_OK $(grep '^REF_INFO' $D/ref.log | cut -c1-300)" || n "REF_FAILED $(tail -2 $D/ref.log | tr '\n' ' ' | cut -c1-200)"
for v in d07 d07np rerun; do [ -s $D/meas/ev_$v.pt ] && $PY $D/cmp_depth07.py $REF $D/meas/ev_$v.pt $D/meas/cmp_$v.json > $D/meas/cmp_$v.txt 2>&1; n "CMP_$v $(grep '_all' $D/meas/cmp_$v.txt | tr -s ' ' | cut -c1-120)"; done
n "ALL_DONE"
