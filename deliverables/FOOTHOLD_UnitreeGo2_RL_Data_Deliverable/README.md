# [FOOTHOLD] Unitree Go2 사족보행 강화학습 데이터 산출물 명세서

> 분류: 제출 산출물
> 작성: Claude 세션 (오흥재 지시, lead-lx) · 2026-11-20
> 근거: 팀장 11/20 11:02 지시 양식 · 학습 실행 EX-42-B-E1F 원본 설정 (`params/agent.yaml` · `params/env.yaml`) · 저장본 sha256 실측 · 계보 문서 `docs/research/20261119-lineage-6-canon3-m15500.md` · 산출물 2: 저장본 `tp424_in_p1_s5_from17000/model_16999.pt` (sha256 실측) · 같은 폴더 `params/agent.yaml` · `params/env.yaml` · `sync_record.txt` · 평가 묶음 `evalgz_tpevf24_b1` (평가 seed 42 · 1001 · 2002 · 3003)
> 요지: 정책 가중치 (.pt) 와 학습 설정 (.yaml) 을 데이터 산출물로 낸다. 산출물 1 (START 기반 m15500) 은 채움 · 산출물 2 (AME-2 재현 teacher · 누적 27,001 iter) 도 채움
> 상태: 산출물 1 · 2 확정

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
    ├── model_27000.pt        # AME-2 기반 Go2 재현 teacher 체크포인트 (누적 27,001 iter)
    └── config_ame2.yaml      # 학습 환경 · 보상 함수 설정
