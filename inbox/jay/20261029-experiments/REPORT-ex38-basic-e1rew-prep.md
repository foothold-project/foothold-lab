# EX-38 기본 보행 보상 판 기동 준비

> 분류: A/정책학습 · 학습 · 보상 · 관측 · 파인튜닝
> 작성: 오흥재 (scripter 반영) · 2026-10-29 02:43
> 근거: lead 10/29 02:3x EX-38 정정 명세, S-B10 model_1500.pt, CPU 시험과 DRY 영수증
> 요지: 기존 일반 지각 학습 경로에서 보상 다섯 항목만 바꾸는 EX-38 기동 인자를 고정했다.
> 상태: 인자 파싱 수정 완료 · Kit 재기동 미확인
> 판: v1.1

## 계약

EX-38은 S-B10 `model_1500.pt`에서 재개한다. 실제 파일 SHA256은
`4d987818c7e25b89e77b7541feca3ddabedd444c5b20651eb29f3681da040d9d`였다.
CPU에서 완료 회차 1500, 정책과 지각망 가중치, PPO와 지각망 optimizer 상태,
AdaSmpl `force_gt=True`, PPO 학습률 `0.0002562890625000001`, 지도 끔 비율 0.1을 읽어 확인했다.
실제 runner의 `load()`는 이 가중치와 두 optimizer 및 PPO 학습률을 복원한다.
새 물리 환경과 에피소드는 별도로 시작하므로 동일 궤적 재개로 부르지 않는다.

명령은 `basic_gait` 새 몫 0.30, 환경과 명령 시드 42, 3072 환경과 24 step,
L0~2 활성 라벨 재배치, 지형·명령 커리큘럼 고정이다. 보상 변경은
`track_ang_vel=1.0`, `track_lin_vel=2.0`, `joint_acc=-1e-7`,
`hip_pos_penalty_l1=-0.05`, `lin_vel_z=-2→0`의 다섯 가지다.
`lin_vel_z`는 이 판의 첫 갱신 1501에서 -2, 2251에서 -1, 3001에서 0이며 이후 0이다.
EX-36의 절대 회차 일정 기본 동작은 유지한다.

빠른 모드는 껐다. depth 카메라, TR-Net, I-E 학습과 학습 기록은 일반 경로다.
`max_iterations=20001`은 12:30 마감까지 회차 상한이 먼저 닿지 않게 한 기술 상한이며
18,500회 학습 목표나 승인 예산을 뜻하지 않는다. 실제 종료는
`2026-10-29T12:30:00+09:00`의 기존 갱신 경계 저장 통로가 맡는다.
출력은 `C:/Users/AI-WS01/s2_lab/basic_gait_runs/main/`의 새 실행별 폴더다.
Kit 캐시는 `D:/mai-cache/isaacsim-5.1/DerivedDataCache`로 전달한다.

## CPU 검증

- `isaac311/python.exe -m pytest -q`로 EX-38, EX-36 fast, 기본 기동, 연장,
  기본 보행 관련 다섯 파일을 실행해 정상 31 PASS를 얻었다.
- 답을 아는 반례는 다른 부모 SHA, 0.5 회전 보상, scratch 표식으로 각각 거절한다.
  상대 일정 입력 1501·2251·3001은 각각 -2·-1·0이다.
- `python -m pyflakes`와 `python -m ruff check --select F`는 바뀐 Python 파일에
  각각 0건이었다. `bash -n`과 `git diff --check`도 통과했다.
- 실제 부모 파일로 `run_basic_gait.sh`를 `LIVE=0` DRY 실행해 rc 0,
  `DRY: training not started`를 얻었다. 영수증은
  `C:/Users/AI-WS01/s2_lab/basic_gait_runs/receipts/main/basic_gait_parent_20261029_023906_881525/launch_receipt.json`에 있다.
  되읽기에서 부모 SHA, EX-38 이름, 보상 네 인자, 일정 표식, 일반 지각 경로,
  Kit 캐시와 종료 시각을 확인했다. `training_approved=null`은 이 DRY 도구가
  팀장 동의 자체를 판단하지 않는다는 뜻이며 `training_started=false`다.
- 실제 `resume_parent()`는 설치 `isaac311` 환경에서 완료 회차 1500과 SHA를 반환했다.
  `isaac311-moects`의 별도 editable rsl_rl은 `store_code_state` import가 없어
  같은 CPU 호출을 못 했다. DRY 기동기가 쓰는 것은 `isaac311`이다.

## lead가 사용할 DRY 인자

```powershell
$env:EX38='1'
$env:LIVE='0'
$env:END_BY='2026-10-29T12:30:00+09:00'
$env:BASIC_LOG_ROOT='C:/Users/AI-WS01/s2_lab/basic_gait_runs'
$env:STAGE='main'
$env:SHARE='0.30'
& 'C:/Program Files/Git/bin/bash.exe' foothold_s2/run_basic_gait.sh parent cuda:0 'C:/mai/wt/foothold-lab/impl-sb/logs/rsl_rl/foothold_s2_sb/2026-10-26_01-17-47_sb-main/model_1500.pt'
```

실제 Kit 예행과 학습은 lead가 EX-36B 종료 후 판단해 실행한다. 현재 학습을 건드리지 않았다.
변경 코드와 시험의 SHA256은 `EX38-SHA256SUMS.txt`에 있다.

## v1.1 · 실제 첫 기동의 인자 파싱 수정

lead 첫 기동 영수증의 `run.log`는 `train_sb.py: error: argument --basic-joint-acc-weight: expected one argument`로 끝났다.
기존 생성기가 `--basic-joint-acc-weight`, `-1e-7`을 두 토큰으로 내어 `argparse`가 음수 지수 표기를
다음 옵션으로 읽었다. `--basic-joint-acc-weight=-1e-7`과 `--basic-hip-pos-weight=-0.05`로 바꿨다.
영수증 파서도 이 한 토큰 형식을 읽는다.

CPU 시험은 생성기의 `--print-args` 출력을 그대로 받아 실제
`train_sol23f_common.py`의 `parser.add_argument` 선언을 AST에서 실행한 뒤 `parse_known_args`에 넣었다.
기존 분리 토큰 입력은 지정 실패, 새 한 토큰 입력은 `joint_acc=-1e-7`과 `hip=-0.05`로 파싱됐다.
AppLauncher 인자 등록과 Kit 시작은 실행하지 않았다. 좁은 관련 시험 17 PASS.
첫 기동은 파서 전에 종료되어 학습이 시작되지 않았으며, 수정본의 실제 Kit 재기동은 lead 담당이다.

## 판 이력

| 판 | 날짜 | 변경 |
|---|---|---|
| v1.0 | 2026-10-29 | EX-38 보상 판 준비와 CPU 검증 |
| v1.1 | 2026-10-29 | 음수 보상 인자 한 토큰 파싱 수정과 실제 인자 선언 CPU 시험 |
