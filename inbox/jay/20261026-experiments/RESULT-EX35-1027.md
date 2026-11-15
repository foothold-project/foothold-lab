> 분류: 실험
> 작성: 오흥재 (lead · scripter 원자료 생성) · 2026-10-27
> 근거: EX-35 학습 영수증·저장본 판정 JSON·A11 창 판정 JSON·map64 및 turn16 반복 NPZ·CMP 영상 · 결과 전 EX-35 카드 §4b.6
> 요지: m2000 MAINTAIN_FAIL의 세 사유 중 둘은 같은 GPU 세 번의 회전 반복에서 유지됐다. 창 판정은 STOP 6행이며 정본 S-B10 m1500을 유지한다.
> 상태: 학습·저장본·창 판정 확인됨 · map64 및 turn16 반복 측정 차이 확인됨 · 비결정성 원인 미확인
> 판: v1.5

# EX-35 결과 · 명령 S2a 창 판정

## 1. 같은 조건의 영상부터 보기

CMP 영상 원본은 `C:\Users\AI-WS01\s2_lab\video_25e\final\runner-26m\p2\rendered\CMP_S-B10-m1500_vs_EX-35-m2000_rough_eval_gt_seq_1x.mp4` (`sha256 ad81b106b2085e0034385bc99516fd777a233a2c5fabff755c9ec352fbc711cb`)이다. 영상 판독과 보행 위상 해석은 진행 중이며, 이 보고서는 영상의 운동 품질을 판정하지 않는다. 공개 링크와 영상 길이·프레임 수는 미확인이다.

## 2. 무엇이 같고 무엇이 다른가

부모는 S-B10 m1500 (`sha256 4d987818c7e25b89e77b7541feca3ddabedd444c5b20651eb29f3681da040d9d`), EX-35는 그 저장본에서 m1501부터 m2000까지 500회 갱신했다. 실행 인자는 GPU `cuda:0`, 3072 env, seed 42, `max_iterations=2001`이다. 명령 과정 S2a와 판정 규칙은 결과 전 [EX-35 카드](../20261021-experiments/EXP-EX35-SB10-cmd-S2a.md)에 등록됐다. 영상·물리 상세 조건의 독립 재확인은 미완료다.

## 3. 저장본별 판정

| 저장본 | 지도 모드 | 단계 안 갱신 | 최소 체류 | 상태 | 사유 수 |
|---|---|---:|---:|---|---:|
| m1750 | eval_gt | 250 | 500 | NEW_TASK_PENDING | 1 |
| m1950 | eval_gt | 450 | 500 | MAINTAIN_FAIL | 3 |
| m2000 | eval_gt | 500 | 500 | MAINTAIN_FAIL | 3 |

m1750의 `NEW_TASK_PENDING`은 최종 유지 판정이 아니다. 최종 판단에는 m1950과 m2000의 상태를 쓴다.

## 4. 유지 실패가 난 칸

| 저장본 | 사례 | 조건 | 측정값 | 등록 한계 |
|---|---|---|---:|---:|
| m1950 | right_then_left | drop_Q | 0.4955872241479847 | 0.5837163634983495 |
| m1950 | right_then_left | rise_C | 0.6950000000000001 | 0.6673828125 |
| m1950 | fwd_then_left | drop_Q | 0.4757363248932633 | 0.5628077151095658 |
| m2000 | left_then_right | survival_16 | 13 | 14 |
| m2000 | right_then_left | drop_Q | 0.5586886471922285 | 0.5837163634983495 |
| m2000 | fwd_then_left | survival_16 | 13 | 14 |

이 표는 `ex35_verdict.json.reasons`를 그대로 펼친 것이다. 원인이나 보행 기전을 뜻하지 않는다.

## 5. 회전 사례의 Q · C · 생존 표본

| 사례 | m1950 Q | m2000 Q | m1950 C | m2000 C | m1950 kept | m2000 kept |
|---|---:|---:|---:|---:|---:|---:|
| fwd_then_left | 0.4757 | 0.5714 | 0.6412 | 0.5558 | 15 | 13 |
| fwd_then_right | 0.8108 | 1.0993 | 0.4083 | 0.4422 | 15 | 16 |
| indep_left | 0.4276 | 0.5401 | 0.6546 | 0.4855 | 14 | 15 |
| indep_right | 0.8341 | 1.1090 | 0.4087 | 0.4366 | 16 | 15 |
| left_then_right | 0.8294 | 1.1200 | 0.4339 | 0.4317 | 15 | 13 |
| right_then_left | 0.4956 | 0.5587 | 0.6950 | 0.5513 | 14 | 14 |
| walk_turn_left | 0.4705 | 0.4820 | 0.1345 | 0.0943 | 16 | 16 |
| walk_turn_right | 0.4746 | 0.4953 | 0.0530 | 0.0469 | 16 | 16 |

Q·C의 정의와 문턱은 등록 카드와 판정기 계약을 따른다. 여기서는 원자료 표시만 한다.

부모와 비교할 때는 같은 사례끼리 본다. 부모 S-B10 m1500은 `startline_table.json`의 `eval_gt`이고 아래 m2000 열은 EX-35 판정 JSON이다.

| 사례 | 부모 Q | m2000 Q | 차이 |
|---|---:|---:|---:|
| fwd_then_left | 0.7628 | 0.5714 | -0.1914 |
| right_then_left | 0.7837 | 0.5587 | -0.2250 |
| indep_left | 0.4266 | 0.5401 | +0.1135 |

독립 좌회전은 부모보다 높다. 전진 뒤 좌회전과 우회전 뒤 좌회전의 하락을 독립 좌회전의 하락으로 일반화하지 않는다.

## 6. 학습 종료와 학습 곡선의 한계

`run.log`의 마지막 학습 회차는 2000/2001, 표시 경과는 03:22:27, `rc.txt`는 0이다. 아래는 run.log의 각 회차 값을 창 안에서 산술 평균한 것이다.

| 갱신 창 | 로그 수 | 평균 보상 | 에피소드 길이 | 지형 레벨 | 엔트로피 | 가치 손실 | PPO KL | bad_orientation |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1501-1550 | 50 | 9.8086 | 560.3838 | 5.8472 | 9.2819 | 0.0236 | 0.0177 | 0.0483 |
| 1701-1750 | 50 | 16.4824 | 951.2884 | 6.0715 | 9.5774 | 0.0260 | 0.0169 | 0.1003 |
| 1901-1950 | 50 | 16.8638 | 962.0696 | 6.1857 | 9.4513 | 0.0243 | 0.0163 | 0.0637 |
| 1951-2000 | 50 | 17.2394 | 962.4546 | 6.2300 | 9.3899 | 0.0236 | 0.0168 | 0.0787 |

