#!/bin/bash
VOL="${VOL:-/data/$USER}"   # 네트워크 볼륨. 다른 자리면 VOL=... 로 덮어쓴다
# 20260907_gap-threshold - 브리지 대조군 4 + FLAT 7점 + ROUGH 7점 + 각 점 영상.
# GPU 는 한 번에 하나. 앞 작업이 끝나기를 기다렸다가 시작한다.
# 🔴 대기 조건에 자기 자신이 걸리지 않도록 «파일 이름» 이 아니라 파이썬 스크립트명을 본다.
while pgrep -f "terrain_audit\.py|play_eval\.py" >/dev/null; do sleep 15; done
cd $VOL/isaaclab
O=$VOL/experiments/20260907_gap-threshold
CK=$VOL/checkpoints/pretrained/go2-rough-nvidia-1500.pt

run () {  # run <run_id> <terrain_cfg>
  local D=$O/$1_s42
  [ -f "$D/manifest.json" ] && grep -q completed "$D/manifest.json" 2>/dev/null && { echo "SKIP $1"; return; }
  mkdir -p "$D"
  echo "=== EVAL $1  $(date -u +%H:%M:%S)"
  ./isaaclab.sh -p scripts/reinforcement_learning/rsl_rl/play_eval.py \
    --task Isaac-Velocity-Rough-Unitree-Go2-Play-v0 --headless --seed 42 \
    --checkpoint $CK --terrain_cfg "$2" \
    --command_vx 1.0 --num_envs 10 --episodes 10 --eval_duration 20.0 \
    --heading --eval_name $1 --out_dir "$D" > "$D/stdout.log" 2>&1
  echo "=== DONE $1 exit=$?  $(date -u +%H:%M:%S)"
}

vid () {  # vid <run_id> <terrain_cfg>
  local D=$O/$1_vid_s42
  [ -n "$(ls $D/video/*.mp4 2>/dev/null)" ] && { echo "SKIP vid $1"; return; }
  mkdir -p "$D"
  echo "=== VID $1  $(date -u +%H:%M:%S)"
  ./isaaclab.sh -p scripts/reinforcement_learning/rsl_rl/play_eval.py \
    --task Isaac-Velocity-Rough-Unitree-Go2-Play-v0 --headless --seed 42 \
    --checkpoint $CK --terrain_cfg "$2" \
    --command_vx 1.0 --num_envs 10 --episodes 1 --eval_duration 20.0 \
    --video --video_length 1000 \
    --heading --eval_name ${1}_vid --out_dir "$D" > "$D/stdout.log" 2>&1
  echo "=== DONE vid $1 exit=$?  $(date -u +%H:%M:%S)"
}

# ── ③ 브리지 대조군. 스윕 «전에». 명목상 같은 형상을 두 해상도에서. ──
run bridge_hs100_gap10 BRIDGE_HS100_GAP10
run bridge_hs025_gap10 BRIDGE_HS025_GAP10
run bridge_hs100_gap00 BRIDGE_HS100_GAP00
run bridge_hs025_gap00 BRIDGE_HS025_GAP00
echo "BRIDGE DONE $(date -u +%H:%M:%S)"

# ── ④-1 FLAT 7점 (주 실험: 돌 높이 고정, 변수는 틈 하나) ──
for G in 000 025 050 075 100 150 200; do run flat$G "FLAT_GAP_SWEEP:flat$G"; done
echo "FLAT DONE $(date -u +%H:%M:%S)"

# ── ④-2 ROUGH 7점 (대조: 돌 높이 무작위) ──
for G in 000 025 050 075 100 150 200; do run rough$G "ROUGH_GAP_SWEEP:rough$G"; done
echo "ROUGH DONE $(date -u +%H:%M:%S)"

# ── 각 점 영상 1편 ──
for G in 000 025 050 075 100 150 200; do vid flat$G "FLAT_GAP_SWEEP:flat$G"; done
for G in 000 025 050 075 100 150 200; do vid rough$G "ROUGH_GAP_SWEEP:rough$G"; done
echo "GAP ALL DONE $(date -u +%H:%M:%S)"
