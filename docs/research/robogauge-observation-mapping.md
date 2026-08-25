# RoboGauge 공개 정책 해부: 45차원 관측의 정확한 순서와 스케일

> 분류: 리서치
> 작성: 오흥재 · 2026-08-13
> 근거: 코드 확인
> 요지: 공개 최상위 정책 4종의 입력 45차원을 코드와 실행 양쪽으로 확정했고, 우리 env 관절 순서까지 실측해 변환 규칙이 완성됐다. 남은 것은 구현뿐이다.
> 상태: 확정

> 작성 2026-08-13 · 워크스테이션 세션 · 방법: RoboGauge·go2_rl_gym 저장소 코드 판독 + 로컬 체크포인트 4종 known-answer 실행 검증 + 우리 env 실측
> 표기: `확인됨` = 코드 실행으로 실측 · `코드확인` = 저장소 코드에서 읽음(실행 안 함) · `추측` · `미확인`
> 검증 스크립트·로그: foothold-lab `tools/robogauge/` (verify_policies.py · verify_extra.py · verify_log.txt)

## 결론 네 줄

1. **45차원의 순서·스케일을 확정했다.** 배포측(RoboGauge)과 학습측(go2_rl_gym) 코드가 동일하다. `코드확인`
2. **네 모델(symmetry·HIM·CTS·DreamWaQ) 전부 로드·실행에 성공했다.** known-answer 테스트 통과. `확인됨`
3. **CTS는 복합 입력이 아니었다.** [1,45] 단일 관측을 받고 히스토리는 내부 버퍼가 유지한다. 예전 실행 실패의 원인은 입력 차원·튜플 출력·배치 크기였다. `확인됨`
4. **DreamWaQ 파일을 찾았다.** HF 저장소 루트의 단일 파일이라 폴더만 뒤져서 못 찾았던 것. 내려받아 실행까지 검증. `확인됨`

## 1. 45차원 매핑 표

| 인덱스 | 항목 | 스케일 | 근거 (파일:줄) | 상태 |
|---|---|---|---|---|
| 0:3 | base_ang_vel | × 0.25 | RoboGauge go2.py:34,46 · go2_env.py:26 | `코드확인` |
| 3:6 | projected_gravity (수평 정지 = (0,0,-1)) | × 1.0 | go2.py:35,47 · math_utils.py:3-18 | `코드확인` + 자리 실측 |
| 6:9 | cmd (vx, vy, ωyaw) | **모델군별 상이** (아래 표) | go2.py:44,48 · go2_lab_config.py:18-20 | `코드확인` |
| 9:21 | q - default_dof_pos (12) | × 1.0 | go2.py:36,49 · go2_env.py:29 | `코드확인` |
| 21:33 | dq (12) | × 0.05 | go2.py:37,50 · go2_env.py:30 | `코드확인` |
| 33:45 | last_action (정책 원출력 12) | × 1.0 | go2.py:51,63 · go2_env.py:31 | `코드확인` |

- lin_vel 은 특권 관측에만 있고 **45차원 정책 입력에는 없다**. 자리를 남겨두면 전 항목이 3칸씩 밀린다. `코드확인`
- default_dof_pos = [hip ±0.1, thigh 0.8(앞)/1.0(뒤), calf -1.5]. `코드확인`
- 관절 순서는 **다리별 묶음 FL→FR→RL→RR × (hip, thigh, calf)**. 근거: go2.xml 관절 트리 + hip_dof_indices=[0,3,6,9]. `코드확인`
- 액션 적용: target = action × 0.25 + default. 제어 50 Hz. `코드확인`

### cmd 스케일은 모델군마다 다르다 (함정)

| 체크포인트 | cmd 스케일 | Kp/Kd |
|---|---|---|
| HIM · DreamWaQ · CTS · MoE-CTS (gym계) | × [2.0, 2.0, 0.25] | 20 / 0.5 |
| symmetry v5.1 (robotlab계) | × [1.0, 1.0, 1.0] | 25 / 0.5 |

HIM 에 [1,1,1] 을 쓰면 yaw 명령이 4배 어긋난다. `코드확인` (run_models.sh 의 task 매핑으로 판별)

## 2. 실측 검증 (known-answer tests) `확인됨`

시스템 python(torch 2.7.0+cu128)으로 실행. `KMP_DUPLICATE_LIB_OK=TRUE` 필요(OMP 중복 오류 실측 후 우회).

| 테스트 | symmetry v5.1 | HIM | CTS vanilla2 | DreamWaQ |
|---|---|---|---|---|
| [1,45] 0벡터 실행 | OK | OK | OK (출력 **튜플**) | OK |
| 표준자세 obs 10스텝 → 수렴 | 수렴, 편차 ≤0.152 rad | 수렴, ≤0.269 | 수렴, ≤0.298 | 수렴, ≤0.391 |
| gravity 부호 반전 반응 | 0.644 | 1.244 | 1.128 | 미시험 |
| [2,45] 배치 | 실패 | 실패 | 실패 | 미시험 |

