# Unitree Go2 미경험 험지 적응 및 Sim-to-Real 프로젝트

> 요지: 다양한 험지에서 학습한 보행 정책을 미학습 험지에서 정량 검증하고, 실제 Go2에 이전해 사전에 정의한 환경에서 안정 보행을 구현한다.
> 작성 2026-08-19 · **원자료: 임석헌(부팀장) 정리 «프로젝트 보고서» (2026-08-18)** 를 웹판으로 재구성 · 용도: 팀 공유 · 미팅 의사결정 · 멘토 설명
> 중간 목표: 학습·평가 파이프라인 구축 (9/30 중간 발표) · 최종 목표: 실제 Go2 안정 보행 (12/11 최종 발표)

## 1. 프로젝트 한눈에 보기

본 프로젝트는 Isaac Lab의 Unitree Go2 험지 보행 환경을 출발점으로 한다. 여러 형태의 학습 지형을 구성해 강화학습 보행 정책을 만들고, **학습에 포함하지 않은 지형**에서 이동 안정성과 명령 추종 성능을 정량적으로 확인한다.

평가에서 확인된 취약점은 지형 구성 · 보상 설계 · 물리 조건 무작위화에 단계적으로 반영한다. 이후 시뮬레이션에서 확보한 정책을 실제 Unitree Go2로 이전하여, 사전에 정한 실제 환경에서 안정적으로 보행하는 과정을 최종 시연한다. 자율주행 기능은 이 과정이 완료된 뒤 여건에 따라 확장한다.

전체 흐름은 여섯 단계다.

[[flow6]]

## 2. 단계별 추진 계획

### 1단계 · 중간발표 (9/30): Custom Terrain 학습과 미학습 Terrain 평가

Isaac Lab에서 프로젝트 목적에 맞는 Custom Terrain을 구성해 Go2를 학습하고, **학습에 사용하지 않은 Terrain에서 보행 성능을 평가**한다. 평가 수치와 함께 시뮬레이션에서 로봇이 험지를 보행하는 장면을 시각화해 보여준다.

작업 순서:

1. Go2 Rough Terrain Baseline 재현
2. 프로젝트용 Custom Terrain 구성
3. RL Training 수행
4. Training / Test Terrain 분리
5. 미학습 Terrain Generalization 평가
6. Baseline과 학습 Policy 비교

**중간발표 제시 내용**: 학습·평가 과정, 학습 지형과 미학습 지형의 정량 결과, 시뮬레이션 험지 보행 영상 또는 실시간 시연.

### 2단계 · 최종발표 (12/11): 실제 Unitree Go2에 Policy 적용

Isaac Lab에서 학습한 정책을 실제 Go2에 적용한다. 모든 실제 험지를 대상으로 하기보다, 프로젝트 기간과 난이도를 고려해 **사전에 정의한 특정 실제 환경 1개**에서 보행을 구현하고 실제 로봇의 동작을 시연한다.

실기 적용 순서:

1. 학습 정책 확보
2. 실기 입력(관측) 구성
3. 정책 추론
4. 관절 제어

## 3. Isaac Lab 학습 및 Custom Terrain 전략

처음부터 환경을 새로 만들지 않고 **Isaac Lab의 Unitree Go2 Rough Terrain 환경을 기반으로 필요한 부분만 수정**한다.

### 반복형 학습 파이프라인

[[loop]]

핵심 루프는 위 순환이다.
초기에는 기본 Reward와 Observation 구조를 유지하고, 평가에서 문제가 확인된 항목만 단계적으로 바꾼다.

### Custom Terrain의 목적과 구축 순서

새로운 Terrain 자체를 만드는 것이 목적이 아니라, **다양한 보행 상황을 경험시켜 Policy의 Generalization 능력을 높이는 학습 환경**으로 쓴다.

| 구축 순서 | 내용 |
|---|---|
| ① 기본 Terrain 활용 | `Random Rough` `Slope` `Stairs` `Discrete Obstacles` `Boxes` 등 |
| ② Parameter 변경 | `계단 높이` `경사도` `장애물 크기` `표면 거칠기` |
| ③ Terrain 조합 | 기존 지형과 조건의 조합 |
| ④ 신규 Terrain 구현 | 조합으로 표현하기 어려운 경우에만 직접 구현 |