이 학습 평균은 같은 명령 분포의 저장본 독립 평가가 아니며, 판정에는 사용하지 않았다.

### 16 env 회전 반복 · m2000 핵심 사유

사슬은 GPU1, R1~R3은 같은 고정 사본·저장본·칸에서 GPU0으로 세 번 실행했다. 아래 수치는 각 `arrays_*.npz`의 살아 있는 프레임과 kept env를 CPU에서 다시 집계했다. 반복 폭은 R1~R3의 최대값에서 최솟값을 뺀 값이며 사슬은 폭 계산에 넣지 않았다.

| 경우 | 사슬 kept | R1 | R2 | R3 | 반복 최소~최대 | 반복 폭 |
|---|---:|---:|---:|---:|---:|---:|
| left_then_right | 13 | 14 | 16 | 15 | 14~16 | 2 |
| fwd_then_left | 13 | 13 | 13 | 13 | 13~13 | 0 |
| right_then_left | 14 | 14 | 14 | 13 | 13~14 | 1 |

| 경우 | 사슬 Q | R1 | R2 | R3 | 반복 최소~최대 | 반복 폭 |
|---|---:|---:|---:|---:|---:|---:|
| left_then_right | 1.1200 | 1.1172 | 1.0698 | 1.1298 | 1.0698~1.1298 | 0.0600 |
| fwd_then_left | 0.5714 | 0.5957 | 0.6160 | 0.5162 | 0.5162~0.6160 | 0.0998 |
| right_then_left | 0.5587 | 0.5669 | 0.5804 | 0.5611 | 0.5611~0.5804 | 0.0193 |

등록 조건은 kept `14` 이상, `right_then_left` Q `0.5837` 이상이다. R1~R3은 표본 세 번이고 장치 차이를 분리하지 못했다.

### 같은 코드·장치·시드·칸 배정의 지형별 전진 비교

부모 S-B10 m1500과 EX-35 m2000을 평가 코드 `84deb79336896b6e77916e7479cbace06ee8ab53`, `cuda:0`, seed 42 및 같은 env별 지형 배정에서 비교했다. 거리는 각 env의 `body_vx_integral_m`를 지형 종류별로 집계한 중앙값(m)이며, 생존은 `alive_end`의 합이다. 켬·가림은 L0~2·L6·L9 모두 측정했고 복원은 L0~2만 측정했다.

