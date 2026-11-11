(18:15)
> 분류: C/운영 · 인프라 · 자동화 · 깃 · 웹 · 예산 · 일정
> 작성: runner-lx · 2026-11-11
> 근거: 실제 E1 m1000 실행 자료, 잠긴 checkout 23ddf076, source/evaluation plan
> 요지: E1 경계 사슬에서 실행 계획과 평가 정책 계획을 분리하고 5단계 CPU 사전검사를 수행
> 상태: 확인됨 · 실제 Kit 평가 미실행

# E1 평가 계획 분리와 사전검사

## 변경

`ex42_e1_boundary_queue.build_queue_plan()`은 D44 계약을 source `--p1-plan`이 아니라 별도 `evaluation_plan.document`에서 읽습니다. P1 evaluator argv에 `--evaluation-plan <locked checkout>/foothold_s2/curriculum/ex42-prep.yaml`을 넣고, 실행 신원 인자 `--p1-plan`은 E1 기동 사본 경로로 유지합니다. 회귀시험은 평가 계획에 고유 값을 넣어 D44 검사기가 그 문서를 받는지, 네 P1 argv가 모두 고정 평가 계획 경로를 전달하는지 확인합니다.

## 입력 고정

| 입력 | 확인값 |
|---|---|
| 실제 잠긴 사본 | `/home/jay/mai/wt/foothold-lab/ex42-post-e1-23ddf076`, HEAD `23ddf0762d66eb2a8f60e312950516b378f9ea6b`, `lock_checkout.py` 결과 894 tracked · 0 writable |
| E1 source plan | `/home/jay/mai/wt/foothold-lab/ex42-launch-b379eb98/foothold_s2/curriculum/ex42-prep.yaml`, SHA-256 `e542961d9c65a588ae893b81a8d07d39cd66ca068f2f118410c3e2d1d7a2d982` |
| 고정 evaluation plan | 잠긴 사본의 `foothold_s2/curriculum/ex42-prep.yaml`, SHA-256 `a2007c8f00fd1a0b5cab8aeaf425e08cfdd8b6e0401d858b39d680bc9a6e45fa` |
| 실제 E1 run | `/home/jay/data/foothold/s2_lab/ex42_main_20261111_114505/main/EX-42-B-E1_20261111_114505`, manifest completed_updates=1000, `model_1000.pt` SHA를 manifest와 대조 |
| 실제 기록 | `/home/jay/mai/tmp/runner/E1_20261111_114505/torchrun.stdout.log`; 실제 메시 `/home/jay/data/foothold/s2_lab/ex42_mesh_1111/seed42_E0_c333`, SHA `88197b3adfdde327edc633c025c6ad9aa690ea59aa7df5d51d548f7f56c12a95` |

## 다섯 단계 사전검사

CPU 스크립트 출력: `/mnt/win-d/mai/tmp/runner/ex42-e1-five-preflight-181102/preflight.json`. 실행은 `isaac311`, GPU/Kit/live queue 쓰기 없이 수행했습니다.

| 단계 | 실제 검사 | 결과 |
|---|---|---|
| P1 경계 4건 | 실제 E1 m1000 manifest/checkpoint, source/evaluation plan, 고정 checkout 잠금 검사로 m250·500·750·1000 항목 구성 | rc 0 · 4/4 argv에 고정 evaluation-plan SHA 경로 · queue_mutated=false |
| E1 관문 계약 | 실제 m1000 SHA를 synthetic 측정 영수증 envelope와 대조 | rc 0 · checkpoint identity 통과 · 합성 판정자료 |
| W09/W08 | 실제 모델·메시·평가 계획으로 dry command chain 생성 | rc 0 · 6 rounds · synthetic gate · 실행/출력 없음 |
| E1F evidence | 실제 manifest·rank exposure 로그·메시로 evidence builder 실행 | rc 0 · applied cap 5 · gate/W09 baseline만 synthetic |
| E1F materialize/launcher | synthetic gate/evidence를 scratch에서 materialize하고 launcher dry argv 생성 | rc 0 · E1F 750 update · cuda:0 · publish/launch 없음 |

뒤 네 단계의 PASS 모양 gate, 측정, W09 baseline/evidence는 scratch 합성 fixture입니다. 실제 E1 P1 점수 및 W09/W08 측정이 아니며, 실제 점수 판정이나 E1F 출발 증거로 사용하지 않습니다. 실제 E1에는 현재 boundary evaluation receipt와 eval 결과 디렉터리가 없어 후속 산출물을 실제 기록으로 검증할 수 없습니다.

## 통합 고정 사본 재검사

PR #697 통합 뒤 runner 변경을 포함한 commit `31718e26a2e947549b70f2d8197396d48cc0e1d9`를 새 detached 사본 `/home/jay/mai/wt/foothold-lab/ex42-e1-plan-31718e26`에 체크아웃하고 `lock_checkout.py lock`을 실행했습니다. 결과는 `894 changed · 894 tracked · 0 writable`입니다. 이 사본에서 실제 E1 run·source plan·evaluation plan·mesh를 사용해 위 다섯 단계 preflight를 다시 돌려 각 rc 0을 확인했습니다.

같은 고정 사본의 `foothold_s2.ex42_eval_once`에 m1000 체크포인트와 manifest SHA, c333 mesh SHA, source `--p1-plan`, 승인 파일, 고정 `--evaluation-plan`, `--p1-stage-id E1`을 넣어 execute 없는 plan 모드로 호출했습니다. rc 0, score config와 evaluation plan 경로가 모두 고정 사본 아래를 가리키고, evaluation SHA `a2007c8f00fd1a0b5cab8aeaf425e08cfdd8b6e0401d858b39d680bc9a6e45fa`, D44 planned judge 6 · record 3을 반환했습니다. 출력 폴더는 생성되지 않았습니다. 출력: `/mnt/win-d/mai/tmp/runner/ex42-e1-five-preflight-31718e26-rerun/eval-plan.json`.

다섯 단계의 gate·W09/W08·E1F 증거는 scratch synthetic fixture를 사용하는 CPU 계약 검사이므로 실제 점수 판정이 아닙니다. 실제 P1 실행과 평가 수치는 아직 없으며, GPU/Kit/live queue는 사용하지 않았습니다.

## 시험

- `test_ex42_e1_boundary_queue_cpu.py`: 10 passed (1.33 s)
- 통합 사본 시험 `test_ex42_e1_boundary_queue_cpu.py`, `test_ex42_e1_judge_cpu.py`, `test_ex42_e1f_flag_cpu.py`, `test_ex42_split_eval_cpu.py`: 77 passed (39.99 s)
- `git diff --check`: 통과
- GPU/Kit 평가 및 실제 queue 등록: 미실행
