> 분류: 검증
> 작성: 오흥재 (ASTRA 검증 세션 작성) · 2026-10-11
> 근거: TASK-astra-5-g0-d1b.md · eval-g0/G0.md 전체 · VERIFY-astra-4.md 4절 · DESIGN 4절 D1/G0/G1 · 로컬 코드·레이·충돌 메시
> 요지: G0의 저장 레이 수치와 구멍 분류는 재현됐다. 실제 관측 경로 연결과 추락 계측을 보완한 뒤 두 encoding을 분리한 D1-B를 진행한다
> 상태: 검토 완료 · 실행 계약은 제안 · 팀장 확정 필요 항목은 마지막 절에 구분

# ASTRA 5 · G0 검증과 D1-B 실행 계약

## 1. 다시 확인한 근거와 G0 판정

이 문서에서 `C`는 `eval-g0/code/`, `R`은 `C:/isaac/ext/go2_rl_robotlab/_eval/out/g0_probe/`, `IL`은 `C:/isaac/IsaacLab/source/isaaclab/isaaclab/`이다. 지정 문서와 연결된 코드·원자료를 읽었다. 새 GPU 실행·학습·정책 rollout은 하지 않았다.

**확인됨:** 먼저 평지·단차·벽·깊은 finite 구멍·±inf·NaN의 답을 아는 입력으로 식을 시험했다. 기존 `g0_test.py`는 결과 JSON을 쓰므로 그 마지막 쓰기 구문 하나만 메모리에서 제외하고 CPU에서 실행했다. 15개 검사가 통과했다. 그다음 저장된 레이 전체를 NumPy로 독립 계산했다.

| 원자료 재계산 항목 | 결과 |
|---|---:|
| 자세 × 자세당 레이 | 33,042 × 187 = 6,178,854 |
| finite hit / +inf / -inf / NaN | 6,111,668 / 67,186 / 0 / 0 |
| 저장된 legacy와 수식 계산의 최대 차 | 0 |
| 저장된 G0와 수식 계산의 최대 차 | 0 |
| finite hit에서 legacy와 G0의 최대 차 | 0 |
| +inf에서 legacy / G0 출력 | -2.5 / +2.5 |
| G0 비유한 출력 | 0 |
| finite hit의 -2.5 / +2.5 포화 | 0 / 0 |
| 학습 8종의 레이 / no-hit | 4,876,314 / 0 |
| gap 열 / 격자 밖의 no-hit | 51,936 / 15,250 |

CPU ray 검사도 알려진 상자의 hit·miss·높이부터 시험했다. 이후 **좌표를 반올림하지 않고** 실제 메시 안쪽 no-hit의 고유 좌표 6,936개를 재투사했다. 해당 51,936개 레이 전부에서 CPU도 표면을 찾지 못했고, 메시 밖 15,250개와 구분됐다. finite hit 양성 대조 5,000개는 모두 맞았고 높이 최대 차는 `4.473329216381217e-6m`였다. `R/G0-results.json`의 핵심 집계와 일치한다.

**확인됨:** `IL/envs/mdp/observations.py:292`~300은 `sensor_z - hit_z - 0.5`, `IL/managers/observation_manager.py:404`~407은 clip 후 scale이다. `IL/terrains/trimesh/mesh_terrains.py:579`~598의 gap은 두께 1m의 중앙 상자와 바깥 고리만 만들며 틈 아래 바닥을 두지 않는다. `IL/terrains/height_field/hf_terrains.py:383`은 돌 간격을 격자 정수로 자른다. 저장 stepping_stones 열의 597,336개 레이는 no-hit 0, 깊은 바닥 hit 0이며 높이도 약 -0.005~0m다. 이 설정을 희소 발판 시험으로 사용하면 안 된다.

**판단:** 지정한 G0 수치 관문, 즉 finite 출력 차 ≤1e-6·no-hit 최종 +2.5·비유한 출력 0은 **시험한 입력과 저장 probe 범위에서 닫힌다.** 이는 관측 변환 검사이며 정책 능력 관문은 아니다.

