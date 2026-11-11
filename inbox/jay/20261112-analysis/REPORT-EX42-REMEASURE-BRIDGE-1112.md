> 분류: 평가 · 구현
> 작성: verifier-lx · 2026-11-12
> 근거: lead 00:56 재학습 부모 채택 의뢰 · 통합 7b43c055 · 실제 b379 기동 plan · CPU 원출력
> 요지: 아홉 저장본 공통 정책 재측정과 새 m1000 PASS의 E1F 부모 채택을 연결
> 상태: CPU 검증 · GPU 미실행 · 실제 1000회 run 바인딩 대기

# EX-42 재측정과 E1F 연결

## 결과와 범위

확인됨: 새 `ex42_remeasure`는 부모 m13000, 옛 E1 m250/500/750/1000, 재학습 E1 m250/500/750/1000을 이 순서로 잰다. 각 저장본은 `ex42_eval_once --device cuda:1 --split-device cuda:0`으로 두 GPU에 나눠 전체 P1을 실행한다. 각 저장본의 작업 완료 뒤 다음 저장본으로 간다. 실행 코드는 기존 평가기이며, 평가 정책은 새 통합 plan, 원래 실행 신원은 각 run의 기동 plan으로 나눈다.

판정 기준선과 문턱은 정본 그대로다. 부모를 새 마찰로 재측정해도 승인 기준선을 자동 교체하지 않는다.

9개가 모두 기술적으로 완료돼야 비교표를 확정한다. 새 run m1000만 E1F 채택 후보이며, 그 P1이 PASS일 때만 W09/W08, 실측 cap 증거, materialize, 자동 승인, CPU 기동 preflight, E1F launcher 순으로 진행한다. 과거 run PASS나 부모 비교 PASS가 새 학습을 시작시키지 않는다. 판정 HOLD/FAIL은 유효한 측정 결과일 수 있지만, 자식 실패와 영수증 누락은 묶음 HOLD다.

현재 실제 재학습 1000회 run은 아직 전달되지 않았다. `EX-42-B-E1-slip50_20261112_004950`은 `max_iterations=50` 및 speed probe이므로 바인딩하지 않았다. GPU/Kit, watcher 실행, 운영 queue 및 표식 쓰기 모두 하지 않았다.

## 실행 계약

| 항목 | 구현 |
|---|---|
| 종료 확인 | 명시한 run의 `train_start_status`: done·iter 1000·log_dir 일치, manifest completed 1000·max_iterations 1000·speed_probe false를 함께 검사 |
| 실행 신원 | manifest CLI의 실제 plan/approvals, startup plan SHA, approval pin, manifest checkpoint SHA와 파일을 대조 |
| 공통 평가 | 같은 새 평가 plan SHA, 마찰 0.8/0.6, seed42, 같은 메시. map64 39칸·axis_v2·stand·D44 전체 |
| 실제 마찰 | map64·axis·stand 세 모드·D44 JSON의 verified readback과 로봇 min/max·지형 값을 재확인, 요청 인자만으로 완료하지 않음 |
| GPU 양보 | done 뒤에도 GPU 프로세스, live/unknown 표식, 실행 중 queue 항목이 있으면 거절. dispatcher 잠금 아래 두 GPU 예약, 평가 표식은 자기 소유만 해제 |
| 새 결과 자리 | `parent/m1000`, `old/m250..1000`, `retrain/m250..1000`. 서로의 이전 창을 읽지 않도록 분리 |
| 코드 및 자료 변경 | request에 코드 HEAD·plan·approvals·이웃 설정·score config·원래 run manifest/startup 등을 pin. 매 평가 앞 재확인 |
| 재실행 | 출력 디렉터리와 영수증 덮어쓰기 거절. 실패 뒤 새 출력으로 재준비하며 실패 자료 보존 |
| 비교 | comparison.json에 원자료 SHA와 map64·D44·두 창 판정. CSV는 원자료 숫자 그대로, 표본이나 인과 해석을 새로 만들지 않음 |
| 부모 m13000 | 로컬 파일 이름은 model_1000.pt. E1 평가 정책으로 비교만 하며 E1 학습 이력이라고 바꾸지 않음 |
| 관문 PASS 뒤 | W09/W08 실제 생산자 → 실측 cap/mesh/baseline 증거 → 불변 plan/approval/transition → 자동 승인 재검 → CPU dry → E1F 시작 |
| 이후 사슬 | 기존 launcher/handoff를 사용. 아래 발견된 별도 연결 공백은 이 PR이 고쳤다고 주장하지 않음 |

실제 완료 영수증의 `launcher_started`는 프로세스 시작 증거다. 첫 update 성공 및 뒤 단계 완주는 별도이며, launcher stdout과 다음 단계 영수증으로 확인해야 한다.

## CPU 검증

- RED: 새 모듈 부재로 ImportError. `/home/jay/mai/tmp/verifier-lx/remeasure-1112/red.log`.
- 답 아는 입력: 50회 또는 다른 run done 거절, GPU 학습/알 수 없는 행 거절, 9개 순서와 양 GPU 인자, rc0 영수증 결측 거절, SHA/정책/마찰 불일치 거절, 타 run PASS 거절, 5번째 자식 실패 뒤 나머지와 기동 미실행.
- 실제 b379 고정 사본의 원래 plan을 읽고 CPU 시험용 PASS·깃발 trace로 materialize와 `validate_automatic_stage_launch`를 호출했다. old plan SHA → gate SHA → 새 plan SHA가 이어진다. 원래 plan에는 새 D44 정책이 없지만 판정은 별도 evaluation plan으로 검증한다.
- 위 연결 시험에서 Kit 생산자와 train_start 실행만 대역이며, materialize·승인 검사·launcher argv는 실제 함수다. 실물 재학습 checkpoint/기준선이 없는 상태를 실기동 PASS로 보고하지 않는다.
- 돌연변이 5개: done 회차 검사, GPU busy 거절, PASS 조건, measurement SHA, 실제 마찰 readback 각각 삭제 시 시험 실패. `/home/jay/mai/tmp/verifier-lx/remeasure-1112/mutations.json`.
- CPU 결과: 새 시험 23개 포함, 직접 연결 회귀 **93 passed in 75.80s**. pyflakes 오류 0.
- 회귀 원출력: `/home/jay/mai/tmp/verifier-lx/remeasure-1112/regression.log`. 새 시험 외 source evidence·launcher·split evaluator·calibration materialize의 직접 연결 시험만 실행.

