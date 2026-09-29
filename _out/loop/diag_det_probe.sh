#!/usr/bin/env bash
# 「처음부터 · lr 1e-3」 경로에서도 GPU 가 결과를 안 바꾸는지 2 분 안에 가린다.
#
# 분류: 진단
# 작성: 오흥재 · 2026-09-28
# 근거: 팀장 질문 「회차 2 는 왜 하는거야?」
#       `night.sh:13-18` 이 적은 이유는 「장치 효과와 보상 효과를 가른다」다.
#       그런데 `v2b-r`(cuda:0) 과 `v2b-p11`(cuda:1) 은 device 한 칸만 다른 짝인데
#       체크포인트 121 개 «전수» 가 정책 가중치·optimizer 텐서까지 완전히 같았다.
#       그 짝은 resume · lr 1e-4 였다. 처음부터 · lr 1e-3 에서도 같은지는 안 쟀다.
# 방법: fs2 와 «완전히 같은 설정» 을 장치만 cuda:0 으로 바꿔 26 회만 돈다.
#       fs2 는 cuda:1 에서 돌았다. model_25.pt 를 fs2 의 model_25.pt 와 텐서로 댄다.
#       같으면 회차 2 (fs1b/fs2b 장치 교차) 는 이미 있는 파일을 복제하는 일이다.
set -u
LAB="C:/Users/AI-WS01/Desktop/jay/인공지능사관학교/foothold-lab"
cd "$LAB" || exit 1
NAME=20260928_probe-det-g0
powershell -NoProfile -Command \
  "Set-Location C:\isaac\IsaacLab; .\run_gap_train.ps1 -Task Isaac-Velocity-V2b-Unitree-Go2-v0 \
   -Iterations 26 -NumEnvs 4096 -Seed 42 -Device cuda:0 -RunName $NAME -FromScratch \
   -Extra @('agent.device=cuda:0','agent.algorithm.learning_rate=1.0e-3','env.rewards.feet_air_time.weight=0.1')" \
  2>&1 | tail -20
echo "--- 학습 끝. 대조한다"
C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe - <<'PY'
import torch, glob, os
L="C:/isaac/IsaacLab/logs/rsl_rl/unitree_go2_gap_nvidia"
d=sorted(glob.glob(os.path.join(L,"*20260928_probe-det-g0*")))
if not d:
    print("  ** 탐사 실행 폴더가 없다 **"); raise SystemExit(1)
P=d[-1]
B=os.path.join(L,"2026-09-28_01-04-43_20260928_fs2-scratch-f01")
print("  탐사 (cuda:0) :", os.path.basename(P))
print("  fs2  (cuda:1) :", os.path.basename(B))
n=0
for ck in (0,25):
    fa,fb=os.path.join(P,"model_%d.pt"%ck), os.path.join(B,"model_%d.pt"%ck)
    if not os.path.isfile(fa): print("  model_%-4d 탐사 쪽 없음"%ck); continue
    if not os.path.isfile(fb): print("  model_%-4d fs2 쪽 없음"%ck); continue
    a=torch.load(fa,map_location="cpu",weights_only=False)["model_state_dict"]
    b=torch.load(fb,map_location="cpu",weights_only=False)["model_state_dict"]
    if set(a)!=set(b): print("  model_%-4d 키가 다르다"%ck); continue
    mx=max((a[k].float()-b[k].float()).abs().max().item() for k in a)
    print("  model_%-4d 최대차 %.6e · %s"%(ck,mx,"완전 동일" if mx==0.0 else "** 다르다 **"))
    n+=1
PY
