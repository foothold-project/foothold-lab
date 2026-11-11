# EX-42 E1 종료 뒤 사슬 순서
> 분류: C/운영 · 자동화 · 깃 · 일정
> 작성: runner-lx · 2026-11-11 17:00 KST
> 근거: lead-lx 17:03 · 17:06 · 17:08 · 17:16 지시, #688 통합 c9018296, scripter #691 CLI, verifier #690 CLI 제안
> 요지: E1 P1 네 경계 뒤 판정, 두 GPU W09/W08, 재핀, E1F 기동 순서를 계획기와 CPU 시험에 고정
> 상태: 확인됨 · 실행 연결은 미완

## 변경

`foothold_s2/scripts/ex42_post_e1_gpu_chain.py` 일정은 다음 순서로 표현한다.

1. E1 P1 m250 · m500 · m750 · m1000 네 평가
2. 네 평가 완료 후 m1000 `p1_score.json`을 `check_e1_gate`로 판정
3. PASS이면 #691 `ex42_flag_baseline_chain --devices cuda:0,cuda:1` 한 명령으로 두 GPU 작업군을 나눈다. GPU0은 W09 seed42와 W08 반복 1·2, GPU1은 W08 반복 3·4·5를 각각 순차 실행한다. 두 작업군은 함께 시작하지만 전체 여섯 회 receipt가 complete 되기 전에는 다음 단계로 가지 않는다.
4. W09/W08 chain receipt가 complete일 때만 verifier CLI를 `--materialize-only --flag-chain`으로 불러 calibration SHA를 고정하고 `launch_env`를 받는다.
5. materialization이 끝난 뒤에만 `ex42_stage_launcher`의 E1F 다음 단계 진입을 허용한다. 학습은 `cuda:0`, torchrun 두 rank다.

E1 gate가 HOLD 또는 FAIL이면 W09/W08, materialize, E1F를 건너뛰고 알림만 남긴다. E1 연장은 lead 승인 전에는 시작하지 않는다. 같은 시점에 GPU 작업을 겹치지 않도록 각 단계의 완료 receipt가 다음 단계의 선행 조건이다.

## 확인과 미해결

- 병합: `c9018296` (#688), 현재 작업 HEAD의 병합 커밋은 `0bc9c5b8`.
- CPU: `test_ex42_post_e1_gpu_chain_cpu.py` 및 `test_ex42_flag_baseline_chain_cpu.py`, 9 passed.
- 구문 확인: 변경된 스크립트와 시험 `py_compile` 통과, `git diff --check` 통과.
- GPU, Kit, live queue 미사용.
- 확인 시점 #691과 verifier #690은 OPEN이다. 계획에는 실제 `--devices cuda:0,cuda:1` 및 `--materialize-only --flag-chain --expected-flag-chain-sha256` argv를 넣었다. 각 PR이 통합되기 전에는 해당 단계가 막힘으로 표시된다.
- 이 파일은 계획기다. live 실행 및 단계 자동 호출은 하지 않는다. 현재 P1 평가와 재핀의 실제 runtime 연결은 미확인이다.
