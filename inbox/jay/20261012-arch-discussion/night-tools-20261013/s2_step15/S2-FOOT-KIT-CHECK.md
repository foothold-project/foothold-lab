# S2-2 발 광선 Kit 단회 접속 계약
> 분류: A/정책학습
> 작성: sol · 2026-10-16
> 근거: TASK-codex-worker-s2-2-foot-reward.md · VERIFY-astra-17ag.md 1~2절
> 요지: 학습 없이 실제 발 충돌구, 지형 광선, 접촉력의 같은 시점 계약을 확인한다.
> 상태: 제안 · CPU 작성, Kit 미실행

## 범위와 실행 경계

- 한 번만 실행한다. `N <= 8`, 최대 300 control step, 50 Hz이면 물리 시간 상한 6초다. 학습 update와 optimizer step은 모두 0이어야 한다.
- 별도 직접 동의, GPU 슬롯, 마감, 출력 경로, STOP 경로, 소유자와 단회 claim을 실행 전에 묶는다. 이 문서는 승인 파일이 아니다.
- 기존 A3.4 감독기의 Job Object 가족 소유, 마감, 상태, 영수증, 단회 claim 방식을 재사용할 수 있다. A3.4의 진단 전용 계약과 합격 판정 자체는 재사용할 수 없다. 새 `s2_foot_kit_check` 범위, 요청 검증과 합격 판정이 필요하다. 기존 slot과 guard 파일은 수정하지 않는다.
- `s2_foot_query.live_raycast`는 Isaac Lab 정적 소스의 `raycast_mesh`와 설치된 RayCaster mesh cache를 사용한다. 이 실제 호출, USD 발 collision 형상, 발 body ID 순서는 Kit에서 미확인이다. 미일치 시 HOLD로 끝낸다.

## 장면과 사전 고정 값

| 장면 | 예상 원시 비용 |
|---|---:|
| 알려진 평면, 지지발 | 0 |
| 직선 절벽, cardinal 한 점 이상 위험, 지지발 | 발당 1 |
| 대각 절벽, diagonal 한 점 이상 위험, 지지발 | 발당 2 |
| 둘 다 위험, 지지발 | 발당 3 |
| 유한 깊이 구멍, 20 cm 초과 낙차 | 해당 유형 비용 |
| 같은 장면을 높이와 XY로 평행 이동 | 같은 비용 |
| 모든 장면의 swing 발 | 0 |
| env별 reset 직후 첫 frame | 새 episode ID, 새 frame 0 허용 |

3×3 world XY 간격은 요청에서 명시한 `0.05 m`다. 발 충돌구 중심 기준 높이는 `z_center - 0.022 m`이고 위험은 `H < z_ref - 0.20 m`이다. 실제 설치된 USD collision sphere 중심이 URDF의 발 링크 `(-0.002,0,0)`과 다르면 즉시 HOLD한다. 광선 시작 높이의 +20 m는 광선에만 적용한다. 하향 최대 30 m는 타일 표면과 원점보다 1 m 아래 구멍 바닥을 모두 덮는지 장면별로 확인한다.

기하 판정 허용치는 실행 전 `0.005 m`로 고정한다. 절벽 모서리에서 표본 XY와 삼각형 경계의 거리가 `0.005 m` 이내이거나 높이 낙차가 0.20 m 임계에서 `0.002 m` 이내면 경계 수치 불안정으로 따로 분류한다. 그 점은 통과 증거로 세지 않는다. 접촉력 1 N 임계 인근 `±0.05 N`도 별도 관찰한다.

## 매 제어 단계 기록

`kit_step_record` 형식으로 env, episode ID, frame ID, 발 body ID와 이름, mesh 경로, 충돌구 중심 world XYZ, 36개 시작 XY/Z, 36개 실제 hit XY/Z 또는 NO_HIT, query 상태, 4개 접촉력 XYZ, raw C, 중앙 불일치 카운터, `C × (-0.01) × dt`를 남긴다. 관측 actor 지도와 보상 광선은 구분한다. 유효 no-hit와 NaN, 부분 inf, 타일 밖, 최대 거리 부족, mesh 없음, stale frame을 별개 코드로 남긴다. 같은 발 pose를 다시 읽어 시작 Z가 누적 상승하지 않는지 확인한다.

## 합격과 보류

알려진 평면, 직선 절벽, 대각 절벽, 유한 구멍, 높이/XY 이동, 지지/swing, 비동기 reset의 비경계 표본이 모두 손계산 비용과 일치하고 raw 비용 `[0,12]`, weighted reward `[-0.0024,0]`(`dt=0.02`일 때)을 지키면 접속만 PASS 후보로 둔다. actor/student와 critic 관측 shape는 reward-off 영수증과 동일해야 한다. 정상 지형에서 edge 조우가 없었다는 이유로 학습 성능을 판정하지 않는다.

USD collision 형상, 실제 발 ray hit, body order, force 축, RewardManager 실측 목록, frame 일치 중 하나라도 미확인 또는 불일치면 HOLD다. 단계 마감이나 GPU 상태와 무관하게 자동 재시도하지 않는다.
