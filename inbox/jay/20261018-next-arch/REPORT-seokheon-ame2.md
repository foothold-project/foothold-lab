> 분류: 조사 보고 (팀원 실험 읽기 · 읽기 전용)
> 작성: 오흥재 (lead 세션 · Claude 하위 조사)
> 근거: s3://rzklpc35sl/limseokheon/ (eu-ro-1, RunPod 네트워크 저장소 S3 API) 의 텍스트 파일 (py · yaml · log · txt). .pt · mp4 · usd 는 받지 않음. 내려받은 텍스트 사본은 C:/Users/AI-WS01/.claude/jobs/09bbf294/tmp/sh_ame2/
> 요지: 바운딩은 10/9 ~ 10/12 의 12 지형 계열(ab_standard → stage2a_main → acc15k_r1)에서 나왔다. 정상 대각 보행은 평지 재학습이 아니라 10/12 보상 · 종료 설정을 바꾼 뒤 처음부터 다시 학습한 계열(s2k0 → c12 → nogap2)에서 나왔다. 바운딩 계열이 gap · stones 를 더 잘 건넜고, 대각 보행 계열은 0.3 m 넘는 gap 과 stones 를 거의 못 건넌다. nogap2 를 20000 업데이트까지 이어 학습한 판은 12000 업데이트 이후 무너졌다
> 상태: 2026-10-18 13:08 KST 기준. nogap2 u19999 Eval5 는 b42 만 나왔고 b1001 진행 중, 미경험 지형 평가(GenEval) 대기 중

경로 표기: 모든 키는 `s3://rzklpc35sl/limseokheon/` 뒤에 붙는다. S3 목록의 시각은 KST, 실행 폴더 이름의 시각은 UTC 다.

## 0. 결론 세 줄

1. 바운딩(앞 두 발 · 뒤 두 발이 짝지어 착지하고 네 발이 함께 뜨는 걸음)은 `ab_standard → stage2a_main → acc15k_r1` 계열 전체에서 측정됐다. 이동 중 네 발이 모두 뜬 비율 25 ~ 33 %, 두 발 지지 가운데 앞쌍 · 뒷쌍 46 ~ 56 %.
2. 정상 보행(두 발 지지 가운데 대각 쌍 75 ~ 80 %, 비행 1 ~ 3 %)은 10/12 설정 변경 뒤 **처음부터** 학습한 판에서 나왔다. 바뀐 것: 도약 벌점 -1 → -5, 고도 문턱 0.2 → 0.3 m, 비발 접촉 -1 → -5, 실제 자기충돌 센서, 초기 레벨 1 → 5. 「약 60M 스텝 평지 재학습」 에 해당하는 실행은 S3 에 없다.
3. 성능은 정반대로 움직였다. 바운딩 계열은 gap · stones 를 훨씬 잘 건넜다(평가기가 달라 비교 주의). 대각 보행 계열은 0.3 m 넘는 gap 과 stones 를 거의 못 건넌다. nogap2 이어 학습에서 Gap12a-Eval5 성공률이 u5999 0.657 → u19999 0.404.

## 1. 실험 목록

