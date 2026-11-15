> 분류: 검증 · 2 겹째(코드가 설계를 따르나) · S1-a 코드 대 설계
> 작성: fable 세션 (Claude Fable 5.1) · lead 의뢰 20m · 10/20 11:4x
> 근거: 코드 = sonnet-code 사본 `C:/Users/AI-WS01/orca/workspaces/foothold-lab/sonnet-code` 커밋 71d6eac2 의 `foothold_s2/`(HANDOFF-S1.md 포함) · 설계 = 커밋 28114f68 의 13 · 14 · 15 · 16 · 17 · 52 · APPROVED-DIRECTION A~M · 설치 Isaac Lab 2.3.2 `managers/command_manager.py` 152~186 · `managers/reward_manager.py` 150~154 · `envs/mdp/rewards.py` 267~275 · 304~315 · `envs/mdp/terminations.py` 51~57 · `actuators/actuator_pd.py` 268~304 · `isaaclab_assets/robots/unitree.py` 170~177 · `managers/manager_term_cfg.py` 184~191 · `contact_sensor_cfg.py` 45
> 요지: 다섯 항목(명령 생성기 · 지형 열 · 보상 14 항 · 종아리 DCMotor · 관측 크기)은 숫자 · 식이 설계와 같다. 다른 곳 8 건(§2 표). 승인된 차이 넷은 13 · 14 · 15 · 17 · 52 · 18 에 반영했다(§3). 코드는 고치지 않았다
> 상태: 완료 · lead 검토 · 커밋 대기 · 사본 작업 트리에 미커밋 변경 있음(§4)

# VERIFY fable 20m · 코드가 설계를 따르나

## 1. 같은 것 (확인한 자리)

| 항목 | 코드 (71d6eac2) | 설계 (28114f68) |
|---|---|---|
| 자유 속도 표집 | `commands/mixed_core.py` 85~99: \|vx\| · \|vy\| ~ U[0, vmax] 부호 무작위, wz U[−2, 2], 유지 0.9 · 0.75 · 0.5 | 14 §3 40 행 |
| 뽑는 순서 · 비율 | 110~130: 정지 0.1 > 제자리 회전(1,000 회 이후 0.2, wz U[−2, 2]) > heading 플래그 5/12 · 1/3 > 자유 wz | 14 §3.2 69~73 행 · 결정 4 |
| heading 식 | 102~107 · 133~140: wz = clip(0.5 × wrap(ψ* − yaw), ±2), 정지가 우선, 매 스텝 갱신(`mixed_command.py` 139~141) | 14 §3.2 67 행 · §8 148 행 |
| 깃발 (이어진 20 %) | `mixed_command.py` 39 env 번호 % 5, 4 깃발 1 m 간격(`mixed_core.py` 297~302), 4 s 재추출(`s1_env_cfg.py` 69) | 14 §3 41 행 · §8 146 행 |
| 깃발 식 | `mixed_core.py` 187~256: v U[0, 1.0], v < 0.3 → (0, 0, wz U[−1.2, 1.2]), 아니면 방향 × v · wz clip(각, ±1), 0.5 m 도달, 마지막 깃발 2 s 이상 0 | 14 §3 42 행 · 결정 5 |
| 물러나기 상수 | 46~49: 확률(기본 0, 듬성한 지형 판에서 켬) · U[0.1, 0.3] · 2 s · 지난 깃발 ≥ 1 · wz 0 | 14 §3 45 행 · 결정 2(0.3 × 2 s = 0.6 m) |
| 범위 커리큘럼(자유 속도) | 270~295 · `curriculum/terrain_levels_mixed.py` 41~74: 두 추종 보상 에피소드 합 / (가중치 × 20 s) 평균 ≥ 0.8 이면 +0.25, 상한 1.5 · 1.0, wz 고정 | 14 §4 99 · 104 행 |
| 승급 · 강등 | `curriculum/rules.py` 14~46: 깃발 전부 / 절반 미만, 자유 속도 max_dist > 4 m / < 0.5 × ‖Σcmd‖ × 4 × 0.9(스텝 합을 재추출 단위로 환산 `terrain_levels_mixed.py` 20), 명령 합 0 이면 판정 제외 | 14 §5 114~116 행 |
| 지형 열 · 비율 | `terrains/columns.py` 11~34(0.10 · 0.10 · 0.08 · 0.08 · 0.04 · 0.04 · 0.02 / 0.14 · 0.10 · 0.10 · 0.10 · 0.06 · 0.04, 50 열 · S1-a 23 열) · `rough_go2_cfg.py` 20~44(치수 · 8 × 8 · 10 줄 · 경계 20 · 0.1 · 0.005) · `s1_env_cfg.py` 42 초기 레벨 2 | 15 §2 · §3 · §5 |
| p_advance | `terrains/progression.py` 13~14: 0.9 · 1,000 · 8,000(S1-a 미사용) | 15 §5 91~95 행 |
| 보상 14 항 | `rewards/core.py` 10~25 가중치 전부 일치 · `start_rewards.py` 75~93: B 식 = 설치 `track_lin_vel_xy_exp`(std 0.5 → /0.25), 충돌 = `undesired_contacts` 0.1 N(base · thigh · Head), 걸려 넘어짐 4 배, 발 가장자리 0 | 16 §1 · §3 · §5 |
| 종아리 DCMotor | `robots/go2_params.py` 16~19 · `go2_cfg.py` 11~16: hip · thigh 23.5 · 23.5 · 30.0, calf 45.43 · 45.43 · 15.70, Kp 25 · Kd 0.5, `velocity_limit_sim` 미적용 · 토크식 35~50 = 설치 `_clip_effort` | 17 §1 26~31 행 · F-D2 |
| PIE 무작위화 | `s1_env_cfg.py` 120~144: 마찰 0.2~1.2 · 짐 −1~2 kg · 무게중심 ±0.05 · Kp · Kd 0.9~1.1 · 초기 관절 (1.0, 1.0) · push 없음 | 17 §5 |
| 관측 | `s1_env_cfg.py` 82~90: ω 3 · g 3 · cmd 3 · θ 12 · θ̇ 12 · a 12 = 45 + scan 187(격자 1.6 × 1.0 · 0.1 = 17 × 11) = 232; blind 192~200 `history_length` 11 = 현재 + 10 → 495(CircularBuffer 는 현재 관측 포함) ; critic 97~106 = 45 + v 3 + 접촉 4 = 52 | 13 §2 28 · 31 · 32 행 · 52 §2 45 행 |
| PPO | `tasks/agents/s1_ppo_cfg.py`: 24 · 5 · 4 · 1e-3 adaptive · 0.99 · 0.95 · 0.2 · 0.01 · 1.0 · [512, 256, 128] ELU · 6,000 회 · 4096 env | 18 §1 · §2 · 13 §3.1 |

