#!/bin/bash
# AME-2 real-robot bundle (TU student, model_19999), step 3: record the student evaluation env (task Ame2-Go2-Gaze-Student-N9P12-Eval5,
# the training code of the students, noise of the student groups off) with the existing recorder rec_student.py of rec430 (unchanged),
# levels 0 and 4 (stones 0 and 2), 1 episode, the rough sub-terrain made flat (max_slope_deg 0, max_roughness_m 0) so that the recorded
# robot of (rough, 0) stands on a flat tile; then extract the two tagged robots (rough 0 = flat, stair_up 4 = stairs), 200 policy steps,
# into a small npz (extract_stu.py). Outputs in the work folder STU_WORK on the container disk (not in the shared _runs folders).
#   POD_HOST=<host name> STU_WORK=<work folder> AME2_VOLUME=<volume folder> ISAACLAB_DIR=<Isaac Lab folder> setsid nohup bash stu_rec.sh > rec.out 2>&1 < /dev/null &
set -u
D=${STU_WORK:?}; S=$D/status.txt; n() { echo "$1 $(date -u +%FT%TZ)" >> $S; }
[ "$(hostname)" = "${POD_HOST:?}" ] || { n "STUREC_FAILED host $(hostname)"; exit 1; }
V=${AME2_VOLUME:?}
EV=$V/ame2_stev; R=$EV/go2/_runs/rec430
CK=$V/ame2_stu/logs/rsl_rl/go2_gaze_student/2026-11-22_19-41-48_stu_tu_x7c_n4096_s42/model_19999.pt
CKSHA=34eba83771f7564f93c163afdfcbefa8620780c44b920e2edb0a1c9b49d42793
MJ=$V/ame2_stu/mapper/mapper_tu_jit.pt; MJSHA=52dd869b9fe5bc0ee1973138e72d56d66bee459626da36fed2e2efa716a0e060
TJ=$V/ame2_stu/teacher/x7c_teacher.jit
PY=${ISAACLAB_DIR:?}/_isaac_sim/python.sh
LOCK=$V/ame2/go2/_runs/gpu_job.lock
[ -e $D/rec ] && { n "STUREC_FAILED $D/rec exists"; exit 1; }
[ "$(sha256sum < $CK | cut -c1-64)" = $CKSHA ] || { n "STUREC_FAILED checkpoint sha256"; exit 1; }
[ "$(sha256sum < $MJ | cut -c1-64)" = $MJSHA ] || { n "STUREC_FAILED mapper sha256"; exit 1; }
( cd $R && md5sum rec_student.py rec_hooks.py fpc_lib.py ) > $D/rec_tools.md5
sed -i 's/\r$//' $D/extract_stu.py
n "STUREC_START pid $$ tools $(cut -c1-8 $D/rec_tools.md5 | tr '\n' ' ')"
exec 9> $LOCK
flock -w 21600 9 || { n "STUREC_FAILED GPU lock busy 6 h"; exit 1; }
used() { timeout 60 nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | head -1 | tr -d ' '; }
for i in $(seq 180); do u=$(used); [ -n "$u" ] && [ "$u" -lt 8000 ] && break; sleep 10; done
u=$(used); { [ -n "$u" ] && [ "$u" -lt 8000 ]; } || { n "STUREC_FAILED GPU memory used ${u:-?} MiB"; exit 1; }
n "STUREC_LOCKED gpu_used_MiB $u"
cd $EV
SA="agent.algorithm.optimizer=adam agent.algorithm.use_mixed_precision=false"
FLAT="env.scene.terrain.terrain_generator.sub_terrains.rough.max_slope_deg=0.0 env.scene.terrain.terrain_generator.sub_terrains.rough.max_roughness_m=0.0"
setsid timeout -k 60 3600 go2/scripts/run.sh py go2/_runs/rec430/rec_student.py --headless --task Ame2-Go2-Gaze-Student-N9P12-Eval5 --num_envs 600 --episodes 1 \
  --checkpoint $CK --seed 42 --out $D/unused_tu.pt --student_map tu --mapper_jit $MJ --teacher_jit $TJ \
  --rec_out $D/rec --rec_mode on --rec_episodes 1 --rec_levels 0,4 --rec_levels_stones 0,2 $SA $FLAT > $D/rec.log 2>&1 9>&- < /dev/null &
ch=$!; wait $ch; rc=$?
for i in $(seq 24); do pgrep -g $ch > /dev/null || break; sleep 5; done
pgrep -g $ch > /dev/null && { kill -TERM -- -$ch; sleep 15; kill -KILL -- -$ch; }
flock -u 9; exec 9>&-
n "UNLOCKED rc $rc $(grep -E 'REC_DONE' $D/rec.log | tail -1 | cut -c1-200)"
[ $rc = 0 ] && grep -q 'REC_DONE' $D/rec.log || { n "STUREC_FAILED recorder $(grep -E 'Error|error' $D/rec.log | tail -2 | tr '\n' ' ' | cut -c1-250)"; exit 1; }
CUDA_VISIBLE_DEVICES= nice -n 10 timeout 1800 $PY $D/extract_stu.py $D/rec $D/stu_rec_extract.npz > $D/extract.log 2>&1
grep -q '^EXTRACT_DONE' $D/extract.log && n "EXTRACT_OK $(grep '^EXTRACT_INFO' $D/extract.log | cut -c1-300)" || { n "STUREC_FAILED extract $(tail -2 $D/extract.log | tr '\n' ' ' | cut -c1-250)"; exit 1; }
n "STUREC_DONE"