| 레벨 | 지형 종류 | 지도 | 명령 | 부모 거리 중앙값 m | 부모 생존/env | m2000 거리 중앙값 m | m2000 생존/env |
|---|---|---|---|---:|---:|---:|---:|
| L0~2 | boxes | 켬 | fwd0.5 | 2.69 | 12/12 | 2.86 | 11/12 |
| L0~2 | hf_pyramid_slope | 켬 | fwd0.5 | 2.78 | 4/4 | 2.99 | 4/4 |
| L0~2 | hf_pyramid_slope_inv | 켬 | fwd0.5 | 2.83 | 4/4 | 2.99 | 4/4 |
| L0~2 | pyramid_stairs | 켬 | fwd0.5 | 2.47 | 15/15 | 2.75 | 15/15 |
| L0~2 | pyramid_stairs_inv | 켬 | fwd0.5 | 3.08 | 15/15 | 3.02 | 15/15 |
| L0~2 | random_rough | 켬 | fwd0.5 | 2.79 | 12/12 | 2.94 | 12/12 |
| L0~2 | stage_stairs | 켬 | fwd0.5 | 2.49 | 2/2 | 2.72 | 2/2 |
| L0~2 | boxes | 켬 | fwd1.0 | 5.39 | 12/12 | 5.69 | 12/12 |
| L0~2 | hf_pyramid_slope | 켬 | fwd1.0 | 5.55 | 4/4 | 5.80 | 4/4 |
| L0~2 | hf_pyramid_slope_inv | 켬 | fwd1.0 | 5.54 | 4/4 | 5.78 | 4/4 |
| L0~2 | pyramid_stairs | 켬 | fwd1.0 | 5.16 | 15/15 | 5.65 | 15/15 |
| L0~2 | pyramid_stairs_inv | 켬 | fwd1.0 | 5.57 | 15/15 | 5.85 | 15/15 |
| L0~2 | random_rough | 켬 | fwd1.0 | 5.46 | 12/12 | 5.73 | 12/12 |
| L0~2 | stage_stairs | 켬 | fwd1.0 | 5.08 | 2/2 | 5.52 | 2/2 |
| L0~2 | boxes | 가림 | fwd0.5 | 2.72 | 12/12 | 2.86 | 12/12 |
| L0~2 | hf_pyramid_slope | 가림 | fwd0.5 | 2.86 | 4/4 | 2.97 | 4/4 |
| L0~2 | hf_pyramid_slope_inv | 가림 | fwd0.5 | 2.87 | 4/4 | 2.99 | 4/4 |
| L0~2 | pyramid_stairs | 가림 | fwd0.5 | 2.70 | 15/15 | 2.85 | 15/15 |
| L0~2 | pyramid_stairs_inv | 가림 | fwd0.5 | 2.92 | 15/15 | 2.99 | 15/15 |
| L0~2 | random_rough | 가림 | fwd0.5 | 2.88 | 12/12 | 2.94 | 12/12 |
| L0~2 | stage_stairs | 가림 | fwd0.5 | 2.73 | 2/2 | 2.69 | 2/2 |
| L0~2 | boxes | 가림 | fwd1.0 | 5.40 | 12/12 | 5.61 | 12/12 |
| L0~2 | hf_pyramid_slope | 가림 | fwd1.0 | 5.50 | 4/4 | 5.74 | 4/4 |
| L0~2 | hf_pyramid_slope_inv | 가림 | fwd1.0 | 5.52 | 4/4 | 5.74 | 4/4 |
| L0~2 | pyramid_stairs | 가림 | fwd1.0 | 5.31 | 15/15 | 5.67 | 15/15 |
| L0~2 | pyramid_stairs_inv | 가림 | fwd1.0 | 5.54 | 15/15 | 5.77 | 14/15 |
| L0~2 | random_rough | 가림 | fwd1.0 | 5.50 | 12/12 | 5.69 | 12/12 |
| L0~2 | stage_stairs | 가림 | fwd1.0 | 5.33 | 2/2 | 5.39 | 2/2 |
| L0~2 | boxes | 복원 | fwd0.5 | 2.66 | 12/12 | 2.89 | 12/12 |
| L0~2 | hf_pyramid_slope | 복원 | fwd0.5 | 2.78 | 4/4 | 2.98 | 4/4 |
| L0~2 | hf_pyramid_slope_inv | 복원 | fwd0.5 | 2.85 | 4/4 | 2.99 | 4/4 |
| L0~2 | pyramid_stairs | 복원 | fwd0.5 | 2.46 | 15/15 | 2.73 | 15/15 |
| L0~2 | pyramid_stairs_inv | 복원 | fwd0.5 | 2.93 | 15/15 | 3.02 | 15/15 |
| L0~2 | random_rough | 복원 | fwd0.5 | 2.78 | 12/12 | 2.95 | 12/12 |
| L0~2 | stage_stairs | 복원 | fwd0.5 | 2.45 | 2/2 | 2.58 | 2/2 |
| L0~2 | boxes | 복원 | fwd1.0 | 5.36 | 12/12 | 5.72 | 12/12 |
| L0~2 | hf_pyramid_slope | 복원 | fwd1.0 | 5.55 | 4/4 | 5.79 | 4/4 |
| L0~2 | hf_pyramid_slope_inv | 복원 | fwd1.0 | 5.51 | 4/4 | 5.80 | 4/4 |
| L0~2 | pyramid_stairs | 복원 | fwd1.0 | 5.14 | 15/15 | 5.59 | 15/15 |
| L0~2 | pyramid_stairs_inv | 복원 | fwd1.0 | 5.54 | 15/15 | 5.72 | 13/15 |
| L0~2 | random_rough | 복원 | fwd1.0 | 5.46 | 12/12 | 5.75 | 12/12 |
| L0~2 | stage_stairs | 복원 | fwd1.0 | 4.99 | 2/2 | 5.21 | 2/2 |
| L6 | boxes | 켬 | fwd0.5 | 2.60 | 12/12 | 2.84 | 12/12 |
| L6 | hf_pyramid_slope | 켬 | fwd0.5 | 2.64 | 4/4 | 2.81 | 4/4 |
| L6 | hf_pyramid_slope_inv | 켬 | fwd0.5 | 3.13 | 4/4 | 3.12 | 4/4 |
| L6 | pyramid_stairs | 켬 | fwd0.5 | 2.16 | 15/15 | 2.42 | 15/15 |
| L6 | pyramid_stairs_inv | 켬 | fwd0.5 | 2.98 | 15/15 | 2.71 | 15/15 |
| L6 | random_rough | 켬 | fwd0.5 | 2.79 | 12/12 | 2.96 | 12/12 |
| L6 | stage_stairs | 켬 | fwd0.5 | 2.54 | 2/2 | 2.63 | 2/2 |
| L6 | boxes | 켬 | fwd1.0 | 5.17 | 11/12 | 5.57 | 11/12 |
| L6 | hf_pyramid_slope | 켬 | fwd1.0 | 5.18 | 4/4 | 5.66 | 4/4 |
| L6 | hf_pyramid_slope_inv | 켬 | fwd1.0 | 5.75 | 4/4 | 5.87 | 4/4 |
| L6 | pyramid_stairs | 켬 | fwd1.0 | 4.98 | 15/15 | 5.28 | 15/15 |
| L6 | pyramid_stairs_inv | 켬 | fwd1.0 | 5.30 | 15/15 | 5.35 | 14/15 |
| L6 | random_rough | 켬 | fwd1.0 | 5.48 | 12/12 | 5.71 | 12/12 |
| L6 | stage_stairs | 켬 | fwd1.0 | 4.96 | 2/2 | 5.37 | 2/2 |
| L6 | boxes | 가림 | fwd0.5 | 2.68 | 12/12 | 2.86 | 12/12 |
| L6 | hf_pyramid_slope | 가림 | fwd0.5 | 2.72 | 4/4 | 3.01 | 4/4 |
| L6 | hf_pyramid_slope_inv | 가림 | fwd0.5 | 3.02 | 4/4 | 3.11 | 4/4 |
| L6 | pyramid_stairs | 가림 | fwd0.5 | 2.44 | 14/15 | 2.67 | 15/15 |
| L6 | pyramid_stairs_inv | 가림 | fwd0.5 | 2.64 | 15/15 | 2.66 | 15/15 |
| L6 | random_rough | 가림 | fwd0.5 | 2.82 | 12/12 | 3.00 | 12/12 |
| L6 | stage_stairs | 가림 | fwd0.5 | 2.77 | 2/2 | 2.87 | 2/2 |
| L6 | boxes | 가림 | fwd1.0 | 5.27 | 11/12 | 5.53 | 12/12 |
| L6 | hf_pyramid_slope | 가림 | fwd1.0 | 5.21 | 4/4 | 5.70 | 4/4 |
| L6 | hf_pyramid_slope_inv | 가림 | fwd1.0 | 5.64 | 4/4 | 5.77 | 4/4 |
| L6 | pyramid_stairs | 가림 | fwd1.0 | 5.18 | 15/15 | 5.34 | 15/15 |
| L6 | pyramid_stairs_inv | 가림 | fwd1.0 | 4.80 | 15/15 | 4.96 | 15/15 |
| L6 | random_rough | 가림 | fwd1.0 | 5.47 | 12/12 | 5.65 | 12/12 |
| L6 | stage_stairs | 가림 | fwd1.0 | 5.30 | 2/2 | 5.42 | 2/2 |
| L6 | boxes | 복원 | fwd0.5 | 미측정 | 미측정 | 미측정 | 미측정 |
| L6 | hf_pyramid_slope | 복원 | fwd0.5 | 미측정 | 미측정 | 미측정 | 미측정 |
| L6 | hf_pyramid_slope_inv | 복원 | fwd0.5 | 미측정 | 미측정 | 미측정 | 미측정 |
| L6 | pyramid_stairs | 복원 | fwd0.5 | 미측정 | 미측정 | 미측정 | 미측정 |
| L6 | pyramid_stairs_inv | 복원 | fwd0.5 | 미측정 | 미측정 | 미측정 | 미측정 |
| L6 | random_rough | 복원 | fwd0.5 | 미측정 | 미측정 | 미측정 | 미측정 |
| L6 | stage_stairs | 복원 | fwd0.5 | 미측정 | 미측정 | 미측정 | 미측정 |
| L6 | boxes | 복원 | fwd1.0 | 미측정 | 미측정 | 미측정 | 미측정 |
| L6 | hf_pyramid_slope | 복원 | fwd1.0 | 미측정 | 미측정 | 미측정 | 미측정 |
| L6 | hf_pyramid_slope_inv | 복원 | fwd1.0 | 미측정 | 미측정 | 미측정 | 미측정 |
| L6 | pyramid_stairs | 복원 | fwd1.0 | 미측정 | 미측정 | 미측정 | 미측정 |
| L6 | pyramid_stairs_inv | 복원 | fwd1.0 | 미측정 | 미측정 | 미측정 | 미측정 |
| L6 | random_rough | 복원 | fwd1.0 | 미측정 | 미측정 | 미측정 | 미측정 |
| L6 | stage_stairs | 복원 | fwd1.0 | 미측정 | 미측정 | 미측정 | 미측정 |
| L9 | boxes | 켬 | fwd0.5 | 2.55 | 10/12 | 2.58 | 11/12 |
| L9 | hf_pyramid_slope | 켬 | fwd0.5 | 2.60 | 4/4 | 2.79 | 4/4 |
| L9 | hf_pyramid_slope_inv | 켬 | fwd0.5 | 3.23 | 4/4 | 3.12 | 4/4 |
| L9 | pyramid_stairs | 켬 | fwd0.5 | 1.63 | 14/15 | 2.41 | 14/15 |
| L9 | pyramid_stairs_inv | 켬 | fwd0.5 | 2.47 | 13/15 | 2.38 | 14/15 |
| L9 | random_rough | 켬 | fwd0.5 | 2.77 | 12/12 | 2.93 | 12/12 |
| L9 | stage_stairs | 켬 | fwd0.5 | 2.53 | 2/2 | 2.75 | 2/2 |
| L9 | boxes | 켬 | fwd1.0 | 5.24 | 11/12 | 5.49 | 12/12 |
| L9 | hf_pyramid_slope | 켬 | fwd1.0 | 4.96 | 4/4 | 5.62 | 4/4 |
| L9 | hf_pyramid_slope_inv | 켬 | fwd1.0 | 5.79 | 4/4 | 5.94 | 4/4 |
| L9 | pyramid_stairs | 켬 | fwd1.0 | 4.84 | 15/15 | 5.27 | 15/15 |
| L9 | pyramid_stairs_inv | 켬 | fwd1.0 | 4.90 | 13/15 | 5.16 | 12/15 |
| L9 | random_rough | 켬 | fwd1.0 | 5.44 | 12/12 | 5.73 | 12/12 |
| L9 | stage_stairs | 켬 | fwd1.0 | 5.05 | 2/2 | 5.46 | 2/2 |
| L9 | boxes | 가림 | fwd0.5 | 2.69 | 12/12 | 2.66 | 11/12 |
| L9 | hf_pyramid_slope | 가림 | fwd0.5 | 2.75 | 4/4 | 2.91 | 4/4 |
| L9 | hf_pyramid_slope_inv | 가림 | fwd0.5 | 3.12 | 4/4 | 3.20 | 4/4 |
| L9 | pyramid_stairs | 가림 | fwd0.5 | 2.28 | 12/15 | 2.80 | 12/15 |
| L9 | pyramid_stairs_inv | 가림 | fwd0.5 | 2.23 | 15/15 | 2.26 | 10/15 |
| L9 | random_rough | 가림 | fwd0.5 | 2.84 | 12/12 | 2.97 | 12/12 |
| L9 | stage_stairs | 가림 | fwd0.5 | 2.80 | 2/2 | 2.84 | 2/2 |
| L9 | boxes | 가림 | fwd1.0 | 5.28 | 11/12 | 5.47 | 12/12 |
| L9 | hf_pyramid_slope | 가림 | fwd1.0 | 5.18 | 4/4 | 5.63 | 4/4 |
| L9 | hf_pyramid_slope_inv | 가림 | fwd1.0 | 5.65 | 4/4 | 5.79 | 4/4 |
| L9 | pyramid_stairs | 가림 | fwd1.0 | 5.27 | 15/15 | 5.38 | 14/15 |
| L9 | pyramid_stairs_inv | 가림 | fwd1.0 | 4.04 | 14/15 | 4.52 | 11/15 |
| L9 | random_rough | 가림 | fwd1.0 | 5.46 | 12/12 | 5.64 | 12/12 |
| L9 | stage_stairs | 가림 | fwd1.0 | 5.40 | 2/2 | 5.50 | 2/2 |
| L9 | boxes | 복원 | fwd0.5 | 미측정 | 미측정 | 미측정 | 미측정 |
| L9 | hf_pyramid_slope | 복원 | fwd0.5 | 미측정 | 미측정 | 미측정 | 미측정 |
| L9 | hf_pyramid_slope_inv | 복원 | fwd0.5 | 미측정 | 미측정 | 미측정 | 미측정 |
| L9 | pyramid_stairs | 복원 | fwd0.5 | 미측정 | 미측정 | 미측정 | 미측정 |
| L9 | pyramid_stairs_inv | 복원 | fwd0.5 | 미측정 | 미측정 | 미측정 | 미측정 |
| L9 | random_rough | 복원 | fwd0.5 | 미측정 | 미측정 | 미측정 | 미측정 |
| L9 | stage_stairs | 복원 | fwd0.5 | 미측정 | 미측정 | 미측정 | 미측정 |
| L9 | boxes | 복원 | fwd1.0 | 미측정 | 미측정 | 미측정 | 미측정 |
| L9 | hf_pyramid_slope | 복원 | fwd1.0 | 미측정 | 미측정 | 미측정 | 미측정 |
| L9 | hf_pyramid_slope_inv | 복원 | fwd1.0 | 미측정 | 미측정 | 미측정 | 미측정 |
| L9 | pyramid_stairs | 복원 | fwd1.0 | 미측정 | 미측정 | 미측정 | 미측정 |
| L9 | pyramid_stairs_inv | 복원 | fwd1.0 | 미측정 | 미측정 | 미측정 | 미측정 |
| L9 | random_rough | 복원 | fwd1.0 | 미측정 | 미측정 | 미측정 | 미측정 |
| L9 | stage_stairs | 복원 | fwd1.0 | 미측정 | 미측정 | 미측정 | 미측정 |

