> 분류: A/정책학습 · ASTRA 의뢰 17ad · S2 B 번들(학습 진입)의 CPU 증거 판독과 배관 smoke 계약
> 작성: 오흥재 (lead 세션 · Claude 작성) · 2026-10-15 17:50
> 근거: `night-tools-20261013/s2_step5/` (sol 작업, 커밋 e06a4d1c) · `s2_step5/REPORT-s2-step5.md` · `S2-STEP5-LAUNCH-PARITY.md` · `S2-STEP5-USAGE.md` · lead 재실행 `evidence_s2_step5/lead_rerun_1602/summary.json` · `VERIFY-astra-17ac.md` 6절 · `TASK-codex-worker-s2-B-plumbing.md`
> 요지: B 학습 진입은 CPU 에서만 시험됐고 GPU · Isaac 은 0회다. 17ac 가 말한 「0단계 PASS 전 배관 smoke」 를 어떤 계약으로 만들지(sol 이 지금 CPU 에서 구현 중) 와, B 코드 자체의 빈틈을 묻는다
> 상태: 의뢰 (GPU 둘 다 계산 0 · 승인 json 없음 · 4차 수집은 팀장 새 동의 대기)

# ASTRA 17ad

비판적이면서도 냉정하고 현실적인 전문가로서 답해 주십시오. 분량 `VERIFY-astra-17ad.md` 한 파일, 첫 줄 한 문장 판정. 코드 수정 · GPU · Isaac · 커밋 금지, em dash 금지. 17ac 에서 닫힌 것은 다시 보지 말고 아래만 봐 주세요. 확인됨 / 추정 / 미확인을 나눠 주세요.

## 사실 (직접 읽을 것)

- B 번들: `s2_train_entry_17v.py`(학습 진입, Kit import 앞 h5py · torch · tensordict 선적재, headless `cuda:0`, 등록 cfg `RobotLab-Go2-v0` + 희소 지형 overlay, N=1,024, gap/stones 각 15 %, E1 부모 `model_20000.pt` SHA `c8951b79…` 고정, 한 프로세스 한 arm), `s2_train_launch.py`(EULA YES · PYTHONUNBUFFERED · CUDA_DEVICE_ORDER · CUDA_VISIBLE_DEVICES=0 · NUL stdin · GO 보고서 60 s · lease · USD lock · Job Object 가족 · heartbeat · STOP · 마감 · 단회 claim · 해시 영수증), `s2_train_manifest.py`(요청 JSON 봉인), `s2_train_contract.py`.
- sol CPU 증거: 정상 PASS 53, 변이 7/7. lead 재실행(`lead_rerun_1602`) 같은 수. 200 update 의 finite loss/KL/entropy 와 0 · 200 · 2,000 · +500 체크포인트는 **결정적 가짜 runner** 로 확인했고 실제 Isaac 학습은 아니다(sol 보고).
- 기동 동등성 표는 1043 학습의 실제 기동 줄(`night_20261013_cmdr1043_v3.sh`, `branch_run.py`, `isaac_slot_v3.py`)과 B 의 대응을 줄별로 대조한다. 오늘 0단계 첫 두 시도가 이 표의 빈칸(EULA 변수 · 선적재)에서 죽었다.
- 지도 계산 모듈 6개(`s2_env_adapter_17v` `s2_map_obs` `s2_sensor_tracker_17v` `s2_policy` `s2_ppo_17v` `s2_terrain_overlay_17v`)는 0단계 A3 번들과 바이트가 같다. 다른 것: `s2_env_config_17v`(학습은 `RobotLab-Go2-v0` + overlay, 0단계는 `Isaac-Velocity-Rough-Unitree-Go2-v0` + known-answer 장면) · `s2_connect_check/diag` · `s2_packet_17v` 등. 즉 0단계 PASS 는 같은 지도 계산 코드를 다른 cfg 위에서 검증한다.
- 현재 계약(`s2_train_contract.py:88-96`)은 `smoke` 가 정확히 200 update, `short` 가 2,000 이다. 17ac 6절은 이것을 「PPO iteration 1~2 회, plumbing_only」 로 줄이라고 했다.

## lead 계획 (구현 중: sol, CPU)

새 단계 `stage=plumbing`: updates 1 또는 2(iteration, 환경 step 과 분리 기록), `checkpoint_interval==updates`, `max_wall_s<=600`, manifest `plumbing_only:true` · `stage0_passed:false` 필수, 출력은 새 격리 폴더와 `PLUMBING_ONLY_` 접두 체크포인트 + 표지 파일, 부모 checkpoint 전후 SHA 재측정, `input_path` 선언(`live_raycaster_unverified` 또는 `synthetic_known_answer`), 진단 무중력 cfg 의 학습 유입 거절, 두 arm 은 순차(아니면 거절), 영수증에 loss · KL · entropy · gradient · parameter 변화 · NaN · freeze · 학습률 · 저장 후 재적재 일치. 전체 문안은 `TASK-codex-worker-s2-B-plumbing.md` 2절.

## 질문

1. B 코드의 CPU 증거에서 17ac 6절 기준으로 **빠진 것 · 잘못 읽은 것**이 있는가. 특히 (a) 결정적 가짜 runner 로 보인 경계가 실제 Isaac 에서 깨질 수 있는 지점 (b) 기동 동등성 표에서 아직 대조 안 한 줄 (c) `RUN_COMPLETE_UNVERIFIED` 의 의미 한정.
2. 위 `plumbing` 계약이 17ac 6절 조건을 다 담는가. 더하거나 뺄 것은. 특히 N=1,024 로 해야 하는가, 배관만 보는 것이니 더 작은 N 을 허용하는가(VRAM 과 GPU 1 점유 10.5 GB 때문. 단 학습 cfg 와 달라지는 만큼 무엇을 증명하지 못하는가).
3. 첫 실제 Isaac plumbing 의 **성공 판정**은 무엇을 근거로 하는가(영수증 항목 중 필수 · 선택). 어떤 결과가 나오면 HOLD 인가.
4. 0단계 4차 수집과 plumbing 의 **순서와 GPU 배정**: 4차(GPU 0)가 끝난 뒤 plumbing 을 GPU 0 에서 이어도 되는가. 서로 겹치지 않으면 GPU 1 에서 4차와 동시에 plumbing 을 띄우는 것은 17ac 의 「두 GPU 를 채우려는 이유만으로 동시 기동 불허」 에 걸리는가.
5. plumbing 단회에 ASTRA 새 판정이 필요한가, 아니면 17ac 7절처럼 lead 검증 기록 + 팀장 새 동의로 족한 범위가 있는가. 후자라면 그 범위를 정의해 달라(왕복을 줄이기 위함, 거절 가능).

## 하지 말 것

- 무인, 자동 재시도, 후속 학습, A/B 비교 시작 허용으로 읽히는 표현. 17z 무인 보류는 유지.
