> 분류: A/정책학습 · 검증 (fable 20o · sonnet-code S2 지형 · 보상 코드가 스스로 정한 가정 다섯 대 START 원문)
> 작성: fable 세션 · lead 의뢰 20o · 10/20 13:2x
> 근거: sonnet-code 사본 커밋 3b056d41(`C:/Users/AI-WS01/orca/workspaces/foothold-lab/sonnet-code`) `foothold_s2/terrains/sparse_terrains.py` · `terrains/s2_runtime.py` · `curriculum/terrain_levels_mixed.py` · `rewards/core.py` · `eval/start_sheet.py` · `HANDOFF-S1.md` 46~48 행 · START 2512.13153v1.txt 223 · 251~255 · 259~261 · 275 · 285~297 · 337~341 행 · 선행 2409.15692v2.txt 280 · 284 행 · Isaac Lab 2.3.2 `terrains/terrain_generator.py` 244~246 · 260~262 행 · `terrain_generator_cfg.py` 115 행 · anaconda isaac311 `rsl_rl_lib-3.1.2.dist-info/METADATA` · `C:/isaac/ext/go2_rl_robotlab/source/rsl_rl/pyproject.toml` 7 행 · Isaac Lab `isaaclab_rl/setup.py` 49 행
> 요지: 다섯 가정 모두 START 본문에 그 값이 없다(원문에 없음 · 가정(sonnet) 유지). ④ 고무작위 r 1 의 크기 · 두 기전만 원문에 있고(337~341 행 · Fig. 4(b)), 저무작위 0 과 「전 레벨 같은 r」 은 선행 284 행의 레벨 비례(0.0 → 0.48)와 다르다(참고 · lead 판단). ③ 은 Isaac 난이도 식과 일치. 15 §2 · §4 · §8.1, 16 §2, 18 §5.1 에 반영
> 상태: 완료 · 미커밋(lead 커밋) · 코드 · 학습 · GPU · Kit 없음

# VERIFY-fable-20o · sonnet 가정 다섯 대 START 원문

## 1. 판정

| # | 가정(sonnet) | 코드(3b056d41) | 원문 대조 | 판정 | 반영 자리 |
|---|---|---|---|---|---|
| ① | START 시험지 8 × 4 m 무늬를 학습 8 × 8 칸 가운데 띠(y 2~6 m)에 놓음 | `sparse_terrains.py` 3 · 21~23 · 151 행(y + 2.0) | START 275 행 「Each patch measures 8m × 4m」. 더 큰 칸 안 배치는 없음. 8 × 8 칸 자체는 15 §2 가정 | 원문에 없음 · **가정(sonnet)** | 15 §2 칸 크기 행 |
| ② | 띠 밖(y 0~2 · 6~8)은 그 칸의 구덩이 바닥 높이, 출발 · 도착 단(x 0~1 · 7~8)은 칸 폭 전체 | 4 · 60~66 행 `_frame` | START 에 없음. START 는 패치 전폭이 지형이고 옆 이웃은 다른 패치(legged_gym 격자) | 원문에 없음 · **가정(sonnet)**. 주의: 옆으로 2 m 벗어나면 START 는 이웃 지형, 우리는 낙하 → 종료. 깃발 열 y = 4 · 듬성한 지형엔 자유 속도 명령 없음(14 §3)이라 드묾. 8 m 전폭 무늬 안은 lead 선택 | 15 §2 칸 크기 행(①과 같이) |
| ③ | Isaac 난이도 d → 레벨 floor(10 × d) | 50~51 행 `level_of` · 215 행 `bind_all` 검사 | START 259 행 「10 difficulty levels」(이산). Isaac `terrain_generator.py` 260~262 행 d = (줄 + U[0, 1)) / 10 · `difficulty_range` 기본 (0, 1)(cfg 115 행) → floor(10 d) = 줄 | 원문에 없음 · **가정(sonnet)** · Isaac 식과 일치(확인) | 15 §2 레벨 수 행 |
| ④ | 징검돌 저무작위 r 0 · 고무작위 r 1 (전 레벨 같은 r). r 은 돌 ±0.5 r × 틈 · 열 ±0.45 r × 틈 | `start_sheet.py` 42~43 · 117~119 · 129~133 행 · `sparse_terrains.py` 28~30 행 | 고무작위 r 1 = START 337~341 행 최대값(돌 0.5 · 열 0.45 × 틈) · Fig. 4(b) 223 행 「two levels of stone position randomization」 = 돌 · 열 두 기전. 저무작위: 223 · 285 행 「lower-randomness」 값 없음. 선행 284 행: 무작위 크기 레벨 따라 0.0 → 0.48 | 고무작위 크기 · 기전 **원문에 있음** · 저무작위 0 원문에 없음 · **선행과 다름(참고)**: 고무작위 열은 레벨 0 에도 최대, 저무작위 열은 레벨 9 에도 0 (시험지 기본 `randomness=None` 은 레벨 비례) | 15 §4 징검돌 무작위 행 |
| ⑤ | 발 가장자리 마스크 해상도 2.5 cm(칸당 320 × 320, 칸별 격자 · 칸 모서리 변환) | `sparse_terrains.py` 26 · 92~110 행 · `rewards/core.py` 118~135 행 · `s2_runtime.py` 21~22 행 | START 251~255 행 「within d cm from an edge」 · 선행 280 행 「morphological dilation」. 해상도 없음 | 원문에 없음 · **가정(sonnet)**. 2.5 cm 는 안쪽 띠 폭과 같아 두 띠를 정수 칸으로 표현하는 가장 성긴 값 · 경계 오차 ±2.5 cm · 메모리 51.2 MB bool(25 열 × 10 줄 × 320 × 320 × 2, 계산) | 16 §2 마스크 줄 · 15 §8.1 좌표 변환 행(설계 「전역 0.05 m 격자」 와 구현 「칸별 2.5 cm」 차이 표기) |

