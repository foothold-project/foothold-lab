> 분류: A/정책학습 · 학습 · 보상 · 관측
> 작성: 오흥재 (runner 반영) · 2026-11-02
> 근거: lead G2/G1/U5 지시 · 939ef8f3 · ex41-fixed5000.yaml · isaac311 CPU · HEAD 후속
> 요지: pose_cmd 결선, bounded rehearsal DRY, EX-41 동일 run 저장본 이어 학습
> 상태: CPU 직렬화/manifest 계약 통과 · 실제 Kit 재개 미확인 · Kit/GPU 미실행

# EX-41 pose 관측 결선과 bounded rehearsal 준비

## 고정 입력과 변경

고정 plan은 `foothold_s2/curriculum/ex41-fixed5000.yaml`이다. 실제 m6000 부모 파일은 `C:/Users/AI-WS01/s2_lab/ex40_main_20261031_041313/main/EX-40-B-main_20261031_041337_26240/model_6000.pt`이며 파일 SHA-256이 plan의 `d5e9ec400f33d74d97e7c69d4ab2092d4980195141bb8b30e683730eecd6b6f5`와 일치했다. manifest의 `checkpoints.model_6000.pt`도 같은 SHA다. manifest `progress.completed_updates=8001`은 run 진행값이며 `model_6000.pt`의 회차로 사용하지 않았다.

scripter 고정본 `939ef8f3`의 `start_obs.apply_ex41_pose_observation`을 `prepare_ex41_env_cfg`에서 `gym.make`보다 먼저 부른다. 별도 `pose_cmd` 그룹의 두 열은 `height_delta_m`, `body_roll_rad`이며 설정값은 0이다. StartRunner가 원래 읽는 첫 TensorDict에서 정책 45, depth 60x60, GT map 512, GT feet 100, base velocity 3, contacts 4, pose_cmd 2 차원과 pose_cmd 열별 0을 한 번만 검사하고 영수증에 남긴다. 추가 관측 호출은 하지 않는다.

bounded rehearsal 인자는 정확히 10 update, 새 `s2_lab/ex41_rehearsal_YYYYMMDD_HHMMSS` 폴더, headless cuda:0, 단일 프로세스만 받는다. 저장 간격은 1로 설정한다. production의 W71 false 차단은 유지된다. rehearsal의 실제 학습과 점수평가는 미실행이며, Kit/GPU 기동도 하지 않았다.

## CPU 검증

실행한 사전검증 명령:

```powershell
C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe -m foothold_s2.scripts.train_start --task FootholdS2-Go2-S2-SB-v0 --ex41_table foothold_s2/curriculum/ex41-fixed5000.yaml --ex41_parent_checkpoint C:/Users/AI-WS01/s2_lab/ex40_main_20261031_041313/main/EX-40-B-main_20261031_041337_26240/model_6000.pt --ex41_rehearsal_updates 10 --ex41_rehearsal_output C:/Users/AI-WS01/s2_lab/ex41_rehearsal_20261102_164500 --device cuda:0 --headless --ex41_dry_run
```

출력은 `kit_started=false`, `gpu_used=false`, 부모 파일 SHA 일치, 부모 `model_6000.pt`, plan SHA `da3ee91a490115f33ed5fd188dc69de2328c0e8cde35d9b44c0790d6d7544d8d`, `initial_dr_scale=0.5`, `w71_ready=false`, `production_launch_allowed=false`였다. 실행기의 초기 dry-run은 Kit bootstrap과 task-config import 전 종료하므로 실제 env import는 확인하지 않았다.

CPU 시험 명령:

```powershell
C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe -m pytest foothold_s2/tests/test_ex40_no_window_stdio_cpu.py foothold_s2/tests/test_ex41_pose_observation_cpu.py foothold_s2/tests/test_ex41_startup_integration_cpu.py -q
```

결과: `17 passed in 11.71s`. 포함 내용은 실제 pose producer의 CPU 입력, 준비 함수 호출 누락 반례, 첫 TensorDict 가짜 계약, 숨김 자식 2단 프로세스, rehearsal 회차·출력 경로·기기 반례다.

## lead 전용 예행 명령 초안

아래는 실제 실행 허가가 아니다. lead가 Kit/GPU를 승인한 뒤에만 실행할 수 있다.

```powershell
C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe -m foothold_s2.scripts.train_start --task FootholdS2-Go2-S2-SB-v0 --ex41_table foothold_s2/curriculum/ex41-fixed5000.yaml --ex41_parent_checkpoint C:/Users/AI-WS01/s2_lab/ex40_main_20261031_041313/main/EX-40-B-main_20261031_041337_26240/model_6000.pt --ex41_rehearsal_updates 10 --ex41_rehearsal_output C:/Users/AI-WS01/s2_lab/ex41_rehearsal_20261102_HHMMSS --device cuda:0 --headless
```

실행 시 예상 readback 표식은 `EX41_FIRST_OBSERVATION`과 `EX41_REHEARSAL_READBACK`이다. 여기에는 첫 pose_cmd 열별 0, 첫 관측 차원, DR scale 0.5, W86 항목·발 순서, update 10, save interval 1을 출력한다. 실제 Kit에서의 readback은 미확인이다.

