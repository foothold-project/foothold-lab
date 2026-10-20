> 분류: A/평가
> 작성: ASTRA (lead 의뢰) · 2026-10-20
> 근거: a4d8722c26061ba7542ebca7205e1e21197055f5 · 41 §4·§9 · CPU 시험
> 요지: N1b 반영 · 듬성한 7종의 뒤·옆 시작점 선택과 시작점 없는 칸 판정 제외
> 상태: N1b 완료 · C안 반영 · CPU 364 통과 1 건너뜀 · Kit 미확인 · 검토·병합 대기

# ASTRA-N1 구현 인계

작업 자리: `C:/mai/wt/foothold-lab/astra2-n1`, 브랜치 `feature/astra2-n1-jay`.
sonnet-code 작업 사본은 편집하지 않았다. GPU·Kit 실행, 병합, push는 하지 않았다.
관련 이슈: [foothold-lab #555](https://github.com/foothold-project/foothold-lab/issues/555).

## N1b · lead 결정 10/20 반영

N1 커밋 `d36307090d331dc914b0a7a4011f1fb826f36215` 다음 변경이다.

- **뒤·옆 칸만** 새 규칙을 적용한다. 앞·앞+회전·제자리 회전의 생성기 원점과 리셋은 유지한다.
- `sparse_starts.py`가 명령 2초 거리와 그 방향으로 0.3m 여유를 검사한다. 발판 패치와 허용 영역의 교집합에서 `(4,4)`에 가장 가까운 점을 고르고 윗면 z를 사용한다. 직사각형 영역에서 시작과 여유 끝점이 안이면 선분 전체가 안이다.
- START 4종은 `x=[1,7], y=[2,6]`. 입구·출구·구덩이 바닥은 지지 후보에서 뺀다.
- 기존 3종은 실제 생성기 설정에서 영역을 계산한다. `gap`은 `platform_width + 2×gap_width`인 중앙 발판·틈 외곽, `floating_ring`은 `platform_width + 2×ring_width`인 고리 외곽이다. `stepping_stones`는 설치본의 `border_pixels=int(border_width/horizontal_scale)+1`을 반영한 내부 영역이다. **영역 해석**: 기존 생성기의 중앙 플랫폼도 그 feature 외곽 안에 포함된다. 출발부터 매 스텝 틈을 건넌다는 뜻은 아니다.
- 기존 3종의 실제 생성 메시에서 위쪽 삼각형 두 개가 평평한 사각형을 이루는 경우만 지지 패치로 인정한다. 징검돌의 구덩이 바닥과 떠 있는 고리 아래 바닥은 제외한다. 영역을 추출할 수 없거나 지지 패치가 없으면 `no_start`다. 이 추출 방식은 lead가 23:47 답에서 그대로 진행하도록 확인했다.
- 검사한 메시를 복사해 실제 생성에 재사용한다. 검사 뒤 재추첨하지 않는다. 캐시는 끄고, 첫 평가 reset 전부터 뒤·옆 칸의 x/y/yaw 흔들기를 0으로 만든다. 자동 reset도 같은 원점을 쓴다.
- `axis3_starts.json`, manifest의 `start_plan`·`excluded_start_terrains`, 지형별 표에 **「시작점 없음 · 판정 제외」**를 남긴다. 해당 지형은 환경 생성·원자료·성공률 분모에서 제외한다. 전체가 제외되면 정책을 로드하지 않고 헤더만 있는 원자료와 제외 상태 표를 쓴다.
- 사슬 완료 검사는 단순히 판 수 부족을 허용하지 않는다. 제외 이름·상태·판 수·두 원장이 모두 맞을 때만 기대 판 수를 줄인다. 일부 지형이 빠진 합산 표는 관문에서 제외하고, 남은 지형의 개별 결과는 보존한다.
- **징검돌은 high만.** gates에 옮길 결정 문구: **「lead 결정 10/20 · high 만」**. low는 평가하지 않는다.
- S1-b 전 관측 vy 칸은 **「미측정 · 판정 제외」**, 고정 ±0.2가 관문이다. 실제 값이 생기면 정책별 같은 입력 규칙으로 기록 칸을 붙인다. 관측 칸은 41 §9대로 기록용이다.

### 보수적으로 처리한 경계와 미확인

- **lead 정정 10/20 · C안**: 0.6m 상한은 뒤 칸에만 적용한다. 관측 옆 칸은 원 vy_obs를 보존하고 **기준 거리=|vy_obs|×2초**, 여기에 0.3m를 더한 구간으로 시작점을 고른다. 예: vy_obs=0.35이면 기준 0.7m, 시작점 검사 거리 1.0m다. 옆 속도를 0.3으로 자르거나 그 초과만으로 제외하지 않는다. A 원값 보존·보류, B 제한 실행의 제안은 채택되지 않았다. 관측값 0은 기존처럼 미측정이다.
- 0.3m는 lead가 지정한 몸 길이 여유 가정이다. CPU 시험은 **원점의 수직 투영이 지지 패치 위인지**와 선분·영역을 검사한다. 네 발의 초기 접촉·착지 안정성·실제 보행·낙하는 Kit 예행 전 **미확인**이다.
- 기존 3종에서 중앙 플랫폼을 포함한 feature 외곽의 의미와 실제 첫 발 디딤은 sonnet 검토·Kit 예행에서 확인할 것. 새로운 물리 관문 수치로 승격하지 않는다.

### N1b 시험

최종 전체 CPU 시험: **364 passed, 1 skipped in 162.53s**. N1보다 31건 늘었다. C안은 vy_obs=0.35가 실패하는 회귀 시험을 추가한 뒤 수정했다. 추가 시험은 START 네 종×뒤·좌·우 12칸, 설치본 기존 세 생성기×뒤·좌·우 9칸, 옛 `(0.5,4)` 후진 거부, 여유 0.3m, 가장 가까운 패치·윗면 높이, 시작점 없는 전체 실행의 정책 미기동·CSV·원장 검증, 자동 reset, 원장 변조 거부를 포함한다. 설치본 함수는 AST로 순수 형상 함수만 읽어 실행하며 Isaac 패키지와 Kit는 import하지 않는다.

설정 근거: `sim/eval/generalization_env_cfg.py:75,85,113`. 형상 근거: 설치본 `C:/isaac/IsaacLab/source/isaaclab/isaaclab/terrains/trimesh/mesh_terrains.py:559,601`, `height_field/hf_terrains.py:354`, `height_field/utils.py:38`. reset 설치 API: 설치본 `managers/event_manager.py:282,304`.

N1b 변경: `eval/sparse_starts.py` 신규, `cells.py`, `manifest.py`, `run_eval.py`, `s0_tables.py`, `terrain_sets.py`, `tests/test_axis3_starts.py` 신규, `tests/test_axis3_sparse.py`, 이 문서. 원본 `terrains/sparse_terrains.py`와 학습 코드는 수정하지 않았다.

## N1 구현 기록 · d3630709 기준

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
| 징검돌 low/high | N1에서는 가정이었다. **N1b에서 lead 결정 10/20 · high 만**으로 닫았다. |
| 시작 위치 | N1의 기존 시작점 문제는 N1b에서 뒤·옆 7종의 방향별 선택으로 고쳤다. 위 N1b 절과 실제 Kit 예행의 미확인 범위를 볼 것. |
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
