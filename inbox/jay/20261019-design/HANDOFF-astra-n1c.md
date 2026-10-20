> 분류: A/평가
> 작성: ASTRA (lead 의뢰) · 2026-10-21
> 근거: b60f84b2 · N1c 의뢰 · lead 04:52 A 결정 · Go2 URDF/USD · CPU 시험
> 요지: 듬성한 뒤·옆 칸의 시작점을 기본 자세 FK 네 발 XY 지지로 선택
> 상태: 구현 완료 · CPU 377 통과·1 건너뜀 · Kit 접촉 미확인 · 검토·병합 대기

# ASTRA-N1c 인계

작업 자리: `C:/mai/wt/foothold-lab/astra2-n1c`, 브랜치 `feature/astra2-n1c-jay`.
기준 커밋: `b60f84b2fefc310430f6a6b8d683632ea5ccd6f5`.
이슈: [foothold-lab #555](https://github.com/foothold-project/foothold-lab/issues/555).
sonnet 사본, GPU, Kit, 학습 프로세스는 건드리지 않았다. 병합·push하지 않는다.

## 구현과 결정

- START 4종과 기존 3종의 **뒤·옆 칸만** 적용한다. 앞·앞+회전·제자리 회전은 기존 생성기 원점과 리셋을 유지한다.
- `go2_kinematics.py`가 기본 관절 자세에서 FL·FR·RL·RR 발 충돌 구 중심을 FK로 계산한다. 반지름 0.022 m에 가정 여유 0.02 m를 더해 패치 경계에서 0.042 m 안쪽을 요구한다.
- 0°부터 345°까지 15° 간격으로 yaw를 탐색한다. 각 yaw에서 네 발이 놓일 수 있는 root 사각형들을 교차해 **연속 위치**를 찾는다. 위치 샘플 격자가 아니므로 격자 사이에 있는 좁은 해도 찾는다. `(4,4)`에 가까운 위치, 작은 yaw 순으로 선택한다. 임의의 연속 yaw 전체를 탐색했다는 뜻은 아니다.
- 명령은 몸 좌표다. 선택 yaw로 세계 좌표 이동 방향을 돌려 2초 기준 거리와 추가 0.3 m 여유가 듬성한 영역 안에 드는지 검사한다. 뒤의 기준 거리 상한 0.6 m, 옆의 관측 속도 무상한, 2초 명령+2초 0 명령은 유지한다.
- 기존 height-field의 같은 높이·완전한 변을 공유하는 사각형은 합쳐 내부 삼각형 경계를 가장자리로 오인하지 않게 한다. 다른 높이와 구멍은 합치지 않는다. 패치 추출 기준은 N1b의 실제 메시 위쪽 사각형이다.
- 네 발 자세가 없으면 `no_start`, `origin=null`, `eligible=false`로 기록하고 해당 뒤·옆 칸을 실행·판정에서 뺀다. `previous_origin/status/reason`은 **이전 규칙의 값을 보존하는 기록일 뿐**이다. 옛 시작점으로 재지 않는다. 원자료를 실패 0점으로 만들지도 않는다.
- lead 04:52 결정 A: 네 발 **XY 투영 지지만 판정**한다. N1b 원점 z와 로봇 cfg의 기본 root 높이는 유지한다. N1b 원점이 없을 경우 원래 생성기의 z를 기록하고 사용한다. 실제 지면 접촉·안정은 미확인이다. 높이 허용 오차는 새로 정하지 않았다.
- `axis3_starts.json`과 manifest에 선택 yaw, FK 발 좌표, 발별 지지 높이, 네 지지면 높이 최대 차, 발 중심 공중 간격을 남긴다. `sole_air_gaps_m`은 구 반지름을 뺀 발 구 바닥 간격이며 음수도 보존한다.
- 뒤·옆 칸은 반복 리셋에도 선택한 yaw와 `default_joint_pos`를 쓴다. 관절 ±5% 흔들기를 제거했다. 다른 칸의 리셋은 원래 함수를 호출한다. cfg 정규식과 실행 시 실제 `default_joint_pos`를 대조하고 다르면 중단한다. 기본 root 높이도 실제 값과 대조한다.
- 흔들기 조건이 달라졌음을 지형별 계획의 `reset_joint_jitter`, `reset_pose_jitter`, `comparison_note`와 요약 CSV의 `reset_condition`에 적는다. 서로 다른 리셋 조건의 이전 결과와 같은 조건이라고 주장하지 않는다.

## 모델 근거와 CPU 확인

- MGDP `legged_gym/resources/robots/all_dog/go2/urdf/go2.urdf`와 설치 robot_lab `C:/isaac/ext/go2_rl_robotlab/resources/go2/urdf/go2.urdf`를 읽었다. 고관절 원점 `(±0.1934, ±0.0465, 0)`, 옆 링크 0.0955 m, 허벅지·종아리 각각 0.213 m, 관절 축 x/y/y, foot 충돌 구 중심 오프셋 `(−0.002,0,0)`을 사용한다.
- 두 URDF를 독립적인 동차행렬 FK로 계산해 영 자세·기본 자세·비대칭 자세를 대조했다. 기본 자세는 설치 Isaac Lab `source/isaaclab_assets/isaaclab_assets/robots/unitree.py:159`의 hip ±0.1, 앞 thigh 0.8, 뒤 thigh 1.0, calf −1.5 rad와 같다. 평가 로봇 cfg에서 읽은 값이 달라지면 조용히 옛 FK를 쓰지 않는다.
- [공식 Go2 USD](https://omniverse-content-production.s3-us-west-2.amazonaws.com/Assets/Isaac/5.1/Isaac/IsaacLab/Robots/Unitree/Go2/go2.usd)와 상대 참조 `Props/instanceable_meshes.usd`를 임시 폴더에 내려받아 **OpenUSD만** 실행했다. `base/FL_hip_joint`, `FL_hip/FL_thigh_joint`, `FL_thigh/FL_calf_joint`, `FL_calf/FL_foot_joint`의 local pose와 `FL_foot/collisions/mesh_0`의 반지름·오프셋을 대조했다. USD는 thigh/calf의 joint X축을 localRot으로 Y축에 맞춘다. Kit를 기동하지 않았다.
- 답을 아는 0.2 m 돌·0.25 m 틈 격자: 정사각형 네 발 배치의 가능한 경우와 불가능한 경우를 구분했다. 실제 Go2 기본 자세도 해를 찾았고 네 발을 원래 돌 경계와 독립적으로 대조했다. 안전 내부 폭이 2 μm인 사례도 연속 위치 탐색으로 찾았다.
- 실제 설치 지형 생성기의 순수 함수만 AST로 읽어 기존 3종을 시험했다. START 4종도 실제 `build_tile` 결과로 뒤 0.3·좌 0.2·우 0.2를 시험했다. 원점만 돌 위인 입력과 옛 `(0.5,4)` 뒤 출발은 거부한다.
- 첫 새 시험은 미구현 FK 모듈에서 실패했다. 구현 뒤 관련 57개가 통과했다. 새 조건과 모순되는 N1b 시험의 'root가 발판 위'·'yaw=0'·'모든 START 칸은 존재' 기대를 네 발·선택 yaw·명시적 제외로 갱신했다.

## 난이도 0.5, seed 42의 CPU 계산

뒤 0.3·좌 0.2·우 0.2 세 방향 모두 네 발 규칙을 사용했다. 아래는 원점의 타일 좌표와 yaw이며 동역학 결과가 아니다. 기존 3종은 각각 seed 42로 생성했다. 여러 종을 묶으면 height-field 난수 소비 순서가 달라질 수 있어 실제 실행의 JSON을 정본으로 삼는다.

| 지형 | 뒤 / 좌 / 우 | yaw (도) | 비고 |
|---|---|---|---|
| stepping_stones_start (high) | ready / ready / ready | 180 / 180 / 180 | root `(4.17508,4,−0.04987)` |
| balance_beams | no_start / no_start / no_start | 없음 | 뒤·옆 실행·판정 제외, 옛 값은 기록만 |
| stepping_beams | ready / ready / ready | 0 / 0 / 0 | root `(4,4,0.00289)` |
| gaps_start | ready / ready / ready | 90 / 90 / 90 | root `(3.56860,4,0)` |
| stepping_stones | ready / ready / ready | 0 / 0 / 0 | 중앙 플랫폼 |
| gap | ready / ready / ready | 0 / 0 / 0 | 중앙 플랫폼 |
| floating_ring | ready / ready / ready | 15 / 60 / 30 | 방향별 위치가 다름 |

START 징검돌의 네 지지면 높이 차는 **0.08466 m**다. 기본 root 높이 0.4 m에서 발 구 바닥 간격은 FL·FR·RL·RR 순으로 **`[-0.00816, 0.07650, 0.06945, 0.06648] m`**다. 첫 발은 약 8 mm 파고드는 위치다. A 결정대로 높이를 올리거나 판정을 추가하지 않고 기록한다. XY 해를 찾았다는 것으로 접촉 문제 해결을 주장하지 않는다.

## 검증 명령과 다음 한 걸음

`isaac311/python.exe -B -m pytest foothold_s2 -q -p no:cacheprovider`를 사용했다. `CUDA_VISIBLE_DEVICES=''`, OMP/MKL 스레드 1, bytecode 쓰기 해제 상태다. 1차 전체 결과는 **376 통과·1 건너뜀, 158.38초**다. 격자 Go2 시험과 리셋 조건 표기를 추가한 최종 전체 결과는 **377 통과·1 건너뜀, 155.51초**다. 건너뛴 시험은 `test_deploy.py:297`의 ONNX 대조이며 이 작업 사본에 `logs/rsl_rl/foothold_s1a/2026-10-20_11-35-41/model_9.pt`가 없어 미확인으로 남는다. 별도 `-rs` 실행으로 건너뜀 사유도 확인했다. `git diff --check` 통과, 변경 파일의 em dash 0개.

다음은 lead의 검토·병합과 sonnet의 별도 Kit 예행이다. 새 결과 폴더에서 선택 위치·yaw·기본 관절이 실제 초기 발 XY와 일치하는지 확인한다. 30스텝에도 네 발이 다 닿지 않는 칸은 지지 높이 차·발별 간격과 함께 보고한다. 높이 기준 추가 여부는 그 뒤 lead가 정한다. START high만 측정, vy_obs 미측정 칸의 판정 제외, 고정 ±0.2 관문은 이번 변경에서 유지했다.

별도 예행 스크립트가 리셋 설치 함수를 직접 부르면 새 인자는 `install_fixed_reset(raw, names, generator.axis3_starts)`다. 저장소의 `run_eval.py` 호출은 반영했다. 외부 예행 스크립트는 수정하지 않았다. 생성기에는 해당 adapter cfg에서 읽은 `root_height_m`을 전달한다.
