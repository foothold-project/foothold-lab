> 분류: A/평가 · 실행 상태 점검
> 작성: analyst · 2026-10-31 07:50
> 근거: 실제 checkpoint SHA · manifest · 평가 자식 PID · Kit PhysX 로그 · GPU UUID · NPZ
> 요지: m500 그림자 평가의 물리·환경 장치가 GPU1임을 확인, 전체 결과는 진행 중
> 상태: 기동 장치 확인 완료 · 평가 완료/점수는 미확인 · 실행 원본 보존

# EX-40 m500 그림자 평가 기동 확인

R1·R10·R20에 따라 관찰기 보고를 직접 원자료로 대조했다. M02에 따라 학습·감독기·실행 사본·primary 원장에는 쓰지 않았다.

| 확인 | 실측과 원자료 |
|---|---|
| 확인 시각 | 2026-10-31T07:50:59.9699662+09:00 |
| 저장본 | model_500.pt, SHA 6d0bfdde1175032bd3b51c1824f08bc1d668a2f4be9dc88e2c4388c9059706da |
| manifest | completed_updates 501, total_env_steps 36937728 |
| 평가 영수증 | C:/Users/AI-WS01/s2_lab/ex40_main_20261031_041313/score-watch/model_500_6d0bfdde1175/eval_receipt.json, stage B0, arm B, state running, device cuda:1, 저장본 SHA 일치 |
| 실행 사슬 | 감독141272 → score-watch74964 → eval_once85012 → 셸88612/94412/117500 → 실제 평가 Python122212 |
| 환경 | map64/run.log:1 AppLauncher cuda:1, :45 Environment device cuda:1 |
| 물리 | Kit 로그:2399 Using CUDA device ordinal 1, :2463 Physics using context, device 1 |
| GPU1 대응 | PID122212가 GPU-315d098f-5fe0-26a0-0d2e-26e2d4c1ae4f에 존재. CUDA_DEVICE_ORDER=PCI_BUS_ID는 고정 run_kit.sh:10 |
| 실제 결과 생성 | map64 NPZ 8개가 관찰됨. 전체평가 완료나 성능 통과를 뜻하지 않음 |
| 학습 계속 | 2026-10-31T07:47:01 iter500, running. 학습PID26240 |
| 고정 사본 | 2df419b0a4278981f6bd26e5eaedecbf7e8458db, tracked 변경 0개 |

**확인 범위:** 물리와 평가 환경이 GPU1을 사용하는 것은 확인됐다. Kit Active 표는 두 장을 모두 등록하고 PID122212도 두 GPU의 컨텍스트 목록에 나타난다. 따라서 GPU0에 어떠한 작업도 없다고 주장하지 않는다. 이 관찰만으로 GPU0에서 평가 물리를 돌린다고 해석하지도 않는다. 별도 장치 설정 변경은 하지 않았다.

전체 평가의 종료값·점수·완료 영수증은 아직 미확인이다. W57은 별도 retry 명령 준비까지만이며 추가 구현·재검토·기동 없음. 단계 끝 W57은 「보류 · retry 원장 참조」 그대로다.

원자료: [READBACK-M500-STARTED-0750.json](READBACK-M500-STARTED-0750.json). Kit 로그: C:/Users/AI-WS01/anaconda3/envs/isaac311/Lib/site-packages/isaacsim/kit/logs/Kit/Isaac-Sim/5.1/kit_20261031_074727.log. 관찰기 events의 accepted=false와 달리 메시지 두 개는 실제 Run에 도착했다. msg_d78488076d1a와 msg_3801d6a51886를 원자료 대조 뒤 ACK했다. 재발송이나 관찰기 수정은 하지 않았다.