## 실제 plan의 뒤 단계 dry 호출

원자료: `/home/jay/mai/tmp/verifier-lx/remeasure-1112/dry-matrix/dry-matrix.json`. 실제 통합 prep/approvals로 단계별 validator, materialize, launcher.build(dry_run=True), adapter registry를 호출했다. 아직 없는 부모·관문·기준선 파일을 가짜 PASS로 채우지 않았다. 따라서 아래는 CPU 경로의 첫 거절이며 Kit 예행이 아니다.

| 단계 | 승인 검사·launcher | materialize | 출구 판정 |
|---|---|---|---|
| E1F | parent SHA 미기입으로 거절 | 실측 evidence 파일 없음 | flag_two_window 등록됨 |
| E2 | parent SHA 미기입으로 거절 | 실측 evidence 파일 없음 | exit_judge 미선언, adapter None |
| E3 | 동일 | 동일 | 동일 |
| E4 | 동일 | 동일 | 동일 |
| E5 | 동일 | 동일 | 동일 |
| M | source contract 미완료·부모 없음 | disabled라 거절 | 출구 없음 |
| E6a | parent SHA 미기입으로 거절 | 실측 evidence 파일 없음 | exit_judge 미선언, adapter None |
| E6b | 동일 | 동일 | 동일 |

부모 null은 앞 단계가 아직 끝나지 않았으므로 채워야 할 실측 경계다. 출구 판정 미선언과 M 비활성은 실측이 생겨도 저절로 풀리지 않는 구현 공백이다.

추가 확인: `ex42_stage_launcher.p1_argv`가 다음 단계 launcher/queue/dispatch 인자를 넣지 않아 PASS여도 `_hand_off`가 no_launcher가 된다. `materializer_from_env`의 BUDGET_USED는 고정 환경값이며, 단계별 evidence 생산자도 필요하다. lead가 이 세 항목을 다음 별도 PR로 배정했다. 또한 E1F 별도 연장 보호는 앞 초안 #723이 통합돼야 한다. 이 PR은 승인 범위를 바꾸지 않는다.

## 운영자가 준비할 실행 입력

검토·병합 뒤 **잠근 통합 평가 사본**에서 준비한다. 오래 도는 평가 중 작업 worktree의 HEAD를 바꾸면 request 검사가 거절하므로 개발 worktree에서 장시간 실행하지 않는다.

1. `launch-env.json`에 실제 `GPU_JOBS_QUEUE`, `EX42_MAIN_ROOT`, `EX42_SOURCE_REF`, `EX42_MESH_DIR`, `EX42_MESH_SHA256`를 넣는다. 민감한 환경 전체를 복사하지 않는다. 이후 사슬용 설정은 후속 연결 PR에서 공급한다.
2. `--prepare`로 새 request를 만들고, 재학습 1000회 run이 실제 생성되면 `--bind`로 run과 실제 torchrun 로그를 고정한다. 마지막 checkpoint SHA는 아직 없으므로 done 때 manifest와 파일에서 고정한다. 바인딩에 optional expected_checkpoint_sha256를 넣으면 그것도 대조한다.
3. 아래 실행 명령은 `--execute`가 있으므로 **지금 실행하지 않았다**. GPU 작업을 시작할 운영자가 사용한다.

```bash
# 잠근 통합 사본의 루트에서. 경로 변수는 실제 파일을 지정해야 한다.
python -m foothold_s2.scripts.ex42_remeasure --prepare --request "$REQUEST" \
  --plan "$EVAL_PLAN" --approvals "$EVAL_APPROVALS" \
  --parent /mnt/win-d/mai/data/foothold/s2_lab/ex42_main_20261108_123914/main/EX-42-B-stagezero_20261108_123914/model_1000.pt \
  --old-run /home/jay/data/foothold/s2_lab/ex42_main_20261111_114505/main/EX-42-B-E1_20261111_114505 \
  --retrain-binding "$RETRAIN_BINDING" --output "$FRESH_OUTPUT" \
  --mesh-dir /home/jay/data/foothold/s2_lab/ex42_mesh_1111/seed42_E0_c333 \
  --launch-env "$LAUNCH_ENV"
python -m foothold_s2.scripts.ex42_remeasure --bind --request "$RETRAIN_BINDING" \
  --run "$ACTUAL_RETRAIN_1000_RUN" --training-log "$ACTUAL_TORCHRUN_LOG"
python -m foothold_s2.scripts.ex42_remeasure --request "$REQUEST"       # CPU preview
python -m foothold_s2.scripts.ex42_remeasure --request "$REQUEST" --execute --wait
```

Python은 `/home/jay/miniforge3/envs/isaac311/bin/python`. `--wait`는 바인딩/학습 done을 기다린다. done 이후 GPU 점유가 남으면 시작 거절 영수증을 쓰며 강제 종료하거나 남의 표식을 지우지 않는다.