켬 `fwd1.0`은 측정한 21칸 모두 m2000의 거리 중앙값이 커졌고, 차이 범위는 0.05~0.65 m다. L6 내려가는 계단(`pyramid_stairs_inv`) 켬 `fwd1.0`은 이 고정 원자료에서 5.30 → 5.35 m다. 의뢰 예시의 끝값 5.28 m는 이 원자료에서 재현되지 않아 표에 넣지 않았다. 한 번의 지형별 거리 차이를 개선 확정으로 읽지 않는다.

생존은 재측정에서 흔들렸다. L9 상자 가림 `fwd1.0`의 같은 m2000 저장본은 8/12 → 12/12이지만 평가 소스 해시도 `ac739f3d8b557043` → `b08941a4ba48e06d`로 달라, 코드 영향과 반복 잡음을 이 사례만으로 분리할 수 없다. 측정한 각 지형 칸은 2~15 env다. L0~2·L6·L9는 이번 비교를 위해 설계로 고른 레벨이 아니라 기존 고정 칸과 10/26 추가 칸이다.

복원 `eval_pred`의 L6·L9는 env별 배열이 없어 **미측정**이다: L6/복원/fwd0.5, L6/복원/fwd1.0, L9/복원/fwd0.5, L9/복원/fwd1.0. 빈 칸을 켬 또는 가림 수치로 채우지 않았다.


