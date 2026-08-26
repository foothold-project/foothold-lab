# ROS2 ↔ Isaac Sim: 파이썬 버전 충돌과 통합 방법

> 분류: 리서치
> 작성: 오흥재 · 2026-08-09
> 근거: 공식 문서
> 요지: 파이썬 충돌은 «같이 설치»가 아니라 «같은 셸에서 source» 할 때 난다. 통신은 DDS 층이라 버전과 무관하다.
> 상태: 확정

> 작성 2026-08-09 · 출처: 공식 문서 검증 + **WS 세션 원본 회수 완료(§회수 완료)**
> 상태: `확인됨`. 참조 블로그·구현 저장소 URL 대조 완료

## 문제: 두 도구의 파이썬이 다르다 `확인됨`

| | 파이썬 | 기반 |
|---|---|---|
| **ROS2 Humble** | **3.10** | Ubuntu 22.04 시스템 파이썬에 묶임 |
| **Isaac Sim 5.x** | **3.11** | 자체 배포 (cp311 wheel) |

같은 환경에 둘을 섞으면 의존성이 충돌한다. 팀장이 참조한 블로그 사례:
**컨테이너를 2개로 분리**(ROS 따로 / Isaac Sim 따로)하고 **통신만 주고받게** 구성.

## 검증: 그 방법이 정석인가?

**네, 정석 중 하나가 맞다.** 그리고 공식 경로가 하나 더 있다:

1. **프로세스/컨테이너 분리 + DDS 통신**: ROS2 는 원래 네트워크 미들웨어라
   **노드가 서로 다른 환경·기계에 있는 것이 기본 설계**다. 분리가 이상한 게 아니라 자연스럽다.
   클라우드 조사에서 발견한 공식 이미지(`nvcr.io/nvidia/isaac-sim:5.1.0` + ROS 이미지)로 그대로 구성 가능.
2. **Isaac Sim 내장 ROS2 Bridge** `확인됨`. Isaac Sim 이 **자체 빌드된 ROS2 라이브러리를 동봉**해서,
   확장을 켜면 파이썬 충돌 없이 시뮬 안에서 바로 토픽을 퍼블리시/구독한다.
   공식 문서: https://docs.isaacsim.omniverse.nvidia.com/latest/ros2_tutorials/index.html
   → **시뮬↔ROS2 연습(⑥단계 준비)은 이 브리지가 가장 짧은 길.**
3. **실기 배포 시점엔 이 충돌이 없다**. Go2 위(Orin NX)에는 Isaac Sim 이 안 올라간다.
   ROS2 + 정책 런타임(ONNX)만 올라가므로 파이썬 충돌 자체가 성립하지 않는다.

## 우리 계획에 미치는 영향

- 특강(8/10~14, 1일차에 Docker 실습 포함)과 정확히 이어진다. 특강의 Docker 가 곧 이 구성의 기초.
- ⑥단계 준비: **가상 Go2 + ROS2 Bridge** 로 실물 없이 통신 연습 (참고: Zhefan-Xu/isaac-go2-ros2)

## ✅ 회수 완료: 원 출처 (2026-08-09, WS 세션)

### 참조한 글

**블로그**: <https://slow-motionn.tistory.com/205>

원문 요지 그대로:
> *"Isaac Sim 5.1.0: Python 3.11 based (built-in) vs. ROS 2 Humble: Python 3.10 based (Ubuntu 22.04 default)"*
>둘을 한 환경에 강제로 넣으면 **패키지가 깨지고 런타임 오류**가 난다.

글쓴이는 개별 오류를 하나씩 잡는 대신 **컨테이너 격리로 통째로 우회**했다. 헤드리스 렌더링 · Fast DDS 설정 · rosdep 의존성 · GPU/Vulkan 접근을 미리 구운 이미지로 자동화했다고 밝힌다.

⚠️ **그 글에는 GPU 모델·구체적 에러 메시지·CUDA/torch 버전이 없다.** *예방적 아키텍처*에 대한 글이지 사후 디버깅 기록이 아니다. 즉 **"이렇게 하면 안 겪는다"는 알지만 "안 하면 정확히 뭐가 터지는지"는 그 글로 알 수 없다.**

### 구현 저장소

**<https://github.com/hms-gymnopedie/IsaacSim_Setting>**

| 컨테이너 | 베이스 이미지 | 담는 것 |
|---|---|---|
| **IsaacSim_Pegasus** | `nvidia/cuda:12.4.1-devel-ubuntu22.04` | Isaac Sim 5.1.0 스탠드얼론 · **Vulkan/X11**(헤드리스용 EGL 기반 Vulkan ICD) · PX4-Autopilot v1.14.3 · Pegasus Simulator |
| **ROS 2 Humble** | `osrf/ros:humble-desktop` | colcon · rosdep · Isaac Sim ROS 워크스페이스 · `humble_ws` 빌드 · **Fast DDS 설정**(`fastdds.xml`, `ROS_DOMAIN_ID=0`) |

**통신**: 두 컨테이너 모두 **`--net=host`** 로 호스트 네트워크 공유 → *"ROS 2 DDS 통신이 즉시 작동하며 추가 설정이 필요 없다"*

### ★ 우리와 다른 점: 우리가 더 유리하다

그 사람은 `nvidia/cuda` 베이스에 **Isaac Sim을 직접 설치**했다. 우리는 그럴 필요가 없다:

```
nvcr.io/nvidia/isaac-sim:5.1.0     ← 우리 버전과 일치
nvcr.io/nvidia/isaac-lab:2.3.2     ← 우리가 고정한 태그와 일치
```

공식 이미지가 있으므로 **Isaac Sim 쪽 컨테이너는 직접 빌드하지 않는다.** ROS2 쪽만 `osrf/ros:humble-desktop` 방식을 참고하면 된다. (근거: `cloud-gpu-options.md` §4)

### 호스트 우분투 버전에 주는 함의

컨테이너로 분리하면 **호스트 우분투 버전의 제약이 크게 줄어든다.** 컨테이너는 자기 파일시스템과 파이썬을 갖기 때문이다.
⚠️ 단 **커널은 호스트와 공유**하므로 GPU 드라이버·커널 버전은 여전히 호스트 것을 쓴다.

**그럼에도 22.04를 택했다. 기술이 아니라 수업 때문이다.**
8/10~14 ROS 보충수업이 **Ubuntu 22.04 + Humble 기준**(1일차 Docker 실습 포함)이고, PinkLAB 강의도 22.04다.
**강의와 환경이 다르면 5일 내내 다른 문제로 시간을 쓴다.**

**ISO 준비 완료**: `C:\Driver\ubuntu-22.04.5-desktop-amd64.iso` (4.44GB)
SHA256 **공식 대조 일치 확인**: `bfd1cee02bc4f35db939e69b934ba49a39a378797ce9aee20f6e3e3e728fefbf`
