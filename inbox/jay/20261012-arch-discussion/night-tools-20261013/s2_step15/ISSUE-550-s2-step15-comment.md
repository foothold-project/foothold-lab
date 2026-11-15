# #550 댓글 초안: S2-2 발 디딤 보상 CPU 후보
> 분류: A/정책학습
> 작성: sol · 2026-10-16
> 근거: TASK-codex-worker-s2-2-foot-reward.md · VERIFY-astra-17ag.md 1~2절 · step15 CPU 시험
> 요지: `feet_center_any9_v1` CPU 구현과 Kit 접속 확인 계약을 lead 재실행 대상으로 제출한다.
> 상태: 초안 · 미게시

`codexE/s2_step15`에 양의 발 비용 함수, world XY 36점 지형 광선 질의, episode/frame 검증, `reward_variant` 선택 연결을 만들었습니다. 기본 `none`의 환경 dict가 step14와 바이트 단위로 같음을 CPU 시험했습니다. 켠 경우에만 RewardManager 항 `feet_center_any9_v1`이 가중치 -0.01로 추가됩니다. 설치된 Go2 URDF 네 발의 충돌구 반지름 0.022 m와 오프셋 `(-0.002,0,0)` 및 부모 RewardsCfg/E1 env.yaml의 15개 항을 정적으로 대조했습니다.

CPU 정상 16 PASS, 변이 10/10 CAUGHT이며 지정 첫 FAIL을 각 변이 로그에 남겼습니다. step14 구성 대조 파일은 번들 내부 고정 fixture로 옮기고 SHA256을 시험에 박았습니다. B 전체 깨끗한 복사본 회귀는 정상 39/39 파일과 PASS 라벨 356, 변이 12/12 파일과 CAUGHT 84로 통과했으며 `first_FAIL=want`입니다. `S2-FOOT-KIT-CHECK.md`는 N<=8, 최대 300 control step, 학습과 optimizer 0인 단회 접속 계약입니다. 실제 Kit 발 광선 응답, 실제 USD collision 발 형상, RewardManager 실제 목록은 미확인입니다. GPU와 Isaac은 실행하지 않았습니다. 승인 JSON은 만들지 않았습니다.

보고: `codexE/REPORT-s2-step15.md`. 해시: `codexE/S2-STEP15-SHA256SUMS.txt`. lead가 독립 재실행하고 실제 Kit 진입은 별도 직접 동의와 감독 범위가 필요합니다.