## 2. 원문과 다른 것 (lead 보고)

| # | 코드 | 원문 | 어느 쪽 · 권고 |
|---|---|---|---|
| ④ (선행과 다름 · START 본문은 최대값만) | 고무작위 열 r = 1 전 레벨 고정(레벨 0 의 돌 0.5 m · 틈 0.175 m 에도 돌 ±0.5 · 열 ±0.45 × 틈), 저무작위 열 r = 0 전 레벨 고정 | 선행 284 행 「Randomization magnitude [0.0 → 0.48] × gap」 = 레벨 따라 증가. START 337~341 행은 최대값(0.5 · 0.45)만, 285~297 행 · 223 행은 「lower / higher-randomness 집단」 만 | START 본문으로는 못 가른다. 선행대로면 고무작위 열의 r 을 레벨 비례(시험지 기본과 같음)로, 저무작위 열은 그보다 작은 비례(예: 0.5 × 레벨 비례) 또는 0. 지금 코드는 「저 = 0 · 고 = 최대」 두 극단. lead 판단 |

①②③⑤ 는 START 본문에 해당 값이 없어 「원문과 다름」 이 아니다. 단 ② 는 START 와 동작이 다른 상황(옆 2 m 이탈)이 있어 위 표 밖 주의로 15 §2 에 적었다.

## 3. 반영한 자리 (미커밋)

- `15-TERRAIN-CURRICULUM.md` §2 칸 크기 행(①②) · 레벨 수 행(③) · §4 징검돌 무작위 행(④) · §8.1 좌표 변환 행(⑤ 구현 차이) · 상태 줄 stamp
- `16-REWARDS.md` §2 마스크 줄(⑤) · stamp
- `18-TRAINING-BUDGET.md` §5.1 버전 · 진입점 행: S2 학습 · 시험 실행 환경 isaac311(rsl-rl-lib 3.1.2) 통일, 기본 Kit python 의 rsl_rl 은 `C:/isaac/ext/go2_rl_robotlab` 다른 판(pyproject 3.3.0) · stamp

## 4. 기록 (판정 아님)

- 실행 환경 한 줄의 근거: isaac311 `rsl_rl_lib-3.1.2.dist-info/METADATA` Version 3.1.2(확인) · Isaac Lab `isaaclab_rl/setup.py` 49 행 핀 3.1.2(확인) · ext 사본 `pyproject.toml` 7 행 version 3.3.0(확인). Kit python 이 실제로 ext 사본을 import 하는지는 Kit 을 띄우지 않아 **미확인**(lead 20o 의뢰문 · sonnet HANDOFF-S1 46 행 「ext 쪽 사본으로 잡힘」 보고에 따름).
- 3b056d41 작업 트리에는 커밋 뒤 미커밋 변경(`tasks/s2_env_cfg.py` · `tasks/__init__.py` 수정, `tasks/agents/s2_ppo_cfg.py` · `tasks/s2_env.py` 미추적)이 있다. 표는 커밋 기준.
- `s2_runtime.py` 54 행 재배정 뒤 `env_origins = terrain_origins[level, type]` 갱신, `rewards/core.py` 118~135 행은 env 의 현재 (level, col) 로 마스크를 고르므로 열이 바뀌어도 새 칸 마스크를 본다(15 §8.1 reset 행과 같은 뜻, 확인).
- 코드 · 학습 · GPU · Kit · 커밋 없음.