다음 두 표현은 구분해야 한다.

- **확인됨:** legacy에서 no-hit가 충분히 높은 finite 표면과 같은 -2.5로 인코딩된다. **미확인:** E1 teacher가 이를 실제로 벽이라고 인식하거나 특정 행동을 한다. 수치의 의미와 신경망의 행동 해석은 같지 않다.
- **확인됨:** 이 정적인 probe에서 학습 8종의 no-hit·포화가 0이다. **추정:** 학습 중에도 드물었을 수 있다. 넘어짐·점프·경계 이탈을 포함한 학습 관측 분포는 기록되지 않았으므로 `학습 중 한 번도 보지 않았다`고 확정하지 않는다.

### D1-B 전에 더 필요한 검사

1. **실제 연결 위치:** `C/g0_probe.py:182`~194는 실제 ObservationManager의 **legacy** block과 별도 `g0_encode` 계산을 비교했다. G0 함수를 연결한 실제 manager → teacher 경로까지 시험한 것은 아니다. `g0_encode`는 이미 clip·scale을 마친 값을 반환하므로 기존 ObsTerm에 그대로 연결하면 finite 값에 처리가 중복된다. 평지 -0.30이 -0.75로 바뀔 수 있다. raw 높이 단계에서 invalid를 +1로 대입하고 manager에서 한 번만 clip·scale하거나, manager 이후 최종 block만 교체하는 방식 중 하나를 고정해야 한다. 정상 finite·단차·no-hit·NaN에서 실제 최종 block, 다른 입력 block 불변, teacher mean 경로를 함께 검사한다.
2. **센서·기체 오류를 구멍으로 숨기지 않기:** 추가 CPU 시험에서 `sensor_z=NaN/+inf/-inf`, finite hit 입력은 G0 출력이 전부 +2.5가 되고 `classify(hit_z)`는 원인을 0(finite)으로 기록했다. 출력이 finite여도 기체 상태는 잘못된 것이다. `base/sensor pose invalid`, `hit NaN`, `hit -inf`, `정상 +inf no-hit`, `finite 입력의 연산 overflow`를 별도 기록한다. 앞의 오류들은 실행 오류로 중단·재현 조사하고, 능력 실패나 구멍 표본으로 섞지 않는다. 임시 대입으로 NaN 전파를 막는 것과 그 episode를 유효 실험으로 인정하는 것은 별개다.
3. **동작 중 계약:** 소수 rollout에서 이동·yaw 회전·reset 직후 레이 위치, 관측 갱신 시각, no-hit mask, 187개 순서를 검사한다. 실제 메시 위 finite·틈 no-hit가 이동과 함께 바뀌고 stale frame을 사용하지 않아야 한다. 이 동적 연결과 이후 제안하는 낙상·접촉 계측의 시뮬레이터 검증은 아직 미확인이다.

## 2. D1-B 조건 여섯 가지

아래는 실행자가 선택지를 다시 임의로 바꾸지 않도록 정한 **계약 제안**이다. 팀장 확정 전에는 승인된 실행 계약으로 표시하지 않는다.

### (1) Encoding: 두 판을 분리하고 각각 정상·permutation 대조

동일 E1 checkpoint에서 다음 네 teacher 조건을 둔다. 학습은 추가하지 않는다.

| 평가 이름의 조건 부분 | no-hit 처리 | height 공간 순서 |
|---|---|---|
| `legacy-normal` | 원본 -2.5 | 정상 |
| `legacy-perm2026` | 원본 -2.5 | 고정 permutation |
| `g0plus-normal` | raw +1, 최종 +2.5 | 정상 |
| `g0plus-perm2026` | raw +1, 최종 +2.5 | 같은 고정 permutation |

전체 이름은 예를 들어 `D1B-gap-v1/E1-s42-m20499/g0plus-normal/...`처럼 실험·훈련 seed·checkpoint·encoding을 모두 포함한다. legacy-normal은 E1 원본 가중치·관측 처리의 **새 gap 과제 성능**, g0plus-normal은 같은 가중치의 **평가 시 관측 개입**이다. 어느 쪽도 기존 8종 E1 성능에 이어 붙이거나 G0로 새로 학습한 정책이라고 부르지 않는다.

