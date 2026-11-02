> 분류: A/정책학습 · 학습 · 보상 · 관측 · 파인튜닝
> 작성: 오흥재 (scripter) · 2026-10-28
> 근거: lead 22:20 예행 결과 · verifier VERIFY-basic-gait-29573c54.md · CPU 답 아는 입력
> 요지: 예행과 본 학습 출력 분리, 추종 기록 정의 보정, 명령 시드와 실제 지형 분포 영수증
> 상태: 코드 준비 · CPU 확인됨 · 수정판 Kit 미실행 · 학습 승인 아님

# 기본 보행 예행 후 고침

## 출력과 기존 예행

`--basic-log-root` 절대경로와 `--basic-stage smoke|main`을 기본 보행에 필수로 했다. 부모와 처음부터 판 이름은 각각 `EX-36A-basic-share30`, `EX-36B-basic-share30` 가칭이다. 실제 출력은 `<root>/<stage>/<name>_<timestamp>_<pid>/`다. 부모 재개도 저장본 옆의 기존 segment 폴더 대신 이 경로를 쓴다. `run_basic_gait.sh`의 실행 전 영수증 역시 `<root>/receipts/<stage>/`에 쓴다. 두 판의 smoke는 부모 2회, 처음부터 10회다. main은 부모 추가 1500회, 처음부터 1501회다. 두 판 모두 seed 42, 3072 env, rollout 24를 유지한다.

이미 만들어진 부모 예행 산출 `C:/mai/wt/foothold-lab/impl-sb/logs/rsl_rl/foothold_s2_sb/2026-10-26_01-17-47_sb-main_resume_20261028_221302_105496`은 읽기만 했고 삭제하거나 이름을 바꾸지 않았다. 새 기동 영수증에 `예행 산출, 정본 아님`으로 적는다. 이 폴더의 `model_1502.pt`도 본 학습 부모로 자동 선택하지 않는다.

## 기록 정의와 시드

`following_env_steps`의 걸으며 돌기에는 몸 전진 속도 0.05 m/s 이상과 명령 부호를 보존한 요속도 추종 비율 0.1 이상을 함께 요구한다. 기존에는 반대 방향으로 돌면서 전진해도 추종으로 셌다. 정지는 지수평균 몸 평면 속도 0.05 m/s 미만과 요속도 절댓값 0.1 rad/s 미만을 함께 요구한다. 정지는 기존 전체 집계의 `nomove`로 남고, 묶음의 `following_env_steps`에만 성공이 기록된다. 이는 학습 보상이 아닌 진단 집계다. 평가 W15의 창 평균과 이 지수평균은 같은 측정량이 아니므로 서로 대체하지 않는다.

기본 보행 분기의 명령 term `cfg.seed`를 env 및 PPO의 42와 맞춘다. 기존 설정 `s1_env_cfg.py`의 명령 기본 시드 0이 그대로 소비되던 결함을 고쳤다. `basic_start_receipt.json`에는 두 시드와 실제 L0/L1/L2 env 수, 레벨·종류 레이블 SHA를 학습 시작 전에 쓴다. 부모 복원과 물리 reset이 끝난 뒤, 처음부터 판의 wrapper 초기화가 끝난 뒤 레벨을 다시 읽는다. manifest에도 이 시작 영수증을 넣는다. 두 판의 초기 레벨 분포가 같다고 가정하지 않는다.

수정 전 Kit 예행 manifest의 분포는 부모 `[1173,841,1058]`, 처음부터 `[1034,1025,1013]`이었다. 두 값은 기존 예행을 읽은 결과이며 수정판의 실제 실행 증거는 아니다. 새 시작 영수증의 Kit 소비는 미확인이다.

## CPU 확인

- `test_basic_gait_cpu.py`, `test_basic_gait_launch_cpu.py`, `test_basic_gait_chain_cpu.py`, `test_w15_map_mode_cells.py`: 23 PASS. 반대 방향 걸으며 돌기, 움직이거나 도는 정지, 정상 추종, 경로 격리, 기존 출력 루트 거절, 잘못된 지형 분포, 중복 영수증을 포함한다.
- 실제 S-B10 `model_1500.pt` SHA 확인을 거친 부모 smoke와 main 영수증 CLI: 각각 종료 0. scratch smoke 영수증 CLI: 종료 0. 부모 SHA는 `4d987818c7e25b89e77b7541feca3ddabedd444c5b20651eb29f3681da040d9d`다.
- Git Bash `run_basic_gait.sh` scratch DRY: 종료 0, `DRY: training not started`, 영수증은 임시 root의 `receipts/smoke`에 생성. `ruff check --select F`, Bash 구문 검사, `git diff --check`: 모두 종료 0.

수정판의 GPU · Isaac · 본 학습은 실행하지 않았다. 승인 전에는 `LIVE=1`을 쓰지 않는다. 이전 예행의 rc0와 Traceback 0은 수정판의 Kit 검증으로 대체하지 않는다.