## U5 동일 run 이어 학습 경로

EX-41 저장본 재개는 `--ex41_table`, 고정 m6000 `--ex41_parent_checkpoint`, 기존 run 의 `--ex41_log_root`, 같은 run 의 numbered `--resume_from`을 함께 준다. 새 run 출력 폴더를 만들지 않는다. preflight 는 Kit 전에 기존 manifest 와 선택 checkpoint SHA, 진행 update, plan/effective SHA, 고정 부모 SHA와 continuation receipt를 확인한다. 불일치하거나 새 continuation receipt가 없는 이전 저장본은 거절한다. W71 생산 허가는 기존 관문을 그대로 통과해야 하므로 이 경로가 W71 차단을 우회하지 않는다.

EX-41 루프는 zero-based PPO loop index 를 update `n=loop_index+1`로 바꾼 뒤 저장한다. 따라서 `model_10.pt`는 `iter=10`, `completed_updates=10`이며 다음 update 는 11이다. 이어 시작할 때 runner 의 저장 회차를 10으로 두어 loop index 10에서 update 11이 시작되게 한다. 일반 runner의 manifest 갱신은 `iter+1`을 쓰므로 EX-41 저장 후 `progress.completed_updates`를 실제 one-based update 회차로 맞춘다. 이 불일치가 있으면 resume preflight가 거절한다.

preflight는 Kit 앞에서 checkpoint 파일 SHA와 manifest/continuation receipt를 확인한 다음 checkpoint payload를 CPU로 열어 저장된 plan/effective/parent SHA, W72 상태, optimizer, AdaSmpl, DR, fixed clock, terrain과 command/RNG 상태를 검증한다. receipt의 회차·W72 경계·DR·시계도 실제 checkpoint 값과 대조한다. 이어 환경에서 `runner.load`를 수행한 뒤 저장된 update·segment와 live DR을 다시 확인한다. 재개는 기존 `agent.yaml`, `env.yaml`, checkpoint map을 다시 만들거나 덮지 않으며 같은 run manifest에 시도/readback을 추가한다.

StartRunner checkpoint 는 optimizer 와 perception optimizer, AdaSmpl, policy/perception, RNG, env terrain levels/types, command RNG, W72 snapshot/last boundary, DR runtime 및 fixed schedule `elapsed/pause_used/recovered/extension`을 가진다. 추가 `ex41_resume` envelope 는 plan/effective/parent SHA, completed/next update, W72 boundary/snapshot과 fixed clock을 적는다. runner restore 뒤에는 상태 구조, plan/parent SHA, update/segment, live DR scale를 다음 rollout 전에 다시 대조한다.

같은 run 을 재개할 때의 CLI 형식:

```powershell
C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe -m foothold_s2.scripts.train_start --task FootholdS2-Go2-S2-SB-v0 --ex41_table foothold_s2/curriculum/ex41-fixed5000.yaml --ex41_parent_checkpoint <고정 model_6000.pt> --ex41_log_root <기존 D:/s2_lab run 폴더> --resume_from <같은 run 폴더/model_N.pt> --device cuda:0 --headless
```

## U5 CPU 시험 결과

`foothold_s2/tests/test_ex41_resume_cpu.py` 는 CPU에서 실제 EX-41 저장 구조를 닮은 checkpoint를 저장하고 새 Python 프로세스에서 읽어 필드 전체 안정 digest가 같은지 확인한다. checkpoint 내부 plan/parent SHA 불일치, manifest progress 앞섬/뒤처짐, receipt와 payload 불일치, optimizer/RNG/command RNG/terrain/W72/fixed-clock 상태 누락을 거절한다. 마지막 실행은 `18 passed`였다. EX-41 시작·디스크·preflight 관련 CPU 검사는 아래 기록대로 별도 실행한다. ruff는 isaac311 환경에 설치되지 않아 실행하지 못했다.

이 시험은 torch checkpoint serialization·새 프로세스 readback 과 runner hook 계약 시험이다. 실제 Isaac 환경에서 StartRunner의 optimizer/env restore, 첫 다음 rollout, W72/DR의 Kit readback 은 미확인이다. 실제 Kit/GPU 재현은 lead 승인 뒤 수행해야 한다. 학습, 평가, Kit, GPU 및 실행 프로세스는 이 작업에서 시작하지 않았다.

점수 연결은 아직 없다. 기존 `foothold_s2.ex41_score`는 score draft, 64-env map_modes와 세 mode의 stand 자료를 요구하며, 10 update rehearsal에 대한 draft/evaluation producer를 이 코드가 만들지 않는다. 임의 판정이나 score를 만들지 않았고 W71 loop 연결 완료로 표시하지 않았다.

관련 EX-41 시작 preflight · startup integration · disk guard 시험 결과: 29 passed in 6.89s. 최종 U5 시험 재실행 결과: 18 passed in 6.15s. 총 47개 통과, 실패 0, skip 0. 두 실행은 isaac311 CPU만 사용했고 pytest 임시 경로는 D:/mai-tmp/runner/ex41-u5 였다.
