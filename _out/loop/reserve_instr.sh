#!/usr/bin/env bash
# 예약 · (ㄱ) 배치 시험이 끝나면 (나) seed 43 계측판을 건다
#
# 분류: 운영
# 작성: 오흥재 · 2026-09-24
# 근거: checkpoint 에 난수 생성기 상태가 없어 resume 으로는 1578 을 재현 못 한다
#       (model_1550.pt 의 열쇠 넷에 rng 가 없음). 그래서 «처음부터» 돌린다.
# 요지: GPU 1 이 비면 계측을 켠 채 seed 43 을 다시 돌린다. 결정론이라
#       반드시 같은 자리(1578)에서 터지고, 그때 minibatch 를 덤프한다.
#
# 왜 폴링이 아니라 이 모양인가
#   이 스크립트가 «끝날 때» 한 번 알림이 온다. 도는 동안은 조용하다.
#
set -u
P11="C:/isaac/IsaacLab/logs/rsl_rl/unitree_go2_gap_nvidia/2026-09-24_14-59-36_20260924_v2b-p11_seed42_iter3000"

echo "대기 시작 $(date '+%H:%M:%S') · (ㄱ) 배치 시험이 끝나기를 기다린다"

# 끝났다고 볼 조건 둘을 «다» 본다 · 마지막 checkpoint 와 프로세스 소멸
until [ -f "$P11/model_3000.pt" ] \
   && ! powershell -NoProfile -Command \
        "if (Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { \$_.CommandLine -match 'v2b-p11' }) { exit 1 } else { exit 0 }"; do
  sleep 60
done

echo "(ㄱ) 끝남 $(date '+%H:%M:%S') · (나) 계측판을 건다"

powershell -NoProfile -Command "Set-Location C:\isaac\IsaacLab; .\run_gap_train.ps1 \
  -Task Isaac-Velocity-V2b-Unitree-Go2-v0 \
  -Iterations 3001 -NumEnvs 4096 -Seed 43 -Device cuda:1 \
  -RunName 20260924_v2b-s3instr_seed43_iter3000 \
  -Script train_instrumented.py \
  -Detached"

echo "걸었다 $(date '+%H:%M:%S')"
echo "계측 출력: C:/isaac/IsaacLab/_out/instr/20260924_v2b-s3instr_seed43_iter3000/"
echo ""
echo "배치를 «일부러» 원본과 같게 둔다 · sim cuda:1 + PPO cuda:0."
echo "  agent.device 를 «안» 준다. 그래야 v2b-s 와 같은 배치가 되고"
echo "  결정론에 의해 «반드시» 1578 에서 터진다. 터져야 덤프를 받는다."
echo "  앞으로의 학습은 sim/PPO 를 맞추지만, 이 판은 «진단용» 이다."
