#!/bin/bash
VOL="${VOL:-/data/$USER}"   # 네트워크 볼륨. 다른 자리면 VOL=... 로 덮어쓴다
# 지형 전수검사 18개 - 브리지 4 + FLAT 7 + ROUGH 7.
# 🔴 종료코드만 믿지 않는다. 2026-09-08 에 AssertionError 가 났는데 exit=0 이 나왔다.
#    terrain_audit.py 를 os._exit 로 고쳤지만, 여기서도 로그의 "[AUDIT] OK" 를 같이 본다.
cd $VOL/isaaclab
O=$VOL/experiments/20260907_gap-threshold
mkdir -p $O
FAIL=0
for C in BRIDGE_HS100_GAP10 BRIDGE_HS025_GAP10 BRIDGE_HS100_GAP00 BRIDGE_HS025_GAP00 \
         FLAT_GAP_SWEEP:flat000 FLAT_GAP_SWEEP:flat025 FLAT_GAP_SWEEP:flat050 \
         FLAT_GAP_SWEEP:flat075 FLAT_GAP_SWEEP:flat100 FLAT_GAP_SWEEP:flat150 \
         FLAT_GAP_SWEEP:flat200 \
         ROUGH_GAP_SWEEP:rough000 ROUGH_GAP_SWEEP:rough025 ROUGH_GAP_SWEEP:rough050 \
         ROUGH_GAP_SWEEP:rough075 ROUGH_GAP_SWEEP:rough100 ROUGH_GAP_SWEEP:rough150 \
         ROUGH_GAP_SWEEP:rough200; do
  N=${C/:/__}
  echo "=== AUDIT $C  $(date -u +%H:%M:%S)"
  ./isaaclab.sh -p scripts/reinforcement_learning/rsl_rl/terrain_audit.py \
    --cfg "$C" --gate_x 0.8 --out $O/audit_${N}.json > $O/audit_${N}.log 2>&1
  E=$?
  if grep -q "\[AUDIT\] OK" $O/audit_${N}.log; then
    echo "=== PASS $C exit=$E"
  else
    echo "=== FAIL $C exit=$E"
    grep -E "\[AUDIT\] 실패|AssertionError|Error" $O/audit_${N}.log | head -3
    FAIL=1
  fi
done
echo "AUDITS DONE fail=$FAIL"
