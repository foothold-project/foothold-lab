> 분류: A/평가
> 작성: 오흥재 (scripter 반영) · 2026-10-29
> 근거: EX-39 try05 B `ex39_kit_probe.json` · `mixed_command.py` 첫 명령 기록 · CPU 시험
> 요지: 첫 heading wz를 0과 대조하지 않고 같은 물리 걸음의 목표 방향식과 대조한다.
> 상태: CPU 검증 완료 · Kit 재실행 미확인

# EX-39 첫 heading wz 검사 수정

## 반례

try05 B는 학습 두 회와 `model_3003.pt` 저장을 마친 뒤 `first_wz < 1e-3` 단언에서 실패했다. 출처는 `C:/Users/AI-WS01/s2_lab/basic_gait_runs/ex39b_kit_smoke/try05/smoke/EX-39B-basic-heading_20261029_234305_53924/ex39_kit_probe.json`과 해당 receipt의 `run.log`다. 첫 재추출에서 `psi_star`와 yaw가 같아도 물리 한 걸음 뒤 yaw가 바뀌면 첫 명령은 0이 아닐 수 있다. 원래 단언은 실제 명령 규칙보다 강했다.

## 고침

- `MixedVelocityCommand._update_command`가 첫 전진 heading env의 실제 명령 wz와 그 걸음의 `heading_wz(psi_star, yaw, stiffness, wz_max)` 재계산값을 함께 잡는다. env 수, 관측값 절대 최대, 기대값 절대 최대, 최대 차이, heading 오차 절대 최대를 기록한다.
- probe는 최대 차이 `≤1e-5`와 관측 `|wz|≤0.1`을 확인한다. 첫 8걸음의 `four_foot_mean` 배열과 첫 heading 세부값을 **단언 전**에 영수증에 넣으므로 실패해도 남는다. 기존 첫 재추출 슬롯 및 heading 비율 검사는 유지한다.
- 실제 코드 `f422178c`의 CPU 시험은 yaw가 0.08, -0.12 rad로 바뀌었을 때 목표 방향식 결과가 -0.04, +0.06 rad/s임을 확인한다. 차이 `2e-5`와 관측 `0.11`은 각각 거절하며 실패 영수증에 값과 eight-step 보상이 남는지 확인한다.

## 검증과 남은 일

`isaac311-moects`로 EX-39 CPU 두 시험 파일 **29 passed**. `ruff check --select F` 0건, `py_compile` 통과. GPU와 Kit는 실행하지 않았다. try05의 실제 `first_wz` 값은 실패 전 코드가 영수증에 쓰지 않아 미확인이다. lead의 B Kit 재실행에서 새 세부값과 결과를 확인해야 한다. 변경 3개 파일의 SHA-256은 `SHA256SUMS-scripter-EX39-heading.txt`에 있다.
