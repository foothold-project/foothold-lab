# EX-39A · EX-39B CPU 준비 보고

> 분류: A/정책학습 · 학습 · 보상 · 관측 · 파인튜닝
> 작성: 오흥재 · scripter 반영 · 2026-10-29 21:44
> 근거: 팀장 D55 의뢰, EX-38 완료 저장본, E1 보상 비교 문서, 아래 CPU 영수증
> 요지: EX-38 m3001에서 heading만 갈리는 두 판의 고정 코드와 DRY 인자를 준비했다.
> 상태: reviewer · verifier 검토 대기. Kit 실제 env import와 첫 학습은 미실행

## 출발과 고정

- 코드 출발: `45f5bcd9`. EX-39 코드 고정: `1e0eafa9`. A와 B는 서로 다른 detached worktree이나 같은 코드 커밋이다.
- A: `C:\mai\wt\foothold-lab\scripter-ex39a` · B: `C:\mai\wt\foothold-lab\scripter-ex39b`.
- 부모: `C:\Users\AI-WS01\s2_lab\basic_gait_runs\main\EX-38-basic-e1rew_20261029_123840_163180\model_3001.pt`.
- 부모 SHA256: `7ff575f356c27ab6280fa2e01dce40f806bbfdd89d4306ae63c827b3ff16706c`. 완료 manifest, status, checkpoint 이름과 SHA를 `check_parent`가 대조한다.
- A/B 동일 학습 인자의 값 차이는 `run_name`과 `basic_ex39_arm`만이다. DRY에서는 자원 분리 때문에 GPU ordinal과 출력 루트도 다르다. PPO, 지각 학습, 기존 EX-38 보상 5항, 정규화와 지도 선택은 부모를 따른다. `lin_vel_z` 일정 시작점 1501을 유지하므로 m3002에서는 가중치 0이다.
- 새 4개 대각 슬롯을 포함한 명령 비율 합 100%를 검사한다. 전진30, 걸으며 돌기5+5, 제자리10+10, 정지10, 후진12, 옆6+6, 대각 네 방향 각1.5%. 실제 10만 CPU 표본에서 각 슬롯 비율 오차 0.4%p 미만이었다.
- B만 전진 전체의 15%p에 현재 yaw 유지 heading, 제자리 회전 전체의 6%p에 무작위 목표 yaw heading을 적용한다. A는 heading 0. 수정판은 두 arm이 같은 순서로 세 난수 배열을 소비하므로 같은 재추출 일정과 입력에서는 비-heading 명령이 같다. 학습으로 reset 시점이 갈라진 뒤에는 분포만 같다. 기존 `heading_wz`와 `apply_heading` 경로를 사용한다.
- W15 13개 명령과 반전·정지 재출발 sequence의 vx/vy/wz는 EX-39의 실제 슬롯 하나 이상에서 동시에 낼 수 있는 조합이다. 경계값은 후진 -1.0과 대각 vy 0.5이며, 연속 분포에서 정확히 뽑힐 확률은 0이다.
- 공통 보상 추가: thigh/calf 기본 자세 L1 -0.01은 E1 `joint_pos_penalty_l1`의 `stand_still_scale=1` 동등식이다. 명령이 0이고 4발 모두 1N 초과 접촉이면 +0.1은 팀장 확정값이다. 최대 항 크기 0.1로 추종 항 가중치 1.0/2.0보다 작고, 4발 중 1발만 접촉하면 0이다. `feet_regulation`은 후보로만 둔다.
- D29 판정 제외 구간: 처치 직후 m3002~3301, 추후 재개 직후 30 update를 manifest/launch receipt에 명시했다. 후속 평가 판정 소비기가 이 필드를 실제로 적용하는지는 미확인이다. 평가 시작 전에 연결 확인이 필요하다.
- 기본 1500 update, L0~2, 총 max_iterations 4502. 옵션 3000 update, L0~3, 총 6002. 상한 관문은 정확히 이 조합만 받는다. 마감은 상한이다. 3000회가 EX-38 실측 상한 29초/회로 24시간을 넘을 수 있어, 기존 `max-wall-s=86400`에서는 완료 전 경계 저장 가능성이 있다.

## 검증

- ISAAC/GPU 0회. `isaac311`에서 새 시험 8 PASS, 인접 EX-38·basic gait·W15 시험 포함 32 PASS. SHA와 코드는 `SHA256SUMS-EX39.txt`.
- 반례: 잘못된 부모 SHA, arm, 1500회 초과 max_iterations, 3000회와 L0~2 불일치, 평가 heading 활성은 거절된다. 실제 파서 AST 추출에 launch argv를 통째로 넣고 계약·부모 영수증도 대조했다. `bash -n`, `git diff --check`, 수정된 순수 모듈의 `pyflakes`는 통과했다. `eval_map_modes.py`에는 기존 미사용 import 경고 6건이 남아 있다.
- A 최종 DRY 영수증: `C:\Users\AI-WS01\s2_lab\basic_gait_runs\ex39a_dry\receipts\ex39\A_20261029_214225_994906\launch_receipt.json`. B: `C:\Users\AI-WS01\s2_lab\basic_gait_runs\ex39b_dry\receipts\ex39\B_20261029_214254_994948\launch_receipt.json`. 각 `prestart.json`은 `prestart_pass`, `source_git_clean=true`, arm과 4502가 맞으며 `run.log`가 없다.
- 평가 코드가 고정 명령 전에 heading을 끄고, 매 step 전후 활성 heading을 거절하도록 했다. CPU 반례는 통과했다. 실제 env에서의 검사는 Kit 기동이 금지되어 아직 미확인이다.
- 별도 bare `isaac311`에서 `FootholdS2SBEnvCfg` 직접 import는 `ModuleNotFoundError: pxr`로 실패한다. 따라서 이번 DRY의 env import 범위는 순수 모듈 import와 실제 학습 parser/계약에 한정된다. Kit가 필요한 cfg import와 실제 보상 term 등록은 lead의 짧은 Kit 확인 전까지 합격으로 표시하지 않는다.

## lead가 정할 것

1. 공통 정지 접촉 보상 +0.1과 기본 1500회 L0~2, 마감 상한 10/30 15:00 KST는 팀장이 확정했다.
2. reviewer · verifier가 코드 고정본과 위 미확인 경계를 보고, lead가 별도 Kit 짧은 확인으로 env cfg import, 보상 term 4발 선택, 평가 heading off를 검사한다.
3. 판정 소비기에 m3002~3301과 재개 직후 30 update 제외를 연결한다. 현재는 영수증/manifest 기록까지만 확인됐다.

## 예상 시간

EX-38 이어 학습 실측 24~29초/회 기준, 1500회는 10~12.1시간, 3000회는 20~24.2시간이다. EX-39의 실제 속도는 미측정이며, 시작/종료와 평가 시간은 이 계산에 없다.
