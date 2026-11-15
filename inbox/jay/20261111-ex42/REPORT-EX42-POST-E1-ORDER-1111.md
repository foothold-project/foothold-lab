# EX-42 E1 종료 뒤 사슬 순서
> 분류: C/운영 · 자동화 · 깃 · 일정
> 작성: runner-lx · 2026-11-11 17:24 KST
> 근거: lead-lx 17:03 · 17:06 · 17:08 · 17:16 지시, #688 통합 c9018296, scripter #691 CLI, verifier #690 CLI 제안
> 요지: E1 P1 직렬 경계, W09/W08, E1F 증거 생성, 재핀과 기동 순서를 고정
> 상태: 확인됨 · 실행 연결은 미완

## 변경

`foothold_s2/scripts/ex42_post_e1_gpu_chain.py` 일정은 다음 순서로 표현한다.

1. m250 → m500 → m750 → m1000 순서로 P1 네 경계를 직렬 평가한다. 각 저장본은 manifest SHA로 확인하고 각 한 경계 평가는 `cuda:1`과 `cuda:0` 두 장에 분할한다. 다음 경계는 직전 경계의 완료 영수증 뒤에 시작한다.
2. 네 평가 완료 후 m1000 `p1_score.json`을 `check_e1_gate`로 판정한다.
3. PASS이면 #691 `ex42_flag_baseline_chain --devices cuda:0,cuda:1` 한 명령으로 W09/W08 기준선을 실행한다. 장치별 작업군은 내부 순차이며 전체 여섯 회 receipt가 complete 되기 전에는 다음 단계로 가지 않는다.
4. W09/W08 chain receipt가 complete일 때 #676 `ex42_e1_boundary_chain --materialize-only --chain-receipt <run>/eval/e1-p1-chain-<E1 source HEAD 12자>.json --w09-baseline <run>/eval/w09-w08/w09_baseline.json`으로 `eval/materialize/E1F-stage-evidence.json`을 만든다. P1 chain receipt와 W09/W08 receipt는 별개이며 둘 다 필요하다. P1 receipt의 12자 접두는 E1 launch HEAD가 아니라 `--fixed-repo`의 현재 `git rev-parse HEAD`에서 만든다. `--p1-chain-receipt` 명시 입력도 지원한다. 이 evidence 생성이 성공한 뒤에만 #690 `ex42_stage_materialize --materialize-only --flag-chain`으로 calibration SHA를 고정하고 `launch_env`를 받는다.
5. materialization이 끝난 뒤에만 `ex42_stage_launcher`가 E1F 다음 단계 진입을 허용한다. 학습은 `cuda:0`, torchrun 두 rank다.

E1 gate가 HOLD 또는 FAIL이면 W09/W08, materialize, E1F를 건너뛰고 알림만 남긴다. E1 연장은 lead 승인 전에는 시작하지 않는다. 같은 시점에 GPU 작업을 겹치지 않도록 각 단계의 완료 receipt가 다음 단계의 선행 조건이다.

## 확인과 미해결

- 병합 확인: #690은 `011ca615`, #691은 통합 `1dc85098`에 포함. 작업 사본에는 둘 다 병합했으며 후속 코드 변경은 별도 커밋한다.
- CPU: `test_ex42_post_e1_gpu_chain_cpu.py` 및 `test_ex42_flag_baseline_chain_cpu.py`, 12 passed. #690/#691이 병합된 상태를 반영해 옛 미병합 blocker 기대값을 제거했다. Reviewer 8b0847b3 v0.2/v0.3 지적을 시험으로 고정: E1F `--chain-receipt`는 P1 사슬 영수증이며 그 이름의 12자는 사슬 실행 고정 저장소 `git rev-parse HEAD`에서 온다. `--p1-chain-receipt` override도 지원한다. `--w09-baseline`은 W09 산출물이며 두 경로를 혼동하지 않는다.
- 실제 입력 dry preflight: `/home/jay/mai/wt/foothold-lab/ex42-launch-b379eb98` HEAD `b379eb98a1f3d0a343bb1caa2551b03410b076fc`; 실제 E1 run `/home/jay/data/foothold/s2_lab/ex42_main_20261111_114505/main/EX-42-B-E1_20261111_114505`; rank 로그 `/home/jay/mai/tmp/runner/E1_20261111_114505/torchrun.stdout.log`; preflight JSON `/home/jay/mai/tmp/runner/e1-post-plan-preflight.json`, rc 0, source HEAD와 startup plan SHA가 E1 manifest/receipt에 일치. actual E1 source HEAD에서 예상한 P1 receipt 경로는 사전검사에서 `--fixed-repo` HEAD로부터 P1 receipt 경로가 파생되고 W09 receipt `eval/w09-w08/chain_receipt.json`과 분리됨을 확인. 커밋 후 고정 checkout에서도 같은 HEAD 기반 규칙이 적용된다.
- dry 시점 manifest는 `completed_updates=850`; m250/500/750 저장본과 SHA는 있으나 m1000, 네 P1 결과, W09 baseline 및 chain receipt는 아직 없다. 그러므로 전 단계 `--materialize-only` 실행이나 E1F evidence 생성은 미실행이며, 출력 상태는 blocked 그대로다. E1 종료 뒤 실제 산출물이 도착하면 그때 evidence command를 실행한다.
- GPU, Kit, live queue 미사용. 계획은 대기열을 변경하지 않는다.