### 1.1 최상위 폴더
| 폴더 | 날짜 (KST) | 무엇 | 근거 |
|---|---|---|---|
| `ame2/` | 10-08 → 10-18 | ETH AME-2 공개 코드(G1, Isaac Lab 2.3.2) 사본 + Go2 포팅 `go2/ame2_go2/` + Go2 학습 · 평가 로그 | `ame2/README.md`, `ame2/go2/ame2_go2/tasks/go2_env_cfg.py` |
| `ame2_nogap20k/` | 10-17 → 10-18 | nogap2 u6000 → u20000 이어 학습. 코드 고정 사본 | `ame2_nogap20k/README.txt` |
| `ame2_geneval/` | 10-18 | 미경험 지형 6 종 평가용 코드 고정 사본. 대기 중 | `ame2_geneval/README.txt`, `ame2_geneval/out/queue_status.txt` |
| `go2_terrain_generalist/` | 10-04 → 10-07 | AME-2 이전 별도 시도. 속도 명령 teacher. 보행 합격 없이 중단 | `go2_terrain_generalist/README.md` |
| `isaaclab/` | 09-02 → 09-17 | Isaac Lab 포크 + 9 월 FOOTHOLD v1 시기 gap 실험 21 개 | `isaaclab/logs/rsl_rl/unitree_go2_gap_nvidia/` |
| `foothold-lab/` | 09-14 | 우리 저장소 9/14 사본. AME-2 문서 없음 | `foothold-lab/AGENTS.md` |
| `tools/` · `backups/` | | git-lfs 바이너리 · `isaaclab_E0-E4_2026-09-03.bundle` | |

「v1 ~ v15」 같은 판 번호는 없다. 실행은 목적 이름으로 붙어 있다.

### 1.2 AME-2 Go2 teacher 실행 (`ame2/logs/rsl_rl/go2_gaze_teacher/`, `ame2_nogap20k/logs/rsl_rl/go2_gaze_teacher/`)
1 업데이트 = 4096 env × 24 step = 98,304 env step, 정책 주기 20 ms.

| 실행 | 시작 | 업데이트 | 지형 | 비고 |
|---|---|---|---|---|
| `2026-10-08_*_stage1_debug*` | 처음 | 최대 1000 | flat + rough | Stage 1 시운전 |
| `2026-10-09_05-27-05_ab_standard` | 처음 | 0 → 2999 | 12 종 | **바운딩 계열의 시작** |
| `2026-10-09_12-44-06_ab_easystart` | 처음 | 0 → 2999 | 12 종, stones 쉬운 시작 | stones A/B |
| `2026-10-09_20-10-10_stage2a_main` | ab_standard u2999 | 3000 → 9999 | 12 종 | 바운딩 |
| `emademote` · `ctrl6000` · `bal_ctrl_r1` · `bal_ema_r1` | ab_standard u2999 등 | → 5999 | 12 종 | 강등 규칙 실험 |
| `2026-10-12_02-19-17_acc15k_r1` | stage2a_main u9999 | 10000 → 10927 (마지막 저장 u10500) | 12 종 | 허벅지 가속도 종료 60 m/s² 추가. 바운딩 |
| `2026-10-12_17-00-33_s2k0_s42` · `_21-43-40_s2k1_s42` | **처음** | 0 → 1999 | 12 종 | 10/12 설정 변경 뒤 첫 판. k1 은 EMA 강등 추가 |
| `2026-10-14_06-49-24_c12_s42` · `_11-47-38_c16_s42` | 처음 | 0 → 1999 | 12 종(목표 · stones v3 개정) | gaze crop 12 × 10 대 16 × 10 |
| `2026-10-14_18-27-53_mix_c12_s42` | 처음 | 0 → 1999 | 12 종, stones 30 → 5 % | 지형 비율 실험 |
| `2026-10-15_07-41-30_nogap2_c12_s42` | 처음 | 0 → 1999 | NoGap 8 종 | **정상 보행 계열** |
| `2026-10-15_14-40-29_nogap2_c12_s42_to6000` | nogap2 u1999 | 2000 → 5999 | NoGap | |
| `2026-10-16_03-30-39_gap12a_c12_s42` | nogap2 u5999 가중치 + 옵티마이저, 레벨 새로 | 0 → 3999 | Gap12a (70/30) | `ame2/go2/scripts/queue_gap12a.sh` |
| `2026-10-16_19-16-42_nogap2_c12_s42_to20000` | nogap2 u5999 | 6000 → 19999 | NoGap | 10-18 12:53 KST 종료 |

student 는 smoke · 계약 시험만 있다(2 ~ 12 업데이트). 본 학습 없음.

