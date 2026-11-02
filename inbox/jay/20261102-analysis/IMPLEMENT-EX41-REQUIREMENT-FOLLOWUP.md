> 분류: A/정책학습 · EX-41 요구 등록부 후속
> 작성: analyst · 2026-11-02
> 근거: 0e85c3d7 EX41-REQUIREMENT-REGISTER · lead 18:2x 분담
> 요지: U6·U10·U12·U15·U16·U17·P3·P7·P8을 소비 경로와 알려진 입력으로 확인한다.
> 상태: 항목별 진행 · GPU/Kit/라이브 변경 없음 · 미연결은 완료로 세지 않음

# EX-41 요구 등록부 후속

## U6 · 전역 오류와 reset 실패

W86 생산부는 `FatalTrainingFault(ValueError)`와 `ex41_fatal.jsonl`을 제공한다. 전역 정책 NaN, env 단위가 아닌 관측/전이 NaN, 모든 env 행동 무효, reset 예외, reset 뒤 관측 무효를 env 격리 성공으로 처리하지 않고 현재 rollout에서 예외를 낸다. 정상 env가 있는 국소 오류는 기존 격리·PPO valid mask 경로를 보존한다.

영수증 계약: format=`ex41-fatal/1`, event=`fatal_training_fault`, step, reason, stop_requested=true, resumable_checkpoint_written=false, required_action=`preserve_last_verified_checkpoint_and_stop_before_update`. reset 실패에는 env_ids·error_type을 덧붙인다. 기록 I/O 실패도 typed exception을 유지하며 receipt_write_error를 포함한다. 손상 모델을 정상 checkpoint로 쓰지 않는다.

**미연결**: 실행기 소유 scripter가 이 예외와 전역 loss/parameter 오류를 안전한 저장·중단 경계에 연결하고, 마지막 검증 저장본 SHA와 알림을 기록해야 한다. 잘못된 상태로 다음 정기 저장(50회)을 기다리며 학습을 계속하는 의미가 아니다. 알림 운송은 runner의 U3 경로다. 따라서 생산부 CPU 통과만으로 U6 전체를 닫지 않는다.

실측: 수정 전7 FAIL(2.66초), 수정 뒤 U6와 기존 W86 19 PASS(4.91초). 원자료 D:/mai-tmp/analyst/u6-red-1814.log, u6-green-1816.log. 실행기·학습 프로세스·원장 변경 없음.

## U10 · 무릎 토크 한계 접근 기록

기존 0.9 비율 문턱을 그대로 쓴다. FL/FR/RL/RR calf의 `abs(applied_torque)/joint_effort_limit >= 0.9` 횟수·정상 표본 수·비율을 `ex41_w86.jsonl`의 `knee_effort.joints`에 기록한다. 불량 env는 분모에서도 빼며, 표본이 없으면 비율은 null이다. 기록용이며 보상·승급 문턱을 새로 만들지 않는다.

빠져 있던 실제 호출은 `EX41Runtime.flush_consumption`이 맡는다. 기존 runner의 회차 종료 호출에서 W86 기록도 함께 배출한다. 알려진 3 env 입력에서 불량 한 행을 제외한 네 무릎 분자는 `[1,1,2,0]`, 분모는 `[2,2,2,2]`, 비율은 `[0.5,0.5,1,0]`이었다. 실제 Git 설정을 읽는 runtime 시험은 수정 전 파일 없음으로 실패, 연결 뒤 통과했다.

점수 소비 인터페이스는 `ex41_scoring.enrich_training_metrics(draft, w86_metrics_path, *, snapshot_dir)`이다. 같은 회차 기록 하나를 검증하고 `metrics.training_knee_effort`를 넣는다. 늘어나는 JSONL 대신 읽은 회차의 고정 JSON 사본과 SHA를 evidence에 남긴다. 중복·누락·NaN·비율 불일치는 거절한다. **runner 점수기에서 이 함수를 호출하는 연결은 미완료**이며, 그 전에는 U10 전체 완료로 세지 않는다.

