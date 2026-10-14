> 분류: A/정책학습 · ASTRA 의뢰 17w · S2 0 단계(학습 없는 Isaac 접속 확인) 묶음 A 의 좁은 검증과 첫 GPU 일 한 번의 허용 조건
> 작성: 오흥재 (lead 세션 · Claude 작성) · 2026-10-15 05:14
> 근거: VERIFY-astra-17v.md 1 · 2 · 3 절 · sol 의 A 중간 보고 `REPORT-s2-step4a.md` (사본 `night-tools-20261013/s2_step4a/`) · lead 재실행 `evidence_lead_0516/` · lead 측정 `night-tools-20261013/s2_lead_measure/lead_measure_20261015_0511.txt`
> 요지: 17v 가 지적한 P1 둘(오래된 센서 packet · yaw 비유한값)을 고치고, 17v 2 절 정답표대로 8 환경 접속 확인과 그 검증기, Windows Job Object 소유 경계의 최소 감독기를 만든 0 단계 묶음 A 다. 학습은 없다. 이 묶음만 좁혀서 검증하고, **첫 GPU 일 한 번(15 분 안팎)의 허용 조건**을 정해 달라. 시간제한 종료 · PPO 차이 · 학습 사슬 · 비교기 · encoder 는 묶음 B 이며 이번에는 보지 않는다
> 상태: 의뢰 (GPU 는 둘 다 비어 있음 · 승인 json 은 값과 조건이 채워지기 전에는 발급하지 말 것)

# ASTRA 17w

## 답하는 자세 (팀장 지시 · 모든 사항에 적용)

비판적이면서도 냉정하고, 현실적이면서도 아주 전문성이 높은, 이 분야를 평생 탐구한 전문가로서 답해 주십시오. **lead 는 Sonnet 5.5** 입니다. sol 의 보고와 lead 요약을 평소보다 더 신중하게 원자료(코드 · 로그 · 반례)로 독립 대조해 주십시오. 17j ~ 17v 의 기준을 적용해 주십시오.

**검증 시간을 줄이기 위한 요청(팀장 질문 반영):** 이번에는 **바뀐 파일과 반례에 집중**해 주십시오. 안 바뀐 2 · 3 단계 파일은 해시 일치(아래 1 절)로 갈음해도 됩니다. 물음은 6 개로 줄였습니다. 깊이를 줄이라는 뜻은 아닙니다.

**분량:** `VERIFY-astra-17w.md` 한 파일. 첫 줄 한 문장 판정, 질문마다 「판정 · 근거 · 남길 미확인」. 코드 수정 · GPU · Isaac · 커밋은 하지 마십시오. em dash 금지.

## 1. 대상과 보고

사본 `night-tools-20261013/s2_step4a/` (`SHA256SUMS.txt` 21 줄: py 20 + md 1). sol 목록 `S2-STEP4A-SHA256SUMS.txt` 24 줄 중 23 개가 현재 바이트와 일치하고, **`test_s2_step4_mutants.py` 하나만 sol 이 A 보고 뒤(05:12) B 변이를 얹으려고 고쳐 해시가 다르다**(목록 `6fa72e6e…78d6` · 현재 `52eae685…fa64`). A 실행기는 `--only` 로 A 변이 5 개만 지정하므로 A 동작은 같다고 lead 는 보지만 이 차이는 ASTRA 가 판단해 달라. 2 · 3 단계 원본 16 + 12 파일 등록 해시는 sol 이 재대조해 불일치 0 이라고 보고.

A 의 파일: `s2_packet_17v.py` · `s2_sensor_tracker_17v.py` · `s2_env_adapter_17v.py` · `s2_env_config_17v.py` · `s2_connect_diag_17v.py` · `s2_connect_check_17v.py` · `s2_stage_gate_17v.py` · `s2_job_owner.py` · `s2_resource_lease.py` · `s2_zero_supervisor.py` · `s2_runner_17v.py` · `s2_chain_runner.py`(변이 대상 한 줄 때문에 포함) · 시험 파일들 · `S2-17V-CONNECT-SOURCE.md`(Isaac Lab 정적 확인표).

