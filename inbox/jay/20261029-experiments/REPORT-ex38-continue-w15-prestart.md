# EX-38 연장 경로 · W15 한 표 · 학습 시작 전 점검

> 분류: A/정책학습 · 학습 · 보상 · 관측 · 파인튜닝
> 작성: 오흥재 · 2026-10-29
> 근거: EX-38 실행 manifest, foothold_s2 소스와 CPU 회귀
> 요지: m3001 연장 경로와 W15 표 생성기, 학습 시작 전 CPU 점검기를 준비했다
> 상태: CPU 확인됨 · 실제 연장 미실행
> 판: v1.0

## 1. EX-38 마감 저장과 이어받기

- `runners/sol23f_runner.py:235-252`는 갱신 로그 뒤 deadline 또는 stop-file을 확인하고 `model_N.pt`를 저장, manifest SHA를 기록, `latest.pt`를 저장한 다음 `DeadlineReached`를 낸다. `scripts/train_sol23f_common.py:341-348`은 이를 `stopped_saved` 상태로 기록한다. `runners/start_runner.py:971-978`의 latest 교체는 임시 파일 뒤 `os.replace`이다. 실제 12:30 종료 결과는 아직 미확인이다.
- `runners/start_runner.py:815-829`의 체크포인트에는 정책·PPO optimizer·학습률·지각망·지각 optimizer·AdaSmpl·환경 상태·RNG가 있다. `:993-1009`가 이를 다시 읽는다. 새 Kit 환경과 에피소드는 `scripts/train_sol23f_common.py:274-281`에서 reset하므로 물리 궤적의 동일 재개는 아니다.
- `basic_gait_ex38_continue.py`는 `model_N.pt`의 실제 SHA, 체크포인트 내부 회차, manifest의 EX-38 이름·보상 네 계수·상대 일정 시작 1501·명령 비율·시드·지형·일반 지각·완료 status와 등록 SHA를 대조한다. `latest.pt`와 실행 중 상태는 거절한다. 새 구간은 같은 EX-38 이름, m3001까지 `--max_iterations 3002`, 새 출력 segment로 만든다. 부모 체크포인트 SHA와 경로를 영수증에 남긴다.
- `train_sol23f_common.py`에서 EX-38 lin_vel_z 상대 일정 시작점을 부모 회차+1 대신 1501로 고정했다. m2251의 계수는 -1, m3001은 0이다. 후속 segment에서도 같은 식을 이어 쓴다. 명령·지형 L0~2·env 3072·시드 42·보상 다섯 항·일반 지각 설정을 유지한다.
- 시작 명령은 마감 뒤 완료된 `model_N.pt`의 실제 전체 SHA로 채운다. `END_BY`는 새로 팀장이 정하는 시각이다. 아래는 준비된 호출 형식이며 이 작업에서 실행하지 않았다.

```bash
END_BY='<새 ISO8601 시각+09:00>' BASIC_LOG_ROOT='C:/Users/AI-WS01/s2_lab/basic_gait_runs' LIVE=0 bash foothold_s2/run_ex38_continue.sh cuda:1 '<완료 model_N.pt>' '<실제 SHA256>'
```

`LIVE=1`은 실제 학습을 시작하므로 이번 CPU 작업에서 사용하지 않았다. 현재 EX-38을 중단하거나 수정하지 않았다.

## 2. W15 한 표

- `w15_one_table.py`는 부모 m1500, EX-36A m1750~m3000, EX-38 같은 저장본과 m3001, E1의 저장된 JSON만 읽어 CSV를 만든다. `eval_gt`와 `eval_pred`, `spin+1.2`와 `spin-1.2`, 좌→우와 우→좌를 별도 행으로 둔다. 64 env 생존 수·추종 절대오차·몸 이동 거리·장치 간 반복 폭을 원자료에서 계산한다. 반복 폭은 체크포인트·시드·지형·코드가 같고 GPU UUID가 다른 자료에서만 계산하며 불일치하면 거절한다. 없는 측정은 `미측`이다.
- 현재 CSV `W15-one-table-prepared.csv`는 496행 중 측정 근거 20행이다. 부모 4행은 옛 core 평가라 생존만 비교 가능하고 추종·몸 이동은 미측이다. E1 16행은 `native_student`이며 GT/PRED라고 부르지 않는다. EX-36A와 EX-38의 W15 원자료는 아직 없어서 빈 칸이다. 장치 간 반복 폭도 현재 미측이다.
- 입력 원자료: `C:/mai/wt/foothold-lab/impl-turncases/logs/sb10_eval_x27j/m1500/map64/map_modes.json`, `C:/Users/AI-WS01/s2_lab/eval_e1_w15/e1/e1_w15.json`, `C:/Users/AI-WS01/s2_lab/basic_gait_runs/eval_w15/`.

## 3. 시작 전 점검과 CPU 증거

- `prestart_check.py`는 현재 `train_sb.py`가 위임하는 `train_sol23f_common.py`의 실제 argparse 선언을 AST로 실행해 `launch_args.txt`를 파싱한다. 현재 기동기에 쓰는 파이썬 모듈 8개를 isaac311에서 실제 import하고, `foothold_s2` 소스의 git 상태와 `git diff --check`를 검사한다. 런타임 출력 `outputs/`와 `train_start_status.json`은 소스 청결 판정에서 제외했다.
- `run_basic_gait.sh`, `run_basic_gait_extend.sh`, `run_ex38_continue.sh`, `run_ex35.sh`, `run_ex35_chained.sh`, `run_sb.sh`의 train_sb 기동 전에 이 점검을 넣었다. 새 훈련을 시작하지 않았다.
- CPU 정상 8 PASS: EX-38 부모·상대 일정·실제 parser·미완료 반례·W15 반복 폭. SHA 불일치, 일정 시작 변경, running status, 음수 인자 두 토큰 변이가 거절된다. Bash 문법 검사 6개 정상, `ruff check --select F` 정상, compileall 정상. pyflakes는 isaac311에 설치되지 않아 미실행.
- 커밋 뒤 실제 현재 EX-38 `launch_args.txt`를 isaac311로 다시 읽어 `prestart_pass`, 실제 import 8개, 소스 git clean을 확인했다. GPU와 Kit는 실행하지 않았다.

## 4. 남은 확인

- 12:30 뒤 `status.json`의 `stopped_saved`, `model_N.pt`, manifest SHA를 읽고 연장 DRY를 실행해야 한다. 부모 저장이 없으면 연장 경로는 HOLD다.
- EX-36A·EX-38 W15 결과가 생기면 표를 다시 생성한다. E1 GT/PRED·반복 폭은 별도 같은 조건 자료가 없으면 계속 `미측`이다.
- 기존 실행 코드를 소비 사본으로 옮기는 일과 실제 Kit 학습은 lead의 별도 결정 사항이다.

## 이력

| 판 | 변경 |
|---|---|
| v1.0 | CPU 준비와 미측 칸 기록 |