## 7. 판정과 증거 범위

m1950과 m2000 저장본의 `MAINTAIN_FAIL`은 확인됐다. 면제 없는 기본 실행은 A11 판독 파일이 없어 `STOP` 4행이었다. 2026-10-27 05:19 KST의 A11 판독표는 다섯 항목 모두 「없음」이며, 판독자는 lead 세션 (Claude Opus 5.5) · 팀장 판독 아님이다. 이를 반영한 창 판정 재실행 결과는 **STOP 6행**, 사유는 `REVERT: 유지 실패 연속 두 저장본 · 멈춤, 되돌림 판은 사람이 띄움`이다. 최신·이전 필수 입력 결측 목록은 모두 빈 목록이다. **EX-35 연장 없음, 정본 S-B10 m1500 유지**다. 저장본 상태와 창 판정을 혼동하지 않는다.

판정 입력은 GPU1 사슬의 16 env 회전 값과 GPU0 재평가의 64 env 네 칸 값을 합쳤다. 같은 m2000 저장본·시드 42의 사슬 및 재평가 map64에서 비교 가능한 수치 74칸 중 28칸이 다르고, `eval_map_modes` 소스 해시는 `ce4d25ea7110b079`에서 `ac739f3d8b557043`로 다르다. 이어 같은 저장본·시드 42·소스 해시 `b08941a4ba48e06d`로 GPU0에서 두 번 잰 수치도 **56칸 중 27칸** 달랐다. GPU0 대 GPU1은 56칸 중 29칸이 달랐다. 따라서 앞의 28칸 차이를 코드 변경 탓으로 단정할 수 없고, 코드 변경의 영향도 이 시험으로 분리할 수 없다. 평가의 비결정성 원인은 미확인이다.

64 env 생존 수는 같은 GPU 반복에서도 1~2대 달랐다. 16 env 회전 반복에서는 `left_then_right` kept가 사슬 13에서 R1~R3 14 · 16 · 15로 바뀌어 이 사유 하나는 반복에서 유지되지 않았다. 그러나 `fwd_then_left` kept는 세 번 모두 13으로 14 미만이고, `right_then_left` Q도 세 번 모두 0.5837 미만이다. 따라서 **m2000 MAINTAIN_FAIL은 세 반복에서도 유지**된다. 사슬 GPU1과 반복 GPU0의 장치 차이는 분리하지 못했고, 세 번의 표본에서 본 폭은 모집단 전체 폭의 하한일 뿐이다. 문턱은 바꾸지 않았다. A11 발자국 메모에는 직진 명령에서 부모 m1500은 왼쪽, EX-35 m2000은 오른쪽으로 휨이 기록됐다. 옆 방향 이동량은 수치 미측이며 이 메모는 판정 항목 밖이다.

## 8. 다음 설계에서 무엇을 바꾸는가

이 보고서만으로 보행 기전이나 비결정성 원인을 정하지 않는다. 보행 위상·저장본 추세 분석과 재현성 원인 조사가 남았다. 새 학습이나 연장은 별도 팀장 결정이 필요하다.

## 9. 실제 완료와 재현 경로

`python inbox/jay/20261026-experiments/figs/ex35/gen_result.py --out inbox/jay/20261026-experiments/RESULT-EX35-1027.md --json-out inbox/jay/20261026-experiments/figs/ex35/result_data.json`