- 0벡터·표준자세에서 목표 관절각이 기본 자세 ±0.4 rad 이내로 수렴: **매핑이 맞다는 간접 증거**.
- **배치 1 고정**: 내부 히스토리 버퍼가 [1,·,·]로 고정. 병렬 평가하려면 모델을 환경 수만큼 복제 로드해야 한다. `확인됨`
- 네 모델 모두 **stateful**(내부 히스토리: symmetry 10프레임 · HIM/DreamWaQ 6 · CTS 5). 에피소드 리셋 시 `model.reset()` 필수. `확인됨`
- 입력 정규화 통계는 **불필요**: 네 모델 모두 normalizer가 Identity. `확인됨`

## 3. CTS 미스터리의 답 `확인됨`

지난 조사에서 "45~320 단일 텐서로는 실행 안 됨, 복합 입력 추정"이라 적었다. 틀렸다.

> **CTS 는 [1,45] 단일 관측 하나를 받는다.** 히스토리 5프레임은 모듈 안의 버퍼가 알아서 유지한다.
> 예전에 실행이 안 된 이유는 셋 중 하나다: ① 1-D (45,) 입력(실패 실측) ② 출력이 튜플 `(action, (None, latent))`인데 텐서로 처리 ③ 배치≠1(실패 실측).

- 근거: exporter.py:130-135 (forward_cts) · actor_critic_cts.py:43,48,162-167 · 로컬 policy.pt 의 히스토리 버퍼 (1,5,45) 실측 일치.
- 같은 폴더의 policy.onnx 는 입력 형식이 다르다: [1,225] 항목별 스택. 혼동 주의. `코드확인`

## 4. DreamWaQ 행방 `확인됨`

HF `wty-yy/go2_rl_gym_data` **루트의 단일 파일** `go2_dwaq_119.5k_0.5054.pt`. 폴더/policy.pt 형태만 뒤져서 못 찾았던 것. 내려받아 [1,45]→[1,12] 실행까지 검증했다. 워크스테이션 `C:\isaac\checkpoints\robogauge\` 에 보관.

## 5. 우리 평가에 붙일 때: 변환 규칙 (전 항목 실측 확정, 2026-08-13)

우리 env 를 실제로 띄워 실측했다 (probe_joint_order.py, 로그 tools/robogauge/probe_joint_order.txt).

### 관절 순서: 예상대로 달랐다 `확인됨`

- 우리 env `robot.joint_names` 실측: **관절종류별 묶음** [FL_hip, FR_hip, RL_hip, RR_hip, FL_thigh, ... , RR_calf]
- RoboGauge: **다리별 묶음** [FL_hip, FL_thigh, FL_calf, FR_hip, ...]
- 변환 permutation (실측 근거로 확정):
  - 우리 → RoboGauge (q·dq·last_action 세 블록): `[0, 4, 8, 1, 5, 9, 2, 6, 10, 3, 7, 11]`
  - 정책 출력 12차원 → 우리 순서 (역재배열): `[0, 3, 6, 9, 1, 4, 7, 10, 2, 5, 8, 11]`

### 나머지 전제도 실측으로 닫혔다

| 항목 | 우리 env 실측 | 변환 |
|---|---|---|
| 관측 구성 | lin_vel 3 + ang_vel 3 + gravity 3 + cmd 3 + q 12 + dq 12 + action 12 + height_scan 187 = 235 | lin_vel·height_scan 버림 | 
| 관측 스케일 | **전부 raw (×1.0)** (velocity_env_cfg.py ObsTerm 에 scale 없음) | ang_vel ×0.25 · dq ×0.05 · cmd ×(모델군별 표) 적용 |
| joint_pos 항목 | 이미 (q - default) (joint_pos_rel) | 재배열만 하면 됨 `확인됨` |
| default 자세 | hip ±0.1 · thigh 0.8(앞)/1.0(뒤) · calf -1.5 | RoboGauge 와 **동일 값** (순서만 다름) `확인됨` |
| action 스케일 | 0.25 + default 오프셋 (Go2 오버라이드) | RoboGauge 와 **동일** : target 의미가 같다 `확인됨` |

남은 것은 확인이 아니라 **구현**이다: 위 표대로 235→45 변환기(재배열 + 스케일)를 짜서 eval_go2.py 에 붙이면 4종 정책을 우리 지형·우리 성공 정의(10m·무넘어짐·20초)로 채점할 수 있다. 단 배치 1 제약(2절) 때문에 평가 병렬화는 모델 복제로 푼다.

부수 확인: symmetry 학습 저장소(robotlab)는 비공개 추정이라 설정 주석과 체크포인트 실측으로만 파악한 상태. `미확인`

## 연결

- 공개 정책 전수 조사(점수표·라이선스) → [go2-pretrained-policies.md](go2-pretrained-policies.md)
- 우리 평가 파이프라인(성공 정의·기준선 86.7%) → [training-benchmarks.md](training-benchmarks.md)
- 프로젝트 흐름에서의 위치(Student 비교 상대) → FLOW §3