## 2. 다른 곳 (승인된 차이 넷은 뺌)

| # | 항목 | 코드 (71d6eac2) | 설계 (28114f68) | 어느 쪽이 맞나 |
|---|---|---|---|---|
| 1 | 깃발 속도 커리큘럼 없음 | `commands/mixed_core.py` 40 `flag_vmax = 1.0` 고정. 273~295 `RangeCurriculum` 과 `curriculum/terrain_levels_mixed.py` 41~74 는 자유 속도 env 의 vmax_x · vmax_y 만 올림 | 14 §4 표 105 행 「깃발(둘 다) v U[0, 1.0] → U[0, 1.5], 같은 조건 + 그 지형군 레벨 중앙값 ≥ 5」 | **설계**. S1-a 에도 이어진 깃발 env 20 % 가 있어 적용 대상. 코드 보완, 또는 「S1-a 는 깃발 상한 1.0 고정」 으로 문서 명시 → lead 결정 |
| 2 | 깃발 env 의 제자리 회전 구간 제외 | `curriculum/rules.py` 29~39 `judge_flag` 는 깃발 수만 센다(시간 제외 없음) | 14 §5 116 행 「START 식 제자리 회전 구간(v = 0)도 깃발 수 판정에서 그 시간만큼 제외」(가정) | 설계 문구가 횟수 판정에 「시간 제외」 라 구현이 정해지지 않음 → lead 결정(권고: 코드대로 두고 14 §5 를 「깃발 env 는 깃발 수만으로 판정」 으로) |
| 3 | 이어진 깃발 열 위치 | `mixed_core.py` 297~302 `straight_flag_line`: env 원점(칸 가운데)에서 세계 +x 로 1 · 2 · 3 · 4 m. 네 번째 깃발이 칸 경계(x = +4 m) 위 | 14 §3 41 행 · 15 §4 71 행 「칸 가운데를 지나는 직선 깃발 열, 1 m 간격 · 4 m(가정)」 | 문구 모호(가운데를 「지나는」 대 가운데에서 「시작」). 둘 다 가정 → lead 결정(권고: 경계 위 깃발을 피해 0.5 · 1.5 · 2.5 · 3.5 m 또는 문서를 코드대로) |
| 4 | 관측 배율 | `tasks/s1_env_cfg.py` 83~90 PolicyCfg 에 `scale` 없음(Isaac 기본 · 잡음만) · `agents/s1_ppo_cfg.py` 16 `actor_obs_normalization=False` | 13 §2 29 행 「ang_vel 0.25 · dof_vel 0.05 · cmd 2.0 / 0.25(가정)」 · 14 §2 28 행 「배율은 lin 2.0 · ang 0.25(가정)」 | 둘 다 가정. 코드 쪽이 v2 · NVIDIA 와 같은 조건(13 §4 「S1-scan 은 v2 와 같은 관측」) → 권고: 문서를 「배율 없음(Isaac Lab 기본)」 으로, lead 결정 |
| 5 | 종료 조건의 기울기 | `s1_env_cfg.py` 152~153 `mdp.bad_orientation(limit_angle 1.5)` = 투영 중력과 z 축 사이 각(설치 `terminations.py` 51~57) | 17 §7 90 행 「roll 또는 pitch > 1.5 rad(JEPLO 835~847)」 | 둘 다 가정이지만 기하가 다르다(roll 1.2 · pitch 1.2 는 설계로는 생존, 코드로는 종료) → 권고: 문서를 코드(기울기 각 1.5)로, lead 결정 |
| 6 | 17 §9 negative control 값 | `tests/test_go2_model.py`(HANDOFF-S1 33 행): 45.43 × (1 − 15.70 / 30) = 21.655 | 17 §9 103 행 「+21.67」 | **문서 반올림 오기** → 21.66 |
| 7 | 켜짐 비율 로그 · A/B 전환 키 | `rewards/start_rewards.py` 71~93 에 벌점 12 · 13 · 14 켜짐 비율 기록과 추종식 A/B cfg 키 없음(`core.py` 41~43 에 A 식은 있음) | 16 §7 85~86 행 「켜짐 비율을 update 마다 기록 · 방식 A/B 는 cfg 한 줄」 · §4 63 행 | **설계**. 계수와는 무관하나 L1 전 코드 보완 |
| 8 | task 이름 | `tasks/__init__.py` 9 `FootholdS2-Go2-S1a-scan-v0` · `-blind-v0` | 13 §6 98 행 `FootholdS2-Go2-S1-v0` | **코드**(두 판이라 이름 둘) → 문서를 코드대로 |

