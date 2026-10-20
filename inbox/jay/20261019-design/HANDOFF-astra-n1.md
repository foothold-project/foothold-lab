> 분류: A/평가
> 작성: ASTRA (lead 의뢰) · 2026-10-20
> 근거: a4d8722c26061ba7542ebca7205e1e21197055f5 · 41 §4·§9 · CPU 시험
> 요지: 축 3 START 8×8 생성기 네 종 연결, 고정 0.2와 관측 vy 옆 칸 분리
> 상태: 구현 완료 · CPU 333 통과 1 건너뜀 · Kit 미확인 · 병합 전 lead 확인

# ASTRA-N1 구현 인계

작업 자리: `C:/mai/wt/foothold-lab/astra2-n1`, 브랜치 `feature/astra2-n1-jay`.
sonnet-code 작업 사본은 편집하지 않았다. GPU·Kit 실행, 병합, push는 하지 않았다.
관련 이슈: [foothold-lab #555](https://github.com/foothold-project/foothold-lab/issues/555).

## 구현

| 요구 | 변경 · 근거 |
|---|---|
| START 네 종 포함 | `run_eval.py:209`, `s0_chain.py:104`의 제외를 제거. 듬성한 행은 기존 3종 + START 4종, 명령 하나당 700판이다. |
| 8×8 생성기 | `terrain_sets.py:29,103`에서 기존 `terrains/sparse_terrains.py:284`를 재사용한다. `stepping_stones_start → stepping_stones_high`, `balance_beams → balance_beams`, `stepping_beams → stepping_beams`, `gaps_start → gaps`. 8×4 START 시험지 진입점은 별개로 유지한다. |
| 좌우 두 칸 | `cells.py:165`는 좌·우 각각 `variant=fixed`와 `observed` 두 행을 만든다. 고정 ±0.2는 항상 있고, 실측값이 있을 때 관측 ±vy_obs도 실행한다. 표는 23행이다. |
| 중복 값 보존 | `s0_chain.py:56`의 관측 실행 폴더에는 `__vy_obs`를 붙인다. vy_obs=0.2여도 고정 칸과 따로 실행·집계한다. `s0_tables.py:110`과 비교 표도 variant로 구별한다. |
| 관측값 연결 | 실행과 집계 모두 반복 가능한 `--vy_obs POLICY=MPS`를 받는다. 정책별 값을 분리하며, 다른 정책의 값을 자동 대입하지 않는다. 음수·NaN·무한대·중복 이름·선택하지 않은 정책 이름은 거부한다. |
| 2초 + 2초 | a4d8722c의 `cells.axis3_rule` 및 runtime을 그대로 쓴다. 뒤 0.3은 기준 0.6m, 옆 0.2는 0.4m. 관측 옆은 vy_obs×2m, 총 4초다. |

위 코드 경로는 `foothold_s2/` 아래다.

## 관측값 입력과 미측정

규칙은 **해당 판 마지막 1,000 학습 update의 깃발 지형 env에서 |vy 명령|의 95분위**, S1-b와 S2를 각각 산출한다. 몸의 실제 옆 속도가 아니다. 근거는 이 작업 사본의 `41-EVAL-AXES.md:119` 및 sol-20u 작업 사본의 `evidence/baselines/gates-v1.json:469`이다. a4d8722c의 gates 파일은 해당 필드가 없는 초안이므로 복사하거나 임의로 채우지 않았다. sol 작업 사본의 실측값 두 키도 읽은 시점에는 null이었다.

명령 실행 시와 표 생성 시 **같은 정책별 관측값 인자**를 준다.
`python -m foothold_s2.eval.s0_chain ... --vy_obs <판이름>=<실측_mps>`와
`python -m foothold_s2.eval.s0_tables ... --vy_obs <판이름>=<동일_실측_mps>`이다.
이 CLI는 학습 로그를 읽어 분위수를 계산하지 않는다. 호출자가 해당 규칙으로 산출한 값을 공급하고 원자료를 남겨야 한다.

관측값 생략 시 `needs_vy_obs` 행을 남기고 관측 실행은 하지 않는다. 0.2로 대체하지 않는다.
관측값 0이면 `zero_vy_obs`로 남긴다. 거리 분모가 0인 정지 명령을 옆 이동 성공으로 판정하지 않기 위한 처리이며, 이 처리의 설계 등록은 **가정 · lead 확인**이다.

## 가정 · lead가 정할 것

| 항목 | 현재 구현 · 남은 결정 |
|---|---|
| 징검돌 low/high | 단일 평가 별칭은 **high**에 연결했다. 학습 생성기는 low/high 두 종류인데 41의 축 3 표는 한 종류만 지정한다. high 선택은 **가정 · lead 확인**이며 확정 수치로 해석하지 않는다. |
| 시작 위치 | 네 생성기의 기존 훈련 시작점 `(0.5, 4.0, 0)`을 사용한다. 새 위치는 만들지 않았다. 뒤 0.3을 2초 정확히 따르면 x=−0.1m가 되어 타일 경계를 벗어난다. 옆 0.2는 입구의 넓은 평지에서 끝날 수 있다. 따라서 **연결 완료가 듬성한 지형 위 후진·옆걸음 측정의 타당성을 보장하지 않는다**. lead가 방향별 시작 위치·진입 후 측정 여부를 정하고 sonnet이 Kit 예행에서 확인해야 한다. |
| 실제 관측값 | S1-b/S2별 로그 산출값과 출처를 lead가 전달한다. 이 작업에서는 값이나 분위수 계산의 추가 표본 정의를 지어내지 않았다. |

오늘 밤 평가 종료 뒤 sonnet이 검토·병합·Kit 예행을 맡는다. **결과 폴더는 새로 지정한다.** 기존 3종 축 3 결과와 새 7종 결과를 섞으면 집계 모집단이 달라진다. 새 하네스를 진행 중인 평가 사본에 덮어쓰지 않는다.

## 시험

isaac311 Python에서 `CUDA_VISIBLE_DEVICES=''`, `OMP_NUM_THREADS=1`, `MKL_NUM_THREADS=1`, `KMP_DUPLICATE_LIB_OK=TRUE`, `PYTHONDONTWRITEBYTECODE=1`로 실행했다.

```text
C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe -B -m pytest foothold_s2 -q -p no:cacheprovider
```

- 변경 전: **318 passed, 1 skipped**.
- 추가 시험은 먼저 8건 실패, 구현 후 통과. CLI 시험 7건도 먼저 실패한 뒤 구현했다.
- 변경 후 평가 모듈: **101 passed**. 추가 시험 15건은 네 실제 메시의 8×8 경계, 7종 목록, 2초 명령·4초 관찰·기준 거리, 좌우 두 칸, 같은 속도 결과 분리, 정책별 CLI→CSV, 잘못된 관측값 거부를 확인했다.
- 전체 CPU 시험: **333 passed, 1 skipped in 136.27s**. Kit 클래스 생성만 대역으로 바꾸고 실제 메시 생성 함수를 실행했다. 실제 Isaac 클래스 결합·충돌·스폰·로봇 보행·CUDA는 **미확인**이다.

## 변경 파일

- 실행·집계: `foothold_s2/eval/cells.py`, `run_eval.py`, `s0_chain.py`, `s0_tables.py`, `terrain_sets.py`.
- 시험: `foothold_s2/eval/tests/test_axis3_sparse.py` 신규, `test_pure_modules.py`, `test_s0_chain.py`, `test_s0_tables.py`의 기존 기대값 갱신.
- 기록: 이 파일.