위 항목은 초기 검토 예시이며 전체 목록이 아니다. Isaac Lab이 제공하는 다른 Terrain과 진행 중 필요한 지형을 추가·교체할 수 있다.

## 4. Domain Randomization과 평가 체계

### Domain Randomization 적용 원칙

시뮬레이션과 실제 로봇의 차이에 대응하기 위한 Sim-to-Real 보완 수단으로 쓴다. **처음부터 전부 적용하지 않고, 기본 Policy의 취약점을 확인한 뒤 필요한 항목을 추가한다.**

| Randomization 항목 | 목적 |
|---|---|
| Mass | 실제 로봇 질량 차이 대응 |
| Center of Mass | 무게중심 오차 대응 |
| Friction | 실제 바닥 마찰력 차이 대응 |
| Motor 특성 | Joint 응답 차이 대응 |
| Sensor Noise | 실제 센서 오차 대응 |

### Unseen Terrain 4유형

| 유형 | 의미 | 예시 |
|---|---|---|
| Parameter Unseen | 같은 Terrain, 학습 범위를 벗어난 난이도 | 더 높은 계단, 더 큰 경사 |
| Combination Unseen | 학습 Terrain의 새로운 조합 | Slope + Rough + Obstacle |
| Structure Unseen | 학습에 없던 새로운 구조 | Gap, Stepping Stones |
| Physics Unseen | 유사 형상에서 물리 조건 변경 | 낮은 마찰력, 질량 변화 |

기간을 고려해 네 유형을 모두 평가하기보다, 프로젝트 목표와 Sim-to-Real에 의미가 큰 **일부 유형을 선정해 집중 평가**할 수 있다.

### 평가 지표와 비교군

평가 지표 예시: `Success Rate` `Fall Rate` `Velocity Tracking Error` `이동 거리` `Episode Survival Time`. (초기 예시이며, 실험 목적에 따라 안정성·에너지·자세 지표를 추가·조정할 수 있다.)

비교군: **Baseline vs Our Policy vs Our Policy + Domain Randomization** 을 동일한 Unseen Terrain·동일 지표로 비교한다.

> ### 핵심 검증 질문
> **우리가 학습한 Policy가 Isaac Lab Baseline보다 미학습 환경에서 더 높은 Generalization 성능을 보이는가?**

## 5. Sim-to-Real 및 Observation 설계

최종 목표는 학습한 Policy를 실제 Go2에서 실행하는 것이다. 범용 환경 대응보다 **선정한 실제 환경 1개에서의 안정 보행**을 현실적인 성공 기준으로 둔다.

주요 기술 이슈: 시뮬과 실기의 Observation 차이 · Joint Control 방식 · Action Scaling · Control Frequency · Sensor Noise · Communication Delay · 물리적 차이.

### Height Scanner 문제: 두 방향

Isaac Lab의 Height Scanner(가상 광선 높이맵)는 실제 로봇에서 그대로 쓸 수 없다. 두 방향을 비교한다.

| | 방향 A · Proprioception 중심 | 방향 B · 외부 센서 활용 |
|---|---|---|
| 구성 | `IMU` `Joint Position` `Joint Velocity` `Previous Action` `Command` | LiDAR 또는 Depth Camera로 지형 정보를 생성해 입력에 포함 |
| 검토점 | 구현 현실성이 높다. 지형 사전 정보 없이 목표 성능이 나오는지 확인 필요 | 정보는 풍부하나 실기 통합 난이도와 처리 부하가 크다 |

실기 실행 흐름:

[[deploy]]

## 6. 자율주행 확장과 역할 분리

자율주행은 핵심 목표가 아니다. RL Locomotion과 Sim-to-Real이 안정적으로 완료된 후 시간이 남을 경우 확장한다.

