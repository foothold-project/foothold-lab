> 분류: A/평가
> 작성: ASTRA (lead 의뢰) · 2026-10-21
> 근거: 1e565bba · N1d 의뢰 · lead 높이 식 선택 2 · n1c_dry_1021 JSON · CPU 시험
> 요지: 지지면 높이 차 3 cm 관문과 발 구 바닥 최소 간격 1 cm를 뒤·옆 시작점에 적용
> 상태: 구현 완료 · CPU 385 통과·1 건너뜀 · Kit 미실행 · 검토·병합 대기

# ASTRA-N1d 인계

작업 자리 `C:/mai/wt/foothold-lab/astra2-n1d`, 브랜치 `feature/astra2-n1d-jay`.
기준 `1e565bbaa416808bf411536eac31670f491509ee`. 관련 이슈 [#555](https://github.com/foothold-project/foothold-lab/issues/555).
GPU·Kit를 실행하지 않았다. sonnet 사본과 종료 판정 코드는 수정하지 않았고 학습 프로세스도 건드리지 않았다. 병합·push하지 않는다.

## 결정과 구현

- START 4종·기존 3종의 뒤·옆 칸에 네 지지면 `max(z)-min(z) <= 0.03 m`를 적용한다. 3 cm는 lead가 지정한 가정이다. 앞·회전 칸의 규칙은 유지한다.
- 기존 15° yaw와 연속 위치 탐색을 유지하되 **모든 후보에 높이 관문을 적용**한다. 최근접 XY 해가 높이 조건에 실패해도 더 먼 유효 자세를 계속 찾는다. 유효 자세끼리는 `(4,4)`에 가까운 위치·작은 yaw 순이다.
- 기본 자세에서 앞·뒤 발 중심 z가 약 9.58 mm 다르므로 lead에게 높이 식을 확인했다. **선택 2**: `spawn_root_z = max_i(support_z_i - FK_foot_center_z_i + 0.022) + 0.01`. 네 발 구 바닥 간격의 최솟값이 정확히 1 cm이고 모두 1 cm 이상이다. 가장 높은 돌의 발 하나만 정확히 1 cm로 강제하는 식은 아니다.
- `spawn_root_z_m`은 타일 좌표에서 로봇 root의 목표 z다. 지형 원점 z와 로봇 cfg의 기본 root 높이는 보존한다. `root_z_offset_m = spawn_root_z_m - terrain_origin_z - root_height_m`을 지형별 `reset_base.pose_range.z`에 고정한다. 최초·반복 리셋 모두 적용한다. 지형 자체를 올리거나 내리지 않는다.
- `root_height_m`은 여전히 cfg의 기본 root z다. 실행 시 실제 default 값과 대조한다. 새 물리 목표 높이는 `spawn_root_z_m`을 읽어야 한다. `origin[2]`만 보고 새 몸 높이라고 해석하면 안 된다.
- 높이 조건을 만족하는 자세가 없으면 `no_start`, `origin=null`, `eligible=false`다. XY 해는 있으나 높이 차만 실패하면 `reason=support_height_spread_exceeded`, XY 해도 없으면 `no_four_foot_support`로 구분한다.
- `xy_only_candidate`에 N1c의 최근접 XY 후보와 당시 높이·간격을 `record_only`, `eligible=false`로 보존한다. `previous_origin`은 N1b 기록이다. 어느 쪽도 실행용 fallback이 아니다. `minimum_candidate_height_spread_m`은 탐색한 XY 후보 중 최소 높이 차다.
- JSON·manifest에 3 cm 한계, 1 cm 간격, root 목표와 리셋 오프셋을 남긴다. 요약 CSV의 리셋 조건도 N1d로 구분한다. N1c의 A 조건을 쓴 과거 결과와 섞어 같은 조건이라고 주장하지 않는다.

## 근거와 시험

실제 읽은 예행 기록: `C:/Users/AI-WS01/s2_lab/eval_new/n1c_dry_1021/stepping_stones_start_back/feet.json`. 기존 후보의 지지면 차는 0.0846561 m, 발 중심 공중 간격은 `[0.0138413,0.0984974,0.0914528,0.0884758] m`, step 30 접촉 수 2개·몸 높이 0.180461 m다. 이 결과는 N1c의 기록이며 N1d 실행 결과가 아니다.

새 CPU 시험을 먼저 실행해 높이 차 0.0301·0.085 m를 잘못 통과시키는 실패와 최근접 잘못된 자세를 고르는 실패를 확인한 뒤 구현했다. 답을 아는 입력은 다음과 같다.

- 높이 차 0.02와 정확히 0.03 m는 인정, 0.0301과 0.085 m는 거부한다. 부동소수점 허용량은 기존 `EPS=1e-8 m`다.
- 가장 가까운 네 돌은 8.5 cm 차, 더 먼 네 돌은 2 cm 차인 입력에서 먼 유효 자세를 찾는다.
- 네 FK 발 z가 −0.3 m, 지지 높이 `[0,0.01,0.02,0.02] m`이면 root z는 **0.352 m**, 구 바닥 간격은 정렬했을 때 `[0.01,0.01,0.02,0.03] m`다.
- 앞뒤 FK z가 다르고 최고 돌의 발이 더 짧은 입력에서도 네 발 전부 1 cm 이상인지 확인한다. 최고 돌 하나만 맞춰 다른 발 여유가 줄어드는 식을 쓰지 않는다.
- cfg 기본 root 높이를 0.4에서 0.42 m로 바꾼 입력에서 실제 목표 높이는 같고 reset z 오프셋만 −0.02 m 달라진다. 지형 원점은 같다.
- 서로 다른 지형의 yaw·z 오프셋이 최초·반복 리셋에 적용되고 다른 칸의 리셋은 보존되는지 CPU 모형으로 확인한다.
- 실제 생성기의 7종×뒤·좌·우 시험에서 ready인 칸은 지지면 차 3 cm 이하와 최소 구 바닥 간격 1 cm를 추가로 검사한다.

관련 시험 **66개 통과**. 최종 전체 `python -B -m pytest foothold_s2 -q -p no:cacheprovider` 결과는 **385 통과·1 건너뜀, 164.53초**다. 건너뜀은 기존 ONNX 배포 대조 시험으로, 이 사본의 체크포인트 부재 상태다. `git diff --check` 통과, 변경 파일 em dash 0개다. Python은 `C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe`, CUDA 장치 숨김, OMP/MKL 스레드 1, Kit 없음이다.

## no_start 목록과 새 선택값

평가 기본값인 **난이도 0.5·seed 42·뒤 −0.3·좌 +0.2·우 −0.2**, 기존 3종은 실제 평가 열 순서로 생성했다. 관측 vy는 미측정 상태를 유지한다.

**no_start: `balance_beams/back`, `balance_beams/left_fixed`, `balance_beams/right_fixed` 3칸.** 모두 `no_four_foot_support`이며 N1c부터 제외된 칸이다. 이번 높이 조건 때문에 새로 no_start가 된 칸은 이 21칸 중 **0칸**이다. 임의 난이도·관측 vy 전체에 대한 전수 결론은 아니다.

| 지형 | 뒤·좌·우 상태 | 선택 지지면 높이 차 m | root 목표 z m | 발 구 바닥 간격 m |
|---|---|---:|---:|---|
| gap | 모두 ready | 0 | 0.333503 | 0.010000, 0.010000, 0.019582, 0.019582 |
| stepping_stones | 모두 ready | 0 | 0.333503 | 위와 같음 |
| floating_ring | 모두 ready | 0 | 0.558503 | 위와 같음 |
| stepping_stones_start (high) | 모두 ready | 0.011875 | 0.329563 | 0.018851, 0.010000, 0.031456, 0.031143 |
| balance_beams | 모두 no_start | 해당 없음 | 해당 없음 | 옛 후보로 실행하지 않음 |
| stepping_beams | 모두 ready | 0.013510 | 0.344225 | 0.013928, 0.013928, 0.010000, 0.010000 |
| gaps_start | 모두 ready | 0 | 0.333503 | 0.010000, 0.010000, 0.019582, 0.019582 |

START 징검돌의 새 XY는 `(4.230851,3.095410)`, yaw 180°다. 기존 `(4.175077,4)`의 높이 차 0.084656 m 후보는 기록만 남는다. 디딤 빔은 `(3.126104,4)`, yaw 0°로 바뀐다. 나머지 지형의 XY/yaw 선택은 이 조건에서 N1c와 같다.

## 다음 한 걸음

lead/sonnet 검토·병합 후 새 결과 폴더에서 Kit 예행을 한다. `install_fixed_reset(raw,names,generator.axis3_starts)` 호출은 유지하되 **새 생성기의 계획**을 넘겨야 한다. N1c 계획에는 `root_z_offset_m`이 없어 재사용할 수 없다. 초기 root 높이·발별 구 바닥 간격과 step 30 네 발 접촉·몸 높이를 확인한다. 접촉 안정은 아직 미확인이다. `gaps_start` 즉시 종료의 원인 분석·종료 판정 수정은 sonnet 담당으로 남긴다.
