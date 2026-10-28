# EX-36 기본 보행 빠른 모드 준비

> 분류: A/정책학습
> 작성: 오흥재 · 2026-10-29
> 근거: EX-36A/B 실행 설정, `foothold_s2` 코드, 설치 RobotLab Go2 보상 원문, CPU 답 아는 입력 시험
> 요지: 정답 지도 기반 기본 보행 연장 구간에서 지각 학습과 깊이 렌더를 선택적으로 끄고 보상 후보를 독립 인자로 준비했다.
> 상태: CPU 확인됨 · Kit 속도와 메모리 효과 미확인 · 학습 미기동
> 판: v1.0

## 1. 25초의 구성과 빠른 모드

lead가 전한 EX-36 실측은 collection 5.8초, learning 19.4초다. 현재 `iter_log`의 `learn_s`는 PPO 갱신과 지각 갱신을 합친 값이므로 손실별 소요 초는 미측정이다. 코드 경로는 `runners/start_runner.py:400-425`의 PPO 뒤 지각 갱신, `:666-687`의 지각 재생이다. 지각 설정은 5 epoch, 4 minibatch (`:60-61`)와 B/S-B의 microbatch 64 env (`tasks/agents/s2_23f_b_ppo_cfg.py:15`)다. 3072 env에서는 768 env 유효 minibatch가 12조각으로 나뉘어 한 갱신에 240조각, 각 조각은 24스텝 시퀀스를 재계산한다. 그 안에서 TR-Net 지도 손실과 I-E의 KL, 다음 관측, 속도, 몸·발 높이 손실을 합친다 (`models/start_perception.py:374-410`). 따라서 19.4초 전부가 지각망이라는 주장은 하지 않는다.

`--fast-gt-only`는 완료된 EX-36A/B 부모 저장본을 SHA로 검사하는 연장 경로에서만 받는다. `force_gt=True`, `map_input=reconstruction`을 유지하고, map-off 10%는 기존처럼 0 지도다. TR-Net forward와 별도 지각 optimizer 갱신을 생략한다. 깊이 센서를 장면에서 제거하고 기존 3600열 깊이 관측 계약에는 0을 공급한다. 지각 재생 버퍼를 할당하지 않으며 깊이 기반 training trace, refined 지도 통계, replay KL 관측을 끈다. manifest와 시작 영수증에 각각의 상태를 남긴다. I-E는 현재 관측에서 51열을 계속 예측하고, actor 96열과 critic 664열 및 모든 지각 가중치·optimizer 구조는 유지한다. 이 모드에서 만든 저장본은 나중에 지각 학습을 다시 켤 수 있는 형태지만, 그 전환의 Kit 실측은 미확인이다.

## 2. 메모리 범위

`PerceptionReplay(3072,24,cpu)`의 `nbytes()`를 CPU에서 재니 **1,402,675,200 bytes = 1.306 GiB**다. 그중 깊이 저장이 1,061,683,200 bytes다. 빠른 모드에서는 이 버퍼가 없어지고 깊이 카메라의 렌더 자원이 빠진다. 지각 상태의 관측 이력·프레임 버퍼, PPO 저장소, PhysX 메모리는 남는다. 따라서 실제 가용 VRAM, 4096 env 가능 여부, 갱신 속도 향상률은 **미확인**이다. 현재 EX-36을 기준으로 env 수를 자동 변경하지 않는다.

## 3. 보상 인자 자리

아래는 모두 선택 인자다. 인자를 생략하면 지금 EX-36 보상에 아무 변경도 없다. 후보 수치는 설치 RobotLab Go2 설정과 `COMPARE-reward-E1-vs-START.md`의 값이며, 새 판의 성과가 아니다.

| 항 | 현재 | 선택 인자 값 | 코드 결선 |
|---|---:|---:|---|
| `track_ang_vel` | 0.5 | 1.0 | 기존 term 가중치만 변경 |
| `track_lin_vel` | 1.5 | 2.0 | 기존 term 가중치만 변경 |
| `joint_acc` | -2.5e-7 | -1e-7 | 기존 term 가중치만 변경 |
| `lin_vel_z` | -2.0 고정 | 절대 갱신 0회 -2.0, 1500회 0 | update 경계에서 기존 term 가중치 변경, 기본 꺼짐 |
| hip 자세 L1 | 없음 | -0.05 | 설치 Go2 `hip_pos_penalty_l1`에 별도 term 추가 |
| `feet_regulation` | 없음 | 미정 | 인자 자리만 예약, 지면 기준 adapter 미확인으로 활성화 거절 |

절대 갱신 일정은 EX-36 완료 부모가 이미 1500회 또는 3000회이므로 연장 첫 갱신에서 0이 된다. 이는 E1의 0→1500회 일정과 같은 절대 축 해석이며, 새 구간에서 일정을 다시 시작하지 않는다. 보상 값은 `rewards/basic_gait_bundle.py`에서 CPU로 계산하고 `runners/start_runner.py:325-330`에서 적용한다. feet regulation은 설치 원문이 지면 높이를 쓰므로 그 계약을 확인하기 전 활성화하지 않는다. 앞 지시의 feet_air_time yaw 및 정지 자세 항은 02:0x 정정으로 제거했다.

## 4. CPU 확인과 한계

`CUDA_VISIBLE_DEVICES=''`에서 `test_basic_gait_fast_cpu.py`, 기존 연장 시험, 지각 시험 합계 **25 PASS**. 알려진 입력으로 일반 모드와 빠른 모드의 GT·map-off I-E 출력이 bitwise 같고, 가중치 key·shape와 optimizer state 구조가 같으며, 빠른 모드에서 TR-Net 호출은 실패하도록 막아도 통과함을 확인했다. 잘못된 GT flag, 잘못된 보상 값, feet regulation 활성화는 거절됐다. Git Bash DRY는 실제 학습 없이 영수증과 argv만 썼다. 바뀐 Python 파일은 pyflakes 0건, `ruff check --select F` 0건, `git diff --check` 통과다.

확장 회귀로 `test_sb_map_switch.py`까지 묶었을 때 **49 PASS, 2 FAIL**이었다. 두 FAIL은 현재 CPU 환경의 editable `rsl_rl` 3.3.0에 `store_code_state`가 없어 `StartRunner`를 import하지 못한 기존 환경 불일치다. 별도 CPU 기동도 같은 설치판의 PPO 생성 인자 `storage` 차이로 멈췄다. 이 차이를 이번 코드로 우회하거나 운영 소스를 바꾸지 않았다. 실제 Kit에서 센서 제거, 장면 생성, 저장·재개, GPU 메모리와 속도는 lead의 별도 확인이 필요하다.

## 5. 안전한 DRY 사용

완료된 EX-36 저장본의 경로와 SHA를 넣어 `run_basic_gait_extend.sh`를 `LIVE=0 FAST_GT_ONLY=1`로 호출한다. `END_BY`, `BASIC_LOG_ROOT`는 기존 연장 기동기와 같이 필수다. 보상 후보는 `BASIC_TRACK_ANG_WEIGHT`, `BASIC_TRACK_LIN_WEIGHT`, `BASIC_JOINT_ACC_WEIGHT`, `BASIC_HIP_POS_WEIGHT`, `BASIC_LIN_VEL_Z_SCHEDULE` 중 필요한 것만 설정한다. `BASIC_FEET_REG_WEIGHT`는 예약 인자이며 값이 있으면 거절한다. 실제 학습을 시작하는 `LIVE=1`은 이 보고의 CPU 검증 범위가 아니다.