### 1.3 바운딩과 정상 보행이 나온 판
`diag_gait.py` 로그 (이동 = 수평 속도 0.3 m/s 초과, 첫 1 초 제외, 레벨 0 ~ 9, 2048 env × 900 step).

| 체크포인트 | 시험 지형 | 0 발 | 4 발 | 2 발 지지 대각 / 앞뒤쌍 / 같은쪽 | 근거 |
|---|---|---|---|---|---|
| ab_standard u1000 | 12 종 | .332 | .279 | .268 / **.486** / .246 | `ame2/go2/_runs/archive_20261016/jumpscan/gait_ab_standard_1000.log` |
| stage2a_main u9999 | 12 종 | .286 | .317 | .250 / **.557** / .194 | `.../jumpscan/gait_stage2a_9999.log` |
| acc15k_r1 u10500 | 12 종 | .254 | .345 | .303 / **.458** / .239 | `.../jumpscan/gait_acc15k_10500.log` |
| s2k0 u1999 | 12 종 | .103 | .206 | .578 / .281 / .142 | `.../10_accel_formula_gait_capacity_1014/gait_k0_mean.log` |
| c12_s42 u1999 | 12 종 | .027 | .168 | **.754** / .075 / .171 | `ame2/go2/_runs/archive_20261016/mix_seed42/gait_ctrl.log` |
| nogap2 u5999 | NoGap | .012 | .071 | **.797** / .051 / .152 | `ame2/go2/_runs/after_nogap2b/gait6000.log` |

바운딩 모델을 NoGap 지형에 올려도 바운딩한다. 정상 보행은 지형 세트를 바꾸지 않은 c12_s42(12 종)에서 이미 나왔다. 그래서 「평지 쪽 재학습이 걸음을 되돌렸다」 는 해석은 파일과 맞지 않는다.

10/12 에 바뀐 설정 (`acc15k_r1/params/env.yaml` 대 `s2k0_s42/params/env.yaml`)

| 항목 | 바운딩 계열 | 10/12 이후 |
|---|---|---|
| undesired_leaping 가중치 / elevation_thr | -1 / 0.2 m | **-5 / 0.3 m** |
| undesired_non_foot_contacts | -1 | **-5** |
| 자기충돌 | 발 간격 대리항, self-collision 꺼짐 | 좌우 다리 필터 접촉 센서 6 개, self-collision 켜짐 |
| max_init_terrain_level | 1 | 5 |
| 커리큘럼 램프 | 600 업데이트 | 2000 업데이트 |
| 시작 | 이어 학습 | **처음부터** |

어느 항목이 걸음을 바꿨는지 하나씩 가른 실험은 없다(미확인).

도약 벌점이 바운딩을 막지 못한 이유 (acc15k_r1 u10500, 레벨 5, 문턱 0.2 m, `.../05_accel_selfcol_gait_1012/diag_gait_level5.log`): 도약 스텝 판정 .219, 벌점이 켜진 비율 .049. `ame2_undesired_leaping` 은 critic 스캔 전체(1.68 × 0.72 m)의 최고 - 최저가 문턱보다 작을 때만 켜지고, 맞지 않은 광선(inf)이 하나만 있어도 꺼진다(`ame2_geneval/go2/ame2_go2/tasks/mdp/rewards.py`). 도약 스텝의 약 78 % 가 벌점 밖(무반사 25 %, 고도차 문턱 이상 52 %). 이 빈틈에서 바운딩이 자랐다는 것은 추정.

## 2. 관측 · 지도 · 신경망 (teacher)
근거: `ame2/go2/ame2_go2/tasks/go2_env_cfg.py` · `tasks/mdp/observations.py` · `sensors/virtual_floor.py` · `ame2/rsl_rl/rsl_rl/models/AME2_models.py` · `tasks/agents/rsl_rl_ppo_cfg_go2.py`