```

## 2. 제출 모델 (산출물) 상세

| 구분 | 파일명 | 기반 논문 및 알고리즘 | 학습 스텝 (Iteration) | 주요 특징 및 비고 |
| :--- | :--- | :--- | :--- | :--- |
| **산출물 1** | `model_15500.pt` | **START** 기반 보행 제어 · PPO | 누적 15,500 iters | 지형 학습 전 기본 보행 정본. 속도 명령 (전진 · 옆 · 회전 · 느린 전진 0.1 m/s) 을 따르고, 깊이 카메라로 발밑 높이 지도를 복원해 함께 쓴다 |
| **산출물 2** | `model_27000.pt` | **AME-2** 기반 Go2 재현 · PPO (Adam) · teacher | 누적 27,001 iters (이 학습 실행 17,000 + 출발 저장본 10,001) | 목표 지점까지 12 가지 험지 (계단 · 상자 · 연속 단차 · 징검돌 · 틈 · 팔레트 · 좁은 빔 등) 를 건너는 teacher 정책. 정답 높이 지도 29 × 13 위를 시선 창 12 × 10 으로 골라 attention 으로 읽는다. 12 지형 성공률 89.39 % (평가 seed 4 개 평균) |

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

### 산출물 2 · `02_AME2_Reproduction/model_27000.pt`

| 칸 | 값 |
|---|---|
| sha256 | `f4eaadb495f590e02c42103f524d0841616a58d33e73b2646ddeb34dc2fb1a41` |
| 크기 | 150,409,420 바이트 (git LFS) |
| 정책 역할 | **teacher**. 근거: actor 관측 그룹이 `teacher_mapping` · `teacher_prop` (`config_ame2.yaml` 문서 1 `obs_groups.actor`), 실험 이름 `go2_gaze_teacher`. `teacher_prop` 에 몸 선속도가 들고 `teacher_mapping` 은 시뮬 광선으로 만든 정답 높이 지도다 (실기에서 직접 못 얻는 특권 입력). 이 계열의 student 는 아직 학습하지 않았다 |
| 학습 실행 | AME-2 공개 코드 위 Go2 재현 계열. 출발 저장본 (완료 10,001 회) 에서 12 지형 과제 `Ame2-Go2-Gaze-N9P12` 로 17,000 회 학습해 누적 27,001 회. 5,000 회 뒤부터 PPO 를 Adam · fp32 · 에폭 4 × 미니배치 3 으로 바꿔 이어 학습했다. 이 실행 안 회차 17,000 · 누적 27,001 (= 출발 저장본 10,001 + 17,000). 실행 이름 `tp424_in_p1_s5_from17000` 의 17000 은 출발 저장본 뒤로 센 이 실행 안 회차다. 이름 `model_27000.pt` 는 산출물 양식을 따랐다 |
| 가중치 평균 | **평균본이다 (원본 2 개).** 완료 15,000 회 (`model_14999`) 부터 두 팟이 같은 저장본에서 500 회씩 따로 학습하고 actor · critic 가중치와 Adam 모멘트를 산술 평균 (학습률은 기하 평균) 하는 일을 4 번 되풀이했다. 이 저장본은 4 번째 평균 (`sync_record.txt` 「averaging 4」, 완료 17,000) 의 결과다. 원본 둘: `tp424_p1_s4` (seed 1001, sha256 `4ef7ec65…`) · `tp424_p2_s4` (seed 42, sha256 `216e2276…`), 둘 다 16,500 -> 17,000. 평균하지 않은 칸 (환경 · 커리큘럼 상태, 회차) 은 팟 1 원본 것. 평균 도구 `run/sync424.py` |
| 저장본 안의 `iter` 값 | 16,999 (마지막 갱신 번호). `go2_env_state.completed_updates` = 17,000 (출발 저장본 뒤 회차), `go2_env_state.start_from.source_completed_updates` = 10,001 |
| 설정 | `config_ame2.yaml` = 이 저장본 폴더의 `params/agent.yaml` · `params/env.yaml` 원본 그대로. 평균 도구가 팟 1 원본 실행 `2026-11-18_00-29-16_tp424_p1_s4_adam_fp32_4x3_from16500_to17000` 의 params 를 복사하고 그 자리에서 sha256 을 대조했다 (`sync424.py` 234 ~ 237 행). 2026-11-19 학습 볼륨에서 잰 sha256 도 두 곳이 같다 (env.yaml `48088f33…` · agent.yaml `855b1b57…`). 팟 2 원본의 params 는 seed 42 · run_name · log_dir 만 다르다 |
| 학습 환경 (3 절과 다른 점) | 병렬 환경 4,096 개 · 에피소드 최대 16 초 · 명령은 속도가 아니라 목표 지점 (몸 기준 x · y · 방향 차의 sin · cos, 2 m 로 자름) · 관측은 고유감각 49 (몸 선속도 포함) + 정답 높이 지도 29 × 13 × 3 · 보상 20 항 (모두 가중치 0 아님) · 강화학습 라이브러리는 AME-2 공개 코드에 든 rsl_rl 5.0.0 · Isaac Lab 2.3.2 (isaaclab 0.54.2) · Isaac Sim 5.1.0 · PyTorch 2.7.0 |
| 같은 정책의 ONNX (앱용) | `inbox/lim/20261103-policy-handoff/ame2-m27001/` (PR #878, `ame2-m27001.onnx` · 계약 · 시험 벡터. 원본 PyTorch 와 action 최대 차 2.9e-6) |
| 시뮬 성능 요약 (12 지형 × 10 단계 · 로봇 2,400 대 · 평가 seed 42 · 1001 · 2002 · 3003, seed 마다 12,000 에피소드) | 목표 도달 성공률 12 지형 평균 89.39 % (seed 범위 89.23 ~ 89.57 %). 지형별 4 seed 평균 % (학습 설정의 지형 이름): rough 99.38 · stair_down 99.35 · stair_up 97.97 · boxes_j 95.88 · discrete_j 97.5 · climb_up 96.85 · climb_down 97.75 · steps_j 96.43 · stones 55.73 · gap 62.75 · pallets 85.28 · beam 87.8 |
| 성능 출처 | 이 저장본으로 2026-11-18 에 돌린 벤치마크 묶음 `evalgz_tpevf24_b1` 의 결과 파일 넷: `20261118T050827Z_21902/evg_tpa4p1_16999_s42.pt` · `20261118T051720Z_22766/evg_tpa4p1_16999_s1001.pt` · `20261118T052610Z_23637/evg_tpa4p1_16999_s2002.pt` · `20261118T053504Z_24516/evg_tpa4p1_16999_s3003.pt`. 성공은 각 로봇의 첫 에피소드를 빼고 5 에피소드로 센다 (벤치마크 대기열 검사와 같은 규칙). 지형별 값은 이 파일들에서 2026-11-20 에 계산했고 `model_manifest.json` 의 `evaluation` 에 있다 |
| 못 하는 것 | 징검돌 (55.7 %) · 틈 (62.8 %) 은 아직 낮다. 특권 입력을 쓰는 teacher 라 실기 Go2 에 그대로 올릴 수 없다 (실기용 student 는 미확인 · 정해질 때까지 시뮬 트윈 전용). 이 저장본이 걷는 영상은 미확인 |

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
2. **무결성:** `sha256sum 01_START_Baseline/model_15500.pt` · `sha256sum 02_AME2_Reproduction/model_27000.pt` 값이 `model_manifest.json` 의 각 `sha256` 과 같아야 한다.
3. **로드:**
   ```python
   import torch
   ckpt = torch.load("01_START_Baseline/model_15500.pt", map_location="cpu", weights_only=False)
   policy = ckpt["model_state_dict"]          # actor · critic 가중치 (actor 입력 98 · 출력 12)
   perception = ckpt["perception_state_dict"] # 깊이 영상에서 높이 지도를 복원하는 모듈

   ame2 = torch.load("02_AME2_Reproduction/model_27000.pt", map_location="cpu", weights_only=False)
   actor = ame2["actor_state_dict"]      # AME2GazeModel teacher (입력 prop 49 · mapping 29x13x3, 출력 12)
   critic = ame2["critic_state_dict"]    # MoE 16 전문가 가치 함수 (보상 항마다 출력 20)
   optim = ame2["optimizer_state_dict"]  # Adam 상태 (학습 재개용)
   it = ame2["iter"]                     # 16999 (마지막 갱신 번호, 누적은 27,001)
   infos = ame2["infos"]                 # None
   state = ame2["go2_env_state"]         # 완료 회차 · 출발 저장본 · 학습률 · 커리큘럼 기록
   ```
   저장본에는 학습 재개용 상태 (최적화기 · 난수 · 커리큘럼) 도 같이 들어 있어 `weights_only=False` 로 읽는다.
4. **설정 읽기:** `config_start.yaml` 은 YAML 문서 두 개다 (문서 1 = 학습기 · PPO · 망 설정, 문서 2 = 환경 · 관측 · 행동 · 보상 · 종료 · 커리큘럼). Isaac Lab 이 남긴 `!!python` 태그가 있어 `yaml.unsafe_load_all` 로 읽는다. 파일 안의 `/mnt/...` 경로는 학습 기계의 로컬 경로 기록이라 재현할 때 자기 경로로 바꾼다. `config_ame2.yaml` 도 같은 꼴이고 (문서 1 = agent, 문서 2 = env), 경로는 `/network-volume/...` 이다.
5. **재현 (Play / Eval):** 같은 Isaac Lab 버전과 FOOTHOLD 학습 코드 (`foothold_s2` 패키지 · 과제 `FootholdS2-Go2-S2-SB-v0`) 위에서 이 설정과 저장본으로 추론 모드를 돌리면 같은 보행을 재현한다. 실기 Go2 에서는 같은 정책의 ONNX (2 절 표) 를 쓴다. 산출물 2 는 AME-2 공개 코드 (`leggedrobotics/ame2_minimal`) 와 FOOTHOLD Go2 코드 (`ame2_go2` 패키지 · 과제 `Ame2-Go2-Gaze-N9P12`) 위에서 같은 방법으로 재현하고, 앱 시뮬에서는 같은 정책의 ONNX (산출물 2 상세 표) 를 쓴다.
