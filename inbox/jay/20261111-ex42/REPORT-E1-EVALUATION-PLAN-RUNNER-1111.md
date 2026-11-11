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

## 평가기 연결 상태

scripter PR #697 HEAD `9d0a09cf4fe980304369763bddcdb3d55540e701`에 `ex42_eval_once --evaluation-plan`과 P1 영수증의 `evaluation_plan {path, sha256}` 변경이 올라와 있고, scripter 보고는 67 passed 및 D44 planned 6입니다. 이 evaluator 변경은 아직 통합 branch나 잠긴 23ddf076 checkout에 들어오지 않았습니다. 따라서 이 보고의 argv/preflight는 runner 호출부의 전달 확인이며, 실제 고정 사본에서 `--evaluation-plan` evaluator 실행은 통합 및 새 lock checkout 뒤 별도 확인이 필요합니다.

## 시험

- `test_ex42_e1_boundary_queue_cpu.py`: 10 passed (1.33 s)
- `git diff --check`: 통과
- GPU/Kit 평가 및 실제 queue 등록: 미실행
