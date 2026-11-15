# EX-36A 좌우 대칭 학습 사전 설계
> 분류: A/정책학습 · 학습 · 보상 · 관측 · 파인튜닝
> 작성: 오흥재 · scripter 반영 · 2026-10-29
> 근거: 설치 Isaac Lab symmetry_cfg.py:13-52 · anymal.py:29-80,92-132,180-197,237-249 · 설치 rsl_rl/algorithms/ppo.py:46-95,231-343 · 아래 Go2 코드
> 요지: EX-36A m3000 이어 학습의 단일 처치 후보로 좌우 대칭 데이터 증강을 설계한다.
> 상태: 검토 초안 · 구현 및 GPU 실행 전 · 좌표 및 특권 관측 매핑 미확인

## 계약과 현재의 틈

Isaac Lab `RslRlSymmetryCfg`는 관측과 행동 동시 증강, 별도 mirror loss를 각각 켠다. 설치 `rsl_rl` PPO도 `symmetry_cfg`를 받아 PPO 미니배치에서 증강한다(`ppo.py:46-95,231-343`). ANYmal 예시는 원본·좌우·전후·대각 네 벌을 만든다. 여기서는 **좌우 원본과 반사본 두 벌만** 후보로 두고 `use_data_augmentation=True`, `use_mirror_loss=False`를 권고한다. 두 처치를 동시에 켜면 D37 단일 처치의 의미가 달라진다. 출처 논문은 Mittal 외, *Symmetry Considerations for Learning Task Symmetric Robot Policies*, ICRA 2024, DOI 10.1109/ICRA57147.2024.10611493 (`IsaacLab/docs/source/_static/refs.bib:178-185`).

현재 `StartRunner`는 지각망이 만든 actor 96열을 PPO 저장소에 먼저 저장한다(`foothold_s2/runners/start_runner.py:234-257,323-420`). 따라서 설치 PPO의 `symmetry_cfg`에 96열을 단순히 뒤집는 함수를 꽂으면 추정 잠재 51열이 물리적으로 반사되지 않는다. 학습 중 `history/depth/map`을 함께 반사한 뒤 I-E/TR-Net을 다시 계산하는 결선이 필요하다. 이 부분은 현재 **미구현**이며 EX-36A 이어 학습 DRY는 대칭 학습 준비 완료로 표시해서는 안 된다.

## Go2 좌우 반사 표

아래 관절 표는 `foothold_s2/robots/go2_kinematics.py:11-13`의 표준 이름 순서 가정이다. 실제 Isaac `robot.joint_names`와 action manager의 `joint_ids` 순서는 런타임에서 확인하고 이름으로 permutation을 만들어야 한다(`foothold_s2/tasks/s1_env_cfg.py:76-79`는 `joint_names=[".*"]`). `C:/isaac/ext/go2_rl_robotlab/resources/go2/urdf/go2.urdf:79,246,413,580`은 FL/FR/RL/RR hip 이름 근거다.

| 대상 이름 또는 0부터 시작한 칸 | 반사 뒤 값 | 부호 |
|---|---|---|
| FL hip 0 · thigh 1 · calf 2 | FR hip 3 · thigh 4 · calf 5 | hip만 반전 |
| FR hip 3 · thigh 4 · calf 5 | FL hip 0 · thigh 1 · calf 2 | hip만 반전 |
| RL hip 6 · thigh 7 · calf 8 | RR hip 9 · thigh 10 · calf 11 | hip만 반전 |
| RR hip 9 · thigh 10 · calf 11 | RL hip 6 · thigh 7 · calf 8 | hip만 반전 |

관절 위치 편차·속도·직전 행동·새 행동은 같은 permutation과 부호를 쓴다. 기본 hip offset 좌우 부호가 달라 위치 편차 표현에도 성립하는지 CPU 대조 후 실제 관절 순서 영수증을 남긴다. ANYmal 참조 부호는 `anymal.py:237-249`다.

