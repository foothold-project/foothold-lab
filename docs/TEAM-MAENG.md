# 맹라현

지형 · 씬 · 시각화 · Blender · 3ds Max · Unity · Isaac Sim

역할 Scene · Viz · 팀 FOOTHOLD

## 맡은 것

FOOTHOLD의 Scene · Viz 담당으로서 사족보행 로봇이 시험받을 가상 지형과 씬을 설계·제작한다. 8/21 팀 미팅에서 디지털 트윈·씬의 main으로 정해졌다 `확인됨` ([8/21 팀 미팅](meetings/20260821-team-meeting.md)).

Isaac Lab에서 학습용 지형과 평가용 지형을 분리하고, 계단·경사·요철을 난이도별로 구성한다. 마찰·질량 조건을 바꿔 시험 시나리오를 만든다. 실측은 3D Gaussian Splatting으로 받아 평가 씬에 연결한다. 발표용 시각화는 학습 씬과 나눠 Path Tracing으로 제작한다.

학습에 쓰는 땅과 보여 주는 렌더를 한 씬에 섞지 않는 것이 이 자리의 일이다.

## 배경

Blender · 3ds Max · Unity · 프리미어 · 웹. 3D 그래픽과 시각화 툴을 다뤄 왔고, 이 프로젝트에서는 그 툴을 물리 시뮬레이터 안의 지형·씬 파이프라인으로 옮긴다.

## 강점

| 무엇 | 왜 이 프로젝트에 쓸모 있나 |
|---|---|
| 학습·평가 지형 분리 | 학습에 쓴 땅을 평가에 다시 쓰지 않게 시험을 나눈다 |
| 커스텀 지형·스캔 | 3DGS 메시를 다듬고 USD로 넣어 평가 씬을 만든다 |
| 학습 씬과 렌더 씬 | 학습은 물리, 발표는 Path Tracing. 한 씬에 섞지 않는다 |
| DCC 툴 | Blender·3ds Max·Unity로 에셋을 다루고 시뮬 포맷으로 넘긴다 |

## 도구

Blender · 3ds Max · Unity  
NVIDIA Isaac Lab (Isaac Sim)  
MuJoCo

## 시뮬레이터와 포맷

Isaac Sim이 씬·로봇·지형을 다루는 형식은 USD(Universal Scene Description, 3D 씬 포맷)다. 파일을 손으로 안 만들어도 시뮬레이터 안에는 USD로 들어간다.

Isaac Lab이 코드로 뽑는 학습용 험지(계단·경사 등)는 Blender가 없어도 된다.

Blender(또는 3ds Max)가 필요한 지점은 커스텀 지형·스캔·렌더 씬이다. 3DGS 메시를 다듬거나 USD로 내보낼 때 쓴다.

MuJoCo는 USD가 아니라 MJCF(XML)다. Isaac에서 학습한 뒤 엔진이 다른 환경에서도 보행이 유지되는지 볼 때 쓴다. 같은 지형을 쓰려면 변환이 한 번 더 필요하다.

## 연락

프로젝트 관련 논의는 GitHub 이슈 또는 디스코드에서.