주 질문은 **각 encoding 안의 정상 대 permutation 차이**다. encoding 간 차이는 별도의 입력 개입 효과로 보고한다. permutation은 `NumPy RandomState(2026).permutation(187)`의 실제 배열과 해시를 저장하고 모든 env·step·checkpoint에서 같은 배열을 사용한다. runtime에서 term 이름·차원으로 실제 slice를 확인한다. probe의 `[88, 187]`을 다른 설정에 맹목적으로 하드코딩하지 않는다. permutation은 인코딩 후의 해당 block에 한 번 적용한다.

teacher는 deterministic mean, obs noise·push는 off로 둔다. student는 height만 바꾼 동일 body 입력의 행동 차 ≤1e-6을 확인하고, 동일 지형·초기 상태의 student rollout을 대조로 하나 둔다. 이 조건에서 height를 쓰지 않는 student의 네 판을 각각 재생할 필요는 없다. 단, actor 입력 밖에서 height로 명령·종료를 바꿔서는 안 된다. 모든 조건에 같은 독립 GT 종료 규칙을 적용한다. 후보 성능의 noise on 확인은 별도 단계다.

E1은 `model_20000`·`model_20499`를 각각 평가한다. 둘을 확대 전/후라고 단정하지 않는다. E2도 실제 끝난 동일 iteration 목록으로 맞춘다. 각 기하·명령 cell은 100 episode/조건, 경계·채택 후보는 규칙을 바꾸지 않고 500으로 확대한다. 서로 다른 checkpoint의 100개 env를 독립 학습 반복으로 세지 않는다.

### (2) Gap 기하·시작·명령·종료 동결

**주 시험은 중앙 platform에서 바깥 bank로 한 번 건너는 바닥 없는 mesh gap이다.**

| 항목 | 제안 값 또는 생성 규칙 |
|---|---|
| tile / 중앙 platform | 9×9m / 3×3m. 로컬 중앙 (0,0), 양 bank 상면 z=0, 상자 두께 1m |
| gap 폭 | 0.10·0.20·0.30m. cell마다 `gap_width_range=(w,w)`로 직접 고정. difficulty는 0.5로 기록하되 폭을 난이도 구간 무작위 값으로 만들지 않음 |
| 평지 대조 | 같은 출발·명령·goal에서 gap을 메운 폭 0의 연속 지면. 퇴행과 방향별 원래 추종 실패를 분리 |
| 바닥 | 주 시험에는 없음. 다른 plane·인접 tile·테두리가 틈 아래를 메우지 않는지 실제 collision/raycast 대상 모두 검사. 깊은 바닥 대조를 추가하면 별도 geometry 이름 사용 |
| world 이동 경로 | +X, y=0. 안쪽 lip x=1.5, 바깥 lip x=1.5+w |
| 시작점 | base xy=(0.70+δ,0)m, δ∈[-0.10,+0.10]를 episode manifest에 저장. lip까지 nominal 0.80m. 네 발 footprint가 중앙 platform 안에 충분히 들어오는지 확인 |
| 초기 z·상태 | 기본 joint pose를 공통 PD로 1초 안정화한 **접지 상태**를 조건별로 복원. root·joint 상태·DR·actuator/관측 history 초기화 규칙을 동결. 교란한 teacher마다 따로 안정화해 서로 다른 시작 상태를 만들지 않음. 복원 일치 미확인 시 본 평가 보류 |
| 지형 seed / 초기화 표본 | validation 지형 seed 12000. episode ID 1000~1099의 시작·DR 목록을 명시적으로 생성·저장하고 모든 조건에 같은 목록 주입. global seed만 같다고 짝이 같다고 가정하지 않음 |
| 제한 시간 | 접지 시작 t=0부터 최대 20초. 낙상은 t=0부터 센다. 추종 MAE의 첫 1초 제외와 낙상 면제를 혼동하지 않음 |
| 통과 goal | base가 x≥1.5+w+0.80에 도달, 네 발 각각 바깥 bank의 유효 touchdown을 한 번 이상 기록, 이후 같은 명령으로 0.50초 생존. 네 발의 **동시** 접촉을 요구하지 않음 |
| 경로·추종 | goal 확인까지 최대 |y|≤0.30m와 고정된 Q1 기준을 함께 보고. 완료 즉시 episode 종료. 시간 내 미도달·경로 이탈·추종 미달·낙상을 분리 |

