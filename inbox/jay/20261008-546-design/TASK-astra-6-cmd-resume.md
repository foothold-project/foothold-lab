> 분류: 검증 의뢰 (ASTRA 6)
> 작성: 오흥재 (lead 세션 · Claude 작성) · 2026-10-11
> 근거: 팀장 10/10 「ASTRA 와 Top-down 으로 로컬 실험」 · `eval-cmd-resume/CMD-RESUME.md` · `VERIFY-astra-4.md` 5절 · `DESIGN-astra-rl-topdown.md` 4절 G1 · 5절
> 요지: 학습 명령의 약 20 % 가 +상한 대각선이고 정지 명령은 0 % 다. resume 은 가중치와 Adam 만 되살린다. G1 · P1 을 E1 부모에서 가르는 방법과 명령 분포 개입의 자리를 정한다
> 상태: 의뢰

# ASTRA 의뢰 6 · 명령 분포와 resume 결과를 설계에 반영

**읽기 전용.** 결과는 `inbox/jay/20261008-546-design/VERIFY-astra-6.md` 새 파일 하나. 커밋 · push 하지 않는다. **컨텍스트가 적으면** `eval-cmd-resume/CMD-RESUME.md` 의 0절(한눈에)과 lead 재검 절, 그리고 아래 사실만 읽는다.

## 사실 (lead 가 코드에서 확인)

- Isaac Lab `_reset_idx` 는 `command_manager.reset` 뒤에 `episode_length_buf = 0` 을 한다. robot_lab 하한 `remaining_dist / ((max_len - len + 1) * dt)` 는 time-out 직후 분모가 1 step 이라 하한이 상한을 넘고, `sample_disjoint_intervals` 는 그때 `cfg_max` 를 낸다
- 그래서 time-out 뒤 매 episode 첫 5.02 s 동안 명령이 (+상한, +상한) 이다. 학습 시간의 23.4 % (20k 전) · 20.5 % (20k 뒤). 20k 뒤에는 (1.0, 1.0) = 1.41 m/s
- 완전 정지 명령 0 % (만드는 코드 경로 없음) · 0 < |v| < 0.2 는 2.9 % · 1.5 % · fwd01 근처 0.01 %
- resume: 가중치 · 두 Adam 상태만 되살아난다. `common_step_counter` → 명령 범위 · zero 확률 · reward 가중치 schedule 이 처음으로 · 지형 레벨 · CUDA RNG 처음으로 · 알고리즘 lr 1e-3 으로 · iteration 번호 마지막 번호 재사용 · `--max_iterations` 는 추가
- E1 20000 에 그대로 resume 하면: 명령 ±1.0 → ±0.5 · base_height -10 → -1 · lin_vel_z 0 → -2 · 지형 레벨 5.67 → 약 2.5
- 후보 수정 (저장소 밖 실행기에서 resume 직후 counter = (L+1)×24 · lr = optimizer lr · 번호 L+1) 으로 counter · zero 확률 · reward 가중치가 연속 run 과 같아짐 (작은 run 시험). E1 은 지형 레벨과 RNG 를 저장하지 않았다

## 물음

1. **G1 · P1 분기 규약.** E1 부모에서 양군을 가를 때 쓸 resume 규약 (위 후보 수정 채택 여부 · 지형 레벨 규칙 · 새 시드 선언 · 예산 「추가 N iter」 표기). 아니면 부모 분기 대신 처음부터 학습이 나은가.
2. **명령 분포 개입의 자리.** 재현(E1 · E2)은 코드 그대로 둔다. 고친 분포(예: reset 순서만 고침 · 또는 정지 · 저속 명령 비율 지정)를 별도 실험으로 둘 때 한 변수의 정의 · 비교군 · 예산 · 판정. G1 (gap 노출) 보다 먼저인가 나중인가.
3. **이미 낸 결과의 해석 범위.** Q-E1 · QD-E1 의 정지 · 저속 약점, 20499 하락을 이 사실로 다시 쓸 곳.

## 형식

머리 다섯 줄 · em dash 금지 · 확인됨 / 추정 / 미확인 · 판정 한 줄. 팀장 확정 필요 항목을 따로 묶는다.
