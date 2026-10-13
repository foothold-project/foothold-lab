#!/usr/bin/env bash
# 10/13 GPU 0: CMD-R 쌍 반복 (학습 시드 1043) · v2 (ASTRA 17 §4 · §6 반영 · v1 night_20261013_cmdr1043.sh 는 실행하지 않고 보존).
#   v1 과 다른 점:
#     - 재사용은 result.json 존재가 아니라 validate_branch.py --reuse_check (stamp 가 지금 파일 해시와 같고 계약 검증 통과) 일 때만.
#     - 이전 시도의 출력 폴더 · 로그 · guard · slot 기록이 있으면 지우지 않고 ../out/branch/_attempts/ 로 옮긴다.
#     - Isaac 실행은 ../isaac_slot.py (변환 구간 OS 잠금 · USD 폴더 하나 · 다른 로그와 겹침 없음) → ../gpu_guard.py 순서.
#     - 끝난 뒤 validate_branch.py (guard · slot · Traceback · [BRANCH] done · args · 부모 해시 · 마지막 iter · 필수 체크포인트)
#       가 통과해야 stamp 를 쓰고 다음 갈래로 간다. 통과하지 못하면 다음 갈래를 띄우지 않는다.
#   범위: 학습만 (갈래당 약 6 시간은 1042 실측 · 동시 렌더 · 평가가 있으면 늘 수 있음). 목표 세 칸 · 등록 회귀 칸 평가는 따로.
#   첫 인자: 팀장 결정 문구. 기술적 스위치일 뿐 승인 진위를 검증하지 않는다 (ASTRA 17 §4).
set -u
if [ -z "${1:-}" ]; then echo "STOP: 팀장 결정 문구가 없다 (첫 인자)"; exit 2; fi
cd "$(dirname "$0")"
PY=C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe
E1=C:/isaac/ext/go2_rl_robotlab/logs/rsl_rl/go2_moe_cts/2026-10-10_12-47-48_e1_seed42_n8192
BRO=../out/branch
export CUDA_DEVICE_ORDER=PCI_BUS_ID CUDA_VISIBLE_DEVICES=0 OMNI_KIT_ACCEPT_EULA=YES PYTHONUNBUFFERED=1
export BRANCH_CONTRACT_CONFIRMED="$1"
ATT="g0-$$-$(date +%m%d%H%M%S)"
mkdir -p $BRO $BRO/_attempts ../slot
for arm in off on; do
  tag=cmdr_s1043_${arm}_u4000
  VAL=("$PY" validate_branch.py --tag "$tag" --parent "$E1/model_20000.pt" --seed 1043 --num_envs 8192 --updates 4000 --cmdr "$arm")
  if "${VAL[@]}" --reuse_check; then echo "$tag REUSE"; continue; fi
  st=$(date +%Y%m%d-%H%M%S)
  for f in "$tag" "$tag.log" "$tag.guard.json" "$tag.slot.json"; do
    if [ -e "$BRO/$f" ]; then mv "$BRO/$f" "$BRO/_attempts/$f.$st"; echo "moved aside $f"; fi
  done
  t0=$(date +%s)
  echo "$tag START $(date '+%F %T') attempt $ATT"
  "$PY" ../isaac_slot.py --watch_log "$BRO/$tag.log" --record "$BRO/$tag.slot.json" \
      --lock ../slot/isaac_convert.lock --registry ../slot/isaac_usd_registry.json --scan_dirs "$BRO,../out_uncr" -- \
    "$PY" ../gpu_guard.py --gpu 0 --min_free_mib 256 --log "$BRO/$tag.log" --summary "$BRO/$tag.guard.json" -- \
    "$PY" branch_run.py --headless --tag "$tag" --parent "$E1/model_20000.pt" --seed 1043 --num_envs 8192 --updates 4000 --cmdr "$arm"
  rc=$?
  echo "$tag EXIT $rc $(( $(date +%s) - t0 ))s $(date '+%F %T')"
  if "${VAL[@]}" --stamp --attempt "$ATT"; then echo "$tag VALID"; else echo "STOP: $tag 검증 실패 (exit $rc) · 다음 갈래를 띄우지 않는다"; exit 1; fi
done
echo "PAIR 1043 DONE $(date '+%F %T')"
