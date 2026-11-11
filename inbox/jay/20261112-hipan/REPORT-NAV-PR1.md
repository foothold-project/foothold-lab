> 분류: B/항법 · 구현 보고 (HiPAN 상위 PR-1 하위 접점과 명령 공간)
> 작성: sonnet-code-lx · 2026-11-12 01:3x
> 근거: PLAN-HIPAN-V2.md §4 · §7 (feature/fable-25a-jay eb37e668) · 통합 7b43c055 코드 줄 (`eval/adapters.py` · `eval/ex41_eval_loader.py` · `models/start_perception.py` · `curriculum/continuous.py` · `curriculum/ex42-prep.yaml`)
> 요지: `nav/lower_adapter.py` (M1) 와 `nav/command_space.py` (M2) 를 계획 계약대로 만들었다. 하위는 평가기 경로 (`load_checkpoint_for_eval` · `load_s2_runner` · `S2Policy`) 를 그대로 부르고, 명령 슬롯은 `ex42-prep.yaml` 에서 읽는다. CPU 시험 18건, 변이 9개 모두 잡힘. Kit · GPU 안 씀.
> 상태: 초안 · 병합 전 · 가정은 표시

## 한 것

- `lower_adapter.py`: `prepare(env_cfg, checkpoint, expected_sha256)` (gym.make 전 · sha 검사 + 평가 경계 준비 · 98 입력 · `ex41_pose_commands` 표지 검사), `LowerPolicy.load(checkpoint, env, device, map_mode, ...)` · `.capabilities` · `.act(obs)` · `.reset(dones)`, `apply_command(term, cmd5, stand, pose_active)` (평가기와 같은 방식으로 `vel_command_b[:, :3]` · `stand` 덮어쓰기, heading · 깃발 모드면 거절), `tracking_error`. 거절: actor 98 아님 · 표지 없음 · sha 불일치 · dt 0.02 아님 · map_mode 가 `eval_gt` · `eval_pred` 가 아님 (저장본 force_gt 에 안 기댐).
- `command_space.py`: 슬롯 13 개를 `stage_zero.shares` · `ranges` 에서 읽음 (숫자 재입력 없음, 부호 규칙은 `continuous.py` W55 검사와 같음). 방식 셋 `clip` (기본) · `project` · `slot`, 5 스텝 유지, vx 상한 1.0, 자세 스위치, 정지 표지 (문턱 0.05), 값 고침 표지, 적용 명령 되돌림.

## 시험 18건 (답을 아는 입력 · 변이 9개 확인)

- 수계산: 계획 예 (0.7, 0.1, 0.3) 는 clip 에서 그대로, project 에서 (0.7, 0, 0.3) (walk_left 거리 0.01 대 forward 0.10 · diag_fwd_left 0.11), slot 방식 walk_left 크기 (0.5, 0.9) 는 (0.55, 0, 0.92).
- 5 스텝 유지: 틱 열 [T F F F F T F F F F T], 값 [0.1 x5, 0.6 x5, 1.0].
- 실제 이름 대조 (AST): `S2Policy.__init__ (runner n z_mode act_mode map_mode)` · `reset(dones)` · `load_s2_runner (env train_cfg checkpoint device expect, *, checkpoint_state)` · `load_checkpoint_for_eval (env_cfg checkpoint)` · 평가기 소스의 `vel_command_b` · `stand` · `heading` · `is_flag_env`. 가짜 정책의 서명이 실제와 같은지도 `inspect` 로 대조.
- 변이: 유지 주기 · 좌우 부호 · vx 상한 · 자세 스위치 · 정지 처리 · dt 검사 · 영수증 sha 검사 · map_mode 전달 · stand 쓰기. 모두 시험이 잡음.

## 하위 지각 추정 51 칸 (계획 §7 PR-1 해야 할 것 4)

`models/start_perception.py:39` `EST_DIM = Z_DIM + V_DIM + ZF_DIM + ZB_DIM` (16 + 3 + 16 + 16) · 연결 순서 `:355` `torch.cat([z, out["v"], out["zf"], out["zb"]], -1)`.

| 칸 | 이름 | 뜻 | 줄 |
|---|---|---|---|
| 0:16 | z | domain latent (mu 에서 평균 또는 표집) | :355 |
| 16:19 | v | 몸 속도 추정 (3) | :355 · 손실 `:402` base_vel 과 MSE |
| 19:35 | zf | 발 지도 latent | :355 |
| 35:51 | zb | 몸 지도 latent | :355 |

- 상위 student 의 「운동 상태 추정」 중 몸 속도는 v (16:19) 에서 얻을 수 있다. 높이 · roll 은 51 칸에 없다 (계획 §6.3 의 가정 그대로: roll 은 IMU 중력 투영, 높이는 복원 지도).
- 관찰 (미확인): `runners/start_runner.py` `_est_in` 의 `oracle_vel` 모드는 `out[..., :3] = v` 로 est 의 앞 3 칸을 덮는데, 연결 순서상 앞 3 칸은 z 이고 v 는 16:19 다. 이 모드가 쓰인 실험의 의도와 다른지는 보지 않았다. 이 PR 은 건드리지 않는다.

## 아직 · 미확인

- `eval_gt` 로 돌릴 때 하위 depth 카메라 (60 x 60) 를 환경에서 뺄 수 있는가 (계획 §4.1 확인 항목): 코드상 `S2Policy.__call__` 이 `_split` 으로 depth 를 꺼내므로 (`adapters.py:465~472`) 카메라를 빼면 모양이 달라진다. 실제로 뺄 수 있는지는 Kit 에서 확인해야 한다 (G2).
- `LowerPolicy.load` 는 실제 runner · env 로 돌려 본 적 없음 (가짜로만). 영수증 꼴 (`stage_id` · `checkpoint_sha256` · `passed`) 은 가정 (verifier 와 맞출 것).
- 명령 공간 방식 선택은 계획 §9 물음 1 (G1 측정 뒤). 기본 clip.
