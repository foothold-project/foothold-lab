# [FOOTHOLD] Unitree Go2 사족보행 강화학습 데이터 산출물 명세서

> 분류: 제출 산출물
> 작성: Claude 세션 (오흥재 지시, lead-lx) · 2026-11-20
> 근거: 팀장 11/20 11:02 지시 양식 · 학습 실행 EX-42-B-E1F 원본 설정 (`params/agent.yaml` · `params/env.yaml`) · 저장본 sha256 실측 · 계보 문서 `docs/research/20261119-lineage-6-canon3-m15500.md`
> 요지: 정책 가중치 (.pt) 와 학습 설정 (.yaml) 을 데이터 산출물로 낸다. 산출물 1 (START 기반 m15500) 은 채움 · 산출물 2 (AME-2 재현 m27000) 는 담당자가 채울 자리
> 상태: 산출물 1 확정 · 산출물 2 대기

## 1. 산출물 개요

본 프로젝트는 정적 (Static) 데이터셋을 쓰는 지도학습과 달리, 물리 시뮬레이터 (Isaac Sim / Isaac Lab) 안에서 에이전트가 실시간으로 상호작용하며 데이터를 만드는 **심층 강화학습 (Deep Reinforcement Learning)** 연구입니다. 그래서 학습 과정에서 쌓인 정책 신경망 가중치 (`.pt`) 와 환경 설정 데이터를 최종 데이터 산출물로 제출합니다.

```
FOOTHOLD_UnitreeGo2_RL_Data_Deliverable/
├── README.md                 # 이 문서 (개요 · 재현 설명)
├── model_manifest.json       # 모델 버전 · 하이퍼파라미터 표준 명세
├── 01_START_Baseline/
│   ├── model_15500.pt        # START 기반 학습 체크포인트 (누적 15,500 iter)
│   └── config_start.yaml     # 학습 환경 · 보상 함수 설정
└── 02_AME2_Reproduction/
    ├── model_27000.pt        # AME-2 기반 Go2 재현 체크포인트 (27,000 iter) · 담당자 추가 예정
    └── config_ame2.yaml      # 학습 환경 · 보상 함수 설정 · 담당자 추가 예정
```

## 2. 제출 모델 (산출물) 상세

| 구분 | 파일명 | 기반 논문 및 알고리즘 | 학습 스텝 (Iteration) | 주요 특징 및 비고 |
| :--- | :--- | :--- | :--- | :--- |
| **산출물 1** | `model_15500.pt` | **START** 기반 보행 제어 · PPO | 누적 15,500 iters | 지형 학습 전 기본 보행 정본. 속도 명령 (전진 · 옆 · 회전 · 느린 전진 0.1 m/s) 을 따르고, 깊이 카메라로 발밑 높이 지도를 복원해 함께 쓴다 |
| **산출물 2** | `model_27000.pt` | **AME-2** 기반 Go2 재현 | 27,000 iters | 험지 (Rough Terrain) 적응 · 보행 고도화 재현 모델 (담당자 추가 예정) |

### 산출물 1 · `01_START_Baseline/model_15500.pt`

| 칸 | 값 |
|---|---|
| sha256 | `13caeb4ae52dd41ab3c2d23f9e6e34801a2414aa811c3efd4b38895e9ce29df6` |
| 크기 | 30,361,227 바이트 (git LFS) |
| 학습 실행 | EX-42 E1F 단계의 250 번째 저장본. 처음부터 누적 15,500 iteration (부모 15,250 + 250) |
| 저장본 안의 `iter` 값 | 250 (이 실행 안의 회차). 누적 회차는 위 줄과 `model_manifest.json` 에 적었다 |
| 같은 정책의 ONNX (실기용) | `inbox/jay/20261103-policy-handoff/start-m15500-app/` (같은 sha256 의 `start-m15500.pt` 와 지도 켬 · 끔 ONNX) |
| 시뮬 성능 요약 (64 대 · 시드 42) | 평지 13 명령 생존 63 ~ 64 / 64 · 느린 전진 0.1 m/s 성공 57 (정답 지도) · 55 (복원 지도) / 64 · 깃발 따라가기 64 / 64 |
| 못 하는 것 | 발 디딜 곳이 띄엄띄엄한 지형 (틈 · 징검돌 · 좁은 빔) 은 아직 배우지 않음 |