실측: U10 첫 반례6 FAIL, 기록 호출 반례1 FAIL. U10·U6·W86·점수·runtime 회귀 60 PASS(40.89초). 원자료 `D:/mai-tmp/analyst/u10-green-1829.log`. GPU·Kit 미실행.

## U12 · 실제 소비율과 지형 분포

기존 `actual_consumption`은 단계·슬롯·지도별 실제 env-step을 기록하고 있었다. 보완한 `config_consumption`은 같은 단계 이름이 재사용돼도 구분되도록 버전 번호와 명령 설정 SHA, 슬롯별 걸음 수, 구·신 설정 걸음 수/비율, 현재 env 배치를 기록한다. 전역 보상·PPO는 경계 즉시 적용이고 명령은 reset에서 바뀐다는 차이를 scope에 명시한다. 전역 설정 SHA와 실제 DR 배율도 따로 적는다. 이름이 같다는 이유로 이전 명령을 새 명령의 성과로 합치지 않는다.

기존 50회 지형 분포 기록에 실제 경계 회차를 더했다. 종류별 env 수·레벨별 수·열 이름·배치 SHA를 보존한다. 정수 아닌 레벨, 음수, 행 수 밖 레벨을 잘못된 집계로 내보내지 않는다. 이 기록은 성과 승급을 증명하지 않으며 실제 승급 동작은 P8에서 다룬다.

실측: 실제 Git 설정 runtime의 4 env 중 2 env만 reset한 입력에서 신 설정2/구 설정2 걸음, 소비율0.5와 종류별2 env가 일치. U12 4 PASS(5.49초), 함께 돌린 기존 U10·runtime 32 PASS. 최초 묶음의 실패1은 시험 장면을 너무 일찍 붙인 fixture 누락(pcfg)으로 고친 뒤 해당 시험을 재확인했다. 원자료 `D:/mai-tmp/analyst/u12-green-1834.log`에는 그 중간 실패가 남아 있으므로 전체 통과 로그로 부르지 않는다. GPU 미확인.

## U15 · 모든 링크 접촉 진단

실제 ContactSensor의 `body_names` 순서로 `net_forces_w`를 받는다. 로봇 링크 전체와 센서 링크 집합이 다르면 attach에서 거절한다. 발·종아리·허벅지·몸통·기타 링크별 접촉 횟수(힘 크기 >1 N), 정상 표본 수, 접촉 비율, 평균 힘과 최대 힘을 `all_link_contact`로 남긴다. 알려진 3 env·6 링크 힘에서 불량 env를 제외한 접촉 수 `[1,1,2,1,0,1]`, 정상 분모2, 최대 힘 `[4,2,5,6,1,7]`을 확인했다. resume에도 링크 순서·누적값이 보존되며, 순서가 바뀌면 합치지 않는다.

한계: 제어 주기의 reset 전 순힘 표본이다. 물리 substep의 모든 충격이나 서로 상쇄된 접촉까지 증명하지 않는다. 원자료가 없으면 unavailable이며 접촉0으로 꾸미지 않는다. 기록만 추가했고 충돌 보상/종료 문턱은 바꾸지 않았다. 설치 API 근거: IsaacLab `sensors/contact_sensor/contact_sensor.py:117`, `assets/articulation/articulation.py:161`. 실제 Kit 연결은 미확인이다.

수정 전 U15 반례3 FAIL. U15·기존 W86 최종 15 PASS(5.21초), 이어받기·이름·분모 시험을 포함한다. 원자료 `D:/mai-tmp/analyst/u15-final-1840.log`. 중간 물리 fixture의 새 이름 필드 누락은 원래 광선 회전 시험을 유지하며 보완했다.

## U16 · foot_slip와 W53 어댑터의 구분

