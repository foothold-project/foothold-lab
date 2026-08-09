# 시스템 아키텍처 결정 — Isaac Sim + ROS2 + 실기 Go2

> 작성 2026-08-09 · 워크스테이션 세션
> **이 문서는 "무엇을 어디에 설치할 것인가"의 결정 근거다.** 결론만 보려면 §5.

---

## 0. 왜 이 문서가 필요한가

Isaac Sim은 **Python 3.11**로 만들어졌고, ROS2 Humble은 **Python 3.10**을 쓴다.
이 하나 때문에 "둘을 어떻게 같이 둘 것인가"가 프로젝트 전체 구조를 가른다.

우리는 이 질문에 **두 번** 답했다. 첫 답은 틀렸고, 이 문서가 수정본이다.

---

## 1. 1차 결론과 그 오류

### 1차 결론 (2026-08-09 오후) — **폐기**

> Ubuntu 22.04 한 대에 ROS2 Humble 네이티브 + Isaac Sim 네이티브를 함께 설치.
> 규칙은 하나 — Isaac Sim을 실행하는 셸에서 Humble을 `source`하지 않는다.

근거로 든 것 3개:

| # | 근거 | 재검증 결과 |
|---|---|---|
| ① | NVIDIA 공식 문서가 이 구성을 기본 워크플로로 기술 | **부분확인** — 5.x 한정. 4.x는 정반대("source하고 실행하라"), 6.x는 또 다름 |
| ② | Isaac Lab 공식 `Dockerfile.ros2`가 한 컨테이너에 둘을 함께 설치 | ❌ **자기부정** — 아래 참조 |
| ③ | DDS가 파이썬 버전과 무관하게 통신 처리 | **부분확인** — 참이지만 논점 회피 |

### ② 가 왜 자기부정인가 — 이것이 결정적이다

`Dockerfile.ros2`를 실제로 열어보면, Isaac Sim + Humble을 함께 깔면서
**`.bashrc`에 `source /opt/ros/humble/setup.bash`를 넣는다.**

> 즉 **NVIDIA 자신은 "source 안 한다" 규칙을 지키지 않는다.**
> 그들은 격리를 **셸 규율이 아니라 컨테이너 경계**로 달성한다.

이 파일은 "네이티브 이중 설치해도 된다"의 증거가 아니라
**"컨테이너로 하라"의 증거**였다. 근거를 거꾸로 읽었다.

### ③ 이 왜 논점 회피인가

DDS가 파이썬 버전과 무관한 것은 **프로세스 *사이*의 통신**에 대해서만 참이다.
실제 사고는 **프로세스 *내부*의 라이브러리 로딩**에서 난다 —
py3.10용 `rclpy`를 py3.11 Isaac Sim이 import하면 즉사한다.

