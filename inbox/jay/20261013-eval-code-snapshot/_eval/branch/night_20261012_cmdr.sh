#!/usr/bin/env bash
# 10/12 밤 GPU 0: CMD-R 쌍 (VERIFY-astra-6 순서: 명령 분포 대조를 G1 앞에). 실행 중 이 파일을 고치지 않는다.
#   근거: 팀장 10/12 23:00 lead 채팅 「오늘부터 내가 자는 시간에도 GPU 가 돌아야 한다 · ASTRA 검증 받고 진행 · Top-down」
#   부모 E1 model_20000 (읽기만) · 시드 1042 · env 8192 · 군마다 update 4000 (저장 500 간격 → 22000 · 24000 지점)
#   군 순서: off (대조) → on (CMD-R adapter). 같은 GPU 0 에서 차례로.
#   감시: gpu_guard 200 ms · GPU 0 여유 256 MiB 아래면 중단 (공유 메모리로 새면 iter 가 20 배 느려진다 · 10/10 E0)
set -u
cd "$(dirname "$0")"
PY=C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe
E1=C:/isaac/ext/go2_rl_robotlab/logs/rsl_rl/go2_moe_cts/2026-10-10_12-47-48_e1_seed42_n8192
export CUDA_DEVICE_ORDER=PCI_BUS_ID CUDA_VISIBLE_DEVICES=0 OMNI_KIT_ACCEPT_EULA=YES PYTHONUNBUFFERED=1
export BRANCH_CONTRACT_CONFIRMED="team-lead chat 2026-10-12 23:00 overnight top-down GPU with ASTRA verification; CMD-R pair first per VERIFY-astra-6"
mkdir -p ../out/branch
for arm in off on; do
  tag=cmdr_s1042_${arm}_u4000
  if [ -f "../out/branch/$tag/result.json" ]; then echo "$tag SKIP (result.json 있음)"; continue; fi
  t0=$(date +%s)
  echo "$tag START $(date '+%F %T')"
  "$PY" ../gpu_guard.py --gpu 0 --min_free_mib 256 --log "../out/branch/$tag.log" --summary "../out/branch/$tag.guard.json" -- \
    "$PY" branch_run.py --headless --tag "$tag" --parent "$E1/model_20000.pt" --seed 1042 --num_envs 8192 --updates 4000 --cmdr "$arm"
  rc=$?
  echo "$tag EXIT $rc $(( $(date +%s) - t0 ))s $(date '+%F %T')"
  if [ "$rc" != "0" ]; then echo "STOP: $tag 실패 · 다음 군을 띄우지 않는다"; exit "$rc"; fi
done
echo "NIGHT DONE $(date '+%F %T')"
