> 분류: A/정책학습 · 학습 · 보상 · 관측 · 파인튜닝
> 작성: 오흥재 (scripter 반영) · 2026-10-30
> 근거: D68 13:4x · S-B10 저장 설정 `env.yaml` / `agent.yaml` · 코드 커밋 `78858c0d` · CPU 시험과 DRY 영수증
> 요지: EX-40을 부모 없이 m0~m6000 한 프로세스로 시작하도록 B0·런처·관문을 바꿨다.
> 상태: CPU 준비 완료 · 새 scratch Kit 검증 전 · 정지 보상과 B2 heading 결정 대기

# EX-40 D68 scratch B0 준비

## 변경과 근거

기존 W55 런처와 관문은 S-B10 `model_1500.pt`의 SHA와 완료 회차를 필수로 읽었다. D68 요구와 맞지 않아 새 detached worktree `C:/mai/wt/foothold-lab/scripter-ex40-d68`에서 부모 인자를 제거했다. 실행 중인 `scripter-w55-h1`과 그 안의 untracked Kit 산출은 그대로 두었다.

| 항목 | S-B10 sb-main 저장 원자료 | D68 B0 코드 |
|---|---|---|
| 출발 | `agent.yaml`: seed 42 · 3072 env · 24 step · resume false | 부모 없음 · m0 · 6001 iterations(마지막 m6000) |
| 명령 | `env.yaml`: start_mode, 전진 80 % · 제자리 회전 20 %, 재추출 4 s, 명령 seed 0, 시계 흩기 없음 | 기존 W55 정지 몫 10 %를 더해 전진 72 % · 좌 9 % · 우 9 % · 정지 10 %, `vy=0`, 명령 seed 0, clock_scatter off |
| 보상 | track_lin 1.5 · track_ang 0.5 · joint_acc -2.5e-7 · lin_vel_z -2 및 그 밖 저장 항 | B0는 기본 가중치 유지. 새 hip · thigh/calf · 네 발 항을 등록만 하고 가중치 0. B1에서 다섯 항과 lin_vel_z 일정 활성화 |
| 지형 | 생성 10행 × 23열, `terrain_levels`와 `command_range` 켬 | B0는 L0~2 재배치 없음, 저장 설정의 지형 진행 유지 |
| DR | startup 재질 static/dynamic U[0.2,1.2], 64 buckets, make_consistent; base 질량 add [-1,3]; reset pose·joint | 같은 SB task cfg를 사용하고 D68 경로에서 DR를 덮어쓰지 않음 |
| 지도 | force_gt true, p_map_off 0.1 | B0~B3 같은 선택, T0에서 복원 선택 |

저장 원자료의 SHA256은 `env.yaml` `4f5edb6aca03c27a6c9085c76b40772415f1970be6049e1126708b5d12639901`, `agent.yaml` `213b82acc0a8d937de3f85171619e7d20c55612b37033bdeb05c6adff3c06308`이다. 런처와 기동 관문 둘 다 이 두 파일 SHA를 다시 확인한다. B0의 72/9/9/10 분할은 S-B10의 80/20에 기존 W55의 정지 10 %를 더한 **현재 구현 선택**이다. 실제 재추출 난수열이 S-B10과 같다는 뜻은 아니다.

`RslRlVecEnvWrapper.__init__`가 `env.reset()`을 호출하므로 stage runtime을 wrapper 생성 **전에** CommandTerm에 설치했다. 그렇지 않으면 첫 reset 명령이 S-B10 START 방식으로만 생성되어 정지 명령이 m0에서 빠진다. 단계 전환은 m1501 B1, m3001 B2, m4501 B3, m5501 T0이며 같은 runner에서 m6000까지 간다. 보상 가중치는 B1 update 경계에서 전 env에 적용되고 명령 단계는 env별 reset에 적용된다.

## CPU 확인

- `isaac311` Python: `pytest test_w55_continuous_cpu.py test_basic_gait_ex38_cpu.py test_basic_gait_cpu.py -q` → **18 passed**.
- D68 전용 반례: 부모 인자, B0 몫 합 오류, 미결정 네 발 보상 삽입, 단계 범위 축소, B0 명령 오염, 실패 자식, reset 0 env, B0 보상 및 startup DR 변조를 거절. 새 Kit 판독기는 저장 S-B10의 지형 생성기 · curriculum · events를 실제 `params/env.yaml`과 대조하도록 했다. 실제 설치 wrapper의 첫 reset 순서도 소스와 대조했다.
- 바뀐 Python에 `python -m pyflakes` 0건, `ruff check --select F` 0건, `git diff --check` 0건.
- LIVE=0 실제 `run_ex40.sh` A·B 각각 rc 0. 영수증 A: `C:/Users/AI-WS01/s2_lab/ex40/d68_dry_20261030_A/receipts/ex40/A_main_20261030_135416_1068051/launch_receipt.json`; B: `C:/Users/AI-WS01/s2_lab/ex40/d68_dry_20261030_B/receipts/ex40/B_main_20261030_135444_1068089/launch_receipt.json`. 최종 코드 고정 `870a2c12`에서 A를 다시 DRY한 영수증은 `C:/Users/AI-WS01/s2_lab/ex40/d68_final_A_20261030/receipts/ex40/A_main_20261030_135735_1068287/launch_receipt.json`이다. `prestart.json`은 실제 `train_sol23f_common.py` 파서, 모듈 import, `source_git_clean=true`, `max_iterations=6001`, `prestart_pass`를 기록했다. 영수증에 `--resume_from` 없음, `start=scratch`, `stand_reward=undecided_disabled`이다.
- 코드·카드 8파일의 SHA는 `EX40-D68-SHA256SUMS.txt`. 최초 고정 커밋 `78858c0d` 뒤 DRY를 실행했고, Kit 판독기의 지형·DR 대조를 후속 고정했다.

## 남은 관문

1. 정지 보상 형태·가중치는 RR 탐침 판독 뒤 결정한다. 현재 네 발 항은 가중치 0으로 비활성이다. B2 heading arm도 최종 결정 전이다. A/B DRY는 선택의 승인이 아니다.
2. B0 실제 Kit `params/env.yaml`, PhysX material readback, 첫 정지 명령, B1 보상 동적 활성화와 T0 지도 선택은 **미확인**이다. 이전 m1500 부모형 W55 Kit PASS를 새 scratch 판의 증거로 쓰지 않는다. 새 scratch 13-update smoke와 실제 첫 50 update 속도가 필요하다.
3. B1 이후 지형은 B0의 S-B10 진행을 이어받는다. 기존 W55의 시작 시 L0~2 고정과 달라졌으므로, 이 차이를 새 실험 조건으로 명시한다. B1에서 별도 L0~2 전환을 요구하면 단계 경계의 env origin·episode reset 계약을 먼저 정해야 한다.
4. 실측 속도 전의 96시간 max-wall과 명시 end-by는 상한이다. m6000 완료 보장은 아니다. 기동은 lead가 별도로 판단한다.
