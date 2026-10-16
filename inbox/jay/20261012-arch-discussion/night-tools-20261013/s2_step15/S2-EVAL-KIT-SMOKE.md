# S2 Kit 평가 첫 단회 계약
> 분류: A/평가
> 작성: Codex · 2026-10-16
> 근거: TASK-codex-worker-s2-eval-kit2.md · 1043 q_eval_cmdr.py · A3.4 감독기 · Isaac Lab ManagerBasedRLEnv 소스
> 요지: 학습 0회, update 0 A/B 네 case의 정보 수집 범위와 HOLD 기준을 고정한다.
> 상태: CPU 확인, Kit 미확인

## lead가 결과 전에 고정한 값

| 구분 | case 쌍 | 명령 | 체크포인트 | 판정 |
|---|---:|---|---|---|
| 첫 Kit 단회 | gap 2, stepping_stones 2, 대조 0 | fwd10, 1.0 m/s | A/B update 0 | 정보 수집만 |
| 전체 측계 | gap 20, stepping_stones 20, flat 10, stairs_up 10 | fwd10, 1.0 m/s | A/B update 0 및 2000 | 첫 단회와 독립 계약 필요 |
| 선택 보조 | 위와 같은 case만 | fwd03, 0.3 m/s | 사전 봉인된 경우만 | 결과 확인 후 선택 금지 |

gap과 stepping_stones는 1043 `unseen10` 생성기의 난도 0.5를 쓴다. 행은 family별 ordinal `% 8`, 열은 각 family의 단일 열이다. 평가 seed는 학습 seed 11, 7 및 이후 학습 seed와 겹치지 않아야 한다. 1043 기본 지면 마찰은 static 1.0, dynamic 1.0이다. `policy_dt=0.02`, `physics_dt=0.005`, `act_inference`만 허용한다. 전체 비교의 구간은 1043 Tango 95%이고, 첫 단회에는 성능 판정을 내리지 않는다.

## 봉인할 입력과 감독 범위

`s2_eval_cases.py`로 smoke case JSON을 먼저 만들고, E1 부모 SHA `c8951b797dbe41570009e9de35589d56b7ea1d10092728af17761d46a2df47e8`, agent.yaml SHA `9b8149ddc6101f92966d2ffdef326f44fa0fb46553678d8f092bcf624dc3173b`, A/B update 0 체크포인트 SHA를 담은 job JSON을 봉인한다. case JSON의 파일 SHA와 내부 `cases_sha256`를 모두 기록한다. 학습 seed 전체 목록, 평가 seed 네 개, terrain 소스 경로와 SHA, 생성 설정 SHA, 명령과 마찰을 결과 전에 고정한다. 승인 JSON은 여기서 생성하지 않는다.

`s2_eval_scope.py`의 `scope=s2_eval_kit_smoke_once`, `purpose=evaluation_information_only`, `training_updates=0`, `max_launches=1`, `retry_count=0`, `observer_mode=attended`가 단회 범위다. 자식은 `s2_eval_driver.py`의 Kit 진입만 허용한다. `required_argv()`의 옵션과 순서, `episodes.json`, `child.log`, USD root, 코드 의존 목록과 SHA, Python과 격리 래퍼 SHA를 봉인한다. 마감은 현재 시각 뒤 900초 이하이다. `s2_eval_supervisor.py`가 단회 claim 디렉터리 생성, GPU UUID lease, 기존 slot의 OS USD 변환 잠금, 독립 watchdog PID와 생성 시각, Job Object 가족 소유, STOP과 시간 및 자원 제한을 확인한다. watchdog은 별도 프로세스로 먼저 준비하고 등록 영수증을 쓴다. 이 문서는 watchdog이나 승인을 자동 생성하지 않는다.