- actor prop 49: 선속도 3 · 각속도 3 · 중력 3 · 관절 위치 12 · 관절 속도 12 · 직전 행동 12 · 명령 4 (목표 위치형). 이력 없음.
- actor 지도: 29 × 13, 0.06 m, yaw 정렬, x -0.42 ~ 1.26 m, y ±0.36 m. 칸마다 (x, y, z). **마스크 · 불확실도 채널 없음.**
- 바닥 없는 틈 처리: sparse 4 종(stones, gap, beam, pallets)의 물리 바닥 없는 타일(생성 시 50 %)에 충돌 없는 **가상 바닥**을 둔다. 높이는 에피소드마다 월드 z U(-1.0, -0.4) m, 지도는 max(지형, 가상 바닥) 을 읽는다(논문 Appendix A). 나머지 무반사는 「스캔의 가장 낮은 유효 높이 - depth」 로 채운다.
- actor AME2GazeModel: prop MLP 49 → 512 → 512 → 128 · 전역 CNN → 64 · 응시 머리가 crop 12 × 10 을 고름 · 칸 특징 96 · query MLP → **MHA 96 차원 32 헤드** · 출력 MLP → 12. crop 16 × 10 은 12 × 10 보다 성공률 0.106 낮음.
- critic: MoE 전문가 16 개, 보상 항마다 value head. 대칭 증강은 critic 에만.
- PPO: muon, bf16, lr 1e-3 adaptive(KL 0.01), 5 epoch, minibatch 8, entropy 0.004.

## 3. 보상 · 종료 · 무작위화 (`go2_env_cfg.py` RewardsCfg)
| 항 | 가중치 | 인자 |
|---|---|---|
| position_tracking / heading_tracking | +100 / +50 | T 4 s / 2 s |
| move2goal / standatgoal | +5 / +5 | |
| early_termination_penalty | -500 | |
| undesired_leaping | **-5** | 모든 발 떨어짐 AND 스캔 고도차 < **0.3 m** |
| undesired_non_foot_contacts | **-5** | 1 N |
| stumbling / slippage | -1 / -1 | |
| self_col_front / rear | -1 / -1 | |
| link_contact_forces | -1e-5 | G = **147.3 N** (Go2 무게, G1 400 N 이 아님) |

없는 항: 발 공중 시간, 보행 위상 · 시계, 대각 강제, 몸 높이 목표. 종료: 허벅지 가속도 60 m/s², 몸통 접촉 147.3 N. 구동 Kp 25 · Kd 0.5. **G1 상수는 이미 Go2 값으로 고쳐 둠**(행동 배율 0.25 만 같음).

## 4. 지형 (재사용용)
공통: 타일 12 × 12 m, 10 행 × 60 열, difficulty (0, 1). 근거 `ame2_geneval/go2/ame2_go2/tasks/terrains_go2.py` · `custom_terrains.py` · `jeplo_heights.py`.

### 4.1 12 종 세트
| 지형 | 비율 | difficulty 0 → 1 |
|---|---|---|
| rough | 5 % | 경사 0 → 20°, 거칠기 0 → 0.10 m |
| stair_down / stair_up | 5 / 5 % | 단 0.03 → 0.17 m |
| boxes | 5 % | 최고 0.03 → 0.22 m |
| obstacles | 5 % | 경사 0 → 20°, 밀도 0 → 0.5 /m² |
| climb_up | **20 %** | 0.06 → 0.50 m |
| climb_down | 5 % | 0.10 → 0.60 m |
| consecutive | 5 % | 단마다 0.05 → 0.25 m |
| gap | 5 % | 폭 0.08 → 0.70 m, 물리 바닥 50 % |
| pallets | 5 % | 판 폭 0.30 → 0.12, 틈 0.05 → 0.24 m |
| beam | 5 % | 폭 0.50 → 0.14 m |
| stones | **30 %** | 윗면 0.45 → 0.15 m, 돌 사이 0.06 → 0.18 m |

