> 분류: A/평가 · 시작 전 준비
> 작성: 오흥재 (runner 초안) · 2026-11-02
> 근거: W78 v1 aa353ee1 · READINESS-EX41-1102.md b021ce2c §1 · 팀장 EX-41 결정 2026-11-02
> 요지: W78 v2 및 EX-41 시작 설정과 정지 후 진단 산출 계약
> 상태: 초안 · 구현 및 Kit 미확인

# EX-41 W78 v2 CLI와 산출 계약

## EX-41 시작 결정과 소유 경계

시작 설정 결정은 부모 `m6000`(checkpoint SHA256 `d5e9ec400f33d74d97e7c69d4ab2092d4980195141bb8b30e683730eecd6b6f5`), DR 초기 배율 `0.5`, 총 `5000`회다. 실행 YAML은 analyst 소유이며 이 문서 초안은 YAML을 대신하거나 실제 설정 반영을 확인한 것으로 보지 않는다.

## 범위

이 계약은 기존 W78 v1 terrain_skill_run.py의 계단 옆방향·후진·오르기 후 회전·되돌아 내려오기, 급경사 케이스와 고정 지형·평균 정책 실행을 유지하고 v2 측정 축을 추가한다. 기존 --terrain-skill은 v1로 보존한다. v2는 별도 --terrain-skill-v2 선택으로 실행해 구 스크립트가 새 측정값을 낸 것처럼 보이지 않게 한다.

v2는 같은 체크포인트에서 다음 전체 조합을 요구한다.

- 지형 레벨 L2와 L5
- 계단 시작 방향 0°, 30°, 60°, 90°
- 지도 모드 eval_gt, eval_pred, probe_prop_only
- v1에 정의된 모든 W78 케이스

계단 시작 방향은 reset 때의 로봇 yaw를 지형 타일의 고정 세계 +x 축에 대해 지정한 각도로 정의한다. 속도 명령은 로봇 몸체 좌표 기준이다. 평가 중 매 스텝 명령과 실제 yaw를 기록한다. 이 정의는 계단 타일의 계단축을 회전시키는 것과 다르다. v2 구현은 계단 생성기와 타일 배치가 이 기준을 지원하는지 CPU 계약 시험 후 적용한다.

## CLI

아래는 구현할 명령 형태다. --terrain-skill-v2 및 --terrain-levels는 현재 v1 parser에 없는 제안 인자이며, 본 문서만으로 실제 실행을 주장하지 않는다.

~~~text
python -m foothold_s2.eval.eval_map_modes
  --task <등록된 EX-41 평가 task>
  --checkpoint <m7500 또는 EX-41 저장본 model_N.pt>
  --out <새로운 빈 산출 폴더>
  --headless --device <cuda:0 또는 cuda:1>
  --envs 64 --eval-seed 42
  --fixed-terrain --terrain-levels 2,5
  --terrain-skill-v2
  --stair-start-angles-deg 0,30,60,90
  --modes eval_gt,eval_pred,probe_prop_only
~~~

필수 검증은 Kit 시작 전에 수행한다. 체크포인트 경로와 SHA, 평가 task, 새 출력 폴더, 유일한 모드 집합, 레벨 집합 {2,5}, 각도 집합 {0,30,60,90}을 검사한다. 중복·누락·알 수 없는 모드와 기존 파일이 있는 출력 폴더는 거절한다. 실행은 저장 없음, latent mean, action mean으로 한다. 시작할 때 부모 manifest에서 실제 iteration, 정책 및 평가 코드 SHA를 읽어 기록한다.

## 수치 정의

| 측정값 | 정의와 분모 |
|---|---|
| 이동 비율 movement_ratio | 각 이동 phase에서 실제 body-frame 수평 속도를 해당 phase 명령 방향에 투영해 dt로 적분한 거리 / 계획한 명령 속도 크기 × phase 전체 예정 시간. 종료 후 표본은 분자에 넣지 않아 종료로 인한 진행 손실을 보존한다. 회전 전용 phase는 null이며 W57 yaw 측정과 혼동하지 않는다. 1 초과 및 음수는 그대로 기록한다. |
| 발별 스윙 높이 swing_clearance_m | 발별 실제 접촉 센서의 접촉 끊김부터 재접촉까지를 스윙으로 분할한다. 이륙 직전과 착지 직후 발 높이의 평균을 지면 대용 기준으로 삼아 구간 내 최대 발 높이를 잰다. 진단 코드 diag_feet.py의 현재 정의를 유지한다. 열린 스윙은 높이 분포에 섞지 않고 open_swing_count로 기록한다. |
| 끌림 비율 drag_ratio_of_contact | diag_feet.py와 같은 정의: 살아 있는 접촉 표본 중 발 수평 세계 속도가 0.15 m/s를 넘은 표본 수 / 살아 있는 접촉 표본 수. 분자·분모와 접촉 임계 1 N을 같이 기록한다. 성공 기준이 아니라 기술 통계다. |
| 정지 진입 뒤 각속도 stop_wz_*_radps | 실제 정지 명령 진입 뒤, 정지 창의 살아 있는 표본에서 몸체 z 각속도의 부호 평균 · 절댓값 평균 · 절댓값 최댓값을 각각 기록한다. 단위 rad/s, 세 값 모두 기술 통계다. |
| 정지 뒤 누적 heading 흐름 stop_heading_flow_*_rad | 정지 진입 직전 heading에서 정지 창 내 각 표본까지의 wrapped yaw 차이를 누적한다. 부호 합과 절댓값 합을 각각 기록한다. 단위 rad이며 endpoint의 wrapped 정지 오차와 구별한다. |
| 후진 정지 뒤 횡 이탈 reverse_stop_lateral_deviation_m | 후진 명령에서 정지 명령으로 넘어가기 직전 위치·heading을 원점으로 삼는다. 이후 고정 정지 창의 위치 변위를 진입 heading의 왼쪽 축으로 투영해 마지막 signed 값과 창 내 최대 절댓값을 기록한다. 단위 m. 후진-정지 전환 인덱스가 입력에 없거나 창이 끝나지 않으면 미측정으로 둔다. |