sol 주장(`REPORT-s2-step4a.md`):
1. **센서 packet:** obs · raw hit · pose · episode · sim step · 센서 세대 · 원자료 SHA 를 하나의 packet 으로 받고, RayCaster private 갱신 호출을 관찰해 env 별 세대와 source receipt 를 만들며 runner 가 별도 source receipt 를 재조회한다. 같은 XY 다른 높이 reset · 일부 env reset · 번호만 새로 붙인 과거 raw · yaw 같은 이동 반례를 시험. **실제 Isaac private hook 시점은 미확인.**
2. **yaw:** yaw · quaternion · 월드 변환 유한성과 quaternion norm ±0.001 을 앞에서 검사.
3. **8 × 256 접속 진단:** 한 장면 4 terrain 열에 환경 0/1 · 2/3 · 4/5 · 6/7 배치, 256 제어 step, 16 warmup, 64 이동 · 128 새 위치 / 높이 reset · 192 yaw. 검증기가 x-fast 187 칸 · yaw 90° 첫 좌표 · height / offset · 전체 +inf miss 와 깊은 유한 바닥 · 비유한 raw · 2 mm 내부 허용 · 5 mm 경계 제외 수 · raw 세대 · 배정 · 출처를 독립 검사. 분석식 8 × 256 정상과 반례 6 개 + 개입표.
4. **최소 OS 감독기:** `s2_job_owner.py` 가 자식을 suspended 로 만들고 Job Object 배정 뒤 resume, KILL_ON_JOB_CLOSE, PID 재조회로 신호하지 않음. `s2_resource_lease.py` 는 UUID 별 byte lock 과 별도의 호스트 USD lock. `s2_zero_supervisor.py` 는 외부 승인 / 파일 해시 · 단회 claim · STOP · 마감 · 상태 · 영수증 · 가족 종료 후 lease 반납. `s2_stage_gate_17v.py` 는 0 단계 raw 256 × 8 · optimizer 0 · source SHA · artifact SHA 재검.
5. **기존 slot / guard 회피:** A 의 진단 자식은 `isaac_slot_v3.py` 와 `gpu_guard.py` 를 호출하지 않고 감독기의 Job Object 안에서 직접 띄운다는 제안(17v 3 절의 PID 재사용 kill 경로를 피하려고).
**sol 이 적은 한계:** 이 스크립트로 실제 raw 를 캡처해도 검사기는 설계대로 **HOLD** 한다(진단 메타가 `mesh_collision_verified=false` · `fixed_pose_verified=false` 를 명시: Kit · driver 판, RayCaster 가 실제 읽은 vertices / faces / world transform 과 충돌 mesh, 숨은 plane 부재, 고정 자세가 아직 확인되지 않음). 감독기 자신의 Orca / CLI 세션 이탈 후 생존 · 독립 hard deadline watchdog · 다른 GPU 실행기의 같은 UUID lease 참여는 미확인. 정적으로 못 찾은 것: Kit / driver 판 accessor · 환경 전체 재개 · 장애물별 조우 이벤트 · 단일 AppLauncher 안 순차 scene 재생성 안전성(A 는 한 장면 8 환경이라 순차 재생성을 요구하지 않음).

## 2. lead 재실행과 측정

**재실행(05:12:27 ~ 05:12:44 · lead):** `run_all_s2_step4a.py --run-id lead_0516` · 정상 7 개 모두 종료 0 (`core` 16 · `sensor_tracker` 4 · `connect` 8 · `job_owner` 5 · `job_object_os` 1 · `resource_lease` 4 · `zero_supervisor` 6 = PASS 라벨 44) · 코드 변이 5/5 CAUGHT. 변이는 각각 한 줄 치환이고 `first_fail` = `want` 이며 정상 종료 0 · 변이 종료 1: `yaw_finite`(`s2_env_adapter_17v.py` 의 yaw 유한성 검사를 `:` 로) · `independent_sensor_receipt`(`s2_runner_17v.py` 의 source receipt 대조를 `if False:`) · `ray_geometry`(`s2_connect_check_17v.py` 의 grid / yaw 오차 hold 를 `False`) · `claim_exclusive`(`s2_chain_runner.py` 의 `claim.mkdir(exist_ok=False)` 를 `True`) · `job_assign_before_resume`(`s2_job_owner.py` 의 Job 배정 호출 생략). 입력 반례와 코드 변이를 따로 센다.
**lead 측정(05:11, 읽기 전용):** GPU 0 UUID `GPU-c08e23b0-62b6-a4f2-8eb2-11151c6a8c7b` (RTX 5080 · 드라이버 591.86 · 16,303 MiB 중 15 MiB 사용 · bus 41:00.0) · GPU 1 `GPU-315d098f-5fe0-26a0-0d2e-26e2d4c1ae4f` (5,887 MiB 사용 = 데스크톱 앱 · bus 81:00.0) · 해석기 `isaac311-moects` Python 3.11.15 · numpy 1.26.0 · torch 2.7.0+cu128 · psutil 7.2.2 · IsaacLab `37ddf626…0d7` · go2_rl_robotlab `28b4516d…bd` · E1 `model_20000.pt` SHA256 `c8951b79…47e8` · slot 도구 해시(`isaac_slot_v3.py` `974919b0…` · `gpu_guard.py` `7fabec30…` · `usd_isolate_run_v3.py` `30dc2ea9…`) · `_eval/slot/` 의 변환 lock 후보 `isaac_convert.lock`, registry 후보 `isaac_usd_registry_v3.json`. 예약 작업은 `MAI-RL-Backup-1-2`(NAS 백업 · Isaac 아님) 하나, 실행 중 Isaac / Kit 프로세스 없음.
**lead 가 하지 않은 것:** 코드 줄 단위 검토 · 17v 반례를 ASTRA 방식으로 직접 재현 · 변이가 의도한 검사만 바꿨는지 대조 · Job Object 의 실제 동작을 CPU 자식 한 개 시험 밖에서 확인 · 실제 GPU · Isaac · 승인 json 발급 · 어떤 UNDECIDED 값도 채우지 않음.

