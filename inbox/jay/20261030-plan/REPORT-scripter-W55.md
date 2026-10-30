# W55 연속 커리큘럼 CPU 구현 인계

> 분류: A/정책학습 · 학습 · 보상 · 관측 · 파인튜닝
> 작성: 오흥재 (scripter 반영) · 2026-10-30
> 근거: `w55_req.md`, `CURRICULUM-GATES.md` §1b.8, `WORKLIST.md` D59 · D61 · D65 · D66, S-B10 m1500 실제 저장본
> 요지: 한 runner 안에서 B1 · B2 · B3 · T0를 넘기는 실행 경로와 CPU 관문을 분리 worktree에 고정했다.
> 상태: CPU 준비 완료 · Kit 실기동 미확인 · EX40 학습 미시작

## 범위와 구현

작업 사본은 `C:\mai\wt\foothold-lab\scripter-w55`다. 코드 커밋은 `68a4edad`와 후속 확인기 커밋 `ef810770`이며 push하지 않았다. 실행 중인 `scripter-ex39a`와 `scripter-ex39b`는 읽거나 수정하지 않았다.

| 단계 | 시작 update | 실제 설정 |
|---|---:|---|
| B1 | 1501 | S-B10 m1500 출발, EX38 보상 네 항과 EX39 정지 보상 두 항, 기본 보행 9 슬롯 |
| B2 | 3001 | EX39 대각 네 슬롯 추가, 범위 확대, 비율 재배분. heading A/B는 결과 전 미정이므로 시작 인자로 명시해야 함 |
| B3 | 4501 | 걸으며 돌기 15%, 전진 25%, 회전 하한 0.3, 저속 전진 전진 슬롯의 20% |
| T0 | 5501 | `force_gt=True`에서 `False`로 전환, 기존 AdaSmpl의 복원 지도 선택 가능, 500 update |

`curriculum/ex40.yaml` 한 장에 단계, 경계, 덧붙일 항목, 비율, 범위를 둔다. `Plan`은 슬롯과 보상의 중복 추가, 범위 축소, 비율 합계 오류를 거절한다. 단계는 update 시작에서 바뀌지만 각 환경의 명령 단계는 다음 개별 reset 때만 바뀐다. 기존 에피소드는 그 단계의 명령 분포로 계속 재추출한다. T0에서도 기존 에피소드의 지도 선택은 유지되고 다음 reset의 AdaSmpl 선택부터 달라진다. 따라서 T0의 첫 reset이 모두 복원 지도를 소비한다고 주장하지 않는다.

단계 사건은 `stage_log.jsonl`에 회차, 이전과 다음 단계, 새 슬롯 · 비율 · 범위 · 지도 정책, 이전 완료 저장본 SHA를 기록한다. 외부 점수표 `foothold-w55-score/1`은 저장본 경계에서 SHA를 대조한다. EX40은 고정 회차 승급이고 점수표는 `shadow_gate`로만 남기며 승급시키지 않는다. 저장본에는 단계 · 환경별 단계 · 점수표 처리 상태 · 표와 arm 및 smoke 경계의 결합 SHA가 들어간다. 다른 arm이나 smoke에서 본판으로 재개하면 거절한다. 재개는 새 물리 에피소드이며 같은 궤적의 물리 재개가 아니다.

## CPU 증거

- 실제 부모 `C:\mai\wt\foothold-lab\impl-sb\logs\rsl_rl\foothold_s2_sb\2026-10-26_01-17-47_sb-main\model_1500.pt`의 SHA256은 `4d987818c7e25b89e77b7541feca3ddabedd444c5b20651eb29f3681da040d9d`, 완료 회차는 1500으로 검사했다.
- 새 정답 및 변이 시험 `test_w55_continuous_cpu.py`: 7 PASS. 비율 100%, 범위 축소 거절, 단계별 명령 계약, 부분 reset, shadow 점수표, 실제 부모와 실제 파서, smoke 확인기 변이를 포함한다.
- 관련 EX39 · 기본 보행 시험을 합쳐 `23 passed, 2 skipped, 1 deselected`. 제외한 옛 시험 `test_scratch_receipt_and_wrong_kind_or_share_rejected`는 2026-10-29 종료 시각을 하드코딩하여 오늘 실행에서는 `deadline has already passed`로 실패한다. EX40 수정에 따른 실패가 아니다.
- 변경 Python의 `ruff check --select F` 0건, `python -m pyflakes` 0건, `git diff --check` 통과. 실제 `isaac311`의 `rsl-rl-lib 3.1.2` 파서와 모듈 import를 통과했다.
- 실제 부모 파일과 실제 기동 인자를 사용한 `LIVE=0` shell DRY 두 건이 `prestart_pass`, `source_git_clean=true`로 되읽기 통과했다. Smoke A는 1511 총회차와 경계 1503 · 1506 · 1509, 본판 B는 6001 총회차와 경계 3001 · 4501 · 5501이었다. 영수증: `C:\Users\AI-WS01\s2_lab\ex40\w55_smoke_cpu_dry\receipts\ex40\A_smoke_20261030_121701_1060966\`와 `C:\Users\AI-WS01\s2_lab\ex40\w55_main_cpu_dry\receipts\ex40\B_main_20261030_121725_1061001\`.

## Kit 확인과 남은 결정

`foothold_s2/run_ex40.sh`는 기본 DRY이며 lead가 `LIVE=1`을 지정해야만 Kit를 연다. 예행은 부모와 같은 3072 env를 쓴다. 저장본의 환경 상태가 3072행이므로 8 env로 줄이는 예행은 현재 경로에 넣지 않았다. `ex40_kit_smoke.py`는 실제 `manifest.json`, `params/env.yaml`, 시작 영수증, 단계 사건, 개별 reset 적용, `model_1510.pt`와 끝 상태의 SHA를 확인한다. **실제 Kit 예행은 아직 실행하지 않았다.** R6 · M15에 따른 실기동 확인은 lead 몫이다.

R20에 따라 가짜 부모가 아니라 실제 파일과 실제 파서로 DRY를 돌렸다. M02에 따라 실행 중 사본을 수정하지 않았다. M76에 따라 환경 YAML과 실제 단계 로그 확인을 Kit smoke 관문에 두었다. M77에 따라 본판 종료 시각은 29초/update 관측 상한에 24시간 여유가 없으면 시작 전에 거절하며, 첫 50 update의 실제 속도 재측정은 남아 있다. R6의 GPU 실기동은 이 CPU 작업에서 미확인이다.

lead가 정할 것: EX39 결과에 따른 B2 heading arm A/B, EX40 실제 예행과 본판 기동 시각. `--end-by`는 그 시각에 맞춰 다시 정해야 한다. T0의 `force_gt=False`는 AdaSmpl 혼합 선택이며 강제 100% 복원 지도 사용은 아니다.

코드 SHA256 목록은 `W55-SHA256SUMS.txt`에 있다.