모든 비율에는 분자, 분모, 유효 표본 수를 저장한다. 이동 비율은 요청한 이동 경로와 실제 이동 경로의 비율이지 커리큘럼의 샘플링 몫이 아니다. 별도 승인 없이 어느 지표에도 합격선을 두지 않는다. 현행 W57 케이스는 목표 회전 후 정지는 포함하지만 후진-정지 명령 구간은 포함하지 않으므로, W57에서 후진 정지 횡 이탈은 해당 케이스가 추가되기 전까지 미측정이다. 명령 크기·전환 시각은 임의로 추가하지 않는다.

## 파일과 영수증

완료 시 출력 폴더에는 terrain_skill_v2.json 한 개와 조합별 NPZ 원자료를 둔다. 각 NPZ는 최소한 t, dt, phase_id, cmd_post, alive, dones, 종료 사유, body-frame 선속도와 각속도, root 위치·자세, 발별 world 위치·속도, 발별 contact를 보존한다. 요약 JSON은 각 (level, stair_start_angle_deg, mode, case)의 요청 조건, 실제 타일 배정과 SHA, 이동 비율, 발별 스윙 높이 분포, 끌림 비율 분자·분모, 생존 표본과 종료 원인을 포함한다.

완료 집합과 영수증은 정확한 조합 키로 단언한다. 같은 level·방향·case의 세 지도 모드는 같은 체크포인트와 동일 terrain assignment SHA를 사용해야 한다. 지정 조합 전체가 검증되기 전에는 final JSON을 만들지 않는다. 진행 중에는 원자 갱신되는 terrain_skill_v2.partial.json, 실패에는 terrain_skill_v2.error.json을 남기며 미완료 상태를 완료로 바꾸지 않는다. 파일 SHA, 평가 코드 SHA, 원본 config SHA, 입력 manifest SHA, seed, env 수, control dt, 실제 level 및 타일 할당을 결과에 기록한다.

## EX-41 maintenance 점수 입력 계약

EX-41 점수의 `metrics.maintenance_counts`는 같은 64 환경 셀별로 아래 정수 구조를 가진다. `passed`와 `baseline_passed`는 등록된 기존 maintenance 셀 판정에서 통과한 환경 수이며, 두 실행 모두 동일한 판정 정의와 `total=64`를 쓴다. 새 합격선은 여기서 만들지 않는다.

| 필드 | 형식 | 뜻 |
|---|---|---|
| `<cell>.passed` | 정수 | 현재 EX-41 저장본에서 등록된 maintenance 셀 판정을 통과한 환경 수 |
| `<cell>.baseline_passed` | 정수 | 기준 부모 m6000에서 같은 셀 판정을 통과한 환경 수 |
| `<cell>.total` | 정수, 항상 64 | 두 판에 동일하게 적용한 환경 수 |

기준은 부모 `m6000` 점수표 `C:/Users/AI-WS01/s2_lab/ex40_main_20261031_041313/scores-b/score_6000_d5e9ec400f33.json`이다. 관찰한 파일 SHA256은 `a1457a3d9ff780bac2804f0949875e305559fa761dc609be09c33ee9a19b85a6`이며, 부모 checkpoint SHA256은 `d5e9ec400f33d74d97e7c69d4ab2092d4980195141bb8b30e683730eecd6b6f5`다. 산출 점수는 이 파일을 SHA로 고정해 `baseline_passed`를 구성하고 원본을 evidence에 포함해야 한다. 점수와 기준표의 SHA 또는 셀 정의가 다르면 점수는 소비 가능한 완료 자료가 아니다.

## CPU 확인과 미확인

CPU 알려진 입력은 조합 전체 누락·중복, 잘못된 지도 모드, 같은 세 모드 사이의 타일 SHA 불일치, 분모 0, 접촉이 닫히지 않은 스윙, 조기 종료 후 분자·분모를 확인한다. 모든 경우 실패는 final JSON 부재로 확인하고 부분 상태와 오류 영수증은 남긴다. 계단 생성 방향의 기하학, 실제 접촉 신호, policy mode별 동작과 GPU 시간은 이 계약 및 CPU 시험만으로 확인되지 않는다. 해당 항목은 최종 EX-41 고정본의 Kit 예행 전까지 미확인이다.
