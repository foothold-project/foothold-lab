# EX-42 E1 P1 출구 판정 연결

> 분류: 실험
> 작성: 오흥재 · 2026-11-11
> 근거: `CURRICULUM-GATES.md` v0.16 187행 · `ex42-prep.yaml` 평가와 q4 · m250 원자료
> 요지: E1은 고정 부모 유지표와 D44 계단참 칸의 두 창을 분리 판정한다.
> 상태: CPU 확인 · D44 평가 열 생산 연결 대기

## 판정 계약

- 유지표는 #631의 A23 부모 다섯 반복 중앙값과 q4 measured를 그대로 쓴다. 현재와 바로 앞 P1 창의 26개 지도 판정 칸을 각각 검사한다. 지도 끔 13칸은 기록 전용이다.
- D44 칸은 `ex42-prep.yaml`의 `evaluation.paper_cells.stairs_landing.id`와 `evaluation.promotion`에서 칸 이름 · 64 env · 성공 하한 · 생존 하한 · 창 수를 읽는다. 현재와 바로 앞 창이 모두 하한에 닿아야 PASS이다. 판정에 새 수치를 박지 않았다.
- 평가 열 자체가 없으면 D44에는 `HOLD: 평가 열 없음`, 바로 앞 P1 창이 없으면 `HOLD: 직전 창 없음`을 별도로 기록한다. 확인된 유지표 실패는 D44 결측으로 숨기지 않고 FAIL로 남긴다.
- D44 연결 입력은 `ex42_score.json`의 `d44_landing` 객체다. 필드 `case_id, envs, success_count, survival_count, raw_file, raw_sha256`를 요구하고 원자료 파일의 SHA와 숫자를 다시 대조한다. analyst의 `landing_016` 평가 생산자가 아직 없으므로 현재 평가는 해당 객체를 만들지 않는다. 이때 E1 출구는 HOLD이고 학습 진행이나 점수 수집 실패와 구분된다.
- 두 창은 같은 E1 실행의 `p1/score_<회차>/` 산출을 잇는다. 직전 창의 P1 영수증 SHA, 점수 설정 SHA, 저장본 SHA, 단계 ID를 확인한다. 직전 창이 아직 없으면 현재 창을 단독 PASS로 올리지 않는다.

## 답을 아는 입력과 실제 m250

- 저장된 E0 m250 원자료를 E1 규칙으로 CPU 재집계: 유지표 PASS, D44 `평가 열 없음`, 바로 앞 창 `직전 창 없음`, E1 출구 HOLD. 원본 P1은 수정하지 않았다.
- 합성 D44 현재 · 직전 창에서 정확히 prep 성공 하한과 생존 하한이면 PASS, 어느 한 창이 하한 미만이면 FAIL. 하한을 바꾼 계획 사본을 넣으면 판정도 함께 바뀐다. 결측 원자료 · 바뀐 SHA · 다른 칸 이름은 거절한다.
- 현재 통합 가지 병합 뒤 전체 EX-42 CPU: `465 passed, 3 skipped` (`isaac311`, `FOOTHOLD_MACHINE_PROFILE` 로드, `CUDA_VISIBLE_DEVICES` 비움). 통합 가지가 이미 고친 E1 승인 시험을 그대로 유지했다.

## 남은 연결

analyst 평가 전용 `landing_016` 산출의 필드를 위 입력 계약에 매핑하고 `ex42_eval_once`의 자식 평가 단계에 추가해야 D44의 실제 PASS/FAIL이 나온다. 이번 PR의 E1 P1은 그 전까지 평가 열 결측을 명시한 HOLD다. 이미 고정해 실행한 평가 사본에는 새 코드가 소급 적용되지 않으므로 다음 고정 사본과 P1 argv를 다시 대조해야 한다.