| 원자료 | 경로 | sha256 |
|---|---|---|
| m1750 | `C:\mai\wt\foothold-lab\impl-turncases\logs\ex35_eval\m1750\ex35_verdict.json` | `9707eb3cc3aecb208177093d054f86e1d1b501951de8aa0849a8b7c86d3b3e4b` |
| m1950 | `C:\mai\wt\foothold-lab\impl-turncases\logs\ex35_eval\m1950\ex35_verdict.json` | `ba66346def7fc4a37fcc70bbedd46f7442284af023352894b7c578a26fb9ec58` |
| m2000 | `C:\mai\wt\foothold-lab\impl-turncases\logs\ex35_eval\m2000\ex35_verdict.json` | `8f1271f8be7196b33c06f350474fd10590d3698a5ab017b679024a544e5c7dc5` |
| receipt | `C:\mai\wt\foothold-lab\impl-ex35-07fc\logs_gate\ex35_main_20261026_232432\launch_receipt.json` | `58707db6fe22b337b3ce4b595f338b2c6afda2dc3f0c12a367c699108430d442` |
| run_log | `C:\mai\wt\foothold-lab\impl-ex35-07fc\logs_gate\ex35_main_20261026_232432\run.log` | `932a5ceddebb412a7efac6b64868151aa38382ee9085a0e804a44d341b285edc` |
| rc | `C:\mai\wt\foothold-lab\impl-ex35-07fc\logs_gate\ex35_main_20261026_232432\rc.txt` | `93ff7811a209e2a8479230bbb9b6bc19f7f311d3af383ec350c1db2a7e7d5494` |
| baseline | `C:\mai\wt\foothold-lab\lead_tmp-20261023\inbox\jay\20261026-experiments\figs\startline\startline_table.json` | `841ce5170e2ec63a952d19c3722ee19cb441020c4b52b8a882295d2605713298` |
| window_default | `C:\mai\wt\foothold-lab\impl-turncases\logs\ex35_combined_x27j\window_m2000_default.json` | `4afd6565ab43d70e8c9e0a30f04afb9bbc109647d2efe020ba60e47ac27038b1` |
| window | `C:\mai\wt\foothold-lab\impl-turncases\logs\ex35_combined_x27j\window_m2000_a11.json` | `a4cdda5ff0fa3acedcac34f89ae65db991173c5048f0b33eae97c451dc3f2a39` |
| a11 | `C:\mai\wt\foothold-lab\impl-turncases\logs\ex35_combined_x27j\a11_m2000.json` | `dce8cc4ca19d52fb765e1a4e207c0b7a6071f1cf2d08ff85e99972de30a65818` |
| remeasure_log | `C:\mai\wt\foothold-lab\impl-turncases\logs\ex35_eval_x27j\remeasure.log` | `4e832817541062fc3b9206cf358fdb98a005cc1ca8abf7426a001a8a2229aee0` |
| chain_map | `C:\mai\wt\foothold-lab\impl-turncases\logs\ex35_eval\m2000\map64\map_modes.json` | `14798c0936bdf900a03d69ead32bcefbdb0c3cfcc34975edc094c185824297a5` |
| remeasure_map | `C:\mai\wt\foothold-lab\impl-turncases\logs\ex35_eval_x27j\m2000\map64\map_modes.json` | `9b31e1234ce0575ad8e287a1cb5bd778871bfb565536ffe2186a4576e036ab6f` |
| cmp_video | `C:\Users\AI-WS01\s2_lab\video_25e\final\runner-26m\p2\rendered\CMP_S-B10-m1500_vs_EX-35-m2000_rough_eval_gt_seq_1x.mp4` | `ad81b106b2085e0034385bc99516fd777a233a2c5fabff755c9ec352fbc711cb` |
| repro_compare | `C:\mai\wt\foothold-lab\impl-turncases\logs\ex35_repro_x27k\compare.md` | `a59703976cda15c044465a2c68775b501bf61475e13ab3efb5a29264913c29b5` |
| repro_a1 | `C:\mai\wt\foothold-lab\impl-turncases\logs\ex35_repro_x27k\A1\map_modes.json` | `4cc8d221dc012559ec174569fd295fc39a5f574d687a532221ae6cab9af60d3e` |
| repro_a2 | `C:\mai\wt\foothold-lab\impl-turncases\logs\ex35_repro_x27k\A2\map_modes.json` | `98c3fff030ab8cc55073fa05886935731a54825fb3ecb84ae4a0bb6849d2f45a` |
| repro_b | `C:\mai\wt\foothold-lab\impl-turncases\logs\ex35_repro_x27k\B\map_modes.json` | `37d40a8850f7873e69474aeb22ea3aafee241978d01d543c9f631f964e063bd3` |
| turn16_compare | `C:\mai\wt\foothold-lab\impl-turncases\logs\ex35_repro_turn16\compare.md` | `49642f7d4ee64d7bb929118c4cd76eb14682937108e3a79c24e0335f92c93c2d` |
| turn16_log | `C:\mai\wt\foothold-lab\impl-turncases\logs\ex35_repro_turn16\repro.log` | `a8531df08b9e847d07a5f822eaed8441aef03061449910b2252672e018a17521` |
| turn16_checkpoint | `C:\mai\wt\foothold-lab\impl-turncases\logs\ex35_repro_turn16\checkpoint_sha256.txt` | `111d212f69b2a956628826d29229833887407b898b446fe6318838b0894adb76` |
| turn16_git_head | `C:\mai\wt\foothold-lab\impl-turncases\logs\ex35_repro_turn16\git_head.txt` | `fb0e8552862b4ca5dfde1ff92bb546550ba3924fb3fa6876e8e92ec97d9302db` |
| turn16_probe_R1 | `C:\mai\wt\foothold-lab\impl-turncases\logs\ex35_repro_turn16\R1\probe_result.json` | `2dd2e0587131f2a1cd34e76fd8a1bd3ef064b68434a305372908904b64ce1791` |
| turn16_probe_R2 | `C:\mai\wt\foothold-lab\impl-turncases\logs\ex35_repro_turn16\R2\probe_result.json` | `4e09a67aa95a2ffa74268f9f780de2424ffd467a9c7f153fe59334e0496b5307` |
| turn16_probe_R3 | `C:\mai\wt\foothold-lab\impl-turncases\logs\ex35_repro_turn16\R3\probe_result.json` | `c10ef0ae8f9274e179f8a55d774342e7ba0955627945ae83fb7446ee7f2b0384` |
| turn16_R1_left_then_right | `C:\mai\wt\foothold-lab\impl-turncases\logs\ex35_repro_turn16\R1\arrays_left_then_right.npz` | `6d8f72b09d3972ca1ca0f2d3511c4d2ea84e54c968dd8dc577b9ab2e5a704406` |
| turn16_R1_fwd_then_left | `C:\mai\wt\foothold-lab\impl-turncases\logs\ex35_repro_turn16\R1\arrays_fwd_then_left.npz` | `caeb847c0939a64b397991f95848bc42b6a2d5d09232fad38b771032614213c2` |
| turn16_R1_right_then_left | `C:\mai\wt\foothold-lab\impl-turncases\logs\ex35_repro_turn16\R1\arrays_right_then_left.npz` | `a931b421803cca9108658759c6bcb7c21ac7c2543307309bf458fe369538322d` |
| turn16_R2_left_then_right | `C:\mai\wt\foothold-lab\impl-turncases\logs\ex35_repro_turn16\R2\arrays_left_then_right.npz` | `407aa7d030b557350c72d4b5e54b78ce3d0e3e4494a6ba7a4e44cc036da1122d` |
| turn16_R2_fwd_then_left | `C:\mai\wt\foothold-lab\impl-turncases\logs\ex35_repro_turn16\R2\arrays_fwd_then_left.npz` | `75af443d817998de2e2a2bb24d9e72caf8cc699b9f57b1b820bf96604fd7e7d4` |
| turn16_R2_right_then_left | `C:\mai\wt\foothold-lab\impl-turncases\logs\ex35_repro_turn16\R2\arrays_right_then_left.npz` | `8b0eb6623c9dd47016ddbd7feccef3bed3031368641ff415108de5b4190eed91` |
| turn16_R3_left_then_right | `C:\mai\wt\foothold-lab\impl-turncases\logs\ex35_repro_turn16\R3\arrays_left_then_right.npz` | `e34b6c6c537fc60ee9fb389073e3441966929dee570035afcc5520b2f7b5986f` |
| turn16_R3_fwd_then_left | `C:\mai\wt\foothold-lab\impl-turncases\logs\ex35_repro_turn16\R3\arrays_fwd_then_left.npz` | `b275d46f5ca5f5d68a9f324c3bb1fb21bafb0ef4f258771adb8a971901f1efb2` |
| turn16_R3_right_then_left | `C:\mai\wt\foothold-lab\impl-turncases\logs\ex35_repro_turn16\R3\arrays_right_then_left.npz` | `1f7a3b19c84dce95cdbb8475b7990706866d6606635aae5ad6809a714e86013d` |
| terrain_parent_L0~2_eval_gt_fwd0.5 | `C:\mai\wt\foothold-lab\impl-turncases\logs\sb10_eval_x27j\m1500\map64\env_arrays_eval_gt_fwd0.5.npz` | `69003d2563a5260f80b38535753260e6114a32a75dec861da882cc5f90d08b9f` |
| terrain_child_L0~2_eval_gt_fwd0.5 | `C:\mai\wt\foothold-lab\impl-turncases\logs\ex35_eval_x27k\m2000\map64\env_arrays_eval_gt_fwd0.5.npz` | `e46b5dde826ba0c2233d9a2bad26cfb6ef5a3b950e1a27ac6d976c1b97b8e74a` |
| terrain_parent_L0~2_eval_gt_fwd1.0 | `C:\mai\wt\foothold-lab\impl-turncases\logs\sb10_eval_x27j\m1500\map64\env_arrays_eval_gt_fwd1.0.npz` | `8374750b333afe6b69433c2b85ed5e1545d1a46116257a51ac6cc7028d452a7c` |
| terrain_child_L0~2_eval_gt_fwd1.0 | `C:\mai\wt\foothold-lab\impl-turncases\logs\ex35_eval_x27k\m2000\map64\env_arrays_eval_gt_fwd1.0.npz` | `dce0cd264933d53f957e1135e5120039643f51994fb2f9612f54fb30eebbd36d` |
| terrain_parent_L0~2_probe_prop_only_fwd0.5 | `C:\mai\wt\foothold-lab\impl-turncases\logs\sb10_eval_x27j\m1500\map64\env_arrays_probe_prop_only_fwd0.5.npz` | `76d217e5ce07bf7a3bd46aef460eb382ad3b381b9c720bc570a2b554baf11a78` |
| terrain_child_L0~2_probe_prop_only_fwd0.5 | `C:\mai\wt\foothold-lab\impl-turncases\logs\ex35_eval_x27k\m2000\map64\env_arrays_probe_prop_only_fwd0.5.npz` | `8209d2748808aea5424b5cffa4f8f6ca6195d57db1ff3b65e5ab49f6f6dbc8e5` |
| terrain_parent_L0~2_probe_prop_only_fwd1.0 | `C:\mai\wt\foothold-lab\impl-turncases\logs\sb10_eval_x27j\m1500\map64\env_arrays_probe_prop_only_fwd1.0.npz` | `330bef74b8677f899dd67a5bd9be08318c8e71b48c95fdde42c28bae91430b68` |
| terrain_child_L0~2_probe_prop_only_fwd1.0 | `C:\mai\wt\foothold-lab\impl-turncases\logs\ex35_eval_x27k\m2000\map64\env_arrays_probe_prop_only_fwd1.0.npz` | `a096d2add79905db2fcfc042fd6fb4be07eab13b25500f2c023299ee31e1975c` |
| terrain_parent_L0~2_eval_pred_fwd0.5 | `C:\mai\wt\foothold-lab\impl-turncases\logs\sb10_eval_x27j\m1500\map64_eval_pred\env_arrays_eval_pred_fwd0.5.npz` | `5206f18895f7ba0235dabfa94b88f6ec43e35aae5af9d56a350b84262aab967e` |
| terrain_child_L0~2_eval_pred_fwd0.5 | `C:\mai\wt\foothold-lab\impl-turncases\logs\ex35_eval_x27k\m2000\map64_eval_pred\env_arrays_eval_pred_fwd0.5.npz` | `34e267550b9c358e5f18d3402f99969a405151f61510949fe7d714cfdc02864a` |
| terrain_parent_L0~2_eval_pred_fwd1.0 | `C:\mai\wt\foothold-lab\impl-turncases\logs\sb10_eval_x27j\m1500\map64_eval_pred\env_arrays_eval_pred_fwd1.0.npz` | `f328f6d67127a5a3dea6010a27522e6a3f33798c14045a880cd0ab9f14b0e44d` |
| terrain_child_L0~2_eval_pred_fwd1.0 | `C:\mai\wt\foothold-lab\impl-turncases\logs\ex35_eval_x27k\m2000\map64_eval_pred\env_arrays_eval_pred_fwd1.0.npz` | `1f3fac098d10a414d13be896e73454cea024cedca3db812b2663ed61aaf29486` |
| terrain_parent_L6_eval_gt_fwd0.5 | `C:\mai\wt\foothold-lab\impl-turncases\logs\sb10_eval_x27j\m1500\hardlevel\L6\env_arrays_eval_gt_fwd0.5.npz` | `b7e770bd57b180f3660ca6e21524681fa2e914b72b34b3a852b5a20e707cc8ec` |
| terrain_child_L6_eval_gt_fwd0.5 | `C:\mai\wt\foothold-lab\impl-turncases\logs\ex35_eval_x27k\m2000\hardlevel\L6\env_arrays_eval_gt_fwd0.5.npz` | `22f726d70701451ebd51a0693ba2669bfed9d1bd8a539ebcd6c93c90a0bf7039` |
| terrain_parent_L6_eval_gt_fwd1.0 | `C:\mai\wt\foothold-lab\impl-turncases\logs\sb10_eval_x27j\m1500\hardlevel\L6\env_arrays_eval_gt_fwd1.0.npz` | `5b71fb704f0f00df9ae27ccefba7a272ba0ef0f9406bb4400d9ca4da8a457ca3` |
| terrain_child_L6_eval_gt_fwd1.0 | `C:\mai\wt\foothold-lab\impl-turncases\logs\ex35_eval_x27k\m2000\hardlevel\L6\env_arrays_eval_gt_fwd1.0.npz` | `ca889feeaf9ec08b492efc14405644a7417e854cc753d6ab7f38f2f9c7be185a` |
| terrain_parent_L6_probe_prop_only_fwd0.5 | `C:\mai\wt\foothold-lab\impl-turncases\logs\sb10_eval_x27j\m1500\hardlevel\L6\env_arrays_probe_prop_only_fwd0.5.npz` | `5067da77783399803dcf5d46ffafdd3412a5aec3af634bcc27e29a171d2f1e46` |
| terrain_child_L6_probe_prop_only_fwd0.5 | `C:\mai\wt\foothold-lab\impl-turncases\logs\ex35_eval_x27k\m2000\hardlevel\L6\env_arrays_probe_prop_only_fwd0.5.npz` | `7fee1979a4a3a1f56e76475f8b37f96768b7cb1066647f85110bd9fb101dd221` |
| terrain_parent_L6_probe_prop_only_fwd1.0 | `C:\mai\wt\foothold-lab\impl-turncases\logs\sb10_eval_x27j\m1500\hardlevel\L6\env_arrays_probe_prop_only_fwd1.0.npz` | `50bb64257b29d5eb386ade00889bfb557e7ec4934c121a54b31aa9e2c6b5e7f8` |
| terrain_child_L6_probe_prop_only_fwd1.0 | `C:\mai\wt\foothold-lab\impl-turncases\logs\ex35_eval_x27k\m2000\hardlevel\L6\env_arrays_probe_prop_only_fwd1.0.npz` | `f3b6150c71f59b9f5ad73a8e625500b4e8f8abb58101347cbd492fe2845aa945` |
| terrain_parent_L9_eval_gt_fwd0.5 | `C:\mai\wt\foothold-lab\impl-turncases\logs\sb10_eval_x27j\m1500\hardlevel\L9\env_arrays_eval_gt_fwd0.5.npz` | `0fa471078a04e5877645465f4d03aa9c10ed8464b7ab61cc117da5bf8e212042` |
| terrain_child_L9_eval_gt_fwd0.5 | `C:\mai\wt\foothold-lab\impl-turncases\logs\ex35_eval_x27k\m2000\hardlevel\L9\env_arrays_eval_gt_fwd0.5.npz` | `25f95b9d7b405e295381c1db4c3f62e1114c1312607907e8bb8b5ad28e6d3a19` |
| terrain_parent_L9_eval_gt_fwd1.0 | `C:\mai\wt\foothold-lab\impl-turncases\logs\sb10_eval_x27j\m1500\hardlevel\L9\env_arrays_eval_gt_fwd1.0.npz` | `4349cf0308f464e35d2a9bbc78c4a5f14ad198c41dfb1abe01005e4fa96b5187` |
| terrain_child_L9_eval_gt_fwd1.0 | `C:\mai\wt\foothold-lab\impl-turncases\logs\ex35_eval_x27k\m2000\hardlevel\L9\env_arrays_eval_gt_fwd1.0.npz` | `5c9c7c7bc4c4fdea462b0c527d4b737576e8dbacf3e0d90f90033b3675fbc708` |
| terrain_parent_L9_probe_prop_only_fwd0.5 | `C:\mai\wt\foothold-lab\impl-turncases\logs\sb10_eval_x27j\m1500\hardlevel\L9\env_arrays_probe_prop_only_fwd0.5.npz` | `86e212b7fb3e7ebf0f28857c6b81fc333bd2315f9145e9ebe0164afd9dba2361` |
| terrain_child_L9_probe_prop_only_fwd0.5 | `C:\mai\wt\foothold-lab\impl-turncases\logs\ex35_eval_x27k\m2000\hardlevel\L9\env_arrays_probe_prop_only_fwd0.5.npz` | `245b2c461dbe19aad585d9d68633d2950b2dc2748c3c12308bb99fccd5da1956` |
| terrain_parent_L9_probe_prop_only_fwd1.0 | `C:\mai\wt\foothold-lab\impl-turncases\logs\sb10_eval_x27j\m1500\hardlevel\L9\env_arrays_probe_prop_only_fwd1.0.npz` | `7e3f74fee85d6cefe9558989ba51a882906b6379b4a0f67ab4967ee5a9fd4ded` |
| terrain_child_L9_probe_prop_only_fwd1.0 | `C:\mai\wt\foothold-lab\impl-turncases\logs\ex35_eval_x27k\m2000\hardlevel\L9\env_arrays_probe_prop_only_fwd1.0.npz` | `3102e6709881dc243d73f5d7ee3f559670e833d71dfa7667f9c4f10aa4ed5b30` |
| terrain_child_earlier_L9_probe_prop_only_fwd1.0 | `C:\mai\wt\foothold-lab\impl-turncases\logs\ex35_eval_x27j\m2000\hardlevel\L9\env_arrays_probe_prop_only_fwd1.0.npz` | `e4b167ed99fb9e94410db74f12cddf26dfb36dbc3625afb89895f92ee69ea2eb` |
| terrain_child_earlier_L9_meta | `C:\mai\wt\foothold-lab\impl-turncases\logs\ex35_eval_x27j\m2000\hardlevel\L9\map_modes.json` | `3868755e474feb6381c2a26957b654755d449a39be2e785504bac3ea47c10d21` |
| terrain_child_current_L9_meta | `C:\mai\wt\foothold-lab\impl-turncases\logs\ex35_eval_x27k\m2000\hardlevel\L9\map_modes.json` | `a19a73a24da9ac793e2be37523b6396518ee5dc56ca0f0640037b48311a21bb8` |
| terrain_original_comparison | `C:\mai\wt\foothold-lab\impl-turncases\logs\sb10_eval_x27j\parent_vs_m2000.md` | `cb2b91590e3faca4d6bd6940b37af651ba34101ed09d6a9aa59d0700f6e2ae98` |

검사: `m1750=NEW_TASK_PENDING`, `m1950=m2000=MAINTAIN_FAIL`, 기본 창 `STOP` 4행, A11 판독 뒤 창 `STOP` 6행, 재평가 20단계 완료, map64 동일 GPU 반복 27/56 수치 차이, turn16의 두 안정 실패 사유, 완료 회차와 rc, 부모 sha 일치를 생성기가 요구한다. `STOP`은 창 판정 코드의 결과이지 저장본 JSON의 상태가 아니다. 재생성 시 원자료가 달라지면 해시와 문서도 달라진다.
