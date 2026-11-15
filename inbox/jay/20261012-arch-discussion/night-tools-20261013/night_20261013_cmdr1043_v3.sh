#!/usr/bin/env bash
# 10/13 GPU 0: CMD-R 쌍 반복 (학습 시드 1043) · v3 (ASTRA 17b §2.1 · §2.2 · §2.3 반영 · v1 · v2 는 실행하지 않고 보존).
#   v2 결함 (17b 재현): mv 실패를 확인하지 않음 · 자식 종료 코드를 보지 않고 검증기로 감 · attempt 를 사후 문자열로만 붙임
#     → 이전 시도의 결과를 이번 시도의 성공으로 적고 「PAIR 1043 DONE」 · exit 0 으로 끝날 수 있었다.
#   v3:
#     - cd · mkdir · 이전 시도 옮기기 하나하나 확인 (옮긴 뒤 원래 자리에 남아 있으면 멈춤)
#     - 실행마다 attempt 이름과 시작 epoch 를 정하고, isaac_slot (--attempt · 실행별 --usd_root · --stop_file · --deadline) 과
#       validate_branch (--attempt · --since) 에 같은 값을 넘긴다
#     - Isaac 스크립트는 usd_isolate_run.py 로 띄워 USD 변환 폴더를 이 시도 전용으로 둔다
#     - 자식 (slot) 종료 코드가 0 이 아니면 검증기로 가지 않고 멈춘다
#     - 재사용은 validate_branch --reuse_check (원래 attempt 를 그대로 보고) 만
#   출력: ../out_branch (기존 ../out/branch 의 1042 결과는 건드리지 않음)
#   멈춤: ../out_branch/STOP_1043 파일이 생기면 다음 갈래를 띄우지 않는다 (slot 대기 중에도 98)
#   범위: 학습만. 목표 세 칸 · 등록 회귀 칸 평가는 따로 (10/14).
#   첫 인자: 팀장 결정 문구 (기술적 스위치 · 승인 진위를 검증하지 않음).
set -u
if [ -z "${1:-}" ]; then echo "STOP: 팀장 결정 문구가 없다 (첫 인자)"; exit 2; fi
cd "$(dirname "$0")" || { echo "STOP: cd 실패"; exit 3; }
PY=C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe
E1=C:/isaac/ext/go2_rl_robotlab/logs/rsl_rl/go2_moe_cts/2026-10-10_12-47-48_e1_seed42_n8192
BRO=../out_branch
export BRANCH_OUT="$BRO"   # branch_run · validate_branch 가 같은 루트를 쓴다 (기존 _eval/out 에 쓰지 않음 · ASTRA 17 §4)
STOPF="$BRO/STOP_1043"
DEADLINE="${DEADLINE_EPOCH:-0}"
export CUDA_DEVICE_ORDER=PCI_BUS_ID CUDA_VISIBLE_DEVICES=0 OMNI_KIT_ACCEPT_EULA=YES PYTHONUNBUFFERED=1
export BRANCH_CONTRACT_CONFIRMED="$1"
mkdir -p "$BRO/_attempts" ../slot "$BRO/_usd" || { echo "STOP: mkdir 실패"; exit 3; }
for arm in off on; do
  tag=cmdr_s1043_${arm}_u4000
  if [ -e "$STOPF" ]; then echo "STOP: $STOPF 있음 · $tag 를 띄우지 않는다"; exit 7; fi
  if "$PY" validate_branch.py --tag "$tag" --parent "$E1/model_20000.pt" --seed 1043 --num_envs 8192 --updates 4000 --cmdr "$arm" --reuse_check; then
    echo "$tag REUSE"; continue
  fi
  st=$(date +%Y%m%d-%H%M%S)
  for f in "$tag" "$tag.log" "$tag.guard.json" "$tag.slot.json"; do
    if [ -e "$BRO/$f" ]; then
      mv "$BRO/$f" "$BRO/_attempts/$f.$st" || { echo "STOP: $f 를 옮기지 못함"; exit 4; }
      if [ -e "$BRO/$f" ]; then echo "STOP: $f 가 아직 원래 자리에 있음"; exit 4; fi
      echo "moved aside $f -> _attempts/$f.$st"
    fi
  done
  ATT="g0-$tag-$(date +%m%d%H%M%S)-$$"
  SINCE=$(date +%s)
  echo "$tag START $(date '+%F %T') attempt $ATT"
  "$PY" ../isaac_slot.py --watch_log "$BRO/$tag.log" --record "$BRO/$tag.slot.json" --attempt "$ATT" --usd_root "$BRO/_usd/$ATT" \
      --lock ../slot/isaac_convert.lock --registry ../slot/isaac_usd_registry.json --scan_dirs "$BRO,../out_uncr" \
      --stop_file "$STOPF" --deadline "$DEADLINE" -- \
    "$PY" ../gpu_guard.py --gpu 0 --min_free_mib 256 --log "$BRO/$tag.log" --summary "$BRO/$tag.guard.json" -- \
    "$PY" ../usd_isolate_run.py branch_run.py --headless --tag "$tag" --parent "$E1/model_20000.pt" --seed 1043 --num_envs 8192 --updates 4000 --cmdr "$arm"
  rc=$?
  echo "$tag EXIT $rc $(( $(date +%s) - SINCE ))s $(date '+%F %T')"
  if [ "$rc" != "0" ]; then echo "STOP: $tag 실행 실패 (slot rc $rc) · 검증하지 않고 다음 갈래를 띄우지 않는다"; exit 5; fi
  if ! "$PY" validate_branch.py --tag "$tag" --parent "$E1/model_20000.pt" --seed 1043 --num_envs 8192 --updates 4000 --cmdr "$arm" \
        --attempt "$ATT" --since "$SINCE" --stamp; then
    echo "STOP: $tag 검증 실패 · 다음 갈래를 띄우지 않는다"; exit 6
  fi
  echo "$tag VALID attempt $ATT"
done
echo "PAIR 1043 DONE $(date '+%F %T')"