`prepare_env_cfg`의 `ex41_foot_slip`은 n0에 가중0으로 등록된다. RewardManager가 0 가중 항을 건너뛰어도 `terminations.ex41_invalid` → `invalid_env` → `refresh`가 계측을 생산하며 U10의 실제 flush 호출이 파일로 남긴다. CPU 답: 접지 발 수평 속도(0.3,0.4) m/s에서 비용0.25 m²/s², 공중 발 속도(3,4)는 제외했다. 가중0 항의 가짜 보상 로그로 대신하지 않는다. 등록·실제 termination 소비·옛 어댑터 차단 4 PASS(2.58초).

W53에서 막힌 `basic_gait_bundle.validate_settings(... feet_regulation_weight=...)`는 별개의 지면 기준 어댑터다. 0이나 음의 가중을 넘겨도 기존 거절이 유지된다. **그 어댑터가 검증됐다고 쓰지 않는다.** 현재 foot_slip는 접촉력 크기 >1 N인 발 링크의 세계 XY 속도 제곱 합이다. 지면 법선에 투영한 접선 속도나 접촉점의 회전 속도까지 포함한 참 미끄럼량은 아니다. 경사면·움직이는 바닥 해석에는 한계가 있으며, 이에 대한 새 보상 연결은 이번 범위에 없다. 실제 Kit 계측은 미확인이다.

## U17 · 제외된 8 FAIL의 처분

직접 재현: 지정된 `test_ex40_dr_v8_cpu.py`·`test_ex40_launch_smoke_cpu.py`·`test_ex40_v7_continue_cpu.py`는 8 FAIL·26 PASS(12.81초). **원자료를 재기 전까지 단순한 옛 시험이라고 가정하지 않았다.** 실패별 처분은 다음과 같다.

| 실패 시험 | 확인한 차이 | 처분 |
|---|---|---|
| dr_v8: range_interpolation | 실제 설정은 verified, 시험은 implementation_in_progress 기대 | 실제 verified 확인 + 별도 미검증 입력 거절 유지 |
| dr_v8: empty_ranges | 위와 같은 상태 기대, main 거절에 정본을 사용 | D: 시험용 미검증 YAML을 명시해서 거절 검증 |
| dr_v8: d76_push_range | 완성된 범위인데 미검증 거절 기대 | 완성 범위는 읽고 상태만 바꾼 반례로 거절 |
| launch_smoke: official_smoke | 11/1 기한이 지나 실패 | CPU 영수증용 유효 기한 생성, 과거 기한 거절 시험 추가 |
| launch_smoke: official_main | 실제 verified 정본을 미검증으로 기대 | 미검증 YAML을 명시, 시작 전 거절 유지 |
| launch_smoke: official_resume | 실제 verified라 파일을 읽음 | 미검증 YAML에서 spec 읽기 전 거절 확인 |
| v7_continue: resume_cli | 정해둔 일정이 현재 시각의 여유 검사를 못 넘음 | 시험 안 계약 시계만 10/28로 고정 |
| v7_continue: resume_preparation | 위와 같음 | 같은 고정 시계로 계약 확인 |

수정 뒤 세 파일 **35 PASS(15.23초)**. 구현·정본 YAML·학습 프로세스는 변경하지 않았다. 미검증 설정 거절·지난 기한 거절·비실행 CPU 영수증 검사를 남겼으며 skip/xfail로 가리지 않았다. 원자료 `D:/mai-tmp/analyst/u17-existing-1844.{log,xml}`와 `u17-fixed-1847.{log,xml}`. 이 결과는 세 파일 범위이며 저장소 전체 또는 Kit 통과가 아니다.

## 남은 항목

U10 무릎 한계 비율·점수 칸, U12 실제 소비·분포, U15 모든 링크 접촉, U16 foot_slip/W53, U17 기존8실패 처분, P3 승인 거울 경로, P7 최종 T0′·졸업, P8 실제 지형 승급. P3는 자동 거울 끔 결정을 유지하며 수동 승인 경로와 관찰 후보를 구분한다. P7 문턱은 planner 정본 확인 뒤 연결한다.
