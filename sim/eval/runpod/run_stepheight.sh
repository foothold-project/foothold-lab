#!/bin/bash
VOL="${VOL:-/data/$USER}"   # 네트워크 볼륨. 다른 자리면 VOL=... 로 덮어쓴다
# ③ 높이 축 - 틈을 «고정» 하고 높이 턱만 0/3/6/9/12 cm 로 바꾼다. 난수 없음(교대 패턴).
# 🔴 조건부다. FLAT 곡선에서 통과율이 아직 «충분히 높은 가장 큰 틈» 을 인자로 준다.
#    바닥(0%)이나 천장(100%)에서 재면 높이를 바꿔도 움직일 여지가 없다.
# 사용법:  bash run_stepheight.sh 0.05      <- 고정할 틈 [m]
set -e
GAP=${1:?고정할 틈 [m] 을 인자로 줘야 한다 (예: 0.05)}
GTAG=$(python3 -c "print('%03d' % round(float('$GAP')*1000))")
O=$VOL/experiments/20260907_gap-threshold
T=$VOL/isaaclab/scripts/reinforcement_learning/rsl_rl/terrain_cfg.py

# ── (1) terrain_cfg.py 에 STEP_SWEEP 딕셔너리를 «그 틈으로» 다시 쓴다 ──────────
#    --terrain_cfg 는 이름만 받으므로 이름이 파일 안에 있어야 한다.
python3 - "$GAP" "$T" <<'PY'
import io, re, sys
gap = float(sys.argv[1])
P = sys.argv[2]
s = io.open(P, encoding="utf-8").read()
block = (f"\n# [2026-09-08 자동생성] ③ 높이 축. 틈 {gap} m 고정, 높이 턱만 바꾼다.\n"
         f"#   run_stepheight.sh 가 이 블록을 매번 다시 쓴다. 손으로 고치지 않는다.\n"
         f"STEP_SWEEP_GAP_M = {gap!r}\n"
         f"STEP_SWEEP = {{'h%03d' % round(h*1000): make_step_height_cfg({gap!r}, h)\n"
         f"              for h in (0.0, 0.03, 0.06, 0.09, 0.12)}}\n")
s = re.sub(r"\n# \[2026-09-08 자동생성\].*?\n              for h in \(0\.0, 0\.03, 0\.06, 0\.09, 0\.12\)\}\n",
           "\n", s, flags=re.S)
io.open(P, "w", encoding="utf-8").write(s.rstrip("\n") + "\n" + block)
print("STEP_SWEEP 를 틈 %.3f m 로 다시 썼다" % gap)
PY

# ── (2) 관문: 5개 지형을 먼저 검사한다. 하나라도 실패하면 평가를 시작하지 않는다 ──
cd $VOL/isaaclab
FAIL=0
for H in 000 030 060 090 120; do
  ./isaaclab.sh -p scripts/reinforcement_learning/rsl_rl/terrain_audit.py \
    --cfg "STEP_SWEEP:h${H}" --gate_x 0.8 \
    --out $O/audit_STEP${GTAG}_h${H}.json > $O/audit_STEP${GTAG}_h${H}.log 2>&1 || true
  if grep -q "\[AUDIT\] OK" $O/audit_STEP${GTAG}_h${H}.log; then
    echo "=== PASS STEP h=$H"
  else
    echo "=== FAIL STEP h=$H"; grep -E "\[AUDIT\] 실패|AssertionError" $O/audit_STEP${GTAG}_h${H}.log|head -3; FAIL=1
  fi
done
[ $FAIL -ne 0 ] && { echo "🔴 지형검사 실패 - 평가 시작 안 함"; exit 1; }

# ── (3) 평가 ──────────────────────────────────────────────────────────────
CK=$VOL/checkpoints/pretrained/go2-rough-nvidia-1500.pt
for H in 000 030 060 090 120; do
  N=step${GTAG}_h${H}
  D=$O/${N}_s42
  [ -f "$D/manifest.json" ] && grep -q completed "$D/manifest.json" 2>/dev/null && { echo "SKIP $N"; continue; }
  mkdir -p "$D"
  echo "=== EVAL $N  $(date -u +%H:%M:%S)"
  ./isaaclab.sh -p scripts/reinforcement_learning/rsl_rl/play_eval.py \
    --task Isaac-Velocity-Rough-Unitree-Go2-Play-v0 --headless --seed 42 \
    --checkpoint $CK --terrain_cfg "STEP_SWEEP:h${H}" \
    --command_vx 1.0 --num_envs 10 --episodes 10 --eval_duration 20.0 \
    --heading --eval_name $N --out_dir "$D" > "$D/stdout.log" 2>&1
  echo "=== DONE $N exit=$?  $(date -u +%H:%M:%S)"
done
echo "STEPHEIGHT DONE $(date -u +%H:%M:%S)"
