# S2-2 발 광선 Kit 단회 확인 계약
> 분류: A/정책학습
> 작성: sol · 2026-10-16
> 근거: TASK-codex-worker-s2-17ai-fixes.md · VERIFY-astra-17ai.md · 설치된 Isaac Lab 소스
> 요지: 분석적 장면, 실제 USD 및 RewardManager 증거를 단회 학습 0 실행에서 확인한다.
> 상태: CPU 작성 · Kit 미실행

## 실행 범위

`s2_foot_kit_check_once` 전용 요청과 직접 동의가 있어야 한다. N은 최대 8이며 현재 드라이버는 장면별 N=1, 부분 reset 장면은 N=2다. 총 control step은 300 이하, 학습 update와 optimizer step은 0이다. 감독기는 단회 claim, STOP, 독립 관찰자, 소유 Job Object 가족 정리, lease, USD lock, 절대 마감과 영수증을 사용한다. 기존 A3.4 manifest를 재사용하지 않는다. CPU 작성 단계에서는 GPU나 Kit를 시작하지 않는다.

## 분석적 정답표

격자 순서는 x가 느린 축, y가 빠른 축이다. 발 중심 (0,0), 간격 0.05 m, 중심 높이 0.022 m, 접촉 2 N일 때 아래 값이 독립 정답이다. 위험 조건은 `H < z_center - 0.022 - 0.20`이고 접촉 조건은 `Fz > 1 N`이다. 경계 부등호를 완화하지 않는다.

| 장면 | 위험 표본 | 예상 비용 |
|---|---|---:|
| 평면 | 없음 | 0 |
| 직선 절벽 `x > 0.025 m`, 낮은 쪽 -0.30 m | 6, 7, 8 | 3 |
| 대각 절벽 `x+y > 0.075 m`, 낮은 쪽 -0.30 m | 8 | 2 |
| 좁은 cardinal 홈 `0.04 < x < 0.06`, `abs(y) < 0.02` | 7 | 1 |
| 유한 구멍, 바닥 -1.0 m | 구멍 위치에 따른 표본 | 분석식으로 산출 |
| 같은 평면 +0.12 m | 없음 | 0 |
| 직선 절벽을 x로 0.10 m 이동 | 실제 발 위치에 따라 산출 | 분석식으로 산출 |
| swing, `Fz <= 1 N` | 위치와 무관 | 0 |

각 표본의 world XY와 기대 hit Z를 기록한다. 비경계 ray hit XY 및 Z 오차 허용치는 각각 0.001 m다. USD 충돌구 중심과 독립 계산 world 중심 거리 허용치는 0.001 m다. 경계군은 모서리 XY 0.005 m 이내, 높이 0.20 m 경계 ±0.002 m, 접촉 1 N 경계 ±0.05 N으로 따로 기록하고 통과 근거에 넣지 않는다. 비경계 표본 부족은 HOLD다.

## 실제 Kit 영수증

발 이름 및 body/contact ID 순서, 실제 USD 충돌구 중심과 반경, 36개 시작점과 hit, 현재 collision mesh 대응, 구멍 바닥 hit, 같은 보상 단계의 pose/force/hit, 비동기 및 명시적 reset ID/세대, RewardManager의 15+1 항 이름·함수·weight·dt와 각 단계 실출력 및 episode 누적을 기록한다. `kit_step_record`의 계산식 `C × weight × dt`는 독립 기대값이다. RewardManager 실출력과 누적 차이를 별도 검사한다. 자연 종료가 일어나지 않으면 해당 분기를 미시험으로 기록한다.

이 자료는 Kit 실행 전이므로 실제 USD, 충돌, 보상, 지지/swing 여부는 미확인이다. 결과 중 하나라도 빠지거나 서로 다르면 HOLD, 자동 재시도 없음.
