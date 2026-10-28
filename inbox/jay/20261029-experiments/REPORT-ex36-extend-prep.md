# EX-36 뒤 기본 보행 연장 및 W15 평가 사슬 준비

> 분류: A/정책학습 · 학습 · 보상 · 관측 · 파인튜닝
> 작성: 오흥재 · 2026-10-29 01:52 KST, scripter 반영
> 근거: EX-36 실행 manifest와 basic_start_receipt, `start_runner.py` 저장·재개 경로, W15 평가 코드
> 요지: 완료된 EX-36 A/B 저장본만 SHA로 확인해 같은 조건의 새 학습 구간을 준비하고, 뒤이어 m250 저장본을 차례로 평가한다.
> 상태: CPU 준비 완료 · GPU와 Kit 미실행 · 실제 EX-36 완료 저장본 미확인

## 결과

| 항목 | 확인 결과 |
|---|---|
| 부모 A | EX-36A `model_3000.pt`, 내부 완료 회차·manifest SHA·status done 대조 |
| 부모 B | EX-36B `model_1500.pt`, 같은 대조 |
| 이어받는 상태 | 정책과 정규화 버퍼, PPO optimizer와 학습률, 지각망과 optimizer, AdaSmpl, 환경 라벨, RNG, 지도 끔 난수 상태를 저장본에서 요구하고 기존 `StartRunner.load()` 경로로 복원 |
| 고정 조건 | 3072 env, 24 step, 환경·명령 seed 42, 명령 basic_gait 새 몫 0.30, 복원 지도, `force_gt=True`, 지도 끔 0.10, L0~2 고정 |
| 새 구간 | 원본 폴더를 덮지 않는 `basic-log-root/main/EX-36<arm>-basic-extend-share30_*` |
| 물리 | 새 시뮬레이터와 에피소드 reset 때문에 물리 궤적 동일 재개가 아님. 영수증에 `physical_resume_identical=false` 기록 |
| 평가 | 원본 manifest에 등록된 m250 체크포인트 SHA를 대조하고 W15 13 명령, 3 연속 명령, 지도 3모드, 64 env, turn16 결과를 확인한 뒤 `.done` 기록. 다시 실행하면 `.done`을 되읽어 검증하고 건너뜀 |

EX-36A/B 실제 저장본은 현재 학습 중이므로 아직 SHA나 내부 state를 실측하지 않았다. CPU 시험은 답을 아는 합성 저장본으로 했으며 실제 GPU·Kit 평가 결과를 뜻하지 않는다.

## 학습 종료 뒤 운영 인자

운영자가 완료 `status.json`, `manifest.json`, 해당 `model_*.pt`의 SHA를 확인한 뒤 `PARENT_SHA`에 전체 64자리 SHA를 넣는다. `BASIC_LOG_ROOT`는 새 출력용 절대경로, `END_BY`는 시각대 포함 마감이다. 아래는 DRY 준비 예시이며 `LIVE=1`은 별도 승인된 기동 때만 붙인다.

```bash
END_BY=2026-10-30T08:00:00+09:00 BASIC_LOG_ROOT=C:/Users/AI-WS01/s2_lab/basic_gait_extend_runs LIVE=0 bash foothold_s2/run_basic_gait_extend.sh A cuda:0 C:/Users/AI-WS01/s2_lab/basic_gait_runs/main/<EX-36A-run>/model_3000.pt "$PARENT_SHA" 500
```

B는 arm `B`, device `cuda:1`, 완료 저장본 `model_1500.pt`로 바꾼다. 추가 갱신 수는 1~1500을 명시한다. wrapper는 먼저 전체 체크포인트·manifest·시작 영수증·종료 상태를 검증하고 기동 argv를 기록한다. `LIVE` 기본값은 0이다. 실제 실행 사본의 코드가 이 커밋과 일치하는지 운영자가 확인해야 한다.

## 이어진 W15 평가

```powershell
python -m foothold_s2.basic_gait_extend_eval --arm A --run-dir <완료된-연장-run-dir> --out-root <새-평가-root> --final-iter 3500 --device cuda:1
```

위 명령은 CPU 계획만 출력한다. 실제 평가에는 별도의 실행 승인 근거와 `--authorization-ref <근거> --live`를 명시한다. A 500회 연장은 m3250, m3500을 순서대로 평가한다. B 500회 연장은 m1750, m2000이다. 두 작업은 한 번에 하나씩 실행한다. 평가 결과가 누락되거나 SHA가 바뀌면 `.done`을 쓰지 않는다. 승인 근거 문자열은 기록용이며 독립 승인 검증을 대신하지 않는다.

## CPU 검증

`CUDA_VISIBLE_DEVICES`를 빈 값으로 둔 `isaac311-moects`에서 새 시험과 기존 basic gait 시험 26개 통과. Git Bash DRY는 실제 argv·영수증을 쓰고 학습을 시작하지 않는 것 확인. 잘못된 SHA, 미완료 status, 바뀐 지도 상태, 잘못된 arm·예산·stop 경로, 저장본 변조, 승인 문자열 누락을 반례로 거절했다. `py_compile`, 설치된 pyflakes와 ruff `F`, `git diff --check`도 통과했다.

미확인: EX-36 실제 `model_3000.pt`/`model_1500.pt`가 만들어지고 status done이 된 뒤의 실파일 대조, 새 구간의 Kit 실행, W15 평가 결과. 기존 학습을 건드리거나 GPU를 기동하지 않았다.