### 4.2 NoGap 8 종 · 4.3 평가
- NoGap: rough · stair_down · stair_up · boxes_j · discrete_j · climb_up · climb_down · steps_j (JEPLO 바탕 3 종 포함).
- Eval5: 12 종 × 5 열, 칸마다 100 에피소드. GenEval 미경험 6 종: rubble · polygons · logs · hurdles · stairs_irr · combo.
- 커리큘럼 약점(본인 기록): gap · beam 은 실패해도 4 m 밖으로 거의 안 나가 강등되지 않음.

## 5. 학습 규모
RTX 4090 한 장, 4096 env, 업데이트당 7.9 ~ 8.8 s, 최대 메모리 17.3 ~ 17.8 GiB. 2000 업데이트(1.97 억 env step) 약 4.9 시간. nogap2 누적 19999 업데이트 = 19.7 억 env step.

## 6. 결과
- 학습 로그 끝 성공 EMA: stage2a_main u9999 gap .04(레벨 8.8) · stones .37(4.5) · beam .44 · pallets .67. c12_s42 u1999 gap .29(1.9) · stones .02(0.0). gap12a u3999 gap .07 · stones .37(0.9).
- 고정 평가: nogap2 u5999 NoGap .923 · Gap12a .662, gap12a u3999 Gap12a .735, **nogap2 u19999 Gap12a-Eval5 .404** (u5999 .657).
- c12_s42 u1999 레벨별: gap .87 .69 .50 .15 .03 이후 0 (계산값으로 약 0.20 ~ 0.27 m 에서 50 %, 0.33 m 이상 3 % 이하), stones .12 .04 .01 이후 0.
- 바운딩 stage2a_main u9999 (확률적 행동, 다른 평가기): gap .99 .98 .89 .74 .79 .62 .49 .36 .19 .01, stones .90 .81 .69 .68 .52 .41 .17 .11 .04 0. 같은 평가기 비교 없음, 방향은 「바운딩 계열이 gap · stones 를 훨씬 잘 건넘」 (추정).
- nogap2 20k 붕괴: u11551 까지 EMA .83, u15718 .612, u19999 .573. lr 이 9500 부터 하한 1e-5, std 0.31 ~ 0.37 → 0.21 ~ 0.25. 원인 미확인.

## 7. go2_terrain_generalist (10/04 → 10/07)
속도 명령 teacher, 지도 near 61 × 61 @0.04 m · far 41 × 41 @0.2 m (8 채널). 125 업데이트까지 이동 성공 0/544. 「보행 및 제로샷 합격도 아직 없다」(`go2_terrain_generalist/docs/AUTONOMOUS_RESULTS_20261005.md`). 10/08 부터 AME-2 로 옮김.

## 8. 우리 설계에 바로 쓸 것
1. 도약 벌점 판정의 빈틈(무반사 하나 · 고도차 문턱)을 먼저 막는다.
2. **바운딩과 sparse 성능이 같이 움직였다.** 걸음을 고치면 gap · stones 가 죽는 위험을 첫 물음으로 둔다.
3. 긴 이어 학습은 무너질 수 있다. 체크포인트는 고정 평가로 고르고 중간 평가를 건다.
4. 4 절 지형 표(특히 stones Go2 끝값 윗면 0.15 · 틈 0.18 m)를 재사용한다.
5. teacher 지도는 (x, y, z), 마스크 없음, 바닥 없는 타일 절반은 가상 바닥.
6. crop 12 × 10 이 16 × 10 보다 낫고, EMA 강등은 해롭다.
7. stones 30 % 로 처음부터 2000 업데이트하면 stones 는 레벨 0 에 머문다.

## 9. 미확인
바운딩 → 대각 보행 단일 원인 · 「약 60M 스텝 평지 재학습」 실행(S3 에 없음) · gap12a 등 지형 × 레벨 표(.pt 에만) · u19999 b1001 · GenEval · 같은 평가기 비교 · u12000 이후 붕괴 원인 · 본인 계획 문서 위치.