## 3. 승인된 차이 넷 · 문서에 반영한 자리 (lead 승인 10/20)

| 차이 | 적은 곳 |
|---|---|
| S1-a 23 열(이어진 지형만이라 정수 배정 · 우리 변경) | 15 §2 열 수 행 · §5 열 배정 문단 · §9 L0 열 배정 행 · 52 §2 지형 행 · 18 §6 표 지형 행 |
| critic = o_t + 선속도 3 + 발 접촉 4 = 52(가정) | 13 §2 새 행 「critic 입력 (S1 두 판 공통)」 · 52 §2 관측 행 |
| 14 §9 시험 허용폭 1,000 표본 ± 0.05 + 20 만 표본 ± 0.005 | 14 §9 L0 세 행(자유 속도 · 깃발 · heading) |
| 시스템 지연 = 행동 지연 버퍼 · 모터 세기 = 이득 무작위화와 같은 startup event(둘 다 구현 예정) | 17 §5 두 행 · §9 구현 문단 |

머리 「상태」 줄에 「20m 승인 차이 넷 반영」 을 붙였다(13 · 14 · 15 · 17 · 52). em dash 0.

## 4. 기록 (지적 아님)

- 사본 작업 트리에는 71d6eac2 뒤의 **미커밋 변경**이 있다(10/20 11:4x 확인): `commands/mixed_command.py` · `tasks/mdp_extra.py` · `tasks/s1_env_cfg.py` · `tests/test_kit_names.py` 수정, `tasks/delayed_action.py` 미추적. 내용은 행동 지연 버퍼(하위 스텝 0~3 개)와 `randomize_motor_strength`(DCMotor `effort_limit` · `_saturation_effort` 배율) 추가 = 승인된 차이 넷의 마지막 항목을 구현하는 중. 이 표는 커밋 기준이고 그 변경은 검토하지 않았다.
- HANDOFF-S1.md 34 행 · `robots/go2_params.py` 24 · 30 행의 「지연 · 모터 세기 구현 안 함」 은 위 변경이 커밋되면 낡은 문장이 된다.
- S1-b 가 이 생성기를 쓸 때 `MixedVelocityCommandCfg.params` 로 `backoff_prob 0.15` 를 넘겨야 물러나기가 켜진다(기본 0). 깃발 목록은 15 §8.1 side table 경로(`flag_provider`) 가 아직 없다(S1-a 는 이어진 깃발 직선만).
- 승급 term 이 읽는 `_episode_sums` 는 설치 `_reset_idx` 순서(curriculum 356 행 → reward reset 375 행)대로 방금 끝난 에피소드 값이다(코드 주석과 같음).