방향 0·45·90도는 **이번 안에서는 몸체에 대한 이동 명령 방향**으로 정의한다. world 경로는 모두 틈에 수직인 +X다. 이렇게 해야 90도가 틈과 평행하게 걷다 끝나는 시험으로 바뀌지 않는다.

| 방향 α | 초기 body yaw | body 명령 (vx, vy, wz) | world 평면 명령 |
|---|---:|---|---|
| 0도 | 0 | (0.30, 0, 0) | (+0.30, 0)m/s |
| 45도 | -π/4 | (0.30/√2, 0.30/√2, 0) | (+0.30, 0)m/s |
| 90도 | -π/2 | (0, +0.30, 0) | (+0.30, 0)m/s |

**확인됨:** 이 좌표 변환은 CPU에서 세 경우 모두 확인했다. 이는 같은 간격을 전진·대각·횡이동으로 건너는 비교이며, bank 법선에 대해 45도로 진입하는 기하 시험과는 다르다. 후자는 별도 incidence-angle 조건으로 추가하고 실제 경로상 빈 길이를 재야 한다. 정사각 고리의 모서리 방향은 단순히 같은 폭의 반복이 아니다.

위 주 시험은 3폭×3방향=9 cell, 평지 대조 3 cell이다. 순차 batch로 평가하고 배치 변경에도 초기 조건을 보존한다. **4m gate는 적용하지 않는다.** x≈0.7에서 4m 전진하면 9m tile의 x=4.5 경계를 넘을 수 있다. 대신 위의 lip 상대 goal을 사용하고 결과를 `D1B-gap-traversal`로 부른다. 기존 4m Q3와 같은 성공률로 합치지 않는다. goal 뒤 0.5초와 레이 footprint까지 tile 안에 머무는지도 기하 검사한다.

GT 메시로 시작점·goal·corridor를 채점하는 것은 허용하지만, 그 정보로 로봇을 조향하거나 hidden heading hold를 넣지 않는다. 같은 평지 대조에서부터 특정 방향이 미달하면 gap 인지 부족으로만 해석하지 않는다. 변경된 저속/대각 Q1을 사용한다면 ASTRA 4의 상대 MAE 제안을 별도 Q 판으로 확정하고 모든 조건에 동일 적용한다.

### (3) 무접촉 추락: ray 평균 대신 고정된 bank 높이 사용

이 규칙은 **양 bank가 같은 높이인 위 D1-B gap 전용**이다. `z_ref`는 실제 collision mesh의 bank 상면 world z로 episode 시작 전에 고정한다. 현재 ray hit 평균이나 몸통에 따라 내려가는 값을 기준 높이로 사용하지 않는다.

- 기존 base contact >1N·기울기 >60도 0.20초 유지 판정은 보존한다.
- 추가 추락: `base_z < z_ref - 0.10m` **그리고** `world_vz < -0.20m/s`가 0.10초 연속이면 실패. body-frame vz를 쓰지 않는다.
- 깊은 추락 보완: `base_z ≤ z_ref - 0.50m`면 속도·접촉·레이 유무와 무관하게 실패. 틈 아래에서 걸려 수직 속도가 0이 되거나 별도 깊은 바닥에 닿아도 놓치지 않는다.
- 발밑 local scanner의 `all +inf`는 `all_local_miss`로 따로 기록하며, **그것만으로 추락으로 세지도 않고 추락의 필수 조건으로 삼지도 않는다.** 점프·정상 높이의 일시적 미관측을 추락으로 세면 안 되고, 좁은 틈에서는 로봇이 빠져도 일부 레이가 bank를 맞힐 수 있다.
- dt=0.02초이면 0.10초 유지는 첫 시각부터 마지막 시각까지 6개 표본, 0.20초는 11개다. 실제 timestamp 차로 확인한다. 실패는 처음 감지된 뒤 latch하고 자동 reset 전 root·속도·접촉을 저장한다. post-reset 상태를 정상 생존으로 이어 붙이지 않는다.
- base/속도 NaN은 하네스 오류다. 정해 둔 평가 영역을 정책이 벗어난 경우는 경로 실패로 기록하며, 메시 바깥 no-hit를 gap 성공·정상 구멍 탐지로 해석하지 않는다.