실사례: `No module named 'rclpy._rclpy_pybind11'`
(https://github.com/isaac-sim/IsaacSim/issues/17)

---

## 2. "규칙 하나"는 거짓 단순화였다

실제로 지켜야 하는 규칙은 최소 **4개**다:

1. `.bashrc` 전역 `source` 금지 — **그런데 이건 ROS2 공식 튜토리얼이 가르치는 표준 관행이다.**
   (https://docs.ros.org/en/humble/Tutorials/Beginner-CLI-Tools/Configuring-ROS2-Environment.html)
   팀원 5명 중 1명이라도 습관대로 하면 그 계정의 **모든 셸**(VSCode 터미널 포함)에서 붕괴.
2. 공식 `ros2 launch isaacsim run_isaacsim.launch.py` 경로 포기 — 이 워크플로는 source된 셸을 전제한다.
3. 커스텀 메시지(`unitree_go` 등) 워크스페이스를 **py3.10(로봇용) / py3.11(심 내부용) 두 벌** 유지.
4. `RMW_IMPLEMENTATION` · `ROS_DOMAIN_ID` · FastRTPS 프로파일을 팀 전체가 통일.

> **사람이 4개월간 4개 규칙을 5명 전원이 지켜야 성립하는 아키텍처는 취약하다.**

### 규칙이 깨졌을 때의 실제 사고 기록
- 심볼 충돌 크래시 `undefined symbol` — NVIDIA 모더레이터가 "source가 원인"으로 진단
  (https://forums.developer.nvidia.com/t/undefined-symbol-error-occured-while-importing-tf2-ros-packages-in-isaac-sim-2022-2-0/242832)
- **역방향 누출**: Isaac Sim 내부 lib 경로를 `.bashrc`에 넣으면 rviz2 등 ROS2 도구가 깨진다
  (https://www.stereolabs.com/docs/isaac-sim/ros2_integration)

---

## 3. 새로 발견된 제약 (1차 결론이 놓쳤던 것)

### 3-1. ⚠️ Blackwell(RTX 5090)은 **open kernel module 전용**  `확인됨`

NVIDIA 1차 문서: *"Blackwell and later are only supported by the open kernel modules"*
(https://us.download.nvidia.com/XFree86/Linux-x86_64/570.86.16/README/kernel_open.html)

- `nvidia-driver-580`이 아니라 **`nvidia-driver-580-open`** 을 설치해야 한다.
- 자동 설치가 proprietary를 고르면 **GPU 미인식 / 부팅 불가**. 실사고 보고 있음.
- Isaac Sim 5.1 최소 드라이버는 **580.65.06** (570 아님).
- Ubuntu 22.04 설치 자체가 5090에서 검은 화면으로 멈춘 사례 있음(iGPU 우회 필요).

### 3-2. ⚠️ Isaac Sim 5.1은 **이미 공식 지원 종료(EOL)**  `확인됨`

5.1 문서에 "no longer supported" 배너가 떠 있다(최신은 6.0).
우리가 방금 설치한 것이 그 5.1이다. Isaac Lab 2.3.x가 5.1.0을 핀하고 있어 당장은 문제없으나,
**"공식 문서가 기본 워크플로로 기술"이라는 근거의 무게를 낮춰 읽어야 한다.**

### 3-3. ⚠️ Isaac Sim 5.1 스트리밍은 **동시 접속 1명 한계**  `확인됨`

포트가 고정이라 커스텀 포트는 **6.0부터**.
(https://github.com/isaac-sim/IsaacSim/discussions/449)

> **"팀원 5명이 동시에 시뮬 GUI를 만진다"는 그림은 5.1에서 불가능하다.**
> 팀 운영 설계를 여기에 맞춰야 한다.

### 3-4. ⚠️ RMW(DDS 벤더) 분열 — **조용한 실패 위험**  `확인됨`

| | 기본 DDS |
|---|---|
| Isaac Sim ROS2 브리지 | **FastDDS** |
| `unitree_ros2` (실기 Go2) | **CycloneDDS 0.10.2 + NIC 바인딩 강제** |

**서로 다른 DDS 벤더는 상호 통신이 안 되고, 에러도 안 낸다.** 토픽이 그냥 0개가 된다.
(커널 원칙 2 — 조용한 실패를 소리 나게 만들 것)

### 3-5. ✅ Ubuntu 22.04 + Humble 선택은 **유지가 맞다** — 단 이유가 다르다  `확인됨`

`unitree_ros2` README: *"Ubuntu 22.04 - humble (recommend)"*. **Jazzy 미지원.**
(https://github.com/unitreerobotics/unitree_ros2)

> 즉 22.04를 고르는 이유는 Isaac Sim이 아니라 **실기 Go2가 강제하기 때문**이다.
> 24.04+Jazzy는 "미래지향"이 아니라 **로봇 공식 지원 밖으로 나가는 것**이다.

### 3-6. ✅ 수업(WSL Humble)은 우분투 멀티부트를 **서두를 이유가 아니다**

- Isaac Sim의 **WSL2 구동은 공식 미지원** (5.1 지원 OS 목록에 WSL 없음).
- 반대로 NVIDIA의 공식 Windows 경로가 **"Isaac Sim은 Windows 네이티브 + ROS2만 WSL2"** 다.
- **우리는 이미 Windows 네이티브 Isaac Sim을 갖고 있다.** 수업 주간(8/10~14)은 그대로 진행 가능.

---

## 4. 왜 컨테이너인가 — 5인 공유 관점 (1차 결론에서 통째로 빠졌던 것)

- 네이티브 apt는 **단일 장애점**이다. 한 명이 `apt upgrade`로 드라이버를 깨면 5명 전원 정지.
- 컨테이너의 학습 성능 페널티는 NVIDIA 공식 표현으로 **"negligible"**.
- Isaac Sim 라이선스는 **무료** (사내 R&D, 인원 무제한).

---

## 5. ★ 확정 아키텍처

```
┌─ 호스트: Ubuntu 22.04.5 (HWE 커널 6.8) ────────────────────┐
│  · NVIDIA 드라이버 580+ ★-open 계열★                        │
│  · Docker + nvidia-container-toolkit                        │
│  · ROS2 Humble 네이티브  ← 수업 호환 + 실기 Go2 배포용       │
│    └ CycloneDDS 0.10.2 + CYCLONEDDS_URI NIC 바인딩          │
│                                                              │
│  ┌─ 컨테이너: IsaacLab v2.3.x Dockerfile.ros2 ──────────┐   │
│  │  · Isaac Sim 5.1 + Isaac Lab + ROS2 Humble           │   │
│  │  · 학습(RL)은 headless                                │   │
│  │  · 격리를 ★사람의 규율이 아니라 컨테이너 경계로★      │   │
│  │  · 5인은 사용자별 볼륨/브랜치로 분리                  │   │
│  └───────────────────────────────────────────────────────┘   │
│                                                              │
│  관찰: WebRTC 스트리밍 (⚠️ 5.1은 동시 1명)                   │
└──────────────────────────────────────────────────────────────┘
```

### 유지 / 폐기

| | |
|---|---|
| ✅ **유지** | Ubuntu 22.04 + Humble (unitree_ros2가 강제), 멀티부트 자체 |
| ❌ **폐기** | "네이티브 이중 설치 + 셸 규율 격리"를 **주** 아키텍처로 삼는 것 |
| 🔄 **교체** | 격리 수단: 사람의 규칙 → **컨테이너 경계** |

### 일정에 미치는 영향
- **수업 주간(8/10~14)에 우분투를 서두르지 않는다.** Windows 네이티브 Isaac Sim + WSL Humble로 충분.
- **9월 첫 2주 안에 "심 정책 → 실기 Go2 토픽 발행" E2E 스모크를 1회 관통**시킨다.
  RMW·메시지 빌드 문제를 앞당겨 노출시키기 위함.

---

## 6. 이 결정이 프로젝트를 망칠 수 있는 시나리오 3개

### ① 11월의 이중 빌드 붕괴
팀이 unitree 메시지를 py3.10으로만 빌드해 4개월을 보내다가,
최종 단계에서 심 안에서 Go2 메시지를 구독하려는 순간 처음으로 import 실패를 만난다.
재빌드 중 의존성 지옥 → **sim-to-real 통합이 발표 3주 전에 시작도 못 한 상태.**
→ **해법: 9월 E2E 스모크.**

### ② 공유 워크스테이션 드라이버 전멸
팀원 하나가 `apt upgrade` 또는 CUDA 설치 중 메타패키지가 proprietary 드라이버를 끌어와
open 모듈을 밀어낸다. **Blackwell은 proprietary로 부팅 불가** → 5명 전원 며칠 정지.
→ **해법: 호스트 최소화 + `apt-mark hold` + 드라이버 변경은 지정 관리자 1인만.**

### ③ "심에서는 됐는데 로봇에서 침묵"
심은 FastDDS, 실기는 CycloneDDS로 각자 개발됨.
12월 리허설에서 심 검증된 launch를 Go2에 붙이자 **토픽이 0개.**
DDS 벤더 간 비상호운용은 **에러도 안 낸다.**
→ **해법: 실기 그래프는 CycloneDDS로 고정하고, 심↔실기 경계에 브리지 노드 1개를 두는 설계를 지금 확정.**

---

## 7. 아직 미확인 (정직하게)

- WSL2에서 Isaac Sim 5.x GPU 렌더링의 "공식 불가" 명문 조항은 **없다.**
  지원 OS 목록 부재 + 컨테이너 미지원 발언 + Vulkan 실패 보고의 **조합에 의한 판단**이다.
- `Dockerfile.ros2` 컨테이너 내부에서 bashrc source 상태로 브리지가 실제 어떤 라이브러리를
  로드하는지(내부 py3.11 lib 우선인지)는 1차 출처로 확정하지 못했다.

## 8. 열려 있는 질문 (Human 결정 필요)

1. **듀얼 5090 워크스테이션의 apt/드라이버를 만질 사람을 1명으로 고정할 수 있는가?**
2. **실기 Go2는 언제부터 팀 수중에 있는가?** — 9월 E2E 스모크가 물리적으로 가능한 일정인가?

---

## 부록: 이 문서가 반증한 출처

블로그 https://slow-motionn.tistory.com/205 (구현 https://github.com/hms-gymnopedie/IsaacSim_Setting)
의 *"같은 환경에 공존 불가 → 컨테이너 2개 분리 필수"* 라는 **전제는 과장**이다.
공존은 가능하다. 다만 **공존을 사람의 규율로 유지하는 것이 나쁜 선택**일 뿐이며,
결론(컨테이너를 쓴다)은 우연히 옳은 방향이었다.

`--net=host`만 쓰고 `--ipc=host`(또는 `-v /dev/shm:/dev/shm`)를 빠뜨리면
Fast DDS의 공유메모리 전송이 **조용히 실패**한다는 점은 블로그에 없다.