성능 숫자의 출처와 측정 조건은 `docs/research/20261119-lineage-6-canon3-m15500.md` 에 있다.

## 3. 데이터 생성 환경 (Simulation Environment)

- **대상 하드웨어:** Unitree Go2 (12-DoF 사족보행 로봇)
- **시뮬레이터 · 라이브러리:** Isaac Sim 5.1.0 · Isaac Lab 2.3 (isaaclab 0.54.2) · rsl-rl-lib 3.1.2 · PyTorch 2.7.0
- **데이터 수집 방식:** 병렬 시뮬레이션 환경 3,072 개에서 PPO (On-policy) 롤아웃 경험 데이터를 축적. 한 번의 iteration 마다 환경당 24 스텝을 모아 정책을 갱신한다
- **제어 주기:** 물리 0.005 초 · 행동 4 스텝마다 = 50 Hz · 에피소드 최대 20 초
- **입력 관측 데이터 (Observation):** 관절 위치 · 속도, IMU 각속도와 투영 중력, 속도 명령, 직전 행동 (고유감각) + 깊이 카메라 영상에서 복원한 발밑 높이 지도의 잠재 특징. 학습 중에는 정답 높이 지도 (Height Scanner) 도 함께 쓴다
- **출력 행동 데이터 (Action):** 12 개 관절 목표 위치 오프셋 (Joint Position Targets · 기본 자세 기준 · 배율 0.25)
- **보상:** 속도 추종 (선속도 · 각속도) 과 자세 · 관절 토크 · 행동 변화 · 충돌 · 발 미끄러짐 벌점 등 가중치가 0 이 아닌 22 항. 항목과 가중치는 `config_start.yaml` 문서 2 의 `rewards`

## 4. 파일 검증 및 활용 방법

1. **받기:** `.pt` 는 git LFS 로 저장돼 있다.
   ```
   git lfs pull --include "deliverables/FOOTHOLD_UnitreeGo2_RL_Data_Deliverable/**/*.pt"
   ```
2. **무결성:** `sha256sum 01_START_Baseline/model_15500.pt` 값이 `model_manifest.json` 의 `sha256` 과 같아야 한다.
3. **로드:**
   ```python
   import torch
   ckpt = torch.load("01_START_Baseline/model_15500.pt", map_location="cpu", weights_only=False)
   policy = ckpt["model_state_dict"]          # actor · critic 가중치 (actor 입력 98 · 출력 12)
   perception = ckpt["perception_state_dict"] # 깊이 영상에서 높이 지도를 복원하는 모듈
   ```
   저장본에는 학습 재개용 상태 (최적화기 · 난수 · 커리큘럼) 도 같이 들어 있어 `weights_only=False` 로 읽는다.
4. **설정 읽기:** `config_start.yaml` 은 YAML 문서 두 개다 (문서 1 = 학습기 · PPO · 망 설정, 문서 2 = 환경 · 관측 · 행동 · 보상 · 종료 · 커리큘럼). Isaac Lab 이 남긴 `!!python` 태그가 있어 `yaml.unsafe_load_all` 로 읽는다. 파일 안의 `/mnt/...` 경로는 학습 기계의 로컬 경로 기록이라 재현할 때 자기 경로로 바꾼다.
5. **재현 (Play / Eval):** 같은 Isaac Lab 버전과 FOOTHOLD 학습 코드 (`foothold_s2` 패키지 · 과제 `FootholdS2-Go2-S2-SB-v0`) 위에서 이 설정과 저장본으로 추론 모드를 돌리면 같은 보행을 재현한다. 실기 Go2 에서는 같은 정책의 ONNX (2 절 표) 를 쓴다.