**확인됨:** 이 추가 규칙의 CPU 합성 궤적 10개를 먼저 시험했다. 구현 파일은 만들지 않았다.

| 답을 아는 궤적 | 결과 |
|---|---|
| z=+0.38, v=0, 정상 hit / 전부 no-hit | 둘 다 추락 아님 |
| z=0.38−4.905t², vz=−9.81t, 전부 no-hit | dt=0.02에서 t=0.42초 감지 |
| 같은 자유낙하, 일부 bank 레이는 계속 finite | 똑같이 0.42초 감지 |
| z=-0.60, vz=0 | 즉시 감지 |
| z=-0.11·vz=-0.21이 0.08초 / 0.10초 지속 | 앞은 미감지, 뒤는 감지 |
| 정상 높이 위의 점프 후 착지, 일시 no-hit | 추락 아님 |
| 감지 뒤 정상 높이로 reset | 실패 유지 |
| base NaN | 유효 궤적으로 수용하지 않음 |

**미확인:** 이 문턱이 실제 Go2 동역학에서 오탐·누락 없이 작동하는지는 아직 시험하지 않았다. 본 평가 전 동일 하네스에서 정상 보행·접촉 없는 제어된 낙하·기울어 걸림·정상 도약·reset 경계로 확인해야 한다. 실측 실패율을 보고 문턱을 움직이지 말고 오류가 있으면 계약 판을 올려 양군 모두 다시 잰다.

### (4) 이번에 필요한 발 착지 계측의 최소 범위

최소한 네 발의 이름·world 위치/속도, 접촉력과 시각, 실제 foot collider의 지면 투영 footprint, touchdown·liftoff, bank/void 분류를 저장한다. foot body 원점만 찍어서 발바닥이 전부 지지됐다고 판단하지 않는다. collider의 크기·형상·pose는 사용 USD에서 읽고 동결한다.

유효 touchdown은 각 발의 상면 지지 접촉이 **연속 두 policy 표본에서 수직력 >1N**이고, 실제 top collision surface와 발의 접촉 위치가 대응하는 사건이다. 사건 시각은 두 번째 표본으로 고정한다. 가능하면 contact point·normal을 직접 쓰고, 발 위치와 힘만으로 근사하면 그 한계를 명시한다. 벽면 접촉, 틈 아래 바닥 접촉, 몸통 충돌은 바깥 bank의 정상 착지로 세지 않는다.

위험 touchdown은 footprint의 일부가 지지 상면 밖이거나 상면 안쪽 여유가 0.02m 미만인 경우다. mesh의 삼각형 내부 변이 아니라 실제 **지지 영역의 외곽 경계**까지 거리를 잰다. 접촉 유지 중 접선 방향 이동거리·속도를 slip 지표로 함께 저장한다. 위험 착지 수/전체 touchdown 수, touchdown 없이 추락한 episode 수를 별도로 적어 분모 밖으로 사라지는 실패를 막는다. 각 episode에 접촉 없는 swing이 있다는 이유만으로 위험 착지라고 부르지는 않는다.

이 최소 계측을 넣지 못하면 `base-goal 도달·생존·추종`까지의 예비 결과만 낸다. 네 발의 유효 착지 goal과 위험 착지 20% 감소는 미확인으로 남기고, `지형에 맞는 디딤 선택 확인` 또는 D1 전체 통과를 선언하지 않는다. 동등 시간창에서 같은 foot 계측을 정상·permutation 양군에 적용해야 한다.