## 3. 물음 (6 개)

1. **P1 둘이 닫혔는가.** 17v 의 반례(첫 packet 을 계속 반환하며 번호만 정상 증가 · 같은 XY 다른 높이 reset · 일부 env reset · yaw NaN · 비정규 quaternion)가 A 의 packet · tracker · 어댑터로 막히는가. RayCaster 의 private 갱신 호출을 관찰해 세대를 만드는 방식이 충분히 독립적인 근거인가(Isaac Lab 판이 바뀌거나 hook 이 누락되면 어떻게 거절되는가).
2. **8 × 256 진단과 검증기가 17v 2 절 정답표대로인가.** 빠진 것 · 거짓 PASS 위험. **이 스크립트로 첫 실제 캡처를 하면 설계대로 HOLD 한다**(mesh · 충돌체 · 고정 자세 증거 필드가 비어 있음). 그렇다면 첫 GPU 일을 「**정보 수집 단계**」(raw 를 모으고 HOLD 를 사유와 함께 기록하며 합격으로 위장하지 않음)로 허용할 수 있는가, 아니면 mesh / 자세 accessor 를 먼저 채워야 하는가. 허용한다면 이 수집 실행이 모아야 할 최소 자료와, 그 자료로 채우게 될 accessor 목록 · 다음 실행(2 차 0 단계)이 PASS 하려면 무엇이 바뀌어야 하는가.
3. **소유 경계의 충분성.** `s2_job_owner.py` · `s2_resource_lease.py` · `s2_zero_supervisor.py` 가 **15 분짜리 단회 0 단계 한 번**에 대해 충분한가. 남은 구멍(감독기의 세션 분리 · 독립 hard deadline watchdog · 감독기 hang · 다른 실행기의 UUID lease 불참)을 「0 단계 한 번에는 수용 가능」 과 「사슬 전에 반드시 닫아야 함」 으로 나눠 달라.
4. **slot / guard 를 쓰지 않는 직접 기동의 대가.** A 는 진단 자식을 감독기의 Job Object 안에서 직접 띄운다. 이로써 기존 `isaac_slot_v3.py` 의 USD 변환 직렬화(변환 lock · registry)와 `gpu_guard.py` 의 VRAM 바닥 · 감시를 잃는다. 대체물(감독기의 호스트 USD lock · 최저 여유 확인 · 격리된 USD 루트)이 최소 조건을 채우는가, 부족하면 무엇을 더해야 하는가. 이 직접 기동 방식이 17u 의 「승인된 사슬 재사용」 원칙과 어떻게 이어지는가(새 승인 대상이 되는가).
5. **첫 GPU 일 한 번의 허용 조건.** 배치(GPU 0 에 한 번, GPU 1 은 데스크톱 앱 사용 중이라 이번에는 쓰지 않는 안)와 승인 JSON 에 들어갈 값 · 누가 채우나(lead 측정은 위 2 절 · 팀장은 「GPU 사용은 lead 권한」 으로 위임했고 이 단회 일의 마감 · 위험 한도는 lead 가 ASTRA 권고 범위에서 정하는 것으로 한다) · 기동 직전 확인 목록 · 중단 조건 · 보고 문구. 이 실행이 소비하는 claim 은 이후 사슬과 어떻게 분리되는가.
6. **견적과 GPU 놀림 방지.** 이 판정 뒤 첫 GPU 일까지 남은 단계(수정 · 승인 파일 발급 · 기동 직전 확인)의 현실적인 시간. 첫 GPU 일 동안 GPU 1 에 안전하게 올릴 수 있는 일이 있는지(없으면 없다고). 묶음 B 가 끝나는 동안 GPU 가 노는 구간을 줄이려면 0 단계 정보 수집 결과를 B 에 어떻게 반영할지.

## 결과

- `inbox/jay/20261012-arch-discussion/VERIFY-astra-17w.md` 한 파일. 첫 줄은 한 문장 판정. 표기: 확인됨 · 추정 · 미확인.
