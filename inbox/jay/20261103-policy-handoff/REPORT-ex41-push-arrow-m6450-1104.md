# EX-41 m6450 밀기 화살표 수정과 세 지도 모드 재촬영
> 분류: A/평가
> 작성: 오흥재 · scripter 반영 · 2026-11-04 01:17
> 근거: 팀장 11/04 00시 화살표 지시 · EX-41 model_450.pt · 새 촬영 영수증
> 요지: 밀기 순간에만 몸통에서 실제 힘 방향으로 짧은 화살표를 보이고 세 지도 모드를 다시 촬영했다.
> 상태: 확인됨, 팀장 공개 전 lead 장면 판독 대기

## 변경과 확인

- 코드 고정 HEAD `3279bcf4` (`4013d289`, `6bc728f3`, `3279bcf4`). 재촬영은 이 HEAD의 별도 고정 사본 `D:\mai-wt\foothold-lab\a-push-arrow-run-3279bcf4`에서 했다.
- 3D 화살표는 실제 밀기 사건 t=2.0 s와 4.0 s의 몸통 중심에서 시작해 world XY 밀기 방향으로 향한다. 길이는 밀기 1 m/s당 0.25 m, 최대 0.5 m다. 범례 화살표도 같은 카메라 투영 방향이다. 범례로 잇는 선은 없다.
- 두 화살표는 사건 후 0.4 s에만 보인다. PUSH 정보 상자는 기존 규칙대로 회복 창 동안 유지하며 그 뒤 범례로 돌아간다.
- isaac311 CPU 관련 시험 18 PASS. 큐 37번의 GPU1 촬영 종료 코드 0. 세 모드 모두 각 150프레임 원본·합성 전 프레임 검사 PASS, 영상 SHA와 영수증 일치. 자동 화살표 검사: 최대 각도 차 0.635°, 장면 폭 대비 최대 길이 13.494%, 몸통 투영 상자와 실제 분할 마스크 안 시작, 밀기 적용 시각 밖 화살표 프레임 0. 사건당 10프레임, 두 사건 총 20프레임.
- 동일 model_450.pt SHA `c5314db17791c8e09539efb8977af7d1d5b66e5cf73c42246f01d418516f85a0`, 지형 pyramid_stairs L0, env0, 시드 42, 밀기 시드 42. 세 모드의 실제 밀기 사건 서명이 일치한다. 원본과 새 촬영의 카메라 거리만 달라졌으므로 장면 픽셀을 정책 성능 비교에 쓰지 않는다.

| 지도 모드 | 새 영상 SHA256 | 전 프레임 |
|---|---|---|
| 정답 eval_gt | `7b630f78bb9519870dbff7cd0f9707c55741a8648d7eb4a77b1f870535a0c044` | 150 PASS |
| 복원 eval_pred | `76527ed7c5a7921c288742f687e90fd650d92f8baee176f4accb0c6d9701f981` | 150 PASS |
| 끔 probe_prop_only | `470bc026b854c7cd730a72cc77e0a3cb3186675e29a0556ae44f2fee96688143` | 150 PASS |

원자료와 자동 검증 수치: `D:\mai-tmp\scripter\a_push_m6450_arrowfix_compare\evidence.json`. 영상·원본·합성 영수증: `D:\mai-tmp\scripter\a_push_m6450_arrowfix\`.

## lead 장면 판독용 전후 그림

| 밀기 | 정답 지도 | 복원 지도 | 지도 끔 |
|---|---|---|---|
| 1.5 m/s, 2.0 s | `D:\mai-tmp\scripter\a_push_m6450_arrowfix_compare\eval_gt_push1_compare_scene.png` | `D:\mai-tmp\scripter\a_push_m6450_arrowfix_compare\eval_pred_push1_compare_scene.png` | `D:\mai-tmp\scripter\a_push_m6450_arrowfix_compare\probe_prop_only_push1_compare_scene.png` |
| 2.0 m/s, 4.0 s | `D:\mai-tmp\scripter\a_push_m6450_arrowfix_compare\eval_gt_push2_compare_scene.png` | `D:\mai-tmp\scripter\a_push_m6450_arrowfix_compare\eval_pred_push2_compare_scene.png` | `D:\mai-tmp\scripter\a_push_m6450_arrowfix_compare\probe_prop_only_push2_compare_scene.png` |

각 그림 왼쪽이 종전, 오른쪽이 새 촬영이다. 정답 지도 두 장을 직접 열어 몸통 시작과 짧은 길이, 범례 방향 일치를 확인했다. lead가 장면을 직접 본 뒤에만 팀장에게 제시한다.