### (5) Stepping stones: 이번 주 gap 행렬에서는 제외

**제안:** 지금은 gap의 encoding·무접촉 추락부터 분리하고, 희소 발판은 D1-B2라는 별도 과제로 남긴다. 현재 평평한 stepping_stones 열을 추가해 지형 수만 늘리지 않는다.

추가할 때의 평가 전용 첫 설정은 `horizontal_scale=h=0.025m`, 돌 폭 `12*h` 고정(약 0.30m), 돌 사이 거리 `6*h` 고정(약 0.15m), platform `120*h`(3.0m), `stone_height_max=0`, `holes_depth=-10m`를 후보로 둔다. **확인됨:** Python에서 실수 리터럴을 바로 나누면 `int(0.30/0.025)=11`, `int(0.15/0.025)=5`다. 격자 수로 값을 구성한 경우 12·6칸이 나오는 것을 CPU에서 확인했다. 실제 생성기에서도 정수화 결과 12·6·120을 assert하고 최종 메시 폭을 재야 한다. 이 값은 물리적 통과 가능성이 검증된 수치가 아니므로 실제 foot footprint·관절 도달 범위와 비교해 본 평가 전에 동결한다.

raw height field의 낮은 칸이 존재하는지만 보면 안 된다. slope correction과 mesh 변환 **후** 실제 폭·돌 크기·지지 연결성이 남는지, CPU/GPU ray가 돌 상면과 깊은 바닥을 각각 맞히는지 검사한다. height-field는 깊은 finite 바닥이 있는 과제이므로 무바닥 mesh gap의 no-hit 시험과 구분한다. 부재 표면이 필요하면 독립 mesh 발판과 바닥 없는 빈 공간으로 새 지형을 만들고 별도 이름을 쓴다. 중앙 platform 밖으로 실제로 진입하는 동작도 확인해야 한다.

### (6) Validation / holdout: seed와 기하를 둘 다 분리

**제안:** validation은 위 9개 gap cell과 평지 대조, terrain seed 12000·episode ID 1000~1099다. 개발 중 반복해서 보는 자료이며 G1/P1 선택·디버깅에 사용할 수 있다.

holdout은 terrain seed 22000·episode ID 2000~2099, platform **2.5m**, 폭 **0.15·0.25m**, body 이동 방향 **-45·-90도**의 4개 gap cell과 해당 평지 대조로 봉인한다. 방향은 같은 식 `yaw=-α`, `(vx,vy)=0.30(cosα,sinα)`로 정의하므로 여전히 world +X로 건넌다. 시작·goal은 고정 좌표 1.5를 재사용하지 말고 해당 platform 반폭으로 계산한다. 나머지 속도·채점·종료 규칙은 같다.

**확인됨:** 현재 `gap_terrain`은 주어진 폭·platform·size를 상자로 만들며 함수 자체에 난수 추출이 없다. seed만 바꾸면 같은 기하일 수 있다. local 좌표로 정규화한 메시·폭·platform·접근 방향·배치 manifest를 비교해 validation과 holdout이 단순 world 이동 복사본인지 검사한다. 초기 상태·DR도 별도의 manifest를 사용한다.

G1의 gap 학습 platform은 3.0m로 고정하고 holdout platform·방향 조합을 튜닝에 사용하지 않는다. 학습에 연속 폭 범위를 사용한다면 holdout의 폭 자체는 이미 그 범위 안일 수 있으므로 `미학습 폭`이라고 부르지 않는다. 이것은 **같은 gap 계열의 새 기하·명령 조합 평가**다. 새로운 지형 종류의 일반화는 별도의 sparse foothold·rails 등에서 확인해야 한다.

holdout은 checkpoint·threshold·encoding 선택을 끝낸 뒤 E1/E2 양 seed의 고정 후보에 적용한다. 결과를 보고 다시 수정하면 그 holdout은 개발 자료가 되므로 새 holdout을 정한다. 동일 training seed의 100 episodes와 독립 training seed 두 개는 분리해 보고한다.