USD 변환 root는 격리 래퍼에 `FOOTHOLD_USD_ROOT`와 `FOOTHOLD_EXPECT_CONVERSIONS=any`로 전달한다. 평가 자식은 네 case의 A/B를 위해 최대 여덟 환경을 만들 수 있으므로 A3.4의 1회 변환 상한을 그대로 적용할 수 없다. 감독기는 `usd_conversion_cap=8`을 매 관찰 주기에 검사하고 초과하면 소유 가족을 끝내며, `s2_eval_usd_provenance.py`는 사후에 실제 변환 수 1~8, 모든 배정 경로와 출력, robot USD 참조가 격리 root 안에 있는지 확인한다. 실제 변환 횟수는 Kit 첫 단회 전에는 미확인이다. A3.4 `asset_snapshot`으로 URDF, 실제 mesh 참조와 소스 SHA를 기동 전후 대조한다. `_eval`, A3.4 원본 및 slot 파일은 읽기만 한다.

## case 기록과 비교

평가 adapter는 `q_eval_cmdr.py:228-301,335-386`의 설정과 배정 방식을 적용한다. 매 case마다 A 다음 B를 실행한다. `s2_eval_pre_reset.py`는 Isaac Lab `manager_based_rl_env.py:204-241`에서 termination 계산 뒤 `_reset_idx` 직전에 모든 env의 root pose, 접촉 종료 플래그, 지면 위 높이, 선속도와 각속도를 복사한다. reset이 없으면 step 뒤 상태를 쓴다. reset 직후 관측을 종료 물리 상태로 잘못 쓰지 않는다. 작은 높이 센서의 reset 직전 갱신은 첫 Kit 단회에서 확인할 항목이며 실패하면 해당 case가 missing이다.

지문은 실제 USD `/World/ground`의 해당 타일 face 좌표 SHA, row와 origin, 초기 root 상태와 관절 위치 및 속도, body mass와 COM 및 material, actuator gain과 delay, motor offset, 지면 마찰, 명령, dt를 포함한다. `s2_eval_post.py`는 A/B의 case 지문이 다르면 유효한 쌍에서 제외한다. 한쪽 누락과 실패 이유를 분모에서 숨기지 않는다. 접촉과 높이의 실제 Kit 동작, mesh 타일 구획, 단일 Kit 프로세스에서 여러 환경을 반복 생성할 때의 자원 회수는 아직 미확인이다.

## 영수증과 HOLD

단회 영수증은 claim ID, manifest와 승인 및 job과 case 파일 SHA, 코드 폐쇄 SHA, GPU UUID/index, Kit/Isaac/torch import 경로와 버전, 자식 PID, lease와 USD 잠금의 획득 및 해제 시각, USD 변환 결과, 기동/종료/마감 시각, 자식 종료 코드, 가족 비움 확인, 각 case의 A/B 지문, episode 파일 SHA, 누락 사유, 독립 관찰자 로그 SHA를 담는다. `comparison_ready=false`, `performance_verified=false`, `information_only=true`를 유지한다.

관찰자가 준비되지 않거나 PID가 재사용되었거나, 승인 범위와 argv가 다르거나, 입력 및 코드 SHA가 다르거나, seed가 겹치거나, 물리 지문이 다르거나, reset 직전 기록이 없거나, USD/자산 영수증이 불완전하거나, 시간 및 자원 한계를 넘거나, 가족이 남으면 HOLD다. 자식 결과가 네 case의 A/B 여덟 행을 모두 내도 이는 접속과 기록의 확인이다. 학습 성능 또는 전체 60쌍의 결론이 아니다.

CPU 증거는 `test_s2_step14_hooks.py`, `test_s2_step14_scope.py`, `test_s2_step14_usd.py`, `test_s2_step13_eval.py` 출력과 `S2-STEP14-SHA256SUMS.txt`이다. Kit을 실행하지 않았으므로 첫 실기동의 결과, USD 변환 횟수, PhysX 접촉/높이 일치, 실제 자원 사용량은 미확인이다.