- **Nav2 = 어디로 이동할 것인가**: SLAM 지도와 센서 정보로 경로·이동 명령(cmd_vel)을 생성해 RL Policy의 command로 전달
- **RL Policy = 어떻게 걸을 것인가**: 이동 명령을 받아 관절 제어를 수행하며 지형에 적응해 험지 보행 담당

### 범위 관리 원칙

| 구분 | 포함 기능 | 착수 조건 | 완료 판단 |
|---|---|---|---|
| Core A | Unseen Terrain Generalization | 즉시 진행 | 분리된 Test Terrain에서 정량 비교 |
| Core B | Policy Sim-to-Real | 학습 Policy 확보 | 선정 환경 1개에서 안정 보행 |
| Extension | LiDAR + SLAM + Nav2 | Core A·B 안정화 + 잔여 기간 확보 | cmd_vel 연계 자율 이동 시연 |

**팀 운영 결정 필요**: SLAM/Nav2를 Sim-to-Real 이후에 진행할지, 일부 팀원이 병렬로 선행 준비할지 일정·인력 기준으로 판단한다. 단, 확장 기능이 핵심 목표의 일정과 검증 품질을 침해하지 않아야 한다.

## 7. 미팅에서 확정할 5가지

1. **중간발표 목표의 적절성**: Custom Terrain RL Training + Unseen Terrain Generalization 평가까지를 중간발표 목표로 설정하는 것이 현실적인가?
2. **최종 Sim-to-Real 목표의 적절성**: 사전에 정의한 실제 환경 1개에서 안정 보행을 구현하는 수준이 적절한가?
3. **실제 환경 선정**: Sim-to-Real 성과를 보여주면서도 기간 내 구현 가능한 실제 Terrain은 어느 수준인가?
4. **Height Scanner 대안**: Proprioception 중심 Policy부터 구현하는 것이 현실적인가, LiDAR/Depth 기반 정보를 포함해야 하는가?
5. **자율주행 개발 시점**: SLAM/Nav2는 Sim-to-Real 이후가 적절한가, 일부 병렬 준비가 좋은가?

## 8. 최종 정의와 산출물

> **프로젝트의 최종 결과 정의**
> "Isaac Lab에서 다양한 험지를 기반으로 Unitree Go2의 Locomotion Policy를 학습하고, 미학습 험지에서 Generalization 성능을 검증한 뒤, 해당 Policy를 실제 Unitree Go2에 이전하여 사전에 정의한 실제 환경에서 안정적인 보행을 구현한다."

| 발표 | Deliverable |
|---|---|
| 중간 (9/30) | 재현 가능한 학습·평가 파이프라인 · 분리된 Terrain 세트 · 정량 성능표 · Baseline 비교 결과 |
| 최종 (12/11) | 실제 Go2 Policy 실행 구조 · 선정 환경의 안정 보행 시연 · Sim-to-Real 이슈와 해결 과정 |

시간이 남으면 SLAM + Nav2 자율 항법으로 확장한다.

## 9. 우리 실측과의 연결 (웹판 추가)

이 계획의 여러 블록은 이미 실측이 시작되어 있다.

| 보고서 항목 | 현재 상태 |
|---|---|
| Baseline 재현 | 완료: 1,500 iter 실측, 통과율 86.7% → [학습 실측](research-training-benchmarks.html) |
| 평가 파이프라인 | v1 가동 중 (성공 정의·CSV·영상) → [학습 실측 §5](research-training-benchmarks.html) |
| Terrain 이해 | [Isaac Lab 지형 가이드](research-terrain-guide-isaaclab.html) (작성 임석헌) |
| 방향 A(Proprioception)의 실증 근거 | 공개 최상위 정책 4종이 전부 45차원 실물형 관측, 로드·실행 검증 완료 → [관측 매핑](research-robogauge-observation-mapping.html) |
| 비교군 확장 | 공개 정책과 같은 지표로 비교 가능 → [공개 정책 조사](research-go2-pretrained-policies.html) |
| 실기 전제(저수준 제어) | 공식 문서상 가능 확인(8/14), 실기 실측 대기 → [Go2 개체 점검 목록](field-check-go2-intake.html) |