| 관측 또는 학습값 | 좌우 반사안 | 확인 항목 |
|---|---|---|
| 명령 `(vx,vy,wz)` | `(vx,-vy,-wz)` | `s1_env_cfg.py:86`; 리샘플 모드도 오른쪽/왼쪽 맞교환 |
| 몸 각속도 `(wx,wy,wz)` | `(-wx,wy,-wz)` | `s1_env_cfg.py:84`; ANYmal 예시 `anymal.py:110-117` |
| 투영 중력 `(gx,gy,gz)` | `(gx,-gy,gz)` | `s1_env_cfg.py:85` |
| 몸 선속도 특권 `(vx,vy,vz)` | `(vx,-vy,vz)` | critic 664열의 별도 3열 또는 clean52 내부 3열 위치를 구분 |
| 발 접촉·발 지도 | FL↔FR, RL↔RR. 각 5×5 패치의 좌우 축도 반사 | `start_obs.py:5-6`, `start_perception.py:22-28` |
| 몸 정답 지도 32×16 · TR-Net rough/refined | 횡축만 반사 | `start_perception.py:22-28,117-131`; `start_obs.py:84-98`의 `ordering="yx"`를 실제 ray 배열과 대조하여 정확한 차원을 고정 |
| depth 영상 2×60×60 | 각 프레임의 가로 영상 축을 반사 | 카메라 extrinsic와 픽셀 좌우 방향 실측 전에는 미확인 |
| I-E 과거 10×45 | 각 과거 시점의 45열을 같은 표로 반사 | `start_perception.py:22-28,296-312`; reset 직전/직후 이력 혼입 금지 |
| I-E/GRU hidden · TR-Net hidden | 벡터 칸을 임의 permutation하지 않는다. 반사한 과거 시퀀스를 reset 경계에서 다시 replay해 생성 | `start_perception.py:273-315,315-367`; 기존 hidden을 복사한 증강은 잘못됨 |
| critic 특권 664열 | policy45 + 몸속도3 + 접촉4 + 지도512 + 발지도100 각각 반사 | `start_runner.py:186-245`; clean52 구성은 별도 열 지도 필요 |

## 구현 전 답을 아는 시험

1. 관절 이름 기반 permutation과 45열·지도·depth·critic 각 반사 함수를 두 번 적용하면 원본과 비트 단위 일치해야 한다. 힙 부호, 명령 vy/wz, 투영 중력 y 한 칸씩 변이해 첫 실패를 지정한다.
2. 저장본 EX-36A m3000을 CPU 로드해 동일 물리 입력과 좌우 뒤집은 입력의 정책 평균 행동을 비교한다. 원본 정책은 대칭으로 학습되지 않았으므로 두 행동이 꼭 일치해야 한다고 요구하면 안 된다. **차이의 원값**을 먼저 기록하고, 증강 뒤 1회 update에서 대칭 처치가 켜졌는지와 변화량을 본다. 이 대조는 물리 평가를 대체하지 않는다.
3. PPO 한 미니배치의 원본·반사본 개수, 유효 batch와 optimizer step, PPO 손실·지각 손실, Adam 상태, 학습 속도 및 첫 update peak 메모리를 답 아는 CPU 입력으로 비교한다. GPU 1회 속도 영향은 lead가 별도 승인한 짧은 실제 확인에서만 측정한다. 현재 미측정이다.
4. Go2 좌우 뒤집힌 상태가 좁은 발판 지형 자체와 접촉 물리를 보존하는지 확인한다. 비대칭 지형을 그대로 둔 채 관측만 반사하면 증강 표본이 유효하지 않을 수 있어 평가 지형별 표시가 필요하다.

## 미결정

`StartRunner`의 지각 latent와 PPO 저장소가 분리되어 있어 설치 PPO의 대칭 옵션만으로는 완결되지 않는다. reviewer와 verifier가 Go2 실제 관절 순서, ray grid 축, depth 카메라 좌우, critic clean52 열, 지각 재생과 PPO 증강의 동시점성을 확인한 뒤 구현 범위를 고정한다. EX-36A의 PPO·보상·환경 조건은 그때까지 바꾸지 않는다.