## 3. E2를 기다리는 범위와 G1 순서

**제안:** E2 완료를 기다리지 않고 E1의 D1-B를 먼저 할 수 있다. 단, 이번 의뢰는 읽기 전용 검토이므로 여기서 실행하지 않는다. 순서는 실제 G0 관측 연결·오류 분류 → 합성 및 시뮬레이터 추락/착지 smoke → validation의 E1 두 checkpoint → 같은 manifest의 E2다. E2의 10/12 낮 완료는 의뢰서의 예정이며 이번에 진행률을 실측하지 않았다. 두 seed 결과 전에는 채택·원인 확정을 보류한다.

**G1의 encoding 결정 자체가 D1-B 성능 결과를 기다릴 필요는 없다.** 정상 no-hit를 raw +1·최종 +2.5로 정의한 G0는 입력 의미를 맞추는 계약이다. E1이 어느 encoding에서 더 잘 걷는지에 따라 임의로 바꾸면 평가 결과로 계약을 맞추는 셈이 된다. 다만 실제 경로 연결, NaN/pose 오류 분리, no-hit 계측, 팀장 확정은 먼저 끝나야 한다.

G1을 시작할 때는 같은 부모 checkpoint에서 분기한 `p_gap=0`과 `p_gap=0.10` **양군 모두 동일 G0**를 사용한다. geometry 범위·명령·reward·resume 상태·예산도 양군 공통으로 동결한다. legacy E1과 G0+gap 학습군만 비교하면 encoding과 노출 효과가 섞인다. legacy 대 G0 학습 효과를 알고 싶으면 같은 지형 mixture의 별도 대조가 필요하다.

G1 **학습 실행**은 E1의 최소 gap 진단으로 하네스가 닫혔는지 확인한 뒤 결정하는 편이 타당하다. D1-B에서 teacher까지 실패하면 입력 분포·물리적 난이도·gap 노출을 함께 검토하고, teacher만 상대적으로 유리하면 P1을 검토할 근거가 된다. permutation 차이가 없다고 height가 본질적으로 불필요하다고 결론 내리지는 않는다. seed 43 반복 전의 결과는 선별 결과로 남긴다.

## 4. 팀장 확정 필요 항목과 최종 판정

계약 변경으로 확정이 필요한 항목은 다음과 같다. 이번 검토자의 제안을 팀장 승인으로 기록하지 않는다.

- legacy/G0를 분리한 D1-B 행렬과, G1·P1 양군의 G0 공통 사용.
- 0·45·90도의 body 이동 방향 정의, 무바닥 3폭, lip 상대 goal을 사용하는 gap 전용 성공 규칙. 기존 4m Q3와 분리.
- bank 기준 추락 높이·속도·유지시간, 최소 발 계측 및 미구현 시 예비 결과 범위.
- 희소 발판의 별도 단계화와 validation/holdout의 기하·명령·초기화 목록.
- E1 선행 진단과 E2 반복의 실행 범위·예산. 기존 프로세스 종료나 다른 작업의 자원 회수는 포함하지 않음.

판정: **고친 뒤 진행**

G0의 저장 입력 수치 검사는 통과했다. 실제 관측 경로 연결과 오류 분류, gap 전용 추락·착지 관문은 아직 닫히지 않았다. 이 부분을 보완하고 위 계약을 확정한 뒤 D1-B를 실행한다. 이번에 정책 성능이나 실제 Go2의 gap 통과 능력을 새로 확인한 것은 아니다.

원자료 SHA-256: `rays.npz` = `385a89637fa2f9fbcb4b934ffcdac36c8fc8f2bf448bd1a05b39a97f7b2ba3ea`, `mesh.npz` = `4e882930a7091ed53241e7e893f205b0f3e40e7e06a086e7af8925db01641ce0`. 원자료는 저장소 밖 `R`에 있다. 이 결과 파일만 새로 작성하며 코드·원자료·다른 세션의 변경은 수정하지 않고 커밋·push도 하지 않는다.
