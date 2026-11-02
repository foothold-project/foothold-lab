> 분류: A/정책학습 · 학습 · 보상 · 관측
> 작성: 오흥재 (runner 반영) · 2026-11-02
> 근거: lead G2/G1 지시 · 939ef8f3 · ex41-fixed5000.yaml · isaac311 CPU
> 요지: pose_cmd 진입 결선과 EX-41 bounded rehearsal DRY 준비
> 상태: CPU 확인 · Kit/GPU 미실행 · score 연결 미완

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

점수 연결은 아직 없다. 기존 `foothold_s2.ex41_score`는 score draft, 64-env map_modes와 세 mode의 stand 자료를 요구하며, 10 update rehearsal에 대한 draft/evaluation producer를 이 코드가 만들지 않는다. 임의 판정이나 score를 만들지 않았고 W71 loop 연결 완료로 표시하지 않았다.
